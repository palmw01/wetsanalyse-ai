"""Welke bronconnectors een beurt aanbiedt: alleen die de vraag of het gesprek noemt (ronde 6, 12 nov 2026).

Elke aangezette connector kost per modelronde ~2k tokens aan toolschema's en een regel in BRONNEN IN DEZE BEURT, ook als
de vraag maar over één bron gaat (Staatsblad ronde 5: +7k per leesbeurt met alle vier aan). De keuze is in code, zonder
model, en generiek: een bron telt als genoemd als zijn beschrijving haar herkent (`ConnectorBeschrijving.herkent`: de
signaalwoorden, een id van zijn soort) of een van zijn `organen` noemt. Een regeling die niet bij naam in de graaf staat
(`buiten_graaf.noemt_regeling_buiten_graaf`) neemt wetgeving buiten de kennisgraaf erbij, maar beperkt alleen niet.

- Noemt de vraag een of meer bronnen die aanstaan, dan krijgen alleen die hun tools.
- Noemt de vraag geen bron, dan houdt een vervolgvraag de keuze van het gesprek (`State.bronkeuze`); zonder keuze blijft
  alles aan wat aanstaat, zoals voorheen.
- Wat zo buiten de beurt valt, krijgt in de bronstand de reden `vraag`: het event en het promptblok zeggen eerlijk wat er
  deze beurt aanstaat, en waarom niet. De jurist zet hem er weer bij door hem in de vraag te noemen.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from bronmodel.connectors import CONNECTORS, herkende

#: De connector die een regeling buiten de kennisgraaf leest (geen signaalwoord: elke wetsnaam zou er een zijn).
BUITEN_GRAAF = "wetgeving_live"


_WOORD = re.compile(r"[\w-]+")


def _woorden(tekst: str) -> str:
    return " " + " ".join(_WOORD.findall((tekst or "").casefold())) + " "


def _organen(tekst: str) -> set[str]:
    """De connectors waarvan de tekst een orgaan noemt (`ConnectorBeschrijving.organen`: "de Eerste Kamer", "de Hoge
    Raad", "het Ministerie van Financiën"), als hele woordgroep."""
    woorden = _woorden(tekst)
    return {n for n, c in CONNECTORS.items() if any(_woorden(o) in woorden for o in c.organen if o.strip())}


def genoemd(teksten: Iterable[str], *, buiten_graaf: bool = False) -> set[str]:
    """De connectors die deze teksten noemen: een signaal of id (`herkende`), of een orgaan. Een regeling buiten de
    kennisgraaf (`buiten_graaf`) neemt wetgeving buiten de graaf erbij, maar beperkt alleen niet: een wet die de graaf
    niet kent, kan net zo goed over haar publicatie of haar wetsgeschiedenis gaan (Staatsblad ronde 5, B23: "Wat verandert
    de Wet Overige fiscale maatregelen 2025 aan de Invorderingswet 1990?")."""
    uit = {n for t in teksten if t for n in (*herkende(t), *_organen(t))}
    return uit | ({BUITEN_GRAAF} if buiten_graaf and uit else set())


def kies(stand: dict[str, dict[str, Any]], genoemde: set[str],
         vorige: list[str] | None) -> tuple[dict[str, dict[str, Any]], list[str] | None]:
    """(de bronstand van deze beurt, de keuze van het gesprek). De keuze is None als er niets te kiezen valt: dan blijft
    alles aan wat aanstaat. Een bron die uit stond, gaat hier nooit aan."""
    aan = [n for n, s in stand.items() if s.get("aan")]
    keuze = [n for n in aan if n in genoemde] or [n for n in aan if n in (vorige or [])]
    if not keuze:
        return stand, (vorige if not genoemde else None)
    if len(keuze) == len(aan):
        return stand, keuze
    return {n: ({**s, "aan": False, "reden": "vraag"} if n in aan and n not in keuze else s)
            for n, s in stand.items()}, keuze


def actief(stand: dict[str, dict[str, Any]]) -> list[str]:
    return [n for n, s in stand.items() if s.get("aan")]
