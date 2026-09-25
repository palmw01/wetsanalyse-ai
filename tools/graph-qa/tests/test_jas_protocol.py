"""Protocolpropagatie en bronintegriteit; geen claim over modelkwaliteit."""
import hashlib
import json
from pathlib import Path


from agent.jas_klassen import GELDIGE_JAS_KLASSEN
from scripts.render_jas_referentieset import MAP, render


def _cases():
    return json.loads((MAP/'cases.json').read_text())


def test_conceptset_is_gesplitst_op_wetsfamilie_en_niet_gold():
    cases = _cases()
    assert len(cases) == len({c['id'] for c in cases}) == 24
    assert len({c['familie'] for c in cases}) == 6
    dev = {c['familie'] for c in cases if c['split']=='ontwikkeling'}
    held = {c['familie'] for c in cases if c['split']=='held-out'}
    assert len(dev)==4 and len(held)==2 and not dev & held
    assert all(c['referentie_status'] == 'provisional' for c in cases)


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
