"""
Specialisten voor het supervisor-patroon (multi-agent).

Een specialist is een **agentprofiel** (ADR-016 §A2): een instructie bovenop SYSTEM_PROMPT plus een toegestane
tool-subset. De profielen staan in `.claude/lex-agents/<naam>.md` en komen hier binnen via het register
(`agent/profielen.py`); dit bestand leidt er alleen de vorm uit af die de antwoordlus leest. De router
(agent/orchestrator.py) kiest er één per vraag; de agent-node draait daarna de gewone agent↔tools-lus met die config.
Zo delen alle specialisten dezelfde tool-laag, grounding en geheugen – het verschil zit in gedrag en tool-bereik.
Uitbreiden of bijsturen = een profielbestand bewerken en `scripts/genereer_jas_klassen.py` draaien.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from .agentvorm import STANDAARD, agent_voor
from .profielen import PROFIELEN, tools_van


@dataclass(frozen=True)
class Specialist:
    system: str
    tools: frozenset[str] | None  # None = alle tools
    # De sjablonen waarmee deze specialist afrondt (`agent/sjablonen`, ADR-008).
    sjablonen: frozenset[str] = frozenset()
    # Wat hij doet, in één zin met wat er níét bij hoort (ADR-010 contractpunt 1); de catalogus toont het (ADR-014).
    doel: str = ""


#: Afgeleid uit het profielregister; de tools van een connector die het profiel noemt, horen erbij (ADR-013).
SPECIALISTS: dict[str, Specialist] = {
    naam: Specialist(system=p.instructie, tools=tools_van(p), sjablonen=frozenset(p.sjablonen), doel=p.beschrijving)
    for naam, p in PROFIELEN.items()
}

DEFAULT = STANDAARD


def get(name: str | None) -> Specialist:
    """Specialist op naam, met de methodetekst van zijn rol vóór zijn instructie; valt terug op 'algemeen' bij
    onbekend/leeg. De agent bouwt die tekst op (`agentvorm.Agent.instructie`)."""
    agent = agent_voor(name)
    return replace(SPECIALISTS[agent.naam], system=agent.instructie)


def methoderol(name: str | None) -> str:
    """De rol uit de skill waarvan de specialist de methodetekst krijgt (`llm_stap` toetst dat hij er staat)."""
    return agent_voor(name).methoderol
