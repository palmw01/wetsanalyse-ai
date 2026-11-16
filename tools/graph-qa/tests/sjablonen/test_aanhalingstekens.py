"""Eén stijl aanhalingstekens in wat Lex zegt: “…”, zoals de werkplek (melding gebruiker 16 nov 2026).

“…” (laag openen) stond door elkaar met “…”; in het denkproces leek dat op een haakje dat niet klopt. Een parser die
wat het model of de gebruiker typte leest, herkent beide vormen nog: alleen daar mag “ staan.
"""
from __future__ import annotations

import re
from pathlib import Path

GRAPHQA = Path(__file__).resolve().parents[2]
# De agent en de spoorregels in het bronmodel (de connectors): beide komen in beeld.
MAPPEN = (GRAPHQA / "agent", GRAPHQA.parents[1] / "packages" / "bronmodel" / "bronmodel")
# Regels die tekst lezen of opschonen, geen tekst maken.
LAAG = "\u201e"  # „, als escape: een zoek-en-vervang over de bestanden raakt deze toets dan niet
_PARSER = re.compile(r"re\.(compile|findall|sub|search|match)|maketrans|\.strip\('|_PAREN|for t in \(")


def test_geen_lage_aanhalingstekens_in_uitvoer():
    fout = [f"{p.name}:{i}" for map_ in MAPPEN for p in sorted(map_.rglob("*.py"))
            for i, regel in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if LAAG in regel and not _PARSER.search(regel)]
    assert not fout, "gebruik “…” in plaats van de lage vorm: " + ", ".join(fout)
