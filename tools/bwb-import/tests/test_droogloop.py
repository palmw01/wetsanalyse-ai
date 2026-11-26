"""De droogloop (`--droog`): alles behalve GraphDB.

Een nieuwe regeling hoort eerst getoetst te worden – opgehaald, gevalideerd, geparst, gebouwd met de
index van de hele run en gemeten – voordat een named-graph PUT iets in de graaf vervangt. Deze tests
leggen vast dat de droogloop GraphDB niet aanraakt en de graph als Turtle wegschrijft.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bronmodel.bwb.parser import ToestandParser
from rdflib import Graph

import app.main as main_module

FIXTURES = Path(__file__).parent / "fixtures"


def test_droogloop_schrijft_turtle_en_raakt_graphdb_niet(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    xml = FIXTURES / "sample_toestand.xml"

    def haal_en_parse(bwb_id, settings):
        return ToestandParser().parse(xml), None, xml, True

    def verboden(*_a, **_k):
        raise AssertionError("de droogloop mag GraphDB niet aanspreken")

    monkeypatch.setattr(main_module, "_haal_en_parse", haal_en_parse)
    monkeypatch.setattr(main_module, "prepare", verboden)
    monkeypatch.setattr(main_module.GraphDbWriter, "graaf_stand", verboden)
    monkeypatch.setattr(main_module.GraphDbWriter, "vervang_wet", verboden)
    monkeypatch.setattr(main_module.GraphDbWriter, "ensure_similarity_index", verboden)
    monkeypatch.setenv("BWB_IMPORT_WTI", "false")

    bwb_id = ToestandParser().parse(xml).bwb_id
    code = main_module.main([bwb_id, "--droog", str(tmp_path)])

    assert code == 0
    ttl = tmp_path / f"{bwb_id}.ttl"
    assert ttl.exists()
    g = Graph().parse(ttl, format="turtle")
    assert len(g) > 0
    assert "Import-overzicht" in capsys.readouterr().out
