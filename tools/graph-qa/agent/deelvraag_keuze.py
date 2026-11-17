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
antwoord, dan geeft `kies` `None` en valt de aanroeper terug op de rangschikking in code.

Met `PER_WERKGEBIED` (standaard uit) kiest het model één keer voor het hele werkgebied (`kies_werkgebied`, onderaan)."""
from __future__ import annotations

import logging
from typing import Any

from .llm_stap import Rol, vraag_tool

logger = logging.getLogger(__name__)

#: Hoeveel kandidaten het model ziet, en hoe lang hun tekst. Meting `bronselectie-2026-11-17-kandidaten` (zonder model): van
#: 172 nodige bepalingen stonden er bij 40 kandidaten 73 op de lijst, bij 80 93, bij 120 99 en bij 160 104. 80 met een
#: kortere tekst houdt een aanroep ongeveer even groot (80 × 300 tegen 40 × 500 tekens).
MAX_KANDIDATEN = 80
MAX_TEKST = 300
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


# --- één keuze voor het hele werkgebied (`PER_WERKGEBIED`, standaard uit) -------------------------------------------
#
# Waarom. Per deelvraag ziet het model de andere deelvragen niet. In de pilot LB3 (LB-08) stonden goede bepalingen bij de
# verkeerde deelvraag: 26 lid 2, 26a en 26b bij deelvraag 3 die bij 1 horen, 28 lid 1 bij 3 die bij 2 hoort, 32 lid 1 bij
# 1 en 2 die bij 3 hoort. De zoekmachine vindt een bepaling bij de deelvraag waarvan ze de woorden raakt; welke deelvraag ze
# beantwoordt, ziet pas wie alle deelvragen naast elkaar leest.
#
# Hoe. De code verenigt de kandidaten van alle deelvragen (om de beurt per deelvraag, in hun eigen volgorde, ontdubbeld,
# hoogstens `MAX_KANDIDATEN_WERKGEBIED`). Het model krijgt het dossier, de genummerde deelvragen en de genummerde
# bepalingen, en wijst met één strict tool per bepaling de deelvraag en de rol aan; een bepaling die bij geen deelvraag
# hoort, noemt het niet. Bij welke deelvraag de zoekmachine een bepaling vond, staat bewust niet in de prompt: juist dat
# spoor zette in LB-08 de bepaling bij de verkeerde deelvraag. De code begrenst per deelvraag op `MAX_GEKOZEN`. Een tweede
# variant woog mee: per deelvraag kiezen met de andere deelvragen in de prompt. Die ziet de kandidaten van de andere
# deelvragen niet, dus kan 26a (gevonden bij 3) niet bij 1 zetten; ze kan haar alleen weglaten.

#: Kiest het model één keer voor het hele werkgebied in plaats van per deelvraag? Standaard uit: de meting zet beide vormen
#: naast elkaar (`eval/bronselectie_model_meting.py --werkgebied`). Uit is het verzoek per deelvraag byte-gelijk.
PER_WERKGEBIED = False
#: Hoeveel kandidaten de vereniging hoogstens heeft. ~150 tokens per kandidaat, dus ~30k invoer bij de grens; vijf
#: deelvragen met elk `MAX_KANDIDATEN` (40) en weinig overlap passen erin.
MAX_KANDIDATEN_WERKGEBIED = 200
#: De uitvoer: ~25 tokens per toewijzing, hoogstens `MAX_GEKOZEN` per deelvraag.
MAX_TOKENS_WERKGEBIED = 4096

SYSTEEM_WERKGEBIED = (
    "Je helpt een jurist bij de bronselectie van een wetsanalyse. Je krijgt het dossier van het werkgebied, de genummerde "
    "deelvragen en een genummerde lijst bepalingen die de zoekmachine bij die deelvragen vond. Zet elke bepaling die de "
    "jurist nodig heeft bij de deelvraag die ze beantwoordt, op grond van haar tekst. Lees eerst alle deelvragen: een "
    "bepaling hoort bij de deelvraag waarover ze vooral gaat, ook als ze woorden van een andere deelvraag noemt. Zet een "
    "bepaling alleen bij meer deelvragen als ze voor elk daarvan kern is. Kern: de bepaling beantwoordt de deelvraag zelf. "
    "Afhankelijkheid: de kern kan niet zonder (een definitie, een bepaling waarnaar de kern verwijst). Aanverwant: nuttig, "
    "niet nodig. Kies een bepaling niet omdat ze een woord van een vraag noemt, maar omdat ze er inhoudelijk over gaat. "
    "Laat weg wat de afbakening uitsluit en wat bij geen deelvraag hoort. Hoogstens acht per deelvraag; minder mag. Geef "
    "alleen nummers uit de lijsten.")


def kandidaten_werkgebied(per_deelvraag: list[list[dict[str, Any]]],
                          maximaal: int = MAX_KANDIDATEN_WERKGEBIED) -> list[dict[str, Any]]:
    """De vereniging van de kandidaten van alle deelvragen (elk de uitkomst van `kandidaten`): om de beurt per deelvraag,
    elk in zijn eigen volgorde, ontdubbeld op `bron_iri`, hoogstens `maximaal`. Elke kandidaat draagt `gevonden_bij`: de
    nummers (vanaf 0) van de deelvragen waarbij de zoekmachine hem vond, ook voorbij de grens. Dat is bewijs voor de
    bronnenrun, geen invoer voor het model."""
    bij: dict[str, list[int]] = {}
    for i, lijst in enumerate(per_deelvraag):
        for k in lijst:
            if i not in bij.setdefault(k["bron_iri"], []):
                bij[k["bron_iri"]].append(i)
    uit: list[dict[str, Any]] = []
    gezien: set[str] = set()
    j = 0
    while len(uit) < maximaal and any(j < len(r) for r in per_deelvraag):
        for r in per_deelvraag:
            if j < len(r) and r[j]["bron_iri"] not in gezien and len(uit) < maximaal:
                gezien.add(r[j]["bron_iri"])
                uit.append({**r[j], "gevonden_bij": bij[r[j]["bron_iri"]]})
        j += 1
    return uit


def prompt_werkgebied(deelvragen: list[str], dossier: dict[str, Any], kand: list[dict[str, Any]]) -> str:
    velden = [("Werkgebied", dossier.get("naam")), ("Analysevraag", dossier.get("analysevraag")),
              ("Praktijkvoorbeeld", dossier.get("praktijkvoorbeeld")),
              ("Buiten de afbakening", dossier.get("afbakening") or dossier.get("buiten"))]
    kop = "\n".join(f"{n}: {' '.join(str(w).split())}" for n, w in velden if w)
    vragen = "\n".join(f"{i}. {' '.join(str(v).split())}" for i, v in enumerate(deelvragen, 1))
    lijst = "\n".join(f"{i}. {k['label'] or k['bron_iri']}: {_afgekapt(k['tekst'])}" for i, k in enumerate(kand, 1))
    return (f"{kop}\n\nDeelvragen:\n{vragen}\n\nBepalingen:\n{lijst}\n\n"
            "Zet met de tool elke bepaling die nodig is bij haar deelvraag.")


def schema_werkgebied() -> dict[str, Any]:
    return {"name": "wijs_bepalingen_toe",
            "description": "Per bepaling de deelvraag waarbij ze hoort en haar rol, als nummers uit de lijsten.",
            "strict": True,
            "input_schema": {"type": "object", "additionalProperties": False, "required": ["toewijzingen"], "properties": {
                "toewijzingen": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False, "required": ["nummer", "deelvraag", "rol"],
                    "properties": {"nummer": {"type": "integer"}, "deelvraag": {"type": "integer"},
                                   "rol": {"type": "string", "enum": list(ROLLEN)}}}}}}}


def _haal_toewijzingen(invoer: dict[str, Any]) -> list[dict[str, Any]] | None:
    t = invoer.get("toewijzingen")
    return t if isinstance(t, list) else None


def kies_werkgebied(llm: Any, model: str, deelvragen: list[str], dossier: dict[str, Any], kand: list[dict[str, Any]],
                    meting: dict[str, Any] | None = None) -> list[list[dict[str, Any]]] | None:
    """Per deelvraag (in de volgorde van `deelvragen`) de kandidaten die het model erbij zet, in zijn volgorde, elk met
    `rol`; hoogstens `MAX_GEKOZEN` per deelvraag. Een nummer of deelvraag die niet bestaat, of een dubbele toewijzing,
    valt weg. Zonder kandidaten lege lijsten zonder aanroep. `None` als het model geen bruikbaar antwoord gaf of de
    aanroep faalde: dan kiest de aanroeper per deelvraag."""
    uit: list[list[dict[str, Any]]] = [[] for _ in deelvragen]
    if not kand or not deelvragen:
        return uit
    verzoek = dict(model=model, max_tokens=MAX_TOKENS_WERKGEBIED, system=SYSTEEM_WERKGEBIED,
                   tools=[schema_werkgebied()], tool_choice={"type": "tool", "name": "wijs_bepalingen_toe"},
                   messages=[{"role": "user", "content": prompt_werkgebied(deelvragen, dossier, kand)}])
    try:
        antwoord = vraag_tool(llm, Rol.DEELVRAAG_KEUZE, verzoek=verzoek, pogingen=1, meting=meting,
                              haal=_haal_toewijzingen)
    except Exception:  # noqa: BLE001 – een keuze die faalt, valt terug op de keuze per deelvraag
        logger.warning("deelvraagkeuze per werkgebied mislukt", exc_info=True, extra={"categorie": "technisch"})
        return None
    if antwoord.waarde is None:
        return None
    gezien: set[tuple[int, int]] = set()
    for t in antwoord.waarde:
        try:
            nummer, dv = int(t.get("nummer")), int(t.get("deelvraag"))
        except (TypeError, ValueError, AttributeError):
            continue
        if not (1 <= nummer <= len(kand) and 1 <= dv <= len(deelvragen)) or (nummer, dv) in gezien:
            continue
        if len(uit[dv - 1]) >= MAX_GEKOZEN:
            continue
        gezien.add((nummer, dv))
        rol = t.get("rol") if t.get("rol") in ROLLEN else "kern"
        uit[dv - 1].append({**kand[nummer - 1], "rol": rol})
    return uit
