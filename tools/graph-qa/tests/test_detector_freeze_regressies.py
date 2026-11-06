"""Reproducties uit bestaande T3/T4-exports; geen juridische referentieannotaties."""
import json
from pathlib import Path

import pytest

from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
from agent.jas_pipeline.detectoren.syntactisch import BijzinDetector, NaamwoordgroepDetector, NominalisatieDetector
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


@pytest.mark.parametrize("cid", ["IW02", "IW03", "WZT04"])
def test_nominalisatie_infinitieftak_verwart_deelwoord_niet_met_infinitief(parser, cid):
    from eval.taal_benchmark import ontwikkelcasussen
    tekst = next(c["tekst"] for c in ontwikkelcasussen() if c["id"] == cid)
    a = parser.analyseer(tekst)
    token = next(t for t in a.tokens if t.tekst == "bepaalde")
    assert token.feat("VerbForm") == "Part", "de regressie betreft de waargenomen deelwoordparse"
    ks = NominalisatieDetector().detecteer(BronTekst.van_tekst(cid, tekst, analyse=a)).kandidaten
    assert not any(e.detail == "bepaalde" for k in ks for e in k.evidence)


def _kandidaten(detector, tekst, parser, cid="urn:bwb:BWBX:artikel:1"):
    return detector.detecteer(BronTekst.van_tekst(cid, tekst, analyse=parser.analyseer(tekst))).kandidaten


@pytest.mark.parametrize("tekst,woord", [
    ("De inspecteur beslist over de toekenning van een subsidie.", "toekenning"),   # bestuursrecht
    ("De ontvanger stelt de termijn vast voor de betaling van een belastingaanslag.", "betaling"),   # belastingrecht
])
def test_nominalisatie_met_voorwerp_is_geen_rechtsobject(parser, tekst, woord):
    [k] = [k for k in _kandidaten(NominalisatieDetector(), tekst, parser) if woord in k.span.tekst]
    assert k.evidence[0].regel == "jas.feit.nominalisatie_met_voorwerp"
    assert set(k.possible_classes) == {"Rechtsfeit", "Voorwaarde"}
    assert not [n for n in _kandidaten(NaamwoordgroepDetector(), tekst, parser) if n.span.tekst.endswith(woord)]


def test_door_bepaling_laat_een_zaak_mogelijk(parser):
    tekst = "De verzekerde ontvangt een vergoeding door de zorgverzekeraar."
    assert [n for n in _kandidaten(NaamwoordgroepDetector(), tekst, parser) if n.span.tekst.endswith("vergoeding")]


@pytest.mark.parametrize("tekst", [
    "De minister stelt regels met betrekking tot de verstrekking van gegevens.",
    "De raad neemt een besluit met betrekking tot de verlening van een vergunning.",
])
def test_grens_begint_na_de_vaste_uitdrukking(parser, tekst):
    [k] = [k for k in _kandidaten(NominalisatieDetector(), tekst, parser)]
    assert k.span.tekst.startswith("de ") and "betrekking" not in k.span.tekst
    assert not [n for n in _kandidaten(NaamwoordgroepDetector(), tekst, parser) if "betrekking" in n.span.tekst]


@pytest.mark.parametrize("tekst,zaak,getal", [
    ("De aanvrager kan niet meer dan twee percelen opgeven.", "percelen", "twee"),   # omgevingsrecht
    ("Het college benoemt ten hoogste drie leden.", "leden", "drie"),                # bestuursrecht
])
def test_aantalsgrens_valt_buiten_de_naamwoordgroep(parser, tekst, zaak, getal):
    groepen = [n.span.tekst for n in _kandidaten(NaamwoordgroepDetector(), tekst, parser)]
    assert zaak in groepen and not [g for g in groepen if getal in g and zaak in g]
