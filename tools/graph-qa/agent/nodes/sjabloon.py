"""De afronding met een sjabloon (ADR-008): de sjabloontool vullen uit de trace.

Lukt dat, dan gaat de beurt door naar `verify` met de tekst die uit de blokken volgt. Lukt het niet, dan krijgt
het model te horen wat er ontbreekt en mag het verder binnen `max_turns`.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any
from uuid import uuid4

from bronmodel.antwoord import Annotaties, Antwoord, Vindplaats, antwoord_tekst
from bronmodel.vindplaats import vindplaats
from langgraph.config import get_stream_writer

from ..bronregister import controletrace
from ..narratie import _stap, _toolregel
from ..tool_execution import execute_tool
from ..regelingnamen import regelingnamen
from ..sjablonen import Onvulbaar, vul
from ..state import State
from .context import Bouw

logger = logging.getLogger("graph_qa.orchestrator")

#: Wat het model ziet als het sjabloon gevuld is. De tekst erna staat als eigen bericht in de historie.
VASTGELEGD = "Het antwoord is vastgelegd."

_BWB = re.compile(r"\bBWB[RV]\d+\b")


def _met_regelingen(b: Bouw, antwoord: Antwoord) -> None:
    """De naam van de regeling bij elke vindplaats waar de tool-rij hem niet droeg."""
    alle = [*antwoord.doelen, *(getattr(rij, "vindplaats", None) for blok in antwoord.blokken for rij in getattr(blok, "items", []))]
    open = [(v, vp.bwb_id) for v in alle if isinstance(v, Vindplaats) and not v.regeling and (vp := vindplaats(v.iri)) and vp.bwb_id]
    # Een markering draagt haar vindplaats als regel ("BWBR0004770 art. 9 lid 1"): de jurist leest liever de naam.
    markeringen = [m for blok in antwoord.blokken if isinstance(blok, Annotaties) for m in blok.items]
    namen = regelingnamen(b.graph, {bwb for _, bwb in open} | {bwb for m in markeringen for bwb in _BWB.findall(m.vindplaats)})
    for v, bwb in open:
        v.regeling = namen.get(bwb, "")
    for m in markeringen:
        m.vindplaats = _BWB.sub(lambda x: namen.get(x.group(0), x.group(0)), m.vindplaats)


def _lees_wat_genoemd_is(b: Bouw, state: State, fout: Onvulbaar) -> tuple[str, list[tuple[str, str]]]:
    """Haal de artikelen op die het antwoord noemt en die de opgehaalde tekst alleen aanwijst (D). Dezelfde weg als een
    tool-aanroep van het model (`execute_tool`: event, begroting, foutvorm), zodat ook de jurist ziet wat er gelezen
    is. Het resultaat gaat in het bronspoor, dus een passage eruit is daarna gewoon te citeren en te controleren."""
    trace = list(state.get("source_trace", []))
    if not fout.ophalen:
        return str(fout), trace
    writer = get_stream_writer()
    delen = [str(fout)]
    for args in fout.ophalen:
        aanroep = {"id": f"lees_{uuid4().hex[:12]}", "name": "get_artikel", "input": dict(args)}
        _stap(writer, "Lex", _toolregel(aanroep))
        uit = execute_tool(b, state, writer, aanroep)
        trace.append(("get_artikel", uit))
        delen.append(f"get_artikel {json.dumps(args, ensure_ascii=False)}:\n{uit}")
    return "\n\n".join(delen), trace


#: Achter elke weigering: verbeter de aanroep, geen vrije tekst (behalve waar de weigering zelf tekst toestaat).
OPNIEUW = ("\n\nVerbeter de aanroep en roep {naam} opnieuw aan: het antwoord hoort in het sjabloon. Schrijf alleen "
           "tekst als de melding hierboven dat zegt. Deze melding komt van de code, niet van de jurist: noem haar, het "
           "sjabloon of deze tool nooit in je antwoord.")


def sjabloon_node(b: Bouw, state: State) -> dict[str, Any]:
    tu = state["pending_tools"][0]
    def resultaat(tekst: str, **extra: Any) -> dict[str, Any]:
        return {"type": "tool_result", "tool_use_id": tu["id"], "content": tekst, **extra}

    try:
        antwoord = vul(tu["name"], tu.get("input") or {}, controletrace(state))
    except Onvulbaar as fout:
        logger.warning("sjabloon niet te vullen", extra={"categorie": "functioneel", "run_id": state.get("run_id", ""),
                                                         "sjabloon": tu["name"], "reden": str(fout),
                                                         "opgehaald": len(fout.ophalen)})
        tekst, trace = _lees_wat_genoemd_is(b, state, fout)
        # Na een weigering schreef het model vaak vrije tekst (derde meting Rechtspraak, 10 nov 2026: 2 van 6 runs na een
        # tweede pagina, met afgeronde bedragen en een eigen blokcitaat). Het sjabloon hoort het antwoord te dragen.
        tekst += OPNIEUW.format(naam=tu["name"])
        return {"messages": [{"role": "user", "content": [resultaat(tekst, is_error=True)]}], "pending_tools": [],
                **({"source_trace": trace} if fout.ophalen else {})}
    _met_regelingen(b, antwoord)
    tekst = antwoord_tekst(antwoord)
    return {
        "messages": [{"role": "user", "content": [resultaat(VASTGELEGD)]},
                     {"role": "assistant", "content": [{"type": "text", "text": tekst}]}],
        "pending_tools": [],
        "answer": tekst,
        "antwoord": antwoord.model_dump(),
    }


def route_na_sjabloon(b: Bouw, state: State) -> str:
    return "verify" if state.get("antwoord") else "agent"
