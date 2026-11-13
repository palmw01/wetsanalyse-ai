"""Het bronpakket (ADR-016 §B1): de bronbestanden van elke skill en elk agentprofiel in dit image.

`bronpakket.json` is gegenereerd uit `.claude/skills/` en `.claude/lex-agents/` (`scripts/genereer_bronpakket.py`); bewerk
het niet met de hand. Per onderdeel de soort, de naam, de bestanden (pad naar tekst) en de hash van
`bronmodel.werkplaats.hash_van`: dezelfde rekenregel als een versie in het register van de werkplaats. Daaraan is te zien
of een versie *actief* is.

Het pakket wordt pas gelezen als iemand ernaar vraagt (de catalogus, de melding aan de api): een beurt van Lex heeft het
niet nodig.
"""
from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

PAD = Path(__file__).with_name("bronpakket.json")


@functools.cache
def pakket() -> dict[str, Any]:
    """`{"onderdelen": {"<soort>/<naam>": {soort, naam, hash, bestanden}}, "sha256": …}`. `sha256` is de hash over de
    hashes van alle onderdelen: de identiteit van het pakket."""
    return json.loads(PAD.read_text(encoding="utf-8"))


def bronhash(soort: str, naam: str) -> str:
    """De hash van de bronbestanden van dit onderdeel in het image, of leeg als het er niet in zit."""
    return pakket()["onderdelen"].get(f"{soort}/{naam}", {}).get("hash", "")
