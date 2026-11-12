"""Overdrachtstools van de centrale agent (ADR-016 §A1): een tool die de beurt aan een route in code geeft.

Een overdrachtstool **bouwt niets na**. Hij zet de state die de route in code nu ook zet en stuurt de beurt naar de node
die er al is; de code vult het antwoord, en het model schrijft er niets overheen. Zo is er per route één implementatie,
of de supervisor haar nu kiest of de centrale agent.

De tools zijn van de agent, niet van het profiel: `CentraleAgent` voegt ze toe (`agentvorm.py`). Een profiel kan ze niet
noemen, en een agent met alle tools (`tools: None`) krijgt ze niet: ze staan niet in de toollaag.

Een nieuwe overdracht is: een `Overdracht` hier, de doelnode in de uitgangen van `overdracht` (`voeg_overdracht_toe`) en
een test in `tests/test_centrale_agent.py`.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from bronmodel.connectors import herkende as bronnen_in_vraag
from langgraph.config import get_stream_writer

from .narratie import _stap
from .state import State

#: De profielen van de centrale agent (ADR-016 §A1): de kernset, en dezelfde agent met alle graaftools.
CENTRAAL = "centraal"
CENTRAAL_BREED = "centraal_breed"


@dataclass(frozen=True)
class Overdracht:
    naam: str
    beschrijving: str
    #: De eigenschappen van de invoer (JSON-schema); leeg = geen argumenten.
    invoer: dict[str, Any]
    #: De node waar de beurt heen gaat.
    naar: str
    #: `(state, invoer) -> de state-update van de route`, of een tekst als de code de overdracht weigert: het model
    #: krijgt die als toolresultaat en werkt verder.
    zet: Callable[[State, dict[str, Any]], dict[str, Any] | str]
    #: De profielen waarvan de agent deze tool krijgt; leeg = elk profiel van de centrale agent.
    van: frozenset[str] = frozenset()
    #: Wat het model ziet als de overdracht slaagt.
    resultaat: str = "Overgedragen."

    @property
    def schema(self) -> dict[str, Any]:
        return {"name": self.naam, "description": self.beschrijving, "strict": True,
                "input_schema": {"type": "object", "properties": self.invoer, "required": sorted(self.invoer),
                                 "additionalProperties": False}}


def _wijs_af(state: State, _invoer: dict[str, Any]) -> dict[str, Any] | str:
    """Buiten de wetgeving: de vaste tekst uit code (`afwijs_node`). Een vraag over een bron naast de wet is nooit buiten
    de scope (ADR-013): die weigert de code, zoals ze een afwijzing van de supervisor terugdraait."""
    if bronnen_in_vraag(state.get("question", "")):
        return ("Deze vraag gaat over een bron naast de wet en valt binnen de wetgeving. Zoek in die bron, of zeg dat ze "
                "in deze beurt uit staat. Wijs de vraag niet af.")
    return {"afwijzen": True}


def _meer_tools(_state: State, _invoer: dict[str, Any]) -> dict[str, Any]:
    """De overdracht aan het brede profiel, binnen dezelfde beurt: de volgende ronde draait dezelfde agent met alle
    graaftools. Het gesprek van de beurt blijft; alleen het voorvoegsel wisselt."""
    return {"specialist": CENTRAAL_BREED}


OVERDRACHT: dict[str, Overdracht] = {o.naam: o for o in (
    Overdracht(
        naam="wijs_af",
        beschrijving=("Roep dit aan als de vraag NIET over Nederlandse wet- en regelgeving gaat (het weer, actualiteit, "
                      "programmeren, rekensommen, meningen). De werkplek toont dan een vaste tekst; schrijf zelf niets. "
                      "Niet voor een vraag over een wet, een bepaling, een juridisch begrip, een werkgebied, een "
                      "annotatie of een bron naast de wet, ook niet als je er niets over vindt: zeg dat dan in tekst."),
        invoer={}, naar="afwijzen", zet=_wijs_af),
    Overdracht(
        naam="meer_tools",
        beschrijving=("Roep dit aan als je een tool nodig hebt die je nu niet hebt. Je krijgt er dan in de volgende ronde "
                      "bij: geldigheid (peildatum, versie, terugwerkende kracht), grondslagen (delegatie), "
                      "verwijst_naar_deze en referenced_by (wie verwijst naar een bepaling), bijlagen, "
                      "overzicht_onderwerp en semantic_search (breder zoeken op een onderwerp), resolve_begrip, "
                      "search_begrippen en get_begrip (vastgelegde begrippen van een werkgebied), graph_schema en "
                      "raw_sparql. Roep het alleen aan als de vraag daarom gaat; voor de tekst, de context en de "
                      "verwijzingen van een bepaling heb je alles al. Schrijf er geen tekst naast."),
        invoer={}, naar="agent", zet=_meer_tools, van=frozenset({CENTRAAL}),
        resultaat="De extra tools staan nu aan. Ga verder met de vraag."),
)}


def voor(profiel: str) -> dict[str, Overdracht]:
    """De overdrachtstools van de centrale agent met dit profiel."""
    return {n: o for n, o in OVERDRACHT.items() if not o.van or profiel in o.van}


def overdracht_node(_b: Any, state: State) -> dict[str, Any]:
    """Voer de overdrachtstool van deze ronde uit: het toolresultaat in de historie, de state van de route, en waar de
    beurt heen gaat. Weigert de code, dan gaat de beurt terug naar de agent met de reden."""
    tu = state["pending_tools"][0]
    o = OVERDRACHT[tu["name"]]
    uitkomst = o.zet(state, tu.get("input") or {})
    geweigerd = isinstance(uitkomst, str)

    def resultaat(tekst: str, **extra: Any) -> dict[str, Any]:
        return {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tu["id"], "content": tekst, **extra}]}

    if geweigerd:
        return {"messages": [resultaat(uitkomst, is_error=True)], "pending_tools": [], "overdracht_naar": ""}
    if o.naar == "afwijzen":
        _stap(get_stream_writer(), "Lex", "deze vraag valt buiten de wet- en regelgeving in de graaf", route="afgewezen")
    return {"messages": [resultaat(o.resultaat)], "pending_tools": [],
            "overdracht_naar": "" if o.naar == "agent" else o.naar, **uitkomst}


def route_na_overdracht(_b: Any, state: State) -> str:
    return state.get("overdracht_naar") or "agent"


def doelen() -> dict[str, str]:
    """De uitgangen van de node `overdracht`: elke doelnode, en terug naar de agent."""
    return {"agent": "agent", **{o.naar: o.naar for o in OVERDRACHT.values()}}
