"""Drift-guard: het manifest dat de api bouwt (`api/app/begrip_manifest.py`) en het `Manifest` van de
keten moeten dezelfde vorm en hetzelfde id hebben. De api kan de keten niet importeren (twee
diensten), dus beide kanten toetsen tegen `manifest-id.vectoren.json` bij de referentiesets; de
api-kant staat in `api/tests/test_begrippen_runs.py`."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.begrippen_pipeline.model import Bron, Formulering
from eval.begrippen_eval import manifest_uit

SETS = Path(__file__).resolve().parents[3] / "docs" / "wetsanalyse" / "referentieset-begrippen"
VECTOREN = json.loads((SETS / "manifest-id.vectoren.json").read_text())


@pytest.mark.parametrize("vector", VECTOREN["vectoren"], ids=lambda v: v["set"])
def test_het_manifest_id_van_de_keten_staat_vast(vector):
    d = SETS / vector["set"]
    m = manifest_uit(json.loads((d / "bronnen.json").read_text()), json.loads((d / "cases.json").read_text()))
    assert m.id == vector["manifest_id"]


def test_de_velden_van_bron_en_formulering_staan_vast():
    assert sorted(Bron.model_fields) == VECTOREN["velden"]["bron"]
    assert sorted(Formulering.model_fields) == VECTOREN["velden"]["formulering"]
