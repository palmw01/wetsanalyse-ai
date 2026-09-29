"""Graafcasussen en gemarkeerde synthetische tegenproeven; geen juridische goldset."""
import json
from pathlib import Path

import pytest

from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
from agent.jas_pipeline.fusie import fuseer
from agent.jas_pipeline.taal import SpacyProvider

DOSSIER = Path(__file__).resolve().parents[3] / "docs/wetsanalyse/onderzoek-invordering-2026-09-29"
CASES = {c["id"]: c for c in json.loads((DOSSIER / "bronnen.json").read_text())["casussen"]}


@pytest.fixture(scope="module")
def parser():
    p = SpacyProvider("nl_core_news_md")
    if p.analyseer("Een synthetische controle.").gedegradeerd:
        pytest.skip("volledige parser vereist")
    return p


def detect(tekst, parser=None):
    return fuseer(detecteer_alles(BronTekst.van_tekst(
        "urn:synthetische-controle", tekst, analyse=parser.analyseer(tekst) if parser else None)))


@pytest.mark.parametrize("verwijzing", ["artikel 9.1", "artikel 3:4", "art. 4"])
def test_afleiding_beschermt_notatie_en_stopt_bij_volgende_zin(verwijzing):
    zin = f"Volgens {verwijzing} bedraagt de vergoeding € 1.000."
    ks = detect(zin + " De aanvraag vervalt.").kandidaten
    ar = [k for k in ks if "Afleidingsregel" in k.possible_classes]
    assert [k.span.tekst for k in ar] == [zin]


@pytest.mark.parametrize("datum,geldig", [
    ("31 december", True), ("29 februari", True), ("29 februari 2024", True),
    ("29 februari 2025", False), ("31 februari", False), ("31 april", False),
    ("0 januari", False), ("1\u00a0januari 2027", True),
])
def test_synthetische_kalenderdatum(datum, geldig):
    ks = detect(f"De termijn eindigt op {datum}. Daarna vervalt het recht.").kandidaten
    dates = [k for k in ks if any(e.code == "TEMPORAL_DATE" for e in k.evidence)]
    assert [k.span.tekst for k in dates] == ([f"op {datum}"] if geldig else [])


def test_datums_op_herhaalde_offsets_blijven_afzonderlijk():
    c = CASES["LI-9.1"]
    ks = detect(c["tekst"]).kandidaten
    dates = [k for k in ks if any(e.code == "TEMPORAL_DATE" for e in k.evidence)]
    assert len(dates) == 2
    assert len({k.span.start for k in dates}) == 2
    assert all("31 december" in k.span.tekst for k in dates)


def test_beide_toewijzingen_en_elliptische_voorwaarde(parser):
    ks = detect(CASES["LI-9.1"]["tekst"], parser).kandidaten
    assert len([k for k in ks if "Afleidingsregel" in k.possible_classes]) == 2
    assert any(k.span.tekst == "Bij afwijkende boekjaren" and "Voorwaarde" in k.possible_classes for k in ks)
    assert any(k.span.tekst == "de laatste dag van de maand" and "Tijdsaanduiding" in k.possible_classes for k in ks)


@pytest.mark.parametrize("tekst,ar", [
    ("De vervaldag wordt op 31 december gesteld.", True),
    ("De vervaldag wordt gesteld op 31 december.", True),
    ("Het boek wordt op tafel gelegd.", False),
    ("Bij ministeriële regeling worden regels gesteld.", False),
    ("Hij neemt zoveel boeken als hij wil.", False),
    ("De bijdrage kent zoveel delen als er maanden resteren.", True),
])
def test_synthetische_toewijzing_en_aantal(parser, tekst, ar):
    assert any("Afleidingsregel" in k.possible_classes for k in detect(tekst, parser).kandidaten) == ar


def test_berekening_en_nominalisatie_lid5(parser):
    ks = detect(CASES["IW-9-5"]["tekst"], parser).kandidaten
    assert any(k.span.start == 0 and "Afleidingsregel" in k.possible_classes for k in ks)
    n = [k for k in ks if k.span.start == 474 and any(e.code == "NOMINALIZED_ACTION" for e in k.evidence)]
    assert [k.span.tekst for k in n] == ["de dagtekening van het aanslagbiljet"]
    assert any(k.span.tekst == "telkens een maand later" and "Tijdsaanduiding" in k.possible_classes for k in ks)
    assert any(k.span.tekst.startswith("Indien") and "niet leidt tot meer dan één termijn" in k.span.tekst for k in ks)


def test_nominalisatie_behoudt_gezamenlijke_start(parser):
    ks = detect("Na de verzending en de bekendmaking van het besluit begint de termijn.", parser).kandidaten
    assert any("de verzending en de bekendmaking van het besluit" in k.span.tekst for k in ks)


def test_kalenderpositie_en_brongetrouwheid(parser):
    tekst = CASES["LI-9.5"]["tekst"]
    ks = detect(tekst, parser).kandidaten
    assert any(k.span.tekst == "de dag die hetzelfde nummer heeft als dat van de dagtekening" and
               "Tijdsaanduiding" in k.possible_classes for k in ks)
    assert any(k.span.start == 556 and "Afleidingsregel" in k.possible_classes for k in ks)
    assert all(tekst[k.span.start:k.span.eind] == k.span.tekst for k in ks)
    assert not any(k.span.tekst == "als dat van de dagtekening" and "Voorwaarde" in k.possible_classes for k in ks)


def test_korte_tijdkern_krijgt_tijd_met_herleidbare_bijdrage(parser):
    f = detect(CASES["IW-9-1"]["tekst"], parser)
    kort = next(k for k in f.kandidaten if k.span.tekst == "zes weken")
    assert "Tijdsaanduiding" in kort.possible_classes
    assert any(b.kandidaat_id == kort.id and b.detector == "fusie" for b in f.bijdragen)
    assert any(b.kandidaat_id == kort.id and b.detector == "naamwoordgroep" for b in f.bijdragen)
