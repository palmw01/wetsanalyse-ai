"""Uitleg zonder model (ADR-004): wat er voor en tegen een voorstel spreekt, in leesbare zinnen.

Elke zin komt uit `verklaringen.yaml` plus het bronfragment en de regel van het bewijs, en
eindigt met de rij van de beslistabel. Er komt geen modeltekst in.
"""
from __future__ import annotations

from functools import cache
from pathlib import Path

import yaml

from .model import Beslissing, Kandidaat, Polariteit

_RICHTING = {Polariteit.STEUN: "voor", Polariteit.TEGEN: "tegen", Polariteit.ONBESLIST: "open"}


@cache
def verklaringen() -> dict[str, dict[str, str]]:
    return yaml.safe_load((Path(__file__).parent / "verklaringen.yaml").read_text(encoding="utf-8"))["signalen"]


def uitleg(kandidaten: list[Kandidaat], beslissingen: dict[str, Beslissing]) -> tuple[str, ...]:
    regels: list[str] = []
    for k in kandidaten:
        for b in k.bewijs:
            naam = verklaringen().get(b.code, {}).get("naam", b.code)
            fragment = f' – "{b.fragment}"' if b.fragment else ""
            regel = f"{_RICHTING[b.polariteit]} ({b.sterkte.value}): {naam}{fragment} [{b.regel}]"
            if regel not in regels:
                regels.append(regel)
        besl = beslissingen.get(k.id)
        if besl:
            regel = f"besluit {besl.besluit.value} ({besl.regel}): {besl.reden}"
            if regel not in regels:
                regels.append(regel)
    return tuple(regels)
