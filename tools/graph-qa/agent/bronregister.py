"""Wat Lex eerder in dit gesprek letterlijk uit de graaf ophaalde, als bewijs voor een vervolgantwoord.

De brongetrouwheidscontrole toetste alleen tegen de trace van de huidige beurt. Een vervolgantwoord
dat een vindplaats of citaat uit het vorige antwoord herhaalde, zonder het opnieuw op te halen, werd
`ongegrond`; de correctieronde haalde de verwijzingen er dan uit. Doorvragen kostte zo juist de
onderbouwing.

Het register bewaart over beurten heen de tool-resultaten zelf – wettekst zoals de graaf hem
teruggaf, nooit modeltekst – zodat dezelfde toets ("staat dit letterlijk in wat er is opgehaald?")
ook geldt voor wat eerder in het gesprek is opgehaald. Annotatieresultaten tellen niet: een
annotatie is geen vindplaats (zie `grounding.check_grounding`).
"""
from __future__ import annotations

import hashlib
from typing import Any

from .tools.annotatie_tools import ANNOTATIE_TOOL_NAMEN

MAX_ITEMS = 24
MAX_TEKENS = 60_000


def _sleutel(tekst: str) -> str:
    return hashlib.sha256(tekst.encode("utf-8")).hexdigest()[:16]


def bij(register: list[Any] | None, trace: list[Any] | None) -> list[list[str]]:
    """Het register na deze beurt: de bruikbare resultaten erbij, ontdubbeld, en begrensd op de
    nieuwste `MAX_ITEMS` en `MAX_TEKENS` (de checkpoint moet klein blijven)."""
    uit = [[str(n), str(t)] for n, t in (register or [])]
    gezien = {_sleutel(t) for _, t in uit}
    for naam, tekst in trace or []:
        tekst = str(tekst or "")
        if (not tekst.strip() or naam in ANNOTATIE_TOOL_NAMEN or tekst.startswith("Fout bij tool")
                or _sleutel(tekst) in gezien):
            continue
        gezien.add(_sleutel(tekst))
        uit.append([str(naam), tekst])
    uit = uit[-MAX_ITEMS:]
    while len(uit) > 1 and sum(len(t) for _, t in uit) > MAX_TEKENS:
        uit.pop(0)
    return uit


def controletrace(state: dict[str, Any]) -> list[tuple[str, str]]:
    """Waartegen een antwoord getoetst wordt: eerst wat eerder is opgehaald, dan deze beurt."""
    return [(n, t) for n, t in state.get("bronregister") or []] + list(state.get("source_trace") or [])
