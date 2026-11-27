"""De vorm van een named graph, getoetst tegen SHACL-shapes: `shapes/bwb-graaf.ttl` voor een wet,
`shapes/kennisgroepen.ttl` voor de index van de kennisgroepstandpunten (`app/kennisgroepen.py`).

De T-Box (`app/ontology.py`) zegt welke klassen en eigenschappen er zijn; de shapes zeggen wat een node van elke
klasse moet en mag hebben. De importer toetst elke graph vóór de PUT, net als de dekking: een PUT vervangt de hele
named graph, dus een controle erna kan niets meer tegenhouden (`dekking.poortbesluit`).

Getoetst wordt per named graph zonder inferentie, zoals hij geschreven wordt. Zonder pyshacl geeft `toets` None:
de import valt nooit om op het ontbreken van een meetinstrument, maar het overzicht zegt dan dat er niet getoetst is.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from rdflib import RDF, Graph, Namespace

SHAPES = Path(__file__).parent / "shapes" / "bwb-graaf.ttl"
KENNISGROEPEN_SHAPES = Path(__file__).parent / "shapes" / "kennisgroepen.ttl"
SH = Namespace("http://www.w3.org/ns/shacl#")


@dataclass(frozen=True)
class Vormtoets:
    """Uitslag van één graph: het aantal afwijkingen en per soort (pad, constraint) een voorbeeld."""

    afwijkingen: int
    soorten: dict[tuple[str, str], tuple[int, str]] = field(default_factory=dict)

    @property
    def conform(self) -> bool:
        return self.afwijkingen == 0

    def regel(self) -> str:
        delen = [
            f"{pad} {constraint} ×{n} (bv. {focus})"
            for (pad, constraint), (n, focus) in self.soorten.items()
        ]
        return f"{self.afwijkingen} vormfout(en): " + "; ".join(delen[:5])


@cache
def shapes(pad: Path = SHAPES) -> Graph:
    return Graph().parse(pad, format="turtle")


def toets(graph: Graph, pad: Path = SHAPES) -> Vormtoets | None:
    try:
        from pyshacl import validate
    except ImportError:
        return None
    _conform, rapport, _tekst = validate(
        graph, shacl_graph=shapes(pad), inference="none", advanced=True
    )
    teller: Counter[tuple[str, str]] = Counter()
    voorbeeld: dict[tuple[str, str], str] = {}
    for r in rapport.subjects(RDF.type, SH.ValidationResult):
        pad = str(rapport.value(r, SH.resultPath) or "")
        constraint = str(rapport.value(r, SH.sourceConstraintComponent) or "").removeprefix(str(SH))
        sleutel = (pad, constraint)
        teller[sleutel] += 1
        voorbeeld.setdefault(sleutel, str(rapport.value(r, SH.focusNode)))
    return Vormtoets(
        afwijkingen=sum(teller.values()),
        soorten={k: (n, voorbeeld[k]) for k, n in teller.most_common()},
    )
