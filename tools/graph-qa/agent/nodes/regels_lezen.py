"""De leesroute voor afleidingsregels (ADR-010: routering in code; regels herleidbaar, 20 nov 2026): eerst zoeken, dan
pas praten. Het patroon van `begrippen_lezen.py`.

Laat je het aan het model over, dan antwoordt het uit de wettekst zonder de regels te lezen (lichte meting #1792, run
f2b676ee). Deze node zoekt vóór de eerste modelaanroep met `search_regels` (in het werkgebied van het gesprek, met het
onderwerp uit de vraag als zoekterm) en leest bij weinig treffers elke regel met `get_regel`, zodat de dragers met hun
vindplaats er al staan. Beide gaan als echte `tool_use`/`tool_result`-paren de historie in; het profiel `regels_lezen`
formuleert, en kan de wettekst van een drager ophalen om te citeren.

De zoekterm is karig: een verkeerd geraden term levert stil te weinig op. Vindt de term niets, dan zoekt de route
zonder term, zodat de regels van het werkgebied er toch staan.
"""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from langgraph.config import get_stream_writer

from ..narratie import _stap
from ..state import State
from ..tool_execution import execute_tool, regel_port
from ..tools.regel_tools import dispatch_regel, zoekterm_regel

LIMIET = 12
#: Bij hoogstens zoveel treffers leest de route elke regel ook (`get_regel`): de vraag gaat dan meestal over hen.
MAX_LEZEN = 3


def _vraag(state: State) -> str:
    return state.get("zelfstandige_vraag") or state.get("question", "") or ""


def _paar(name: str, invoer: dict[str, Any], raw: str) -> tuple[dict, dict, str]:
    call_id = uuid4().hex
    return ({"type": "tool_use", "id": call_id, "name": name, "input": invoer},
            {"type": "tool_result", "tool_use_id": call_id, "content": raw}, call_id)


def _voer_uit(b, state: State, writer, port, name: str, invoer: dict[str, Any]) -> tuple[str, dict]:
    tool = {"id": uuid4().hex, "name": name, "input": invoer}
    raw = execute_tool(b, state, writer, tool, operation=lambda: dispatch_regel(name, invoer, port))
    try:
        data = json.loads(raw)
    except ValueError:
        data = {}
    return raw, data if isinstance(data, dict) else {}


def zoek_regels_node(b, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    port = regel_port(b, state)
    term = zoekterm_regel(_vraag(state))
    filters: dict[str, Any] = {"limit": LIMIET, **({"zoekterm": term} if term else {})}
    _stap(writer, "Afleidingsregels", f"zoeken: {f'“{term}”' if term else 'alle vastgelegde regels'}")
    aanroepen: list[tuple[str, dict[str, Any], str]] = []
    raw, data = _voer_uit(b, state, writer, port, "search_regels", filters)
    aanroepen.append(("search_regels", filters, raw))
    if term and data.get("status") == "ok" and not data.get("resultaten"):
        filters = {"limit": LIMIET}
        raw, data = _voer_uit(b, state, writer, port, "search_regels", filters)
        aanroepen.append(("search_regels", filters, raw))
    rijen = data.get("resultaten") or [] if data.get("status") == "ok" else []
    if 0 < len(rijen) <= MAX_LEZEN:
        for r in rijen:
            invoer = {"werkgebied_id": r.get("werkgebied_id", ""), "regel_id": r.get("id", "")}
            if invoer["werkgebied_id"] and invoer["regel_id"]:
                raw_r, _ = _voer_uit(b, state, writer, port, "get_regel", invoer)
                aanroepen.append(("get_regel", invoer, raw_r))
    toelichting = ("Deze aanroepen zijn al voor je uitgevoerd; herhaal ze niet met dezelfde argumenten. Beantwoord de "
                   "vraag op basis van deze regels: noem per regel de status, en waarop ze rust (de dragers met hun "
                   "vindplaats). Een regel is een analyse-uitkomst, geen wettekst: wil je de wettekst van een drager "
                   "citeren, haal die bepaling dan op met get_artikel, get_lid of get_bepaling.")
    gebruik, resultaten = [], []
    for name, invoer, uitkomst in aanroepen:
        aanroep, resultaat, _ = _paar(name, invoer, uitkomst)
        gebruik.append(aanroep)
        resultaten.append(resultaat)
    return {
        "source_trace": [*state.get("source_trace", []), *((n, r) for n, _, r in aanroepen)],
        "messages": [{"role": "assistant", "content": gebruik},
                     {"role": "user", "content": [*resultaten, {"type": "text", "text": toelichting}]}],
    }
