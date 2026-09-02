"""Tests voor zelfregistratie met beheerdersgoedkeuring.

Een bezoeker vraagt toegang aan (`POST /v1/auth/registratie`), een beheerder beslist
(`/v1/admin/registraties/*`). Pas bij goedkeuring ontstaat er een account – met het wachtwoord dat
de aanvrager zelf koos, zodat er geen tijdelijk wachtwoord hoeft te worden rondgestuurd.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


def _fresh_settings(monkeypatch, **env):
    """Zet env, leeg de gecachte settings/crypto, en geef verse Settings terug."""
    from cryptography.fernet import Fernet

    from app import secrets_crypto
    from app.config import get_settings

    env.setdefault("LLM_CONFIG_SECRET", Fernet.generate_key().decode())
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    secrets_crypto._fernet.cache_clear()
    return get_settings()


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
    _fresh_settings(
        monkeypatch,
        WETSANALYSE_ADMIN_TOKENS="adm:admin-token",
        WETSANALYSE_AUTH_REQUIRED="0",
    )
    from app import db, ratelimit

    ratelimit.reset()
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()

    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    await db.dispose_engine()


_ADMIN = {"Authorization": "Bearer admin-token"}


def _aanvraag(voornaam="Willard", achternaam="Palm", email="w@example.com", wachtwoord="geheim123"):
    return {
        "voornaam": voornaam, "achternaam": achternaam,
        "email": email, "password": wachtwoord,
    }


# --- userid-afleiding ----------------------------------------------------------

def test_userid_vorm():
    from app.registraties import leid_userid_af

    # Vier letters achternaam + eerste letter voornaam + tweecijferig volgnummer.
    assert leid_userid_af("Willard", "Palm") == "palmw01"
    assert leid_userid_af("Willard", "Palm", 2) == "palmw02"
    assert leid_userid_af("Anne", "Vandenberg") == "vanda01"


def test_userid_diakrieten_en_leestekens():
    from app.registraties import leid_userid_af

    assert leid_userid_af("José", "Müller") == "mullj01"
    assert leid_userid_af("Jan-Peter", "de Vries") == "devrj01"
    assert leid_userid_af("Ïñes", "O'Brien") == "obrii01"


def test_userid_korte_naam_blijft_geldig():
    from app.registraties import leid_userid_af
    from app.users import _USERID_RE

    kort = leid_userid_af("Wu", "Li")
    assert kort == "liw01"
    # De userid-regex eist minstens drie tekens; het volgnummer haalt dat altijd.
    assert _USERID_RE.match(kort)


def test_userid_zonder_bruikbare_letters():
    from app.registraties import leid_userid_af
    from app.users import UserError

    with pytest.raises(UserError):
        leid_userid_af("!!!", "???")


async def test_userid_volgnummer_loopt_op(db):
    from app import registraties

    eerste = await registraties.maak_aanvraag("Willard", "Palm", "a@example.com", "geheim123")
    tweede = await registraties.maak_aanvraag("Wendy", "Palmer", "b@example.com", "geheim123")
    assert eerste.userid_voorstel == "palmw01"
    assert tweede.userid_voorstel == "palmw02"


async def test_userid_wijkt_uit_voor_bestaand_account(db):
    from app import registraties, users

    await users.bootstrap_admin("palmw01", "baas@example.com", "wachtwoord1")
    aanvraag = await registraties.maak_aanvraag("Willard", "Palm", "w@example.com", "geheim123")
    assert aanvraag.userid_voorstel == "palmw02"


async def test_afgewezen_aanvraag_geeft_volgnummer_vrij(db):
    from app import registraties

    eerste = await registraties.maak_aanvraag("Willard", "Palm", "a@example.com", "geheim123")
    await registraties.wijs_af(eerste.id, reden="test")
    tweede = await registraties.maak_aanvraag("Wendy", "Palmer", "b@example.com", "geheim123")
    assert tweede.userid_voorstel == "palmw01"


# --- aanvragen -----------------------------------------------------------------

async def test_aanvraag_maakt_geen_account(client):
    r = await client.post("/v1/auth/registratie", json=_aanvraag())
    assert r.status_code == 201
    assert r.json() == {"userid": "palmw01", "status": "aangevraagd"}

    # Nog geen account: de setup-route staat dus nog open en /verify weigert.
    assert (await client.get("/v1/auth/setup-status")).json()["needs_setup"] is True
    assert (await client.get("/v1/admin/users", headers=_ADMIN)).json() == []


async def test_aanvraag_dubbel_emailadres(client):
    assert (await client.post("/v1/auth/registratie", json=_aanvraag())).status_code == 201
    r = await client.post(
        "/v1/auth/registratie", json=_aanvraag(voornaam="Willemijn", achternaam="Palmboom")
    )
    assert r.status_code == 409


async def test_aanvraag_op_bestaand_emailadres_van_account(client):
    await client.post(
        "/v1/auth/setup",
        json={"userid": "baas", "email": "boss@example.com", "password": "wachtwoord1"},
    )
    r = await client.post("/v1/auth/registratie", json=_aanvraag(email="boss@example.com"))
    assert r.status_code == 409


async def test_aanvraag_kort_wachtwoord(client):
    r = await client.post("/v1/auth/registratie", json=_aanvraag(wachtwoord="kort"))
    assert r.status_code == 422  # min_length op het Pydantic-model


async def test_aanvraag_rate_limit(client):
    from app import ratelimit

    # De per-e-mail-bucket staat drie pogingen toe; de vierde loopt tegen 429.
    for i in range(3):
        await client.post("/v1/auth/registratie", json=_aanvraag(email="spam@example.com"))
    r = await client.post("/v1/auth/registratie", json=_aanvraag(email="spam@example.com"))
    assert r.status_code == 429
    ratelimit.reset()


# --- beoordelen ----------------------------------------------------------------

async def test_goedkeuren_maakt_inlogbaar_account(client):
    await client.post("/v1/auth/registratie", json=_aanvraag())
    lijst = (await client.get("/v1/admin/registraties", headers=_ADMIN)).json()
    assert len(lijst) == 1 and lijst[0]["status"] == "aangevraagd"
    aanvraag_id = lijst[0]["id"]

    r = await client.post(
        f"/v1/admin/registraties/{aanvraag_id}/goedkeuren", json={"role": "analist"}, headers=_ADMIN
    )
    assert r.status_code == 200
    assert r.json()["userid"] == "palmw01" and r.json()["role"] == "analist"

    # Inloggen met het ZELF gekozen wachtwoord – geen tijdelijk wachtwoord nodig.
    v = await client.post("/v1/auth/verify", json={"userid": "palmw01", "password": "geheim123"})
    assert v.status_code == 200 and v.json()["ok"] is True


async def test_goedkeuren_met_gecorrigeerde_userid_en_rol(client):
    await client.post("/v1/auth/registratie", json=_aanvraag())
    aanvraag_id = (await client.get("/v1/admin/registraties", headers=_ADMIN)).json()[0]["id"]

    r = await client.post(
        f"/v1/admin/registraties/{aanvraag_id}/goedkeuren",
        json={"userid": "w.palm", "role": "beheerder"}, headers=_ADMIN,
    )
    assert r.status_code == 200 and r.json()["userid"] == "w.palm"

    v = await client.post("/v1/auth/verify", json={"userid": "w.palm", "password": "geheim123"})
    assert v.json()["ok"] is True and v.json()["role"] == "beheerder"


async def test_goedkeuren_botsende_userid_geeft_409(client):
    await client.post(
        "/v1/auth/setup",
        json={"userid": "bezet", "email": "boss@example.com", "password": "wachtwoord1"},
    )
    await client.post("/v1/auth/registratie", json=_aanvraag())
    aanvraag_id = (await client.get("/v1/admin/registraties", headers=_ADMIN)).json()[0]["id"]

    r = await client.post(
        f"/v1/admin/registraties/{aanvraag_id}/goedkeuren", json={"userid": "bezet"}, headers=_ADMIN
    )
    assert r.status_code == 409
    # De aanvraag blijft open, dus de beheerder kan het opnieuw proberen.
    assert (await client.get("/v1/admin/registraties?status=aangevraagd", headers=_ADMIN)).json()


async def test_tweemaal_goedkeuren_geeft_409(client):
    await client.post("/v1/auth/registratie", json=_aanvraag())
    aanvraag_id = (await client.get("/v1/admin/registraties", headers=_ADMIN)).json()[0]["id"]

    assert (await client.post(
        f"/v1/admin/registraties/{aanvraag_id}/goedkeuren", json={}, headers=_ADMIN
    )).status_code == 200
    assert (await client.post(
        f"/v1/admin/registraties/{aanvraag_id}/goedkeuren", json={}, headers=_ADMIN
    )).status_code == 409


async def test_afwijzen_met_reden(client):
    await client.post("/v1/auth/registratie", json=_aanvraag())
    aanvraag_id = (await client.get("/v1/admin/registraties", headers=_ADMIN)).json()[0]["id"]

    r = await client.post(
        f"/v1/admin/registraties/{aanvraag_id}/afwijzen",
        json={"reden": "geen testgebruiker"}, headers=_ADMIN,
    )
    assert r.status_code == 204

    rij = (await client.get("/v1/admin/registraties", headers=_ADMIN)).json()[0]
    assert rij["status"] == "afgewezen" and rij["reden"] == "geen testgebruiker"
    assert (await client.get("/v1/admin/users", headers=_ADMIN)).json() == []


async def test_bulk_goedkeuren_is_best_effort(client):
    await client.post("/v1/auth/registratie", json=_aanvraag(email="a@example.com"))
    await client.post(
        "/v1/auth/registratie",
        json=_aanvraag(voornaam="Wendy", achternaam="Palmer", email="b@example.com"),
    )
    ids = [r["id"] for r in (await client.get("/v1/admin/registraties", headers=_ADMIN)).json()]

    r = await client.post(
        "/v1/admin/registraties/goedkeuren",
        json={"ids": ids + [9999], "role": "analist"}, headers=_ADMIN,
    )
    assert r.status_code == 200
    regels = r.json()
    assert [x["ok"] for x in regels] == [True, True, False]
    assert {x["userid"] for x in regels if x["ok"]} == {"palmw01", "palmw02"}


async def test_verwijderen_geeft_emailadres_vrij(client):
    await client.post("/v1/auth/registratie", json=_aanvraag())
    aanvraag_id = (await client.get("/v1/admin/registraties", headers=_ADMIN)).json()[0]["id"]
    await client.post(f"/v1/admin/registraties/{aanvraag_id}/afwijzen", json={}, headers=_ADMIN)

    assert (await client.post("/v1/auth/registratie", json=_aanvraag())).status_code == 409
    assert (await client.delete(
        f"/v1/admin/registraties/{aanvraag_id}", headers=_ADMIN
    )).status_code == 204
    assert (await client.post("/v1/auth/registratie", json=_aanvraag())).status_code == 201


async def test_admin_endpoints_vereisen_token(client):
    assert (await client.get("/v1/admin/registraties")).status_code == 401
    assert (await client.post("/v1/admin/registraties/1/goedkeuren", json={})).status_code == 401


# --- statusmelding bij het inloggen --------------------------------------------

async def test_inloggen_toont_openstaande_aanvraag(client):
    await client.post("/v1/auth/registratie", json=_aanvraag())

    r = await client.post("/v1/auth/verify", json={"userid": "palmw01", "password": "geheim123"})
    assert r.status_code == 200
    assert r.json()["ok"] is False and r.json()["code"] == "aanvraag_open"


async def test_inloggen_toont_afwijzing(client):
    await client.post("/v1/auth/registratie", json=_aanvraag())
    aanvraag_id = (await client.get("/v1/admin/registraties", headers=_ADMIN)).json()[0]["id"]
    await client.post(f"/v1/admin/registraties/{aanvraag_id}/afwijzen", json={}, headers=_ADMIN)

    r = await client.post("/v1/auth/verify", json={"userid": "palmw01", "password": "geheim123"})
    assert r.json()["ok"] is False and r.json()["code"] == "aanvraag_afgewezen"


async def test_verkeerd_wachtwoord_lekt_de_aanvraag_niet(client):
    """De status is alleen zichtbaar bij het juiste wachtwoord – anders is dit een middel om te
    ontdekken wie er een aanvraag heeft liggen."""
    await client.post("/v1/auth/registratie", json=_aanvraag())

    r = await client.post("/v1/auth/verify", json={"userid": "palmw01", "password": "mis"})
    assert r.json()["code"] == "invalid"


async def test_onbekende_userid_blijft_invalid(client):
    r = await client.post("/v1/auth/verify", json={"userid": "niemand", "password": "geheim123"})
    assert r.json()["code"] == "invalid"


async def test_gedeactiveerd_account_blijft_invalid(client):
    """Een goedgekeurde-en-daarna-gedeactiveerde gebruiker mag niet in het aanvraag-pad vallen."""
    await client.post("/v1/auth/registratie", json=_aanvraag())
    aanvraag_id = (await client.get("/v1/admin/registraties", headers=_ADMIN)).json()[0]["id"]
    await client.post(f"/v1/admin/registraties/{aanvraag_id}/goedkeuren", json={}, headers=_ADMIN)
    await client.patch("/v1/admin/users/palmw01", json={"active": False}, headers=_ADMIN)

    r = await client.post("/v1/auth/verify", json={"userid": "palmw01", "password": "geheim123"})
    assert r.json()["ok"] is False and r.json()["code"] == "invalid"
