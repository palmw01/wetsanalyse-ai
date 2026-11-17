"""Een model kiest de bepalingen bij een deelvraag uit wat de code vond (`Zoekprofiel.model_kiest`, standaard aan sinds
de meting `bronselectie-2026-11-17-model`).

Waarom. De pilot LB3 van Lex Bench (17 nov 2026, `docs/architectuur/metingen/lex-bench-2026-11-17-pilot/`) liet zien dat
de index ongeveer de helft van de bepalingen vindt die het team nodig vindt, maar dat de rangschikking in code er
nauwelijks iets van overhoudt. Twee ingrepen in de rangschikking zonder model hielpen de ene set en schaadden een andere.

Hoe. De code verzamelt de kandidaten: om de beurt uit de pool vanaf de gebeurtenis (`zoekvragen.opties_bij_deelvraag`)
en uit de woordenroute (`deelvraag_zoeken.bepaling_opties`), ontdubbeld, hoogstens `MAX_KANDIDATEN`, elk met zijn tekst
(afgekapt op `MAX_TEKST`). Het model krijgt de deelvraag, het dossier en de genummerde kandidaten, en wijst met één
strict tool hoogstens `MAX_GEKOZEN` nummers aan, met per nummer een rol. Het model typt geen iri en geen tekst: de code
neemt die van de kandidaat over. Een nummer dat niet bestaat of dubbel staat, valt weg. Geeft het model geen bruikbaar
antwoord, dan geeft `kies` `None` en valt de aanroeper terug op de rangschikking in code."""
from __future__ import annotations

import logging
from typing import Any

from .llm_stap import Rol, vraag_tool

logger = logging.getLogger(__name__)

MAX_KANDIDATEN = 40
MAX_TEKST = 500
MAX_GEKOZEN = 8
MAX_TOKENS = 1024
ROLLEN = ("kern", "afhankelijkheid", "aanverwant")

SYSTEEM = (
    "Je helpt een jurist bij de bronselectie van een wetsanalyse. Je krijgt één deelvraag, het dossier van het "
    "werkgebied en een genummerde lijst bepalingen die de zoekmachine vond. Kies de bepalingen die de jurist nodig "
    "heeft om deze deelvraag te beantwoorden, op grond van hun tekst. Kern: de bepaling beantwoordt de deelvraag zelf. "
    "Afhankelijkheid: de kern kan niet zonder (een definitie, een bepaling waarnaar de kern verwijst). Aanverwant: "
    "nuttig, niet nodig. Kies een bepaling niet omdat ze een woord van de vraag noemt, maar omdat ze er inhoudelijk "
    "over gaat. Laat weg wat de afbakening uitsluit. Kies er hoogstens acht; minder mag. Geef alleen nummers uit de "
    "lijst.")


def kandidaten(uit_pool: list[dict[str, Any]], woorden: list[dict[str, Any]],
               maximaal: int = MAX_KANDIDATEN) -> list[dict[str, Any]]:
    """De kandidaten voor het model: om de beurt uit de pool en uit de woordenroute, elk in hun eigen volgorde,
    ontdubbeld op `bron_iri`. Een optie die de woordenroute als *buiten* markeerde, doet niet mee. Elke kandidaat
    draagt `bron_iri`, `label`, `tekst` en `bron` (`pool` of `woorden`)."""
    rijen = [[{**o, "bron": "pool"} for o in uit_pool],
             [{**o, "bron": "woorden"} for o in woorden if not o.get("buiten")]]
    uit: list[dict[str, Any]] = []
    gezien: set[str] = set()
    i = 0
    while len(uit) < maximaal and any(i < len(r) for r in rijen):
        for r in rijen:
            if i < len(r) and r[i]["bron_iri"] not in gezien and len(uit) < maximaal:
                gezien.add(r[i]["bron_iri"])
                uit.append({"bron_iri": r[i]["bron_iri"], "label": r[i].get("label") or "",
                            "tekst": " ".join(str(r[i].get("tekst") or r[i].get("zin") or "").split()),
                            "bron": r[i]["bron"]})
        i += 1
    return uit


def _afgekapt(tekst: str) -> str:
    if len(tekst) <= MAX_TEKST:
        return tekst
    return tekst[:MAX_TEKST].rsplit(" ", 1)[0] + " …"


def prompt(vraag: str, dossier: dict[str, Any], kand: list[dict[str, Any]]) -> str:
    velden = [("Werkgebied", dossier.get("naam")), ("Analysevraag", dossier.get("analysevraag")),
              ("Praktijkvoorbeeld", dossier.get("praktijkvoorbeeld")),
              ("Buiten de afbakening", dossier.get("afbakening") or dossier.get("buiten"))]
    kop = "\n".join(f"{n}: {' '.join(str(w).split())}" for n, w in velden if w)
    lijst = "\n".join(f"{i}. {k['label'] or k['bron_iri']}: {_afgekapt(k['tekst'])}" for i, k in enumerate(kand, 1))
    return f"{kop}\n\nDeelvraag: {vraag}\n\nBepalingen:\n{lijst}\n\nKies met de tool de bepalingen bij deze deelvraag."


def schema() -> dict[str, Any]:
    return {"name": "kies_bepalingen", "description": "De bepalingen bij de deelvraag, als nummers uit de lijst.",
            "strict": True,
            "input_schema": {"type": "object", "additionalProperties": False, "required": ["gekozen"], "properties": {
                "gekozen": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False, "required": ["nummer", "rol"], "properties": {
                        "nummer": {"type": "integer"}, "rol": {"type": "string", "enum": list(ROLLEN)}}}}}}}


def _haal(invoer: dict[str, Any]) -> list[dict[str, Any]] | None:
    gekozen = invoer.get("gekozen")
    return gekozen if isinstance(gekozen, list) else None


def kies(llm: Any, model: str, vraag: str, dossier: dict[str, Any], kand: list[dict[str, Any]],
         meting: dict[str, Any] | None = None) -> list[dict[str, Any]] | None:
    """De kandidaten die het model bij de deelvraag kiest, in zijn volgorde, elk met `rol`; hoogstens `MAX_GEKOZEN`.
    Zonder kandidaten een lege lijst zonder aanroep. `None` als het model geen bruikbaar antwoord gaf of de aanroep
    faalde: dan kiest de code."""
    if not kand:
        return []
    verzoek = dict(model=model, max_tokens=MAX_TOKENS, system=SYSTEEM, tools=[schema()],
                   tool_choice={"type": "tool", "name": "kies_bepalingen"},
                   messages=[{"role": "user", "content": prompt(vraag, dossier, kand)}])
    try:
        uit = vraag_tool(llm, Rol.DEELVRAAG_KEUZE, verzoek=verzoek, pogingen=1, meting=meting, haal=_haal)
    except Exception:  # noqa: BLE001 – een keuze die faalt, valt terug op de rangschikking in code
        logger.warning("deelvraagkeuze mislukt", exc_info=True, extra={"categorie": "technisch"})
        return None
    if uit.waarde is None:
        return None
    gekozen: list[dict[str, Any]] = []
    gezien: set[int] = set()
    for g in uit.waarde:
        try:
            nummer = int(g.get("nummer"))
        except (TypeError, ValueError, AttributeError):
            continue
        if 1 <= nummer <= len(kand) and nummer not in gezien and len(gekozen) < MAX_GEKOZEN:
            gezien.add(nummer)
            rol = g.get("rol") if g.get("rol") in ROLLEN else "kern"
            gekozen.append({**kand[nummer - 1], "rol": rol})
    return gekozen
