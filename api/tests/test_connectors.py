"""ADR-013 fase 1b: het register van de bronconnectors.

Welke connectors er bestaan, staat in de code; het register zegt alleen aan of uit, per beheerder mét 2FA, en
elke wijziging is een auditregel. Graph-qa leest `GET /v1/connectors`.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

_ADMIN = {"Authorization": "Bearer admin-token"}
_BEHEERDER = {**_ADMIN, "X-User-Id": "gebruiker-a"}
_ZONDER_2FA = {**_ADMIN, "X-User-Id": "gebruiker-b"}


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    monkeypatch.setenv("WETSANALYSE_ADMIN_TOKENS", "adm:admin-token")
    from sqlalchemy import update

    from app import db, ratelimit
    from app.config import get_settings
    from app.routers.auth import vergeet_actief
    from conftest import maak_testgebruikers

    get_settings.cache_clear()
    ratelimit.reset()
    vergeet_actief()
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    await db.reconcile_schema()
    await maak_testgebruikers("gebruiker-a", "gebruiker-b")
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.users).where(db.users.c.userid == "gebruiker-a").values(totp_enabled=True))
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    get_settings.cache_clear()
    await db.dispose_engine()


async def test_een_bekende_connector_staat_uit_tot_de_beheerder_hem_aanzet(client):
    r = await client.get("/v1/admin/connectors", headers=_ADMIN)
    assert r.status_code == 200
    [kst] = r.json()
    assert (kst["naam"], kst["brontype"], kst["aan"]) == ("kamerstukken", "kamerstuk", False)
    assert (await client.get("/v1/connectors")).json() == {"aan": []}

    r = await client.put("/v1/admin/connectors/kamerstukken", json={"aan": True}, headers=_BEHEERDER)
    assert r.status_code == 200 and r.json()["aan"] and r.json()["door"] == "gebruiker-a"
    assert (await client.get("/v1/connectors")).json() == {"aan": ["kamerstukken"]}


async def test_elke_wijziging_is_een_auditregel_en_dubbel_aanzetten_niet(client):
    for aan in (True, True, False):
        await client.put("/v1/admin/connectors/kamerstukken", json={"aan": aan}, headers=_BEHEERDER)
    regels = (await client.get("/v1/admin/connectors/kamerstukken/audit", headers=_ADMIN)).json()
    assert [(r["actie"], r["door"]) for r in regels] == [("uit", "gebruiker-a"), ("aan", "gebruiker-a")]


async def test_zonder_2fa_of_zonder_admin_geen_wijziging(client):
    r = await client.put("/v1/admin/connectors/kamerstukken", json={"aan": True}, headers=_ZONDER_2FA)
    assert r.status_code == 403
    r = await client.put("/v1/admin/connectors/kamerstukken", json={"aan": True}, headers={"X-User-Id": "gebruiker-a"})
    assert r.status_code == 401
    assert (await client.get("/v1/connectors")).json() == {"aan": []}


async def test_onbekende_connector(client):
    r = await client.put("/v1/admin/connectors/confluence", json={"aan": True}, headers=_BEHEERDER)
    assert r.status_code == 404
    r = await client.put("/v1/admin/connectors/kamerstukken", json={"aan": True, "url": "x"}, headers=_BEHEERDER)
    assert r.status_code == 422
