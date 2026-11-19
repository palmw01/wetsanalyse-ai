"""De gaten van een afleidingsregel in de skill tegen de methode, het register en de gegenereerde kopie in de api.

Het bestand is een build-input (ADR-018 besluit 7.6): de api krijgt het gegenereerd (`genereer_regelgaten.py`). Een gat
dat de skill noemt en de api niet kent, of omgekeerd, maakt de volledigheidstoets stil onvolledig.
"""
from __future__ import annotations

import json
import re
import runpy

from routeboek import WORTEL

SKILL = WORTEL / ".claude" / "skills" / "wetsanalyse"
DATA = json.loads((SKILL / "regelgaten.json").read_text(encoding="utf-8"))
REGISTER = (SKILL / "references" / "bronnen.md").read_text(encoding="utf-8")
UITLEG = (SKILL / "references" / "afleidingsregels.md").read_text(encoding="utf-8")


def test_de_skill_noemt_dezelfde_gaten_in_dezelfde_volgorde():
    deel = UITLEG[UITLEG.index("## Wat een regel mist"):]
    deel = deel[:deel.index("\n## ", 5)] if "\n## " in deel[5:] else deel
    assert re.findall(r"^- `([a-z_]+)`:", deel, re.M) == list(DATA["gaten"])


def test_elk_gat_rust_op_een_bron_uit_het_register():
    for code, g in DATA["gaten"].items():
        for b in g["bron"]:
            m = re.match(r"(M\d\d)\b", b)
            assert m and f"| {m.group(1)} |" in REGISTER, f"{code}: {b} staat niet in bronnen.md"


def test_de_gaten_van_bijlage_a_staan_erin():
    """De zeven van de regelspecialist en de zes die de methode noemt (ADR-018 bijlage A §4.2)."""
    herkomst = {g["herkomst"] for g in DATA["gaten"].values()}
    assert herkomst == {"regelspecialist", "methode"}
    assert sum(g["herkomst"] == "methode" for g in DATA["gaten"].values()) >= 6


def test_de_kopie_in_de_api_is_gegenereerd():
    gen = runpy.run_path(str(WORTEL / "tools" / "graph-qa" / "scripts" / "genereer_regelgaten.py"))
    for doel, inhoud in gen["genereer"]().items():
        assert doel.read_text(encoding="utf-8") == inhoud, f"{doel} loopt uit de pas: draai genereer_regelgaten.py"
