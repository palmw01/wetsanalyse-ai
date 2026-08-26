"""
JAS-kennistools — pure Python-functies over de JAS-specificatie.

Fase 2B: de classificatie-agent kan deze functies aanroepen als tool in
plaats van de volledige klasse-dump in de systeemprompt te ontvangen.
Voordelen:
  - Kleinere, stabielere systeemprompt → betere prompt-caching.
  - De redenering is zichtbaar in de tool-trace (auditeerbaar per annotatie).
  - Experiment: meet accuracy en tokengebruik met/zonder tools (zie plan §2B).

Gebruik:
    from agent.tools.jas_tools import jas_klasse_opvragen, jas_regels_opvragen

    spec = jas_klasse_opvragen("Rechtssubject")
    conflict = jas_regels_opvragen("Tijdsaanduiding", "Variabele en variabelewaarde")

Integratie in anthropic_schemas():
    De twee tools zijn opgenomen in JAS_TOOLS — een aparte lijst zodat de
    orchestrator ze alleen aan de klasseer-agent geeft, niet aan de QA-agent.
    Gebruik `anthropic_schemas(only=JAS_TOOL_NAMEN)` om ze te selecteren.

STAND: aangeboden kan, aangeroepen nog niet.
    `anthropic_schemas` kent ze inmiddels (ze stonden alleen in `_BY_NAME`, dus
    `only=JAS_TOOL_NAMEN` gaf een lege lijst) en `dispatch` voert ze uit. Maar de
    node die ze zou gebruiken — `annoteer_klasseer_node` — doet een pure
    `llm.create(tools=[])` zonder agent-lus, dus in de draaiende keten roept nog
    niemand ze aan. Dat aanzetten is het eigenlijke 2B-experiment (klasse-dump uit
    de systeemprompt halen en het model laten opvragen) en hoort met een eval
    ernaast te gebeuren, niet als stille bijvangst.
"""
from __future__ import annotations

import json
from typing import Any

from ..jas_klassen import GELDIGE_JAS_KLASSEN, JAS_KLASSEN, REGELS, RegelType

# ---------------------------------------------------------------------------
# Handlers (pure functies — geen GraphPort)
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
    }, ensure_ascii=False)


def _jas_regels_opvragen(klasse_a: str, klasse_b: str) -> str:
    """Geef de JAS-prioriteitsregels die van toepassing zijn op dit klassepaar.

    Vraag: 'als een fragment zowel klasse_a als klasse_b kan zijn, welke prevaleert?'
    Returns JSON met de van toepassing zijnde regel(s) en de winnende klasse,
    of een leeg resultaat als er geen prioriteitsregel geldt.
    """
    a, b = klasse_a.strip(), klasse_b.strip()
    resultaten = []
    for regel in REGELS:
        if regel.type != RegelType.PRIORITEIT:
            continue
        if a not in regel.applies_to or b not in regel.applies_to:
            continue
        prio = dict(regel.priority)
        rang_a = prio.get(a, 0)
        rang_b = prio.get(b, 0)
        if rang_a > rang_b:
            winnaar = a
        elif rang_b > rang_a:
            winnaar = b
        else:
            winnaar = None
        resultaten.append({
            "regel_id": regel.id,
            "omschrijving": regel.description,
            "prioriteit": {k: v for k, v in prio.items() if k in (a, b)},
            "winnaar": winnaar,
        })
    if not resultaten:
        return json.dumps({
            "boodschap": (
                f"Geen prioriteitsregel gevonden voor '{a}' en '{b}'. "
                "Kies de klasse die het beste past bij de herken-vraag."
            ),
        }, ensure_ascii=False)
    return json.dumps({"regels": resultaten}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool-schema's (Anthropic Messages API formaat)
# ---------------------------------------------------------------------------

JAS_TOOLS: list[dict[str, Any]] = [
    {
        "name": "jas_klasse_opvragen",
        "description": (
            "Geef de volledige JAS-specificatie van één klasse: omschrijving, herkenningsvraag "
            "en uitdrukkingswijze. Gebruik dit als je twijfelt of een fragment bij een bepaalde "
            "klasse past."
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
    {
        "name": "jas_regels_opvragen",
        "description": (
            "Geef de prioriteitsregel(s) voor twee JAS-klassen die mogelijk allebei van "
            "toepassing zijn op hetzelfde fragment. Geeft de winnende klasse terug als er "
            "een regel geldt, anders een advies om de herken-vraag te gebruiken."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "klasse_a": {"type": "string", "description": "Eerste kandidaat-klasse."},
                "klasse_b": {"type": "string", "description": "Tweede kandidaat-klasse."},
            },
            "required": ["klasse_a", "klasse_b"],
            "additionalProperties": False,
        },
        "handler": lambda _graph, args: _jas_regels_opvragen(
            args.get("klasse_a", ""), args.get("klasse_b", "")
        ),
    },
]

JAS_TOOL_NAMEN: frozenset[str] = frozenset(t["name"] for t in JAS_TOOLS)
