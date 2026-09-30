"""Eén artikel per annotatievraag – en dat hangt niet van het model af.

Drie lagen: de vraag zelf (deterministisch, vóór elke ophaalcall), de ophaal-JSON `meerdere`, en een
vangnet op de fetch-calls. Zonder die lagen wint bij "artikel 8 en 9" stil de laatste call en verdwijnt
artikel 8 zonder melding.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from agent.aanwijzing import lees_aanwijzing, melding_meerdere
from agent.agent import answer_stream
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block

IW = "BWBR0004770"


@pytest.mark.parametrize("vraag, artikelen", [
    ("annoteer artikel 8 en 9", ("8", "9")),
    ("annoteer artikel 8 en 9 van de Invorderingswet 1990", ("8", "9")),
    ("annoteer de artikelen 8, 9 en 10 IW", ("8", "9", "10")),
    ("annoteer artikelen 8 t/m 10", ("8", "9", "10")),
    ("annoteer art. 8 lid 2 en art. 9", ("8", "9")),
    ("annoteer artikel 8 lid 2 en artikel 9 lid 1", ("8", "9")),
    ("annoteer artt. 8-9 IW 1990", ("8", "9")),
    ("annoteer artikel 3:40 en 3:41 Awb", ("3:40", "3:41")),
    ("annoteer artikel 22bis en 23 Leidraad", ("22bis", "23")),
])
def test_meerdere_artikelen_worden_herkend(vraag, artikelen):
    a = lees_aanwijzing(vraag)
    assert a.artikelen == artikelen and a.meerdere_artikelen
    assert a.leden == (), "leden zonder één artikel betekenen niets"


@pytest.mark.parametrize("vraag, artikel, leden", [
    ("annoteer artikel 9 IW 1990", "9", ()),
    ("annoteer artikel 9 van de Invorderingswet 1990", "9", ()),
    ("annoteer artikel 9 lid 1", "9", ("1",)),
    ("annoteer artikel 9 lid 1 en 3", "9", ("1", "3")),
    ("annoteer artikel 9 lid 1 en lid 3", "9", ("1", "3")),
    ("annoteer artikel 9, leden 2 t/m 4", "9", ("2", "3", "4")),
    ("annoteer de leden 1 en 3 van artikel 9", "9", ("1", "3")),
    ("annoteer artikel 9, eerste en derde lid", "9", ("1", "3")),
    ("annoteer het tweede lid van artikel 9", "9", ("2",)),
    ("annoteer artikel 9.1 en 9.5 van de Leidraad Invordering 2008", "9", ("1", "5")),
    ("annoteer 9.1 t/m 9.3 leidraad, artikel 9.1 tot en met 9.3", "9", ("1", "2", "3")),
    ("annoteer artikel 9 lid 1 onderdeel a en b", "9", ("1",)),
    ("annoteer artikel 3:40 Awb", "3:40", ()),
    ("annoteer art. 22bis lid 2", "22bis", ("2",)),
    ("annoteer Artikel 9 en leg de termijnen uit", "9", ()),
])
def test_een_artikel_blijft_een_artikel(vraag, artikel, leden):
    a = lees_aanwijzing(vraag)
    assert a.artikelen == (artikel,) and not a.meerdere_artikelen
    assert a.leden == leden


def test_geen_artikel_is_geen_afwijzing():
    """Een onderwerpvraag noemt geen artikel; die gaat naar de kandidatenroute."""
    assert lees_aanwijzing("annoteer alles over uitstel van betaling").artikelen == ()


def test_melding_noemt_de_artikelen_en_wat_wel_kan():
    tekst = melding_meerdere(("8", "9", "10"))
    assert "artikel 8, artikel 9 en artikel 10" in tekst and "opnieuw" in tekst


def _run(gen):
    async def collect():
        return [e async for e in gen]
    return asyncio.run(collect())


def _tekst(events):
    return "".join(e.get("content", "") for e in events if e["type"] == "token")


def test_vraag_met_twee_artikelen_stopt_voor_het_ophalen():
    llm = FakeLLM([response([text_block("WORKERS: annotatie\nPLAN: annoteer")], "end_turn")])
    graph = FakeGraph()
    events = _run(answer_stream("annoteer artikel 8 en 9 IW 1990", settings=make_settings(), llm=llm, graph=graph))
    assert llm.index == 1, "alleen de router; geen ophaal-agent"
    assert graph.queries == []
    assert not any(e["type"] in {"doel", "element", "kandidaten", "error"} for e in events), events
    assert "artikel 8 en artikel 9" in _tekst(events)


def test_afwijzing_blijft_niet_hangen_in_het_gesprek():
    llm = FakeLLM([response([text_block("WORKERS: annotatie\nPLAN: annoteer")], "end_turn"),
                   response([text_block("WORKERS: definitie\nPLAN: leg uit")], "end_turn"),
                   response([text_block("Een belastingaanslag is invorderbaar.")], "end_turn")])
    _run(answer_stream("annoteer artikel 8 en 9", "gesprek", settings=make_settings(), llm=llm, graph=FakeGraph()))
    events = _run(answer_stream("wat is invorderbaar?", "gesprek", settings=make_settings(), llm=llm, graph=FakeGraph()))
    assert "meer dan één artikel" not in _tekst(events)


def test_ophaal_json_meerdere_wordt_afgewezen():
    """De vraag zelf verraadt het niet ("de twee artikelen over uitstel"), de ophaal-agent wel."""
    llm = FakeLLM([
        response([text_block("WORKERS: annotatie\nPLAN: annoteer")], "end_turn"),
        response([text_block(json.dumps({"meerdere": ["25", "26"]}))], "end_turn"),
    ])
    events = _run(answer_stream("annoteer de twee bepalingen over uitstel", settings=make_settings(),
                                llm=llm, graph=FakeGraph()))
    assert not any(e["type"] in {"doel", "element", "kandidaten"} for e in events)
    assert "artikel 25 en artikel 26" in _tekst(events)


def test_vangnet_twee_opgehaalde_artikelen_annoteert_niet_stil_de_laatste():
    llm = FakeLLM([
        response([text_block("WORKERS: annotatie\nPLAN: annoteer")], "end_turn"),
        response([tool_block("t1", "get_artikel", {"bwb_id": IW, "artikel": "8"})], "tool_use"),
        response([tool_block("t2", "get_artikel", {"bwb_id": IW, "artikel": "9"})], "tool_use"),
        response([text_block(json.dumps({"bwbId": IW, "artikel": "9", "lid": "", "citeertitel": "IW 1990"}))], "end_turn"),
    ])
    events = _run(answer_stream("annoteer de invorderingstermijnen", settings=make_settings(),
                                llm=llm, graph=FakeGraph(result="?x\n")))
    assert not any(e["type"] in {"doel", "element", "kandidaten"} for e in events), events
    assert "artikel 8 en artikel 9" in _tekst(events)


def test_misser_in_een_andere_regeling_telt_niet_als_tweede_artikel():
    from agent.doel import _meerdere_artikelen
    berichten = [{"role": "assistant", "content": [
        {"type": "tool_use", "name": "get_artikel", "input": {"bwb_id": "BWBR0002320", "artikel": "9"}},
        {"type": "tool_use", "name": "get_artikel", "input": {"bwb_id": IW, "artikel": "9"}},
        {"type": "tool_use", "name": "get_bepaling", "input": {"bwb_id": IW, "nummer": "9.1"}},
    ]}]
    assert _meerdere_artikelen({"messages": berichten, "answer": ""}) == []
