"""Eén uitvoeringsgrens voor werkelijke tool-calls en hun zichtbare levenscyclus."""
from __future__ import annotations

import json
from time import monotonic
from uuid import uuid4

import logging

from .annotatie_read import AnnotatieReadApi
from .begrip_read import BegripReadApi
from .tools import dispatch
from .tools.annotatie_tools import ANNOTATIE_TOOL_NAMEN
from .tools.begrip_tools import AFGELEIDE_TOOL_NAMEN, BEGRIP_TOOL_NAMEN
from .resultaat import BUDGET, fout, is_contract

logger = logging.getLogger(__name__)


def read_port(b, state):
    return b.annotaties or AnnotatieReadApi(b.settings, state.get("user_id", "") or b.settings.annotatie_read_user_id)


def begrip_port(b, state):
    """De leespoort voor begrippen: de rungebruiker als actor, het werkgebied van het gesprek vooraan."""
    return getattr(b, "begrippen", None) or BegripReadApi(
        b.settings, state.get("user_id", "") or b.settings.annotatie_read_user_id, state.get("werkgebied_id", "") or "")


def execute_tool(b, state, writer, tool, *, operation=None):
    name, args = tool["name"], tool.get("input") or {}
    leesroute = "annotaties_lezen" if state.get("annotaties_lezen") else "begrippen_lezen" if state.get("begrippen_lezen") else ""
    if leesroute and not operation:
        from .specialists import SPECIALISTS
        if name not in SPECIALISTS[leesroute].tools:
            return json.dumps({"status": "unavailable", "volledig": False,
                               "reden": "tool_niet_toegestaan_in_leesroute"})
    event = {"type": "tool_execution", "run_id": state.get("run_id", ""),
             "call_id": tool.get("id") or uuid4().hex, "tool": name,
             "actie": ("annotaties_lezen" if name in ANNOTATIE_TOOL_NAMEN or name == "get_annotatieweergave" else
                       "begrippen_lezen" if name in BEGRIP_TOOL_NAMEN else "bron_lezen"),
             "filters": {k: v for k, v in args.items() if k in {"klasse", "jas_klassen", "tekst", "lifecycle", "laagstatus", "tekstveld", "match", "scope", "bronversie", "inclusief_verouderd", "limit", "offset", "cursor", "herkomst", "aandacht", "subtype", "beslist_door", "met_twijfel"}},
             "doel": {k: v for k, v in args.items() if k in {"bron_iri", "bwb_id", "artikel", "lid", "id"}}}
    writer({**event, "phase": "start", "status": "running"})
    start = monotonic()
    try:
        raw = operation() if operation else dispatch(name, b.graph, args, b.settings,
                                                     annotaties=read_port(b, state), begrippen=begrip_port(b, state))
        if not isinstance(raw, str):
            raw = json.dumps(raw, ensure_ascii=False)
        try:
            data = json.loads(raw)
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        status = data.get("status", "error" if raw.startswith("Fout bij tool") else "ok")
        contract = is_contract(raw) is not None and name not in AFGELEIDE_TOOL_NAMEN
        te_groot = contract and len(raw) > BUDGET
        omvang = len(raw)
        if te_groot:
            # Een graaftool begrenst zijn eigen resultaat (`agent/resultaat.py`); lukt dat niet, dan is
            # dat een fout in die tool. Het model krijgt het NIET – ook niet ingekort: liever zichtbaar
            # geen resultaat dan onzichtbaar halve juridische informatie.
            logger.error("tool_resultaat_te_groot", extra={"tool": name, "omvang": omvang, "budget": BUDGET})
            raw = fout("resultaatcontract_overschreden",
                       f"Het resultaat van {name} past niet binnen de begroting; dit is een fout in de tool.",
                       omvang=omvang, budget=BUDGET)
            status = "error"
        results = data.get("resultaten") or ([] if not data.get("element") else [data["element"]])
        writer({**event, "phase": "end", "status": status,
                # Alleen een antwoord dat een lijst of een element dráágt heeft een aantal. De dekking
                # heeft geen van beide, en toonde daardoor altijd "0 resultaten".
                "aantal": len(results) if ((name in AFGELEIDE_TOOL_NAMEN or contract) and status in ("ok", "partial")
                                           and ("resultaten" in data or "element" in data)) else None,
                # Bij een contract is er één waarheid: `volledig`. has_more is er een afleiding van.
                "has_more": (not data.get("volledig", True)) if contract else
                            data.get("has_more", bool(data.get("cursor") or data.get("volgende_offset")))
                            if status in ("ok", "partial") else None,
                "duur_ms": round((monotonic() - start) * 1000),
                "actualiteit": {k: data[k] for k in ("snapshot_id", "peilmoment", "volledig") if k in data},
                "foutcode": ("tool_resultaat_te_groot" if te_groot else data.get("reden", ""))
                            if status not in ("ok", "partial") else "",
                **({"omvang": omvang, "budget": BUDGET} if te_groot else {})})
        # Toolresultaten worden nooit afgeknipt: elke graaftool begrenst zelf (`agent/resultaat.py`),
        # een te groot resultaat is hierboven al een foutresultaat geworden.
        return raw
    except Exception:
        writer({**event, "phase": "end", "status": "unavailable",
                "duur_ms": round((monotonic() - start) * 1000), "foutcode": "tool_mislukt"})
        raise
