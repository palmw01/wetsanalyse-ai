"""Wat er gelezen is en wat alleen gevonden: één regel voor het rapport uit code en de controle (meting bundel 115, D01).

De centrale agent schreef "de 16 uitspraken die de subagent las", terwijl het kind er 9 op naam opvroeg en 7 alleen in
een zoekresultaat zag. Een stuk is **gelezen** als een leestool zijn tekst gaf (`spoorbronnen`: `leestools`): bij een
bronconnector het `stuk` van het resultaat, bij de kennisgraaf de bepalingen in het resultaat. Wat alleen een zoektool
noemde, is **gevonden**. Een verwijzing in de tekst van een gelezen stuk (een voetnoot, een aangehaalde uitspraak) is
geen gelezen stuk.
"""
from __future__ import annotations

import json
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
