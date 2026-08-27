"""Wat een node nodig heeft buiten zijn eigen state om.

De nodes waren geneste functies in `build_graph` en trokken negen dingen uit de omringende scope:
de drie poorten, de stopvlag, drie modelnamen en twee afgeleide contexthelpers. Dat werkte, maar
maakte ze onlosmakelijk van die ene functie van ruim 1300 regels. `Bouw` maakt die afhankelijkheden
expliciet: de nodes worden gewone functies met `(b, state)` en `build_graph` bindt `b` er met
`functools.partial` aan vast.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

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

    # `model` is het sterke model: annoteerder, Critic, herziener en de QA-specialisten. De router
    # en de ophaal-agent mogen apart gezet worden (`Settings.model_voor`); staat er niets, dan zijn
    # ze alle drie hetzelfde en draait de keten exact als voorheen.
    model: str
    model_router: str
    model_ophaal: str

    # Afgeleid uit de state, maar afhankelijk van settings — vandaar dat ze meereizen in plaats van
    # dat elke node ze zelf samenstelt.
    memory_context: Callable[[State], str]
    corpus: Callable[[State], str]
    advies_context: Callable[[State], str]
