"""De hoofdzin van een ALS→DAN-regel draagt geen eigen norm (`agent/jas_pipeline/hoofdzin.py`).

Besluit eigenaar 25 nov 2026: de regel is de hele zin. Positief, negatief, rand en overlap, zoals de detectorregels.
"""
from __future__ import annotations

import pytest

from agent.jas_pipeline import hoofdzin as H
from agent.jas_pipeline.besluit import deterministisch
from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
from agent.jas_pipeline.fusie import fuseer
from agent.jas_pipeline.kandidaten import CandidateStatus
from agent.jas_pipeline.taal import SpacyProvider


@pytest.fixture(scope="module")
def parser():
    p = SpacyProvider()
    if p.analyseer("test").gedegradeerd:
        pytest.skip("volledige parser vereist")
    return p


def _per_span(tekst: str, parser) -> dict:
    bron = BronTekst.van_tekst("urn:test", tekst, analyse=parser.analyseer(tekst))
    return {k.span.tekst: k for k in H.pas_toe(fuseer(detecteer_alles(bron)).kandidaten)}


def test_de_hoofdzin_van_een_als_dan_regel_draagt_geen_norm(parser):
    """Positief: de regel is de hele zin; de hoofdzin wordt niets, want hij had alleen normklassen."""
    per = _per_span("Indien de aanslag is opgelegd, vervalt de termijn één maand na de dagtekening.", parser)
    assert "Afleidingsregel" in per["Indien de aanslag is opgelegd, vervalt de termijn één maand na de dagtekening."].possible_classes
    gevolg = per["vervalt de termijn één maand na de dagtekening"]
    assert gevolg.status is CandidateStatus.REJECTED and gevolg.evidence[-1].code == H.CODE
    assert deterministisch(gevolg).reden == H.REGEL


def test_wat_in_de_hoofdzin_staat_blijft(parser):
    """Overlap: de tijdsaanduiding en de voorwaarde in dezelfde zin blijven eigen kandidaten, onaangeroerd."""
    per = _per_span("Indien de aanslag is opgelegd, vervalt de termijn één maand na de dagtekening.", parser)
    assert "Tijdsaanduiding" in per["één maand na de dagtekening"].possible_classes
    assert "Voorwaarde" in per["Indien de aanslag is opgelegd"].possible_classes
    assert all(e.code != H.CODE for k in per.values() if k.span.tekst != "vervalt de termijn één maand na de dagtekening"
               for e in k.evidence)


@pytest.mark.parametrize("tekst", ["De termijn vervalt één maand na de dagtekening.",
                                   "De ontvanger is bevoegd de aanslag te verrekenen indien de schuld vaststaat."])
def test_zonder_voorwaarde_ervoor_verandert_niets(parser, tekst):
    """Negatief: zonder ALS→DAN-regel ervoor (of met de voorwaarde erachter) blijft de uitkomst gelijk."""
    bron = BronTekst.van_tekst("urn:test", tekst, analyse=parser.analyseer(tekst))
    kandidaten = fuseer(detecteer_alles(bron)).kandidaten
    assert H.pas_toe(kandidaten) is kandidaten


def test_een_inversie_als_voorwaarde(parser):
    """Rand: de persoonsvorm voorop ('Is …, dan vervalt …') is ook een voorwaarde."""
    per = _per_span("Is de termijn zes weken, dan vervalt de termijn op 26 april.", parser)
    gevolg = per["dan vervalt de termijn op 26 april"]
    assert gevolg.status is CandidateStatus.REJECTED
    regel = per["Is de termijn zes weken, dan vervalt de termijn op 26 april."]
    assert set(regel.possible_classes) == {"Afleidingsregel", "Rechtsbetrekking"}
