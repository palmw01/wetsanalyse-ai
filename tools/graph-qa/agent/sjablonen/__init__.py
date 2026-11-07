"""Antwoordsjablonen: het antwoord is de laatste toolaanroep (ADR-008).

Een sjabloon is een tool waarmee een specialist zijn beurt afrondt. Het model levert alleen wat een oordeel
of formulering vraagt; `vul` haalt de feiten uit wat de graaf in deze beurt teruggaf. Zo typt het model
nooit een citaat of vindplaats over, en krijgt de werkplek vaste blokken.

Dit zijn geen graaftools: ze staan niet in `TOOLS`, komen niet op de MCP-server en doen niets met de graaf.
Alleen deze tools zijn `strict`, en ze zijn klein en plat: voor een strict tool gelden per verzoek harde
grenzen op optionele en union-parameters, dus het model stelt geen blokken samen.

`tool_choice` blijft `auto` (geforceerd geeft een 400 op de nieuwste modellen). Schrijft het model toch
tekst, dan is dat een geldig vrij antwoord; de log zegt het (`sjabloon_gemist`).
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from bronmodel.antwoord import Antwoord

from .annotaties import SCHEMA as _ANNOTATIES, vul as _vul_annotaties
from .begrip import SCHEMA as _BEGRIP, vul as _vul_begrip
from .bepaling import SCHEMA as _BEPALING, vul as _vul_bepaling
from .duiding import SCHEMA as _DUIDING, vul as _vul_duiding
from .vullen import Onvulbaar, Trace

__all__ = ["Onvulbaar", "Sjabloon", "SJABLONEN", "sjabloon_schemas", "sjabloon_uit_tekst", "vul"]


@dataclass(frozen=True)
class Sjabloon:
    schema: dict[str, Any]
    vul: Callable[[dict[str, Any], Trace], Antwoord]


SJABLONEN: dict[str, Sjabloon] = {
    _ANNOTATIES["name"]: Sjabloon(_ANNOTATIES, _vul_annotaties),
    _BEGRIP["name"]: Sjabloon(_BEGRIP, _vul_begrip),
    _BEPALING["name"]: Sjabloon(_BEPALING, _vul_bepaling),
    _DUIDING["name"]: Sjabloon(_DUIDING, _vul_duiding),
}


def sjabloon_schemas(namen: frozenset[str]) -> list[dict[str, Any]]:
    return [SJABLONEN[n].schema for n in sorted(namen)]


def vul(naam: str, invoer: dict[str, Any], trace: Trace) -> Antwoord:
    return SJABLONEN[naam].vul(invoer, trace)


_AANROEP = re.compile(r'<invoke name="([\w-]+)">(.*?)</invoke>', re.S)
_PARAMETER = re.compile(r'<parameter name="([\w-]+)">(.*?)</parameter>', re.S)


def _invoer(naam: str, binnen: str) -> dict[str, Any] | None:
    """De argumenten van een als tekst geschreven aanroep, of None als ze niet bij het schema passen."""
    schema = SJABLONEN[naam].schema["input_schema"]
    invoer: dict[str, Any] = {}
    for sleutel, waarde in _PARAMETER.findall(binnen):
        soort = schema["properties"].get(sleutel, {}).get("type")
        if soort is None:
            return None
        if soort == "string":
            invoer[sleutel] = waarde.strip()
            continue
        try:
            invoer[sleutel] = json.loads(waarde)
        except ValueError:
            return None
    return invoer if all(k in invoer for k in schema.get("required", [])) else None


def sjabloon_uit_tekst(tekst: list[str], namen: frozenset[str]) -> dict[str, Any] | None:
    """Een sjabloonaanroep die het model als tekst schreef, als echte aanroep.

    Soms schrijft het model de aanroep uit (`<invoke name="antwoord_annotaties">…`) in plaats van de tool aan te
    roepen. Die tekst is geen antwoord: de jurist kreeg markup te zien en geen blokken. Wat niet bij het schema past,
    blijft gewoon tekst."""
    for naam, binnen in _AANROEP.findall("\n".join(tekst)):
        if naam in namen and (invoer := _invoer(naam, binnen)) is not None:
            return {"id": f"toolu_tekst_{uuid4().hex}", "name": naam, "input": invoer}
    return None
