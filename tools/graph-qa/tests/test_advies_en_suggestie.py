"""**Advies bij twijfel** (`modus="advies"`) – een vraag bij een bestaande annotatie. De supervisor
kiest dan niet zelf maar routeert hard naar de antwoord-worker, zodat een adviesvraag
*topologisch* geen annotatie kan wijzigen: die route emit simpelweg geen doel/element-events.

Het Critic-advies op eigen markeringen van de jurist (`suggestie`-events) verviel met de
legacy-keten in ADR-001 PR 18.
"""
from __future__ import annotations

import asyncio
import json

from bron_fakes import answer_stream
from agent.models import ChatContext
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block

LID_TSV = json.dumps(
    '?nummer\t?tekst\t?jci\n"1"\t"De ontvanger verleent uitstel van betaling indien de schuldenaar '
    'daarom verzoekt."@nl\t"jci"'
)


def _run(gen):
    async def collect():
        return [ev async for ev in gen]

    return asyncio.run(collect())


# --- 1. de agent als sparringpartner -------------------------------------------------------------

def test_adviesvraag_wijzigt_nooit_een_annotatie():
    """De kern: geen doel- of element-events, dus er kán niets in het document belanden."""
    llm = FakeLLM([
        # GEEN supervisor-respons: bij modus=advies mag die node geen LLM-call doen. Zou hij dat
        # toch doen, dan pakt hij deze en loopt de rest van het scenario mis.
        response([tool_block("t1", "get_lid", {"bwb_id": "BWBR0004770", "artikel": "9", "lid": "1"})], "tool_use"),
        response([text_block("Een voorwaarde bepaalt wanneer een rechtsgevolg intreedt; hier is dat "
                             "de aanvraag van de schuldenaar.")], "end_turn"),
        response([text_block("gegrond")], "end_turn"),   # verify
    ])
    events = _run(answer_stream(
        "waarom is dit een Voorwaarde en geen Rechtsfeit?",
        modus="advies",
        context=ChatContext(
            bwbId="BWBR0004770", artikel="9", lid="1", element_id="el-a", klasse="Voorwaarde",
            fragment="indien de schuldenaar daarom verzoekt",
            corpus="De ontvanger verleent uitstel van betaling indien de schuldenaar daarom verzoekt.",
        ),
        settings=make_settings(enable_decomposition=False), llm=llm, graph=FakeGraph(result=LID_TSV),
    ))

    soorten = {e["type"] for e in events}
    assert "doel" not in soorten and "element" not in soorten, "advies mag niets voorstellen"
    assert "token" in soorten, "maar er komt wel een antwoord"


def test_adviesvraag_slaat_de_supervisor_over():
    """Geen LLM-call voor een keuze die al vaststaat – en geen kans dat hij 'annotatie' kiest."""
    llm = FakeLLM([
        response([text_block("Een voorwaarde is een conditie voor een rechtsgevolg.")], "end_turn"),
        response([text_block("gegrond")], "end_turn"),
    ])
    _run(answer_stream(
        "waarom deze klasse?", modus="advies", context=ChatContext(klasse="Voorwaarde"),
        settings=make_settings(enable_decomposition=False), llm=llm, graph=FakeGraph(result=LID_TSV),
    ))
    # De eerste call is meteen de agent (met SYSTEM_PROMPT), niet de supervisor.
    assert "WORKERS" not in llm.calls[0]["system"], "de supervisor-prompt hoort niet gedraaid te zijn"


def test_de_context_staat_in_de_prompt():
    llm = FakeLLM([
        response([text_block("Antwoord.")], "end_turn"),
        response([text_block("gegrond")], "end_turn"),
    ])
    _run(answer_stream(
        "klopt dit?", modus="advies",
        context=ChatContext(bwbId="BWBR0004770", artikel="9", lid="1", klasse="Voorwaarde",
                            fragment="indien de schuldenaar daarom verzoekt", corpus="De ontvanger…"),
        settings=make_settings(enable_decomposition=False), llm=llm, graph=FakeGraph(result=LID_TSV),
    ))
    system = llm.calls[0]["system"]
    assert "WAAR DE VRAAG OVER GAAT" in system
    assert "indien de schuldenaar daarom verzoekt" in system
    assert "ADVIESVRAAG" in system


def _motiveer(buren=()):
    llm = FakeLLM([
        response([text_block("Dit is een voorwaarde omdat…")], "end_turn"),
        response([text_block("gegrond")], "end_turn"),
    ])
    _run(answer_stream(
        "motiveer", modus="advies",
        context=ChatContext(bwbId="BWBR0004770", artikel="9", lid="1", klasse="Voorwaarde",
                            fragment="indien de schuldenaar daarom verzoekt",
                            bestaande_elementen=list(buren)),
        settings=make_settings(enable_decomposition=False), llm=llm, graph=FakeGraph(result=LID_TSV),
    ))
    return llm.calls[0]["system"]


def test_de_adviesvraag_wordt_afgebakend_tot_het_gekozen_fragment():
    """Eén element aanklikken en "motiveer" vragen hoort één motivering op te leveren.

    De annotatiebeurt zit in dezelfde thread, dus het model ziet álle markeringen in zijn historie
    staan en motiveerde ze zonder deze afbakening allemaal.
    """
    system = _motiveer()
    assert "AFBAKENING VAN DEZE VRAAG" in system
    assert "indien de schuldenaar daarom verzoekt" in system
    # De tegenkracht tegen het gespreksgeheugen: eerder voorgestelde elementen zijn géén onderwerp.
    assert "GEEN eigen motivering" in system
    assert "eerder in dit gesprek" in system


def test_de_buren_mogen_ter_ondersteuning_worden_gebruikt():
    """Niet verbieden, wel ondergeschikt maken: een voorwaarde is soms alleen uit te leggen door het
    rechtsgevolg te noemen waar hij bij hoort."""
    system = _motiveer()
    assert "NODIG is om" in system, "de buren mogen erbij als dat de onderbouwing dient"


def test_de_buren_gaan_mee_in_de_context_en_niet_uit_het_geheugen():
    """Anders verschilt hetzelfde antwoord per gesprek – afhankelijk van wat er nog in de historie zat."""
    system = _motiveer([
        {"id": "a", "klasse": "Rechtsobject", "tekst": "belastingaanslag", "lid": "1"},
        {"id": "b", "klasse": "Tijdsaanduiding", "tekst": "zes weken", "lid": "1"},
    ])
    assert "ANDERE MARKERINGEN IN DEZE BEPALING" in system
    assert 'Rechtsobject – "belastingaanslag"' in system
    assert 'Tijdsaanduiding – "zes weken"' in system


def test_zonder_buren_geen_leeg_kopje():
    assert "ANDERE MARKERINGEN" not in _motiveer()


def test_zonder_fragment_geen_afbakening():
    """Een vraag zonder aangewezen fragment (bv. over de bepaling als geheel) mag breed antwoorden."""
    llm = FakeLLM([
        response([text_block("Antwoord.")], "end_turn"),
        response([text_block("gegrond")], "end_turn"),
    ])
    _run(answer_stream(
        "waar gaat dit artikel over?", modus="advies",
        context=ChatContext(bwbId="BWBR0004770", artikel="9"),
        settings=make_settings(enable_decomposition=False), llm=llm, graph=FakeGraph(result=LID_TSV),
    ))
    assert "AFBAKENING VAN DEZE VRAAG" not in llm.calls[0]["system"]


def test_gewone_vraag_gebruikt_de_supervisor_gewoon():
    """De adviesmodus mag de normale route niet raken."""
    llm = FakeLLM([
        response([text_block("WORKERS: antwoord\nPLAN: beantwoord de vraag")], "end_turn"),
        response([text_block("Een voorwaarde is een conditie.")], "end_turn"),
        response([text_block("gegrond")], "end_turn"),
    ])
    _run(answer_stream(
        "wat is een voorwaarde?",
        settings=make_settings(enable_decomposition=False), llm=llm, graph=FakeGraph(result=LID_TSV),
    ))
    assert "WORKERS" in llm.calls[0]["system"], "zonder adviesmodus loopt het via de supervisor"
