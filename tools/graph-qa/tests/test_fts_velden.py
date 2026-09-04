"""Drift-guard: de zoekvelden die we het model aanbieden bestaan ook echt in de Lucene-index.

`search_wetgeving` biedt sinds 4 sep 2026 veldgericht zoeken aan (`definieertBegrip:"bestuurder"`).
Dat werkt alleen als de veldnaam overeenkomt met wat `tools/bwb-import` in de connector-config zet.
Doet hij dat niet, dan levert Lucene geen fout maar **nul treffers** – het model concludeert dan dat
het begrip niet in de wet staat, terwijl de vraag verkeerd gesteld was. Stille onvolledigheid,
dezelfde klasse fout als de `bwb:bevat`-bug.

De importer is de bron: `_FTS_VELDEN` plus het handmatig toegevoegde `label` (dat op `rdfs:label`
staat en dus niet in die tuple past). Deze test leest dat bestand als tekst – graph-qa mag
`bwb-import` niet importeren, het is een los pakket dat niet in dit image zit.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from agent.graph import queries

WRITER = Path(__file__).resolve().parents[3] / "tools" / "bwb-import" / "app" / "graphdb_writer.py"


def _velden_van_de_importer() -> set[str]:
    tekst = WRITER.read_text(encoding="utf-8")
    blok = re.search(r"_FTS_VELDEN = \(([^)]*)\)", tekst, re.S)
    assert blok, "kon _FTS_VELDEN niet vinden – is de vorm van graphdb_writer.py veranderd?"
    velden = set(re.findall(r'"([A-Za-z]+)"', blok.group(1)))
    # `label` wordt apart toegevoegd omdat het op rdfs:label staat, niet op een bwb:-property.
    velden.add("label")
    return velden


def _types_van_de_importer() -> set[str]:
    tekst = WRITER.read_text(encoding="utf-8")
    blok = re.search(r"_FTS_TYPES = \(([^)]*)\)", tekst, re.S)
    assert blok, "kon _FTS_TYPES niet vinden"
    return set(re.findall(r'"([A-Za-z]+)"', blok.group(1)))


@pytest.mark.skipif(not WRITER.exists(), reason=f"importer niet beschikbaar: {WRITER}")
def test_fts_velden_komen_overeen_met_de_index():
    assert set(queries.FTS_VELDEN) == _velden_van_de_importer(), (
        "queries.FTS_VELDEN loopt uit de pas met _FTS_VELDEN in tools/bwb-import. "
        "Een veldnaam die niet in de index staat geeft NUL treffers zonder foutmelding."
    )


@pytest.mark.skipif(not WRITER.exists(), reason=f"importer niet beschikbaar: {WRITER}")
def test_fts_types_komen_overeen_met_de_index():
    assert set(queries.FTS_TYPES) == _types_van_de_importer()


def test_een_onbekend_veld_wordt_geweigerd():
    """Liever een tool-foutmelding die het model kan herstellen dan stil nul treffers."""
    with pytest.raises(ValueError, match="Onbekend zoekveld"):
        queries.fts("iets", veld="bestaat_niet")
    with pytest.raises(ValueError, match="Onbekend soort"):
        queries.fts("iets", soort="Voetnoot")


def test_veldgericht_zoeken_bindt_de_hele_query():
    """`tekst:aansprakelijk bestuurder` zou anders alleen het eerste woord op het veld binden."""
    sparql = queries.fts("aansprakelijk bestuurder", veld="tekst")
    assert 'tekst:(aansprakelijk bestuurder)' in sparql
