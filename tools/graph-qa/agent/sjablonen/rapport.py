"""Het rapport: de ene uitgang van een subagent (ADR-016 §A4).

Een subagent rondt zijn opdracht af met deze tool, nooit in tekst. Het rapport zegt wat hij deed, wat hij vond en wat
niet lukte. Wat hij vond, draagt hetzelfde onderbouwingscontract als een uitleg (`duiding.py`, ADR-008): het model wijst
passages aan met hun eerste en laatste woorden, de code neemt de tekst uit wat de tools teruggaven. Zo toetst de code
het rapport zoals elk antwoord, en krijgt de centrale agent alleen citaten uit de bron.

`status` is `klaar`, `vraag` of `niet_gelukt`. Bij `niet_gelukt` hoeft er geen passage te zijn: dan zegt het rapport
wat er wel en niet lukte. **Een vraag naar boven is een rapport met `status: vraag`** (§A4): de subagent kan niet verder
zonder een antwoord, en zegt in `vragen` wat hij wil weten, met opties als die er zijn. Er is geen aparte tool om een vraag
te stellen, en na het rapport is de run gewoon klaar: de centrale agent of de jurist antwoordt, en dan hervat de code hem
in hetzelfde deelgesprek.
"""
from __future__ import annotations

from typing import Any

from bronmodel.antwoord import Antwoord, Citaten, Toelichting

from . import duiding
from .vullen import Onvulbaar, Trace, bron_rijen

#: Wat `sjablonen.vul` meegeeft bij een rapport: de aanwijzingen in 'extern' die niet te tonen waren, en hoeveel stukken
#: wél als blok getoond worden.
NIET_GETOOND = "_niet_getoond"
EXTERN_GETOOND = "_extern_getoond"
#: Hoe lang één reden onder 'Open' hoogstens is: genoeg om te zien wat en waarom.
MAX_REDEN = 200

NAAM = "rapport"
STATUS = ("klaar", "vraag", "niet_gelukt")
#: Hoeveel vragen een rapport hoogstens stelt, en hoeveel opties een vraag hoogstens heeft (de kaart van de jurist).
MAX_VRAGEN = 3
MAX_OPTIES = 4
MAX_VRAAG = 300

_ONDERBOUWING = duiding.SCHEMA["input_schema"]["properties"]["onderbouwing"]

SCHEMA: dict[str, Any] = {
    "name": NAAM,
    "description": (
        "Rond je opdracht af met dit rapport, als laatste stap en zonder tekst ernaast. Het rapport gaat naar de agent die "
        "je de opdracht gaf, niet naar de gebruiker. Schrijf wat je deed, wat je vond en wat niet lukte. Wijs bij wat je "
        "vond de passages aan die het dragen, met hun eerste en laatste woorden: schrijf het citaat niet uit, de code neemt "
        "de tekst uit wat de tools teruggaven. status klaar: je vond wat de opdracht vroeg (ten minste één passage). status "
        "vraag: je kunt niet verder zonder een antwoord dat alleen de gebruiker of de opdrachtgever heeft (welke "
        "regeling, welk jaar, welke lezing); stel dan in 'vragen' hoogstens drie korte vragen, met opties als die er "
        "zijn, en zet in 'bevindingen' wat je al vond. Raad nooit om door te kunnen. status niet_gelukt: je vond het "
        "niet, of niet alles; zeg in 'open' wat ontbreekt."),
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
            "vragen": {"type": "array", "description": (
                "Alleen bij status vraag: wat je moet weten om verder te kunnen, hoogstens drie, elk één zin met een "
                "vraagteken. Leeg bij klaar en niet_gelukt."),
                "items": {"type": "object", "properties": {
                    "tekst": {"type": "string"},
                    "opties": {"type": "array", "items": {"type": "string"}, "description": (
                        "Hoogstens vier korte antwoorden om uit te kiezen; leeg als de vraag open is.")}},
                    "required": ["tekst", "opties"], "additionalProperties": False}},
        },
        "required": ["status", "gedaan", "bevindingen", "onderbouwing", "open", "vragen"],
        "additionalProperties": False,
    },
}


def _tekst(waarde: Any) -> str:
    return " ".join(str(waarde or "").split())


def _open(invoer: dict[str, Any]) -> list[str]:
    return list(dict.fromkeys(p for x in invoer.get("open") or [] if (p := _tekst(x))))


def _ruwe_vragen(invoer: dict[str, Any]) -> list[dict[str, Any]]:
    """De vragen zoals het model ze schreef: tekst en opties ontdubbeld, lege weg."""
    uit: list[dict[str, Any]] = []
    for v in invoer.get("vragen") or []:
        if not isinstance(v, dict):
            continue
        tekst = _tekst(v.get("tekst"))
        if tekst and tekst not in (x["tekst"] for x in uit):
            uit.append({"tekst": tekst, "opties": list(dict.fromkeys(o for x in v.get("opties") or [] if (o := _tekst(x))))})
    return uit


def genormaliseerd(invoer: dict[str, Any]) -> dict[str, Any]:
    """Het rapport zoals de code het leest. Een vraag in de verkeerde vorm is geen reden om het rapport te weigeren
    (meting bundel 115, D01: het kind wilde vragen, het rapport werd geweigerd op `rapport_vragen`, en daarna eindigde het
    `niet_gelukt` zonder bevindingen):

    - `niet_gelukt` met vragen is een vraag: het kind kan niet verder zonder antwoord;
    - `klaar` met vragen blijft klaar; de vragen staan dan onder 'Open';
    - een vraag zonder vraagteken krijgt er een, meer dan `MAX_OPTIES` opties worden er `MAX_OPTIES`, en vragen boven
      `MAX_VRAGEN` gaan naar 'Open'.

    Alleen wat niet te herstellen is, weigert `vul` nog: een vraag boven `MAX_VRAAG` tekens, of `vraag` zonder vraag."""
    status = invoer.get("status") if invoer.get("status") in STATUS else "niet_gelukt"
    vragen = [{"tekst": v["tekst"] if v["tekst"].endswith("?") else v["tekst"].rstrip(".!:; ") + "?",
               "opties": v["opties"][:MAX_OPTIES]} for v in _ruwe_vragen(invoer)]
    open_ = _open(invoer)
    if vragen and status == "niet_gelukt":
        status = "vraag"
    if vragen and status == "klaar":
        open_, vragen = [*open_, *(f"Open vraag: {v['tekst']}" for v in vragen)], []
    if len(vragen) > MAX_VRAGEN:
        open_ += [f"Open vraag: {v['tekst']}" for v in vragen[MAX_VRAGEN:]]
        vragen = vragen[:MAX_VRAGEN]
    return {**invoer, "status": status, "vragen": vragen, "open": list(dict.fromkeys(open_))}


def vragen_van(invoer: dict[str, Any]) -> list[dict[str, Any]]:
    """De vragen van het rapport zoals de code ze doorgeeft (`genormaliseerd`)."""
    return genormaliseerd(invoer)["vragen"]


def _toets_vragen(status: str, vragen: list[dict[str, Any]]) -> None:
    if status != "vraag":
        if vragen:
            raise Onvulbaar("Zet vragen alleen bij status vraag; anders blijft 'vragen' leeg.", code="rapport_vragen")
        return
    if not vragen:
        raise Onvulbaar("Stel bij status vraag ten minste één vraag in 'vragen'.", code="rapport_vragen")
    if len(vragen) > MAX_VRAGEN:
        raise Onvulbaar(f"Stel hoogstens {MAX_VRAGEN} vragen.", code="rapport_vragen")
    for v in vragen:
        if len(v["tekst"]) > MAX_VRAAG or not v["tekst"].endswith("?"):
            raise Onvulbaar(f"Een vraag is één zin met een vraagteken, hoogstens {MAX_VRAAG} tekens.",
                            code="rapport_vragen")
        if len(v["opties"]) > MAX_OPTIES:
            raise Onvulbaar(f"Geef bij een vraag hoogstens {MAX_OPTIES} opties.", code="rapport_vragen")


def vul(invoer: dict[str, Any], trace: Trace) -> Antwoord:
    if invoer.get("status") not in STATUS:
        raise Onvulbaar("Kies de status: klaar, vraag of niet_gelukt.", code="rapport_status")
    invoer = genormaliseerd(invoer)
    status = invoer["status"]
    gedaan = _tekst(invoer.get("gedaan"))
    if not gedaan:
        raise Onvulbaar("Schrijf in 'gedaan' wat je deed.", code="rapport_gedaan")
    vragen = vragen_van(invoer)
    _toets_vragen(status, vragen)
    bevindingen, open_ = _tekst(invoer.get("bevindingen")), _open(invoer)
    kop = [Toelichting(kop="Gedaan", tekst=gedaan)]
    staart = [Toelichting(kop="Open", tekst="\n".join(f"- {p}" for p in open_))] if open_ else []
    if vragen:
        staart.insert(0, Toelichting(kop="Vragen", tekst="\n".join(
            f"- {v['tekst']}" + (f" (opties: {'; '.join(v['opties'])})" if v["opties"] else "") for v in vragen)))
    if status in ("niet_gelukt", "vraag") and not (bevindingen or invoer.get("onderbouwing")):
        if status == "niet_gelukt" and not open_:
            raise Onvulbaar("Zeg in 'open' wat niet lukte.", code="rapport_open")
        return Antwoord(sjabloon="rapport", blokken=[*kop, *staart], doelen=[])
    if not bevindingen:
        raise Onvulbaar("Schrijf in 'bevindingen' wat je vond, of kies status niet_gelukt.", code="rapport_bevindingen")
    # Elke passage gaat door dezelfde toets als een uitleg (`duiding._citaat`: letterlijk in de aangewezen bepaling). Een
    # passage die niet te tonen is, laat de code weg en noemt hij onder 'Open'; het rapport valt er niet meer om
    # (meting 14 nov 2026, S03 en D01: twee geweigerde rapporten van elk ~4k uitvoertokens, daarna tekst). Een rapport is
    # een gegeven voor de centrale agent, en wat die de gebruiker zegt, toetst `verify` tegen dezelfde trace. Alleen als
    # er niets te tonen is, weigert de code: dan kan de subagent herstellen.
    rijen, fouten = bron_rijen(trace), []
    citaten = [c for stuk in invoer.get("onderbouwing") or [] if isinstance(stuk, dict)
               and (c := duiding._citaat(stuk, rijen, trace, fouten))]
    niet_getoond = [*fouten, *(str(x) for x in invoer.get(NIET_GETOOND) or [])]
    if status == "klaar" and not citaten and not int(invoer.get(EXTERN_GETOOND) or 0):
        if niet_getoond:
            raise Onvulbaar("Geen enkele passage is te tonen. " + "; ".join(niet_getoond) + ". Rond daarna opnieuw af.",
                            code="passage_niet_te_tonen")
        raise Onvulbaar("Wijs ten minste één passage aan, in 'onderbouwing' (wettekst uit de kennisgraaf) of in 'extern' "
                        "(een stuk uit een bron naast de wet), of kies status niet_gelukt.", code="geen_passage")
    if niet_getoond:
        regels = [f"- {r if len(r) <= MAX_REDEN else r[:MAX_REDEN - 1].rsplit(' ', 1)[0] + '…'}" for r in niet_getoond]
        punt = Toelichting(kop="Niet als citaat getoond", tekst="\n".join(regels))
        staart.insert(len(staart) - (1 if open_ else 0), punt)
    blokken = [Toelichting(kop="Bevindingen", tekst=duiding._lex(bevindingen, trace) or bevindingen),
               *([Citaten(items=citaten)] if citaten else [])]
    return Antwoord(sjabloon="rapport", blokken=[*kop, *blokken, *staart],
                    doelen=list({c.vindplaats.iri: c.vindplaats for c in citaten}.values()))


def status_van(invoer: dict[str, Any]) -> str:
    """De status die de code doorgeeft aan de ouder (`genormaliseerd`): wat het model koos, als het een geldige waarde is,
    en `vraag` als een `niet_gelukt` vragen draagt."""
    return genormaliseerd(invoer)["status"]
