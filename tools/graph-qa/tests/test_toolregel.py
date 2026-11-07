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
    assert _toolregel({"name": "search_wetgeving", "input": {"query": "uitstel"}}) == "zoekt „uitstel”"
    assert _toolregel({"name": "list_regelingen", "input": {}}) == "bekijkt welke regelingen er zijn"
    assert _toolregel({"name": "iets_nieuws", "input": {}}) == "raadpleegt de kennisgraaf"
    for regel in (_toolregel({"name": n, "input": {"bwb_id": "BWBR1", "artikel": "1", "query": "x"}}) for n in
                  ("get_lid", "get_context", "zoek_definitie", "inhoudsopgave", "search_annotaties")):
        assert "_" not in regel and "(" not in regel.split(" (")[0]
