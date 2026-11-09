"""De vaste route voor een lijstvraag over een bron naast de wet (ADR-013, ADR-010 laag 2), zonder model.

De supervisor zet `bron_lijst` als de code de vraag helemaal kon lezen (`agent/bron_lijst.py`): de zoektool van de
connector met een volgorde, een aantal en de filters uit de vraag. Deze node roept hem één keer aan en vult het blok
`stukken` uit de rijen (`sjablonen/extern.lijsten`); een lege uitkomst is een leemte met de zoekvraag erbij. Daarna
`verify` en `finalize` zoals bij elk sjabloon. Mislukt de aanroep, dan gaat de beurt naar de agent, met het resultaat
in de historie: die zegt wat er misging.

Op acceptatie (gesprek e906567a) kostte "wat is het laatste stuk van dossier 32140" elf modelrondes en gaf twee foute
antwoorden. Hier is het één toolaanroep en nul modelrondes.
"""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from bronmodel.antwoord import Antwoord, Leemte, antwoord_tekst
from bronmodel.connectors import CONNECTORS
from langgraph.config import get_stream_writer

from ..narratie import _stap, _toolregel
from ..sjablonen.extern import lijsten, zoekvraag_tekst
from ..sjablonen.vullen import Onvulbaar
from ..state import State
from ..tool_execution import execute_tool


def bron_lijst_node(b, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    v = state.get("bron_lijst") or {}
    c = CONNECTORS[v["connector"]]
    tool = {"id": uuid4().hex, "name": v["tool"], "input": dict(v.get("args") or {})}
    _stap(writer, "Lex", _toolregel(tool))
    raw = execute_tool(b, state, writer, tool)
    paar = [{"role": "assistant", "content": [{"type": "tool_use", **tool}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool["id"], "content": raw}]}]
    trace = [(tool["name"], raw)]
    try:
        data = json.loads(raw)
    except ValueError:
        data = {}
    if data.get("status") not in ("ok", "partial"):
        # Een fout: de agent krijgt het resultaat en zegt wat er misging, met de tools voor een tweede poging.
        return {"bron_lijst": {}, "messages": paar, "source_trace": [*state.get("source_trace", []), *trace]}
    ids = [r["id"] for r in data.get("resultaten") or [] if isinstance(r, dict) and isinstance(r.get("id"), str)]
    try:
        blokken: list[Any] = lijsten(ids, trace) if ids else []
    except Onvulbaar:
        blokken = []
    if not blokken:
        zoekvraag = zoekvraag_tekst(c, data.get("zoekvraag") or {})
        blokken = [Leemte(tekst=f"Geen {c.label} gevonden die aan de zoekvraag voldoen. {zoekvraag}".strip())]
    antwoord = Antwoord(sjabloon="extern", blokken=blokken)
    uit = antwoord_tekst(antwoord)
    return {
        "answer": uit,
        "antwoord": antwoord.model_dump(),
        "source_trace": [*state.get("source_trace", []), *trace],
        # Het paar plus het antwoord: een vervolgvraag ("lees de eerste") kent de ids en de zoekvraag.
        "messages": [*paar, {"role": "assistant", "content": [{"type": "text", "text": uit}]}],
    }


def route_na_bron_lijst(b, state: State) -> str:
    """Met een antwoord naar de controle; na een fout naar de agent."""
    return "verify" if state.get("antwoord") else "agent"
