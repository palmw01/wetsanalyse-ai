"""Het sjabloon voor een vraag naar bestaande annotaties: de treffers zelf, met of ze compleet zijn.

Een annotatie is afgeleide duiding, geen bron. Wat niet gevonden is, is niet bewezen afwezig: een storing of nul
treffers zegt de code, en dan vervalt de toelichting van het model. Dezelfde meldingen als `begrens_antwoord`, dat het
vrije antwoord begrenst; een sjabloon gaat daar niet langs.
"""
from __future__ import annotations

import json
import re
from typing import Any

from bronmodel.antwoord import Annotaties, Antwoord, Leemte, Markering, Toelichting

from ..tools.annotatie_tools import (ANNOTATIE_TOOL_NAMEN, ANNOTATIES_NIET_TE_RAADPLEGEN, ANNOTATIES_ONVOLLEDIG,
                                     annotatie_storing, uitkomsten)
from .vullen import Onvulbaar, Trace, vindplaats_van

SCHEMA: dict[str, Any] = {
    "name": "antwoord_annotaties",
    "description": (
        "Rond een vraag naar bestaande annotaties of markeringen af. Roep deze tool aan nadat de zoekopdracht klaar is, en "
        "schrijf geen antwoord ernaast. De werkplek toont de treffers van je laatste zoekopdracht zelf, met hun aantal en of "
        "ze compleet zijn: herhaal die niet. Jij levert alleen een korte toelichting in eigen woorden: de gebruikte filters "
        "en wat opvalt. Een annotatie is duiding, geen wettekst: citeer niet. Is er niets gevonden of mislukte het zoeken, dan "
        "zegt de werkplek dat zelf."),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "toelichting": {"type": "string", "description": "Twee of drie zinnen: de gebruikte filters en wat opvalt. Leeg als er niets te zeggen valt."},
        },
        "required": ["toelichting"],
        "additionalProperties": False,
    },
}

_ZOEKTOOLS = ("search_annotaties", "overzicht_annotaties")
_PAGINERING = ("offset", "cursor", "limit")


def _laatste_zoekopdracht(trace: Trace) -> tuple[list[dict[str, Any]], bool]:
    """De pagina's van de laatste zoekopdracht, en of er daarna iets misging. Een nieuwe zoekopdracht verfijnt of
    verbreedt de vorige: alles samenvoegen toont treffers bij filters die niet meer gelden. Pagina's horen wel bij elkaar."""
    paginas: list[dict[str, Any]] = []
    sleutel, fout = None, False
    for naam, tekst in trace:
        if naam not in _ZOEKTOOLS:
            continue
        data = uitkomsten([(naam, tekst)], _ZOEKTOOLS)[0]
        if data.get("status") not in ("ok", "partial"):
            fout = True
            continue
        filters = {k: v for k, v in (data.get("filters") or {}).items() if k not in _PAGINERING}
        nieuw = naam + json.dumps(filters, sort_keys=True, ensure_ascii=False)
        if nieuw != sleutel:
            paginas, sleutel, fout = [], nieuw, False
        paginas.append(data)
    return paginas, fout


def _markering(rij: dict[str, Any]) -> Markering:
    plek = rij.get("vindplaats") or (vindplaats_van(rij["bron_iri"]).label if rij.get("bron_iri") else "")
    # Een `verwijzing` is een element dat maar deels binnen het bereik valt: dat draagt geen tekst.
    return Markering(id=rij.get("id", ""), klasse=rij.get("klasse", ""), tekst=rij.get("tekst") or "Annotatie met een ruimere bronselectie",
                     vindplaats=f"{plek} (verouderd)" if rij.get("verouderd") else plek)


def _groep(rij: dict[str, Any]) -> Markering:
    plek = ", ".join(rij.get("vindplaatsen") or [])
    aantal = rij.get("aantal", 1)
    return Markering(id=rij.get("voorbeeld_id", ""), klasse=rij.get("klasse", ""), tekst=rij.get("tekst", ""),
                     vindplaats=f"{aantal}×: {plek}" if aantal > 1 else plek)


def _rijen(paginas: list[dict[str, Any]]) -> tuple[list[Markering], int]:
    """De markeringen en hun aantal. Een groep uit het overzicht telt voor elke markering erin; `bekeken` kan dat niet,
    want daar zit ook de uitgezonderde bepaling in. De zoekroute kent geen totaal: dan is het wat er is opgehaald."""
    items: dict[str, Markering] = {}
    totaal = 0
    for data in paginas:
        for rij in data.get("groepen") or []:
            items[f"{rij.get('klasse')}|{rij.get('tekst')}"] = _groep(rij)
            totaal += rij.get("aantal", 1)
        for rij in data.get("resultaten") or []:
            if isinstance(rij, dict) and rij.get("id") not in items:
                items[rij.get("id", "")] = _markering(rij)
                totaal += 1
    return list(items.values()), totaal


def _filterregel(filters: dict[str, Any]) -> str:
    delen = [*(filters.get("jas_klassen") or []), filters.get("klasse", ""), f"„{filters['tekst']}”" if filters.get("tekst") else "",
             vindplaats_van(filters["bron_iri"]).label if filters.get("bron_iri") else "", filters.get("bwb_id", "")]
    return ", ".join(d for d in delen if d)


_AANTAL = re.compile(r"\b(\d+)\s+(?:\w+\s+)?(?:annotaties|markeringen|treffers|resultaten|elementen)\b", re.I)
_ZIN = re.compile(r"(?<=[.!?])\s+")


def _zonder_ander_aantal(tekst: str, totaal: int) -> str:
    """De toelichting zonder zinnen die een ander aantal treffers noemen dan de lijst toont.

    Het model neemt het getal over van zijn eigen zoekopdracht ("50 annotaties" bij `limit: 50`), ook als de code
    daarna 54 rijen ophaalde. De werkplek toont het aantal zelf, dus een zin die iets anders zegt valt weg."""
    return " ".join(z for z in _ZIN.split(tekst) if all(int(n) == totaal for n in _AANTAL.findall(z))).strip()


def _alleen(tekst: str) -> Antwoord:
    return Antwoord(sjabloon="annotaties", blokken=[Leemte(tekst=tekst)])


def vul(invoer: dict[str, Any], trace: Trace) -> Antwoord:
    antwoorden = uitkomsten(trace, ANNOTATIE_TOOL_NAMEN)
    if not antwoorden:
        raise Onvulbaar("Zoek eerst met search_annotaties of overzicht_annotaties.")
    if melding := annotatie_storing(antwoorden):
        return _alleen(melding)
    paginas, fout = _laatste_zoekopdracht(trace)
    if not paginas:  # alleen `get_annotatie` of de dekking slaagde; het zoeken zelf niet
        return _alleen(ANNOTATIES_NIET_TE_RAADPLEGEN)
    items, totaal = _rijen(paginas)
    # `volledig` van de api gaat over de projectie, niet over de paginering: bij een volgende pagina staat hij op waar.
    volledig = (not fout and not paginas[-1].get("volgende_offset")
                and all(p.get("status") == "ok" and p.get("volledig") is not False for p in paginas))
    if not items:
        filters = _filterregel(paginas[-1].get("filters") or {})
        tekst = f"Geen annotaties gevonden met deze zoekopdracht{f' ({filters})' if filters else ''}. Dat zegt niet dat ze er niet zijn."
        return _alleen(tekst if volledig else f"{tekst} {ANNOTATIES_ONVOLLEDIG}")
    blokken: list[Any] = [Annotaties(items=items, totaal=totaal, volledig=volledig)]
    if toelichting := _zonder_ander_aantal(str(invoer.get("toelichting") or "").strip(), totaal):
        blokken.append(Toelichting(tekst=toelichting))
    return Antwoord(sjabloon="annotaties", blokken=blokken)
