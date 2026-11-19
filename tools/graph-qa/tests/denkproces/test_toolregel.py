"""De statusregel van een graafaanroep, in de woorden van een jurist (G2a)."""
from __future__ import annotations

from agent import overzicht
from agent.narratie import _toolregel


def test_een_lid_met_de_naam_van_de_regeling(monkeypatch):
    monkeypatch.setattr(overzicht, "_REGELINGEN_CACHE", [{"bwb_id": "BWBR0004770", "citeertitel": "Invorderingswet 1990"}])
    regel = _toolregel({"name": "get_lid", "input": {"bwb_id": "BWBR0004770", "artikel": "9", "lid": "1"}})
    assert regel == "leest artikel 9, lid 1 (Invorderingswet 1990)"


def test_zonder_bekende_naam_het_bwb_id_en_nooit_de_toolnaam(monkeypatch):
    monkeypatch.setattr(overzicht, "_REGELINGEN_CACHE", [])
    assert _toolregel({"name": "get_artikel", "input": {"bwb_id": "BWBR0004770", "artikel": "25"}}) == "leest artikel 25 (BWBR0004770)"
    assert _toolregel({"name": "search_wetgeving", "input": {"query": "uitstel"}}) == "zoekt “uitstel”"
    assert _toolregel({"name": "list_regelingen", "input": {}}) == "bekijkt welke regelingen er zijn"
    assert _toolregel({"name": "iets_nieuws", "input": {}}) == "raadpleegt de kennisgraaf"
    for regel in (_toolregel({"name": n, "input": {"bwb_id": "BWBR1", "artikel": "1", "query": "x"}}) for n in
                  ("get_lid", "get_context", "zoek_definitie", "inhoudsopgave", "search_annotaties")):
        assert "_" not in regel and "(" not in regel.split(" (")[0]


def test_een_zoekactie_in_de_graaf_noemt_haar_afbakening(monkeypatch):
    """Twee zoekacties op dezelfde term, één in de definities en één in alle tekst, heetten allebei "zoekt “derdenbeslag”"
    met twee verschillende uitkomsten eronder (acceptatie 19 nov 2026)."""
    monkeypatch.setattr(overzicht, "_REGELINGEN_CACHE", [{"bwb_id": "BWBR0024096", "citeertitel": "Leidraad Invordering 2008"}])
    zoek = lambda naam, **inp: _toolregel({"name": naam, "input": {"query": "derdenbeslag", **inp}})
    assert zoek("search_wetgeving") == "zoekt “derdenbeslag”"
    assert zoek("search_wetgeving", limit=5) == "zoekt “derdenbeslag”", "de vorm van het antwoord is geen afbakening"
    assert zoek("search_wetgeving", veld="definieertBegrip") == "zoekt “derdenbeslag” (in de definities)"
    assert zoek("search_wetgeving", soort="Artikel", bwb_id="BWBR0024096") == \
        "zoekt “derdenbeslag” (alleen artikel, in Leidraad Invordering 2008)"
    assert zoek("zoek_opbouw", bwb_id="BWBR0024096") == "zoekt in de opbouw naar “derdenbeslag” (in Leidraad Invordering 2008)"
    # Een regel die de regeling al noemt, noemt haar niet nog eens.
    assert _toolregel({"name": "bijlagen", "input": {"bwb_id": "BWBR0024096"}}) == "bekijkt de bijlagen van Leidraad Invordering 2008"
    assert _toolregel({"name": "verwijst_naar_deze", "input": {"bwb_id": "BWBR0024096", "nummer": "14.4.1"}}) == \
        "zoekt wat naar artikel 14.4.1 (Leidraad Invordering 2008) verwijst"


def test_elk_zoekveld_van_de_graaf_heeft_woorden():
    from agent.graph import queries
    from agent.spoorbronnen import _VELDEN

    assert set(_VELDEN) == set(queries.FTS_VELDEN)
