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

import difflib
import json
from typing import Any

from ..jas_klassen import GELDIGE_JAS_KLASSEN, JAS_KLASSEN
from ..jas_toelichting import TOELICHTING

# ---------------------------------------------------------------------------
# Handlers (pure functies – geen GraphPort)
# ---------------------------------------------------------------------------


#: Gangbare namen die geen klassenaam zijn, naar de klasse (plan methodes scheiden, G2b; meting G2: "Parameterwaarde"
#: gaf een fout en kostte een ronde). De delen van een samengestelde naam ("Parameter", "parameterwaarde") vindt
#: `_klasse_van` zelf; hier staan alleen synoniemen uit de bron of de praktijk.
SYNONIEMEN: dict[str, str] = {
    "constante": "Parameter en parameterwaarde",  # H2:89: "wordt een parameter ook wel constante genoemd"
    "subject": "Rechtssubject",
    "object": "Rechtsobject",
    "plicht": "Rechtsbetrekking",
    "bevoegdheid": "Rechtsbetrekking",
    "rechtshandeling": "Rechtsfeit",
    "gebeurtenis": "Rechtsfeit",
    "afleiding": "Afleidingsregel",
    "berekening": "Afleidingsregel",
    "rekenregel": "Afleidingsregel",
    "beslisregel": "Afleidingsregel",
    "termijn": "Tijdsaanduiding",
    "tijd": "Tijdsaanduiding",
    "plaats": "Plaatsaanduiding",
    "delegatie": "Delegatiebevoegdheid en delegatie-invulling",
    "definitie": "Brondefinitie",
    "begripsbepaling": "Brondefinitie",
}


def _sleutel(naam: str) -> str:
    return " ".join(naam.casefold().replace("_", " ").split())


def _namen() -> dict[str, str]:
    """Elke naam waaronder een klasse te vinden is: de klassenaam, de delen van een samengestelde naam en de synoniemen."""
    namen = {_sleutel(k): v for k, v in SYNONIEMEN.items()}
    for k in JAS_KLASSEN:
        namen[_sleutel(k.naam)] = k.naam
        for deel in k.naam.split(" en "):
            namen[_sleutel(deel)] = k.naam
    return namen


def _klasse_van(naam: str):
    gevonden = _namen().get(_sleutel(naam))
    return next((k for k in JAS_KLASSEN if k.naam == gevonden), None)


def _jas_klasse_opvragen(naam: str) -> str:
    """Geef de volledige JAS-specificatie van één klasse als JSON-string.

    Returns JSON met: naam, omschrijving, vraag, uitdrukkingswijze en de toelichting uit de skill. Een gangbare naam
    ("Parameterwaarde", "variabele", "constante") vindt de klasse; het resultaat noemt dan ook `gevraagd`. Een naam die
    niet te vinden is, geeft een fout met de naam die het meest lijkt en de dertien klassen.
    """
    naam = naam.strip()
    klasse = _klasse_van(naam)
    if klasse is None:
        lijkt = difflib.get_close_matches(_sleutel(naam), list(_namen()), n=1, cutoff=0.6)
        geldige = ", ".join(sorted(GELDIGE_JAS_KLASSEN))
        hint = f" Bedoel je '{_namen()[lijkt[0]]}'?" if lijkt else ""
        return json.dumps({
            "fout": f"Onbekende JAS-klasse: '{naam}'.{hint} Geldige klassen: {geldige}.",
        }, ensure_ascii=False)
    return json.dumps({
        "naam": klasse.naam,
        **({"gevraagd": naam} if naam != klasse.naam else {}),
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
                    "description": "Naam van de JAS-klasse, bijv. 'Rechtssubject'; ook een deel of gangbare naam als 'Parameterwaarde'.",
                },
            },
            "required": ["naam"],
            "additionalProperties": False,
        },
        "handler": lambda _graph, args: _jas_klasse_opvragen(args.get("naam", "")),
    },
]

JAS_TOOL_NAMEN: frozenset[str] = frozenset(t["name"] for t in JAS_TOOLS)
