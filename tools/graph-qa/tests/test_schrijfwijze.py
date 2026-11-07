"""Het SCHRIJFWIJZE-blok in de prompt is het blok uit de schrijfrichtlijn (G2b).

De richtlijn zei dat het blok "op te nemen" was, en het stond er nooit in: de toon van Lex hing alleen af van wat het
model uit zichzelf deed. Nu staat het in het stabiele deel van de prompt, en deze test houdt het gelijk met de richtlijn.
"""
from __future__ import annotations

import re
from pathlib import Path

from agent.prompts import SYSTEM_PROMPT

RICHTLIJN = Path(__file__).resolve().parents[3] / "docs" / "schrijfrichtlijn-lex.md"


def _blok() -> str:
    m = re.search(r"```\n(SCHRIJFWIJZE – .*?)\n```", RICHTLIJN.read_text(encoding="utf-8"), re.S)
    assert m, "het promptblok staat niet meer in de schrijfrichtlijn"
    return m.group(1)


def test_het_blok_uit_de_richtlijn_staat_letterlijk_in_de_prompt():
    assert _blok() in SYSTEM_PROMPT


def test_het_blok_staat_in_het_stabiele_deel_achteraan():
    """Na ANTWOORD en vóór niets dat per beurt verschilt: SYSTEM_PROMPT is het gedeelde cache-prefix."""
    assert SYSTEM_PROMPT.rstrip().endswith(_blok())
