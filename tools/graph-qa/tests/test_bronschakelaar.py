"""ADR-013 fase 1b: de bronnen van een beurt (*Bronnen en tools*).

De straat bepaalt wat er bestaat (`CONNECTOR_*`), de beurt wat er aanstaat (`ChatRequest.bronnen`). Eén regel,
`tools.toegestane_tools`, voor de schema's van het model, de MCP-server en `dispatch`.
"""
from __future__ import annotations

import asyncio
import json
import typing

import pytest
from pydantic import ValidationError

from agent import tools
from agent.agent import answer_stream
from agent.models import ChatRequest, Connector
from tests.fakes import FakeGraph, FakeLLM, make_settings, response, text_block

AAN = make_settings(connector_kamerstukken=True)
UIT = make_settings()


def test_connector_literal_is_het_register():
    assert set(typing.get_args(Connector)) == set(tools.CONNECTORS)


@pytest.mark.parametrize("settings,bronnen,verwacht", [
    (AAN, None, True),               # weggelaten: wat de straat aanbiedt
    (AAN, ["kamerstukken"], True),
    (AAN, [], False),                # leeg: alleen wetgeving
    (UIT, ["kamerstukken"], False),  # de beurt zet niets aan wat de straat niet aanbiedt
    (UIT, None, False),
])
def test_een_regel(settings, bronnen, verwacht):
    assert (tools.CONNECTOR_TOOLS <= tools.toegestane_tools(None, settings, bronnen)) is verwacht
    assert (tools.actieve_connectors(settings, bronnen) == {"kamerstukken"}) is verwacht


def test_chatrequest_kent_alleen_bekende_connectors():
    assert ChatRequest(question="x", bronnen=["kamerstukken"]).bronnen == ["kamerstukken"]
    assert ChatRequest(question="x").bronnen is None
    with pytest.raises(ValidationError):
        ChatRequest(question="x", bronnen=["confluence"])


def test_dispatch_weigert_een_uitgezette_bron_ook_in_code():
    d = json.loads(tools.dispatch("get_kamerstuk", None, {"id": "kst-1-1"}, AAN, bronnen=[]))
    assert (d["status"], d["reden"]) == ("error", "connector_uit")


def _tools_van_de_agent(settings, bronnen):
    llm = FakeLLM([response([text_block("Antwoord.")], "end_turn")])

    async def loop():
        async for _ in answer_stream("vraag", settings=settings.model_copy(update={"enable_planning": False}),
                                     llm=llm, graph=FakeGraph(result=""), bronnen=bronnen):
            pass

    asyncio.run(loop())
    return {t["name"] for t in llm.calls[0]["tools"]}


def test_het_model_krijgt_een_uitgezette_bron_niet_aangeboden():
    assert tools.CONNECTOR_TOOLS <= _tools_van_de_agent(AAN, ["kamerstukken"])
    assert not (tools.CONNECTOR_TOOLS & _tools_van_de_agent(AAN, []))
    # Uit is byte-gelijk aan vóór de connector: dezelfde toolset als een straat zonder connectors.
    assert _tools_van_de_agent(AAN, []) == _tools_van_de_agent(UIT, None)


class _NepApi:
    def __init__(self, aan=None, fout=False):
        self.aan, self.fout = aan or [], fout

    async def connectors(self):
        if self.fout:
            raise RuntimeError("api weg")
        return self.aan

    async def aclose(self):
        pass


@pytest.mark.parametrize("register,fout,bronnen,verwacht", [
    (["kamerstukken"], False, None, ["kamerstukken"]),
    ([], False, None, []),                 # de beheerder zette hem niet aan
    (["kamerstukken"], False, [], []),      # de beurt zet hem uit
    (["kamerstukken"], True, None, []),     # onleesbaar register: niets aan
])
def test_het_register_van_de_beheerder_begrenst(monkeypatch, register, fout, bronnen, verwacht):
    from agent import agent as agentmod
    from agent import wetsanalyse_api

    monkeypatch.setattr(wetsanalyse_api, "WetsanalyseApi", lambda *_a, **_k: _NepApi(register, fout))
    s = AAN.model_copy(update={"wetsanalyse_api_url": "https://api.test", "wetsanalyse_api_token": "t"})
    assert s.legt_zelf_vast
    assert asyncio.run(agentmod._bronnen_van_beurt(s, "u", bronnen)) == verwacht


def test_zonder_connector_in_de_straat_geen_registervraag(monkeypatch):
    from agent import agent as agentmod
    from agent import wetsanalyse_api

    monkeypatch.setattr(wetsanalyse_api, "WetsanalyseApi", lambda *_a, **_k: pytest.fail("geen api-aanroep"))
    s = UIT.model_copy(update={"wetsanalyse_api_url": "https://api.test", "wetsanalyse_api_token": "t"})
    assert asyncio.run(agentmod._bronnen_van_beurt(s, "u", None)) is None


def test_het_register_van_de_api_kent_dezelfde_connectors():
    """`api/app/connectors.py:BEKEND` en `tools.CONNECTORS` komen uit één beschrijving (`bronmodel.connectors`);
    de vorm van de afleiding toetst `tests/poort/test_connectorbeschrijving.py`."""
    from bronmodel.connectors import CONNECTORS

    assert set(tools.CONNECTORS) == set(CONNECTORS)
    assert all(tools.CONNECTORS[n] == c.tools for n, c in CONNECTORS.items())
