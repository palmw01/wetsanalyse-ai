"""
JAS-kennistool – een pure Python-functie over de JAS-specificatie.

`jas_klasse_opvragen` geeft de omschrijving, herkenningsvraag en uitdrukkingswijze
van één klasse (de bronvelden uit de Rijksspecificatie), en daarnaast de toelichting uit
de skill: subklassen, samenhang en afbakening tegenover verwarbare klassen
(`agent/jas_toelichting.py`, plan methodes scheiden G2). De duiding-specialist krijgt hem (`agent/specialists.py`); hij
staat in `JAS_TOOLS`, apart van `TOOLS`, zodat hij alleen meedoet als een
specialist hem bij naam noemt (`anthropic_schemas(only=...)`).

`jas_regels_opvragen` (prioriteitsregels voor een klassepaar) is in november 2026
weggehaald: geen specialist bood hem aan. Hij staat in de git-historie.
"""
from __future__ import annotations

import json
from typing import Any

from ..jas_klassen import GELDIGE_JAS_KLASSEN, JAS_KLASSEN
from ..jas_toelichting import TOELICHTING

# ---------------------------------------------------------------------------
# Handlers (pure functies – geen GraphPort)
# ---------------------------------------------------------------------------


def _jas_klasse_opvragen(naam: str) -> str:
    """Geef de volledige JAS-specificatie van één klasse als JSON-string.

    Returns JSON met: naam, omschrijving, vraag, uitdrukkingswijze.
    Geeft een foutmelding als de klasse niet bestaat.
    """
    naam = naam.strip()
    klasse = next((k for k in JAS_KLASSEN if k.naam == naam), None)
    if klasse is None:
        geldige = ", ".join(sorted(GELDIGE_JAS_KLASSEN))
        return json.dumps({
            "fout": f"Onbekende JAS-klasse: '{naam}'. Geldige klassen: {geldige}.",
        }, ensure_ascii=False)
    return json.dumps({
        "naam": klasse.naam,
        "omschrijving": klasse.omschrijving,
        "vraag": klasse.vraag,
        "uitdrukkingswijze": klasse.uitdrukkingswijze,
        **TOELICHTING.get(klasse.naam, {}),
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool-schema's (Anthropic Messages API formaat)
# ---------------------------------------------------------------------------

JAS_TOOLS: list[dict[str, Any]] = [
    {
        "name": "jas_klasse_opvragen",
        "description": (
            "Geef de volledige JAS-specificatie van één klasse: omschrijving, herkenningsvraag "
            "en uitdrukkingswijze, en uit de methode de subklassen, de samenhang met andere klassen "
            "en de afbakening tegenover klassen waarmee zij verward wordt. Gebruik dit als je "
            "twijfelt of een fragment bij een bepaalde klasse past, of tussen twee klassen."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "naam": {
                    "type": "string",
                    "description": "Exacte naam van de JAS-klasse, bijv. 'Rechtssubject'.",
                },
            },
            "required": ["naam"],
            "additionalProperties": False,
        },
        "handler": lambda _graph, args: _jas_klasse_opvragen(args.get("naam", "")),
    },
]

JAS_TOOL_NAMEN: frozenset[str] = frozenset(t["name"] for t in JAS_TOOLS)
