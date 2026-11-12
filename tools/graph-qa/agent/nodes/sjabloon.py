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

from ..beurtmeting import tel_sjabloon
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
           "tekst als de melding hierboven dat zegt, en geen tekst naast de aanroep. Deze melding komt van de code, niet van de jurist: noem haar, het "
           "sjabloon of deze tool nooit in je antwoord.")


def redencode(fout: BaseException) -> str:
    """Waar de weigering vandaan kwam, zonder inhoud: de module en de functie die `Onvulbaar` gooide
    (`extern.blokken`, `duiding.vul`). Zo telt het `meting`-event weigeringen per soort zonder één melding aan te passen."""
    tb = fout.__traceback__
    while tb is not None and tb.tb_next is not None:
        tb = tb.tb_next
    if tb is None:
        return "onbekend"
    module = tb.tb_frame.f_globals.get("__name__", "").rsplit(".", 1)[-1]
    return f"{module}.{tb.tb_frame.f_code.co_name}"


def vul_aanroep(b: Bouw, state: State, tu: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Vul één sjabloonaanroep uit de trace van `state`: (het `tool_result`, de berichten erna, de rest van de update).

    Gedeeld door `sjabloon_node` en `tools_node` (een sjabloon naast graaftools): het resultaat komt in hetzelfde
    user-bericht als de andere resultaten van die ronde, want elke `tool_use` hoort zijn resultaat in het volgende bericht
    te krijgen."""
    def resultaat(tekst: str, **extra: Any) -> dict[str, Any]:
        return {"type": "tool_result", "tool_use_id": tu["id"], "content": tekst, **extra}

    try:
        antwoord = vul(tu["name"], tu.get("input") or {}, controletrace(state))
    except Onvulbaar as fout:
        logger.warning("sjabloon niet te vullen", extra={"categorie": "functioneel", "run_id": state.get("run_id", ""),
                                                         "sjabloon": tu["name"], "reden": str(fout),
                                                         "redencode": redencode(fout),
                                                         "opgehaald": len(fout.ophalen)})
        tekst, trace = _lees_wat_genoemd_is(b, state, fout)
        # Na een weigering schreef het model vaak vrije tekst (derde meting Rechtspraak, 10 nov 2026: 2 van 6 runs na een
        # tweede pagina, met afgeronde bedragen en een eigen blokcitaat). Het sjabloon hoort het antwoord te dragen.
        tekst += OPNIEUW.format(naam=tu["name"])
        return (resultaat(tekst, is_error=True), [],
                {**({"source_trace": trace} if fout.ophalen else {}),
                 **tel_sjabloon(state, "geweigerd", f"{tu['name']}:{redencode(fout)}")})
    _met_regelingen(b, antwoord)
    tekst = antwoord_tekst(antwoord)
    return (resultaat(VASTGELEGD), [{"role": "assistant", "content": [{"type": "text", "text": tekst}]}],
            {"answer": tekst, "antwoord": antwoord.model_dump(), **tel_sjabloon(state, "gevuld", tu["name"])})


def sjabloon_node(b: Bouw, state: State) -> dict[str, Any]:
    blok, na, upd = vul_aanroep(b, state, state["pending_tools"][0])
    return {"messages": [{"role": "user", "content": [blok]}, *na], "pending_tools": [], **upd}


def route_na_sjabloon(b: Bouw, state: State) -> str:
    return "verify" if state.get("antwoord") else "agent"
