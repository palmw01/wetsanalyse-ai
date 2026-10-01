"""Deterministische kandidaatdetectie (ADR-001).

Een detector krijgt de tekst van één bronnode (plus eventueel zijn taalanalyse en de aanhef van
zijn ouder) en levert een `DetectorResult`: kandidaten met bewijs, of een zichtbare reden waarom hij
niet kon draaien. Een detector **classificeert niet**: hij zegt welke JAS-klassen mogelijk zijn,
volgens het detectieprofiel. Een latere stap beslist.

Twee soorten:

- **Regeldetectoren** (`regels.py` + `regels/*.yaml`): lexicale en juridische patronen, declaratief,
  elk met een regel-id, de JAS-herkomst en eigen testgevallen (positief, negatief, rand, overlap).
- **Structuurdetectoren** (`structuur.py`): waar de vorm van de bron het signaal is, zoals een
  begripsbepalingenartikel ('wordt verstaan onder:' + onderdelen).

Het **verwijzingsmasker** is geen detector van JAS-elementen maar een negatief patroon: een
nummer in "artikel 9, derde lid" is geen parameterwaarde, 'als bedoeld in' is geen voorwaarde.
Regels onderdrukken standaard wat binnen het masker valt (`niet_binnen`).
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable
from typing import Protocol

from bronmodel import Span, tekst_hash

from ..kandidaten import Candidate, DetectieBijdrage, DetectorResult
from ..taal import LinguisticAnalysis


@dataclass(frozen=True)
class BronTekst:
    """De eigen tekst van één bronnode, met wat een detector eromheen mag weten."""

    bron_iri: str
    tekst: str
    bron_hash: str
    analyse: LinguisticAnalysis | None = None
    context: str = ""          # de aanhef van de ouder, voor onderdelen van een opsomming

    @classmethod
    def van_tekst(cls, bron_iri: str, tekst: str, **kw) -> BronTekst:
        return cls(bron_iri, tekst, tekst_hash(tekst), **kw)

    def span(self, start: int, eind: int) -> Span:
        if not 0 <= start < eind <= len(self.tekst):
            raise ValueError(f"span {start}-{eind} valt buiten de bron")
        return Span(self.bron_iri, start, eind, self.tekst[start:eind], self.bron_hash)


class Detector(Protocol):
    naam: str
    versie: str

    def detecteer(self, bron: BronTekst) -> DetectorResult: ...


def resultaat(detector: Detector, bron: BronTekst, kandidaten: Iterable[Candidate] = (), *,
              bijdragen: Iterable[DetectieBijdrage] | None = None,
              overgeslagen: bool = False, reden: str = "") -> DetectorResult:
    """Eén constructie voor treffers, nul treffers en overslaan, inclusief ruwe herkomst."""
    ks = tuple(kandidaten)
    if overgeslagen and (ks or not reden):
        raise ValueError(f"{detector.naam}: overslaan vereist een reden en nul kandidaten")
    return DetectorResult(
        detector=detector.naam, versie=detector.versie, bron_iri=bron.bron_iri,
        kandidaten=ks, overgeslagen=overgeslagen, reden=reden,
        bijdragen=tuple(bijdragen) if bijdragen is not None else
        tuple(DetectieBijdrage.van(k, detector.naam, detector.versie) for k in ks))


def detecteer_alles(bron: BronTekst, detectoren: list[Detector] | None = None) -> list[DetectorResult]:
    """Draai alle detectoren. Geen fusie: dezelfde span kan uit meerdere resultaten komen."""
    if detectoren is None:
        detectoren = standaard_detectoren()
    uit = []
    for d in detectoren:
        r = d.detecteer(bron)
        if (r.detector, r.versie, r.bron_iri) != (d.naam, d.versie, bron.bron_iri):
            raise ValueError(f"detectorcontract: {d.naam}@{d.versie} leverde "
                             f"{r.detector}@{r.versie} voor {r.bron_iri}")
        if any((b.detector, b.versie) != (d.naam, d.versie) for b in r.bijdragen):
            raise ValueError(f"detectorcontract: onjuiste bijdrage-identiteit bij {d.naam}")
        if r.overgeslagen and (r.kandidaten or not r.reden or r.bijdragen):
            raise ValueError(f"detectorcontract: ongeldige overslag bij {d.naam}")
        if any(e.detector != d.naam for k in r.kandidaten for e in k.evidence):
            raise ValueError(f"detectorcontract: onjuiste bewijsidentiteit bij {d.naam}")
        uit.append(r)
    return uit


def kandidaten_van(resultaten: list[DetectorResult]) -> list[Candidate]:
    return [k for r in resultaten for k in r.kandidaten]


def standaard_detectoren() -> list[Detector]:
    from .functies import FunctieDetector
    from .regels import regeldetectoren
    from .structuur import BetekenisDetector, DefinitieDetector
    from .syntactisch import syntactische_detectoren
    return [*regeldetectoren(), DefinitieDetector(), BetekenisDetector(), *syntactische_detectoren(), FunctieDetector()]
