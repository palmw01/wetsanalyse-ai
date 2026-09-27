"""Reproducties uit bestaande T3/T4-exports; geen juridische referentieannotaties."""
import json
from pathlib import Path

import pytest

from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
from agent.jas_pipeline.detectoren.syntactisch import BijzinDetector
from agent.jas_pipeline.taal import SpacyProvider

CASES = {c["id"]: c for c in json.loads((Path(__file__).parent / "fixtures/detector_audit_diagnostiek.json").read_text())}


def test_t3_duur_stopt_voor_volgende_termijnen():
    c = CASES["IW-D2"]
    ks = [k for r in detecteer_alles(BronTekst.van_tekst(c["bron_iri"], c["tekst"])) for k in r.kandidaten
          if any(e.code == "TEMPORAL_DURATION" for e in k.evidence)]
    assert "één maand na de dagtekening van het aanslagbiljet" in {k.span.tekst for k in ks}
    assert not any("en elk" in k.span.tekst for k in ks)


@pytest.mark.parametrize("tekst,verwacht", [
    ("zes weken na de verzending en de bekendmaking van het besluit.",
     "zes weken na de verzending en de bekendmaking van het besluit"),
    ("zes weken na de dagtekening van het aanslagbiljet.",
     "zes weken na de dagtekening van het aanslagbiljet"),
    ("één maand na de verzending en ieder van de volgende termijnen een maand later.",
     "één maand na de verzending"),
])
def test_duur_behoudt_startgebeurtenis(tekst, verwacht):
    ks = [k for r in detecteer_alles(BronTekst.van_tekst("test", tekst)) for k in r.kandidaten
          if any(e.code == "TEMPORAL_DURATION" for e in k.evidence)]
    assert verwacht in {k.span.tekst for k in ks}


@pytest.fixture(scope="module")
def parser():
    p = SpacyProvider()
    if p.analyseer("test").gedegradeerd:
        pytest.skip("nl_core_news_md ontbreekt; freeze vereist ook een run met echte parse")
    return p


def voorwaarden(tekst, parser):
    bron = BronTekst.van_tekst("test", tekst, analyse=parser.analyseer(tekst))
    return [k.span.tekst for k in BijzinDetector().detecteer(bron).kandidaten
            if any(e.code == "CONDITIONAL_CLAUSE" for e in k.evidence)]


def test_t4_elliptische_vergelijking_is_geen_voorwaarde(parser):
    ks = voorwaarden(CASES["LI-D3"]["tekst"], parser)
    assert "als dat van de dagtekening" not in ks
    assert any(k.startswith("Als de dagtekening") for k in ks)


@pytest.mark.parametrize("tekst,positief", [
    ("Als de aanvrager niet tijdig betaalt, vervalt het recht.", True),
    ("De aanslag als bedoeld in artikel 9 is invorderbaar.", False),
    ("Hij treedt op als bestuurder van het lichaam.", False),
    ("Het bedrag is even hoog als dat van de aanslag.", False),
    ("Als hetzelfde nummer wordt gebruikt, vervalt het recht.", True),
    ("Hetzelfde recht vervalt als dat van toepassing is.", True),
])
def test_als_contexten(parser, tekst, positief):
    assert bool(voorwaarden(tekst, parser)) is positief
