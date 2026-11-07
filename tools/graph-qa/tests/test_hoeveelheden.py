"""R4a: termijnen, bedragen en datums in vrije tekst, getoetst tegen wat er is opgehaald."""
from __future__ import annotations

import json

import pytest

from agent.grounding import check_grounding
from agent.hoeveelheden import buiten, hoeveelheden

IW9 = "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet."


@pytest.mark.parametrize("tekst,verwacht", [
    ("binnen zes weken", {"6 week"}),
    ("binnen 6 weken", {"6 week"}),
    ("één maand na de dagtekening", {"1 maand"}),
    ("een maand later", {"1 maand"}),
    ("veertien dagen", {"14 dag"}),
    ("vijf jaren", {"5 jaar"}),
    ("€ 1.500 of 20 procent", {"1500 euro", "20 procent"}),
    ("op 1 oktober 2026 in werking", {"1 oktober 2026"}),
    ("artikel 9 heeft 12 leden", set()),          # een vindplaats en een telling zijn geen hoeveelheid
    ("de onderdelen a en b", set()),
])
def test_wat_als_hoeveelheid_telt(tekst, verwacht):
    assert hoeveelheden(tekst) == verwacht


def test_geschreven_en_in_cijfers_zijn_gelijk():
    assert buiten("Je hebt 6 weken.", IW9) == []


def test_een_termijn_die_de_bron_niet_noemt():
    assert buiten("Je hebt twee maanden de tijd.", IW9) == ["2 maand"]


def test_een_datum_zonder_bron_maakt_het_antwoord_onbepaald():
    """Acceptatie 7 nov 2026: "inwerkingtredingsdatum: 1 oktober 2026" zonder bron. Een signaal, geen afkeuring."""
    trace = [("get_lid", json.dumps({"status": "ok", "resultaten": [{"iri": "urn:bwb:BWBR0004770:artikel:9:lid:1", "tekst": IW9}]}))]
    r = check_grounding("De termijn is zes weken. Het lid geldt sinds 1 oktober 2026.", trace)
    assert r.grounded is True and r.niveau == "onbepaald" and "1 oktober 2026" in r.onbevestigd


def test_een_termijn_uit_de_bron_is_geen_signaal():
    trace = [("get_lid", json.dumps({"status": "ok", "resultaten": [{"iri": "urn:bwb:BWBR0004770:artikel:9:lid:1", "tekst": IW9}]}))]
    assert "6 week" not in check_grounding("Je hebt 6 weken de tijd.", trace).onbevestigd
