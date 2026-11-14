"""Het agent-token komt niet op een beslissingsroute, en de audit zegt welke client schreef (G6)."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

AGENT = {"Authorization": "Bearer agent-token", "X-User-Id": "user1"}
WEBAPP = {"Authorization": "Bearer webapp-token", "X-User-Id": "user1"}


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite://")
    monkeypatch.setenv("WETSANALYSE_API_TOKENS", "graph-qa:agent-token,frontend:webapp-token")
    from app import db, ratelimit
    from app.config import get_settings

    get_settings.cache_clear()
    ratelimit.reset()
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    await db.reconcile_schema()
    from conftest import maak_testgebruikers
    await maak_testgebruikers("user1")
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await db.dispose_engine()
    get_settings.cache_clear()


async def test_het_agent_token_beslist_niet(client):
    for pad in ("/v1/annotatie/elementen/e1/beslissing", "/v1/annotatie/lagen/l1/status",
                "/v1/werkgebieden/w1/begrippen/b1/accorderen"):
        res = await client.post(pad, headers=AGENT, json={})
        assert res.status_code == 403, pad
    # Dezelfde route met het token van de webapp komt wel langs de autorisatie (en faalt daarna inhoudelijk).
    assert (await client.post("/v1/annotatie/elementen/e1/beslissing", headers=WEBAPP, json={})).status_code != 403


async def test_een_route_van_de_agent_mag_wel(client):
    assert (await client.get("/v1/begrippen", headers=AGENT)).status_code == 200


async def test_de_audit_noemt_de_client(client):
    from app import db

    res = await client.post("/v1/werkgebieden", headers=WEBAPP, json={"naam": "Proef", "analysevraag": "Wat?"})
    assert res.status_code in (200, 201), res.text
    async with db.get_engine().connect() as conn:
        clients = (await conn.execute(select(db.werkgebied_audit.c.client))).scalars().all()
    assert clients and set(clients) == {"frontend"}


async def test_het_agent_token_maakt_alleen_een_deelgesprek_van_een_lopende_delegatie(client):
    """ADR-012, ADR-016 §A5: Lex maakt deelgesprekken onder een delegatie, en niets anders, voor de gebruiker ervan."""
    from conftest import maak_testgebruikers
    await maak_testgebruikers("user2")
    wg = (await client.post("/v1/werkgebieden", headers=WEBAPP, json={"naam": "Regie", "analysevraag": "Wat?"})).json()
    ouder = (await client.post("/v1/gesprekken", headers=WEBAPP, json={"werkgebied_id": wg["id"]})).json()
    regie = (await client.post("/v1/delegaties", headers=AGENT, json={
        "werkgebied_id": wg["id"], "gesprek_id": ouder["id"], "opdracht": "bronnen",
        "plan_id": "0123456789abcdef"})).json()
    kind = {"titel": "Bronnen · deelvraag 1", "werkgebied_id": wg["id"], "ouder_id": ouder["id"],
            "delegatie_id": regie["id"]}

    res = await client.post("/v1/gesprekken", headers=AGENT, json=kind)
    assert res.status_code == 201, res.text
    assert (res.json()["ouder_id"], res.json()["user_id"]) == (ouder["id"], "user1")
    # Een los gesprek, of een gesprek zonder regie, maakt het agent-token niet; de webapp wel.
    for body in ({"titel": "Los"}, {"werkgebied_id": wg["id"]}, {**kind, "delegatie_id": ""}):
        res = await client.post("/v1/gesprekken", headers=AGENT, json=body)
        assert res.status_code == 403 and res.json()["detail"]["fout"] == "alleen_deelgesprek", (body, res.text)
    assert (await client.post("/v1/gesprekken", headers=WEBAPP, json={"titel": "Los"})).status_code == 201
    # Namens een andere gebruiker: de ouder en de regie zijn niet van hem.
    ander = {**AGENT, "X-User-Id": "user2"}
    assert (await client.post("/v1/gesprekken", headers=ander, json=kind)).status_code == 404
    # Na afloop van de regie geen nieuwe deelgesprekken meer.
    await client.patch(f"/v1/delegaties/{regie['id']}", headers=AGENT, json={"status": "klaar"})
    res = await client.post("/v1/gesprekken", headers=AGENT, json=kind)
    assert res.status_code == 409 and res.json()["detail"]["fout"] == "delegatie_afgerond"
