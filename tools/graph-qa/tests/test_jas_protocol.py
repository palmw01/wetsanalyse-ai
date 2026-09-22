"""Protocolpropagatie en bronintegriteit; geen claim over modelkwaliteit."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent import annotatie_prompt as prompts
from agent.jas_klassen import GELDIGE_JAS_KLASSEN
from agent.nodes import annotatie as nodes
from fakes import FakeLLM, make_settings, response, text_block
from scripts.render_jas_referentieset import MAP, render


@pytest.mark.parametrize('builder,section', [
    (prompts.annotatie_systeemprompt, 'Classificatie'),
    (prompts.klasseer_systeemprompt, 'Classificatie'),
    (prompts.kandidaten_systeemprompt, 'Kandidaten'),
    (prompts.critic_systeemprompt, 'Review'),
    (prompts.herziening_systeemprompt, 'Review'),
])
def test_protocolwijziging_bereikt_elke_relevante_prompt(monkeypatch, builder, section):
    from agent.methodepakket import PAKKET
    key = {'Classificatie': 'classificatie', 'Kandidaten': 'kandidaten', 'Review': 'review'}[section]
    monkeypatch.setitem(PAKKET['secties']['annotatie-gedeeld'], 'tekst', 'unieke-gedeelde-instructie')
    monkeypatch.setitem(PAKKET['secties']['annotatie-' + key], 'tekst', 'unieke-fase-instructie')
    modes = [()] if section == 'Kandidaten' else [(), (True,)]
    for args in modes:
        text = builder(*args)
        assert 'unieke-gedeelde-instructie' in text
        assert 'unieke-fase-instructie' in text


def test_verfijnde_kandidaatgrens_wordt_op_bron_gecontroleerd(monkeypatch):
    corpus = 'Het bedrag bedraagt tien euro.'
    llm = FakeLLM([response([text_block(json.dumps({'elementen': [
        {'klasse': 'Afleidingsregel', 'tekst': corpus, 'lid': '1'},
        {'klasse': 'Rechtssubject', 'tekst': 'De minister', 'lid': '1'},
    ]}))], 'end_turn')])
    monkeypatch.setattr(nodes, 'get_stream_writer', lambda: lambda event: None)
    monkeypatch.setattr(nodes, '_bepaal_doel', lambda state: {'bwbId':'test', 'artikel':'1', 'lid':'1'})
    result = nodes.annoteer_klasseer_node(
        SimpleNamespace(llm=llm, model='fake', settings=make_settings()),
        {'corpus':corpus, 'kandidaten_v2a':[{'span':'bedraagt','lid':'1'}]},
    )
    assert [e['tekst'] for e in result['voorstellen']] == [corpus]
    assert result['verworpen_fragmenten'][0]['tekst'] == 'De minister'
    assert llm.calls[0]['tools'] == []


def _cases():
    return json.loads((MAP/'cases.json').read_text())


def test_conceptset_is_gesplitst_op_wetsfamilie_en_niet_gold():
    cases = _cases()
    assert len(cases) == len({c['id'] for c in cases}) == 24
    assert len({c['familie'] for c in cases}) == 6
    dev = {c['familie'] for c in cases if c['split']=='ontwikkeling'}
    held = {c['familie'] for c in cases if c['split']=='held-out'}
    assert len(dev)==4 and len(held)==2 and not dev & held
    assert all(c['status']=='concept' and not c['referentie_goedgekeurd'] for c in cases)


def test_conceptannotaties_zijn_letterlijk_en_hebben_precies_voorkomen():
    for c in _cases():
        assert hashlib.sha256(c['tekst'].encode()).hexdigest() == c['tekst_sha256']
        for e in c['annotaties']:
            assert c['tekst'][e['start']:e['end']] == e['tekst'], (c['id'], e['id'])
            assert e['klasse'] in GELDIGE_JAS_KLASSEN


def test_leesbare_dossiers_volgen_de_conceptset():
    for name, text in render(_cases()).items():
        assert (MAP/name).read_text() == text


def test_bewaarde_bronnen_kloppen_met_manifest():
    root = Path(__file__).resolve().parents[3]
    sources = json.loads((root/'docs/wetsanalyse/bronnen/manifest.json').read_text())
    assert {c['bron_id'] for c in _cases()} <= {s['id'] for s in sources}
    for source in sources:
        if source['status'] != 'lokaal_bewaard':
            continue
        path = root/source['pad']
        # Copyrightmateriaal is bewust lokaal-only en ontbreekt in CI.
        if path.exists():
            assert hashlib.sha256(path.read_bytes()).hexdigest() == source['sha256'], source['id']
