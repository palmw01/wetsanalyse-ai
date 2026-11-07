"""De inlogrem op `/v1/auth/verify` (SEC-4): alleen missers tellen, op (client-IP, userid), plus een globale teller.

Het IP komt uit `X-Client-IP`, en alleen van de frontend-client: van elke andere client is de header een bewering.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pyotp
import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient

_MAX = 3
_FRONTEND = {"Authorization": "Bearer ftok"}
_OVERIG = {"Authorization": "Bearer otok"}


def _van(ip: str, client: dict[str, str] = _FRONTEND) -> dict[str, str]:
    return {**client, "X-Client-IP": ip}


@pytest.fixture
async def ac(monkeypatch):
    from app import db, ratelimit, secrets_crypto, users
    from app.config import get_settings

    for k, v in {
        "WETSANALYSE_API_TOKENS": "frontend:ftok,overig:otok",
        "WETSANALYSE_RATE_LIMIT_MAX": str(_MAX),
        "WETSANALYSE_RATE_LIMIT_WINDOW": "60",
        "LLM_CONFIG_SECRET": Fernet.generate_key().decode(),
    }.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    secrets_crypto._fernet.cache_clear()
    klok = {"t": 1_800_000_000.0}
    monkeypatch.setattr(users, "_nu", lambda: klok["t"])
    ratelimit.reset()
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()

    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/v1/auth/setup", json={"userid": "baas", "email": "b@example.com", "password": "wachtwoord1"},
            headers=_FRONTEND,
        )
        assert r.status_code == 201
        client.klok = klok  # type: ignore[attr-defined]
        yield client
    await db.dispose_engine()
    ratelimit.reset()


async def _verify(ac, headers, password="fout", **extra):
    return await ac.post("/v1/auth/verify", json={"userid": "baas", "password": password, **extra}, headers=headers)


async def test_missers_van_een_aanvaller_sluiten_de_echte_gebruiker_niet_buiten(ac):
    for _ in range(_MAX):
        assert (await _verify(ac, _van("203.0.113.66"))).json()["code"] == "invalid"
    assert (await _verify(ac, _van("203.0.113.66"))).status_code == 429, "de aanvaller zelf is geremd"

    echt = await _verify(ac, _van("198.51.100.7"), password="wachtwoord1")
    assert echt.status_code == 200 and echt.json()["ok"] is True
    # Ook een tikfout van de echte gebruiker kan nog: hij heeft zijn eigen teller.
    assert (await _verify(ac, _van("198.51.100.7"))).status_code == 200


async def test_een_geslaagde_login_telt_niet(ac):
    for _ in range(_MAX * 2):
        r = await _verify(ac, _van("198.51.100.7"), password="wachtwoord1")
        assert r.status_code == 200 and r.json()["ok"] is True
    # De volle ruimte voor missers staat nog.
    for _ in range(_MAX):
        assert (await _verify(ac, _van("198.51.100.7"))).status_code == 200
    assert (await _verify(ac, _van("198.51.100.7"))).status_code == 429


async def test_de_ip_header_telt_alleen_van_de_frontend_client(ac):
    # Een andere client kan met een verzonnen IP per poging de rem niet ontlopen: zijn header telt niet.
    for i in range(_MAX):
        assert (await _verify(ac, _van(f"192.0.2.{i}", _OVERIG))).status_code == 200
    assert (await _verify(ac, _van("192.0.2.99", _OVERIG))).status_code == 429

    # Van de frontend telt hij wel: daar is elk IP een eigen teller.
    for i in range(_MAX + 1):
        assert (await _verify(ac, _van(f"192.0.2.{i}"))).status_code == 200


async def test_een_onleesbaar_ip_valt_terug_op_de_userid(ac):
    for i in range(_MAX):
        assert (await _verify(ac, _van(f"geen-ip-{i}"))).status_code == 200
    assert (await _verify(ac, _van("ook-geen-ip"))).status_code == 429


async def test_de_2fa_stap_telt_alleen_een_foute_code(ac):
    hdr = {**_FRONTEND, "X-User-Id": "baas"}
    uri = (await ac.post("/v1/auth/2fa/begin", json={"password": "wachtwoord1"}, headers=hdr)).json()["otpauth_uri"]
    totp = pyotp.TOTP(parse_qs(urlparse(uri).query)["secret"][0])
    ac.klok["t"] += 30
    assert (await ac.post("/v1/auth/2fa/activate", json={"totp": totp.at(ac.klok["t"])}, headers=hdr)).status_code == 200

    ip = _van("198.51.100.7")
    # Wachtwoord goed, nog geen code: het gewone eerste deel van een 2FA-login, geen misser.
    for _ in range(_MAX + 1):
        stap_a = (await _verify(ac, ip, password="wachtwoord1")).json()
        assert stap_a["code"] == "totp_required"
    # Een foute code is wel een misser.
    for _ in range(_MAX):
        r = await _verify(ac, ip, password="", ticket=stap_a["ticket"], totp="000000")
        assert r.status_code == 200 and r.json()["code"] == "totp_required"
    assert (await _verify(ac, ip, password="", ticket=stap_a["ticket"], totp="000000")).status_code == 429


def test_de_globale_rem_telt_missers_over_alle_sleutels(monkeypatch):
    from app import ratelimit
    from app.config import get_settings

    monkeypatch.setenv("WETSANALYSE_RATE_LIMIT_MAX", "2")
    get_settings.cache_clear()
    ratelimit.reset()
    try:
        plafond = 2 * ratelimit._LOGIN_GLOBAL_FACTOR
        for i in range(plafond):
            assert ratelimit.login_allowed(f"gebruiker{i}", "203.0.113.1") is not None
        assert ratelimit.login_allowed("nog-een", "198.51.100.7") is None, "spraying raakt het globale plafond"
        # Een geweigerde poging telt nergens: de sleutel bestaat niet eens.
        assert ratelimit._login_sleutel("nog-een", "198.51.100.7") not in ratelimit._hits

        # Wat geen misser was, komt terug van het plafond.
        ratelimit.reset()
        for i in range(plafond * 2):
            poging = ratelimit.login_allowed(f"gebruiker{i}", "203.0.113.1")
            assert poging is not None
            ratelimit.login_telt_niet(poging)
        assert not ratelimit._hits
    finally:
        ratelimit.reset()
        get_settings.cache_clear()
