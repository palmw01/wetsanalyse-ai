"""Tokenbudget: het venster, het journaal, de stand en de begrenzing.

Het hart van deze suite is `test_verwijderd_gesprek_verandert_de_stand_niet`: verbruik is een
journaal op `userid`, geen teller die aan werk hangt. Werk weggooien mag geen tokens teruggeven.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

A = {"X-User-Id": "gebruiker-a"}
B = {"X-User-Id": "gebruiker-b"}
_ADMIN = {"Authorization": "Bearer admin-token"}
# `gebruiker-a` is de eerste en dus de beheerder (`maak_testgebruikers`); `gebruiker-b` is analist.
_BEHEERDER = {**_ADMIN, "X-User-Id": "gebruiker-a"}
_ANALIST = {**_ADMIN, "X-User-Id": "gebruiker-b"}


@pytest.fixture
async def client(monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    monkeypatch.setenv("WETSANALYSE_ADMIN_TOKENS", "adm:admin-token")
    monkeypatch.setenv("LLM_CONFIG_SECRET", Fernet.generate_key().decode())
    monkeypatch.setenv("WETSANALYSE_TOKEN_BUDGET", "1000")
    monkeypatch.setenv("WETSANALYSE_TOKEN_BUDGET_DAGEN", "7")

    from app import db, ratelimit, secrets_crypto
    from app.config import get_settings
    from app.deps import get_gesprek_store
    from app.routers.auth import vergeet_actief
    from conftest import maak_testgebruikers

    get_settings.cache_clear()
    get_gesprek_store.cache_clear()
    secrets_crypto._fernet.cache_clear()
    ratelimit.reset()
    # De actief-status-cache is module-globaal en overleeft een suite; zonder deze reset blijft een
    # gebruiker uit een eerdere testdatabase hier als "onbekend" hangen.
    vergeet_actief()

    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    await db.reconcile_schema()
    await maak_testgebruikers("gebruiker-a", "gebruiker-b")

    from app import verbruik
    await verbruik.ensure_seeded(get_settings())
    await _zet_2fa("gebruiker-a", True)

    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    get_settings.cache_clear()
    get_gesprek_store.cache_clear()
    await db.dispose_engine()


async def _zet_2fa(userid: str, aan: bool) -> None:
    from sqlalchemy import update

    from app import db

    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.users).where(db.users.c.userid == userid).values(totp_enabled=aan))


async def _journaal() -> list[tuple]:
    from sqlalchemy import select

    from app import db

    async with db.get_engine().connect() as conn:
        return [tuple(r) for r in (await conn.execute(select(db.token_verbruik).order_by(db.token_verbruik.c.id))).all()]


async def _audit() -> list[dict]:
    from sqlalchemy import select

    from app import db

    async with db.get_engine().connect() as conn:
        return [dict(r) for r in (await conn.execute(select(db.budget_audit).order_by(db.budget_audit.c.id))).mappings().all()]


async def _boek(client, *, invoer=100, uitvoer=50, cache_lees=0, cache_schrijf=0,
                run_id="", gesprek_id="", headers=A):
    return await client.post("/v1/verbruik", headers=headers, json={
        "bron": "agent", "model": "claude-test",
        "invoer": invoer, "uitvoer": uitvoer,
        "cache_lees": cache_lees, "cache_schrijf": cache_schrijf,
        "run_id": run_id, "gesprek_id": gesprek_id,
    })


# --- het venster (pure functies) -----------------------------------------------

def _beleid(dagen=7, anker=None):
    from app.verbruik_contracts import BudgetBeleid

    return BudgetBeleid(
        periode_dagen=dagen,
        anker=anker or datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_venster_op_het_anker():
    from app.verbruik import venster_einde, venster_start

    b = _beleid()
    assert venster_start(b, b.anker) == b.anker
    assert venster_einde(b, b.anker) == b.anker + timedelta(days=7)


def test_venster_midden_en_op_de_grens():
    from app.verbruik import venster_start

    b = _beleid()
    # Middenin het eerste venster → nog steeds het anker.
    assert venster_start(b, b.anker + timedelta(days=3)) == b.anker
    # Precies op de grens → het nieuwe venster begint.
    assert venster_start(b, b.anker + timedelta(days=7)) == b.anker + timedelta(days=7)
    # Drie vensters verder.
    assert venster_start(b, b.anker + timedelta(days=22)) == b.anker + timedelta(days=21)


def test_venster_voor_het_anker():
    """Een handmatig vooruitgezet anker mag geen negatief venster opleveren."""
    from app.verbruik import venster_start

    b = _beleid()
    assert venster_start(b, b.anker - timedelta(days=5)) == b.anker


def _utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def test_venster_blijft_op_maandag_middernacht_over_de_zomertijd():
    """Eind maart gaat de klok vooruit: de reset blijft maandag 00:00 in Nederland, dus een uur eerder in UTC."""
    from app.verbruik import venster_einde, venster_start

    # Maandag 23 maart 2026 00:00 CET = zondag 22 maart 23:00 UTC; zomertijd op zondag 29 maart.
    b = _beleid(anker=_utc(2026, 3, 22, 23, 0))
    maandag_30_maart = _utc(2026, 3, 29, 22, 0)  # 00:00 CEST
    assert venster_einde(b, _utc(2026, 3, 25, 12, 0)) == maandag_30_maart
    # Zondagavond 23:30 zomertijd hoort nog bij de oude week, maandag 00:00 begint de nieuwe.
    assert venster_start(b, _utc(2026, 3, 29, 21, 30)) == b.anker
    assert venster_start(b, maandag_30_maart) == maandag_30_maart
    assert venster_einde(b, maandag_30_maart) == _utc(2026, 4, 5, 22, 0)


def test_venster_blijft_op_maandag_middernacht_over_de_wintertijd():
    """Eind oktober gaat de klok terug: in UTC zou "maandag 00:00" daarna "maandag 01:00" worden."""
    from app.verbruik import venster_einde, venster_start

    # Maandag 19 oktober 2026 00:00 CEST = zondag 18 oktober 22:00 UTC; wintertijd op zondag 25 oktober.
    b = _beleid(anker=_utc(2026, 10, 18, 22, 0))
    maandag_26_oktober = _utc(2026, 10, 25, 23, 0)  # 00:00 CET
    assert venster_einde(b, _utc(2026, 10, 21, 9, 0)) == maandag_26_oktober
    # Zondag 23:30 wintertijd is 22:30 UTC: met een vast UTC-ritme zat dit al in de nieuwe week.
    assert venster_start(b, _utc(2026, 10, 25, 22, 30)) == b.anker
    assert venster_start(b, maandag_26_oktober) == maandag_26_oktober


def test_venster_blijft_maanden_later_op_maandag_middernacht():
    from zoneinfo import ZoneInfo

    from app.verbruik import venster_einde, venster_start

    nl = ZoneInfo("Europe/Amsterdam")
    b = _beleid(anker=_utc(2026, 11, 22, 23, 0))  # maandag 23 november 2026 00:00
    for nu in (_utc(2027, 4, 1, 10, 0), _utc(2027, 7, 15, 3, 0), _utc(2027, 11, 3, 23, 30)):
        for grens in (venster_start(b, nu), venster_einde(b, nu)):
            lokaal = grens.astimezone(nl)
            assert (lokaal.weekday(), lokaal.hour, lokaal.minute) == (0, 0, 0), lokaal
        assert venster_start(b, nu) <= nu < venster_einde(b, nu)


def _maand_beleid(anker, maanden=1):
    from app.verbruik_contracts import BudgetBeleid

    return BudgetBeleid(periode_dagen=30, periode_maanden=maanden, anker=anker)


def test_per_maand_op_de_eerste_om_middernacht():
    """Een maand is geen vast aantal dagen: het venster volgt de kalender, ook over de zomertijd heen."""
    from app.verbruik import venster_einde, venster_start

    b = _maand_beleid(_utc(2026, 1, 31, 23, 0))  # 1 februari 2026 00:00 CET
    # Februari heeft 28 dagen: de reset is 1 maart, niet 3 maart.
    assert venster_einde(b, _utc(2026, 2, 15, 12, 0)) == _utc(2026, 2, 28, 23, 0)
    # 1 april valt in de zomertijd: 00:00 CEST is 22:00 UTC.
    assert venster_start(b, _utc(2026, 4, 10, 12, 0)) == _utc(2026, 3, 31, 22, 0)
    assert venster_start(b, _utc(2026, 3, 31, 21, 59)) == _utc(2026, 2, 28, 23, 0)
    # 1 november weer in de wintertijd.
    assert venster_einde(b, _utc(2026, 10, 20, 12, 0)) == _utc(2026, 10, 31, 23, 0)
    # Over de jaargrens.
    assert venster_start(b, _utc(2027, 1, 5, 12, 0)) == _utc(2026, 12, 31, 23, 0)


def test_per_maand_op_de_31e_valt_terug_op_de_laatste_dag():
    from app.verbruik import venster_einde, venster_start

    b = _maand_beleid(_utc(2026, 1, 30, 23, 0))  # 31 januari 2026 00:00
    assert venster_einde(b, _utc(2026, 2, 10, 12, 0)) == _utc(2026, 2, 27, 23, 0)  # 28 februari
    assert venster_einde(b, _utc(2026, 3, 10, 12, 0)) == _utc(2026, 3, 30, 22, 0)  # 31 maart, zomertijd
    assert venster_start(b, _utc(2026, 4, 10, 12, 0)) == _utc(2026, 3, 30, 22, 0)
    assert venster_einde(b, _utc(2026, 4, 10, 12, 0)) == _utc(2026, 4, 29, 22, 0)  # 30 april


def test_per_kwartaal():
    from app.verbruik import venster_einde

    b = _maand_beleid(_utc(2025, 12, 31, 23, 0), maanden=3)  # 1 januari 2026
    assert venster_einde(b, _utc(2026, 2, 1, 0, 0)) == _utc(2026, 3, 31, 22, 0)  # 1 april 00:00 CEST


def test_het_standaardanker_is_het_begin_van_de_werkweek():
    from app.verbruik import begin_periode

    # Woensdag 25 november 2026 21:28 → maandag 23 november 00:00.
    assert begin_periode(7, _utc(2026, 11, 25, 20, 28)) == _utc(2026, 11, 22, 23, 0)
    # Op maandag zelf: vandaag.
    assert begin_periode(7, _utc(2026, 11, 23, 8, 0)) == _utc(2026, 11, 22, 23, 0)
    # Zondagavond laat in de zomer: nog de week die op maandag begon.
    assert begin_periode(7, _utc(2026, 7, 12, 21, 30)) == _utc(2026, 7, 5, 22, 0)
    assert begin_periode(1, _utc(2026, 11, 25, 20, 28)) == _utc(2026, 11, 24, 23, 0)


def test_een_anker_zonder_tijdzone_is_nederlandse_tijd():
    from app.verbruik import lokaal_anker

    assert lokaal_anker(datetime(2026, 11, 23, 0, 0)) == _utc(2026, 11, 22, 23, 0)
    assert lokaal_anker(datetime(2026, 7, 6, 0, 0)) == _utc(2026, 7, 5, 22, 0)
    # Met een tijdzone blijft het hetzelfde moment.
    assert lokaal_anker(_utc(2026, 11, 22, 23, 0)) == _utc(2026, 11, 22, 23, 0)


# --- boeken en optellen ---------------------------------------------------------

async def test_stand_telt_alle_vier_de_soorten(client):
    await _boek(client, invoer=100, uitvoer=50, cache_lees=200, cache_schrijf=25)
    r = await client.get("/v1/verbruik", headers=A)
    assert r.status_code == 200
    stand = r.json()
    # Het volle promptvolume telt: caching verlaagt de factuur, niet het budget.
    assert stand["gebruikt"] == 375
    assert stand["budget"] == 1000
    assert stand["percentage"] == 37
    assert stand["resterend"] == 625
    assert stand["waarschuwing"] is False and stand["geblokkeerd"] is False


async def test_verbruik_is_per_gebruiker(client):
    await _boek(client, invoer=500, uitvoer=0, headers=A)
    assert (await client.get("/v1/verbruik", headers=A)).json()["gebruikt"] == 500
    assert (await client.get("/v1/verbruik", headers=B)).json()["gebruikt"] == 0


async def test_boeken_is_idempotent_op_run_id(client):
    r1 = await _boek(client, invoer=100, uitvoer=0, run_id="run-1")
    r2 = await _boek(client, invoer=100, uitvoer=0, run_id="run-1")
    assert r1.json()["geboekt"] is True
    assert r2.json()["geboekt"] is False
    assert (await client.get("/v1/verbruik", headers=A)).json()["gebruikt"] == 100


async def test_lege_boeking_doet_niets(client):
    r = await _boek(client, invoer=0, uitvoer=0)
    assert r.json()["geboekt"] is False
    assert (await client.get("/v1/verbruik", headers=A)).json()["gebruikt"] == 0


async def test_verbruik_buiten_het_venster_telt_niet_mee(client):
    """Een boeking van vóór het huidige venster valt er vanzelf buiten – geen reset nodig."""
    from datetime import timedelta

    from sqlalchemy import insert

    from app import db, verbruik
    from app.user import _utcnow

    # Verschuif het anker naar nu, zodat "gisteren" buiten het venster valt.
    await verbruik.zet_beleid(periode_dagen=7, actief=True, anker=_utcnow())
    async with db.get_engine().begin() as conn:
        await conn.execute(insert(db.token_verbruik).values(
            userid="gebruiker-a", bron="agent", model="", invoer=900, uitvoer=0,
            cache_lees=0, cache_schrijf=0, tijdstip=_utcnow() - timedelta(days=1),
        ))
    assert (await client.get("/v1/verbruik", headers=A)).json()["gebruikt"] == 0

    # En binnen het venster telt het wél.
    await _boek(client, invoer=10, uitvoer=0)
    assert (await client.get("/v1/verbruik", headers=A)).json()["gebruikt"] == 10


# --- het hart: werk weggooien geeft geen tokens terug ---------------------------

async def test_verwijderd_gesprek_verandert_de_stand_niet(client):
    r = await client.post("/v1/gesprekken", json={"titel": "Test"}, headers=A)
    gesprek_id = r.json()["id"]

    await _boek(client, invoer=400, uitvoer=100, gesprek_id=gesprek_id, run_id="run-x")
    assert (await client.get("/v1/verbruik", headers=A)).json()["gebruikt"] == 500

    assert (await client.delete(f"/v1/gesprekken/{gesprek_id}", headers=A)).status_code == 204
    # Het gesprek is weg, het verbruik niet.
    assert (await client.get("/v1/verbruik", headers=A)).json()["gebruikt"] == 500


# --- drempels en begrenzing -----------------------------------------------------

async def test_waarschuwing_vanaf_negentig_procent(client):
    await _boek(client, invoer=890, uitvoer=0)
    assert (await client.get("/v1/verbruik", headers=A)).json()["waarschuwing"] is False
    await _boek(client, invoer=10, uitvoer=0)
    stand = (await client.get("/v1/verbruik", headers=A)).json()
    assert stand["percentage"] == 90 and stand["waarschuwing"] is True
    assert stand["geblokkeerd"] is False


async def test_blokkade_bij_vol_budget(client):
    await _boek(client, invoer=1000, uitvoer=0)
    stand = (await client.get("/v1/verbruik", headers=A)).json()
    assert stand["geblokkeerd"] is True and stand["percentage"] == 100
    assert (await client.get("/v1/verbruik/controle", headers=A)).json()["toegestaan"] is False
    # De andere gebruiker raakt niets.
    assert (await client.get("/v1/verbruik/controle", headers=B)).json()["toegestaan"] is True


async def test_percentage_kapt_op_honderd(client):
    """Overschrijden mag: een lopende beurt wordt niet afgekapt. De meter loopt niet over."""
    await _boek(client, invoer=5000, uitvoer=0)
    stand = (await client.get("/v1/verbruik", headers=A)).json()
    assert stand["percentage"] == 100
    assert stand["gebruikt"] == 5000  # het ruwe getal blijft eerlijk
    assert stand["resterend"] == 0


async def test_begrenzing_uit_blokkeert_niets(client):
    from app import verbruik

    await _boek(client, invoer=5000, uitvoer=0)
    await verbruik.zet_beleid(periode_dagen=7, actief=False)
    stand = (await client.get("/v1/verbruik", headers=A)).json()
    assert stand["actief"] is False and stand["geblokkeerd"] is False
    # Er wordt nog steeds gemeten.
    assert stand["gebruikt"] == 5000


# --- het budget volgt uit de rol ------------------------------------------------

async def test_de_env_seedt_elke_rol_en_daarna_niet_meer(client):
    from app import verbruik
    from app.config import Settings

    r = await client.get("/v1/admin/budget", headers=_ADMIN)
    assert {x["rol"]: x["tokens"] for x in r.json()["rollen"]} == {"beheerder": 1000, "analist": 1000}

    await client.put("/v1/admin/budget/rollen/analist", json={"tokens": 300}, headers=_BEHEERDER)
    instellingen = Settings()
    instellingen.token_budget = 9999
    await verbruik.ensure_seeded(instellingen)
    assert (await client.get("/v1/verbruik", headers=B)).json()["budget"] == 300


async def test_elke_rol_heeft_zijn_eigen_budget(client):
    assert (await client.put(
        "/v1/admin/budget/rollen/beheerder", json={"tokens": 5000}, headers=_BEHEERDER
    )).status_code == 200
    assert (await client.put(
        "/v1/admin/budget/rollen/analist", json={"tokens": 300}, headers=_BEHEERDER
    )).status_code == 200

    stand_a = (await client.get("/v1/verbruik", headers=A)).json()
    stand_b = (await client.get("/v1/verbruik", headers=B)).json()
    assert (stand_a["budget"], stand_a["rol"]) == (5000, "beheerder")
    assert (stand_b["budget"], stand_b["rol"]) == (300, "analist")

    regels = {x["userid"]: x for x in (await client.get("/v1/admin/verbruik", headers=_ADMIN)).json()}
    assert regels["gebruiker-a"]["budget"] == 5000 and regels["gebruiker-a"]["rol"] == "beheerder"
    assert regels["gebruiker-b"]["budget"] == 300 and regels["gebruiker-b"]["rol"] == "analist"


async def test_een_rolbudget_begrenst_ook(client):
    await client.put("/v1/admin/budget/rollen/analist", json={"tokens": 100}, headers=_BEHEERDER)
    await _boek(client, invoer=100, uitvoer=0, headers=B)
    assert (await client.get("/v1/verbruik/controle", headers=B)).json()["toegestaan"] is False
    assert (await client.get("/v1/verbruik/controle", headers=A)).json()["toegestaan"] is True


async def test_rolwissel_geeft_meteen_het_budget_van_de_nieuwe_rol(client):
    await client.put("/v1/admin/budget/rollen/beheerder", json={"tokens": 5000}, headers=_BEHEERDER)
    await client.put("/v1/admin/budget/rollen/analist", json={"tokens": 300}, headers=_BEHEERDER)
    await _boek(client, invoer=400, uitvoer=0, headers=B)
    assert (await client.get("/v1/verbruik", headers=B)).json()["geblokkeerd"] is True

    r = await client.patch("/v1/admin/users/gebruiker-b", json={"role": "beheerder"}, headers=_ADMIN)
    assert r.status_code == 200

    stand = (await client.get("/v1/verbruik", headers=B)).json()
    assert (stand["budget"], stand["rol"]) == (5000, "beheerder")
    # Het verbruik reist mee: een rolwissel is geen reset.
    assert stand["gebruikt"] == 400 and stand["geblokkeerd"] is False
    regels = {x["userid"]: x for x in (await client.get("/v1/admin/verbruik", headers=_ADMIN)).json()}
    assert regels["gebruiker-b"]["budget"] == 5000


async def test_een_limiet_per_gebruiker_bestaat_niet_meer(client):
    from app import db
    from app.main import app

    for veld in ({"token_budget": 100}, {"token_budget_wissen": True}):
        r = await client.patch("/v1/admin/users/gebruiker-a", json=veld, headers=_ADMIN)
        assert r.status_code == 422, veld
    assert (await client.get("/v1/verbruik", headers=A)).json()["budget"] == 1000

    assert "token_budget" not in db.users.c and "tokens" not in db.budget_beleid.c
    gebruiker = (await client.get("/v1/admin/users", headers=_ADMIN)).json()[0]
    assert "token_budget" not in gebruiker
    stand = (await client.get("/v1/verbruik", headers=A)).json()
    assert "eigen_budget" not in stand
    assert "eigen_budget" not in (await client.get("/v1/admin/verbruik", headers=_ADMIN)).json()[0]
    # De enige routes met een budget erin zijn die van het beleid en de rollen.
    paden = {pad for pad in app.openapi()["paths"] if "budget" in pad}
    assert paden == {"/v1/admin/budget", "/v1/admin/budget/proef", "/v1/admin/budget/rollen/{rol}"}


async def test_reconcile_haalt_de_oude_kolommen_weg(client):
    from sqlalchemy import inspect, text

    from app import db

    async with db.get_engine().begin() as conn:
        await conn.execute(text("ALTER TABLE users ADD COLUMN token_budget INTEGER"))
        await conn.execute(text("ALTER TABLE budget_beleid ADD COLUMN tokens INTEGER"))
    await db.reconcile_schema()
    await db.reconcile_schema()  # idempotent

    async with db.get_engine().connect() as conn:
        for tabel, kolom in (("users", "token_budget"), ("budget_beleid", "tokens")):
            namen = await conn.run_sync(lambda c, t=tabel: {k["name"] for k in inspect(c).get_columns(t)})
            assert kolom not in namen


# --- beheer ---------------------------------------------------------------------

async def test_beleid_lezen_en_wijzigen(client):
    r = await client.get("/v1/admin/budget", headers=_ADMIN)
    assert r.status_code == 200 and r.json()["periode_dagen"] == 7
    assert r.json()["reset_op"] and r.json()["periode_maanden"] == 0
    # Een vers beleid loopt per week vanaf maandag 00:00 Nederlandse tijd.
    from zoneinfo import ZoneInfo
    anker = datetime.fromisoformat(r.json()["anker"]).astimezone(ZoneInfo("Europe/Amsterdam"))
    assert (anker.weekday(), anker.hour, anker.minute) == (0, 0, 0)
    assert "tokens" not in r.json()

    r = await client.put(
        "/v1/admin/budget", json={"periode_dagen": 30, "actief": True}, headers=_BEHEERDER,
    )
    assert r.status_code == 200 and r.json()["periode_dagen"] == 30
    assert r.json()["updated_by"] == "gebruiker-a"


async def test_beleid_op_weekdag_en_tijd(client):
    """De UI stuurt "maandag 00:00" als wandkloktijd; de api bewaart het moment en rekent de vensters lokaal."""
    r = await client.put(
        "/v1/admin/budget", json={"periode_dagen": 7, "actief": True, "anker": "2026-11-23T00:00:00"},
        headers=_BEHEERDER,
    )
    assert r.status_code == 200
    b = r.json()
    assert datetime.fromisoformat(b["anker"]) == _utc(2026, 11, 22, 23, 0)
    assert b["tijdzone"] == "Europe/Amsterdam"
    from zoneinfo import ZoneInfo
    for veld in ("venster_start", "reset_op"):
        lokaal = datetime.fromisoformat(b[veld]).astimezone(ZoneInfo("Europe/Amsterdam"))
        assert (lokaal.weekday(), lokaal.hour, lokaal.minute) == (0, 0, 0)


async def test_beleid_per_maand(client):
    r = await client.put(
        "/v1/admin/budget",
        json={"periode_dagen": 30, "periode_maanden": 1, "actief": True, "anker": "2026-11-01T00:00:00"},
        headers=_BEHEERDER,
    )
    assert r.status_code == 200
    b = r.json()
    assert b["periode_maanden"] == 1
    from zoneinfo import ZoneInfo
    for veld in ("venster_start", "reset_op"):
        lokaal = datetime.fromisoformat(b[veld]).astimezone(ZoneInfo("Europe/Amsterdam"))
        assert (lokaal.day, lokaal.hour, lokaal.minute) == (1, 0, 0)
    regel = (await _audit())[-1]
    assert regel["details"]["nieuw"]["periode_maanden"] == 1
    # Terug naar weken: 0 maanden.
    r = await client.put("/v1/admin/budget", json={"periode_dagen": 7, "actief": True}, headers=_BEHEERDER)
    assert r.json()["periode_maanden"] == 0
    assert (await client.put("/v1/admin/budget", json={"periode_dagen": 7, "periode_maanden": 13, "actief": True},
                             headers=_BEHEERDER)).status_code == 422


async def test_proef_noemt_wie_in_het_nieuwe_venster_boven_budget_zit(client):
    """Een anker verder terug haalt verbruik terug dat het oude venster al had verrekend."""
    from sqlalchemy import insert

    from app import db, verbruik
    from app.user import _utcnow

    await verbruik.zet_beleid(periode_dagen=7, actief=True, anker=_utcnow())
    async with db.get_engine().begin() as conn:
        await conn.execute(insert(db.token_verbruik).values(
            userid="gebruiker-b", bron="agent", model="", invoer=1200, uitvoer=0,
            cache_lees=0, cache_schrijf=0, tijdstip=_utcnow() - timedelta(days=2),
        ))
    voor = (await client.get("/v1/admin/budget", headers=_ADMIN)).json()
    audit_voor = await _audit()

    terug = (_utcnow() - timedelta(days=3)).replace(tzinfo=None).isoformat()
    r = await client.post("/v1/admin/budget/proef", json={"periode_dagen": 7, "actief": True, "anker": terug},
                          headers=_ADMIN)
    assert r.status_code == 200
    assert r.json()["boven_budget"] == ["gebruiker-b"]
    # Een proef slaat niets op.
    assert (await client.get("/v1/admin/budget", headers=_ADMIN)).json()["anker"] == voor["anker"]
    assert await _audit() == audit_voor

    # Het huidige anker: dat verbruik viel er al buiten.
    r = await client.post("/v1/admin/budget/proef", json={"periode_dagen": 7, "actief": True}, headers=_ADMIN)
    assert r.json()["boven_budget"] == []


async def test_beleid_weigert_onzin(client):
    r = await client.put(
        "/v1/admin/budget", json={"periode_dagen": 0, "actief": True}, headers=_BEHEERDER
    )
    assert r.status_code == 422  # ge=1 op het model


@pytest.mark.parametrize("tokens", [0, -1, None, 3_000_000_000])
async def test_rolbudget_weigert_onzin(client, tokens):
    r = await client.put("/v1/admin/budget/rollen/analist", json={"tokens": tokens}, headers=_BEHEERDER)
    assert r.status_code == 422


async def test_rolbudget_kent_alleen_de_rollen(client):
    r = await client.put("/v1/admin/budget/rollen/stagiair", json={"tokens": 5}, headers=_BEHEERDER)
    assert r.status_code == 404


async def test_wijzigingen_staan_in_de_audit(client):
    await client.put("/v1/admin/budget/rollen/analist", json={"tokens": 300}, headers=_BEHEERDER)
    await client.put("/v1/admin/budget/rollen/analist", json={"tokens": 400}, headers=_BEHEERDER)
    await client.put("/v1/admin/budget", json={"periode_dagen": 14, "actief": False}, headers=_BEHEERDER)

    regels = await _audit()
    assert [(x["actie"], x["doel"], x["door"]) for x in regels] == [
        ("rolbudget_gewijzigd", "analist", "gebruiker-a"),
        ("rolbudget_gewijzigd", "analist", "gebruiker-a"),
        ("beleid_gewijzigd", "", "gebruiker-a"),
    ]
    assert regels[0]["details"] == {"oud": 1000, "nieuw": 300}
    assert regels[1]["details"] == {"oud": 300, "nieuw": 400}
    assert regels[2]["details"]["oud"] == {"periode_dagen": 7, "periode_maanden": 0, "actief": True}
    assert regels[2]["details"]["nieuw"]["periode_dagen"] == 14


# --- de reset -------------------------------------------------------------------

_RESET_B = "/v1/admin/users/gebruiker-b/verbruik/reset"


async def test_reset_geeft_het_volle_budget_terug(client):
    await _boek(client, invoer=1500, uitvoer=0, headers=B)
    voor = (await client.get("/v1/verbruik", headers=B)).json()
    assert voor["geblokkeerd"] is True

    r = await client.post(_RESET_B, headers=_BEHEERDER)
    assert r.status_code == 200
    assert r.json()["gebruikt"] == 0 and r.json()["gereset_door"] == "gebruiker-a"
    assert r.json()["gereset_op"]

    stand = (await client.get("/v1/verbruik", headers=B)).json()
    assert stand["gebruikt"] == 0 and stand["resterend"] == 1000 and stand["geblokkeerd"] is False
    assert (await client.get("/v1/verbruik/controle", headers=B)).json()["toegestaan"] is True
    # Het venster schuift niet op, en wie het deed gaat de gebruiker niets aan.
    assert stand["reset_op"] == voor["reset_op"]
    assert stand["gereset_op"] and stand["gereset_door"] == ""


async def test_reset_laat_het_journaal_intact(client):
    await _boek(client, invoer=600, uitvoer=10, run_id="r1", headers=B)
    await _boek(client, invoer=700, uitvoer=20, run_id="r2", headers=B)
    await _boek(client, invoer=5, uitvoer=5, run_id="r3", headers=A)
    voor = await _journaal()
    assert len(voor) == 3

    assert (await client.post(_RESET_B, headers=_BEHEERDER)).status_code == 200

    # Geen rij gewijzigd, geen rij weg, en geen tegenboeking erbij.
    assert await _journaal() == voor
    # Een herhaalde melding van een oude beurt blijft ontdubbeld: het journaal kent hem nog.
    assert (await _boek(client, invoer=600, uitvoer=10, run_id="r1", headers=B)).json()["geboekt"] is False


async def test_wat_na_de_reset_geboekt_wordt_telt_weer_mee(client):
    await _boek(client, invoer=900, uitvoer=0, headers=B)
    await client.post(_RESET_B, headers=_BEHEERDER)
    await _boek(client, invoer=70, uitvoer=0, headers=B)

    assert (await client.get("/v1/verbruik", headers=B)).json()["gebruikt"] == 70
    regels = {x["userid"]: x for x in (await client.get("/v1/admin/verbruik", headers=_ADMIN)).json()}
    assert regels["gebruiker-b"]["gebruikt"] == 70

    # Een tweede reset begint opnieuw, en het overzicht toont de laatste.
    await client.post(_RESET_B, headers=_BEHEERDER)
    assert (await client.get("/v1/verbruik", headers=B)).json()["gebruikt"] == 0


async def test_reset_raakt_alleen_de_gebruiker_zelf(client):
    await _boek(client, invoer=100, uitvoer=0, headers=A)
    await _boek(client, invoer=200, uitvoer=0, headers=B)
    await client.post(_RESET_B, headers=_BEHEERDER)

    assert (await client.get("/v1/verbruik", headers=A)).json()["gebruikt"] == 100
    regels = {x["userid"]: x for x in (await client.get("/v1/admin/verbruik", headers=_ADMIN)).json()}
    assert regels["gebruiker-a"]["gebruikt"] == 100 and regels["gebruiker-a"]["gereset_op"] is None


async def test_een_reset_uit_een_vorig_venster_doet_niets_meer(client):
    from sqlalchemy import update

    from app import db, verbruik
    from app.user import _utcnow

    await client.post(_RESET_B, headers=_BEHEERDER)
    await _boek(client, invoer=100, uitvoer=0, headers=B)
    # Een nieuw venster dat vóór de reset begon telt alles; dezelfde reset, naar achteren in de tijd.
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.budget_audit).values(tijdstip=_utcnow() - timedelta(days=30)))
    assert await verbruik.reset_in_venster("gebruiker-b", _utcnow() - timedelta(days=1)) is None
    regels = {x["userid"]: x for x in (await client.get("/v1/admin/verbruik", headers=_ADMIN)).json()}
    assert regels["gebruiker-b"]["gereset_op"] is None and regels["gebruiker-b"]["gereset_door"] == ""


async def test_reset_staat_in_de_audit(client):
    await _boek(client, invoer=800, uitvoer=0, headers=B)
    await client.post(_RESET_B, headers=_BEHEERDER)

    regels = await _audit()
    assert len(regels) == 1
    assert (regels[0]["actie"], regels[0]["doel"], regels[0]["door"]) == ("verbruik_reset", "gebruiker-b", "gebruiker-a")
    assert regels[0]["details"] == {"gebruikt": 800, "budget": 1000}


async def test_reset_van_onbekende_gebruiker(client):
    assert (await client.post("/v1/admin/users/niemand/verbruik/reset", headers=_BEHEERDER)).status_code == 404


# --- wie het mag ----------------------------------------------------------------

_WIJZIGINGEN = [
    ("POST", _RESET_B, None),
    ("PUT", "/v1/admin/budget/rollen/analist", {"tokens": 5}),
    ("PUT", "/v1/admin/budget", {"periode_dagen": 3, "actief": True}),
]


@pytest.mark.parametrize("methode,pad,body", _WIJZIGINGEN)
async def test_een_analist_mag_het_niet(client, methode, pad, body):
    """Ook niet met een geldig admin-token: de rol uit `X-User-Id` beslist."""
    await _zet_2fa("gebruiker-b", True)
    await _boek(client, invoer=200, uitvoer=0, headers=B)
    r = await client.request(methode, pad, json=body, headers=_ANALIST)
    assert r.status_code == 403
    assert await _audit() == []
    assert (await client.get("/v1/verbruik", headers=B)).json()["gebruikt"] == 200


@pytest.mark.parametrize("methode,pad,body", _WIJZIGINGEN)
async def test_een_beheerder_zonder_2fa_mag_het_niet(client, methode, pad, body):
    await _zet_2fa("gebruiker-a", False)
    r = await client.request(methode, pad, json=body, headers=_BEHEERDER)
    assert r.status_code == 403 and r.json()["detail"] == "Koppel eerst zelf 2FA."
    assert await _audit() == []


@pytest.mark.parametrize("methode,pad,body", _WIJZIGINGEN)
async def test_een_kaal_admin_token_mag_het_niet(client, methode, pad, body):
    """Geen persoon, dus niets om in de audit te zetten: de admin-MCP komt hier niet."""
    r = await client.request(methode, pad, json=body, headers=_ADMIN)
    assert r.status_code in (400, 401, 403)
    assert await _audit() == []


@pytest.mark.parametrize("methode,pad,body", _WIJZIGINGEN)
async def test_zonder_admin_token_mag_het_niet(client, methode, pad, body):
    r = await client.request(methode, pad, json=body, headers={"X-User-Id": "gebruiker-a"})
    assert r.status_code == 401
    assert await _audit() == []


async def test_beheeroverzicht_zwaarste_eerst(client):
    await _boek(client, invoer=100, uitvoer=0, headers=A)
    await _boek(client, invoer=800, uitvoer=0, headers=B)

    r = await client.get("/v1/admin/verbruik", headers=_ADMIN)
    assert r.status_code == 200
    regels = r.json()
    assert [x["userid"] for x in regels[:2]] == ["gebruiker-b", "gebruiker-a"]
    assert regels[0]["gebruikt"] == 800


async def test_admin_endpoints_vereisen_token(client):
    assert (await client.get("/v1/admin/budget")).status_code == 401
    assert (await client.get("/v1/admin/verbruik")).status_code == 401
    assert (await client.put(
        "/v1/admin/budget", json={"periode_dagen": 1, "actief": True}
    )).status_code == 401


def test_een_budget_van_nul_is_geen_tokens():
    """Budget 0 toonde een volle meter maar blokkeerde niemand (API-06)."""
    from app import verbruik

    beleid = verbruik.BudgetBeleid(periode_dagen=7, anker=datetime(2026, 1, 1, tzinfo=timezone.utc), actief=True)
    stand = verbruik._maak_stand("x", 0, 0, "analist", beleid)
    assert stand.geblokkeerd is True and stand.percentage == 100


async def test_dezelfde_beurt_twee_keer_tegelijk_boekt_een_keer(client):
    """De toets vóór het schrijven dekt twee gelijktijdige meldingen niet; de unieke index wel (API-07)."""
    from sqlalchemy import insert
    from sqlalchemy.exc import IntegrityError

    from app import db, verbruik

    assert await verbruik.boek("gebruiker-a", bron="agent", invoer=10, run_id="r1")
    rij = dict(userid="gebruiker-a", bron="agent", model="", invoer=10, uitvoer=0, cache_lees=0, cache_schrijf=0,
               run_id="r1", tijdstip=datetime.now(timezone.utc))
    with pytest.raises(IntegrityError):
        async with db.get_engine().begin() as conn:
            await conn.execute(insert(db.token_verbruik).values(**rij))
    # Zonder run ontdubbelt niets: de verbindingstest boekt elke keer.
    assert await verbruik.boek("gebruiker-a", bron="test", invoer=1)
    assert await verbruik.boek("gebruiker-a", bron="test", invoer=1)
