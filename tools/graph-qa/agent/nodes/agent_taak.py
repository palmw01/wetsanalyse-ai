"""De node `agent_taak`: één taak van een agent onder de supervisor (F3c, ADR-005).

De supervisor zette agent, taak en parameters in `State.agent_taak` – met het model uit de `TAAK:`-regel,
of zonder model uit een `actie`. Deze node maakt de getypte invoer, draait de agent op de event loop van
de beurt (`agents.uitvoering.draai`; de agents praten async met de api) en zet de uitkomst om in events:

- elke stap als `status` (`Lex · …`), zoals de andere ketens;
- de samenvatting als `token` – tekst uit code, nooit van een model;
- het `artefact` en de `bevestiging` als eigen events: de beurt-driver legt ze op het bericht en het
  `opgeslagen`-event, de werkplek opent er het paneel of de knop mee.

Een ongeldige taak, een object dat ontbreekt of een storing wordt een zin in het gesprek, nooit een stille
lege beurt. Geen verify/finalize: er wordt niets over wetgeving beweerd, alleen voorgesteld.
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.config import get_stream_writer
from pydantic import ValidationError

from ..agents import Context, Uitkomst, fout, geweigerd
from ..agents import register
from ..agents.uitvoering import draai
from ..narratie import _stap
from ..state import State
from .context import Bouw

logger = logging.getLogger("graph_qa.agent_taak")

STORING = "Dat lukte nu niet: de wetsanalyse-api of de graaf haperde. Probeer het zo opnieuw; wat al bewaard was, blijft staan."
ZONDER_API = "Zonder koppeling met de wetsanalyse-api kan ik in een werkgebied niets voorstellen of bewaren."


def _maak_api(b: Bouw, user_id: str) -> Any:
    if b.agent_api is not None:
        return b.agent_api(b.settings, user_id)
    from ..wetsanalyse_api import WetsanalyseApi
    return WetsanalyseApi(b.settings, user_id)


async def _voer_uit(b: Bouw, state: State, agent: str, invoer: Any, stuur) -> Uitkomst:
    """Op de event loop van de beurt: de api-client hoort bij deze loop."""
    api = _maak_api(b, state.get("user_id", ""))
    ctx = Context(api=api, settings=b.settings, user_id=state.get("user_id", ""), run_id=state.get("run_id", ""),
                  gesprek_id=state.get("gesprek_id", ""), graph=b.graph, llm=b.llm,
                  melding=lambda bericht: _stap(stuur, "Lex", bericht),
                  gestopt=lambda: bool(b.stop_check and b.stop_check()))
    try:
        return await register.voer_uit(agent, invoer, ctx)
    except Exception:  # noqa: BLE001 – een storing is een zin in het gesprek, de oorzaak staat in het log
        logger.exception("agent-taak mislukt", extra={"categorie": "technisch", "agent": agent,
                                                      "taak": str(getattr(invoer, "taak", ""))})
        return fout(str(getattr(invoer, "taak", "")), STORING)
    finally:
        aclose = getattr(api, "aclose", None)
        if aclose is not None:
            await aclose()


def agent_taak_node(b: Bouw, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    opdracht = state.get("agent_taak") or {}
    agent, taak = opdracht.get("agent", ""), opdracht.get("taak", "")
    try:
        invoer = register.invoer(agent, taak, opdracht.get("parameters") or {})
    except (ValueError, ValidationError):
        bekend = ", ".join(register.taken(agent)) if agent in register.AGENTS else ""
        uitkomst = geweigerd(taak, "Wat wil je dat ik doe?" + (f" Ik kan hier: {bekend}." if bekend else ""))
    else:
        if not b.settings.legt_zelf_vast:
            uitkomst = fout(taak, ZONDER_API)
        else:
            uitkomst = draai(lambda stuur: _voer_uit(b, state, agent, invoer, stuur), loop=b.loop, schrijf=writer)
    tekst = uitkomst.gesprekstekst or "(geen uitkomst)"
    logger.info("agent-taak klaar", extra={"categorie": "functioneel", "agent": agent, "taak": taak,
                                           "status": uitkomst.status, "voorstellen": len(uitkomst.voorstellen),
                                           "model": bool(uitkomst.meting.get("model"))})
    writer({"type": "token", "content": tekst})
    if uitkomst.artefact:
        writer({"type": "artefact", "artefact": uitkomst.artefact})
    if uitkomst.bevestiging:
        writer({"type": "bevestiging", "bevestiging": uitkomst.bevestiging})
    _stap(writer, "Klaar", {"ok": "gedaan", "bevestiging": "wacht op je bevestiging",
                            "geweigerd": "niet gestart", "fout": "mislukt"}[uitkomst.status])
    return {"answer": tekst, "messages": [{"role": "assistant", "content": tekst}],
            "agent_uitkomst": uitkomst.model_dump()}
