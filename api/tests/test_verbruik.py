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
    # Een nieuwe kolom op `users` (token_budget) komt er op een bestaande tabel via reconcile.
    await db.reconcile_schema()
    await maak_testgebruikers("gebruiker-a", "gebruiker-b")

    from app import verbruik
    await verbruik.ensure_seeded(get_settings())

    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    get_settings.cache_clear()
    get_gesprek_store.cache_clear()
    await db.dispose_engine()


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
        tokens=1000, periode_dagen=dagen,
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
    await verbruik.zet_beleid(tokens=1000, periode_dagen=7, actief=True, anker=_utcnow())
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
    await verbruik.zet_beleid(tokens=1000, periode_dagen=7, actief=False)
    stand = (await client.get("/v1/verbruik", headers=A)).json()
    assert stand["actief"] is False and stand["geblokkeerd"] is False
    # Er wordt nog steeds gemeten.
    assert stand["gebruikt"] == 5000


# --- per-gebruiker budget -------------------------------------------------------

async def test_eigen_budget_wint_van_het_beleid(client):
    r = await client.patch(
        "/v1/admin/users/gebruiker-a", json={"token_budget": 100}, headers=_ADMIN
    )
    assert r.status_code == 200 and r.json()["token_budget"] == 100

    await _boek(client, invoer=100, uitvoer=0)
    stand = (await client.get("/v1/verbruik", headers=A)).json()
    assert stand["budget"] == 100 and stand["geblokkeerd"] is True
    assert stand["eigen_budget"] is True
    # De ander volgt nog gewoon het beleid.
    assert (await client.get("/v1/verbruik", headers=B)).json()["budget"] == 1000


async def test_eigen_budget_wissen(client):
    await client.patch("/v1/admin/users/gebruiker-a", json={"token_budget": 100}, headers=_ADMIN)
    r = await client.patch(
        "/v1/admin/users/gebruiker-a", json={"token_budget_wissen": True}, headers=_ADMIN
    )
    assert r.json()["token_budget"] is None
    assert (await client.get("/v1/verbruik", headers=A)).json()["budget"] == 1000


async def test_patch_zonder_budget_laat_het_staan(client):
    """Een rolwijziging mag het budget niet stilzwijgend wissen."""
    await client.patch("/v1/admin/users/gebruiker-a", json={"token_budget": 250}, headers=_ADMIN)
    r = await client.patch("/v1/admin/users/gebruiker-a", json={"role": "beheerder"}, headers=_ADMIN)
    assert r.json()["token_budget"] == 250


# --- beheer ---------------------------------------------------------------------

async def test_beleid_lezen_en_wijzigen(client):
    r = await client.get("/v1/admin/budget", headers=_ADMIN)
    assert r.status_code == 200 and r.json()["tokens"] == 1000 and r.json()["periode_dagen"] == 7
    assert r.json()["reset_op"]

    r = await client.put(
        "/v1/admin/budget", json={"tokens": 500_000, "periode_dagen": 30, "actief": True},
        headers=_ADMIN,
    )
    assert r.status_code == 200 and r.json()["tokens"] == 500_000
    assert (await client.get("/v1/verbruik", headers=A)).json()["budget"] == 500_000


async def test_beleid_weigert_onzin(client):
    r = await client.put(
        "/v1/admin/budget", json={"tokens": -1, "periode_dagen": 7, "actief": True}, headers=_ADMIN
    )
    assert r.status_code == 422  # ge=0 op het model


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
        "/v1/admin/budget", json={"tokens": 1, "periode_dagen": 1, "actief": True}
    )).status_code == 401
