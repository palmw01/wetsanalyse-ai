"""Eén uitvoeringsgrens voor werkelijke tool-calls en hun zichtbare levenscyclus."""
from __future__ import annotations

import json
from time import monotonic
from uuid import uuid4

from .agent_common import kap_toolresultaat
from .annotatie_read import AnnotatieReadApi
from .tools import dispatch
from .tools.annotatie_tools import ANNOTATIE_TOOL_NAMEN


def read_port(b, state):
    return b.annotaties or AnnotatieReadApi(b.settings, state.get("user_id", "") or b.settings.annotatie_read_user_id)


def execute_tool(b, state, writer, tool, *, operation=None):
    name, args = tool["name"], tool.get("input") or {}
    if state.get("annotaties_lezen") and not operation:
        from .specialists import SPECIALISTS
        if name not in SPECIALISTS["annotaties_lezen"].tools:
            return json.dumps({"status": "unavailable", "volledig": False,
                               "reden": "tool_niet_toegestaan_in_leesroute"})
    event = {"type": "tool_execution", "run_id": state.get("run_id", ""),
             "call_id": tool.get("id") or uuid4().hex, "tool": name,
             "actie": "annotaties_lezen" if name in ANNOTATIE_TOOL_NAMEN or name == "get_annotatieweergave" else "bron_lezen",
             "filters": {k: v for k, v in args.items() if k in {"klasse", "jas_klassen", "tekst", "lifecycle", "laagstatus", "tekstveld", "match", "scope", "bronversie", "inclusief_verouderd", "limit", "offset", "cursor"}},
             "doel": {k: v for k, v in args.items() if k in {"bron_iri", "bwb_id", "artikel", "lid", "id"}}}
    writer({**event, "phase": "start", "status": "running"})
    start = monotonic()
    try:
        raw = operation() if operation else dispatch(name, b.graph, args, b.settings,
                                                     annotaties=read_port(b, state))
        if not isinstance(raw, str):
            raw = json.dumps(raw, ensure_ascii=False)
        try:
            data = json.loads(raw)
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        status = data.get("status", "error" if raw.startswith("Fout bij tool") else "ok")
        results = data.get("resultaten") or ([] if not data.get("element") else [data["element"]])
        writer({**event, "phase": "end", "status": status,
                "aantal": len(results) if name in ANNOTATIE_TOOL_NAMEN and status in ("ok", "partial") else None,
                "has_more": data.get("has_more", bool(data.get("cursor") or data.get("volgende_offset"))) if status in ("ok", "partial") else None,
                "duur_ms": round((monotonic() - start) * 1000),
                "actualiteit": {k: data[k] for k in ("snapshot_id", "peilmoment", "volledig") if k in data},
                "foutcode": data.get("reden", "") if status not in ("ok", "partial") else ""})
        # JSON-annotatieantwoorden nooit midden in een bewijsrecord afkappen.
        return raw if name in ANNOTATIE_TOOL_NAMEN or operation else kap_toolresultaat(raw)
    except Exception:
        writer({**event, "phase": "end", "status": "unavailable",
                "duur_ms": round((monotonic() - start) * 1000), "foutcode": "tool_mislukt"})
        raise
