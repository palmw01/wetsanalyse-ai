"""Wat elk sjabloon nodig heeft: de rijen die de tools in deze beurt teruggaven."""
from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any

from bronmodel.antwoord import Vindplaats
from bronmodel.vindplaats import vindplaats

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


def volledige_tekst(iri: str, trace: Trace) -> str:
    """De langste tekst die de trace voor deze bronnode heeft. Een zoekrij draagt een voorproef; als de
    bepaling is opgehaald, staat de hele tekst er ook."""
    beste = ""
    for _, tekst in trace:
        for rij in _rijen_diep(_data(tekst)):
            if iri in (rij.get("node"), rij.get("iri"), rij.get("uri")) and rij.get("tekst_volledig") is not False:
                t = rij.get("tekst")
                if isinstance(t, str) and len(t) > len(beste):
                    beste = t
    return beste


def vindplaats_van(iri: str, *, jci: str = "", regeling: str = "", label: str = "") -> Vindplaats:
    """De vindplaats zoals `bronmodel` hem leest; `label` is de terugval voor een wet-lokale node."""
    vp = vindplaats(iri)
    return Vindplaats(iri=iri, jci=jci, regeling=regeling, label=(vp.label if vp else "") or label or iri)
