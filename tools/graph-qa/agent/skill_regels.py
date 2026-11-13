"""Regels uit een methode-skill (ADR-014 §7, S6), achter de proefvlag `SKILL_REGELS`.

De skill wetsanalyse mag regelsets meebrengen onder `regels/jas/` en `regels/begrippen/`; een andere methode niet, want
beide ketens zijn van wetsanalyse (plan methodes scheiden, S3). De generator bundelt ze in het
methodepakket (`PAKKET["regels"]`), want het image bevat de skillmap niet. Hij toetst ook het id-voorvoegsel, de vier
testsoorten en dat de bewijscode al een verklaring heeft.

De laders (`jas_pipeline/detectoren/regels.py`, `begrippen_pipeline/patronen.py`) nemen ze alleen mee als de vlag
aanstaat. De vlag staat standaard uit en alleen op acceptatie aan (`main.bicep:skillRegels`, met een poort-guard), tot
een meting beslist: een regel uit een skill verandert wat Lex annoteert.

Met de vlag uit is de uitkomst bitgelijk aan zonder deze code. De catalogus toont de regelsets altijd, met `straat`.
"""
from __future__ import annotations

import os
from typing import Any

from . import methodepakket

#: De straatvlag; de catalogus noemt hem bij elke regelset uit een skill.
VLAG = "SKILL_REGELS"


def aan() -> bool:
    return os.environ.get(VLAG, "").strip().lower() in ("1", "true", "ja", "yes")


def regelsets(keten: str) -> dict[str, list[dict[str, Any]]]:
    """Alle regelsets uit skills voor deze keten (`jas` of `begrippen`), op `<skill>.<familie>`, ook met de vlag uit."""
    return dict(methodepakket.PAKKET.get("regels", {}).get(keten, {}))


def actief(keten: str) -> dict[str, list[dict[str, Any]]]:
    """Wat de keten in deze straat meeneemt: niets met de vlag uit."""
    return regelsets(keten) if aan() else {}
