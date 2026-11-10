"""Termijnen, bedragen, percentages en datums in vrije tekst, om ze tegen de opgehaalde tekst te toetsen (R4a).

De controle toetste vindplaatsen en citaten, niet wat de uitleg beweert. Op acceptatie schreef Lex "inwerkingtredingsdatum:
1 oktober 2026" zonder bron, en in een toelichting een termijn die nergens stond. Een getal met een eenheid en een datum
zijn het deel van zo'n bewering dat de code zonder model kan nalopen: staat "zes weken" of "1 oktober 2026" ook in wat er
is opgehaald? Een kaal getal ("22 leden", "artikel 9") niet: dat is een telling of een vindplaats, met een eigen toets.

Geschreven en cijfermatige getallen zijn gelijk ("zes weken" = "6 weken"), en een eenheid telt in enkelvoud en meervoud.
"""
from __future__ import annotations

import re

_TELWOORDEN = {
    "een": 1, "één": 1, "twee": 2, "drie": 3, "vier": 4, "vijf": 5, "zes": 6, "zeven": 7, "acht": 8, "negen": 9,
    "tien": 10, "elf": 11, "twaalf": 12, "dertien": 13, "veertien": 14, "vijftien": 15, "zestien": 16, "zeventien": 17,
    "achttien": 18, "negentien": 19, "twintig": 20, "dertig": 30, "veertig": 40, "vijftig": 50, "zestig": 60,
    "zeventig": 70, "tachtig": 80, "negentig": 90, "honderd": 100, "duizend": 1000,
}
_EENHEDEN = {
    "dag": "dag", "dagen": "dag", "werkdag": "werkdag", "werkdagen": "werkdag", "week": "week", "weken": "week",
    "maand": "maand", "maanden": "maand", "jaar": "jaar", "jaren": "jaar", "uur": "uur", "uren": "uur",
    "procent": "procent", "%": "procent", "euro": "euro",
}
_MAANDEN = ("januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
            "november", "december")

_GETAL = r"\d+(?:[.,]\d+)?|" + "|".join(sorted(_TELWOORDEN, key=len, reverse=True))
_EENHEID = "|".join(sorted((re.escape(e) for e in _EENHEDEN), key=len, reverse=True))
_HOEVEELHEID = re.compile(rf"(?<![\w€])(?:€\s*(?P<bedrag>\d+(?:[.,]\d+)*)|(?P<getal>{_GETAL})\s*(?P<eenheid>{_EENHEID}))(?![\w])",
                          re.IGNORECASE)
_DATUM = re.compile(rf"(?<!\d)(\d{{1,2}})\s+({'|'.join(_MAANDEN)})\s+(\d{{4}})(?!\d)", re.IGNORECASE)
#: Een datum zoals een bron hem levert ("2024-10-31", de metadata van een Kamerstuk): dezelfde datum als "31 oktober 2024".
#: Zonder dit telde een datum uit een zoekresultaat als onbevestigd (gesprek e906567a, 9 nov 2026).
_ISO_DATUM = re.compile(r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?![\d-])")


def _getal(woord: str) -> str:
    woord = woord.casefold()
    if woord in _TELWOORDEN:
        return str(_TELWOORDEN[woord])
    return woord.replace(".", "").replace(",", ".")


def hoeveelheden(tekst: str) -> set[str]:
    """De termijnen, bedragen, percentages en datums in de tekst, genormaliseerd ("6 week", "100 euro", "1 oktober 2026")."""
    uit: set[str] = set()
    for m in _HOEVEELHEID.finditer(tekst or ""):
        if m.group("bedrag"):
            uit.add(f"{_getal(m.group('bedrag'))} euro")
        else:
            uit.add(f"{_getal(m.group('getal'))} {_EENHEDEN[m.group('eenheid').casefold()]}")
    for dag, maand, jaar in _DATUM.findall(tekst or ""):
        uit.add(f"{int(dag)} {maand.casefold()} {jaar}")
    for jaar, maand, dag in _ISO_DATUM.findall(tekst or ""):
        if 1 <= int(maand) <= 12 and 1 <= int(dag) <= 31:
            uit.add(f"{int(dag)} {_MAANDEN[int(maand) - 1]} {jaar}")
    return uit


def buiten(tekst: str, bron: str) -> list[str]:
    """Wat de tekst aan termijnen, bedragen en datums noemt dat de bron niet noemt, in vaste volgorde."""
    return sorted(hoeveelheden(tekst) - hoeveelheden(bron))
