"""De overzichtsroute: eerst het overzicht bouwen, dan pas praten.

Een overzichtsvraag ("welke artikelen gaan over invordering?") liet het model tool, zoekterm en opbouw
kiezen en de uitkomst overtypen; dezelfde vraag gaf zo telkens een ander antwoord, een andere
bronnenlijst en een andere 3D-graaf. Deze node bouwt het overzicht deterministisch (`agent/overzicht.py`)
vóór de eerste LLM-call – zoals `annotaties_zoeken` dat voor de leesroute doet – en geeft het op drie
manieren door:

- als **`overzicht`-event**: de werkplek toont het volledig, met alle nummers, en bewaart het bij het
  bericht (dezelfde vraag → hetzelfde blok, ook na herladen);
- als echt **`tool_use`/`tool_result`-paar** in de historie (`overzicht.voor_model`): het model duidt,
  met de tellingen en de opbouw, zonder de nummerlijsten om over te typen;
- in de **`source_trace`** (`overzicht.bronrijen`): bronnen en grounding komen uit het overzicht.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from langgraph.config import get_stream_writer

from .. import overzicht as ov_mod
from ..narratie import _stap
from ..resultaat import fout
from ..state import State
from ..tool_execution import execute_tool

logger = logging.getLogger(__name__)

TOOL = "overzicht_onderwerp"


def bouw_overzicht_node(b, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    vraag = state.get("zelfstandige_vraag") or state.get("question", "")
    onderwerp = ov_mod.onderwerp_uit(vraag)
    _stap(writer, "Overzicht", f"onderwerp: {onderwerp}")
    gebouwd: dict[str, Any] = {}

    def bouw() -> str:
        gebouwd.update(ov_mod.bouw_overzicht(b.graph, vraag))
        return ov_mod.voor_model(gebouwd)

    call_id = uuid4().hex
    tool = {"id": call_id, "name": TOOL, "input": {"onderwerp": onderwerp}}
    try:
        raw = execute_tool(b, state, writer, tool, operation=bouw)
    except Exception:  # noqa: BLE001 – een storing wordt een zichtbaar foutresultaat, geen kapotte beurt
        logger.warning("overzicht niet opgebouwd", extra={"onderwerp": onderwerp}, exc_info=True)
        gebouwd.clear()
        raw = ""
    if not gebouwd:
        # Geen half overzicht: het model krijgt de fout als resultaat en zegt dat; de werkplek toont geen
        # blok, en de bronnen komen uit wat de agent daarna eventueel zelf ophaalt.
        _stap(writer, "Overzicht", "niet opgebouwd")
        raw = fout("overzicht_niet_opgebouwd", "Het overzicht kon niet uit de graaf worden opgebouwd; "
                   "zeg dat tegen de gebruiker en zoek eventueel zelf met de tools.")
        return {"messages": _paar(call_id, onderwerp, raw)}

    delen = sum(len(r["delen"]) for r in gebouwd["regelingen"])
    _stap(writer, "Overzicht", f"{delen} delen in {len(gebouwd['regelingen'])} regelingen, "
                               f"{ov_mod.aantal_bepalingen(gebouwd)} bepalingen")
    writer({"type": "overzicht", "overzicht": gebouwd})
    return {
        "overzicht": gebouwd,
        # De vindplaatsen van het hele overzicht, niet alleen wat het model las: daaruit komen de
        # bronnen, en daartegen toetst de grounding.
        "source_trace": [*state.get("source_trace", []), (TOOL, ov_mod.bronrijen(gebouwd))],
        "messages": _paar(call_id, onderwerp, raw),
    }


def _paar(call_id: str, onderwerp: str, raw: str) -> list[dict[str, Any]]:
    return [
        {"role": "assistant", "content": [{"type": "tool_use", "id": call_id, "name": TOOL,
                                           "input": {"onderwerp": onderwerp}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": call_id, "content": raw}]},
    ]
