"""Leesbare verklaringen van de codes in een `trace` (zie `verklaringen.yaml`).

De werkplek, de exports en de vocabulairegraaf lezen dezelfde catalogus; de jurist ziet de naam,
het id staat in de tooltip.
"""
from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import yaml

PAD = Path(__file__).with_name("verklaringen.yaml")
SECTIES = ("detectie", "besluit", "twijfel", "resolutie", "validatie", "classifier")


@cache
def laad() -> dict[str, dict[str, dict[str, str]]]:
    return yaml.safe_load(PAD.read_text(encoding="utf-8"))


def naam(sectie: str, code: str) -> str:
    """De leesbare naam, of de code zelf als hij (nog) niet verklaard is – nooit een lege plek."""
    return laad().get(sectie, {}).get(code, {}).get("naam", code)


def als_dict() -> dict[str, Any]:
    return {s: dict(laad().get(s, {})) for s in SECTIES}
