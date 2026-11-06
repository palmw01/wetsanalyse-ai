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

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from bronmodel.antwoord import Antwoord

from .begrip import SCHEMA as _BEGRIP, vul as _vul_begrip
from .vullen import Onvulbaar, Trace

__all__ = ["Onvulbaar", "Sjabloon", "SJABLONEN", "sjabloon_schemas", "vul"]


@dataclass(frozen=True)
class Sjabloon:
    schema: dict[str, Any]
    vul: Callable[[dict[str, Any], Trace], Antwoord]


SJABLONEN: dict[str, Sjabloon] = {_BEGRIP["name"]: Sjabloon(_BEGRIP, _vul_begrip)}


def sjabloon_schemas(namen: frozenset[str]) -> list[dict[str, Any]]:
    return [SJABLONEN[n].schema for n in sorted(namen)]


def vul(naam: str, invoer: dict[str, Any], trace: Trace) -> Antwoord:
    return SJABLONEN[naam].vul(invoer, trace)
