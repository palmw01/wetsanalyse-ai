"""De contenttoets: content toetsen op juistheid en volledigheid tegen de bron (plan docs/architectuur/plan-contenttoets.md).

De vaste woorden van de toets, gedeeld door graph-qa, de api en de werkplek (`frontend/lib/contenttoets.ts` is de spiegel,
`contenttoets.test.ts` leest dit bestand). De methode zelf staat in de skill `.claude/skills/contenttoets/`: de criteria
hieronder zijn daar uitgewerkt (`references/criteria.md`), met een herkenningsvraag en een voorbeeld per criterium.

Het blok zelf (`Contenttoets`) staat in `antwoord.py`, naast de andere blokken van een antwoord.
"""
from __future__ import annotations

from typing import Literal

#: De oordelen per bewering, een gesloten lijst. "Mogelijk onjuist": Lex stelt voor, de mens beslist.
Oordeel = Literal["juist", "mogelijk_onjuist", "onvolledig", "niet_in_de_bron"]
OORDELEN: tuple[str, ...] = ("mogelijk_onjuist", "onvolledig", "niet_in_de_bron", "juist")

#: Het oordeel in woorden, enkelvoud (label) en in een telling.
OORDEEL_LABEL: dict[str, str] = {
    "juist": "Juist", "mogelijk_onjuist": "Mogelijk onjuist", "onvolledig": "Onvolledig",
    "niet_in_de_bron": "Niet in de bron",
}
OORDEEL_TELLING: dict[str, str] = {
    "mogelijk_onjuist": "mogelijk onjuist", "onvolledig": "onvolledig", "niet_in_de_bron": "niet in de bron",
    "juist": "juist",
}

#: De criteria uit de skill (`references/criteria.md`). J: juistheid, V: volledigheid.
CRITERIA: dict[str, str] = {
    "J1": "Waarde",
    "J2": "Voorwaarde en uitzondering",
    "J3": "Reikwijdte",
    "J4": "Modaliteit",
    "J5": "Telmoment",
    "J6": "Samenhang",
    "J7": "Geldigheid",
    "V1": "Voorwaarde ontbreekt",
    "V2": "Gevolg ontbreekt",
    "V3": "Uitzondering ontbreekt",
}

#: Welke criteria bij een oordeel horen. Bij "juist" en "niet in de bron" is het criterium leeg of een J-criterium.
CRITERIA_BIJ: dict[str, tuple[str, ...]] = {
    "mogelijk_onjuist": tuple(c for c in CRITERIA if c.startswith("J")),
    "onvolledig": tuple(CRITERIA),
    "juist": ("", *(c for c in CRITERIA if c.startswith("J"))),
    "niet_in_de_bron": ("", *(c for c in CRITERIA if c.startswith("J"))),
}

#: Een oordeel dat op een letterlijke passage uit de bron rust. "Niet in de bron" rust nergens op: daar zegt de
#: toelichting wat er gezocht is.
MET_BRON: frozenset[str] = frozenset({"juist", "mogelijk_onjuist", "onvolledig"})


def criterium_tekst(code: str) -> str:
    """"J1 Waarde"; leeg bij geen criterium."""
    return f"{code} {CRITERIA[code]}" if code in CRITERIA else ""


def telling_tekst(aantallen: dict[str, int], ontbreekt: int = 0) -> str:
    """"11 beweringen: 3 mogelijk onjuist, 2 onvolledig, 2 niet in de bron, 4 juist. 1 punt ontbreekt." De werkplek zegt
    hetzelfde (`tellingTekst` in `lib/contenttoets.ts`)."""
    totaal = sum(aantallen.get(o, 0) for o in OORDELEN)
    delen = [f"{aantallen[o]} {OORDEEL_TELLING[o]}" for o in OORDELEN if aantallen.get(o)]
    zin = f"{totaal} {'bewering' if totaal == 1 else 'beweringen'}" + (f": {', '.join(delen)}." if delen else ".")
    if ontbreekt:
        zin += f" {ontbreekt} {'punt ontbreekt' if ontbreekt == 1 else 'punten ontbreken'}."
    return zin


# ── Het oordeel van de redacteur of de jurist (C7) ──────────────────────────────────────────────────────────────────
# Lex stelt voor; de mens beoordeelt. Per bevinding twee vragen: klopt het oordeel van Lex (eens, oneens), en wat
# gebeurt er met het voorstel (overgenomen, aangepast, afgewezen). Bewaard op het bericht (api `toetsbesluiten`), want
# de toets zelf bestaat alleen daar. De werkplek spiegelt deze waarden in `lib/contenttoets.ts`.

#: Klopt het oordeel van Lex?
TOETSOORDELEN: tuple[str, ...] = ("eens", "oneens")

#: Wat er met het voorstel gebeurt. "Aangepast" draagt de tekst die de redacteur ervan maakte.
VOORSTELBESLUITEN: tuple[str, ...] = ("overgenomen", "aangepast", "afgewezen")

TOETSOORDEEL_LABEL: dict[str, str] = {
    "eens": "Eens",
    "oneens": "Oneens",
}

VOORSTELBESLUIT_LABEL: dict[str, str] = {
    "overgenomen": "Overgenomen",
    "aangepast": "Aangepast",
    "afgewezen": "Afgewezen",
}
