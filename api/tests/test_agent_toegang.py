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
