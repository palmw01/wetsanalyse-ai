"""Eén ingang voor elke run (ADR-012): `start_beurt` is wat `POST /v1/runs` en de regisseur gebruiken, en stoppen van
een regierun stopt zijn kinderen."""
from __future__ import annotations

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

import api.main as main
from agent.models import ChatRequest
from agent.runstore.geheugen import GeheugenStore


def _tot_stop(_request, _gebruiker=""):
    async def maak(run):
        yield {"type": "status", "content": "bezig"}
        for _ in range(200):
            if run.stop_gevraagd:
                return
            await asyncio.sleep(0.02)
    return maak


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main.settings, "graphdb_token", "test", raising=False)
    monkeypatch.setattr(main.settings, "graphdb_mcp_url", "https://graaf.test/mcp", raising=False)
    monkeypatch.setattr(main, "_stroom_voor", _tot_stop)
    monkeypatch.setattr(main, "runs", GeheugenStore())
    with TestClient(main.app) as c:
        yield c


def _status(client, gesprek: str, gebruiker: str, *, binnen_s: float = 5.0) -> str:
    eind, status = time.monotonic() + binnen_s, ""
    while time.monotonic() < eind:
        status = (client.get(f"/v1/conversations/{gesprek}/run", headers={"X-User-Id": gebruiker}).json()
                  or {}).get("status", "")
        if status and status != "loopt":
            return status
        time.sleep(0.02)
    return status


def test_stoppen_van_de_regierun_stopt_zijn_kinderen(client):
    kop = {"X-User-Id": "jurist-a"}
    ouder = client.post("/v1/runs", json={"question": "regie", "conversation_id": "regie"}, headers=kop).json()

    async def kind_starten():
        return await main.start_beurt(ChatRequest(question="kind", conversation_id="kind"), "jurist-a",
                                      ouder_run_id=ouder["run_id"])
    kind = client.portal.call(kind_starten)
    los = client.post("/v1/runs", json={"question": "los", "conversation_id": "los"}, headers=kop).json()
    assert kind.ouder_run_id == ouder["run_id"]
    assert {r["conversation_id"]: r["ouder_run_id"] for r in client.get("/v1/runs?actief=true", headers=kop).json()} \
        == {"regie": "", "kind": ouder["run_id"], "los": ""}

    assert client.post(f"/v1/runs/{ouder['run_id']}/cancel", headers=kop).status_code == 202
    assert _status(client, "regie", "jurist-a") == "gestopt"
    assert _status(client, "kind", "jurist-a") == "gestopt"
    # Een run zonder deze ouder loopt door.
    assert (client.get("/v1/conversations/los/run", headers=kop).json() or {}).get("status") == "loopt"
    client.post(f"/v1/runs/{los['run_id']}/cancel", headers=kop)


def test_start_beurt_houdt_het_slot_per_gesprek(client):
    from agent.runstore import RunBestaatAl
    client.post("/v1/runs", json={"question": "een", "conversation_id": "g"}, headers={"X-User-Id": "a"})

    async def tweede():
        await main.start_beurt(ChatRequest(question="twee", conversation_id="g"), "a", ouder_run_id="x")
    with pytest.raises(RunBestaatAl):
        client.portal.call(tweede)


def test_start_beurt_toetst_het_budget_alleen_op_verzoek(client, monkeypatch):
    gevraagd: list[str] = []

    async def poort(gebruiker):
        gevraagd.append(gebruiker)
    monkeypatch.setattr(main, "controleer_budget", poort)

    async def starten(budget):
        return await main.start_beurt(ChatRequest(question="q", conversation_id=f"b{budget}"), "a", budget=budget)
    for budget in (False, True):
        run = client.portal.call(starten, budget)
        client.post(f"/v1/runs/{run.run_id}/cancel", headers={"X-User-Id": "a"})
    assert gevraagd == ["a"]


def test_een_gesprek_verwijderen_stopt_ook_de_kinderen(client, monkeypatch):
    async def niets(*_a, **_k):
        return None
    monkeypatch.setattr(main, "delete_conversation", niets)
    kop = {"X-User-Id": "a"}
    ouder = client.post("/v1/runs", json={"question": "regie", "conversation_id": "regie"}, headers=kop).json()

    async def kind_starten():
        return await main.start_beurt(ChatRequest(question="kind", conversation_id="kind"), "a",
                                      ouder_run_id=ouder["run_id"])
    client.portal.call(kind_starten)
    assert client.delete("/v1/conversations/regie", headers=kop).status_code in (200, 204)
    assert _status(client, "kind", "a") == "gestopt"
