"""De workflow voor de tekst van een bepaling (ADR-010, laag 2; D1): ophalen en vullen in code, hoogstens één
modelaanroep voor een korte toelichting.

De supervisor zet `bepalingsvraag` als de vraag eenduidig één artikel (en hoogstens één lid) van één regeling aanwijst
(`bepaling_workflow.lees`). Lukt het ophalen of vullen niet, dan gaat de beurt naar de agent, die het op de gewone
manier doet: deze route geeft nooit een halve tekst. Daarna volgen `verify` en `finalize` zoals bij elk sjabloon.
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from bronmodel.antwoord import antwoord_tekst
from langgraph.config import get_stream_writer

from .. import bepaling_workflow as wf
from ..narratie import _stap
from ..sjablonen.vullen import vindplaats_van
from ..state import State
from ..tool_execution import execute_tool
from .context import Bouw
from .sjabloon import _met_regelingen


def bepaling_node(b: Bouw, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    v = wf.Bepalingsvraag(**state["bepalingsvraag"])

    def voer_uit(tool: str, args: dict[str, Any]) -> str:
        return execute_tool(b, state, writer, {"id": uuid4().hex, "name": tool, "input": args})

    trace = wf.haal(b.graph, v, voer_uit)
    kaal = wf.antwoord(v, trace) if trace else None
    if kaal is None:
        _stap(writer, "Lex", "kon de tekst niet in één keer ophalen; zoekt verder")
        return {"bepalingsvraag": {}}
    tekst = "\n\n".join(item.tekst for item in kaal.blokken[0].items)
    toelichting = wf.schrijf_toelichting(b.llm, b.model, f"{vindplaats_van(v.iri).label}\n\n{tekst}")
    antwoord = wf.antwoord(v, trace, toelichting) or kaal
    _met_regelingen(b, antwoord)
    uit = antwoord_tekst(antwoord)
    return {
        "answer": uit,
        "antwoord": antwoord.model_dump(),
        "source_trace": [*state.get("source_trace", []), *trace],
        "messages": [{"role": "assistant", "content": [{"type": "text", "text": uit}]}],
    }


def route_na_bepaling(b: Bouw, state: State) -> str:
    """Met een antwoord naar de controle; zonder (niet op te halen) naar de agent."""
    return "verify" if state.get("antwoord") else "agent"
