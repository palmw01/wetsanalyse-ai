"""`bronmodel.bepaling_label` tegen de gedeelde vectorset (frontend/lib/bepalingLabel.vectoren.json).

Dezelfde vectoren toetsen `bepalingLabel` in de werkplek: een onderdeel heet in de bronnenlijst, de vindplaatsen van een
antwoord, de keuzekaart en het bepalingenpaneel overal hetzelfde. Een onderdeel zonder eigen nummer stond als
"Onderdeel –" in het paneel, een onderdeel van de Leidraad als "Onderdeel c." zonder artikel (25 nov 2026).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from bronmodel.vindplaats import bepaling_label

from agent.provenance import collect_sources
from agent.sjablonen.vullen import vindplaats_van

_ROOT = Path(__file__).resolve().parents[4]
_PAD = _ROOT / "frontend" / "lib" / "bepalingLabel.vectoren.json"
_VECTOREN = json.loads(_PAD.read_text(encoding="utf-8"))["vectoren"] if _PAD.exists() else []

_LR = ("urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie25%2FCirculaire.divisie25.3a"
       "%2FCirculaire.divisie25.3a.1")


@pytest.mark.skipif(not _VECTOREN, reason="frontend niet aanwezig")
@pytest.mark.parametrize("v", _VECTOREN, ids=lambda v: f"{v['iri'][-40:]}|{v['gegeven']}")
def test_vectoren(v: dict) -> None:
    assert bepaling_label(v["iri"], v["gegeven"]) == v["label"]


def test_vindplaatsen_van_een_antwoord_noemen_het_streepje_bij_zijn_artikel() -> None:
    assert vindplaats_van(f"{_LR}%2FTekst%2FOnderdeel._2", label="Onderdeel –").label == "Artikel 25.3a.1, 2e streepje"
    assert vindplaats_van(_LR, label="Voorwaarden standaardbetalingsregeling").label == "Voorwaarden standaardbetalingsregeling"
    assert vindplaats_van("urn:bwb:BWBR0004770:artikel:9:lid:2", label="Lid 2").label == "Artikel 9, lid 2"


def test_bronnenlijst_noemt_het_streepje_bij_zijn_artikel() -> None:
    rijen = [{"node": f"{_LR}%2FTekst%2FOnderdeel._{n}", "label": "Onderdeel –", "nummer": "–"} for n in (1, 2, 3)]
    tekst = json.dumps({"status": "ok", "volledig": True, "aantal": 3, "resultaten": rijen})
    labels = [s.label for s in collect_sources([("get_bepaling", tekst)])]
    assert labels == [f"Artikel 25.3a.1, {n}e streepje" for n in (1, 2, 3)]


def test_geen_eigen_lijst_opsommingstekens_in_de_agent() -> None:
    """De tekens van een ongenummerd onderdeel staan in `bronmodel.vindplaats.OPSOMMINGSTEKENS`; een tweede lijst in de
    agent loopt vroeg of laat uiteen (de hergebruikmelding telt ze met `isalnum`, dat is geen lijst)."""
    agent = _ROOT / "tools" / "graph-qa" / "agent"
    eigen = [p.relative_to(agent).as_posix() for p in agent.rglob("*.py")
             if re.search(r"""\{\s*["']–["']\s*,\s*["']—["']""", p.read_text(encoding="utf-8"))]
    assert eigen == []
