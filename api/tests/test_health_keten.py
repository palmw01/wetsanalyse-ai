"""De ketenrooktest van de api: `GET /health?keten=1` zegt of de database antwoordt (plan Lex Bench §20.5 stap 5).
Zonder parameter blijft `/health` de lichte liveness, zonder database."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app import db

pytestmark = pytest.mark.risico("R02")


@pytest.fixture
async def client():
    db.init_engine("sqlite+aiosqlite://")
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    await db.dispose_engine()


async def test_met_keten_en_een_werkende_database_ok(client):
    r = await client.get("/health?keten=1")
    assert r.status_code == 200 and r.json()["database"] == "ok"


async def test_met_keten_en_een_database_die_faalt_503(client, monkeypatch):
    class Weg:
        def connect(self):
            raise OSError("database weg")

    monkeypatch.setattr(db, "get_engine", lambda: Weg())
    r = await client.get("/health?keten=1")
    assert r.status_code == 503 and r.json()["database"] == "onbereikbaar" and r.json()["status"] == "onvolledig"


async def test_zonder_keten_raakt_de_liveness_de_database_niet(client, monkeypatch):
    def niet():
        raise AssertionError("de liveness mag de database niet vragen")

    monkeypatch.setattr(db, "get_engine", niet)
    r = await client.get("/health")
    assert r.status_code == 200 and "database" not in r.json()
