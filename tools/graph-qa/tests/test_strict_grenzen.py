"""De strict schema's van één verzoek blijven binnen de grenzen van de API (structured outputs, *Schema complexity limits*).

De API maakt van alle schema's met `strict: true` in een verzoek samen één grammatica. Daarvoor gelden:
- drie gedocumenteerde grenzen: hoogstens 20 strict tools, 24 optionele parameters en 16 parameters met een union;
- daarboven een interne grens op de omvang van de grammatica, die de API niet publiceert. Overschrijden geeft een 400
  ("Schema is too complex for compilation") vóór er één token is gegenereerd.

Gemeten op acceptatie (14 nov 2026):
- op 23eb57bb (bundel 112) had de centrale agent met een connector aan 16 strict tools (~12,3k tekens schema), en elke
  eerste modelaanroep gaf die 400;
- op d2c1f585 waren het er 12 (~9,4k tekens), en dat werkte.

Deze test begrenst daarom elk profiel, met alle connectors aan, op de gedocumenteerde grenzen én op die laatst bewezen
omvang. Wil je erboven, toets dan eerst een verzoek tegen de echte API, en verhoog daarna pas de budgetten hieronder.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from agent import overdracht, profielen
from agent.agentvorm import agent_voor
from bronmodel.connectors import CONNECTORS
from fakes import make_settings

#: De gedocumenteerde grenzen van de API.
MAX_STRICT_API = 20
MAX_OPTIONEEL = 24
MAX_UNION = 16
#: De laatst bewezen omvang (d2c1f585, centraal met connector): het aantal strict tools en hun schema's in tekens.
MAX_STRICT = 12
MAX_STRICT_TEKENS = 9_500

ALLES_AAN = {naam: {"aan": True} for naam in CONNECTORS}


def _tel(schema: dict[str, Any]) -> tuple[int, int]:
    """(optionele parameters, parameters met een union) in een schema, ook genest."""
    optioneel = union = 0
    if "anyOf" in schema or isinstance(schema.get("type"), list):
        union += 1
    verplicht = set(schema.get("required") or [])
    delen = [*(schema.get("properties") or {}).values(), *([schema["items"]] if "items" in schema else []),
             *(schema.get("anyOf") or [])]
    optioneel += sum(1 for k in schema.get("properties") or {} if k not in verplicht)
    for deel in delen:
        o, u = _tel(deel)
        optioneel, union = optioneel + o, union + u
    return optioneel, union


def _agents():
    for naam in profielen.PROFIELEN:
        yield naam, agent_voor(naam)
        if naam in profielen.KIESBAAR:
            yield f"{naam} (subagent)", agent_voor(naam, subagent=True)


@pytest.mark.parametrize("naam, agent", list(_agents()), ids=lambda x: x if isinstance(x, str) else "")
def test_de_strict_schemas_van_elk_profiel_passen_bij_de_api(naam, agent):
    schemas = agent.toolschemas(make_settings(centrale_agent="aan"), None, ALLES_AAN)
    strict = [s for s in schemas if s.get("strict")]
    optioneel = union = 0
    for s in strict:
        o, u = _tel(s["input_schema"])
        optioneel, union = optioneel + o, union + u
    tekens = sum(len(json.dumps(s["input_schema"], ensure_ascii=False)) for s in strict)
    assert len(strict) <= min(MAX_STRICT_API, MAX_STRICT), f"{naam}: {sorted(s['name'] for s in strict)}"
    assert optioneel <= MAX_OPTIONEEL and union <= MAX_UNION, naam
    assert tekens <= MAX_STRICT_TEKENS, f"{naam}: {tekens} tekens strict schema"


def test_de_delegatietools_zijn_niet_strict_en_de_code_toetst_hun_invoer():
    """Hun invoer is ruim (een lijst opdrachten met zes velden), en de code toetst hem toch zelf (`overdracht`)."""
    for naam in ("subagent", "regie_plan"):
        assert overdracht.OVERDRACHT[naam].schema["strict"] is False, naam
    zet = overdracht.OVERDRACHT["subagent"].zet
    assert "object" in zet(None, {}, {"opdrachten": ["geen object", "nog een"]})
    assert "één tot" in zet(None, {}, {"opdrachten": "geen lijst"})
    assert "bestaat niet" in zet(None, {}, {"opdrachten": [{"profiel": ["x"], "doel": "Zoek."}]})
    assert "Kies de opdracht" in overdracht.OVERDRACHT["regie_plan"].zet(None, {}, {"opdracht": 3})
