"""`bronmodel.vindplaats` tegen de gedeelde vectorset (frontend/lib/jci-vectoren.json).

Dezelfde vectoren toetsen `bronDoel` in de werkplek en de importer: één bepaling heeft op alle drie
de kanten dezelfde bronnode, of de bronnenlijst toont haar dubbel en de 3D-graaf opent iets anders.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from bronmodel.vindplaats import vindplaats

_PAD = Path(__file__).resolve().parents[3] / "frontend" / "lib" / "jci-vectoren.json"
_VECTOREN = json.loads(_PAD.read_text(encoding="utf-8"))["vectoren"] if _PAD.exists() else []


@pytest.mark.skipif(not _VECTOREN, reason="frontend niet aanwezig")
@pytest.mark.parametrize("v", _VECTOREN, ids=lambda v: v["ref"])
def test_vectoren(v: dict) -> None:
    vp = vindplaats(v["ref"])
    if v["soort"] is None:
        assert vp is None
        return
    assert vp is not None
    assert (vp.bron_iri, vp.soort, vp.label) == (v["iri"], v["soort"], v["label"])


def test_iri_en_jci_van_dezelfde_node_vallen_samen() -> None:
    a = vindplaats("jci1.3:c:BWBR0005537&artikel=4:94a&z=2026-08-15&g=2026-08-15")
    b = vindplaats("urn:bwb:BWBR0005537:artikel:4%3A94a")
    assert a is not None and a == b


def test_hoofdstuk_valt_niet_samen_met_de_regeling() -> None:
    assert vindplaats("urn:bwb:BWBR0004770:hoofdstuk:I").bron_iri != vindplaats("BWBR0004770").bron_iri


@pytest.mark.parametrize("ref", [
    "", "https://example.org", "urn:bwb:verwijzing:d612be1321b3fdf4", "urn:bwb:BWBR0004770:artikel",
    "urn:bwb:BWBR0004770:onbekend:1", "urn:bwb:BWBR0004770:artikel:%ZZ", "jci1.3:c:BWBR0004770&artikel=",
])
def test_geen_vindplaats(ref: str) -> None:
    assert vindplaats(ref) is None


def test_id_iri_wordt_herkend_zonder_label() -> None:
    vp = vindplaats("urn:bwb:BWBR0005537:id:BWBR0005537%2FBijlage1")
    assert vp is not None and vp.soort == "node" and vp.label == ""
