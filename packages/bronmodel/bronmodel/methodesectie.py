"""Methodesecties in een skill (ADR-014): de tekst tussen `<!-- methode:<id>:begin -->` en `<!-- methode:<id>:end -->`.

De validator voor de generator van het methodepakket (`tools/graph-qa/scripts/genereer_methodepakket.py`) en voor de
skills van de werkplaats (`bronmodel.skill`).
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
