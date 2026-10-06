"""Waar een meting haar casussen vandaan haalt: één ingang voor v1, concepten en losse bestanden.

- `v1` – de ontwikkelsplit van referentieset v1 (standaard). Held-out blijft geweigerd: die families
  mogen niet sturen wat we bouwen.
- `concept` of `concept:IW05,…` – conceptcasussen uit `referentieset/concept/`. Die zijn
  **diagnostisch**: een AI-concept dat nog geen jurist zag. Ze tonen of een fout weg is, maar tellen
  nooit mee in een v1-totaal – `controleer_niet_gemengd` bewaakt dat.
- `pad:<bestand>` – een los casusbestand (lijst of één casus), ook diagnostisch.

De profielen blijven bewust op v1 (`profielen.referentieset_pad`): hun `test_cases` toetsen tegen de
vastgestelde set, niet tegen een concept.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from agent.jas_pipeline.profielen import referentieset_map, referentieset_pad

STANDAARD = "v1"


def concept_map() -> Path:
    return referentieset_map() / "concept"


def _lees(pad: Path) -> list[dict[str, Any]]:
    data = json.loads(pad.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def bestanden(spec: str = STANDAARD) -> list[Path]:
    """De bestanden waar deze casusset uit komt; hun hash hoort in het manifest."""
    if spec == "v1":
        return [referentieset_pad()]
    if spec == "concept" or spec.startswith("concept:"):
        ids = spec.partition(":")[2]
        if not ids:
            return sorted(concept_map().glob("*.json"))
        paden = [concept_map() / f"{i.strip()}.json" for i in ids.split(",")]
        ontbreekt = [p.name for p in paden if not p.exists()]
        if ontbreekt:
            raise ValueError(f"onbekende conceptcasus: {', '.join(ontbreekt)}")
        return paden
    if spec.startswith("pad:"):
        pad = Path(spec[4:])
        if not pad.exists():
            raise ValueError(f"casusbestand bestaat niet: {pad}")
        return [pad]
    raise ValueError(f"onbekende casusbron '{spec}' (verwacht v1, concept[:ID,…] of pad:<bestand>)")


def laad(spec: str = STANDAARD) -> list[dict[str, Any]]:
    """De casussen van deze bron; buiten v1 gemarkeerd als `diagnostisch`."""
    casussen = [c for p in bestanden(spec) for c in _lees(p)]
    if spec == "v1":
        return [c for c in casussen if c.get("split") == "ontwikkeling"]
    if any(c.get("split", "ontwikkeling") != "ontwikkeling" for c in casussen):
        raise ValueError("held-out casussen niet gebruiken voor ontwikkelmetingen")
    from eval.referentieset import valideer_concept
    uit = [{**c, "diagnostisch": True} for c in casussen]
    for c in uit:
        valideer_concept(c)          # schema, letterlijkheid, tekst_sha256, status provisional
    return uit


def hashes(spec: str = STANDAARD) -> dict[str, str]:
    root = referentieset_map().parents[2]
    uit = {}
    for p in bestanden(spec):
        try:
            naam = str(p.resolve().relative_to(root))
        except ValueError:
            naam = str(p)
        uit[naam] = hashlib.sha256(p.read_bytes()).hexdigest()
    return uit


def controleer_niet_gemengd(casussen: list[dict[str, Any]]) -> None:
    """Eén aggregaat is óf v1 óf diagnostisch – nooit allebei (onderzoek §18.6)."""
    soorten = {bool(c.get("diagnostisch")) for c in casussen}
    if len(soorten) > 1:
        raise ValueError("v1- en conceptcasussen niet in één aggregaat meten; meet ze apart")
