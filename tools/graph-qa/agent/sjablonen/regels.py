"""Het antwoord over vastgelegde afleidingsregels (ADR-008, ADR-018; laatste meting na #1797, 20 nov 2026).

Het model schrijft het korte antwoord en kiest welke regels het toont; de feiten komen uit de api, zoals `search_regels`
en `get_regel` ze in deze beurt teruggaven: id, naam, status, de open punten, de gevallen met hun regeltekst, de dragers
met hun vindplaats en de opvolging. Het model typt dus geen regelnaam, status of vindplaats over.

Het duidingssjabloon was het enige van de route en vraagt aangewezen wettekstpassages: bij een vraag naar de stand of
de opvolging van regels past het nooit, en het model schreef tekst (`sjabloon.gemist`, runs 27e2865d en 7928ca59). Een
tekstantwoord in deze route zet `als_regelantwoord` om, zonder modelronde, zoals een lijst gevonden stukken.

Het blok `regels` is afgeleide duiding: niet getoetst als bron (`bronmodel.antwoord.NIET_GETOETST`). De doelen van het
antwoord zijn de bronnodes van de dragers: daar staat de wettekst waarop de regels rusten.
"""
from __future__ import annotations

import json
from typing import Any

from bronmodel.antwoord import (Antwoord, RegelDrager, RegelVerwijzing, Regels, Toelichting, Twijfel, VastgelegdeRegel,
                                Vindplaats)

from .vullen import Onvulbaar, Trace

NAAM = "antwoord_regels"
#: Zoveel regels toont het blok hoogstens; de lijst van een werkgebied is meestal kleiner.
MAX_REGELS = 12

SCHEMA: dict[str, Any] = {
    "name": NAAM,
    "description": (
        "Rond een vraag over de vastgelegde afleidingsregels af: welke er liggen, hun status of opvolging, of waarop ze "
        "rusten. Jij schrijft alleen het korte antwoord in eigen woorden en noemt welke regels je toont (hun id uit "
        "search_regels of get_regel). De werkplek toont per regel zelf de naam, de status, de open punten, de gevallen met "
        "hun regeltekst, de dragers met hun vindplaats en de opvolging, uit wat de tools teruggaven: herhaal die niet en "
        "zet geen regeltekst tussen aanhalingstekens. Schrijf geen antwoord ernaast."),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "kort_antwoord": {"type": "string", "description": "Twee tot vier zinnen: het antwoord op de vraag."},
            "regels": {"type": "array", "items": {"type": "string"},
                       "description": "De id's van de regels die het antwoord toont, in de volgorde van het antwoord."},
            "twijfel": {"type": "array", "items": {"type": "string"},
                        "description": "Wat onzeker is of nog openstaat, kort. Leeg als er niets is."},
        },
        "required": ["kort_antwoord", "regels", "twijfel"],
        "additionalProperties": False,
    },
}


def _data(tekst: str) -> dict[str, Any]:
    try:
        d = json.loads(tekst or "")
    except ValueError:
        return {}
    return d if isinstance(d, dict) and d.get("status", "ok") == "ok" else {}


def regels_in_trace(trace: Trace) -> dict[str, VastgelegdeRegel]:
    """Per regel-id wat de tools van deze beurt teruggaven: een gelezen regel (`get_regel`) wint van een zoekrij."""
    uit: dict[str, VastgelegdeRegel] = {}
    for naam, tekst in trace:
        if naam == "search_regels":
            for r in _data(tekst).get("resultaten") or []:
                if r.get("id") and r["id"] not in uit:
                    uit[r["id"]] = VastgelegdeRegel(
                        id=r["id"], werkgebied_id=r.get("werkgebied_id", ""), werkgebied=r.get("werkgebied", ""),
                        naam=r.get("naam", ""), uitvoer=r.get("uitvoer", ""), status=r.get("regel_status", ""),
                        soort=r.get("soort", ""), **_opvolging_van(r))
        elif naam == "get_regel" and (r := _data(tekst)).get("id"):
            vorig = uit.get(r["id"])
            tekst_ = r.get("regeltekst")
            uit[r["id"]] = VastgelegdeRegel(
                id=r["id"], werkgebied_id=r.get("werkgebied_id", ""),
                werkgebied=(vorig.werkgebied if vorig else ""), naam=r.get("naam", ""), uitvoer=r.get("uitvoer", ""),
                status=r.get("regel_status", ""), soort=r.get("soort", ""),
                gevallen=[{"label": g.get("geval", ""), "tekst": g.get("tekst", "")} for g in tekst_]
                if isinstance(tekst_, list) else ([{"label": "", "tekst": tekst_}] if tekst_ else []),
                dragers=_ontdubbeld(r.get("dragers") or []),
                open_punten=int((r.get("open_punten") or {}).get("open") or 0), gelezen=True, **_opvolging_van(r))
    return uit


def _opvolging_van(r: dict[str, Any]) -> dict[str, Any]:
    """`vervangen_door` en `vervangt` uit een zoekrij of een gelezen regel: dezelfde velden (`regel_tools._opvolging`)."""
    return {"vervangen_door": RegelVerwijzing(**r["vervangen_door"]) if isinstance(r.get("vervangen_door"), dict) else None,
            "vervangt": [RegelVerwijzing(**v) for v in r.get("vervangt") or [] if isinstance(v, dict)]}


def _ontdubbeld(dragers: list[dict[str, Any]]) -> list[RegelDrager]:
    """De dragers, per geval één keer per element en rol (slotmeting na #1798: een dubbele drager in lid 5)."""
    gezien, uit = set(), []
    for d in dragers:
        sleutel = (d.get("geval", ""), d.get("element_id") or d.get("passage", ""), d.get("rol", ""))
        if sleutel in gezien:
            continue
        gezien.add(sleutel)
        uit.append(RegelDrager(element_id=d.get("element_id", ""), rol=d.get("rol", ""), geval=d.get("geval", ""),
                               beoordeling=d.get("beoordeling", ""), passage=d.get("passage", ""),
                               vindplaats=d.get("vindplaats", ""), bron_iri=d.get("bron_iri", ""), jci=d.get("jci", "")))
    return uit


def _doelen(regels: list[VastgelegdeRegel]) -> list[Vindplaats]:
    """De bronnodes van elke drager die niet is afgewezen, ook context: daar rust het antwoord op (slotmeting na #1798:
    LI 9.5 is een contextdrager bij lid 5, en viel met alleen de grondslag uit de bronnen)."""
    uit: dict[str, Vindplaats] = {}
    for r in regels:
        for d in r.dragers:
            if d.bron_iri and d.beoordeling != "afgewezen" and d.bron_iri not in uit:
                uit[d.bron_iri] = Vindplaats(iri=d.bron_iri, label=d.vindplaats or d.bron_iri, jci=d.jci)
    return list(uit.values())


def bouw(kort: str, ids: list[str], twijfel: list[str], trace: Trace) -> Antwoord:
    bekend = regels_in_trace(trace)
    if not bekend:
        raise Onvulbaar("Er is in deze beurt geen regel gezocht of gelezen: roep eerst search_regels of get_regel aan.",
                        code="geen_regels")
    onbekend = [i for i in ids if i not in bekend]
    if onbekend:
        raise Onvulbaar("Deze id's staan niet in wat search_regels of get_regel teruggaf: " + ", ".join(onbekend[:5])
                        + ". Noem alleen regels uit die resultaten.", code="regel_onbekend")
    gekozen = [bekend[i] for i in dict.fromkeys(ids)] or list(bekend.values())
    blokken: list[Any] = [*([Toelichting(kop="Kort antwoord", tekst=kort)] if kort else []),
                          Regels(items=gekozen[:MAX_REGELS])]
    if twijfel:
        blokken.append(Twijfel(punten=twijfel))
    return Antwoord(sjabloon="regels", blokken=blokken, doelen=_doelen(gekozen[:MAX_REGELS]))


def vul(invoer: dict[str, Any], trace: Trace) -> Antwoord:
    kort = str(invoer.get("kort_antwoord") or "").strip()
    if not kort:
        raise Onvulbaar("Schrijf het korte antwoord.", code="kort_antwoord")
    twijfel = [t for x in invoer.get("twijfel") or [] if (t := str(x).strip())]
    return bouw(kort, [str(i) for i in invoer.get("regels") or []], twijfel, trace)


def omzetting(tekst: str, trace: Trace) -> dict[str, Any] | None:
    """Een tekstantwoord in de leesroute voor regels als aanroep van dit sjabloon, zonder modelronde (zoals
    `lijst_omzetten` bij stukken): de tekst als kort antwoord, en de regels die ze bij naam of id noemt, anders de
    gelezen regels, anders alle gevonden. None als er geen regel in de trace staat; dan blijft de tekst het antwoord."""
    bekend = regels_in_trace(trace)
    if not bekend or not (tekst or "").strip():
        return None
    laag = tekst.casefold()
    genoemd = [i for i, r in bekend.items() if i in tekst or (r.naam and r.naam.casefold() in laag)]
    gelezen = [i for i, r in bekend.items() if r.gelezen]
    from uuid import uuid4
    return {"id": "omgezet_" + uuid4().hex[:12], "name": NAAM,
            "input": {"kort_antwoord": tekst.strip(), "regels": (genoemd or gelezen or list(bekend))[:MAX_REGELS],
                      "twijfel": []}}
