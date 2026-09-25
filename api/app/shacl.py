"""SHACL-diagnose van de v2-projectie (ADR-001 PR 14). Niet-blokkerend.

`valideer(graph)` toetst een geprojecteerde laag tegen `shapes/jas-v2.ttl` en splitst de
bevindingen naar niveau: `rdf` (structureel geldige RDF) en `jas_model` (structureel geldig
JAS-model). Een derde niveau – juridisch juist – bestaat hier bewust niet: dat oordeel is aan de
jurist, niet aan een shape.

pyshacl is sinds de graafcontrole (`app/graafcontrole.py`) een runtime-afhankelijkheid, maar de shapes
blijven niet-blokkerend: ze draaien nooit in het schrijfpad. Zonder pyshacl geeft `valideer`
`beschikbaar: False` terug in plaats van te falen: de projectie mag nooit op een diagnose-instrument
omvallen.
"""
from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

from rdflib import Graph, Namespace, URIRef

SHAPES = Path(__file__).parent / "shapes" / "jas-v2.ttl"
SH = Namespace("http://www.w3.org/ns/shacl#")
JASV = Namespace("urn:jas-ns:validatie:")
_NIVEAU = {JASV.RdfStructuur: "rdf", JASV.JasModel: "jas_model"}


@cache
def shapes() -> Graph:
    return Graph().parse(SHAPES, format="turtle")


def _niveau(rapport: Graph, resultaat: Any) -> str:
    bron = rapport.value(resultaat, SH.sourceShape)
    groep = shapes().value(bron, SH.group) if bron is not None else None
    if groep in _NIVEAU:
        return _NIVEAU[groep]
    # sh:sparql-constraints en node-shapes zonder groep: het schone-wettekst-invariant is JAS-model.
    return "jas_model" if rapport.value(resultaat, SH.sourceConstraintComponent) == SH.SPARQLConstraintComponent else "rdf"


def valideer(graph: Graph) -> dict[str, Any]:
    try:
        from pyshacl import validate
    except ImportError:
        return {"beschikbaar": False, "conform": None, "rdf": [], "jas_model": []}
    conform, rapport, _tekst = validate(graph, shacl_graph=shapes(), advanced=True, inference="none")
    uit: dict[str, Any] = {"beschikbaar": True, "conform": bool(conform), "rdf": [], "jas_model": []}
    for r in rapport.subjects(URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), SH.ValidationResult):
        uit[_niveau(rapport, r)].append({
            "focus": str(rapport.value(r, SH.focusNode)),
            "pad": str(rapport.value(r, SH.resultPath) or ""),
            "melding": str(rapport.value(r, SH.resultMessage) or ""),
        })
    return uit
