"""Fase 2A: de gesplitste annotatieroute (kandidaatgeneratie → classificatie).

Met `enable_kandidaat_splitsing` aan loopt de annotatie via twee LLM-calls in plaats van één:
`annoteer_kandidaten_node` zoekt spans zonder ze te classificeren, `annoteer_klasseer_node` hangt er
de JAS-klasse aan. Alles daarna (Critic, patch, emit) is ongewijzigd.

Deze route was tot nu toe volledig ongetest — de vlag staat default uit, dus de andere tests liepen
er nooit doorheen. Wat hier vastligt is precies wat er dan misging: het corpus moet van de ene node
naar de andere komen, een onderwerp mag ook hier niet geannoteerd worden, en een bepaling die niet
op te halen is hoort dat te zeggen in plaats van "geen elementen gevonden".

FakeLLM-volgorde: supervisor → ophaal-agent(tool_use) → ophaal-agent(doel-JSON) →
kandidaten-JSON → elementen-JSON → critic-JSON.
"""
from __future__ import annotations

import asyncio
import json

from agent.agent import answer_stream
from agent.annotatie import filter_kandidaten, parse_kandidaten
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block

LID_TSV = json.dumps('?nummer\t?tekst\t?jci\n"1"\t"De ontvanger verleent uitstel van betaling."@nl\t"jci"')

DOEL_JSON = '{"bwbId":"BWBR0004770","artikel":"9","lid":"1","nummer":"","citeertitel":"IW 1990"}'

KANDIDATEN_JSON = json.dumps({"kandidaten": [
    {"span": "De ontvanger", "lid": "1", "reden": "lijkt een handelende partij"},
    {"span": "verleent uitstel van betaling", "lid": "1", "reden": "lijkt een bevoegdheid"},
]})

ELEMENTEN_JSON = json.dumps({"elementen": [
    {"klasse": "Rechtssubject", "tekst": "De ontvanger", "lid": "1", "toelichting": "wie",
     "alternatieven": []},
    {"klasse": "Rechtsbetrekking", "tekst": "verleent uitstel van betaling", "lid": "1",
     "toelichting": "wat", "alternatieven": []},
]})

CRITIC_JSON = json.dumps({"oordelen": [
    {"index": 0, "aandacht": "groen", "motivatie": "helder"},
    {"index": 1, "aandacht": "groen", "motivatie": "helder"},
], "ontbrekend": []})

ONDERWERP_KANDIDATEN_JSON = json.dumps({"kandidaten": [
    {"bwbId": "BWBR0004770", "artikel": "36", "lid": "", "citeertitel": "Invorderingswet 1990",
     "fragment": "Hoofdelijk aansprakelijk is voor de loonbelasting…"},
    {"bwbId": "BWBR0004770", "artikel": "36a", "lid": "1", "citeertitel": "Invorderingswet 1990",
     "fragment": "Hoofdelijk aansprakelijk is de bestuurder…"},
]})


def _run(gen):
    async def collect():
        return [ev async for ev in gen]

    return asyncio.run(collect())


def _splitsing(**extra):
    return make_settings(
        enable_decomposition=True, enable_kandidaat_splitsing=True, critic_max_rondes=0, **extra,
    )


def _annoteer(llm, *, graph_result=LID_TSV):
    return _run(answer_stream(
        "annoteer artikel 9 lid 1 van de Invorderingswet 1990",
        settings=_splitsing(), llm=llm, graph=FakeGraph(result=graph_result),
    ))


def _volledige_keten() -> FakeLLM:
    return FakeLLM([
        response([text_block("WORKERS: annotatie\nPLAN: annoteer art 9 lid 1")], "end_turn"),
        response([tool_block("t1", "get_lid", {"bwb_id": "BWBR0004770", "artikel": "9", "lid": "1"})], "tool_use"),
        response([text_block(DOEL_JSON)], "end_turn"),
        response([text_block(KANDIDATEN_JSON)], "end_turn"),
        response([text_block(ELEMENTEN_JSON)], "end_turn"),
        response([text_block(CRITIC_JSON)], "end_turn"),
    ])


# --- de deterministische filter --------------------------------------------------------------

def test_filter_houdt_alleen_wat_letterlijk_in_de_tekst_staat():
    corpus = "De ontvanger verleent uitstel van betaling."
    ruw = parse_kandidaten(json.dumps({"kandidaten": [
        {"span": "De ontvanger", "lid": "1"},
        {"span": "de curator", "lid": "1"},          # staat er niet — verzonnen span
        {"span": "x", "lid": "1"},                   # te kort
        {"span": "De ontvanger", "lid": "1"},        # dubbel
    ]}))
    spans = [k["span"] for k in filter_kandidaten(ruw, corpus)]
    assert spans == ["De ontvanger"]


def test_parser_overleeft_proza_om_de_json_heen():
    tekst = "Hier zijn de kandidaten:\n```json\n" + KANDIDATEN_JSON + "\n```\nTot zover."
    assert [k["span"] for k in parse_kandidaten(tekst)] == [
        "De ontvanger", "verleent uitstel van betaling",
    ]


# --- de keten ---------------------------------------------------------------------------------

def test_de_gesplitste_route_grondt_tegen_de_opgehaalde_tekst():
    """De kern: `annoteer_kandidaten_node` haalt het corpus op, `annoteer_klasseer_node` gebruikt het.

    Gaf de eerste node het corpus niet mee, dan grondde de tweede elk fragment tegen een lege tekst
    en verwierp hij alles — een annotatie die stilzwijgend niets oplevert.
    """
    events = _annoteer(_volledige_keten())

    elementen = [e["element"] for e in events if e["type"] == "element"]
    assert {el["klasse"] for el in elementen} == {"Rechtssubject", "Rechtsbetrekking"}
    for el in elementen:
        assert el["grounded"] is True, "gegrond tegen de tekst die de kandidaat-node ophaalde"
        assert el["vindplaats"] == "BWBR0004770 art. 9 lid 1"


def test_de_kandidaten_worden_gemeld_voor_de_eval():
    """`kandidaten_v2a` is de enige manier om kandidaat-recall los van classificatie te meten."""
    events = _annoteer(_volledige_keten())
    kandidaten = next(e for e in events if e["type"] == "kandidaten_v2a")["items"]
    assert [k["span"] for k in kandidaten] == ["De ontvanger", "verleent uitstel van betaling"]


def test_een_onderwerp_wordt_ook_hier_eerst_voorgelegd():
    """Zonder deze grens gaat de gesplitste route annoteren op een bepaling die niemand aanwees."""
    llm = FakeLLM([
        response([text_block("WORKERS: annotatie\nPLAN: zoek de bepalingen over dit onderwerp")], "end_turn"),
        response([tool_block("t1", "semantic_search", {"query": "aansprakelijkheid bestuurder"})], "tool_use"),
        response([text_block(ONDERWERP_KANDIDATEN_JSON)], "end_turn"),
    ])
    events = _run(answer_stream(
        "annoteer alles over aansprakelijkheid van de bestuurder",
        settings=_splitsing(), llm=llm,
        graph=FakeGraph(result=json.dumps('?iri\t?titel\n"iri"\t"Invorderingswet 1990"')),
    ))

    kandidaten = next(e for e in events if e["type"] == "kandidaten")["kandidaten"]
    assert [k["artikel"] for k in kandidaten] == ["36", "36a"]
    soorten = {e["type"] for e in events}
    assert "element" not in soorten and "doel" not in soorten, "de jurist kiest eerst"
    assert llm.index == 3, "geen kandidaat-, klasseer- of critic-call"


def test_een_bepaling_die_niet_op_te_halen_is_zegt_dat():
    """Anders leest de jurist "geen JAS-elementen gevonden" terwijl de tekst nooit binnenkwam."""
    llm = FakeLLM([
        response([text_block("WORKERS: annotatie\nPLAN: annoteer art 9 lid 1")], "end_turn"),
        response([tool_block("t1", "get_lid", {"bwb_id": "BWBR0004770", "artikel": "9", "lid": "1"})], "tool_use"),
        response([text_block(DOEL_JSON)], "end_turn"),
    ])
    # Lege graaf: er valt geen corpus op te halen.
    events = _annoteer(llm, graph_result=json.dumps("?nummer\t?tekst\t?jci\n"))

    tekst = "".join(e["content"] for e in events if e["type"] == "token")
    assert "niet ophalen" in tekst
    assert not [e for e in events if e["type"] == "element"]
    assert llm.index == 3, "geen kandidaat- en geen klasseer-call op een lege tekst"
