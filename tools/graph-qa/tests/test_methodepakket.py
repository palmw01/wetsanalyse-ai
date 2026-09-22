"""Importcontract, traceerbaarheid en modelaanroepen via bestaande routes."""
import json
import logging
import shutil
import subprocess
import sys
import pytest
from agent.agent import answer_stream
from agent.methode import instructies
from agent.methodepakket import PAKKET
from scripts.genereer_methodepakket import DOEL, SKILL, compileer, genereer, sha
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block
from test_doel_en_modellen import _run, _aanloop, _annoteer, _critic, _ELEMENT, _GROEN, DOEL as TARGET, ARTIKEL_TSV, LID_TSV


def antwoord(text): return response([text_block(text)], 'end_turn')


def check(call, rol):
    assert f'rol {rol}' in call['system']
    for key in PAKKET['rollen'][rol]: assert PAKKET['secties'][key]['tekst'] in call['system']
    if 'system_delen' in call:
        assert f'rol {rol}' in call['system_delen'][0]
        assert all('WETSANALYSE' not in d for d in call['system_delen'][1:])


def test_drift_en_hashes():
    assert DOEL.read_text() == genereer()
    assert compileer() == PAKKET
    for spec in PAKKET['secties'].values(): assert spec['sha256'] == sha(spec['tekst'])
    assert PAKKET['sha256'] == sha(json.dumps({k:v for k,v in PAKKET.items() if k != 'sha256'}, sort_keys=True, ensure_ascii=False))


@pytest.mark.parametrize('fout', ['rol','selectie','bron','sectie','dubbel','pad','versie'])
def test_ongeldige_import_faalt(tmp_path, fout):
    skill = tmp_path/'skill'; shutil.copytree(SKILL, skill)
    pad = skill/'agentrollen.json'; mapping = json.loads(pad.read_text())
    if fout == 'rol': mapping['rollen']['vreemd'] = ['basis']
    if fout == 'selectie': mapping['rollen']['duiding'] = ['onbekend']
    if fout == 'bron': mapping['secties']['basis']['bronnen'] = ['M99']
    if fout == 'pad': mapping['secties']['basis']['bestand'] = '../buiten.md'
    if fout in ['sectie','dubbel']:
        ref = skill/'references/agentrollen.md'
        ref.write_text(ref.read_text().replace('<!-- methode:basis:begin -->', '' if fout == 'sectie' else '<!-- methode:basis:begin -->'*2))
    if fout == 'versie':
        ref = skill/'SKILL.md'; ref.write_text(ref.read_text().replace('methode_versie:', 'vervallen:'))
    pad.write_text(json.dumps(mapping))
    with pytest.raises(ValueError): compileer(skill)


def test_logging(caplog):
    with caplog.at_level(logging.INFO, logger='graph_qa.methode'): instructies('duiding')
    r = caplog.records[-1]
    assert r.methode_sha256 == PAKKET['sha256']
    assert r.methode_secties == PAKKET['rollen']['duiding']
    assert r.methode_rol == 'duiding'
    assert 'tekst' not in r.__dict__
    with pytest.raises(KeyError): instructies('onbekend')


@pytest.mark.parametrize('rol',['definitie','duiding','algemeen'])
def test_gewone_route(rol):
    llm = FakeLLM([antwoord(f'SPECIALIST: {rol}\nPLAN: analyse'), antwoord('Antwoord.')])
    _run(answer_stream('Leg uit', settings=make_settings(), llm=llm, graph=FakeGraph()))
    check(llm.calls[0], 'supervisor'); check(llm.calls[1], rol)
    assert llm.calls[0]['tools'] == []


def test_advies():
    llm = FakeLLM([antwoord('Advies.')])
    events = _run(answer_stream('Waarom?', modus='advies', settings=make_settings(), llm=llm, graph=FakeGraph()))
    check(llm.calls[0], 'duiding')
    assert not any(e['type'] in ['element','doel'] for e in events)


def test_volledige_ophaalroute():
    llm = FakeLLM([*_aanloop(), _annoteer([_ELEMENT]), _critic([_GROEN])])
    _run(answer_stream('Annoteer artikel 9 lid 1', settings=make_settings(), llm=llm, graph=FakeGraph(result=LID_TSV)))
    for call,rol in zip(llm.calls,['supervisor','retrieval','retrieval','annotator','critic'], strict=True): check(call,rol)
    assert llm.calls[-1]['tools'] == llm.calls[-2]['tools'] == []


def test_explicit_doel():
    llm = FakeLLM([_annoteer([_ELEMENT]), _critic([_GROEN])])
    _run(answer_stream('Annoteer', doel=TARGET, settings=make_settings(), llm=llm, graph=FakeGraph(result=ARTIKEL_TSV)))
    assert len(llm.calls) == 2
    check(llm.calls[0], 'annotator'); check(llm.calls[1], 'critic')


def test_kandidaten():
    from test_kandidaat_splitsing import _volledige_keten, _annoteer as run_split
    llm = _volledige_keten(); run_split(llm)
    check(llm.calls[3], 'kandidaten'); check(llm.calls[4], 'classificatie'); check(llm.calls[5], 'critic')


def test_decompositie_synthese():
    llm = FakeLLM([antwoord('SPECIALIST: duiding\nPLAN: onderzoek'), antwoord('1. Eerste vraag\n2. Tweede vraag'),
                   antwoord('Eerste antwoord.'), antwoord('Tweede antwoord.'), antwoord('Samen.')])
    _run(answer_stream('Twee vragen', settings=make_settings(enable_decomposition=True), llm=llm, graph=FakeGraph()))
    for call,rol in zip(llm.calls,['supervisor','decompositie','duiding','duiding','synthese'], strict=True): check(call,rol)


def test_correctie():
    llm = FakeLLM([antwoord('SPECIALIST: duiding\nPLAN: uitleg'),
                   antwoord('Zie [jci1.3:c:BWBR0004770&artikel=99].'), antwoord('Zonder onbewezen verwijzing.')])
    _run(answer_stream('Leg uit', settings=make_settings(), llm=llm, graph=FakeGraph()))
    assert len(llm.calls) == 3
    check(llm.calls[1], 'duiding'); check(llm.calls[2], 'duiding')


def test_productiepackage_zonder_skill(tmp_path):
    shutil.copytree(DOEL.parent, tmp_path/'agent', ignore=shutil.ignore_patterns('__pycache__'))
    code = ('import sys; sys.path.insert(0, '+repr(str(tmp_path))+'); '
            'from agent.methode import instructies; from agent.annotatie_prompt import annotatie_systeemprompt; '
            'assert "rol duiding" in instructies("duiding"); assert "rol annotator" in annotatie_systeemprompt()')
    subprocess.run([sys.executable,'-I','-c',code], cwd=tmp_path, check=True, capture_output=True)


def test_herziening_met_onopgelost_fragment():
    llm = FakeLLM([
        _annoteer([_ELEMENT, {'id':'fout','klasse':'Voorwaarde','tekst':'verzonnen tekst','lid':'1'}]),
        _critic([_GROEN]), _annoteer([_ELEMENT]), _critic([_GROEN]),
    ])
    _run(answer_stream('Annoteer', doel=TARGET, settings=make_settings(), llm=llm, graph=FakeGraph(result=ARTIKEL_TSV)))
    assert len(llm.calls) == 4
    check(llm.calls[2], 'herziening'); check(llm.calls[3], 'critic')
    assert all(c['tools'] == [] for c in llm.calls)
