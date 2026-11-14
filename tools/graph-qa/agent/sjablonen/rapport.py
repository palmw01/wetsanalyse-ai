"""Het rapport: de ene uitgang van een subagent (ADR-016 §A4).

Een subagent rondt zijn opdracht af met deze tool, nooit in tekst. Het rapport zegt wat hij deed, wat hij vond en wat
niet lukte. Wat hij vond, draagt hetzelfde onderbouwingscontract als een uitleg (`duiding.py`, ADR-008): het model wijst
passages aan met hun eerste en laatste woorden, de code neemt de tekst uit wat de tools teruggaven. Zo toetst de code
het rapport zoals elk antwoord, en krijgt de centrale agent alleen citaten uit de bron.

`status` is `klaar` of `niet_gelukt`. Een vraag naar boven (`vraag`) komt met stap A4. Bij `niet_gelukt` hoeft er geen
passage te zijn: dan zegt het rapport wat er wel en niet lukte.
"""
from __future__ import annotations

from typing import Any

from bronmodel.antwoord import Antwoord, Toelichting

from . import duiding
from .vullen import Onvulbaar, Trace

NAAM = "rapport"
STATUS = ("klaar", "niet_gelukt")

_ONDERBOUWING = duiding.SCHEMA["input_schema"]["properties"]["onderbouwing"]

SCHEMA: dict[str, Any] = {
    "name": NAAM,
    "description": (
        "Rond je opdracht af met dit rapport, als laatste stap en zonder tekst ernaast. Het rapport gaat naar de agent die "
        "je de opdracht gaf, niet naar de gebruiker. Schrijf wat je deed, wat je vond en wat niet lukte. Wijs bij wat je "
        "vond de passages aan die het dragen, met hun eerste en laatste woorden: schrijf het citaat niet uit, de code neemt "
        "de tekst uit wat de tools teruggaven. status klaar: je vond wat de opdracht vroeg (ten minste één passage). status "
        "niet_gelukt: je vond het niet, of niet alles; zeg in 'open' wat ontbreekt."),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": list(STATUS)},
            "gedaan": {"type": "string", "description": "Wat je deed, in één tot drie zinnen: waar je zocht en wat je las."},
            "bevindingen": {"type": "string", "description": (
                "Wat je vond, in eigen woorden en zonder citaten, zo volledig als de opdracht vraagt. Leeg als je niets "
                "vond.")},
            "onderbouwing": {**_ONDERBOUWING, "description": (
                "De passages die de bevindingen dragen. Elke bepaling die je noemt staat hierin. Leeg bij niet_gelukt "
                "zonder bevindingen.")},
            "open": {"type": "array", "items": {"type": "string"}, "description": (
                "Wat niet lukte, niet aan bod kwam of open blijft (aannames, twijfel), elk als één punt. Leeg als alles "
                "lukte.")},
        },
        "required": ["status", "gedaan", "bevindingen", "onderbouwing", "open"],
        "additionalProperties": False,
    },
}


def _tekst(waarde: Any) -> str:
    return " ".join(str(waarde or "").split())


def _open(invoer: dict[str, Any]) -> list[str]:
    return list(dict.fromkeys(p for x in invoer.get("open") or [] if (p := _tekst(x))))


def vul(invoer: dict[str, Any], trace: Trace) -> Antwoord:
    status = invoer.get("status")
    if status not in STATUS:
        raise Onvulbaar("Kies de status: klaar of niet_gelukt.", code="rapport_status")
    gedaan = _tekst(invoer.get("gedaan"))
    if not gedaan:
        raise Onvulbaar("Schrijf in 'gedaan' wat je deed.", code="rapport_gedaan")
    bevindingen, open_ = _tekst(invoer.get("bevindingen")), _open(invoer)
    kop = [Toelichting(kop="Gedaan", tekst=gedaan)]
    staart = [Toelichting(kop="Open", tekst="\n".join(f"- {p}" for p in open_))] if open_ else []
    if status == "niet_gelukt" and not (bevindingen or invoer.get("onderbouwing")):
        if not open_:
            raise Onvulbaar("Zeg in 'open' wat niet lukte.", code="rapport_open")
        return Antwoord(sjabloon="rapport", blokken=[*kop, *staart], doelen=[])
    if not bevindingen:
        raise Onvulbaar("Schrijf in 'bevindingen' wat je vond, of kies status niet_gelukt.", code="rapport_bevindingen")
    # Wat hij vond, toetst dezelfde code als een uitleg: elke passage in de aangewezen bepaling, elke genoemde bepaling
    # met een passage. De twijfel staat bij het rapport onder 'Open'.
    vond = duiding.vul({"kort_antwoord": bevindingen, "onderbouwing": invoer.get("onderbouwing") or [], "twijfel": [],
                        **({duiding.EXTERN_IDS: invoer[duiding.EXTERN_IDS]} if duiding.EXTERN_IDS in invoer else {})},
                       trace)
    blokken = [b.model_copy(update={"kop": "Bevindingen"}) if b.soort == "toelichting" else b for b in vond.blokken]
    return Antwoord(sjabloon="rapport", blokken=[*kop, *blokken, *staart], doelen=vond.doelen)


def status_van(invoer: dict[str, Any]) -> str:
    """De status die de code doorgeeft aan de ouder: wat het model koos, als het een geldige waarde is."""
    return invoer.get("status") if invoer.get("status") in STATUS else "niet_gelukt"
