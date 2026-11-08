"""Bronnen naast de wet in een antwoord (ADR-008 + ADR-013): het blok `extern`, als subsjabloon en als eigen sjabloon.

Een antwoord met een Kamerstuk (of later een uitspraak, EU-recht) krijgt een vaste vorm in plaats van vrije tekst
waarin de wetsgeschiedenis door de uitleg loopt. Eén herbruikbaar blok, generiek per brontype:

- **Als subsjabloon.** De sjablonen van een specialist die een connector bedient (`ConnectorBeschrijving.specialisten`)
  krijgen één extra veld, `extern`: een lijst platte objecten `{id, van_nr, tot_nr}`. Zonder union, zonder recursie en
  verplicht maar mag leeg zijn: binnen de grenzen die strict tools stellen. Het veld staat er alleen als er een
  connector aanstaat, dus zonder connector is het schema byte-gelijk aan vóór ADR-013 (open keuze 6, aanbeveling a).
- **Als eigen sjabloon** (`antwoord_extern`): een vraag die alleen over een bron naast de wet gaat. Een kort antwoord
  van Lex, dezelfde `extern`-aanwijzing en de twijfel.

Het model wijst alleen het stuk en de passages aan. De tekst, de vindplaats, het brontype en de kop komen uit de code:
de rijen van de leestool van de connector (contract: `stuk: {id, label, link}` en rijen `{nr, tekst, kop?}`) en de
beschrijving (`kop_in_antwoord`). Een id dat niet gelezen is, of een passage die er niet is, is `Onvulbaar`: het model
haalt dan eerst op, net als bij `van`/`tot` in de duiding.
"""
from __future__ import annotations

import copy
from typing import Any

from bronmodel.antwoord import Antwoord, Extern, ExternePassage, Toelichting, Twijfel
from bronmodel.connectors import ConnectorBeschrijving, van_id
from bronmodel.extern import externe_vindplaats

from .vullen import Onvulbaar, Trace, resultaten

#: Zo veel passages mag één aanwijzing omvatten: meer is een samenvatting, en die schrijft Lex in eigen woorden.
MAX_PASSAGES = 6
#: Zo veel stukken per antwoord.
MAX_STUKKEN = 4

VELD = "extern"

ITEMS: dict[str, Any] = {
    "type": "array",
    "description": (
        "Passages uit een bron naast de wet (een Kamerstuk, later een uitspraak) die je in dit gesprek met de leestool "
        "ophaalde: per stuk het id en het eerste en laatste alineanummer. Schrijf de tekst niet uit, de code neemt hem "
        "uit de bron. Leeg als het antwoord zo'n bron niet gebruikt. Een bron naast de wet onderbouwt nooit wat de wet zegt."),
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Het id van het stuk uit het toolresultaat, bijvoorbeeld 'kst-33755-3'."},
            "van_nr": {"type": "integer", "description": "Het nummer (nr) van de eerste alinea."},
            "tot_nr": {"type": "integer", "description": "Het nummer (nr) van de laatste alinea; gelijk aan van_nr voor één alinea."},
        },
        "required": ["id", "van_nr", "tot_nr"],
        "additionalProperties": False,
    },
}

SCHEMA: dict[str, Any] = {
    "name": "antwoord_extern",
    "description": (
        "Rond een vraag af die alleen over een bron naast de wet gaat (wetsgeschiedenis, later rechtspraak): wat staat er in "
        "dit stuk, wat zegt de memorie van toelichting hierover. Roep deze tool aan nadat je het stuk hebt opgehaald, en "
        "schrijf geen antwoord ernaast. Jij schrijft het korte antwoord in eigen woorden en wijst de passages aan; de code "
        "toont ze letterlijk met hun vindplaats. Gaat de vraag (ook) over wat de wet zegt, gebruik dan het sjabloon voor "
        "de bepaling of de uitleg, met de passages in hun veld 'extern'."),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "kort_antwoord": {"type": "string", "description": "Het antwoord in twee tot vier zinnen, in eigen woorden en zonder citaten."},
            VELD: ITEMS,
            "twijfel": {"type": "array", "items": {"type": "string"},
                        "description": "Aannames en wat de opgehaalde tekst open laat, elk als één punt. Leeg als die er niet zijn."},
        },
        "required": ["kort_antwoord", VELD, "twijfel"],
        "additionalProperties": False,
    },
}


def met_veld(schema: dict[str, Any]) -> dict[str, Any]:
    """Een sjabloonschema met het veld `extern` erbij: het subsjabloon. Het origineel blijft ongemoeid."""
    uit = copy.deepcopy(schema)
    invoer = uit["input_schema"]
    invoer["properties"][VELD] = copy.deepcopy(ITEMS)
    if VELD not in invoer["required"]:
        invoer["required"].append(VELD)
    return uit


def _gelezen(trace: Trace, c: ConnectorBeschrijving, ident: str) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    """Het stuk en zijn passages op nummer, uit alle pagina's van de leestool voor dit id."""
    stuk: dict[str, Any] = {}
    rijen: dict[int, dict[str, Any]] = {}
    for data in resultaten(trace, [c.leestool]):
        s = data.get("stuk") or {}
        if s.get("id") != ident:
            continue
        stuk = stuk or s
        for r in data.get("resultaten") or []:
            if isinstance(r, dict) and isinstance(r.get("nr"), int) and isinstance(r.get("tekst"), str):
                rijen.setdefault(r["nr"], r)
    return stuk, rijen


def blokken(items: Any, trace: Trace) -> list[Extern]:
    """De blokken `extern` uit de aanwijzingen van het model; elk feit uit de trace."""
    if not items:
        return []
    if not isinstance(items, list) or len(items) > MAX_STUKKEN * 2:
        raise Onvulbaar(f"'{VELD}' is een lijst van hoogstens {MAX_STUKKEN * 2} aanwijzingen.")
    per_stuk: dict[str, Extern] = {}
    for item in items:
        ident = str((item or {}).get("id") or "").strip()
        vp = externe_vindplaats(ident)
        c = van_id(ident)
        if vp is None or c is None:
            raise Onvulbaar(f"'{ident}' is geen id van een bron naast de wet die hier aanstaat.")
        stuk, rijen = _gelezen(trace, c, vp.id)
        if not stuk:
            raise Onvulbaar(f"{vp.label} is in dit gesprek niet gelezen: haal het stuk eerst op met {c.leestool}, en wijs "
                            "dan de passages aan.")
        van, tot = item.get("van_nr"), item.get("tot_nr")
        if not isinstance(van, int) or not isinstance(tot, int) or van > tot:
            raise Onvulbaar(f"{vp.label}: van_nr en tot_nr zijn alineanummers, met van_nr ≤ tot_nr.")
        if tot - van + 1 > MAX_PASSAGES:
            raise Onvulbaar(f"{vp.label}: hoogstens {MAX_PASSAGES} alinea's per aanwijzing; vat de rest in eigen woorden samen.")
        ontbreekt = [n for n in range(van, tot + 1) if n not in rijen]
        if ontbreekt:
            raise Onvulbaar(f"{vp.label}: alinea {', '.join(map(str, ontbreekt))} is niet opgehaald. Haal het vervolg op, "
                            "of wijs alinea's aan die in het resultaat staan.")
        blok = per_stuk.setdefault(vp.id, Extern(
            brontype=vp.brontype, id=vp.id, label=str(stuk.get("label") or vp.label),
            link=str(stuk.get("link") or vp.uri), kop=c.kop_in_antwoord, passages=[]))
        al = {p.nr for p in blok.passages}
        blok.passages += [ExternePassage(nr=n, tekst=rijen[n]["tekst"], kop=str(rijen[n].get("kop") or ""))
                          for n in range(van, tot + 1) if n not in al]
    if len(per_stuk) > MAX_STUKKEN:
        raise Onvulbaar(f"Hoogstens {MAX_STUKKEN} stukken per antwoord.")
    for b in per_stuk.values():
        b.passages.sort(key=lambda p: p.nr)
    return list(per_stuk.values())


def vul(invoer: dict[str, Any], trace: Trace) -> Antwoord:
    """Het sjabloon `antwoord_extern`: kort antwoord, de passages en de twijfel."""
    gevonden = blokken(invoer.get(VELD), trace)
    if not gevonden:
        raise Onvulbaar("Wijs minstens één passage aan, of antwoord in tekst als je niets vond.")
    kort = str(invoer.get("kort_antwoord") or "").strip()
    if not kort:
        raise Onvulbaar("Schrijf een kort antwoord in eigen woorden.")
    punten = [str(p).strip() for p in invoer.get("twijfel") or [] if str(p).strip()]
    return Antwoord(sjabloon="extern", blokken=[Toelichting(tekst=kort), *gevonden, *([Twijfel(punten=punten)] if punten else [])])
