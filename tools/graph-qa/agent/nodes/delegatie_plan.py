"""Twee nodes die een plan van de centrale agent voorleggen, zonder model (ADR-016 §A5).

- `subagent_plan`: meer dan één subagent. De overdracht `subagent` met twee of meer opdrachten zette de opdrachten in `State.subagent_plan`; deze
  node bewaart het plan bij de api als delegatie die wacht, en eindigt met de bevestiging als vraagkaart (`sa_start`).
  Een klik start ze (`nodes/subagent_vervolg.py`).
- `regie_voorstel`: de regisseur als tool. De overdracht `regie_plan` zette de opdracht (bronnen of annoteren); deze
  node maakt het plan uit de stand bij de api, met dezelfde tekst en knop als de regie zelf (`regisseur.voorstel`).

Beide schrijven alleen tekst uit code; het model schrijft er niets overheen.
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.config import get_stream_writer

from .. import subagent as sub
from ..agents.uitvoering import draai
from ..models import SubagentOpdracht
from ..narratie import _stap
from ..state import State
from ..wetsanalyse_api import WetsanalyseApiFout
from .context import Bouw, met_api

logger = logging.getLogger("graph_qa.subagent")

STORING = "Het plan kon ik niet maken: de wetsanalyse-api haperde. Vraag het zo opnieuw."


def _klaar(writer, tekst: str, **extra: Any) -> dict[str, Any]:
    writer({"type": "token", "content": tekst})
    for soort, waarde in extra.items():
        writer({"type": soort, soort: waarde})
    return {"answer": tekst, "messages": [{"role": "assistant", "content": tekst}]}


def subagent_plan_node(b: Bouw, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    _stap(writer, "Lex", "legt het plan met subagents voor", route="subagent")
    opdrachten = [(o["profiel"], SubagentOpdracht(**o["opdracht"])) for o in state.get("subagent_plan") or []]

    async def maak(_stuur) -> tuple[str, dict[str, Any] | None]:
        async with met_api(b, state.get("user_id", "")) as api:
            return await sub.plan_klaar(state, opdrachten, settings=b.settings, api=api)

    tekst, kaart = draai(maak, loop=b.loop, schrijf=writer)
    return _klaar(writer, tekst, **({"vraagkaart": kaart} if kaart else {}))


def regie_voorstel_node(b: Bouw, state: State) -> dict[str, Any]:
    from ..regie.regisseur import REGIE_PARALLEL, plan_van, voorstel

    from ..regie.regisseur import FASEN_TEKST

    writer = get_stream_writer()
    # "Werk dit werkgebied uit" (agentset M04): een plan in fasen, waarvan de eerste de bronnen zijn.
    fasen = state.get("regie_plan") == "uitwerken"
    opdracht = "bronnen" if fasen else state.get("regie_plan") or "bronnen"
    _stap(writer, "Lex", "maakt het plan voor de regie uit de stand van het werkgebied", route="regie")

    async def maak(_stuur) -> tuple[str, dict[str, Any] | None]:
        async with met_api(b, state.get("user_id", "")) as api:
            plan = await plan_van(api, state.get("werkgebied_id", ""), opdracht)
            return voorstel(plan, getattr(b.settings, "regie_parallel", REGIE_PARALLEL))

    try:
        tekst, bevestiging = draai(maak, loop=b.loop, schrijf=writer)
    except WetsanalyseApiFout:
        logger.warning("regie_plan: api-fout", extra={"categorie": "technisch"})
        return _klaar(writer, STORING)
    return _klaar(writer, (FASEN_TEKST if fasen and bevestiging else "") + tekst,
                  **({"bevestiging": bevestiging} if bevestiging else {}))
