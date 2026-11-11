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


def test_een_iso_datum_in_de_bron_is_dezelfde_datum():
    """De metadata van een Kamerstuk draagt "2024-10-31"; Lex schrijft "31 oktober 2024" (gesprek e906567a)."""
    from agent.hoeveelheden import buiten, hoeveelheden

    assert hoeveelheden('{"datum": "2024-10-31"}') == {"31 oktober 2024"}
    assert buiten("Het stuk is van 31 oktober 2024.", '{"datum": "2024-10-31"}') == []
    assert buiten("Het stuk is van 1 november 2024.", '{"datum": "2024-10-31"}') == ["1 november 2024"]
    # Geen datum: een dossiernummer met streepjes of een onmogelijke maand.
    assert hoeveelheden("kst-2024-10-31-x 2024-13-01") == set()


def test_een_kaal_getal_in_een_tabel_draagt_de_eenheid_van_de_titel_of_de_kolom():
    """K28 (ronde 1 Kamerstukken, 11 nov 2026): "€ 106 miljoen" uit tabel 1 van kst-33755-3 telde als niet opgehaald."""
    import json
    from agent.hoeveelheden import buiten, uit_tabellen
    eerste = json.dumps({"status": "ok", "stuk": {"id": "kst-33755-3"}, "resultaten": [
        {"nr": 13, "soort": "tabel", "tekst": "Tabel 1 Opbrengst (€ mln)", "cellen": ["Jaar", "2014", "Aandeel (%)"]},
        {"nr": 14, "soort": "tabelrij", "cellen": ["Rente", "-106", "12"], "tekst": "Rente | -106 | 12"}]})
    volgende = json.dumps({"status": "ok", "stuk": {"id": "kst-33755-3"}, "resultaten": [
        {"nr": 15, "soort": "tabelrij", "cellen": ["Totaal", "155", "4,5"], "tekst": "Totaal | 155 | 4,5"}]})
    bron = uit_tabellen([("get_kamerstuk", eerste), ("get_kamerstuk", volgende)])
    assert buiten("Lagere uitgaven van € 106 miljoen, in totaal € 155; een aandeel van 12% en 4,5 procent.", bron) == []
    assert buiten("Het is € 12.", bron) == ["12 euro"], "de kolom met procenten is geen bedrag"
    assert uit_tabellen([("get_kamerstuk", json.dumps({"status": "ok", "resultaten": [
        {"nr": 1, "soort": "tabelrij", "cellen": ["7"]}]}))]) == "", "zonder tabel geen eenheid"
