"""Kleine lijsten die op meer plekken staan, en waarom (H8).

Wat api en agent allebei lezen staat één keer in `packages/bronmodel/bronmodel/taal.py`. Twee lijsten staan bewust
dubbel, omdat de lezer dat pakket niet kan gebruiken: de importer (geen bronmodel) en de logredactie (ook in de
frontend, en per dienst met eigen velden). Die bewaken we hier op tekst, zonder de onderdelen te importeren.
"""
from __future__ import annotations

import ast
import re

from routeboek import FRONTEND, WORTEL

TAAL = WORTEL / "packages" / "bronmodel" / "bronmodel" / "taal.py"


def _toekenning(pad, naam: str) -> ast.expr:
    for knoop in ast.parse(pad.read_text(encoding="utf-8")).body:
        if isinstance(knoop, ast.Assign) and any(getattr(d, "id", "") == naam for d in knoop.targets):
            return knoop.value
    raise AssertionError(f"{naam} staat niet in {pad}")


def test_de_importer_telt_dezelfde_rangtelwoorden():
    """De importer leest "derde lid" uit de ankertekst van een verwijzing; de agent en de api lezen dezelfde woorden
    met de lijst uit het bronmodel. Een spelling of volgorde die uiteenloopt, wijst een ander lid aan."""
    gedeeld = ast.literal_eval(_toekenning(TAAL, "RANGTELWOORDEN"))
    waarde = _toekenning(WORTEL / "tools" / "bwb-import" / "app" / "references.py", "_RANGTELWOORDEN")
    assert isinstance(waarde, ast.Call) and waarde.func.attr == "split"
    assert tuple(ast.literal_eval(waarde.func.value).split()) == gedeeld


def test_de_bron_iri_staat_een_keer_in_python():
    """De vorm van een bron-IRI (`urn:bwb:<BWB-id>…`) staat in `bronmodel.taal`; een nieuwe kopie loopt uiteen."""
    kopieen = [str(p.relative_to(WORTEL)) for map_ in ("api/app", "tools/graph-qa/agent", "packages/bronmodel/bronmodel")
               for p in (WORTEL / map_).rglob("*.py")
               if p != TAAL and r'urn:bwb:(BWB[RV]\d+)(?::[^<>' in p.read_text(encoding="utf-8")]
    assert kopieen == []


# Wat elke dienst uit zijn logregels haalt. Daarbovenop heeft elke dienst velden die alleen bij hem binnenkomen.
_KERN = {"authorization", "token", "bearer", "secret", "password", "api_key", "apikey"}
_EIGEN = {
    "api": {"chat_secret", "chatinput"},
    "graph-qa": {"question"},
    "frontend": {"chat_secret"},
}


def test_geheime_logvelden_lopen_niet_uiteen():
    """Drie kopieën (Python kan de TypeScript niet lezen en omgekeerd). De kern moet overal gelijk zijn; wat een dienst
    extra weglaat staat hierboven, zodat een verschil een keuze is en geen vergissing."""
    gevonden = {
        "api": ast.literal_eval(_toekenning(WORTEL / "api" / "app" / "observability.py", "GEHEIME_VELDEN")),
        "graph-qa": ast.literal_eval(_toekenning(WORTEL / "tools" / "graph-qa" / "agent" / "observability.py",
                                                 "GEHEIME_VELDEN")),
    }
    ts = (FRONTEND / "lib" / "logger.ts").read_text(encoding="utf-8")
    m = re.search(r"const GEHEIME_VELDEN = new Set\(\[(.*?)\]\)", ts, re.S)
    assert m, "GEHEIME_VELDEN staat niet meer in frontend/lib/logger.ts"
    gevonden["frontend"] = set(re.findall(r'"([^"]+)"', m.group(1)))
    assert gevonden == {dienst: _KERN | eigen for dienst, eigen in _EIGEN.items()}
