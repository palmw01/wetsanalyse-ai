"""Het register van de procesbrede toestand: caches en standen die een module voor het hele proces bewaart.

In productie is zo'n toestand bewust gedeeld (de citeertitels één keer per proces ophalen, de modelkeuze van de beheerder
onthouden). In de tests lekt hij van de ene test naar de volgende, en dan hangt een uitkomst af van de volgorde. Zo was
`test_sjablonen` alleen groen als `overzicht._REGELINGEN_CACHE` leeg was, en rood na `test_eval` (Lex Bench §14.1).

Een module met zo'n toestand meldt hier een functie die hem leegmaakt (`registreer`). `tests/conftest.py` roept `reset`
voor en na elke test aan. `tests/test_procestoestand.py` zoekt in `agent/` naar toestand die een functie wijzigt, en
eist dat zijn module zich hier gemeld heeft: een nieuwe cache kan dus niet stil lekken.
"""
from __future__ import annotations

from collections.abc import Callable

_RESETS: dict[str, Callable[[], None]] = {}


def registreer(module: str, leeg: Callable[[], None]) -> None:
    """Meld de functie die de procesbrede toestand van `module` leegmaakt. Een tweede melding vervangt de eerste."""
    _RESETS[module] = leeg


def gemeld() -> frozenset[str]:
    """De modules die zich gemeld hebben."""
    return frozenset(_RESETS)


def reset() -> None:
    """Maak alle gemelde toestand leeg (voor tests)."""
    for leeg in _RESETS.values():
        leeg()
