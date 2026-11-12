"""`Bericht.contextopbouw` en de leesroute voor de boom (plan contextweergave, stap 3).

Graph-qa rekent de contextopbouw uit; de api bewaart haar op het bericht en geeft bij een gesprek die van zijn
deelgesprekken terug. Niets is dubbel opgeslagen: de boom ontstaat bij het lezen.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

BASIS = "/v1/gesprekken"
A = {"X-User-Id": "gebruiker-a"}
B = {"X-User-Id": "gebruiker-b"}


def _opbouw(run_id: str = "run-1", ouder: str = "", **extra) -> dict:
    """De vorm van versie 1, zoals graph-qa haar levert (`agent/contextopbouw.py`)."""
    return {
        "versie": 1, "run_id": run_id, "ouder_run_id": ouder, "profiel_id": "", "profiel_versie": "",
        "agenten": [{
            "rol": "antwoord", "model": "m", "venster": 1_000_000,
            "laatste": {"delen": [{"categorie": "systeem", "omvang": 4000}, {"categorie": "beurt", "omvang": 1000}],
                        "totaal": 5000, "voorvoegsel": {"omvang": 4000, "exact": True},
                        "cache": {"lees": 4000, "schrijf": 900, "nieuw": 100}},
            "begin": {"totaal": 4500, "cache": {"lees": 0, "schrijf": 4400, "nieuw": 100},
                      "tools_hash": "abc", "system_hash": "def"},
            "historiegrens": 11000,
            "venster_beurten": {"in_venster": 2, "gekrompen": 0, "weggevallen": 0},
        }],
        "verbruik": [{"rol": "antwoord", "model": "m", "aanroepen": 2, "invoer": 200, "cache_lees": 4000,
                      "cache_schrijf": 5300, "uitvoer": 300, "duur": 1200}],
        "som": {"invoer": 200, "cache_lees": 4000, "cache_schrijf": 5300, "uitvoer": 300},
        "aanroepen": [{"rol": "antwoord", "totaal": 4500, "cache_lees": 0, "cache_schrijf": 4400, "invoer": 100,
                       "uitvoer": 100, "ms": 600, "tools_hash": "abc", "system_hash": "def"}],
        **extra,
    }


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")

    from app import db, ratelimit
    from app.config import get_settings
    from app.deps import get_gesprek_store
    from conftest import maak_testgebruikers

    get_settings.cache_clear()
    get_gesprek_store.cache_clear()
    ratelimit.reset()
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    await maak_testgebruikers("gebruiker-a", "gebruiker-b")

    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    get_settings.cache_clear()
    get_gesprek_store.cache_clear()
    await db.dispose_engine()


async def _gesprek(gid: str, user: str = "gebruiker-a", ouder: str = "", titel: str = "") -> str:
    from app.gesprek_contracts import Gesprek
    from app.gesprek_store import GesprekStore
    await GesprekStore().maak_gesprek(Gesprek(id=gid, user_id=user, titel=titel or gid, ouder_id=ouder,
                                              werkgebied_id="wg-1" if ouder else ""))
    return gid


async def _bericht(client, gid: str, headers=A, **velden) -> dict:
    r = await client.post(f"{BASIS}/{gid}/berichten", json={"rol": "assistant", "tekst": "antwoord", **velden},
                          headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_de_contextopbouw_overleeft_het_heropenen(client):
    gid = await _gesprek("g1")
    bewaard = await _bericht(client, gid, run_id="run-1", contextopbouw=_opbouw())
    assert bewaard["contextopbouw"] == _opbouw()
    doc = (await client.get(f"{BASIS}/{gid}", headers=A)).json()
    assert doc["berichten"][0]["contextopbouw"] == _opbouw()


async def test_een_bericht_zonder_meting_heeft_geen_contextopbouw(client):
    gid = await _gesprek("g1")
    await _bericht(client, gid, run_id="run-1")
    assert (await client.get(f"{BASIS}/{gid}", headers=A)).json()["berichten"][0]["contextopbouw"] is None


async def test_geen_veld_heet_token(client):
    """De logredactie laat een veld met de naam `token` weg; het contract gebruikt die naam dus nergens."""
    from app.gesprek_contracts import BerichtContext, Contextopbouw, ContextopbouwBoom, KindContext
    for model in (Contextopbouw, BerichtContext, KindContext, ContextopbouwBoom):
        assert not [v for v in model.model_fields if "token" in v.lower()]


async def test_een_onbekend_veld_valt_weg_en_een_te_lange_lijst_wordt_geweigerd(client):
    gid = await _gesprek("g1")
    bewaard = await _bericht(client, gid, run_id="run-1", contextopbouw=_opbouw(nieuw_veld=1))
    assert "nieuw_veld" not in bewaard["contextopbouw"]
    from app.gesprek_contracts import MAX_CONTEXT_AANROEPEN
    te_veel = _opbouw(aanroepen=[{"rol": "antwoord"}] * (MAX_CONTEXT_AANROEPEN + 1))
    r = await client.post(f"{BASIS}/{gid}/berichten", json={"rol": "assistant", "run_id": "run-2",
                                                             "contextopbouw": te_veel}, headers=A)
    assert r.status_code == 422


async def test_een_veraalde_contextopbouw_breekt_het_gesprek_niet(client):
    """Zoals elk optioneel veld: past de bewaarde vorm niet meer bij het contract, dan valt alleen dat veld weg."""
    from sqlalchemy import update
    from app import db
    gid = await _gesprek("g1")
    await _bericht(client, gid, run_id="run-1", contextopbouw=_opbouw())
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.gesprek_berichten).values(
            inhoud={"tekst": "antwoord", "run_id": "run-1", "contextopbouw": {"versie": "geen getal"}}))
    doc = await client.get(f"{BASIS}/{gid}", headers=A)
    assert doc.status_code == 200 and doc.json()["berichten"][0]["contextopbouw"] is None
    # En in de boom van een ouder evenmin: het kind staat er, zonder meting.
    await _gesprek("ouder")
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.gesprekken).where(db.gesprekken.c.id == gid).values(ouder_id="ouder"))
    boom = (await client.get(f"{BASIS}/ouder/contextopbouw", headers=A)).json()
    assert boom["kinderen"] == [{"gesprek_id": gid, "titel": "g1", "updated": boom["kinderen"][0]["updated"],
                                 "berichten": []}]


async def test_de_boom_geeft_per_deelgesprek_de_contextopbouw_van_zijn_beurten(client):
    await _gesprek("ouder")
    await _gesprek("kind-1", ouder="ouder", titel="Deelvraag 1")
    await _gesprek("kind-2", ouder="ouder", titel="Deelvraag 2")
    await _gesprek("kind-3", ouder="ouder", titel="Loopt nog")
    await _gesprek("los")
    # De ouder zelf en een los gesprek horen niet in de boom: hun contextopbouw staat op hun eigen berichten.
    await _bericht(client, "ouder", run_id="r0", contextopbouw=_opbouw("r0"))
    await _bericht(client, "los", run_id="rx", contextopbouw=_opbouw("rx"))
    await _bericht(client, "kind-1", run_id="r1", contextopbouw=_opbouw("r1", ouder="r0"))
    await _bericht(client, "kind-1", run_id="r1b", contextopbouw=_opbouw("r1b", ouder="r0"))
    await _bericht(client, "kind-2", run_id="r2")                       # een beurt zonder model: geen meting
    await client.post(f"{BASIS}/kind-2/berichten", json={"rol": "user", "tekst": "vraag"}, headers=A)

    r = await client.get(f"{BASIS}/ouder/contextopbouw", headers=A)
    assert r.status_code == 200
    boom = r.json()
    assert boom["gesprek_id"] == "ouder"
    assert [(k["gesprek_id"], k["titel"], [b["run_id"] for b in k["berichten"]]) for k in boom["kinderen"]] == [
        ("kind-1", "Deelvraag 1", ["r1", "r1b"]), ("kind-2", "Deelvraag 2", []), ("kind-3", "Loopt nog", [])]
    eerste = boom["kinderen"][0]["berichten"][0]
    assert eerste["contextopbouw"] == _opbouw("r1", ouder="r0") and eerste["bericht_id"] and eerste["created"]
    # Alleen de contextopbouw, niet de rest van het bericht.
    assert set(eerste) == {"bericht_id", "run_id", "created", "contextopbouw"}


async def test_een_gesprek_zonder_deelgesprekken_heeft_een_lege_boom(client):
    await _gesprek("g1")
    assert (await client.get(f"{BASIS}/g1/contextopbouw", headers=A)).json() == {"gesprek_id": "g1", "kinderen": []}


async def test_de_boom_is_alleen_voor_de_eigen_gesprekken(client):
    await _gesprek("ouder")
    await _gesprek("van-b", user="gebruiker-b")
    assert (await client.get(f"{BASIS}/ouder/contextopbouw", headers=B)).status_code == 404
    assert (await client.get(f"{BASIS}/bestaat-niet/contextopbouw", headers=A)).status_code == 404
    assert (await client.get(f"{BASIS}/ouder/contextopbouw")).status_code == 401
    # Een deelgesprek van een ander onder het eigen gesprek telt niet mee (dat kan de api niet aanmaken, maar de
    # leesroute vertrouwt daar niet op).
    await _gesprek("vreemd-kind", user="gebruiker-b", ouder="ouder")
    assert (await client.get(f"{BASIS}/ouder/contextopbouw", headers=A)).json()["kinderen"] == []
