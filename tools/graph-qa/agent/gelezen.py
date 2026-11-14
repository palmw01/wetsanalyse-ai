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
            bekend = _rijwoorden(items, vp.id)
            eigen = [w for w in _WOORD.findall(segment.casefold()) if w not in bekend and w not in _FUNCTIEWOORDEN]
            if len(eigen) > MAX_EIGEN_WOORDEN:
                uit.append(vp.id)
    return [f"samenvatting van {i} zonder gelezen tekst" for i in uit]


def _rijwoorden(items: list[tuple[str, str]], ident: str) -> set[str]:
    """De woorden van de zoekrijen van één stuk (label, titel, instantie, datum): wat het zoekresultaat over dat stuk zegt,
    niet over de andere treffers in hetzelfde resultaat."""
    woorden: set[str] = set()
    for tool, tekst in items:
        bron = bron_van(tool)
        if bron is not None and tool in bron.leestools:
            continue
        try:
            data = json.loads(tekst)
        except (TypeError, ValueError):
            continue
        for rij in (data.get("resultaten") if isinstance(data, dict) else None) or []:
            if isinstance(rij, dict) and ident in json.dumps(rij, ensure_ascii=False):
                woorden |= set(_WOORD.findall(json.dumps(rij, ensure_ascii=False).casefold()))
    return woorden


#: Hoeveel van de eigen woorden van een duiding in de passages van het stuk moeten staan (op hun stam).
MIN_STEUN = 0.5
_STAM = 5


def _stammen(woorden: Iterable[str]) -> set[str]:
    return {w[:_STAM] for w in woorden}


def zonder_steun(tekst: str, steun: dict[str, str], trace: Iterable[Any]) -> list[str]:
    """Na een rapport van een subagent: de stukken die `tekst` duidt zonder dat een passage van dat stuk het draagt
    (meting bundel 117, D01: zeven samenvattingen van gelezen uitspraken, geen enkele klopte, en toch *gegrond*, want de
    stukken stonden in de trace). Een stuk mag het antwoord noemen, met wat het zoekresultaat erover zegt; wie meer zegt
    (meer dan `MAX_EIGEN_WOORDEN` eigen woorden in een zin of lijstregel), moet dat uit de passages van dat stuk halen:
    die van het rapport, en die het antwoord zelf toont (`steun`). Ten minste `MIN_STEUN` van die woorden staat erin, op
    hun stam. Zonder passage van het stuk is een duiding een bewering."""
    from bronmodel.extern import externe_verwijzingen

    items = [(str(x[0]), str(x[1])) for x in trace]
    uit: dict[str, str] = {}
    for segment in _SEGMENT.split(tekst or ""):
        for vp in externe_verwijzingen(segment):
            if vp.id in uit:
                continue
            bekend = _rijwoorden(items, vp.id)
            eigen = [w for w in _WOORD.findall(segment.casefold()) if w not in bekend and w not in _FUNCTIEWOORDEN]
            if len(eigen) <= MAX_EIGEN_WOORDEN:
                continue
            passages = _stammen(_WOORD.findall((steun.get(vp.id) or "").casefold()))
            if not passages:
                uit[vp.id] = f"duiding van {vp.id} zonder passage van dat stuk in het rapport"
            elif sum(w[:_STAM] in passages for w in eigen) < MIN_STEUN * len(eigen):
                uit[vp.id] = f"duiding van {vp.id} die de passages van dat stuk niet dragen"
    return list(uit.values())
