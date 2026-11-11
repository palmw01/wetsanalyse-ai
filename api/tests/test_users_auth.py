"""Tests voor de login-module: wachtwoord-hashing, credential-verificatie (op userid), eenmalige
registratie, rol-guards, optionele 2FA (TOTP) en de HTTP-endpoints (auth + admin-gebruikersbeheer).

Inloggen gaat met de userid; e-mail is een verplicht, uniek registratiegegeven.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pyotp
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


# De klok van `app.users` (`_nu`) staat in deze tests stil tot een test hem verzet. Een TOTP-code
# geldt maar één keer per tijdstap; `_totp_now` schuift daarom eerst een stap op, zodat elke code die
# een test opvraagt een verse is – zoals bij een mens die op de volgende code wacht.
_KLOK = {"t": 1_800_000_000.0}


@pytest.fixture(autouse=True)
def _stilstaande_klok(monkeypatch):
    from app import users

    _KLOK["t"] = 1_800_000_000.0
    monkeypatch.setattr(users, "_nu", lambda: _KLOK["t"])


def _secret(otpauth_uri: str) -> str:
    return parse_qs(urlparse(otpauth_uri).query)["secret"][0]


def _totp_now(otpauth_uri: str) -> str:
    """Een verse code: de klok gaat eerst één tijdstap (30 s) vooruit."""
    _KLOK["t"] += 30
    return pyotp.TOTP(_secret(otpauth_uri)).at(_KLOK["t"])


def _totp_zelfde(otpauth_uri: str) -> str:
    """De code van de huidige tijdstap, zónder de klok te verzetten – om hergebruik te testen."""
    return pyotp.TOTP(_secret(otpauth_uri)).at(_KLOK["t"])


# --- wachtwoord-hashing --------------------------------------------------------

def test_hash_password_round_trip():
    from app import users

    h = users.hash_password("geheim-wachtwoord")
    assert h != "geheim-wachtwoord"
    assert users.verify_password("geheim-wachtwoord", h)
    assert not users.verify_password("fout", h)
    assert not users.verify_password("x", "")


# --- eenmalige registratie -----------------------------------------------------

async def test_bootstrap_eenmalig(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    assert await users.needs_setup()
    user = await users.bootstrap_admin("Baas", "Eerste@Example.com", "wachtwoord1")
    assert user.role == "beheerder"
    assert user.userid == "baas"  # genormaliseerd
    assert user.email == "eerste@example.com"
    assert not await users.needs_setup()
    with pytest.raises(users.UserError):
        await users.bootstrap_admin("baas2", "tweede@example.com", "wachtwoord2")


async def test_userid_en_email_validatie(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    with pytest.raises(users.UserError):  # te kort / spaties
        await users.create_user("ab", "x@example.com")
    with pytest.raises(users.UserError):  # ongeldige e-mail
        await users.create_user("geldigeid", "geen-email")


# --- credential-verificatie (op userid) ----------------------------------------

async def test_verify_credentials(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "a@example.com", "goedwachtwoord")
    user, code = await users.verify_credentials("baas", "goedwachtwoord")
    assert code == "ok" and user is not None and user.role == "beheerder"

    # Inloggen met e-mail kan NIET (uitsluitend userid).
    assert (await users.verify_credentials("a@example.com", "goedwachtwoord"))[1] == "invalid"
    assert (await users.verify_credentials("baas", "fout"))[1] == "invalid"
    assert (await users.verify_credentials("onbekend", "x"))[1] == "invalid"

    # Een gedeactiveerd account kan niet inloggen (apart account; de enige beheerder is beschermd).
    _, temp = await users.create_user("analist1", "b@example.com", role="analist")
    await users.patch_user("analist1", active=False)
    assert (await users.verify_credentials("analist1", temp))[1] == "invalid"


# --- uniciteit -----------------------------------------------------------------

async def test_unieke_userid_en_email(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    await users.create_user("jan", "jan@example.com")
    with pytest.raises(users.UserError):  # dubbele userid
        await users.create_user("jan", "anders@example.com")
    with pytest.raises(users.UserError):  # dubbele e-mail
        await users.create_user("piet", "jan@example.com")


# --- rol-guards ----------------------------------------------------------------

async def test_laatste_beheerder_beschermd(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("admin", "admin@example.com", "wachtwoord1")
    with pytest.raises(users.UserError):
        await users.patch_user("admin", role="analist")
    with pytest.raises(users.UserError):
        await users.patch_user("admin", active=False)
    with pytest.raises(users.UserError):
        await users.delete_user("admin")

    # Met een tweede beheerder mag het wél.
    await users.create_user("admin2", "admin2@example.com", role="beheerder")
    await users.patch_user("admin", role="analist")
    assert (await users.get_user("admin")).role == "analist"


async def test_patch_user_gecombineerd_atomair(monkeypatch, db):
    """patch_user toetst de laatste-beheerder-invariant op de EIND-toestand: rol+active tegelijk
    wijzigen mag de enige beheerder niet degraderen, maar een no-op-combinatie (beheerder blijft
    actief beheerder) wél."""
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("admin", "admin@example.com", "wachtwoord1")
    # Rol+active in één patch die de enige beheerder zou wegnemen → geweigerd (geen half-effect).
    with pytest.raises(users.UserError):
        await users.patch_user("admin", role="analist", active=False)
    na = await users.get_user("admin")
    assert na.role == "beheerder" and na.active is True  # niets veranderd

    # Een niet-degraderende patch (blijft actief beheerder) mag.
    u = await users.patch_user("admin", role="beheerder", active=True)
    assert u.role == "beheerder" and u.active is True

    # Met een tweede beheerder mag de gecombineerde degradatie wél.
    await users.create_user("admin2", "admin2@example.com", role="beheerder")
    u = await users.patch_user("admin", role="analist", active=False)
    assert u.role == "analist" and u.active is False


async def test_gedeactiveerde_beheerder_telt_niet_mee(monkeypatch, db):
    """Een tweede beheerder die niet actief is, redt de laatste actieve niet: die blijft beschermd."""
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("admin", "admin@example.com", "wachtwoord1")
    await users.create_user("slaper", "slaper@example.com", role="beheerder")
    await users.patch_user("slaper", active=False)
    for poging in (
        lambda: users.patch_user("admin", role="analist"),
        lambda: users.patch_user("admin", active=False),
        lambda: users.delete_user("admin"),
    ):
        with pytest.raises(users.UserError):
            await poging()
    na = await users.get_user("admin")
    assert na.role == "beheerder" and na.active is True

    # Een inactieve beheerder mag weg of terug naar analist: dat raakt de telling niet.
    await users.patch_user("slaper", role="analist")
    await users.delete_user("slaper")
    # Weer actief maken telt hem wél mee.
    await users.create_user("terug", "terug@example.com", role="beheerder")
    await users.patch_user("terug", active=False)
    await users.patch_user("terug", active=True)
    await users.patch_user("admin", role="analist")
    assert (await users.get_user("terug")).role == "beheerder"


async def test_laatste_beheerder_via_admin_api_en_userid_in_hoofdletters(client):
    """De admin-API (en dus de admin-MCP en de webapp, die er allebei langs gaan) houdt dezelfde regel, ook als
    de userid anders geschreven is."""
    await client.post(
        "/v1/auth/setup", json={"userid": "baas", "email": "boss@example.com", "password": "wachtwoord1"}
    )
    for pad in ("/v1/admin/users/baas", "/v1/admin/users/BAAS"):
        assert (await client.patch(pad, json={"role": "analist"}, headers=_ADMIN)).status_code == 409
        assert (await client.patch(pad, json={"active": False}, headers=_ADMIN)).status_code == 409
        assert (await client.patch(pad, json={"role": "analist", "active": False}, headers=_ADMIN)).status_code == 409
        assert (await client.delete(pad, headers=_ADMIN)).status_code == 409
    me = (await client.get("/v1/auth/me", headers={"X-User-Id": "baas"})).json()
    assert me["role"] == "beheerder"


async def test_verify_credentials_dummy_bcrypt_bij_onbekende_user(monkeypatch, db):
    """Bij een onbekende/inactieve gebruiker draait tóch een bcrypt-verificatie (dummy-hash), zodat
    er geen timing-oracle 'bestaat + actief' ontstaat. We toetsen het waarneembare contract: de
    reden blijft de generieke 'invalid', en de dummy-hash is een geldige bcrypt-hash."""
    _fresh_settings(monkeypatch)
    from app import users

    assert (await users.verify_credentials("bestaat-niet", "x"))[1] == "invalid"
    assert users.verify_password("x", users._DUMMY_HASH) is True


# --- stateless auth-tokens: login-ticket + trusted device ----------------------

async def test_login_ticket_roundtrip(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    t = users.maak_login_ticket("baas")
    assert t is not None
    assert users.lees_login_ticket(t) == "baas"
    assert users.lees_login_ticket("rommel") is None
    assert users.lees_login_ticket(None) is None


async def test_trusted_device_bind_invalidatie_bij_wachtwoordwijziging(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "a@example.com", "wachtwoord1")
    uri = await users.begin_2fa("baas", "wachtwoord1")
    await users.activate_2fa("baas", _totp_now(uri))

    token = users.maak_trusted_device(await users.get_user("baas"))
    assert token is not None
    assert await users.valideer_trusted_device(token) == "baas"

    # Wachtwoord wijzigen verandert de bind → token automatisch ongeldig (geen revocatielijst).
    await users.change_own_password("baas", "wachtwoord1", "wachtwoord2")
    assert await users.valideer_trusted_device(token) is None


async def test_trusted_device_ongeldig_zonder_2fa(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "a@example.com", "wachtwoord1")
    # Token gemaakt vóór 2FA aanstaat: valideren moet falen (2FA niet aan).
    token = users.maak_trusted_device(await users.get_user("baas"))
    assert await users.valideer_trusted_device(token) is None


async def test_verify_credentials_via_ticket_en_trusted(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "a@example.com", "wachtwoord1")
    uri = await users.begin_2fa("baas", "wachtwoord1")
    await users.activate_2fa("baas", _totp_now(uri))

    # Wachtwoord ok maar 2FA nodig.
    user, code = await users.verify_credentials("baas", "wachtwoord1")
    assert user is None and code == "totp_required"

    # Ticket telt als wachtwoord-bewijs; met geldige TOTP → ok (het 2FA-scherm zonder wachtwoord).
    ticket = users.maak_login_ticket("baas")
    user, code = await users.verify_credentials("baas", "", _totp_now(uri), ticket=ticket)
    assert code == "ok_totp" and user is not None

    # Een ticket voor een ándere userid telt niet als bewijs.
    user, code = await users.verify_credentials("baas", "", _totp_now(uri),
                                                ticket=users.maak_login_ticket("iemand-anders"))
    # (wachtwoord leeg + ticket voor andere user → geen bewijs → invalid)
    assert user is None and code == "invalid"

    # Trusted device slaat de TOTP-stap over.
    token = users.maak_trusted_device(await users.get_user("baas"))
    user, code = await users.verify_credentials("baas", "wachtwoord1", trusted_token=token)
    assert code == "ok" and user is not None


# --- wachtwoord wijzigen -------------------------------------------------------

async def test_change_own_password(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "a@example.com", "oudwachtwoord")
    with pytest.raises(users.UserError):
        await users.change_own_password("baas", "fout", "nieuwwachtwoord")
    # De minimumlengte van het nieuwe wachtwoord wordt op de routerlaag afgedwongen
    # (Pydantic `PasswordChangeIn.new`, min_length=8), niet meer in deze service-functie —
    # zie test_change_password_te_kort_http.
    await users.change_own_password("baas", "oudwachtwoord", "nieuwwachtwoord")
    assert (await users.verify_credentials("baas", "oudwachtwoord"))[1] == "invalid"
    assert (await users.verify_credentials("baas", "nieuwwachtwoord"))[1] == "ok"


# --- 2FA (TOTP) ----------------------------------------------------------------

async def test_2fa_cyclus(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    await _baas_als_analist()
    uri = await users.begin_2fa("baas", "wachtwoord1")
    assert not (await users.get_user("baas")).totp_enabled
    assert (await users.verify_credentials("baas", "wachtwoord1"))[1] == "ok"

    with pytest.raises(users.UserError):
        await users.activate_2fa("baas", "000000")
    await users.activate_2fa("baas", _totp_now(uri))
    assert (await users.get_user("baas")).totp_enabled

    assert (await users.verify_credentials("baas", "wachtwoord1"))[1] == "totp_required"
    assert (await users.verify_credentials("baas", "wachtwoord1", "000000"))[1] == "totp_required"
    ok_user, code = await users.verify_credentials("baas", "wachtwoord1", _totp_now(uri))
    assert code == "ok_totp" and ok_user is not None

    with pytest.raises(users.UserError):
        await users.disable_2fa("baas", "000000")
    await users.disable_2fa("baas", _totp_now(uri))
    assert not (await users.get_user("baas")).totp_enabled
    assert (await users.verify_credentials("baas", "wachtwoord1"))[1] == "ok"


async def test_totp_code_geldt_maar_een_keer(monkeypatch, db):
    """Een afgekeken code mag binnen zijn ±30 s-venster niet nog eens werken."""
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "u@example.com", "wachtwoord1")
    uri = await users.begin_2fa("baas", "wachtwoord1")
    await users.activate_2fa("baas", _totp_now(uri))

    code = _totp_now(uri)
    assert (await users.verify_credentials("baas", "wachtwoord1", code))[1] == "ok_totp"
    # Dezelfde code, dezelfde tijdstap: geweigerd.
    assert (await users.verify_credentials("baas", "wachtwoord1", code))[1] == "totp_required"
    # Ook de code van de activering (een oudere stap) werkt niet meer.
    assert (await users.verify_credentials("baas", "wachtwoord1", _totp_zelfde(uri)))[1] == "totp_required"
    # De volgende stap wel.
    assert (await users.verify_credentials("baas", "wachtwoord1", _totp_now(uri)))[1] == "ok_totp"


async def test_totp_oudere_stap_na_nieuwere_geweigerd(monkeypatch, db):
    """`valid_window` accepteert één stap terug; die mag niet meer ná een nieuwere stap."""
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "u@example.com", "wachtwoord1")
    uri = await users.begin_2fa("baas", "wachtwoord1")
    await users.activate_2fa("baas", _totp_now(uri))

    _KLOK["t"] += 30
    vorige = pyotp.TOTP(_secret(uri)).at(_KLOK["t"] - 30)
    huidige = _totp_zelfde(uri)
    assert (await users.verify_credentials("baas", "wachtwoord1", huidige))[1] == "ok_totp"
    assert (await users.verify_credentials("baas", "wachtwoord1", vorige))[1] == "totp_required"


async def test_2fa_ticket_bewijst_wachtwoord_en_tweede_factor(monkeypatch, db):
    """Het 2FA-scherm verbruikt de code; de tweede verificatie (Auth.js) leunt op het 2FA-ticket."""
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "u@example.com", "wachtwoord1")
    uri = await users.begin_2fa("baas", "wachtwoord1")
    await users.activate_2fa("baas", _totp_now(uri))

    code = _totp_now(uri)
    login = users.maak_login_ticket("baas")
    assert (await users.verify_credentials("baas", "", code, ticket=login))[1] == "ok_totp"
    # Zonder 2FA-ticket stuit de tweede verificatie met dezelfde code op de verbruikte stap.
    assert (await users.verify_credentials("baas", "", code, ticket=login))[1] == "totp_required"
    # Met het 2FA-ticket lukt het, ook zonder (of met een oude) code.
    tweede = users.maak_2fa_ticket("baas")
    assert users.lees_2fa_ticket(tweede) == "baas"
    assert (await users.verify_credentials("baas", "", code, ticket=tweede))[1] == "ok"
    assert (await users.verify_credentials("baas", "", None, ticket=tweede))[1] == "ok"
    # Een 2FA-ticket voor een ander telt niet, en een login-ticket is geen 2FA-ticket.
    assert (await users.verify_credentials("baas", "", None, ticket=users.maak_2fa_ticket("ander")))[1] == "invalid"
    assert users.lees_2fa_ticket(login) is None
    assert users.lees_login_ticket(tweede) is None


async def test_2fa_ticket_verloopt(monkeypatch, db):
    import time

    _fresh_settings(monkeypatch)
    from app import users

    tweede = users.maak_2fa_ticket("baas")
    assert users.lees_2fa_ticket(tweede) == "baas"
    # Fernet toetst de TTL tegen `time.time()`; laat die voorbij de 5 minuten lopen.
    echt = time.time()
    monkeypatch.setattr(time, "time", lambda: echt + 5 * 60 + 1)
    assert users.lees_2fa_ticket(tweede) is None


async def test_2fa_aan_en_uit_verbruiken_de_code(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    await _baas_als_analist()
    uri = await users.begin_2fa("baas", "wachtwoord1")
    code = _totp_now(uri)
    await users.activate_2fa("baas", code)
    # Met de activeringscode meteen weer uitzetten gaat niet: die is gebruikt.
    with pytest.raises(users.UserError):
        await users.disable_2fa("baas", code)
    await users.disable_2fa("baas", _totp_now(uri))
    assert not (await users.get_user("baas")).totp_enabled


# --- HTTP-endpoints ------------------------------------------------------------

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


async def test_setup_flow_http(client):
    r = await client.get("/v1/auth/setup-status")
    assert r.status_code == 200 and r.json()["needs_setup"] is True

    r = await client.post(
        "/v1/auth/setup", json={"userid": "baas", "email": "boss@example.com", "password": "wachtwoord1"}
    )
    assert r.status_code == 201 and r.json()["role"] == "beheerder" and r.json()["userid"] == "baas"

    r = await client.post(
        "/v1/auth/setup", json={"userid": "x", "email": "x@example.com", "password": "wachtwoord1"}
    )
    assert r.status_code == 409
    assert (await client.get("/v1/auth/setup-status")).json()["needs_setup"] is False


async def test_verify_http(client):
    await client.post(
        "/v1/auth/setup", json={"userid": "baas", "email": "boss@example.com", "password": "wachtwoord1"}
    )

    r = await client.post("/v1/auth/verify", json={"userid": "baas", "password": "wachtwoord1"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["userid"] == "baas" and body["role"] == "beheerder"

    r = await client.post("/v1/auth/verify", json={"userid": "baas", "password": "fout"})
    assert r.status_code == 200 and r.json()["ok"] is False and r.json()["code"] == "invalid"


async def test_change_password_te_kort_http(client):
    # De minimumlengte van het nieuwe wachtwoord leeft op de routerlaag (Pydantic min_length=8):
    # een te korte waarde geeft 422; een geldige wijziging slaagt (204).
    await client.post(
        "/v1/auth/setup", json={"userid": "baas", "email": "b@example.com", "password": "wachtwoord1"}
    )
    hdr = {"X-User-Id": "baas"}

    te_kort = await client.post(
        "/v1/auth/change-password", json={"current": "wachtwoord1", "new": "kort"}, headers=hdr
    )
    assert te_kort.status_code == 422

    ok = await client.post(
        "/v1/auth/change-password", json={"current": "wachtwoord1", "new": "nieuwwachtwoord"}, headers=hdr
    )
    assert ok.status_code == 204


async def test_admin_users_http(client):
    assert (await client.get("/v1/admin/users")).status_code == 401

    await client.post(
        "/v1/auth/setup", json={"userid": "baas", "email": "boss@example.com", "password": "wachtwoord1"}
    )

    r = await client.post(
        "/v1/admin/users",
        json={"userid": "analist1", "email": "analist@example.com", "role": "analist"},
        headers=_ADMIN,
    )
    assert r.status_code == 201
    temp = r.json()["temp_password"]
    assert temp and r.json()["role"] == "analist" and r.json()["userid"] == "analist1"

    v = await client.post("/v1/auth/verify", json={"userid": "analist1", "password": temp})
    assert v.json()["ok"] is True

    assert len((await client.get("/v1/admin/users", headers=_ADMIN)).json()) == 2

    p = await client.patch("/v1/admin/users/analist1", json={"role": "beheerder"}, headers=_ADMIN)
    assert p.status_code == 200 and p.json()["role"] == "beheerder"

    rp = await client.post("/v1/admin/users/analist1/reset-password", headers=_ADMIN)
    assert rp.status_code == 200 and rp.json()["temp_password"]

    d = await client.delete("/v1/admin/users/analist1", headers=_ADMIN)
    assert d.status_code == 200 and d.json() == {"gesprekken": []}


async def test_2fa_http_via_header(client):
    await client.post(
        "/v1/auth/setup", json={"userid": "baas", "email": "boss@example.com", "password": "wachtwoord1"}
    )
    hdr = {"X-User-Id": "baas"}

    assert (await client.get("/v1/auth/me", headers=hdr)).json()["totp_enabled"] is False
    assert (await client.get("/v1/auth/me")).status_code == 401

    begin = await client.post("/v1/auth/2fa/begin", json={"password": "wachtwoord1"}, headers=hdr)
    assert begin.status_code == 200
    code = _totp_now(begin.json()["otpauth_uri"])

    act = await client.post("/v1/auth/2fa/activate", json={"totp": code}, headers=hdr)
    assert act.status_code == 200 and len(act.json()["codes"]) == 10
    assert (await client.get("/v1/auth/me", headers=hdr)).json()["totp_enabled"] is True

    # Een beheerder zet 2FA niet uit, ook niet met een geldige code; die code blijft dan ongebruikt.
    totp_code = _totp_now(begin.json()["otpauth_uri"])
    dis = await client.post("/v1/auth/2fa/disable", json={"totp": totp_code}, headers=hdr)
    assert dis.status_code == 409
    assert (await client.get("/v1/auth/me", headers=hdr)).json()["totp_enabled"] is True
    login = await client.post("/v1/auth/verify", json={"userid": "baas", "password": "wachtwoord1", "totp": totp_code})
    assert login.json()["ok"] is True

    # Een analist mag het wel.
    temp = (await client.post("/v1/admin/users", json={"userid": "ana", "email": "a@example.com"}, headers=_ADMIN)).json()["temp_password"]
    ahdr = {"X-User-Id": "ana"}
    auri = (await client.post("/v1/auth/2fa/begin", json={"password": temp}, headers=ahdr)).json()["otpauth_uri"]
    await client.post("/v1/auth/2fa/activate", json={"totp": _totp_now(auri)}, headers=ahdr)
    assert (await client.post("/v1/auth/2fa/disable", json={"totp": "000000"}, headers=ahdr)).status_code == 400
    assert (await client.post("/v1/auth/2fa/disable", json={"totp": _totp_now(auri)}, headers=ahdr)).status_code == 204


async def test_begin_2fa_laat_actieve_2fa_staan(monkeypatch, db):
    """SEC-1: `begin` zette actieve 2FA uit zonder code. Het secret en de vlag blijven nu staan, dus
    het wachtwoord alleen is geen inlog en de oude authenticator blijft gelden."""
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "boss@example.com", "wachtwoord1")
    uri = await users.begin_2fa("baas", "wachtwoord1")
    await users.activate_2fa("baas", _totp_now(uri))
    secret_voor = (await users.get_user("baas")).totp_secret_enc

    with pytest.raises(users.TotpActiefError):
        await users.begin_2fa("baas", "wachtwoord1")

    na = await users.get_user("baas")
    assert na.totp_enabled and na.totp_secret_enc == secret_voor
    assert (await users.verify_credentials("baas", "wachtwoord1"))[1] == "totp_required"
    assert (await users.verify_credentials("baas", "wachtwoord1", _totp_now(uri)))[1] == "ok_totp"


async def test_begin_2fa_race_met_activeren(monkeypatch, db):
    """De weigering zit in de UPDATE, niet in een eerdere lezing: wie 2FA nog uit zag staan terwijl
    een ander tabblad hem net activeerde, overschrijft het secret niet."""
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "boss@example.com", "wachtwoord1")
    uri = await users.begin_2fa("baas", "wachtwoord1")
    verouderd = await users.get_user("baas")
    await users.activate_2fa("baas", _totp_now(uri))
    secret_voor = (await users.get_user("baas")).totp_secret_enc

    async def oude_lezing(_userid):
        return verouderd

    monkeypatch.setattr(users, "_require_user", oude_lezing)
    with pytest.raises(users.TotpActiefError):
        await users.begin_2fa("baas", "wachtwoord1")

    na = await users.get_user("baas")
    assert na.totp_enabled and na.totp_secret_enc == secret_voor


async def test_begin_2fa_vraagt_het_wachtwoord(monkeypatch, db):
    """Een gekaapte sessie kent het wachtwoord niet en kan dus geen eigen authenticator koppelen."""
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "boss@example.com", "wachtwoord1")
    with pytest.raises(users.UserError, match="wachtwoord"):
        await users.begin_2fa("baas", "fout")
    u = await users.get_user("baas")
    assert u.totp_secret_enc is None and not u.totp_enabled


async def test_begin_2fa_opnieuw_voor_bevestiging_en_na_uitzetten(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    await _baas_als_analist()
    eerste = await users.begin_2fa("baas", "wachtwoord1")
    tweede = await users.begin_2fa("baas", "wachtwoord1")  # onbevestigd: vervangt het eerste secret
    assert _secret(eerste) != _secret(tweede)

    await users.activate_2fa("baas", _totp_now(tweede))
    await users.disable_2fa("baas", _totp_now(tweede))
    derde = await users.begin_2fa("baas", "wachtwoord1")
    await users.activate_2fa("baas", _totp_now(derde))
    assert (await users.get_user("baas")).totp_enabled


async def test_2fa_begin_http_statussen(client):
    await client.post(
        "/v1/auth/setup", json={"userid": "baas", "email": "boss@example.com", "password": "wachtwoord1"}
    )
    hdr = {"X-User-Id": "baas"}

    assert (await client.post("/v1/auth/2fa/begin", headers=hdr)).status_code == 422
    fout = await client.post("/v1/auth/2fa/begin", json={"password": "fout"}, headers=hdr)
    assert fout.status_code == 400

    uri = (await client.post("/v1/auth/2fa/begin", json={"password": "wachtwoord1"}, headers=hdr)).json()["otpauth_uri"]
    assert (await client.post("/v1/auth/2fa/activate", json={"totp": _totp_now(uri)}, headers=hdr)).status_code == 200

    actief = await client.post("/v1/auth/2fa/begin", json={"password": "wachtwoord1"}, headers=hdr)
    assert actief.status_code == 409
    assert (await client.get("/v1/auth/me", headers=hdr)).json()["totp_enabled"] is True


async def test_2fa_login_http_verbruikt_code_en_geeft_2fa_ticket(client):
    """De flow van de webapp: wachtwoord → login-ticket, 2FA-scherm → 2FA-ticket, Auth.js → sessie.
    De code gaat één keer mee; de tweede verificatie leunt op het 2FA-ticket."""
    await client.post(
        "/v1/auth/setup", json={"userid": "baas", "email": "boss@example.com", "password": "wachtwoord1"}
    )
    hdr = {"X-User-Id": "baas"}
    uri = (await client.post("/v1/auth/2fa/begin", json={"password": "wachtwoord1"}, headers=hdr)).json()["otpauth_uri"]
    assert (await client.post("/v1/auth/2fa/activate", json={"totp": _totp_now(uri)}, headers=hdr)).status_code == 200

    stap_a = (await client.post("/v1/auth/verify", json={"userid": "baas", "password": "wachtwoord1"})).json()
    assert stap_a["code"] == "totp_required" and stap_a["ticket"]

    code = _totp_now(uri)
    stap_b = (await client.post("/v1/auth/verify", json={"userid": "baas", "ticket": stap_a["ticket"], "totp": code})).json()
    assert stap_b["ok"] is True and stap_b["ticket"], "na een verbruikte code hoort er een 2FA-ticket mee te komen"

    # Zelfde code met alleen het login-ticket: verbruikt.
    opnieuw = (await client.post("/v1/auth/verify", json={"userid": "baas", "ticket": stap_a["ticket"], "totp": code})).json()
    assert opnieuw["ok"] is False and opnieuw["code"] == "totp_required"
    # Met het 2FA-ticket (zoals Auth.js na het 2FA-scherm): gelukt, en geen nieuw ticket.
    sessie = (await client.post("/v1/auth/verify", json={"userid": "baas", "ticket": stap_b["ticket"], "totp": code})).json()
    assert sessie["ok"] is True and sessie["ticket"] is None


async def test_gevoelige_endpoints_rate_limited(monkeypatch):
    """De geauthenticeerde 2FA/wachtwoord-endpoints delen de brute-force-rem (`sensitive_allowed`):
    na de limiet volgt 429 – ook op mislukte pogingen, zodat een gekaapte sessie geen TOTP/wachtwoord
    kan brute-forcen. Een andere userid heeft zijn eigen bucket."""
    _fresh_settings(
        monkeypatch,
        WETSANALYSE_AUTH_REQUIRED="0",
        WETSANALYSE_RATE_LIMIT_MAX="2",
        WETSANALYSE_RATE_LIMIT_WINDOW="60",
    )
    from app import db, ratelimit

    ratelimit.reset()
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()

    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post(
            "/v1/auth/setup", json={"userid": "baas", "email": "b@example.com", "password": "wachtwoord1"}
        )
        hdr = {"X-User-Id": "baas"}
        payload = {"current": "fout", "new": "nieuwwachtwoord"}  # geldig contract, fout huidig ww → 400

        # 2 pogingen toegestaan (400 = fout wachtwoord), de 3e wordt door de rem geblokkeerd (429).
        assert (await ac.post("/v1/auth/change-password", json=payload, headers=hdr)).status_code == 400
        assert (await ac.post("/v1/auth/change-password", json=payload, headers=hdr)).status_code == 400
        geblokkeerd = await ac.post("/v1/auth/change-password", json=payload, headers=hdr)
        assert geblokkeerd.status_code == 429 and geblokkeerd.headers.get("Retry-After")
        # `2fa/begin` vraagt ook het wachtwoord en deelt dus dezelfde rem.
        assert (await ac.post("/v1/auth/2fa/begin", json={"password": "fout"}, headers=hdr)).status_code == 429

        # De rem is per-userid: een andere X-User-Id wordt niet meteen geblokkeerd (eigen bucket).
        ander = await ac.post("/v1/auth/change-password", json=payload, headers={"X-User-Id": "ander"})
        assert ander.status_code != 429

    await db.dispose_engine()


# --- sessie-revocatie bij wachtwoordwijziging (Finding 1) ----------------------

async def test_reconcile_schema_voegt_kolom_toe(monkeypatch, db):
    """reconcile_schema voegt een in de definitie aanwezige, in de DB ontbrekende kolom additief toe
    (create_all dekt alleen ontbrekende tabellen) en is idempotent."""
    from sqlalchemy import inspect as sa_inspect

    from app import db as _db

    def _kolommen(sync_conn) -> set[str]:
        return {c["name"] for c in sa_inspect(sync_conn).get_columns("users")}

    async with _db.get_engine().begin() as conn:
        # Simuleer een 'oude' DB zonder de kolom.
        await conn.exec_driver_sql("ALTER TABLE users DROP COLUMN sessions_valid_from")
        assert "sessions_valid_from" not in await conn.run_sync(_kolommen)

    await _db.reconcile_schema()
    async with _db.get_engine().begin() as conn:
        assert "sessions_valid_from" in await conn.run_sync(_kolommen)

    # Idempotent: nog een keer draaien mag niet falen.
    await _db.reconcile_schema()


async def test_wachtwoordwijziging_bumpt_sessie_epoch(monkeypatch, db):
    """change_own_password en reset_password zetten sessions_valid_from; een ongewijzigd account houdt
    None (geen revocatie van bestaande sessies tot de eerste wijziging)."""
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "a@example.com", "wachtwoord1")
    assert (await users.get_user("baas")).sessions_valid_from is None

    await users.change_own_password("baas", "wachtwoord1", "nieuwwachtwoord")
    na_wijziging = (await users.get_user("baas")).sessions_valid_from
    assert na_wijziging is not None

    # Een admin-reset bumpt de epoch opnieuw (revoke overal).
    _, _temp = await users.reset_password("baas")
    assert (await users.get_user("baas")).sessions_valid_from >= na_wijziging


async def test_me_geeft_sessions_valid_from(client):
    await client.post(
        "/v1/auth/setup", json={"userid": "baas", "email": "b@example.com", "password": "wachtwoord1"}
    )
    hdr = {"X-User-Id": "baas"}
    assert (await client.get("/v1/auth/me", headers=hdr)).json()["sessions_valid_from"] is None
    await client.post(
        "/v1/auth/change-password", json={"current": "wachtwoord1", "new": "nieuwwachtwoord"}, headers=hdr
    )
    assert (await client.get("/v1/auth/me", headers=hdr)).json()["sessions_valid_from"] is not None


# --- herstelcodes en de 2FA-plicht ----------------------------------------------

async def _baas_als_analist() -> None:
    """"baas" (wachtwoord1) als analist: een beheerder kan 2FA niet uitzetten, dus de uitzet-tests draaien op een
    analist. "reserve" blijft beheerder, anders weigert de degradatie."""
    from app import users

    await users.bootstrap_admin("baas", "u@example.com", "wachtwoord1")
    await users.create_user("reserve", "r@example.com", role="beheerder")
    await users.patch_user("baas", role="analist")


async def _met_2fa(userid: str = "baas") -> tuple[str, list[str]]:
    """Een account met actieve 2FA: geeft de otpauth-URI en de herstelcodes."""
    from app import users

    uri = await users.begin_2fa(userid, "wachtwoord1")
    return uri, await users.activate_2fa(userid, _totp_now(uri))


async def test_opnieuw_koppelen_vervangt_pas_na_een_code_van_de_nieuwe_app(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "u@example.com", "wachtwoord1")
    oud, _ = await _met_2fa()

    # Zonder geldige code of met het verkeerde wachtwoord staat er niets klaar.
    with pytest.raises(users.UserError):
        await users.begin_2fa("baas", "wachtwoord1", "000000")
    with pytest.raises(users.UserError):
        await users.begin_2fa("baas", "fout", _totp_now(oud))
    with pytest.raises(users.TotpActiefError):
        await users.begin_2fa("baas", "wachtwoord1")
    assert await users._klaarstaande_app("baas") is None

    eerste = await users.begin_2fa("baas", "wachtwoord1", _totp_now(oud))
    tweede = await users.begin_2fa("baas", "wachtwoord1", _totp_now(oud))  # vervangt de eerste klaargezette
    # Tot de bevestiging blijft de oude app gelden en blijft 2FA aan.
    assert (await users.get_user("baas")).totp_enabled
    assert (await users.verify_credentials("baas", "wachtwoord1", _totp_now(oud)))[1] == "ok_totp"
    with pytest.raises(users.UserError):
        await users.activate_2fa("baas", _totp_now(eerste))
    with pytest.raises(users.UserError):
        await users.activate_2fa("baas", _totp_now(oud))

    codes = await users.activate_2fa("baas", code := _totp_now(tweede))
    assert len(codes) == 10 and await users._klaarstaande_app("baas") is None
    assert (await users.verify_credentials("baas", "wachtwoord1", _totp_now(oud)))[1] == "totp_required"
    # De bevestigingscode is gebruikt; de volgende van de nieuwe app werkt.
    assert (await users.verify_credentials("baas", "wachtwoord1", code))[1] == "totp_required"
    assert (await users.verify_credentials("baas", "wachtwoord1", _totp_now(tweede)))[1] == "ok_totp"
    with pytest.raises(users.UserError):
        await users.activate_2fa("baas", _totp_now(tweede))  # niets meer klaar


async def test_opnieuw_koppelen_met_een_herstelcode_en_een_reset_ruimt_op(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "u@example.com", "wachtwoord1")
    await users.create_user("collega", "c@example.com", role="beheerder")
    _, codes = await _met_2fa()
    nieuw = await users.begin_2fa("baas", "wachtwoord1", codes[0])
    with pytest.raises(users.UserError):
        await users.begin_2fa("baas", "wachtwoord1", codes[0])  # verbruikt
    # Een reset door een collega laat geen klaargezette app achter.
    await users.reset_2fa("baas", door="collega")
    assert await users._klaarstaande_app("baas") is None
    with pytest.raises(users.UserError):
        await users.activate_2fa("baas", _totp_now(nieuw))
    assert users.moet_2fa_koppelen(await users.get_user("baas"))


async def test_beheerder_zet_2fa_niet_uit_analist_wel(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "u@example.com", "wachtwoord1")
    uri, codes = await _met_2fa()
    for code in (_totp_now(uri), codes[0]):
        with pytest.raises(users.BeheerderHoudt2faError):
            await users.disable_2fa("baas", code)
    # De weigering verbruikt de herstelcode niet.
    assert await users.aantal_herstelcodes("baas") == 10
    assert (await users.get_user("baas")).totp_enabled

    # Gedegradeerd (met een tweede beheerder) mag het wel.
    await users.create_user("tweede", "t@example.com", role="beheerder")
    await users.patch_user("baas", role="analist")
    await users.disable_2fa("baas", codes[0])
    assert not (await users.get_user("baas")).totp_enabled


async def test_herstelcodes_gelden_een_keer_en_de_set_is_uniek(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "u@example.com", "wachtwoord1")
    _, codes = await _met_2fa()
    assert len(set(codes)) == 10 and await users.aantal_herstelcodes("baas") == 10
    assert all(len(c) == 19 and c.count("-") == 3 for c in codes)

    gebruiker, code = await users.verify_credentials("baas", "wachtwoord1", codes[0])
    assert gebruiker is not None and code == "ok_herstelcode"
    assert await users.aantal_herstelcodes("baas") == 9
    assert (await users.verify_credentials("baas", "wachtwoord1", codes[0]))[1] == "totp_required"
    # Kleine letters en zonder streepjes tellen ook: mensen typen dit over.
    kaal = codes[1].replace("-", "").lower()
    assert (await users.verify_credentials("baas", "wachtwoord1", kaal))[1] == "ok_herstelcode"


async def test_herstelcode_tegelijk_haalt_er_een(monkeypatch):
    """Twee gelijktijdige pogingen: de DELETE laat er één door. Op een bestand, want `:memory:` deelt
    geen verbindingen."""
    import asyncio

    _fresh_settings(monkeypatch)
    import tempfile

    from app import db as _db
    from app import users

    with tempfile.TemporaryDirectory() as map_:
        _db.init_engine(f"sqlite+aiosqlite:///{map_}/t.db")
        await _db.create_all()
        try:
            await users.bootstrap_admin("baas", "u@example.com", "wachtwoord1")
            _, codes = await _met_2fa()
            user = await users.get_user("baas")
            uitkomst = await asyncio.gather(*(users._verbruik_tweede_factor(user, codes[0]) for _ in range(5)))
            assert sorted(u for u in uitkomst if u) == ["herstelcode"]
        finally:
            await _db.dispose_engine()


async def test_herstelcode_van_een_ander_account_geldt_niet(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "u@example.com", "wachtwoord1")
    await users.insert_user_met_hash("tweede", "t@example.com", users.hash_password("wachtwoord1"), role="analist")
    _, codes = await _met_2fa("baas")
    await _met_2fa("tweede")
    assert (await users.verify_credentials("tweede", "wachtwoord1", codes[0]))[1] == "totp_required"
    assert await users.aantal_herstelcodes("baas") == 10


async def test_herstelcode_overleeft_een_geroteerde_sleutel(monkeypatch, db):
    """De hele reden dat de codes niet in Fernet staan: het TOTP-secret is dan niet meer te lezen."""
    from cryptography.fernet import Fernet

    _fresh_settings(monkeypatch)
    from app import users
    from app.secrets_crypto import SecretsCryptoError

    await _baas_als_analist()
    _, codes = await _met_2fa()

    _fresh_settings(monkeypatch, LLM_CONFIG_SECRET=Fernet.generate_key().decode())
    with pytest.raises(SecretsCryptoError):
        await users.verify_credentials("baas", "wachtwoord1", "123456")
    assert (await users.verify_credentials("baas", "wachtwoord1", codes[0]))[1] == "ok_herstelcode"
    await users.disable_2fa("baas", codes[1])
    assert not (await users.get_user("baas")).totp_enabled


async def test_nieuwe_telefoon_met_twee_herstelcodes(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    await _baas_als_analist()
    _, codes = await _met_2fa()

    assert (await users.verify_credentials("baas", "wachtwoord1", codes[0]))[1] == "ok_herstelcode"
    with pytest.raises(users.UserError):
        await users.disable_2fa("baas", codes[0])  # verbruikt
    await users.disable_2fa("baas", codes[1])
    assert await users.aantal_herstelcodes("baas") == 0
    uri = await users.begin_2fa("baas", "wachtwoord1")
    assert len(await users.activate_2fa("baas", _totp_now(uri))) == 10


async def test_vervangen_maakt_oude_codes_ongeldig(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "u@example.com", "wachtwoord1")
    uri, oud = await _met_2fa()
    with pytest.raises(users.UserError):
        await users.vervang_herstelcodes("baas", "000000")
    assert await users.aantal_herstelcodes("baas") == 10

    nieuw = await users.vervang_herstelcodes("baas", _totp_now(uri))
    assert not set(oud) & set(nieuw) and await users.aantal_herstelcodes("baas") == 10
    assert (await users.verify_credentials("baas", "wachtwoord1", oud[1]))[1] == "totp_required"
    assert (await users.verify_credentials("baas", "wachtwoord1", nieuw[0]))[1] == "ok_herstelcode"


async def test_verwijderen_ruimt_herstelcodes_op(monkeypatch, db):
    """Een nieuw account met dezelfde userid mag de codes van het oude niet erven."""
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "u@example.com", "wachtwoord1")
    await users.insert_user_met_hash("weg", "w@example.com", users.hash_password("wachtwoord1"), role="analist")
    await _met_2fa("weg")
    await users.delete_user("weg")
    assert await users.aantal_herstelcodes("weg") == 0


async def test_verwijderen_wist_de_gesprekken_en_houdt_de_userid_bezet(monkeypatch, db):
    """Een nieuw account met een oude userid erfde de gesprekken van de vorige eigenaar (API-03)."""
    _fresh_settings(monkeypatch)
    from datetime import datetime, timezone

    from sqlalchemy import insert, select

    from app import db as dbm, registraties, users

    await users.bootstrap_admin("baas", "u@example.com", "wachtwoord1")
    await users.create_user("palmw01", "w@example.com")
    nu = datetime.now(timezone.utc)
    async with dbm.get_engine().begin() as conn:
        await conn.execute(insert(dbm.gesprekken).values(id="g1", user_id="palmw01", titel="t", created=nu, updated=nu))
        await conn.execute(insert(dbm.gesprek_berichten).values(gesprek_id="g1", rol="user", inhoud={"tekst": "vraag"},
                                                                created=nu))
        await conn.execute(insert(dbm.gesprekken).values(id="g2", user_id="baas", titel="t", created=nu, updated=nu))

    assert await users.delete_user("palmw01") == ["g1"]
    async with dbm.get_engine().connect() as conn:
        assert (await conn.execute(select(dbm.gesprekken.c.id))).scalars().all() == ["g2"]
        assert (await conn.execute(select(dbm.gesprek_berichten.c.id))).scalars().all() == []
    with pytest.raises(users.UserError, match="eerder gebruikt"):
        await users.create_user("palmw01", "nieuw@example.com")
    # De zelfregistratie slaat hem over en kiest het volgende volgnummer.
    assert await registraties.unieke_userid("Willard", "Palm") == "palmw02"


async def test_plicht_geldt_voor_elke_weg_naar_beheerder(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    eerste = await users.bootstrap_admin("baas", "u@example.com", "wachtwoord1")
    assert users.moet_2fa_koppelen(eerste)

    nieuw, _ = await users.create_user("tweede", "t@example.com", role="beheerder")
    assert users.moet_2fa_koppelen(nieuw)

    analist, _ = await users.create_user("derde", "d@example.com")
    assert not users.moet_2fa_koppelen(analist)
    assert users.moet_2fa_koppelen(await users.patch_user("derde", role="beheerder"))

    uri = await users.begin_2fa("baas", "wachtwoord1")
    await users.activate_2fa("baas", _totp_now(uri))
    assert not users.moet_2fa_koppelen(await users.get_user("baas"))
    # Uitzetten mag een beheerder niet; een reset door een collega zet de plicht weer aan.
    with pytest.raises(users.BeheerderHoudt2faError):
        await users.disable_2fa("baas", _totp_now(uri))
    await users.reset_2fa("baas", door="tweede")
    assert users.moet_2fa_koppelen(await users.get_user("baas"))


async def test_reset_wist_alles_en_laat_sessies_vervallen(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "u@example.com", "wachtwoord1")
    await users.insert_user_met_hash("kwijt", "k@example.com", users.hash_password("wachtwoord1"), role="analist")
    _, codes = await _met_2fa("kwijt")
    apparaat = users.maak_trusted_device(await users.get_user("kwijt"))
    assert await users.valideer_trusted_device(apparaat) == "kwijt"

    await users.reset_2fa("kwijt", door="baas")

    na = await users.get_user("kwijt")
    assert not na.totp_enabled and na.totp_secret_enc is None and na.sessions_valid_from is not None
    assert await users.aantal_herstelcodes("kwijt") == 0
    assert await users.valideer_trusted_device(apparaat) is None
    assert (await users.verify_credentials("kwijt", "wachtwoord1"))[1] == "ok"
    with pytest.raises(users.UserError):
        await users.reset_2fa("kwijt", door="baas")  # staat al uit


async def test_reset_op_jezelf_kan_niet(monkeypatch, db):
    _fresh_settings(monkeypatch)
    from app import users

    await users.bootstrap_admin("baas", "u@example.com", "wachtwoord1")
    await _met_2fa()
    with pytest.raises(users.UserError):
        await users.reset_2fa("baas", door="BAAS ")
    assert (await users.get_user("baas")).totp_enabled


async def test_herstelcode_login_http_geeft_2fa_ticket(client):
    await client.post(
        "/v1/auth/setup", json={"userid": "baas", "email": "boss@example.com", "password": "wachtwoord1"}
    )
    hdr = {"X-User-Id": "baas"}
    uri = (await client.post("/v1/auth/2fa/begin", json={"password": "wachtwoord1"}, headers=hdr)).json()["otpauth_uri"]
    codes = (await client.post("/v1/auth/2fa/activate", json={"totp": _totp_now(uri)}, headers=hdr)).json()["codes"]

    stap_a = (await client.post("/v1/auth/verify", json={"userid": "baas", "password": "wachtwoord1"})).json()
    stap_b = (await client.post("/v1/auth/verify", json={"userid": "baas", "ticket": stap_a["ticket"], "totp": codes[0]})).json()
    assert stap_b["ok"] is True and stap_b["ticket"], "de code is op, dus de tweede verify leunt op het ticket"
    sessie = (await client.post("/v1/auth/verify", json={"userid": "baas", "ticket": stap_b["ticket"], "totp": codes[0]})).json()
    assert sessie["ok"] is True
    assert (await client.get("/v1/auth/me", headers=hdr)).json()["herstelcodes_over"] == 9


async def test_herstelcodes_vervangen_http(client):
    await client.post(
        "/v1/auth/setup", json={"userid": "baas", "email": "boss@example.com", "password": "wachtwoord1"}
    )
    hdr = {"X-User-Id": "baas"}
    assert (await client.post("/v1/auth/2fa/herstelcodes", json={"totp": "000000"}, headers=hdr)).status_code == 400
    uri = (await client.post("/v1/auth/2fa/begin", json={"password": "wachtwoord1"}, headers=hdr)).json()["otpauth_uri"]
    await client.post("/v1/auth/2fa/activate", json={"totp": _totp_now(uri)}, headers=hdr)

    assert (await client.post("/v1/auth/2fa/herstelcodes", json={"totp": "000000"}, headers=hdr)).status_code == 400
    assert (await client.post("/v1/auth/2fa/herstelcodes", json={"totp": _totp_now(uri)})).status_code == 401
    res = await client.post("/v1/auth/2fa/herstelcodes", json={"totp": _totp_now(uri)}, headers=hdr)
    assert res.status_code == 200 and len(res.json()["codes"]) == 10


async def test_tfa_nodig_http_op_setup_en_me(client):
    res = await client.post(
        "/v1/auth/setup", json={"userid": "baas", "email": "boss@example.com", "password": "wachtwoord1"}
    )
    assert res.json()["tfa_nodig"] is True
    hdr = {"X-User-Id": "baas"}
    assert (await client.get("/v1/auth/me", headers=hdr)).json()["tfa_nodig"] is True
    uri = (await client.post("/v1/auth/2fa/begin", json={"password": "wachtwoord1"}, headers=hdr)).json()["otpauth_uri"]
    await client.post("/v1/auth/2fa/activate", json={"totp": _totp_now(uri)}, headers=hdr)
    assert (await client.get("/v1/auth/me", headers=hdr)).json()["tfa_nodig"] is False


async def test_rondleiding_hoort_bij_de_gebruiker(client):
    await client.post(
        "/v1/auth/setup", json={"userid": "baas", "email": "boss@example.com", "password": "wachtwoord1"}
    )
    hdr = {"X-User-Id": "baas"}
    me = (await client.get("/v1/auth/me", headers=hdr)).json()
    assert me["rondleiding_aangeboden"] == 0 and me["rondleiding_knop"] is True  # een nieuwe gebruiker ziet de knop

    # Overslaan: niet meer vanzelf aanbieden, de knop blijft.
    res = await client.patch("/v1/auth/me/rondleiding", json={"aangeboden": 3}, headers=hdr)
    assert res.json() == {"rondleiding_aangeboden": 3, "rondleiding_knop": True}

    # Het vinkje aan het eind: de knop gaat uit, en elke sessie leest dat terug.
    await client.patch("/v1/auth/me/rondleiding", json={"knop": False}, headers=hdr)
    assert (await client.get("/v1/auth/me", headers=hdr)).json()["rondleiding_knop"] is False

    # De knop alleen aanzetten laat de versie staan, en een oude bundel zet de versie niet terug.
    res = await client.patch("/v1/auth/me/rondleiding", json={"knop": True}, headers=hdr)
    assert res.json() == {"rondleiding_aangeboden": 3, "rondleiding_knop": True}
    res = await client.patch("/v1/auth/me/rondleiding", json={"aangeboden": 2}, headers=hdr)
    assert res.json()["rondleiding_aangeboden"] == 3


async def test_rondleiding_vraagt_een_actief_account(client):
    assert (await client.patch("/v1/auth/me/rondleiding", json={"knop": False})).status_code == 401
    res = await client.patch("/v1/auth/me/rondleiding", json={"knop": False}, headers={"X-User-Id": "niemand"})
    assert res.status_code == 401
    await client.post(
        "/v1/auth/setup", json={"userid": "baas", "email": "boss@example.com", "password": "wachtwoord1"}
    )
    res = await client.patch("/v1/auth/me/rondleiding", json={"aangeboden": -1}, headers={"X-User-Id": "baas"})
    assert res.status_code == 422


async def _twee_beheerders(client) -> str:
    """"baas" heeft 2FA, "kwijt" (beheerder) ook; geeft de URI van baas."""
    await client.post(
        "/v1/auth/setup", json={"userid": "baas", "email": "boss@example.com", "password": "wachtwoord1"}
    )
    temp = (await client.post(
        "/v1/admin/users", json={"userid": "kwijt", "email": "k@example.com", "role": "beheerder"}, headers=_ADMIN
    )).json()["temp_password"]
    uri = None
    for userid, wachtwoord in (("kwijt", temp), ("baas", "wachtwoord1")):
        hdr = {"X-User-Id": userid}
        uri = (await client.post("/v1/auth/2fa/begin", json={"password": wachtwoord}, headers=hdr)).json()["otpauth_uri"]
        await client.post("/v1/auth/2fa/activate", json={"totp": _totp_now(uri)}, headers=hdr)
    return uri


async def test_reset_http_vraagt_een_beheerder_met_2fa(client):
    await _twee_beheerders(client)
    pad = "/v1/admin/users/kwijt/2fa/reset"

    # Een kaal admin-token (de admin-MCP) weet niet wie het is, en dat is hier de eis.
    assert (await client.post(pad, headers=_ADMIN)).status_code == 401
    assert (await client.post(pad, headers={"X-User-Id": "baas"})).status_code == 401  # geen admin-token
    # Een analist en een beheerder zonder 2FA komen er ook niet door.
    await client.post("/v1/admin/users", json={"userid": "ana", "email": "a@example.com"}, headers=_ADMIN)
    await client.post("/v1/admin/users", json={"userid": "kaal", "email": "n@example.com", "role": "beheerder"}, headers=_ADMIN)
    assert (await client.post(pad, headers={**_ADMIN, "X-User-Id": "ana"})).status_code == 403
    assert (await client.post(pad, headers={**_ADMIN, "X-User-Id": "kaal"})).status_code == 403
    # Zichzelf niet, en een onbekend account of iemand zonder 2FA is een conflict.
    zelf = await client.post(pad, headers={**_ADMIN, "X-User-Id": "kwijt"})
    assert zelf.status_code == 409
    assert (await client.post("/v1/admin/users/ana/2fa/reset", headers={**_ADMIN, "X-User-Id": "baas"})).status_code == 409

    res = await client.post(pad, headers={**_ADMIN, "X-User-Id": "baas"})
    assert res.status_code == 204
    me = (await client.get("/v1/auth/me", headers={"X-User-Id": "kwijt"})).json()
    assert me["totp_enabled"] is False and me["tfa_nodig"] is True and me["herstelcodes_over"] == 0


async def test_laatste_beheerder_redt_zich_met_een_herstelcode(client):
    """Geen collega voor de reset: dan dragen de herstelcodes het."""
    await client.post(
        "/v1/auth/setup", json={"userid": "baas", "email": "boss@example.com", "password": "wachtwoord1"}
    )
    hdr = {"X-User-Id": "baas"}
    uri = (await client.post("/v1/auth/2fa/begin", json={"password": "wachtwoord1"}, headers=hdr)).json()["otpauth_uri"]
    codes = (await client.post("/v1/auth/2fa/activate", json={"totp": _totp_now(uri)}, headers=hdr)).json()["codes"]

    # Telefoon kwijt: inloggen met een herstelcode, opnieuw koppelen met de volgende. 2FA staat geen moment uit.
    login = await client.post("/v1/auth/verify", json={"userid": "baas", "password": "wachtwoord1", "totp": codes[0]})
    assert login.json()["ok"] is True
    nieuw = (await client.post(
        "/v1/auth/2fa/begin", json={"password": "wachtwoord1", "totp": codes[1]}, headers=hdr
    )).json()["otpauth_uri"]
    assert (await client.get("/v1/auth/me", headers=hdr)).json()["tfa_nodig"] is False
    res = await client.post("/v1/auth/2fa/activate", json={"totp": _totp_now(nieuw)}, headers=hdr)
    assert res.status_code == 200 and len(res.json()["codes"]) == 10
    me = (await client.get("/v1/auth/me", headers=hdr)).json()
    assert me["tfa_nodig"] is False and me["herstelcodes_over"] == 10
    # De oude app geldt niet meer, de nieuwe wel.
    oud = await client.post("/v1/auth/verify", json={"userid": "baas", "password": "wachtwoord1", "totp": _totp_now(uri)})
    assert oud.json()["ok"] is False
    goed = await client.post("/v1/auth/verify", json={"userid": "baas", "password": "wachtwoord1", "totp": _totp_now(nieuw)})
    assert goed.json()["ok"] is True


async def test_enige_beheerder_zonder_2fa_logt_in_en_koppelt_opnieuw(client):
    """Een beheerder zonder 2FA (net gepromoveerd, of gereset door een collega die daarna vertrok) zit niet vast:
    het inloggen vraagt alleen het wachtwoord, het beheer met zijn naam is dicht tot hij koppelt, en koppelen kan
    hij zelf."""
    await _twee_beheerders(client)
    hdr = {"X-User-Id": "baas"}
    assert (await client.post("/v1/admin/users/baas/2fa/reset", headers={**_ADMIN, "X-User-Id": "kwijt"})).status_code == 204
    assert (await client.delete("/v1/admin/users/kwijt", headers=_ADMIN)).status_code == 200

    login = (await client.post("/v1/auth/verify", json={"userid": "baas", "password": "wachtwoord1"})).json()
    assert login["ok"] is True and login["role"] == "beheerder"
    me = (await client.get("/v1/auth/me", headers=hdr)).json()
    assert me["role"] == "beheerder" and me["tfa_nodig"] is True
    persoonlijk = "/v1/admin/users/baas/verbruik/reset"
    assert (await client.post(persoonlijk, headers={**_ADMIN, **hdr})).status_code == 403

    nieuw = (await client.post("/v1/auth/2fa/begin", json={"password": "wachtwoord1"}, headers=hdr)).json()["otpauth_uri"]
    assert (await client.post("/v1/auth/2fa/activate", json={"totp": _totp_now(nieuw)}, headers=hdr)).status_code == 200
    assert (await client.get("/v1/auth/me", headers=hdr)).json()["tfa_nodig"] is False
    assert (await client.post(persoonlijk, headers={**_ADMIN, **hdr})).status_code == 200
    # En de beheerder bleef al die tijd beheerder: het uitzetten raakt de rol niet.
    assert (await client.patch("/v1/admin/users/baas", json={"role": "analist"}, headers=_ADMIN)).status_code == 409


async def test_zonder_master_key_geen_koppeling_en_de_plicht_blijft(monkeypatch):
    _fresh_settings(monkeypatch, LLM_CONFIG_SECRET="", WETSANALYSE_ADMIN_TOKENS="adm:admin-token",
                    WETSANALYSE_AUTH_REQUIRED="0")
    from app import db as _db
    from app import ratelimit

    ratelimit.reset()
    _db.init_engine("sqlite+aiosqlite://")
    await _db.create_all()
    from app.main import app, _waarschuw_zonder_master_key

    _waarschuw_zonder_master_key()  # mag niet vallen
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            await ac.post("/v1/auth/setup", json={"userid": "baas", "email": "b@example.com", "password": "wachtwoord1"})
            hdr = {"X-User-Id": "baas"}
            assert (await ac.post("/v1/auth/2fa/begin", json={"password": "wachtwoord1"}, headers=hdr)).status_code == 400
            assert (await ac.get("/v1/auth/me", headers=hdr)).json()["tfa_nodig"] is True
            # Inloggen blijft werken: alleen het beheer is dicht.
            assert (await ac.post("/v1/auth/verify", json={"userid": "baas", "password": "wachtwoord1"})).json()["ok"] is True
    finally:
        await _db.dispose_engine()


async def test_elke_inlogpoging_staat_in_de_log_zonder_wat_iemand_per_ongeluk_typte(client, caplog):
    """SEC-10/11: de uitkomst van elke poging, en een userid alleen als het account bestaat."""
    import logging

    await client.post("/v1/auth/setup", json={"userid": "baas", "email": "boss@example.com", "password": "wachtwoord1"})
    with caplog.at_level(logging.INFO, logger="app.routers.auth"):
        await client.post("/v1/auth/verify", json={"userid": "baas", "password": "fout"})
        await client.post("/v1/auth/verify", json={"userid": "mijnWachtwoord!", "password": "x"})
        await client.post("/v1/auth/verify", json={"userid": "baas", "password": "wachtwoord1"})
    pogingen = [(r.uitkomst, r.userid) for r in caplog.records if getattr(r, "actie", "") == "inloggen"]
    assert pogingen == [("invalid", "baas"), ("invalid", "(onbekend)"), ("ok", "baas")]
    assert "mijnWachtwoord!" not in caplog.text
