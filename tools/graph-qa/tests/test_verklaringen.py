"""Elke code die de annotatieketen in een `trace` kan zetten, heeft een leesbare verklaring – en er
blijven geen verklaringen hangen voor codes die niet meer bestaan.

Een ontbrekende verklaring is een lege plek in de werkplek ("Waarom?") en in de export; een
verouderde is een uitleg over iets wat de keten niet meer doet."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from agent.jas_pipeline import resolver
from agent.jas_pipeline.verklaringen import SECTIES, laad, naam

PIJPLIJN = Path(__file__).resolve().parents[1] / "agent" / "jas_pipeline"


def _bron(*patronen: str) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for pat in patronen for p in PIJPLIJN.glob(pat))


def _uitgegeven() -> dict[str, set[str]]:
    regels = set()
    for f in (PIJPLIJN / "detectoren" / "regels").glob("*.yaml"):
        if not f.name.startswith("_"):
            regels |= {r["code"] for r in yaml.safe_load(f.read_text(encoding="utf-8")) or []}
    python = _bron("*.py", "detectoren/*.py")
    return {
        "detectie": regels | set(re.findall(r'Evidence\([^)]*?code="([A-Z_]+)"', python, re.S)),
        "besluit": set(re.findall(r'door="([a-z]+)"', _bron("besluit.py"))),
        "twijfel": set(re.findall(r'reden="([A-Z_]+)"', _bron("onzekerheid.py"))),
        "resolutie": {r for r, _ in resolver.TABEL.values()} | {resolver.ONGELDIG[0], resolver.TEGEN_REGEL},
        "validatie": set(re.findall(r'"([VW]_[A-Z_]+)"', _bron("validatie.py"))),
        "classifier": set(re.findall(r'"(CLASSIFIER_[A-Z_]+)', python)) - {"CLASSIFIER_ABSTAIN"}
                      | {"VALIDATION_ERROR"},
    }


@pytest.mark.parametrize("sectie", SECTIES)
def test_elke_uitgegeven_code_is_verklaard_en_niets_is_verouderd(sectie):
    uitgegeven, verklaard = _uitgegeven()[sectie], set(laad()[sectie])
    assert uitgegeven, f"de scan vond geen codes voor {sectie} – de test zelf klopt niet meer"
    assert not uitgegeven - verklaard, f"{sectie}: zonder verklaring: {sorted(uitgegeven - verklaard)}"
    assert not verklaard - uitgegeven, f"{sectie}: verklaard maar niet meer uitgegeven: {sorted(verklaard - uitgegeven)}"


def test_elke_verklaring_heeft_een_naam_en_een_uitleg():
    for sectie in SECTIES:
        for code, v in laad()[sectie].items():
            assert v.get("naam", "").strip() and v.get("uitleg", "").strip(), f"{sectie}.{code}"


def test_een_onbekende_code_valt_terug_op_zichzelf():
    assert naam("detectie", "BESTAAT_NIET") == "BESTAAT_NIET"
    assert naam("detectie", "TEMPORAL_DURATION") == "Termijn"
