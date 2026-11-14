"""Wat een node nodig heeft buiten zijn eigen state om.

De nodes waren geneste functies in `build_graph` en trokken negen dingen uit de omringende scope:
de drie poorten, de stopvlag, drie modelnamen en twee afgeleide contexthelpers. Dat werkte, maar
maakte ze onlosmakelijk van die ene functie van ruim 1300 regels. `Bouw` maakt die afhankelijkheden
expliciet: de nodes worden gewone functies met `(b, state)` en `build_graph` bindt `b` er met
`functools.partial` aan vast.
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from ..config import Settings
from ..ports import GraphPort, LLMPort
from ..state import State


@dataclass(frozen=True)
class Bouw:
    """De gedeelde afhankelijkheden van één gebouwde graaf."""

    settings: Settings
    llm: LLMPort
    graph: GraphPort
    stop_check: Callable[[], bool] | None

    # `model` is het sterke model: de annotatie-classifier, de reviewer en de QA-specialisten. De
    # router en de ophaal-agent mogen apart gezet worden (`Settings.model_voor`); staat er niets,
    # dan zijn ze alle drie hetzelfde.
    model: str
    model_router: str
    model_ophaal: str

    # Afgeleid uit de state, maar afhankelijk van settings — vandaar dat ze meereizen in plaats van
    # dat elke node ze zelf samenstelt.
    memory_context: Callable[[State], str]
    advies_context: Callable[[State], str]
    annotaties: object | None = None
    begrippen: object | None = None
    # De event loop van de beurt: de agents (`nodes/agent_taak.py`) draaien daarop, omdat hun api-client
    # erbij hoort. None buiten een lopende loop (een synchrone aanroep): dan een eigen loop.
    loop: Any = None
    # Voor tests: een eigen api-client voor de agents, `(settings, user_id) -> api`.
    agent_api: Callable[[Settings, str], Any] | None = None
    # Een subagent starten en stoppen (ADR-016 §A3): `agent.subagent.Kinderen`, gegeven door `api.main` (de ene ingang).
    # None zonder api (een test, een straat zonder vastleggen): dan weigert de overdracht `subagent`.
    kinderen: Any = None


@asynccontextmanager
async def met_api(b: Bouw, user_id: str) -> AsyncIterator[Any]:
    """De wetsanalyse-api namens `user_id`, gesloten na gebruik (H5, M-04). Hoort bij de event loop van de beurt: open
    hem binnen de coroutine die `agents.uitvoering.draai` uitvoert. Tests geven `Bouw.agent_api` mee."""
    if b.agent_api is not None:
        api = b.agent_api(b.settings, user_id)
    else:
        from ..wetsanalyse_api import WetsanalyseApi
        api = WetsanalyseApi(b.settings, user_id)
    try:
        yield api
    finally:
        if (aclose := getattr(api, "aclose", None)) is not None:
            await aclose()


def zeg(writer: Callable[[dict[str, Any]], Any], tekst: str, **upd: Any) -> dict[str, Any]:
    """Een zin van Lex als eindantwoord: als `token` naar de werkplek en als assistent-bericht in de historie."""
    writer({"type": "token", "content": tekst})
    return {**upd, "answer": tekst, "messages": [{"role": "assistant", "content": tekst}]}
