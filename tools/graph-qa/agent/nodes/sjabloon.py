"""De afronding met een sjabloon (ADR-008): de sjabloontool vullen uit de trace.

Lukt dat, dan gaat de beurt door naar `verify` met de tekst die uit de blokken volgt. Lukt het niet, dan krijgt
het model te horen wat er ontbreekt en mag het verder binnen `max_turns`.
"""
from __future__ import annotations

import logging
from typing import Any

from bronmodel.antwoord import Antwoord, Vindplaats, antwoord_tekst
from bronmodel.vindplaats import vindplaats

from ..bronregister import controletrace
from ..regelingnamen import regelingnamen
from ..sjablonen import Onvulbaar, vul
from ..state import State
from .context import Bouw

logger = logging.getLogger("graph_qa.orchestrator")

#: Wat het model ziet als het sjabloon gevuld is. De tekst erna staat als eigen bericht in de historie.
VASTGELEGD = "Het antwoord is vastgelegd."


def _met_regelingen(b: Bouw, antwoord: Antwoord) -> None:
    """De naam van de regeling bij elke vindplaats waar de tool-rij hem niet droeg."""
    alle = [*antwoord.doelen, *(getattr(rij, "vindplaats", None) for blok in antwoord.blokken for rij in getattr(blok, "items", []))]
    open = [(v, vp.bwb_id) for v in alle if isinstance(v, Vindplaats) and not v.regeling and (vp := vindplaats(v.iri)) and vp.bwb_id]
    namen = regelingnamen(b.graph, {bwb for _, bwb in open})
    for v, bwb in open:
        v.regeling = namen.get(bwb, "")


def sjabloon_node(b: Bouw, state: State) -> dict[str, Any]:
    tu = state["pending_tools"][0]
    def resultaat(tekst: str, **extra: Any) -> dict[str, Any]:
        return {"type": "tool_result", "tool_use_id": tu["id"], "content": tekst, **extra}

    try:
        antwoord = vul(tu["name"], tu.get("input") or {}, controletrace(state))
    except Onvulbaar as fout:
        logger.warning("sjabloon niet te vullen", extra={"categorie": "functioneel", "run_id": state.get("run_id", ""),
                                                         "sjabloon": tu["name"], "reden": str(fout)})
        return {"messages": [{"role": "user", "content": [resultaat(str(fout), is_error=True)]}], "pending_tools": []}
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
