"""TOOI: de organisatie achter een regeling als vaste URI (spoor I6).

De WTI noemt het eerstverantwoordelijke ministerie als tekst ("Financiën"). TOOI (Thesauri en
Ontologieën voor Overheidsinformatie, identifier.overheid.nl) geeft het een URI die over tijd heen
stabiel is: `https://identifier.overheid.nl/tooi/id/ministerie/mnre1090`. Het register staat als
snapshot in `tooi_ministeries.json` (CC0), met bron en datum; ook historische namen ("Justitie",
"Veiligheid en Justitie") wijzen naar het ministerie van nu. Een onbekende naam blijft tekst en wordt
gelogd – liever geen URI dan een geraden.
"""
from __future__ import annotations

import json
import logging
from functools import cache
from pathlib import Path

logger = logging.getLogger(__name__)

SNAPSHOT = Path(__file__).with_name("tooi_ministeries.json")


@cache
def _register() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def ministerie(naam: str | None) -> tuple[str, str] | None:
    """(TOOI-URI, officiële naam van nu) bij een naam uit de WTI, of None."""
    sleutel = " ".join((naam or "").split()).lower()
    if not sleutel:
        return None
    r = _register()
    uri = r["namen"].get(sleutel) or r["namen"].get(f"ministerie van {sleutel}")
    if uri is None:
        logger.warning("TOOI: onbekend ministerie", extra={"naam": naam})
        return None
    return uri, r["ministeries"][uri]
