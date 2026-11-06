"""De afronding met een sjabloon (ADR-008): de sjabloontool vullen uit de trace.

Lukt dat, dan gaat de beurt door naar `verify` met de tekst die uit de blokken volgt. Lukt het niet, dan krijgt
het model te horen wat er ontbreekt en mag het verder binnen `max_turns`.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from bronmodel.antwoord import Annotaties, Antwoord, Vindplaats, antwoord_tekst
from bronmodel.vindplaats import vindplaats

from ..bronregister import controletrace
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
    open: list[tuple[Vindplaats, str]] = []
    for blok in antwoord.blokken:
        for rij in getattr(blok, "items", []):
            v = getattr(rij, "vindplaats", None)
            if isinstance(v, Vindplaats) and not v.regeling and (vp := vindplaats(v.iri)) and vp.bwb_id:
                open.append((v, vp.bwb_id))
    # Een markering draagt haar vindplaats als regel ("BWBR0004770 art. 9 lid 1"): de jurist leest liever de naam.
    markeringen = [m for blok in antwoord.blokken if isinstance(blok, Annotaties) for m in blok.items]
    namen = regelingnamen(b.graph, {bwb for _, bwb in open} | {bwb for m in markeringen for bwb in _BWB.findall(m.vindplaats)})
    for v, bwb in open:
        v.regeling = namen.get(bwb, "")
    for m in markeringen:
        m.vindplaats = _BWB.sub(lambda x: namen.get(x.group(0), x.group(0)), m.vindplaats)


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
