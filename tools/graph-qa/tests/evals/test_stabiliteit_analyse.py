"""Stabiliteitsanalyse: uitlijning over runs en de maten daarop, zonder model."""
from __future__ import annotations

import pytest

from eval.keten_fixture import laad_cases
from eval.stabiliteit_analyse import analyseer_casus, cluster, plaats

TEKST = 'De ontvanger betaalt de belastingaanslag binnen zes weken na de dagtekening.'


def _e(tekst: str, klasse: str, **extra) -> dict:
    return {'tekst': tekst, 'klasse': klasse, **extra}


def _run(*elementen: dict) -> list[dict]:
    return list(elementen)


BASIS = _run(_e('De ontvanger', 'Rechtssubject'), _e('de belastingaanslag', 'Rechtsobject'),
             _e('binnen zes weken', 'Tijdsaanduiding'))


def test_identieke_runs_zijn_volledig_stabiel():
    m = analyseer_casus(TEKST, [BASIS, BASIS, BASIS])
    assert m['clusters'] == 3
    assert m['detectie_stabiel'] == 1.0
    assert m['span_exact'] == 1.0 and m['span_iou'] == 1.0
    assert m['klasse_unaniem'] == 1.0 and m['klasse_paarsgewijs'] == 1.0
    assert m['klasseparen'] == {}
    assert m['elementen_spreiding'] == 0


def test_klassewissel_levert_het_klassepaar_op():
    anders = _run(_e('De ontvanger', 'Rechtssubject'), _e('de belastingaanslag', 'Rechtsfeit'),
                  _e('binnen zes weken', 'Tijdsaanduiding'))
    m = analyseer_casus(TEKST, [BASIS, BASIS, anders])
    assert m['klasseparen'] == {'Rechtsfeit ↔ Rechtsobject': 2}
    assert m['voorbeelden']['Rechtsfeit ↔ Rechtsobject'] == 'de belastingaanslag'
    assert m['klasse_unaniem'] == pytest.approx(2 / 3, abs=1e-3)
    assert m['detectie_stabiel'] == 1.0


def test_ontbrekend_element_verlaagt_detectiestabiliteit():
    zonder = _run(_e('De ontvanger', 'Rechtssubject'), _e('de belastingaanslag', 'Rechtsobject'))
    m = analyseer_casus(TEKST, [BASIS, zonder])
    assert m['clusters'] == 3
    assert m['detectie_stabiel'] == pytest.approx(2 / 3, abs=1e-3)
    assert m['elementen_per_run'] == [3, 2]


def test_overlappende_spans_komen_in_een_cluster():
    breder = _run(_e('De ontvanger', 'Rechtssubject'), _e('de belastingaanslag', 'Rechtsobject'),
                  _e('binnen zes weken na de dagtekening', 'Tijdsaanduiding'))
    m = analyseer_casus(TEKST, [BASIS, breder])
    assert m['clusters'] == 3
    assert m['span_exact'] == pytest.approx(2 / 3, abs=1e-3)
    assert m['span_iou'] < 1.0
    assert m['klasse_unaniem'] == 1.0


def test_cluster_neemt_per_run_hooguit_een_element():
    per_run = [[((0, 12), 'A'), ((0, 5), 'B')], [((0, 12), 'A')]]
    clusters = cluster(per_run)
    assert all(len(c) == len(set(c)) for c in clusters)
    assert sorted(len(c) for c in clusters) == [1, 2]
    groot = next(c for c in clusters if len(c) == 2)
    assert groot[0] == ((0, 12), 'A')


def test_plaatsing_via_anker_kiest_het_juiste_voorkomen():
    tekst = 'de termijn van zes weken; daarna nogmaals zes weken.'
    tweede = tekst.rindex('zes weken')
    element = _e('zes weken', 'Tijdsaanduiding', ankers=[{
        'start': 100, 'eind': 109,  # offsets op een ander corpus; de context beslist
        'voor': tekst[:tweede], 'na': tekst[tweede + 9:]}])
    assert plaats(element, tekst) == ((tweede, tweede + 9), False)
    assert plaats(_e('zes weken', 'Tijdsaanduiding'), tekst) == ((tekst.index('zes weken'), 24), True)


def test_plaatsing_negeert_witruimteverschil_en_meldt_onplaatsbaar():
    tekst = 'De ontvanger\nbetaalt.'
    assert plaats(_e('De ontvanger betaalt', 'Rechtshandeling'), tekst)[0] == (0, 20)
    m = analyseer_casus(tekst, [[_e('verzonnen fragment', 'Rechtsfeit')], []])
    assert m['onplaatsbaar'] == 1 and m['clusters'] == 0


def test_held_out_casussen_worden_geweigerd():
    with pytest.raises(ValueError, match='held-out'):
        laad_cases(['IW01', 'BW01'])
    with pytest.raises(ValueError, match='onbekende'):
        laad_cases(['XX99'])
    assert [c['id'] for c in laad_cases(['IW01'])] == ['IW01']


def test_fixture_draagt_de_volledige_keten():
    """De fixture moet de v2-bronroute voeden; anders levert elke meting stil nul calls op."""
    import asyncio

    from agent.agent import answer_stream
    from agent.jas_pipeline.kandidaten import GEEN_ANNOTATIE
    from eval.keten_fixture import Capture, FixtureGraph, LegeAnnotaties, fixture_doel
    from fakes import KetenLLM, make_settings

    llm = Capture(KetenLLM(kies=lambda toegestaan, f: (
        'Rechtssubject' if f == 'De ontvanger' and 'Rechtssubject' in toegestaan else GEEN_ANNOTATIE)))
    case = {'id': 'X', 'tekst': TEKST}

    async def verzamel():
        return [e async for e in answer_stream(
            'Annoteer de aangewezen bronpassage.', doel=fixture_doel(case), llm=llm,
            graph=FixtureGraph(TEKST), annotaties=LegeAnnotaties(TEKST),
            settings=make_settings())]

    events = asyncio.run(verzamel())
    assert not [e for e in events if e['type'] == 'error'], events
    elementen = [e['element'] for e in events if e['type'] == 'element']
    assert 'De ontvanger' in {el['tekst'] for el in elementen}
    assert llm.calls, 'de fixture voedde geen classifier-call'


def test_geneste_bijna_gelijke_spans_lopen_niet_door_elkaar():
    tekst = 'Toegelaten wordt de bestuurder die aannemelijk maakt dat hij niets verzuimde.'
    groot = _e('de bestuurder die aannemelijk maakt dat hij niets verzuimde', 'Rechtssubject')
    klein = _e('die aannemelijk maakt dat hij niets verzuimde', 'Voorwaarde')
    # Andere volgorde per run: de uitlijning mag daar niet van afhangen.
    m = analyseer_casus(tekst, [[groot, klein], [klein, groot], [groot, klein]])
    assert m['clusters'] == 2
    assert m['klasseparen'] == {}
    assert m['span_exact'] == 1.0


def test_omhullend_extra_element_kaapt_geen_cluster():
    """Live gezien bij IW03: een extra omhullend element deed alle geneste elementen opschuiven."""
    tekst = 'Tot de weerlegging wordt toegelaten de bestuurder die aannemelijk maakt dat hij niets verzuimde.'
    rs = _e('de bestuurder die aannemelijk maakt dat hij niets verzuimde', 'Rechtssubject')
    vw = _e('die aannemelijk maakt dat hij niets verzuimde', 'Voorwaarde')
    extra = _e('Tot de weerlegging wordt toegelaten de bestuurder die aannemelijk maakt dat hij niets verzuimde',
               'Voorwaarde')
    m = analyseer_casus(tekst, [[rs, vw], [extra, rs, vw], [rs, vw]])
    assert m['klasseparen'] == {}
    assert m['clusters'] == 3
    assert m['detectie_stabiel'] == pytest.approx(2 / 3, abs=1e-3)
