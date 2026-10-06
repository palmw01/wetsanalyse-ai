"""De supervisor in een lopend gesprek: eerst lezen waar een vervolgvraag over gaat, dan kiezen.

Zonder dit zag de supervisor alleen de kale vraag. "Waarom?" na een annotatie werd een afwijzing of
een plan zonder onderwerp, en "welke zijn er nog meer?" na een vraag over rechtssubjecten was geen
leesvraag – het woord "annotatie" stond er niet in.
"""
from __future__ import annotations

import asyncio

from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block
from test_bronnode_keten import ReadApi, snapshot

from agent.agent import answer_stream
from agent.berichten import eerdere_beurten


def _run(gen):
    async def collect():
        return [ev async for ev in gen]
    return asyncio.run(collect())


def test_eerdere_beurten_zonder_toolruis():
    messages = [
        {"role": "user", "content": "Wat regelt artikel 9?"},
        {"role": "assistant", "content": [{"type": "text", "text": "Ik zoek."},
                                          {"type": "tool_use", "id": "t", "name": "get_artikel", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t", "content": "x" * 5000}]},
        {"role": "assistant", "content": [{"type": "text", "text": "Artikel 9 regelt de invorderbaarheid."}]},
        {"role": "user", "content": "Let op: onderbouw dit."},
        {"role": "user", "content": "En lid 2?"},
    ]
    assert eerdere_beurten(messages, "En lid 2?") == [("Wat regelt artikel 9?", "Artikel 9 regelt de invorderbaarheid.")]
    assert eerdere_beurten(messages[:1], "Wat regelt artikel 9?") == []


def _eerste_beurt(settings, gid):
    llm = FakeLLM([
        response([text_block("WORKERS: antwoord\nSPECIALIST: duiding\nPLAN: art 9")], "end_turn"),
        response([tool_block("t1", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": "9"})], "tool_use"),
        response([text_block("Artikel 9 regelt wanneer een aanslag invorderbaar is.")], "end_turn"),
    ])
    _run(answer_stream("Wat regelt artikel 9 van de Invorderingswet 1990?", gid, settings=settings, llm=llm,
                       graph=FakeGraph(result='?nummer\t?tekst\n"9"\t"tekst"')))
    supervisor = str(llm.calls[0]["system"])
    assert "VERVOLGVRAAG" not in supervisor, "de eerste vraag van een gesprek heeft niets te herschrijven"


def test_vervolgvraag_wordt_met_het_gesprek_gelezen_en_herschreven(tmp_path):
    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"))
    _eerste_beurt(settings, "g-vervolg")
    llm = FakeLLM([
        response([text_block("VRAAG: Wat regelt artikel 9 lid 2 van de Invorderingswet 1990?\n"
                             "WORKERS: antwoord\nSPECIALIST: duiding\nPLAN: haal lid 2 op")], "end_turn"),
        response([text_block("Lid 2 regelt een afwijkende termijn.")], "end_turn"),
    ])
    events = _run(answer_stream("En lid 2?", "g-vervolg", settings=settings, llm=llm, graph=FakeGraph(result="")))
    supervisor = str(llm.calls[0]["system"])
    assert "VERVOLGVRAAG" in supervisor
    assert "Jurist: Wat regelt artikel 9 van de Invorderingswet 1990?" in supervisor
    assert "Lex: Artikel 9 regelt wanneer een aanslag invorderbaar is." in supervisor
    # De specialist krijgt de herschreven vraag in zijn aanpak; de historie houdt de echte vraag.
    specialist = str(llm.calls[1]["system"])
    assert "zelfstandig geformuleerd: Wat regelt artikel 9 lid 2" in specialist
    assert llm.calls[1]["messages"][-1]["content"] == "En lid 2?"
    assert any("leest de vraag als" in e.get("message", "") for e in events if e["type"] == "status")


def test_een_herschreven_leesvraag_gaat_de_leesroute_in_met_het_klassefilter(tmp_path):
    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"))
    _eerste_beurt(settings, "g-lees")
    api = ReadApi(snapshot())
    llm = FakeLLM([
        response([text_block("VRAAG: Welke rechtssubjecten zijn er al gemarkeerd in andere annotaties?\n"
                             "WORKERS: antwoord\nSPECIALIST: algemeen\nPLAN: zoek")], "end_turn"),
        response([text_block("Er zijn geen treffers binnen dit filter.")], "end_turn"),
    ])
    events = _run(answer_stream("En welke zijn er nog meer bekend?", "g-lees", settings=settings, llm=llm,
                                graph=FakeGraph(), annotaties=api))
    assert api.calls and api.calls[0][0] == "zoeken"
    assert api.calls[0][1]["jas_klassen"] == ["Rechtssubject"]
    assert "bwb_id" not in api.calls[0][1], "het artikel van de vorige beurt is geen zoekbereik"
    assert any(e.get("message", "").startswith("Lex · raadpleegt bestaande annotaties")
               for e in events if e["type"] == "status")


def test_zonder_vraagregel_blijft_de_eigen_vraag_gelden(tmp_path):
    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"))
    _eerste_beurt(settings, "g-geen")
    llm = FakeLLM([
        response([text_block("WORKERS: antwoord\nSPECIALIST: duiding\nPLAN: leg uit")], "end_turn"),
        response([text_block("Omdat de wetgever rechtszekerheid wilde.")], "end_turn"),
    ])
    _run(answer_stream("Waarom?", "g-geen", settings=settings, llm=llm, graph=FakeGraph(result="")))
    assert "zelfstandig geformuleerd" not in str(llm.calls[1]["system"])
