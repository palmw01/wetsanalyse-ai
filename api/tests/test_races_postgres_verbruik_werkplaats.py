"""Races op PostgreSQL voor het verbruik en de werkplaats (Lex Bench §20.5 stap 3, risico R07; testplan api V4). Dezelfde
beurt twee keer tegelijk boeken telt één keer; twee nieuwe versies op dezelfde voorganger: één wint, de ander 409. De
bestaande client-fixtures draaien ongewijzigd, op een eigen schema (`conftest.op_postgres`)."""
from __future__ import annotations

import asyncio

import pytest

from conftest import op_postgres, vereis_postgres
from test_verbruik import A, _boek, _journaal
from test_verbruik import client as verbruik_client  # noqa: F401
from test_werkplaats import B, PROFIEL, _maak
from test_werkplaats import client as werkplaats_client  # noqa: F401

pytestmark = [vereis_postgres(), pytest.mark.risico("R07")]


@pytest.fixture(autouse=True)
async def database(monkeypatch):
    async for _ in op_postgres("races_vw", monkeypatch):
        yield


async def test_dezelfde_beurt_tegelijk_boeken_telt_een_keer(verbruik_client):
    a, b = await asyncio.gather(_boek(verbruik_client, invoer=100, uitvoer=0, run_id="run-1"),
                                _boek(verbruik_client, invoer=100, uitvoer=0, run_id="run-1"))
    assert sorted([a.status_code, b.status_code]) == [201, 201], (a.text, b.text)
    assert sorted([a.json()["geboekt"], b.json()["geboekt"]]) == [False, True]
    assert len([r for r in await _journaal() if "run-1" in r]) == 1
    assert (await verbruik_client.get("/v1/verbruik", headers=A)).json()["gebruikt"] == 100


async def test_twee_nieuwe_versies_op_dezelfde_voorganger_een_409(werkplaats_client):
    o = (await _maak(werkplaats_client)).json()
    pad = f"/v1/werkplaats/onderdelen/{o['id']}/versies"
    a, b = await asyncio.gather(
        werkplaats_client.post(pad, json={"bestanden": {"jrm-scenario.md": PROFIEL + "A.\n"}, "na_versie": 1}, headers=B),
        werkplaats_client.post(pad, json={"bestanden": {"jrm-scenario.md": PROFIEL + "B.\n"}, "na_versie": 1}, headers=B))
    assert sorted([a.status_code, b.status_code]) == [200, 409], (a.text, b.text)
    stand = (await werkplaats_client.get(f"/v1/werkplaats/onderdelen/{o['id']}", headers=B)).json()
    assert stand["versies"] == 2
