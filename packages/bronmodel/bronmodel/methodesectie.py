"""Methodesecties in een skill (ADR-014): de tekst tussen `<!-- methode:<id>:begin -->` en `<!-- methode:<id>:end -->`.

Eén validator voor de generator van het methodepakket (`tools/graph-qa/scripts/genereer_methodepakket.py`) en voor
een wijzigingsvoorstel vanuit de werkplek (`api/app/catalogus_voorstel.py`). Zo landt een voorstel dat de api
accepteert ook in de generator, en weigert de api wat de generator zou weigeren.
"""
from __future__ import annotations

import re

SECTIE_ID = re.compile(r"[a-z][a-z-]*")
#: Een sectie is kort: ze gaat letterlijk in een systeemprompt.
MAX_TEKENS = 6000


class SectieFout(ValueError):
    """Een sectie die niet (eenduidig) te lezen of te vervangen is."""


def _markers(sectie: str) -> tuple[str, str]:
    if not SECTIE_ID.fullmatch(sectie):
        raise SectieFout(f"ongeldig sectie-ID: {sectie}")
    return f"<!-- methode:{sectie}:begin -->", f"<!-- methode:{sectie}:end -->"


def lees_sectie(tekst: str, sectie: str) -> str:
    """De tekst van de sectie, zonder witruimte eromheen. Precies één begin- en eindmarker, in die volgorde."""
    start, einde = _markers(sectie)
    if tekst.count(start) != 1 or tekst.count(einde) != 1:
        raise SectieFout(f"ontbrekende of dubbele sectie: {sectie}")
    if tekst.index(einde) < tekst.index(start):
        raise SectieFout(f"omgekeerde sectie: {sectie}")
    inhoud = tekst.split(start)[1].split(einde)[0].strip()
    if not inhoud:
        raise SectieFout(f"lege sectie: {sectie}")
    return inhoud


def toets_nieuwe_tekst(nieuw: str) -> str:
    """De nieuwe tekst van een sectie: niet leeg, binnen de grens, en zonder markers (die zouden de bestandsvorm breken)."""
    nieuw = (nieuw or "").strip()
    if not nieuw:
        raise SectieFout("de nieuwe tekst is leeg")
    if len(nieuw) > MAX_TEKENS:
        raise SectieFout(f"de nieuwe tekst is langer dan {MAX_TEKENS} tekens")
    if "<!--" in nieuw or "-->" in nieuw:
        raise SectieFout("de nieuwe tekst bevat een HTML-commentaar of marker")
    return nieuw


def vervang_sectie(tekst: str, sectie: str, nieuw: str) -> str:
    """Het bestand met de sectie vervangen door `nieuw`; de rest blijft byte-gelijk. Weigert wat `lees_sectie` weigert."""
    lees_sectie(tekst, sectie)
    nieuw = toets_nieuwe_tekst(nieuw)
    start, einde = _markers(sectie)
    voor, rest = tekst.split(start)
    _, na = rest.split(einde)
    return f"{voor}{start}\n{nieuw}\n{einde}{na}"
