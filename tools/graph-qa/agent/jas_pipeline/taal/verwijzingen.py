"""Gedeelde lexicale verwijzingsherkenning; geen kandidaat- of splitsingsbeleid.

De detector-maskers kiezen welke treffers kandidaten onderdrukken. De grensanalyse
beschermt uitsluitend leestekens binnen dezelfde treffers. Slotinterpunctie hoort
nooit bij een artikelnummer: `artikel 9.1.` houdt dus zijn echte zinseinde.
"""
import re

VERSIE = "2"  # ook samengestelde artikelnummers met punten
RANGTELWOORD = (
    r"(?:eerste|tweede|derde|vierde|vijfde|zesde|zevende|achtste|negende|tiende|"
    r"elfde|twaalfde|\d+e|vorige|volgende|voorgaande|laatste)"
)
PATRONEN = {
    "artikel": re.compile(
        r"\b(?:artikel|artikelen|art\.)\s+\d+[a-z]*(?:[.:]\d+[a-z]*)*"
        rf"(?:,\s*(?:het\s+)?{RANGTELWOORD}\s+lid)?"
        r"(?:,\s*onderdeel\s+[a-z0-9]+°?)?", re.IGNORECASE),
    "lid": re.compile(rf"\b(?:het\s+|dit\s+)?{RANGTELWOORD}\s+(?:lid|leden)\b", re.IGNORECASE),
    "bedoeld": re.compile(r"\b(?:als\s+)?bedoeld\s+in\b", re.IGNORECASE),
}


def verwijzingen(tekst: str) -> tuple[tuple[int, int, str], ...]:
    return tuple(sorted((m.start(), m.end(), naam)
                        for naam, patroon in PATRONEN.items() for m in patroon.finditer(tekst)))
