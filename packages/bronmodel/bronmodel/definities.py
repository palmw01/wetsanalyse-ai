"""Wat de wet over het bereik van haar definities zegt: de vaste formules van de Aanwijzingen voor de regelgeving.

Gedeeld door de begrippenketen van graph-qa (die werkt op IRI-prefixen) en de api (die de bronboom heeft en
daardoor ook "dit hoofdstuk" kan oplossen). Geen graafverkeer en geen modelbeslissingen.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_REGELING = re.compile(r"\b(?:deze|dit)\s+(?:wet|besluit|regeling|rijkswet)\b", re.IGNORECASE)
_ARTIKEL_HIER = re.compile(r"\b(?:in|voor de toepassing van)\s+dit\s+artikel\b", re.IGNORECASE)
_LID_HIER = re.compile(r"\bin\s+dit\s+lid\b", re.IGNORECASE)
_ARTIKEL_N = re.compile(r"\bvoor de toepassing van artikel\s+([0-9]+[a-z]*)\b", re.IGNORECASE)
_STRUCTUUR = re.compile(r"\b(?:dit|deze)\s+(hoofdstuk|afdeling|paragraaf|titel|titeldeel|onderdeel)\b",
                        re.IGNORECASE)


@dataclass(frozen=True)
class Geldigheid:
    soort: str                 # "regeling" | "artikel" | "artikel_n" | "lid" | "structuur" | "" (geen formule)
    formule: str = ""          # de herkende formule, voor de uitleg
    waarde: str = ""           # het artikelnummer bij "artikel_n", het woord ("hoofdstuk") bij "structuur"


def geldigheid_uit(tekst: str) -> Geldigheid:
    """De formule in deze tekst. Geen formule: soort leeg; een begripsbepaling geldt dan voor de hele regeling."""
    if m := _ARTIKEL_N.search(tekst):
        return Geldigheid("artikel_n", m.group(0), m.group(1))
    if m := _ARTIKEL_HIER.search(tekst):
        return Geldigheid("artikel", m.group(0))
    if m := _LID_HIER.search(tekst):
        return Geldigheid("lid", m.group(0))
    if m := _STRUCTUUR.search(tekst):
        return Geldigheid("structuur", m.group(0), m.group(1).lower())
    if m := _REGELING.search(tekst):
        return Geldigheid("regeling", m.group(0))
    return Geldigheid("")


def losse_termen(ruw: str) -> list[str]:
    """De termen in een opsomming, zoals de graaf ze als één begrip draagt: "directeur, inspecteur of ontvanger"
    → drie termen, met gewone spaties en hun eigen hoofdletters."""
    delen = re.split(r",\s*|\s+(?:of|en)\s+", ruw.strip())
    return [" ".join(d.split()) for d in delen if d.strip()]


def term_vindplaats(term: str, tekst: str) -> str:
    """Het letterlijke fragment waarin `term` in `tekst` staat, of "".

    Op woordgrens, zonder stamming: liever gemist dan verkeerd. Alleen de gewone meervoudsvormen van het laatste
    woord tellen mee, want het fragment staat erbij. Een term met een hoofdletter is een naam (Rijk ≠ rijk); bij
    de rest mag alleen de eerste letter afwijken, omdat die aan het begin van een zin staat."""
    if not term:
        return ""
    naam = any(c.isupper() for c in term)
    kop = re.escape(term[0]) if naam else f"[{re.escape(term[0].lower())}{re.escape(term[0].upper())}]"
    staart = re.escape(term[1:])
    vormen = ["en", "s", "n"]
    if len(term) > 2 and term[-1].isalpha() and term[-1] not in "aeiou" and term[-2] in "aeiou":
        vormen.append(re.escape(term[-1]) + "en")
    m = re.search(rf"(?<!\w){kop}{staart}(?:{'|'.join(vormen)})?(?!\w)", tekst)
    return m.group(0) if m else ""
