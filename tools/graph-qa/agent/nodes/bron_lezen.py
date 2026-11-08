"""Een genoemd stuk direct lezen (ADR-013): de vraag noemt een id van een connector die aanstaat (`kst-35496-F`).

Het model zocht dan eerst: `zoek_kamerstukken` met verkeerde argumenten, twee pagina's van het hele dossier en pas
daarna `get_kamerstuk` – zes rondes en ruim 100k cache-tokens voor een stuk waarvan de jurist het id al gaf
(acceptatie 8 nov 2026). Net als bij een genoemd artikel beslist de code: de leestool uit de beschrijving
(`leestool`, `lees_argument`) draait vóór de eerste modelronde, als echt `tool_use`/`tool_result`-paar in de historie
en in de `source_trace`, zodat bronnen, grounding en het subsjabloon `extern` het resultaat zien. Daarna formuleert de
agent, met de tools beschikbaar voor het vervolg (een volgende pagina, een tabel).

Dezelfde vorm als de leesroute voor annotaties (`annotatie_lezen.zoek_annotaties_node`).
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from langgraph.config import get_stream_writer

from ..narratie import _stap, _toolregel
from ..state import State
from ..tool_execution import execute_tool

TOELICHTING = (
    "Deze stukken zijn al voor je opgehaald, omdat de vraag hun id noemt; haal ze niet opnieuw op en zoek ze niet. "
    "Beantwoord de vraag uit deze tekst. Is het resultaat niet volledig, haal dan alleen het vervolg op dat je nodig hebt."
)


def bron_lezen_node(b, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    gebruik, resultaten, trace = [], [], list(state.get("source_trace", []))
    for aanroep in state.get("bron_lezen") or []:
        tool = {"id": uuid4().hex, "name": aanroep["name"], "input": dict(aanroep.get("input") or {})}
        _stap(writer, "Lex", _toolregel(tool))
        raw = execute_tool(b, state, writer, tool)
        gebruik.append({"type": "tool_use", **tool})
        resultaten.append({"type": "tool_result", "tool_use_id": tool["id"], "content": raw})
        trace.append((tool["name"], raw))
    if not gebruik:
        return {"bron_lezen": []}
    return {
        # Eén keer: een volgende worker in de keten leest niet opnieuw.
        "bron_lezen": [],
        "source_trace": trace,
        "messages": [{"role": "assistant", "content": gebruik},
                     {"role": "user", "content": [*resultaten, {"type": "text", "text": TOELICHTING}]}],
    }
