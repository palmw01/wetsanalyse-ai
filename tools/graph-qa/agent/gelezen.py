"""Wat er gelezen is en wat alleen gevonden: één regel voor het rapport uit code en de controle (meting bundel 115, D01).

De centrale agent schreef "de 16 uitspraken die de subagent las", terwijl het kind er 9 op naam opvroeg en 7 alleen in
een zoekresultaat zag. Een stuk is **gelezen** als een leestool zijn tekst gaf (`spoorbronnen`: `leestools`): bij een
bronconnector het `stuk` van het resultaat, bij de kennisgraaf de bepalingen in het resultaat. Wat alleen een zoektool
noemde, is **gevonden**. Een verwijzing in de tekst van een gelezen stuk (een voetnoot, een aangehaalde uitspraak) is
geen gelezen stuk.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

from .spoorbronnen import bron_van


def _stuk(tekst: str) -> tuple[str, str] | None:
    try:
        data = json.loads(tekst)
    except (TypeError, ValueError):
        return None
    stuk = data.get("stuk") if isinstance(data, dict) else None
    # Een foutresultaat met een stuk (alleen een PDF, geen tekst bij de bron) is niet gelezen.
    if not isinstance(stuk, dict) or data.get("status") == "error" or stuk.get("leesbaar") is False or not stuk.get("id"):
        return None
    from bronmodel.extern import externe_vindplaats

    ident = str(stuk["id"])
    vp = externe_vindplaats(ident)
    # De canonieke id, zoals `collect_sources` hem uit een zoekresultaat haalt: anders telt hetzelfde stuk twee keer.
    return (vp.id if vp else ident), str(stuk.get("label") or ident)


def _bronnen(paren: list[tuple[str, str]]) -> list[tuple[str, str]]:
    from .provenance import collect_sources

    try:
        bronnen = collect_sources(paren)
    except Exception:  # noqa: BLE001 – een label is een gemak; zonder labels blijft de rest staan
        return []
    return [(str(getattr(b, "uri", "") or ""), str(getattr(b, "label", "") or getattr(b, "uri", ""))) for b in bronnen
            if b and getattr(b, "uri", "")]


def gelezen_en_gevonden(trace: Iterable[Any]) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """(gelezen, alleen gevonden) als lijsten (id, label), ontdubbeld, in volgorde van de trace."""
    gelezen: dict[str, str] = {}
    zoeken: list[tuple[str, str]] = []
    for item in trace:
        tool, tekst = str(item[0]), str(item[1])
        bron = bron_van(tool)
        if bron is None or tool not in bron.leestools:
            zoeken.append((tool, tekst))
            continue
        if bron.connector is not None:
            if (stuk := _stuk(tekst)) is not None:
                gelezen.setdefault(*stuk)
            continue
        for ident, label in _bronnen([(tool, tekst)]):
            gelezen.setdefault(ident, label)
    gevonden = {i: lab for i, lab in _bronnen(zoeken) if i not in gelezen}
    return list(gelezen.items()), list(gevonden.items())


#: Hoeveel eigen woorden een zin of lijstregel over een stuk hoogstens heeft zonder dat het een samenvatting is: woorden
#: die niet in het zoekresultaat van dat stuk staan (titel, label, instantie, datum) en geen functiewoord zijn. "ECLI:… (Hoge
#: Raad, 12 maart 2026), over de melding" is een vermelding; wat de rechter oordeelde is een samenvatting.
MAX_EIGEN_WOORDEN = 5

_WOORD = re.compile(r"[a-zà-ÿ]{3,}")
_SEGMENT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý(])|\n+")
_FUNCTIEWOORDEN = frozenset(
    "de het een en van in op over met voor door aan bij dat die dit deze zijn is was wordt werd worden heeft hebben had "
    "naar uit ook niet als zoals dan maar om tot onder tegen hij zij ze er hier daar wat welke wie waar wel nog al geen "
    "kan kon zou zal moet mag uitspraak uitspraken arrest arresten vonnis rechter rechtbank hof hoge raad gerechtshof "
    "zaak stuk stukken waarin waarbij volgens gaat ging betreft".split())


def ongelezen_samengevat(tekst: str, trace: Iterable[Any]) -> list[str]:
    """De stukken die `tekst` inhoudelijk samenvat terwijl hun tekst niet gelezen is (meting bundel 116, D01: twee
    uitspraken samengevat die niemand las, en het oordeel *gegrond* omdat de blokcitaten letterlijk waren). Een stuk is pas
    bron als het gelezen is; dezelfde regel geldt voor wat het antwoord erover zegt. Per zin of lijstregel die het stuk bij
    id noemt: meer dan `MAX_EIGEN_WOORDEN` woorden die niet uit zijn zoekresultaat komen, is een samenvatting."""
    from bronmodel.extern import externe_verwijzingen

    items = [(str(x[0]), str(x[1])) for x in trace]
    gelezen = {i for i, _ in gelezen_en_gevonden(items)[0]}
    uit: list[str] = []
    for segment in _SEGMENT.split(tekst or ""):
        for vp in externe_verwijzingen(segment):
            if vp.id in gelezen or vp.id in uit:
                continue
            bekend = set(_WOORD.findall(" ".join(t for _, t in items if vp.id in t).casefold()))
            eigen = [w for w in _WOORD.findall(segment.casefold()) if w not in bekend and w not in _FUNCTIEWOORDEN]
            if len(eigen) > MAX_EIGEN_WOORDEN:
                uit.append(vp.id)
    return [f"samenvatting van {i} zonder gelezen tekst" for i in uit]
