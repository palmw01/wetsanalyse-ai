"""Wat elk sjabloon nodig heeft: de rijen die de tools in deze beurt teruggaven."""
from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any

from bronmodel.antwoord import Vindplaats
from bronmodel.vindplaats import vindplaats

from ..tools.begrip_tools import AFGELEIDE_TOOL_NAMEN

Trace = list[tuple[str, str]]


class Onvulbaar(ValueError):
    """Het sjabloon kan niet uit de trace gevuld worden. De tekst gaat als fout terug naar het model, dat
    eerst ophaalt wat ontbreekt: een halve vulling tonen we nooit."""


def _data(tekst: str) -> dict[str, Any] | None:
    try:
        data = json.loads(tekst)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def resultaten(trace: Trace, tools: Iterable[str]) -> Iterator[dict[str, Any]]:
    """De geslaagde resultaten van deze tools, oudste eerst."""
    namen = set(tools)
    for naam, tekst in trace:
        data = _data(tekst) if naam in namen else None
        if data is not None and data.get("status") in ("ok", "partial"):
            yield data


def rijen(trace: Trace, tools: Iterable[str]) -> Iterator[dict[str, Any]]:
    for data in resultaten(trace, tools):
        yield from (r for r in data.get("resultaten") or [] if isinstance(r, dict))


def _rijen_diep(v: Any) -> Iterator[dict[str, Any]]:
    if isinstance(v, dict):
        yield v
        v = list(v.values())
    if isinstance(v, list):
        for x in v:
            yield from _rijen_diep(x)


#: De velden waarin een tool-rij de iri van zijn eigen tekst draagt.
_IRI_VELDEN = ("node", "iri", "uri", "lid", "onderdeel")


def bron_rijen(trace: Trace) -> dict[str, dict[str, Any]]:
    """Per bronnode de rij met de langste hele tekst. Een zoekrij draagt soms een voorproef; als de bepaling is
    opgehaald, staat de hele tekst er ook. Annotaties en begrippen tellen niet: die zijn duiding, geen bron."""
    uit: dict[str, dict[str, Any]] = {}
    for naam, tekst in trace:
        for rij in _rijen_diep(None if naam in AFGELEIDE_TOOL_NAMEN else _data(tekst)):
            t = rij.get("tekst")
            if not isinstance(t, str) or rij.get("tekst_volledig") is False:
                continue
            for iri in (rij.get(veld) for veld in _IRI_VELDEN):
                if isinstance(iri, str) and iri and len(t) > len(uit.get(iri, {}).get("tekst", "")):
                    uit[iri] = rij
    return uit


def volledige_tekst(iri: str, trace: Trace) -> str:
    return bron_rijen(trace).get(iri, {}).get("tekst", "")


def vindplaats_van(iri: str, *, jci: str = "", regeling: str = "", label: str = "") -> Vindplaats:
    """De vindplaats zoals `bronmodel` hem leest; `label` is de terugval voor een wet-lokale node."""
    vp = vindplaats(iri)
    return Vindplaats(iri=iri, jci=jci, regeling=regeling, label=(vp.label if vp else "") or label or iri)
