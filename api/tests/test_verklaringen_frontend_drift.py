"""Drift-guard: de werkplek leest secties uit de verklaringen die de api serveert.

`frontend/lib/verklaringen.ts` noemt in `GEBRUIKTE_SECTIES` welke secties van
`GET /v1/annotatie/verklaringen` de Waarom-uitklap opzoekt. Hernoemt de generator in graph-qa er
één, dan valt de uitklap stil terug op kale codes – niets faalt, er verdwijnt alleen uitleg. Deze
test maakt dat zichtbaar.
"""
from __future__ import annotations

import re

import pytest

from app.config import PROJECT_ROOT
from app.graaf_projectie_v2 import verklaringen

VERKLARINGEN_TS = PROJECT_ROOT / "frontend" / "lib" / "verklaringen.ts"


def _secties_uit_frontend() -> list[str]:
    bron = VERKLARINGEN_TS.read_text(encoding="utf-8")
    m = re.search(r"GEBRUIKTE_SECTIES[^=]*=\s*\[([^\]]*)\]", bron)
    assert m, "GEBRUIKTE_SECTIES niet gevonden in frontend/lib/verklaringen.ts"
    return re.findall(r'"([a-z_]+)"', m.group(1))


@pytest.mark.skipif(not VERKLARINGEN_TS.exists(), reason="frontend niet aanwezig (api-only image)")
def test_frontend_leest_alleen_bestaande_secties():
    secties = _secties_uit_frontend()
    assert secties, "lege sectielijst"
    v = verklaringen()
    ontbrekend = [s for s in secties if not isinstance(v.get(s), dict) or not v[s]]
    assert not ontbrekend, f"frontend leest secties die de vocabulaire niet (meer) heeft: {ontbrekend}"


def test_elke_verklaring_heeft_naam_en_uitleg():
    v = verklaringen()
    for sectie in ("besluit", "detectie", "regels", "resolutie", "twijfel", "validatie"):
        for code, item in v[sectie].items():
            assert item.get("naam"), f"{sectie}.{code} zonder naam"
            assert "uitleg" in item, f"{sectie}.{code} zonder uitleg"
