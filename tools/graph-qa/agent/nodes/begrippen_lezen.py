"""De leesroute voor begrippen (fase F4): eerst echt zoeken, dan pas praten.

Dezelfde reden als `annotatie_lezen.py`: laat je het aan het model over om `search_begrippen` aan te
roepen, dan antwoordt het soms zonder te zoeken. Deze node zoekt vóór de eerste LLM-call en zet het
resultaat als echt `tool_use`/`tool_result`-paar in de historie.

De filters zijn karig: een status als de vraag die noemt, een zoekterm alleen als de vraag hem
aanwijst ("het begrip termijn", "termijn als begrip", of tussen aanhalingstekens). Een verkeerd
geraden zoekterm levert stil te weinig op; het model kan daarna zelf verfijnen.
"""
from __future__ import annotations

import json
import re
from typing import Any
from uuid import uuid4

from langgraph.config import get_stream_writer

from ..narratie import _stap
from ..state import State
from ..tool_execution import begrip_port, execute_tool
from ..tools.begrip_tools import STATUSSEN, dispatch_begrip

LIMIET = 25

_STATUS = {"geaccordeerd": re.compile(r"\bgeaccordeerd\w*\b|\baccordeerd\w*\b"),
           "concept": re.compile(r"\bconcept(en)?\b"),
           "vervangen": re.compile(r"\bvervangen\b")}
_AANHALING = re.compile(r"[\"“”'‘’]([^\"“”'‘’]{2,80})[\"“”'‘’]")
_HET_BEGRIP = re.compile(r"\bhet begrip\s+([\w\-]+(?:\s+[\w\-]+){0,2}?)(?=\s+(?:in|uit|van|als|met|dat|die|al|nog|wel|"
                         r"ook|staat|is|bestaat|vastgelegd|geaccordeerd)\b|\s*[?.!,;:]|\s*$)")
_ALS_BEGRIP = re.compile(r"\b([\w\-]+(?:\s+[\w\-]+){0,2}?)\s+als begrip\b")
_STOP = {"er", "het", "de", "een", "dit", "dat", "staat", "is", "we", "wij", "ons"}


def _vraag(state: State) -> str:
    return state.get("zelfstandige_vraag") or state.get("question", "") or ""


def zoekterm_uit(vraag: str) -> str:
    if m := _AANHALING.search(vraag):
        return m.group(1).strip()
    q = vraag.casefold()
    for patroon in (_HET_BEGRIP, _ALS_BEGRIP):
        if m := patroon.search(q):
            woorden = [w for w in m.group(1).split() if w not in _STOP]
            if woorden:
                return " ".join(woorden)
    return ""


def zoekfilters(state: State) -> dict[str, Any]:
    q = _vraag(state).casefold()
    filters: dict[str, Any] = {"limit": LIMIET}
    if term := zoekterm_uit(_vraag(state)):
        filters["zoekterm"] = term
    statussen = [s for s in STATUSSEN if _STATUS[s].search(q)]
    if statussen:
        filters["status"] = statussen
    return filters


def _filterregel(filters: dict[str, Any]) -> str:
    delen = []
    if filters.get("zoekterm"):
        delen.append(f"“{filters['zoekterm']}”")
    if filters.get("status"):
        delen.append(", ".join(filters["status"]))
    return " · ".join(delen) or "alle vastgelegde begrippen"


def zoek_begrippen_node(b, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    filters = zoekfilters(state)
    _stap(writer, "Begrippen", f"zoeken: {_filterregel(filters)}")
    call_id = uuid4().hex
    tool = {"id": call_id, "name": "search_begrippen", "input": filters}
    port = begrip_port(b, state)
    raw = execute_tool(b, state, writer, tool,
                       operation=lambda: dispatch_begrip("search_begrippen", filters, b.graph, port))
    try:
        data = json.loads(raw)
    except ValueError:
        data = {}
    aantal = len(data.get("resultaten") or []) if isinstance(data, dict) else 0
    _stap(writer, "Begrippen", f"{aantal} begrip(pen)")
    toelichting = (
        "Deze zoekopdracht is al voor je uitgevoerd; herhaal hem niet met dezelfde filters. "
        "Beantwoord de vraag op basis van dit resultaat; noem per begrip de status en het werkgebied, "
        "en de gebruikte filters, ook als er geen treffers zijn. Gebruik get_begrip voor passages en "
        "relaties, of search_begrippen met een ándere zoekterm."
    )
    return {
        "source_trace": [*state.get("source_trace", []), ("search_begrippen", raw)],
        "messages": [
            {"role": "assistant", "content": [{"type": "tool_use", "id": call_id,
                                               "name": "search_begrippen", "input": filters}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": call_id, "content": raw},
                                         {"type": "text", "text": toelichting}]},
        ],
    }
