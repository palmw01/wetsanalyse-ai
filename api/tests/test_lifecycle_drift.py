"""Drift-guard: wat "beoordeeld" is, staat in de api (`annotatie_v2_contracts`) en als kopie in de werkplek. Liepen die
uiteen, dan rekent het scherm een laag als klaar die de api weigert af te ronden (B19)."""
from __future__ import annotations

import re

import pytest

from app.annotatie_v2_contracts import AFGEHANDELD, BEOORDEELD
from app.config import PROJECT_ROOT

ANNOTATIE_TS = PROJECT_ROOT / "frontend" / "lib" / "annotatie.ts"


def _lijst(naam: str, bron: str) -> set[str]:
    m = re.search(rf"export const {naam}[^=]*= \[([^\]]*)\]", bron)
    assert m, f"{naam} niet gevonden in lib/annotatie.ts"
    return set(re.findall(r'"([a-z_]+)"', m.group(1)))


@pytest.mark.parametrize("naam, waarden", [("BEOORDEELD_LIFECYCLES", BEOORDEELD), ("BESLIST_LIFECYCLES", AFGEHANDELD)])
def test_de_werkplek_draagt_dezelfde_definitie(naam, waarden):
    assert _lijst(naam, ANNOTATIE_TS.read_text(encoding="utf-8")) == set(waarden)
