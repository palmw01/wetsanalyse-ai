"""Tests voor het berichtensysteem: service (berichten + leesbewijzen) en router-autorisatie."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def db():
    from app import db as _db

    _db.init_engine("sqlite+aiosqlite://")
    await _db.create_all()
    try:
        yield _db
    finally:
        await _db.dispose_engine()


@pytest.fixture
async def client(monkeypatch):
    """ASGI-client met cliënt- én admin-auth, geen netwerk."""
    monkeypatch.setenv("WETSANALYSE_ADMIN_TOKENS", "adm:admin-token")
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")

    from app import db, ratelimit
    from app.config import get_settings
    from app.deps import get_store

    get_settings.cache_clear()
    get_store.cache_clear()
    ratelimit.reset()
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()

    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    get_store.cache_clear()
    await db.dispose_engine()


_ADM = {"Authorization": "Bearer admin-token"}
_CLI = {}  # auth_required=0 → elk verzoek zonder token wordt doorgelaten als client


# --- service: basis CRUD -------------------------------------------------------

async def test_maak_en_lijst(db):
    from app import berichten as svc

    row = await svc.maak_bericht("Titel", "Inhoud", "info", None, "adm")
    assert row["id"] is not None
    assert row["gepubliceerd"] is False
    assert row["type"] == "info"

    alle = await svc.list_alle_berichten()
    assert any(r["id"] == row["id"] for r in alle)


async def test_publiceer_en_zichtbaar_voor_analist(db):
    from app import berichten as svc

    row = await svc.maak_bericht("Update", "Iets nieuws.", "update", "v1.0", "adm")
    bericht_id = row["id"]

    # Ongepubliceerd → niet zichtbaar voor analist.
    assert await svc.list_berichten("user1") == []

    await svc.set_gepubliceerd(bericht_id, True)

    berichten = await svc.list_berichten("user1")
    assert len(berichten) == 1
    assert berichten[0]["gelezen"] is False


async def test_ongelezen_aantal_basis(db):
    from app import berichten as svc
    from app import db as _db
    from sqlalchemy import insert
    from app.db import utcnow

    # Maak een user-rij aan (nodig voor de created-subquery in ongelezen_aantal).
    async with _db.get_engine().begin() as conn:
        await conn.execute(insert(_db.users).values(
            userid="u1", email="u1@test.nl", password_hash="x",
            role="analist", active=True, created=utcnow(), updated=utcnow(),
        ))

    assert await svc.ongelezen_aantal("u1") == 0

    row = await svc.maak_bericht("Bericht", "Tekst", "info", None, "adm")
    await svc.set_gepubliceerd(row["id"], True)

    assert await svc.ongelezen_aantal("u1") == 1

    await svc.markeer_alles_gelezen("u1")
    assert await svc.ongelezen_aantal("u1") == 0


async def test_markeer_alles_gelezen_is_idempotent(db):
    from app import berichten as svc

    row = await svc.maak_bericht("B", "T", "info", None, "adm")
    await svc.set_gepubliceerd(row["id"], True)

    # Twee keer aanroepen mag geen fout geven.
    await svc.markeer_alles_gelezen("u1")
    await svc.markeer_alles_gelezen("u1")


async def test_verwijder_cascade_leesbewijzen(db):
    from app import berichten as svc
    from app import db as _db
    from sqlalchemy import select

    row = await svc.maak_bericht("B", "T", "info", None, "adm")
    await svc.set_gepubliceerd(row["id"], True)
    await svc.markeer_alles_gelezen("u1")

    # Leesbewijs bestaat.
    async with _db.get_engine().connect() as conn:
        cnt = await conn.scalar(
            select(_db.bericht_leesbewijzen)
            .where(_db.bericht_leesbewijzen.c.bericht_id == row["id"])
        )
    assert cnt is not None

    await svc.verwijder_bericht(row["id"])

    # Leesbewijs is mee verwijderd.
    async with _db.get_engine().connect() as conn:
        cnt2 = await conn.scalar(
            select(_db.bericht_leesbewijzen)
            .where(_db.bericht_leesbewijzen.c.bericht_id == row["id"])
        )
    assert cnt2 is None


async def test_verwijder_onbekend_gooit_error(db):
    from app import berichten as svc

    with pytest.raises(svc.BerichtError):
        await svc.verwijder_bericht(9999)


# --- router: autorisatie -------------------------------------------------------

async def test_analist_mag_geen_admin_berichten(client):
    # Zonder admin-token → 401.
    r = await client.get("/v1/admin/berichten")
    assert r.status_code == 401


async def test_admin_maak_en_publiceer(client):
    r = await client.post(
        "/v1/admin/berichten",
        headers=_ADM,
        json={"titel": "Titel", "inhoud": "Inhoud.", "type": "update"},
    )
    assert r.status_code == 201
    bericht_id = r.json()["id"]

    r = await client.patch(
        f"/v1/admin/berichten/{bericht_id}/publicatie",
        headers=_ADM,
        json={"gepubliceerd": True},
    )
    assert r.status_code == 200
    assert r.json()["gepubliceerd"] is True


async def test_analist_ziet_gepubliceerd_bericht(client):
    # Maak + publiceer via admin.
    r = await client.post(
        "/v1/admin/berichten",
        headers=_ADM,
        json={"titel": "Nieuw", "inhoud": "Tekst.", "type": "info"},
    )
    bericht_id = r.json()["id"]
    await client.patch(
        f"/v1/admin/berichten/{bericht_id}/publicatie",
        headers=_ADM,
        json={"gepubliceerd": True},
    )

    # Analist haalt lijst op.
    r = await client.get("/v1/berichten", headers={"X-User-Id": "u1"})
    assert r.status_code == 200
    ids = [b["id"] for b in r.json()]
    assert bericht_id in ids
