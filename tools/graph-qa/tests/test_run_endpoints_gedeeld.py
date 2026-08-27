"""Dezelfde HTTP-endpoints, maar met de gedeelde store eronder.

`test_run_endpoints.py` toetst de run-machinerie tegen de geheugenvariant. Deze suite draait de
kerngevallen nog eens tegen PostgreSQL, want dat is wat er op Azure onder zit. Een store die het
protocol nakomt maar zich via de HTTP-laag nét anders gedraagt — een 404 waar een 409 hoorde, een
SSE-stream die niet sluit — is precies het soort verschil dat je in productie pas merkt.

Gemarkeerd als `integration`; slaat zichzelf over zonder RUNSTORE_TEST_DSN. Zie
`tests/test_runstore_postgres.py` voor het opstartcommando van een testdatabase.
"""

from __future__ import annotations

import asyncio
import json
import os

import pytest
from fastapi.testclient import TestClient

from api import main

DSN = os.environ.get("RUNSTORE_TEST_DSN", "")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DSN, reason="RUNSTORE_TEST_DSN niet gezet"),
]


def _nep_stroom(_request, _gebruiker=""):
    async def maak(_run):
        for i in range(6):
            await asyncio.sleep(0.05)
            yield {"type": "token", "content": f"deel{i} "}
        yield {"type": "done"}
    return maak


@pytest.fixture
def client(monkeypatch):
    from agent.runstore.postgres import PostgresStore

    monkeypatch.setattr(main.settings, "graphdb_token", "test", raising=False)
    monkeypatch.setattr(main.settings, "graphdb_mcp_url", "https://graaf.test/mcp", raising=False)
    monkeypatch.setattr(main, "_stroom_voor", _nep_stroom)
    monkeypatch.setattr(main, "runs", PostgresStore(DSN))
    # De lifespan roept setup() aan; daarna leegmaken zodat tests elkaar niet zien.
    with TestClient(main.app) as c:
        async def leeg():
            async with main.runs.pool.connection() as conn:
                await conn.execute("TRUNCATE agent_run_events, agent_runs")
        c.portal.call(leeg)
        yield c


def _tokens(response) -> str:
    tekst = ""
    for regel in response.iter_lines():
        if regel.startswith("data:"):
            event = json.loads(regel[5:].strip())
            if event["type"] == "token":
                tekst += event["content"]
    return tekst


def _start(client, gesprek="g1", gebruiker="u1"):
    return client.post("/v1/runs", json={"question": "v", "conversation_id": gesprek},
                       headers={"X-User-Id": gebruiker})


def test_een_beurt_loopt_en_is_volledig_terug_te_lezen(client):
    r = _start(client)
    assert r.status_code == 201
    run_id = r.json()["run_id"]
    with client.stream("GET", f"/v1/runs/{run_id}/events?vanaf=0",
                       headers={"X-User-Id": "u1"}) as stroom:
        tekst = _tokens(stroom)
    assert tekst == "deel0 deel1 deel2 deel3 deel4 deel5 "


def test_opnieuw_aanhaken_levert_precies_het_gemiste(client):
    run_id = _start(client).json()["run_id"]
    with client.stream("GET", f"/v1/runs/{run_id}/events?vanaf=3",
                       headers={"X-User-Id": "u1"}) as stroom:
        tekst = _tokens(stroom)
    assert tekst == "deel3 deel4 deel5 "


def test_een_tweede_run_op_hetzelfde_gesprek_geeft_409(client):
    eerste = _start(client).json()["run_id"]
    botsing = _start(client)
    assert botsing.status_code == 409
    assert botsing.json()["detail"] == {"reden": "run_loopt_al", "run_id": eerste}


def test_de_run_van_een_ander_bestaat_niet_voor_je(client):
    run_id = _start(client, gebruiker="u1").json()["run_id"]
    r = client.get(f"/v1/runs/{run_id}/events", headers={"X-User-Id": "u2"})
    assert r.status_code == 404


def test_de_lopende_run_van_een_gesprek_is_op_te_vragen(client):
    run_id = _start(client).json()["run_id"]
    r = client.get("/v1/conversations/g1/run", headers={"X-User-Id": "u1"})
    assert r.status_code == 200 and r.json()["run_id"] == run_id


def test_stoppen_beeindigt_de_beurt(client):
    run_id = _start(client).json()["run_id"]
    r = client.post(f"/v1/runs/{run_id}/cancel", headers={"X-User-Id": "u1"})
    assert r.status_code == 202
    # De stream sluit; de status is daarna niet meer 'loopt'.
    with client.stream("GET", f"/v1/runs/{run_id}/events?vanaf=0",
                       headers={"X-User-Id": "u1"}) as stroom:
        _tokens(stroom)
    stand = client.get("/v1/conversations/g1/run", headers={"X-User-Id": "u1"}).json()
    assert stand is None or stand["status"] != "loopt"
