"""De traceerbaarheidsmatrix van Lex Bench (plan-lex-bench.md §21): het register is goed gevormd, en elke marker in de
tests noemt een bekend risico. Voorlopig alleen zichtbaar, nog niet bindend (besluit 15): een risico zonder test op zijn
primaire laag faalt niet, het staat als *niet gedekt* in `python scripts/risicomatrix.py`."""
from __future__ import annotations

import importlib.util

import pytest

from routeboek import WORTEL

pytestmark = pytest.mark.risico("R21", laag=2)

_spec = importlib.util.spec_from_file_location("risicomatrix", WORTEL / "scripts" / "risicomatrix.py")
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)


def test_het_register_is_goed_gevormd():
    reg = rm.register()
    ids = [r["id"] for r in reg["risicos"]]
    assert ids == sorted(set(ids)) and ids[0] == "R01", "unieke ids, op volgorde"
    for r in reg["risicos"]:
        assert r["risico"] and r["impact"] in ("hoog", "middel", "laag"), r
        assert r["primair"] in range(1, 6) and (r["tweede"] is None or r["tweede"] in range(1, 6)), r


def test_elke_marker_noemt_een_bekend_risico():
    markers = rm.verzamel()
    soorten = {("tests/poort" in m["test"]) or m["test"].endswith(".py::" + m["test"].split("::")[-1]) for m in markers}
    assert markers and soorten, "de zoektocht vindt geen markers: dan toetst deze test niets"
    assert any(".test.ts" in m["test"] for m in markers), "geen vitest-marker gevonden"
    assert any(m["test"].endswith((".mjs", ".yml")) for m in markers), "geen marker in een script of workflow gevonden"
    assert rm.matrix(markers)["onbekend"] == [], "een marker noemt een risico dat niet in het register staat"


def test_de_matrix_meldt_een_onbekend_risico_en_telt_per_laag():
    """De positieve controle, met een verzonnen marker."""
    m = rm.matrix([{"risico": "R99", "laag": 1, "test": "x"}, {"risico": "R01", "laag": 3, "test": "y"}])
    assert m["onbekend"] == ["R99"]
    assert m["risicos"]["R01"]["per_laag"] == {"3": ["y"]} and not m["risicos"]["R01"]["primair_gedekt"]
    assert "R01" in m["niet_gedekt_hoog"]
