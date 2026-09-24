"""Dekkingsboekhouding (ADR-001 PR 10, opdracht §22): twee maten, en uitdrukkelijk geen derde.

- **A – kandidaatverwerking**: elke kandidaat eindigt als ACCEPTED, REJECTED, UNCERTAIN of
  HUMAN_REVIEW. `UNHANDLED = 0` is een invariant, geen streefwaarde: een kandidaat zonder
  beslissing is een fout in de keten, en `controleer_a` gooit dan.
- **B – structurele dekking**: per bronnode welke van de twaalf detectiedimensies zijn uitgevoerd,
  gedeeltelijk (een deel van de detectoren sloeg zich over) of overgeslagen – plus welke zinnen en
  bijzinnen géén enkele kandidaat opleverden. Dat laatste is het zichtbare vangnet voor gemiste
  elementen; het vervangt de generatieve 'ontbrekend'-lijst van de legacy-Critic.

Wat hier níét staat is **annotation recall** (C): hoeveel echte elementen er gevonden zijn, kan
alleen tegen een vastgestelde referentie (`eval/metrieken.py`, status adjudicated/gold). 100% A en
100% B zeggen daar niets over.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from .besluit import Beslissing
from .fusie import Fusie
from .kandidaten import CandidateStatus
from .taal import bijzinnen

# Detectiedimensie → de detectoren die haar dragen (opdracht §22B).
DIMENSIES: dict[str, tuple[str, ...]] = {
    "actor": ("naamwoordgroep", "subject"),
    "object": ("naamwoordgroep",),
    "normatieve relatie": ("norm",),
    "handeling/gebeurtenis": ("nominalisatie",),
    "voorwaarde": ("voorwaarde", "bijzin", "betekenis"),
    "berekening/afleiding": ("afleiding",),
    "waarde": ("numeriek", "naamwoordgroep"),
    "operator": ("operator", "logisch"),
    "tijd": ("tijd",),
    "plaats": ("plaats",),
    "delegatie": ("delegatie",),
    "definitie": ("definitie",),
}


class DekkingsFout(RuntimeError):
    """Een kandidaat kwam zonder beslissing uit de keten (UNHANDLED > 0)."""


def controleer_a(fusie: Fusie, beslissingen: list[Beslissing]) -> dict[str, int]:
    besloten = {b.kandidaat_id for b in beslissingen}
    zonder = [k.label for k in fusie.kandidaten if k.id not in besloten]
    if zonder:
        raise DekkingsFout(f"kandidaten zonder beslissing: {', '.join(zonder[:10])}")
    telling = Counter(b.status.value for b in beslissingen)
    return {s.value: telling.get(s.value, 0) for s in CandidateStatus}


def structureel(fusie: Fusie, bronnen: list[Any], gedraaid: dict[str, set[str]]) -> dict[str, Any]:
    """B per bronnode. `gedraaid[bron_iri]` = namen van de detectoren die daar werkelijk draaiden."""
    overgeslagen: dict[str, set[str]] = {}
    for o in fusie.overgeslagen:
        overgeslagen.setdefault(o.bron_iri, set()).add(o.detector)
    per_bron = {}
    for bron in bronnen:
        ran, skip = gedraaid.get(bron.bron_iri, set()), overgeslagen.get(bron.bron_iri, set())
        dims = {}
        for dim, detectoren in DIMENSIES.items():
            ok = [d for d in detectoren if d in ran and d not in skip]
            dims[dim] = "uitgevoerd" if len(ok) == len(detectoren) else ("gedeeltelijk" if ok else "overgeslagen")
        per_bron[bron.bron_iri] = {"dimensies": dims, "ongedekt": ongedekt(fusie, bron)}
    return per_bron


def ongedekt(fusie: Fusie, bron: Any) -> list[str]:
    """Zinnen en bijzinnen van deze bron waar geen enkele kandidaat mee overlapt."""
    spans = [(k.span.start, k.span.eind) for k in fusie.kandidaten if k.span.bron_iri == bron.bron_iri]

    def raak(s: int, e: int) -> bool:
        return any(ks < e and s < ke for ks, ke in spans)
    delen: list[tuple[int, int]] = []
    if bron.analyse is not None:
        delen += [(z.start, z.eind) for z in bron.analyse.zinnen]
        delen += [(c.start, c.eind) for c in bijzinnen(bron.analyse)]
    uit = []
    for s, e in sorted(set(delen)):
        if not raak(s, e) and bron.tekst[s:e].strip(" .,;:"):
            uit.append(bron.tekst[s:e])
    return uit
