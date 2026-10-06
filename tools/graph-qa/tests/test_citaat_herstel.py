"""Een bijna-letterlijk citaat wordt de brontekst, niet een correctieronde.

Gemeten in de gesprekseval (docs/architectuur/metingen/gesprek-vervolgvragen-2026-10-06): het model
zette "Zes weken na de dagtekening van het aanslagbiljet" tussen aanhalingstekens waar de bron
"zes weken …" heeft, of een punt binnen het citaat waar de bron doorloopt. De controle keurde dat
af, er volgde een correctieronde, en de jurist had het afgekeurde antwoord al gezien.
"""
from __future__ import annotations

from agent.grounding import check_grounding, herstel_citaten

BRON = [("get_lid", '?tekst\n"Een belastingaanslag is invorderbaar zes weken na de dagtekening van het '
                    'aanslagbiljet."'),
        ("jas_klasse_opvragen", "Een tijdsaanduiding is nodig om een tijdsverloop met rechtsgevolg uit "
                                "te drukken of als variabele bij een rechtssubject.")]


def test_hoofdletter_aan_het_begin_wordt_de_brontekst():
    antwoord = 'De termijn is "Zes weken na de dagtekening van het aanslagbiljet" volgens de wet.'
    nieuw, hersteld = herstel_citaten(antwoord, BRON)
    assert nieuw == 'De termijn is "zes weken na de dagtekening van het aanslagbiljet" volgens de wet.'
    assert hersteld == [("Zes weken na de dagtekening van het aanslagbiljet",
                         "zes weken na de dagtekening van het aanslagbiljet")]
    assert check_grounding(nieuw, BRON).niveau == "gegrond"


def test_een_punt_die_de_bron_niet_heeft_gaat_achter_het_aanhalingsteken():
    antwoord = 'De klasse dient “om een tijdsverloop met rechtsgevolg uit te drukken.”'
    nieuw, _ = herstel_citaten(antwoord, BRON)
    assert nieuw == 'De klasse dient “om een tijdsverloop met rechtsgevolg uit te drukken”.'
    assert check_grounding(nieuw, BRON).niveau == "gegrond"


def test_wat_echt_afwijkt_blijft_een_afwijking():
    for citaat in ('"zes weken na de verzending van het aanslagbiljet"',      # ander woord
                   '"zes weken (...) van het aanslagbiljet"',                 # weglating
                   '"is invorderbaar binnen zes weken na dagtekening"'):     # eigen woorden
        nieuw, hersteld = herstel_citaten(f"Zie {citaat}.", BRON)
        assert hersteld == [] and nieuw == f"Zie {citaat}."
        assert check_grounding(nieuw, BRON).niveau == "ongegrond"


def test_een_letterlijk_citaat_blijft_onaangeroerd():
    antwoord = 'Zie "zes weken na de dagtekening van het aanslagbiljet".'
    assert herstel_citaten(antwoord, BRON) == (antwoord, [])


def test_annotaties_zijn_geen_bron_voor_herstel():
    trace = [("search_annotaties", '{"tekst": "zes weken na de dagtekening van het aanslagbiljet"}')]
    assert herstel_citaten('Zie "Zes weken na de dagtekening van het aanslagbiljet".', trace)[1] == []


def test_alleen_bij_een_eenduidige_vindplaats():
    trace = [("get_lid", "De ontvanger stelt de termijn vast. de Ontvanger stelt de termijn vast.")]
    assert herstel_citaten('Zie "DE ONTVANGER STELT DE TERMIJN VAST".', trace)[1] == []


def test_in_de_keten_ziet_de_jurist_alleen_het_herstelde_citaat():
    import asyncio

    from agent.agent import answer_stream
    from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block

    tsv = '?node\t?tekst\n<urn:bwb:BWBR0004770:artikel:9:lid:1>\t"Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet."'
    llm = FakeLLM([
        response([text_block("WORKERS: antwoord\nSPECIALIST: duiding\nPLAN: lid 1")], "end_turn"),
        response([tool_block("t1", "get_lid", {"bwb_id": "BWBR0004770", "artikel": "9", "lid": "1"})], "tool_use"),
        response([text_block('De termijn: "Zes weken na de dagtekening van het aanslagbiljet." (BWBR0004770)')], "end_turn"),
        response([text_block("Mag niet nodig zijn.")], "end_turn"),
    ])

    async def run():
        return [e async for e in answer_stream("Wanneer is een aanslag invorderbaar?", settings=make_settings(
            enable_decomposition=False), llm=llm, graph=FakeGraph(result=tsv))]
    events = asyncio.run(run())
    tokens = "".join(e["content"] for e in events if e["type"] == "token")
    assert tokens == 'De termijn: "zes weken na de dagtekening van het aanslagbiljet". (BWBR0004770)'
    assert next(e for e in events if e["type"] == "grounding")["niveau"] == "gegrond"
    assert len(llm.calls) == 3, "geen correctieronde"
    assert any("letterlijk gemaakt" in e.get("message", "") for e in events if e["type"] == "status")
