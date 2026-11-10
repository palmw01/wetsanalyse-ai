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
#: De tools van de connector die AAN aanbiedt; de andere connectors staan in deze straat uit.
KST = tools.CONNECTORS["kamerstukken"]


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
    assert (KST <= tools.toegestane_tools(None, settings, bronnen)) is verwacht
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
    assert KST <= _tools_van_de_agent(AAN, ["kamerstukken"])
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


@pytest.mark.parametrize("register,fout,bronnen,verwacht,reden", [
    (["kamerstukken"], False, None, ["kamerstukken"], "aan"),
    ([], False, None, [], "beheerder"),                    # de beheerder zette hem niet aan
    (["kamerstukken"], False, [], [], "gesprek"),           # de beurt zet hem uit
    (["kamerstukken"], True, None, [], "register_onleesbaar"),  # onleesbaar register: niets aan
])
def test_het_register_van_de_beheerder_begrenst(monkeypatch, register, fout, bronnen, verwacht, reden):
    from agent import agent as agentmod
    from agent import wetsanalyse_api

    monkeypatch.setattr(wetsanalyse_api, "WetsanalyseApi", lambda *_a, **_k: _NepApi(register, fout))
    s = AAN.model_copy(update={"wetsanalyse_api_url": "https://api.test", "wetsanalyse_api_token": "t"})
    assert s.legt_zelf_vast
    actief, stand = asyncio.run(agentmod._bronnen_van_beurt(s, "u", bronnen))
    assert actief == verwacht
    assert stand["kamerstukken"]["reden"] == reden and stand["kamerstukken"]["aan"] is (reden == "aan")


def test_zonder_connector_in_de_straat_geen_registervraag(monkeypatch):
    from agent import agent as agentmod
    from agent import wetsanalyse_api

    monkeypatch.setattr(wetsanalyse_api, "WetsanalyseApi", lambda *_a, **_k: pytest.fail("geen api-aanroep"))
    s = UIT.model_copy(update={"wetsanalyse_api_url": "https://api.test", "wetsanalyse_api_token": "t"})
    actief, stand = asyncio.run(agentmod._bronnen_van_beurt(s, "u", None))
    assert actief is None and stand["kamerstukken"]["reden"] == "straat"


def test_het_register_van_de_api_kent_dezelfde_connectors():
    """`api/app/connectors.py:BEKEND` en `tools.CONNECTORS` komen uit één beschrijving (`bronmodel.connectors`);
    de vorm van de afleiding toetst `tests/poort/test_connectorbeschrijving.py`."""
    from bronmodel.connectors import CONNECTORS

    assert set(tools.CONNECTORS) == set(CONNECTORS)
    assert all(tools.CONNECTORS[n] == c.tools for n, c in CONNECTORS.items())


@pytest.mark.parametrize("settings,bronnen,herkomst,reden", [
    (UIT, ["kamerstukken"], "gesprek", "straat"),        # de straat gaat voor: niemand in de werkplek zet hem aan
    (AAN, [], "gesprek", "gesprek"),
    (AAN, [], "werkgebied", "werkgebied"),
    (AAN, [], None, "gesprek"),
    (AAN, None, "standaard", "aan"),
])
def test_de_reden_zegt_wie_hem_aanzet(settings, bronnen, herkomst, reden):
    from agent import bronstand

    s = bronstand.bepaal(settings, bronnen, herkomst)["kamerstukken"]
    assert s["reden"] == reden and s["label"] == "Kamerstukken"
    assert reden == "aan" or reden in bronstand.WIE_ZET_AAN


def test_de_beurt_meldt_haar_bronstand_en_de_meting_leest_hem(monkeypatch):
    """Het eerste event is de bronstand; `beurt_meting` noemt per connector de reden."""
    from agent import beurtmeting

    llm = FakeLLM([response([text_block("Geen antwoord.")], "end_turn")])
    s = AAN.model_copy(update={"enable_planning": False})

    async def loop():
        stroom = answer_stream("Wat zegt de MvT?", settings=s, llm=llm, graph=FakeGraph(result=""), bronnen=[],
                               bronnen_herkomst="werkgebied")
        return [e async for e in beurtmeting.gemeten(stroom, meter=None, run=None, gesprek_id="g1", model="m")]

    gelogd = []
    monkeypatch.setattr(beurtmeting.logger, "info", lambda msg, extra=None: gelogd.append(extra))
    events = asyncio.run(loop())
    # Een connector die de straat niet aanbiedt, staat erbij met de reden `straat`.
    assert events[0] == {"type": "bronstand", "bronnen": [
        {"naam": "kamerstukken", "label": "Kamerstukken", "aan": False, "reden": "werkgebied"},
        {"naam": "rechtspraak", "label": "Rechtspraak", "aan": False, "reden": "straat"}]}
    assert gelogd[-1]["bronnen"] == "kamerstukken:werkgebied,rechtspraak:straat"


def test_chatrequest_kent_de_herkomst():
    assert ChatRequest(question="x", bronnen=[], bronnen_herkomst="werkgebied").bronnen_herkomst == "werkgebied"
    with pytest.raises(ValidationError):
        ChatRequest(question="x", bronnen_herkomst="iemand")


def test_zonder_connector_in_de_straat_geen_bronstand_event():
    llm = FakeLLM([response([text_block("Antwoord.")], "end_turn")])

    async def loop():
        return [e async for e in answer_stream("vraag", settings=UIT.model_copy(update={"enable_planning": False}),
                                               llm=llm, graph=FakeGraph(result=""))]

    assert not [e for e in asyncio.run(loop()) if e["type"] == "bronstand"]
