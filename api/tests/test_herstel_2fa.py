"""Het noodherstel van de 2FA van de enige beheerder (`app.herstel_2fa`, azure-infra → `2fa-herstel`).

Het effect moet precies `users.reset_2fa` zijn, en de weigeringen zijn het punt: met een collega die 2FA heeft,
loopt de reset via het beheer en doet dit niets.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pyotp
import pytest

_KLOK = {"t": 1_800_000_000.0}


@pytest.fixture(autouse=True)
def _omgeving(monkeypatch):
    from cryptography.fernet import Fernet

    from app import secrets_crypto, users
    from app.config import get_settings

    monkeypatch.setenv("LLM_CONFIG_SECRET", Fernet.generate_key().decode())
    get_settings.cache_clear()
    secrets_crypto._fernet.cache_clear()
    _KLOK["t"] = 1_800_000_000.0
    monkeypatch.setattr(users, "_nu", lambda: _KLOK["t"])


@pytest.fixture
async def db():
    from app import db as _db

    _db.init_engine("sqlite+aiosqlite://")
    await _db.create_all()
    try:
        yield _db
    finally:
        await _db.dispose_engine()


async def _met_2fa(userid: str) -> None:
    from app import users

    uri = await users.begin_2fa(userid, "wachtwoord1")
    _KLOK["t"] += 30
    code = pyotp.TOTP(parse_qs(urlparse(uri).query)["secret"][0]).at(_KLOK["t"])
    await users.activate_2fa(userid, code)


async def _account(userid: str, role: str, *, tfa: bool) -> None:
    from app import users

    await users.insert_user_met_hash(userid, f"{userid}@example.test", users.hash_password("wachtwoord1"), role=role)
    if tfa:
        await _met_2fa(userid)


async def test_de_enige_beheerder_met_2fa_wordt_gereset(db):
    from app import herstel_2fa, users

    await _account("baas", "beheerder", tfa=True)
    await _account("collega", "beheerder", tfa=False)  # zonder 2FA kan die niet resetten, dus geen weigering
    await _account("analist", "analist", tfa=True)
    apparaat = users.maak_trusted_device(await users.get_user("baas"))
    assert await users.aantal_herstelcodes("baas") == 10

    await herstel_2fa.herstel(" Baas ", door="github:iemand")

    na = await users.get_user("baas")
    assert not na.totp_enabled and na.totp_secret_enc is None and na.sessions_valid_from is not None
    assert await users.aantal_herstelcodes("baas") == 0
    assert await users.valideer_trusted_device(apparaat) is None
    assert users.moet_2fa_koppelen(na)
    # Het wachtwoord blijft nodig, en werkt nog.
    assert (await users.verify_credentials("baas", "wachtwoord1"))[1] == "ok"
    # De andere accounts zijn niet geraakt.
    assert (await users.get_user("analist")).totp_enabled


@pytest.mark.parametrize(
    ("opzet", "userid", "door", "code"),
    [
        ("leeg", "baas", "", "ongeldige_invoer"),
        ("leeg", "x", "github:iemand", "ongeldige_invoer"),
        ("leeg", "baas; drop", "github:iemand", "ongeldige_invoer"),
        ("leeg", "niemand", "github:iemand", "onbekend"),
        ("analist", "baas", "github:iemand", "geen_beheerder"),
        ("inactief", "baas", "github:iemand", "inactief"),
        ("zonder_2fa", "baas", "github:iemand", "geen_2fa"),
        ("collega_met_2fa", "baas", "github:iemand", "andere_beheerder"),
    ],
)
async def test_weigeringen_laten_alles_staan(db, opzet, userid, door, code):
    from app import herstel_2fa, users

    await _account("baas", "analist" if opzet == "analist" else "beheerder", tfa=opzet != "zonder_2fa")
    if opzet == "inactief":
        await _account("tweede", "beheerder", tfa=False)  # de laatste actieve beheerder mag niet weg
        await users.patch_user("baas", active=False)
    if opzet == "collega_met_2fa":
        await _account("collega", "beheerder", tfa=True)
    voor = await users.get_user("baas")

    with pytest.raises(herstel_2fa.Weigering) as fout:
        await herstel_2fa.herstel(userid, door=door)

    assert fout.value.code == code
    assert code in herstel_2fa.WEIGERINGEN
    na = await users.get_user("baas")
    assert (na.totp_enabled, na.totp_secret_enc, na.sessions_valid_from) == (
        voor.totp_enabled, voor.totp_secret_enc, voor.sessions_valid_from,
    )


async def test_een_inactieve_collega_met_2fa_houdt_het_herstel_niet_tegen(db):
    from app import herstel_2fa, users

    await _account("baas", "beheerder", tfa=True)
    await _account("oud", "beheerder", tfa=True)
    await users.patch_user("oud", active=False)

    await herstel_2fa.herstel("baas", door="github:iemand")

    assert not (await users.get_user("baas")).totp_enabled


def test_de_uitleg_bij_een_weigering_noemt_geen_account():
    from app import herstel_2fa

    # De workflow toont de uitleg in een openbare log: een vaste tekst, nooit met een userid erin.
    for tekst in herstel_2fa.WEIGERINGEN.values():
        assert "{" not in tekst


def test_main_geeft_de_uitkomst_op_een_regel_zonder_userid(monkeypatch, capsys):
    from app import herstel_2fa

    async def _draai(userid, door):
        raise herstel_2fa.Weigering("andere_beheerder")

    monkeypatch.setattr(herstel_2fa, "_draai", _draai)
    monkeypatch.setenv("HERSTEL_USERID", "geheimeuserid")
    monkeypatch.setenv("HERSTEL_DOOR", "github:iemand")
    assert herstel_2fa.main() == 2
    uit = capsys.readouterr().out
    assert "UITKOMST: andere_beheerder" in uit
    assert "geheimeuserid" not in uit

    async def _goed(userid, door):
        return herstel_2fa.GERESET

    monkeypatch.setattr(herstel_2fa, "_draai", _goed)
    assert herstel_2fa.main() == 0
    assert "UITKOMST: gereset" in capsys.readouterr().out
