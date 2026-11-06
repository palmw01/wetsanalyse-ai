"""De afronding met een sjabloon (ADR-008): de sjabloontool vullen uit de trace.

Lukt dat, dan gaat de beurt door naar `verify` met de tekst die uit de blokken volgt. Lukt het niet, dan krijgt
het model te horen wat er ontbreekt en mag het verder binnen `max_turns`.
"""
from __future__ import annotations

import logging
from typing import Any

from bronmodel.antwoord import antwoord_tekst

from ..bronregister import controletrace
from ..sjablonen import Onvulbaar, vul
from ..state import State
from .context import Bouw

logger = logging.getLogger("graph_qa.orchestrator")

#: Wat het model ziet als het sjabloon gevuld is. De tekst erna staat als eigen bericht in de historie.
VASTGELEGD = "Het antwoord is vastgelegd."


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
