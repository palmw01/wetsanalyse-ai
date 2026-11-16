"""Na het rapport van een subagent leest de centrale agent de wettekst gericht na, en schrapt de correctie wat het rapport
niet draagt (E2E Rekeningafspraken, 16 nov 2026, B-3).

Het geval: de wetsgeschiedenis van een lid. De subagent las de Kamerstukken, en zijn rapport zei terecht dat het lid zelf
niet werd toegelicht. De centrale agent schreef er een eigen duiding van de bepaling bij die nergens stond. Hij kondigde aan
de bepaling te lezen, maar de code weigerde elke tool na een rapport (`na_subagent`), en de correctieronde zei "haal het op
of laat het weg", wat niet kon; hij herformuleerde de zin.

De regel is generiek: na elke subagent mag de centrale agent de wettekst van hoogstens `MAX_NALEZEN` bepalingen zelf lezen
(`NALEES_TOOLS`), want een rapport over stukken naast de wet draagt die tekst niet. Het herlezen van de stukken zelf blijft
geweigerd. En na een subagent vraagt de correctie om te schrappen in plaats van te herformuleren.
"""
from __future__ import annotations

import asyncio
import json

from agent import subagent as sub
from agent.nodes import antwoord as antwoordnodes
from agent.nodes.antwoord import MAX_NALEZEN, NA_RAPPORT, NALEZEN_PLAFOND, na_subagent
from agent import wetsanalyse_api
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block
from test_subagent import OPDRACHT, Api, _kinderen

BWB = "BWBR0004770"
KAMERSTUK = ("get_kamerstuk", json.dumps({"status": "ok", "volledig": True, "aantal": 1,
                                         "stuk": {"id": "kst-34002-3", "label": "Kamerstukken 34002, nr. 3"},
                                         "resultaten": [{"nr": 1, "tekst": "De wijziging laat het vierde lid vervallen."}]}))
KIND = {"rapport": {"status": "klaar"}, "answer": "Het vierde lid zelf wordt in de memorie niet toegelicht.",
        "source_trace": [KAMERSTUK]}


def _instellingen():
    return make_settings(wetsanalyse_api_url="http://api.test", wetsanalyse_api_token="t",
                         connector_kamerstukken=True)


class _Register:
    """Het connectorregister van de beheerder met Kamerstukken aan: zonder dat staat de connector uit
    (`register_onleesbaar`) en biedt de beurt `get_kamerstuk` niet aan, dus kan een model hem niet aanroepen."""

    def __init__(self, *_a, **_k):
        pass

    async def connectors(self):
        return ["kamerstukken"]

    async def aclose(self):
        pass


def _beurt(llm, graph, monkeypatch):
    monkeypatch.setattr(sub, "WetsanalyseApi", lambda *_a, **_k: Api())
    monkeypatch.setattr(wetsanalyse_api, "WetsanalyseApi", _Register)
    kinderen, gestart, _ = _kinderen(KIND)
    from agent.agent import answer_stream

    async def alles():
        return [e async for e in answer_stream("Wat zeggen de Kamerstukken over artikel 7a, vierde lid, Invorderingswet "
                                               "1990?", "hoofd", settings=_instellingen(), llm=llm, graph=graph,
                                               user_id="jurist", run_id="ouder-run", kinderen=kinderen)]
    return asyncio.run(alles()), gestart


def _toolresultaten(llm, ronde: int) -> dict[str, str]:
    """De toolresultaten die het model in deze ronde (vanaf 0) terugkreeg, per tool_use_id."""
    berichten = llm.calls[ronde]["messages"]
    return {b["tool_use_id"]: b["content"] for m in berichten if m["role"] == "user" and isinstance(m["content"], list)
            for b in m["content"] if isinstance(b, dict) and b.get("type") == "tool_result"}


def test_na_een_rapport_leest_de_centrale_agent_de_bepaling_na_en_niet_de_stukken(monkeypatch):
    opdracht = {"profiel": "wetsgeschiedenis_lezen", **OPDRACHT.model_dump()}
    llm = FakeLLM([
        response([tool_block("s1", "subagent", {"opdrachten": [opdracht]})], "tool_use"),
        # Na het rapport: de bepaling zelf, twee andere bepalingen, en nog eens het Kamerstuk.
        response([tool_block("n1", "get_lid", {"bwb_id": BWB, "artikel": "7a", "lid": "4"}),
                  tool_block("n2", "get_artikel", {"bwb_id": BWB, "artikel": "7a"}),
                  tool_block("n3", "get_artikel", {"bwb_id": BWB, "artikel": "7b"}),
                  tool_block("n4", "get_kamerstuk", {"id": "kst-34002-3"})], "tool_use"),
        response([text_block("Het vierde lid wordt in de memorie niet toegelicht.")], "end_turn"),
    ])
    graph = FakeGraph(result="")
    events, gestart = _beurt(llm, graph, monkeypatch)

    assert gestart, "de subagent startte"
    uit = _toolresultaten(llm, 2)
    assert uit["n4"] == NA_RAPPORT, "de stukken leest hij niet zelf opnieuw"
    assert uit["n3"] == NALEZEN_PLAFOND, f"hoogstens {MAX_NALEZEN} bepalingen"
    assert NA_RAPPORT not in (uit["n1"], uit["n2"]) and NALEZEN_PLAFOND not in (uit["n1"], uit["n2"])
    geweigerd = {e["call_id"]: e["foutcode"] for e in events
                 if e.get("type") == "tool_execution" and e.get("phase") == "end" and e.get("status") == "geweigerd"}
    assert geweigerd == {"n3": "nalezen_plafond", "n4": "na_subagent"}
    assert graph.queries, "de wettekst kwam uit de graaf"


def test_het_rapport_zegt_vooraf_dat_de_wettekst_na_te_lezen_is():
    for uitkomst in ("klaar", "niet_gelukt"):
        assert "get_lid of get_artikel" in sub.als_toolresultaat("wetsgeschiedenis_lezen", uitkomst, "x")
    # Alleen na een subagent die het werk deed: een specialist of een kind zelf heeft geen grens.
    assert na_subagent({"subagenten": [{"uitkomst": "klaar"}]}, "get_lid") == ""
    assert na_subagent({"subagenten": [{"uitkomst": "klaar"}]}, "search_wetgeving") == NA_RAPPORT
    assert antwoordnodes.nalezen_over({"opdracht": {"doel": "x"}, "subagenten": [{"uitkomst": "klaar"}]},
                                      [{"name": "get_lid"}] * 5) == set()
    assert antwoordnodes.nalezen_over({"subagenten": [{"uitkomst": "gestopt"}]}, [{"name": "get_lid"}] * 5) == set()


def test_na_een_subagent_schrapt_de_correctie_in_plaats_van_te_herformuleren(monkeypatch):
    """Een duiding van een stuk die de passages niet dragen (`zonder_steun`): de correctie vraagt te schrappen."""
    monkeypatch.setattr(antwoordnodes, "get_stream_writer", lambda: (lambda _e: None))
    bewering = "duiding van kst-34002-3 die de passages van dat stuk niet dragen"
    na_rapport = antwoordnodes.correct_node(None, {"beweringen": [bewering], "subagenten": [{"uitkomst": "klaar"}],
                                                   "rapport_steun": {"kst-34002-3": "De wijziging laat het lid vervallen."}})
    tekst = na_rapport["messages"][0]["content"]
    assert "Schrap" in tekst and "herformuleer ze niet" in tekst and "Haal het op met de tools" not in tekst
    zonder = antwoordnodes.correct_node(None, {"beweringen": ["het getal 412"]})
    assert "Haal het op met de tools" in zonder["messages"][0]["content"], "zonder subagent: de gewone correctie"


def test_de_correctie_na_een_subagent_door_de_hele_graaf(monkeypatch):
    """Het antwoord duidt het gelezen stuk met woorden die het niet draagt: de correctieronde vraagt te schrappen, en de
    beurt eindigt met het geschrapte antwoord."""
    opdracht = {"profiel": "wetsgeschiedenis_lezen", **OPDRACHT.model_dump()}
    llm = FakeLLM([
        response([tool_block("s1", "subagent", {"opdrachten": [opdracht]})], "tool_use"),
        response([text_block("Volgens kst-34002-3 werkt betaling aan een aangewezen derde bevrijdend voor de "
                             "belastingschuldige en ook voor iedere aansprakelijke derde partij.")], "end_turn"),
        response([text_block("Volgens kst-34002-3 laat de wijziging het vierde lid vervallen.")], "end_turn"),
    ])
    events, _ = _beurt(llm, FakeGraph(result=""), monkeypatch)
    assert len(llm.calls) == 3, "één correctieronde"
    correctie = llm.calls[2]["messages"][-1]["content"]
    correctie = correctie if isinstance(correctie, str) else json.dumps(correctie, ensure_ascii=False)
    assert "Schrap" in correctie and "herformuleer" in correctie
    assert any(e.get("type") == "token" and "vierde lid vervallen" in e.get("content", "") for e in events)
