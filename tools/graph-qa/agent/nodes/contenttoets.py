"""De voorbereiding van de contenttoets (plan contenttoets, C2): de content in het gesprek zetten, dan toetsen.

De node leest de content en de peildatum uit de vraag (`agent.contenttoets.ontleed`) en zet ze in het bronspoor als
resultaat van `CONTENT_TOOL`: daar leest het sjabloon `antwoord_contenttoets` hem, en de controle toetst er de citaten
uit de content tegen. Naar het model gaat er niets extra: de content staat al in de vraag, dus de beurt betaalt hem
niet twee keer, en een extra bericht na de vraag zou de grens van de beurt verschuiven (`berichten.beurt_start`). Daarna
formuleert het profiel `contenttoets`.
"""
from __future__ import annotations

from typing import Any

from langgraph.config import get_stream_writer

from ..contenttoets import ontleed
from ..narratie import _stap
from ..sjablonen.contenttoets import CONTENT_TOOL, content_resultaat
from ..state import State


def _vraag(state: State) -> str:
    return state.get("question", "") or ""


def bereid_contenttoets_node(b, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    content, peildatum = ontleed(_vraag(state))
    _stap(writer, "Contenttoets", f"{len(content):,} tekens, peildatum {peildatum}".replace(",", "."))
    return {
        "source_trace": [*state.get("source_trace", []), (CONTENT_TOOL, content_resultaat(content, peildatum))],
    }
