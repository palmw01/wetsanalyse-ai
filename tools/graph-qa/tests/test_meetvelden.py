"""Twee meetvelden voor de meetlus van ADR-016 (§A6): de modelronde op elke toolaanroep, en de reden van een
sjabloonweigering. Geen van beide verandert wat het model ziet.

- **`ronde` op `tool_execution`.** Twee aanroepen met dezelfde ronde liepen naast elkaar. Zonder dit veld was de
  rondegrens alleen af te leiden uit de eventvolgorde, en bij connectortools niet (ronde 1 van A2, 12 nov 2026).
- **`geweigerd_reden` in de meting.** `duiding.vul` weigert om vier verschillende redenen; de telling per functie liet
  niet zien welke. De reden is een naam uit de code, zonder inhoud: de melding zelf gaat alleen naar het model.
"""
from __future__ import annotations

import asyncio

import pytest

from agent.agent import answer_stream
from agent.nodes.sjabloon import geweigerd, redencode
from agent.sjablonen import Onvulbaar
from agent.sjablonen.duiding import vul
from tests.fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block


def _run(gen):
    async def collect():
        return [ev async for ev in gen]

    return asyncio.run(collect())


def _supervisor(specialist: str = "duiding"):
    return response([text_block(f"SPECIALIST: {specialist}\nPLAN: kort plan.")], "end_turn")


def test_elke_toolaanroep_draagt_de_modelronde_die_erom_vroeg():
    llm = FakeLLM([
        _supervisor(),
        # Ronde 1: twee aanroepen naast elkaar. Ronde 2: één. Dan het antwoord.
        response([tool_block("t1", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": "9"}),
                  tool_block("t2", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": "10"})], "tool_use"),
        response([tool_block("t3", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": "11"})], "tool_use"),
        response([text_block("Antwoord.")], "end_turn"),
    ])
    events = _run(answer_stream("Hoe verhouden artikel 9, 10 en 11 van de Invorderingswet 1990 zich tot elkaar?",
                                settings=make_settings(), llm=llm, graph=FakeGraph(result="")))
    rondes = {e["call_id"]: e["ronde"] for e in events if e["type"] == "tool_execution"}
    assert rondes == {"t1": 1, "t2": 1, "t3": 2}
    assert all("ronde" in e for e in events if e["type"] == "tool_execution"), "op het begin en op het eind van elke aanroep"
    # Het verzoek aan het model draagt het veld niet: het is een meetveld.
    assert all("'ronde':" not in str(c["messages"]) for c in llm.calls)


def test_een_aanroep_van_de_code_zelf_heeft_ronde_nul():
    """Een route in code (hier: een genoemd artikel, de bepalingsroute) roept een tool aan zonder model."""
    llm = FakeLLM([response([text_block("Toelichting.")], "end_turn")])
    events = _run(answer_stream("Wat staat er in artikel 9 van de Invorderingswet 1990?", settings=make_settings(),
                                llm=llm, graph=FakeGraph(result="")))
    eigen = [e for e in events if e["type"] == "tool_execution"]
    assert all(e["ronde"] == 0 for e in eigen)


@pytest.mark.parametrize(("invoer", "code"), [
    ({"kort_antwoord": ""}, "kort_antwoord"),
    ({"kort_antwoord": "Een uitleg."}, "geen_passage"),
    ({"kort_antwoord": "Een uitleg.", "onderbouwing": [{"bepaling": "urn:bwb:BWBR0004770:art-9", "van": "x", "tot": "y",
                                                         "waarom": "z"}]}, "passage_niet_te_tonen"),
])
def test_een_weigering_van_de_duiding_draagt_haar_reden_als_code(invoer, code):
    with pytest.raises(Onvulbaar) as fout:
        vul(invoer, [])
    assert fout.value.code == code
    assert redencode(fout.value) == "duiding.vul", "de telling per functie blijft vergelijkbaar met eerdere metingen"


def test_de_meting_telt_de_weigering_per_functie_en_per_reden():
    with pytest.raises(Onvulbaar) as fout:
        vul({"kort_antwoord": "Een uitleg."}, [])
    telling = geweigerd({}, "antwoord_duiding", fout.value)["sjabloon_telling"]
    assert telling == {"geweigerd": {"antwoord_duiding:duiding.vul": 1},
                       "geweigerd_reden": {"antwoord_duiding:duiding.vul:geen_passage": 1}}
    # Een tweede weigering om een andere reden: dezelfde functie, een andere reden.
    with pytest.raises(Onvulbaar) as fout2:
        vul({"kort_antwoord": ""}, [])
    telling = geweigerd({"sjabloon_telling": telling}, "antwoord_duiding", fout2.value)["sjabloon_telling"]
    assert telling["geweigerd"] == {"antwoord_duiding:duiding.vul": 2}
    assert telling["geweigerd_reden"] == {"antwoord_duiding:duiding.vul:geen_passage": 1,
                                          "antwoord_duiding:duiding.vul:kort_antwoord": 1}


def test_een_reden_is_een_naam_uit_de_code_zonder_inhoud():
    """De melding kan tekst uit de vraag of uit een bron dragen; de code niet."""
    from agent.sjablonen.duiding import _genoemd_is_gelezen

    fout = _genoemd_is_gelezen(["artikel 99", "artikel 12"], {}, [])
    assert fout.code == "genoemd_onbekend" and "artikel 99" in str(fout) and "99" not in fout.code
    assert Onvulbaar("x").code == ""
