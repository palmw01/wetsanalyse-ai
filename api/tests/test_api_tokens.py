"""Tests voor genereerbare API-tokens: de service (alleen-hash-opslag, verify/revoke) en de
admin-auth via een DB-token (naast de statische env-admin-tokens). Geen netwerk."""

from __future__ import annotations

import hashlib

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select


@pytest.fixture
async def db():
    from app import db as _db

    _db.init_engine("sqlite+aiosqlite://")
    await _db.create_all()
    try:
        yield _db
    finally:
        await _db.dispose_engine()


# --- service -------------------------------------------------------------------

async def test_create_slaat_alleen_hash_op(db):
    from app import api_tokens

    record, plaintext = await api_tokens.create("mijn-mcp", created_by="adm")
    assert plaintext.startswith("wa_admin_")
    assert record["label"] == "mijn-mcp"
    assert record["token_prefix"] == plaintext[:16]
    assert "token" not in record and "token_hash" not in record  # geen geheim in het record
    # In de DB staat de sha256-hash, niet de plaintext.
    async with db.get_engine().connect() as conn:
        row = (await conn.execute(select(db.api_tokens))).mappings().first()
    assert row["token_hash"] == hashlib.sha256(plaintext.encode()).hexdigest()
    assert plaintext not in str(dict(row))


async def test_verify_accepteert_geldig_en_werkt_last_used_bij(db):
    from app import api_tokens

    _, plaintext = await api_tokens.create("x")
    assert (await api_tokens.list_tokens())[0]["last_used"] is None
    assert await api_tokens.verify(plaintext) == "apitoken:x"
    assert (await api_tokens.list_tokens())[0]["last_used"] is not None


async def test_verify_blijft_geldig_als_last_used_write_faalt(db, monkeypatch):
    """De `last_used`-bijwerking is best-effort en ontkoppeld van de auth-beslissing: faalt de write,
    dan blijft een geldig token toch geaccepteerd (geen 401 door een metadata-hapering)."""
    from app import api_tokens

    _, plaintext = await api_tokens.create("x")

    async def kapotte_touch(_token_id):
        raise RuntimeError("DB-hapering tijdens metadata-write")

    monkeypatch.setattr(api_tokens, "_touch_last_used", kapotte_touch)
    assert await api_tokens.verify(plaintext) == "apitoken:x"


async def test_verify_weigert_onbekend_leeg_en_ingetrokken(db):
    from app import api_tokens

    assert await api_tokens.verify(None) is None
    assert await api_tokens.verify("zonder-prefix") is None
    assert await api_tokens.verify("wa_admin_nietbestaand") is None
    record, plaintext = await api_tokens.create("revoke-me")
    await api_tokens.revoke(record["id"])
    assert await api_tokens.verify(plaintext) is None


async def test_revoke_onbekend_faalt(db):
    from app import api_tokens

    with pytest.raises(api_tokens.ApiTokenError):
        await api_tokens.revoke("bestaat-niet")


# --- admin-auth via de API -----------------------------------------------------

@pytest.fixture
async def admin_client(monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("WETSANALYSE_ADMIN_TOKENS", "adm:admin-token")
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    monkeypatch.setenv("LLM_CONFIG_SECRET", Fernet.generate_key().decode())

    from app import db, ratelimit
    from app.config import get_settings

    get_settings.cache_clear()
    ratelimit.reset()
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()

    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    await db.dispose_engine()


_ENV = {"Authorization": "Bearer admin-token"}


async def test_genereer_gebruik_en_intrek_token(admin_client):
    # 1. Genereer via het env-admin-token (bootstrap-pad).
    r = await admin_client.post("/v1/admin/api-tokens", headers=_ENV, json={"label": "mcp"})
    assert r.status_code == 201
    body = r.json()
    token, tid = body["token"], body["id"]
    assert token.startswith("wa_admin_")

    # 2. De lijst toont het token zonder plaintext/hash.
    lijst = (await admin_client.get("/v1/admin/api-tokens", headers=_ENV)).json()
    entry = next(t for t in lijst if t["id"] == tid)
    assert entry["label"] == "mcp" and entry["active"] is True
    assert "token" not in entry and "token_hash" not in entry

    # 3. Het gegenereerde token werkt als admin-bearer (het DB-pad in require_admin).
    db_h = {"Authorization": f"Bearer {token}"}
    assert (await admin_client.get("/v1/admin/profiles", headers=db_h)).status_code == 200

    # 4. Na intrekken werkt het token niet meer.
    assert (await admin_client.delete(f"/v1/admin/api-tokens/{tid}", headers=_ENV)).status_code == 204
    assert (await admin_client.get("/v1/admin/profiles", headers=db_h)).status_code == 401


async def test_ongeldig_token_blijft_401(admin_client):
    assert (await admin_client.get(
        "/v1/admin/api-tokens", headers={"Authorization": "Bearer wa_admin_fout"}
    )).status_code == 401


# --- accounttokens -------------------------------------------------------------

@pytest.fixture
async def analist(db):
    from app import users

    user, _ = await users.create_user("analist1", "analist1@example.org")
    return user


async def test_accounttoken_geeft_het_account(analist):
    from app import api_tokens

    record, plaintext = await api_tokens.create_gebruiker("mcp", "analist1", created_by="adm")
    assert plaintext.startswith("wa_pat_")
    assert record["scope"] == "gebruiker" and record["userid"] == "analist1"
    assert record["verloopt"] > record["created"]
    gevonden = await api_tokens.verify_gebruiker(plaintext)
    assert gevonden == {"token_id": record["id"], "userid": "analist1",
                        "email": "analist1@example.org", "role": "analist"}
    assert (await api_tokens.list_tokens())[0]["last_used"] is not None


async def test_accounttoken_en_admin_token_kruisen_niet(analist):
    """Het prefix alleen is niet genoeg: ook een accounttoken met het admin-prefix opent `verify` niet."""
    from app import api_tokens

    _, acc = await api_tokens.create_gebruiker("mcp", "analist1")
    _, adm = await api_tokens.create("adm")
    assert await api_tokens.verify(acc) is None
    assert await api_tokens.verify_gebruiker(adm) is None

    vermomd = "wa_admin_vermomd"
    record, _ = await api_tokens.create_gebruiker("x", "analist1")
    async with api_tokens.db.get_engine().begin() as conn:
        await conn.execute(api_tokens.db.api_tokens.update().where(
            api_tokens.db.api_tokens.c.id == record["id"]).values(token_hash=hashlib.sha256(vermomd.encode()).hexdigest()))
    assert await api_tokens.verify(vermomd) is None


async def test_accounttoken_voor_onbekend_of_inactief_account(analist):
    from app import api_tokens, users

    with pytest.raises(api_tokens.ApiTokenError):
        await api_tokens.create_gebruiker("x", "bestaat-niet")
    await users.patch_user("analist1", active=False)
    with pytest.raises(api_tokens.ApiTokenError):
        await api_tokens.create_gebruiker("x", "analist1")


async def test_ingetrokken_verlopen_en_gedeactiveerd_gelden_niet(analist):
    from datetime import timedelta

    from app import api_tokens, users
    from app.user import _utcnow

    ingetrokken, a = await api_tokens.create_gebruiker("a", "analist1")
    verlopen, b = await api_tokens.create_gebruiker("b", "analist1")
    actief, c = await api_tokens.create_gebruiker("c", "analist1")

    await api_tokens.revoke(ingetrokken["id"])
    async with api_tokens.db.get_engine().begin() as conn:
        await conn.execute(api_tokens.db.api_tokens.update().where(
            api_tokens.db.api_tokens.c.id == verlopen["id"]).values(verloopt=_utcnow() - timedelta(seconds=1)))

    assert await api_tokens.verify_gebruiker(a) is None
    assert await api_tokens.verify_gebruiker(b) is None
    assert not await api_tokens.gebruiker_geldig(ingetrokken["id"])
    assert not await api_tokens.gebruiker_geldig(verlopen["id"])
    assert await api_tokens.gebruiker_geldig(actief["id"])

    await users.patch_user("analist1", active=False)
    assert await api_tokens.verify_gebruiker(c) is None
    assert not await api_tokens.gebruiker_geldig(actief["id"])
    assert not await api_tokens.gebruiker_geldig("onbekend")


async def test_nieuw_account_erft_geen_tokens_van_het_oude(analist):
    from app import api_tokens, users

    _, plaintext = await api_tokens.create_gebruiker("x", "analist1")
    await users.delete_user("analist1")
    assert await api_tokens.verify_gebruiker(plaintext) is None
    # Een nieuw account krijgt de userid niet eens meer (B3), en de tokens blijven ook dan dood.
    with pytest.raises(users.UserError):
        await users.create_user("analist1", "ander@example.org")
    assert await api_tokens.verify_gebruiker(plaintext) is None


@pytest.fixture
async def token_client(monkeypatch, admin_client):
    from app import users
    from app.config import get_settings

    monkeypatch.setenv("API_TOKEN_LOGIN", "true")
    get_settings.cache_clear()
    await users.create_user("analist1", "analist1@example.org")
    yield admin_client
    get_settings.cache_clear()


async def test_inwisselen_en_hercontrole(token_client):
    gemaakt = await token_client.post("/v1/admin/api-tokens", headers=_ENV, json={"label": "mcp", "userid": "analist1"})
    assert gemaakt.status_code == 201
    body = gemaakt.json()
    assert body["scope"] == "gebruiker" and body["userid"] == "analist1" and body["verloopt"]

    res = await token_client.post("/v1/auth/api-token/verify", json={"token": body["token"]})
    assert res.json() == {"ok": True, "token_id": body["id"], "userid": "analist1",
                          "email": "analist1@example.org", "role": "analist"}
    assert (await token_client.get(f"/v1/auth/api-token/{body['id']}/status")).status_code == 204

    await token_client.delete(f"/v1/admin/api-tokens/{body['id']}", headers=_ENV)
    res = await token_client.post("/v1/auth/api-token/verify", json={"token": body["token"]})
    assert res.status_code == 200 and res.json()["ok"] is False
    assert (await token_client.get(f"/v1/auth/api-token/{body['id']}/status")).status_code == 401


async def test_accounttoken_opent_de_admin_api_niet(token_client):
    token = (await token_client.post("/v1/admin/api-tokens", headers=_ENV,
                                     json={"userid": "analist1"})).json()["token"]
    res = await token_client.get("/v1/admin/api-tokens", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


async def test_onbekend_account_is_422(token_client):
    res = await token_client.post("/v1/admin/api-tokens", headers=_ENV, json={"userid": "bestaat-niet"})
    assert res.status_code == 422


async def test_zonder_de_vlag_bestaat_inloggen_met_token_niet(admin_client):
    from app import users

    await users.create_user("analist1", "analist1@example.org")
    res = await admin_client.post("/v1/admin/api-tokens", headers=_ENV, json={"userid": "analist1"})
    assert res.status_code == 409
    assert (await admin_client.post("/v1/auth/api-token/verify", json={"token": "wa_pat_x"})).status_code == 404
    assert (await admin_client.get("/v1/auth/api-token/abc/status")).status_code == 404
