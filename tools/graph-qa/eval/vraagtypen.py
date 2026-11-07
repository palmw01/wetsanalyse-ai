"""Vraagtypen in de eval-sets: de as waarlangs de kwaliteitsnulmeting wordt gelezen.

Eén slagingspercentage over de hele set zegt niet wáár Lex zwak is. Elke QA-case en elke gespreksbeurt draagt
daarom een `vraagtype` uit deze vaste lijst (een gesprek mag een default per scenario geven). De rapporten tonen
per type het aantal, het slagingspercentage en de toonovertredingen, en een dekkingsoverzicht met de types die te
weinig cases hebben om iets over te zeggen.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

VRAAGTYPEN: tuple[str, ...] = (
    "begrip",          # wat betekent een begrip, waar staat de definitie
    "bepaling",        # wat staat er in een aangewezen artikel of lid
    "duiding",         # waarom, hoe verhoudt het zich, wat betekent dit voor
    "feit",            # vrije feitvraag over de graaf of een regeling
    "overzicht",       # welke bepalingen gaan over een onderwerp
    "annotatie",       # annoteren
    "annotatievraag",  # een vraag óver bestaande annotaties
    "vervolg",         # een vervolgvraag die op de vorige beurt leunt
    "agent",           # een taak voor een agent op een werkgebied
    "verduidelijken",  # de vraag is dubbelzinnig: Lex moet doorvragen
    "afwijzing",       # buiten de wet- en regelgeving
)

#: Onder dit aantal cases is een percentage per type geen uitspraak. Zichtbaar, geen fout.
MIN_CASES = 5


def vraagtype_van(case: dict[str, Any], beurt: dict[str, Any] | None = None) -> str:
    """Het type van een QA-case, of van een beurt (met de default van het gesprek)."""
    return str((beurt or {}).get("vraagtype") or case.get("vraagtype") or "")


def dekking(typen: Iterable[str]) -> dict[str, int]:
    """Aantal cases per type, in de volgorde van `VRAAGTYPEN`, ook de types zonder cases."""
    lijst = list(typen)
    return {t: lijst.count(t) for t in VRAAGTYPEN}


def dekking_regel(typen: Iterable[str]) -> str:
    d = dekking(typen)
    onder = [t for t, n in d.items() if n < MIN_CASES]
    return ("Dekking: " + ", ".join(f"{t} {n}" for t, n in d.items() if n)
            + (f"\n  onder de {MIN_CASES}: {', '.join(onder)}" if onder else ""))


def print_per_vraagtype(rijen: Iterable[tuple[str, bool, int, float]]) -> None:
    """Per type: aantal, geslaagd, toonovertredingen en het gemiddelde aandeel lange zinnen. De toon staat los
    van het slaagcriterium.

    `rijen` is per case of beurt (vraagtype, geslaagd, toonovertredingen, aandeel lange zinnen)."""
    rijen = list(rijen)
    per: dict[str, list[tuple[bool, int, float]]] = {}
    for t, ok, toon, lang in rijen:
        per.setdefault(t or "?", []).append((ok, toon, lang))
    print(f"\n{'vraagtype':16} {'n':>3} {'geslaagd':>9} {'toon':>5} {'lang':>5}")
    for t in [*VRAAGTYPEN, "?"]:
        if v := per.get(t):
            print(f"{t:16} {len(v):3d} {sum(x[0] for x in v) / len(v):9.0%} {sum(x[1] for x in v):5d} "
                  f"{sum(x[2] for x in v) / len(v):5.0%}")
    print(dekking_regel(r[0] for r in rijen))
