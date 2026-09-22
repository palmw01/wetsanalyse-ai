"""De leesroute: eerst echt zoeken, dan pas praten.

Waarom deze node bestaat. De leesroute liet het aan het model over om `search_annotaties` aan te
roepen. Op 22 sep 2026 deed het dat niet: één LLM-call, nul tools, geen enkele zoekopdracht bij de
api – en omdat er dan geen annotatiebewijs in de `source_trace` staat, verving `begrens_antwoord`
het antwoord door "Ik heb de opgeslagen annotaties niet kunnen raadplegen". De jurist las een
non-antwoord op een vraag die gewoon te beantwoorden was.

Een strengere prompt lost dat niet op; die vraagt het model opnieuw om iets te onthouden. De
annotatieroute deed het daarom al anders: die haalt de bron deterministisch op (`lees_bron`) vóór
de eerste LLM-call. Deze node doet hetzelfde voor de leesroute – zoeken is hier geen keuze meer,
maar een stap in de keten.

Het resultaat gaat als echt `tool_use`/`tool_result`-paar de historie in, precies zoals `tools_node`
dat doet: dan blijft het bewijs, niet een instructie, en blijven de bestaande knip- en
krimp-helpers kloppen.
"""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from langgraph.config import get_stream_writer

from ..doel import _bepaal_doel
from ..jas_klassen import klassen_in_tekst
from ..narratie import _stap
from ..state import State
from ..tool_execution import execute_tool, read_port
from ..tools.annotatie_tools import dispatch_annotatie

#: De api hanteert dezelfde standaard; expliciet meesturen maakt het event leesbaar.
LIMIET = 25


def zoekfilters(state: State) -> dict[str, Any]:
    """De filters voor de eerste zoekopdracht, afgeleid uit de vraag en het meegegeven doel.

    Bewust karig: wat hier niet met zekerheid uit de vraag volgt, laten we aan het model – dat heeft
    de tools nog en kan gericht verfijnen. Een verkeerd geraden filter is erger dan een breed
    resultaat, want dat levert stil te weinig treffers op.
    """
    filters: dict[str, Any] = {"limit": LIMIET}
    klassen = klassen_in_tekst(state.get("question", "") or "")
    if klassen:
        filters["jas_klassen"] = klassen
    # Alleen wat de werkplek zelf meegaf: `search_annotaties` kent bron_iri en bwb_id, geen
    # artikel/lid (zie `Zoekvraag` in de api).
    doel = _bepaal_doel(state) or {}
    if doel.get("bron_iri"):
        filters["bron_iri"] = doel["bron_iri"]
        filters["scope"] = "subtree"
    elif doel.get("bwbId") or doel.get("bwb_id"):
        filters["bwb_id"] = doel.get("bwbId") or doel.get("bwb_id")
    return filters


def _filterregel(filters: dict[str, Any]) -> str:
    delen = []
    if filters.get("jas_klassen"):
        delen.append(", ".join(filters["jas_klassen"]))
    if filters.get("bron_iri") or filters.get("bwb_id"):
        delen.append(str(filters.get("bron_iri") or filters.get("bwb_id")))
    return " · ".join(delen) or "alle opgeslagen annotaties"


def zoek_annotaties_node(b, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    filters = zoekfilters(state)
    _stap(writer, "Annotaties", f"zoeken: {_filterregel(filters)}")
    call_id = uuid4().hex
    tool = {"id": call_id, "name": "search_annotaties", "input": filters}
    port = read_port(b, state)
    # `operation` omzeilt de whitelistcheck van de leesroute (dit ís de leesroute) en levert echte
    # tool_execution-events, zodat het spoor in de werkplek klopt.
    raw = execute_tool(b, state, writer, tool,
                       operation=lambda: dispatch_annotatie("search_annotaties", filters, port))
    try:
        data = json.loads(raw)
    except ValueError:
        data = {}
    aantal = len(data.get("resultaten") or []) if isinstance(data, dict) else 0
    _stap(writer, "Annotaties", f"{aantal} treffer(s)")
    toelichting = (
        "Deze zoekopdracht is al voor je uitgevoerd; herhaal hem niet met dezelfde filters. "
        "Beantwoord de vraag op basis van dit resultaat en noem de gebruikte filters en de "
        "reikwijdte, ook als er geen treffers zijn. Gebruik get_annotatie voor detail, of "
        "search_annotaties met ándere filters."
    )
    return {
        # `execute_tool` vult de trace niet – dat doet alleen `tools_node`. Zonder deze regel ziet
        # `begrens_antwoord` geen bewijs en vervangt het antwoord alsnog.
        "source_trace": [*state.get("source_trace", []), ("search_annotaties", raw)],
        "messages": [
            {"role": "assistant", "content": [{"type": "tool_use", "id": call_id,
                                               "name": "search_annotaties", "input": filters}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": call_id,
                                          "content": raw},
                                         {"type": "text", "text": toelichting}]},
        ],
    }
