"""Het profielregister (ADR-016 §A2): één register voor elke agent van de open laag.

Een profiel is configuratie die een Python-agent laadt: een beschrijving, een instructie en een keuze uit de tools, de
skills, de connectors en de sjablonen die de code aanbiedt. De profielen staan als Markdown in `.claude/lex-agents/`
(de vorm van een Claude Code-subagent) en zijn gebundeld in `agentprofielen.py`; dit register laadt ze als getypeerde
objecten en toetst ze tegen de grenzen **voordat** er een agent uit wordt opgebouwd. Een profiel dat iets noemt wat
niet bestaat, laat graph-qa niet starten.

De specialisten van de supervisor zijn de eerste profielen; `specialists.SPECIALISTS` is hiervan afgeleid. `kiesbaar`
zegt of een model het profiel mag kiezen: nu de supervisor, straks de centrale agent. Een profiel met `kiesbaar: false`
is een stap van een route in code.
"""
from __future__ import annotations

import hashlib
import json

from bronmodel.agentprofiel import Agentprofiel, Grenzen, valideer
from bronmodel.connectors import CONNECTORS

from .agentprofielen import REGISTER
from .methodepakket import PAKKET
from .sjablonen import SJABLONEN
from .tools import ANNOTATIE_TOOL_NAMEN, BEGRIP_TOOL_NAMEN, CONNECTOR_TOOLS, JAS_TOOL_NAMEN, TOOLS


#: De tools die alleen van wetsanalyse zijn: de annotatieleestools, de begrippenleestools en de JAS-tools. Een profiel
#: waarvan de rol geen sectie van wetsanalyse draagt, krijgt ze niet (plan methodes scheiden, S3). Gelijk aan de tools
#: die de catalogus van wetsanalyse noemt; `tests/test_methodegrenzen.py` bewaakt dat.
TOOLS_VAN_WETSANALYSE: frozenset[str] = frozenset(ANNOTATIE_TOOL_NAMEN) | frozenset(BEGRIP_TOOL_NAMEN) | frozenset(JAS_TOOL_NAMEN)


def rol_methodes(pakket: dict = PAKKET) -> dict[str, frozenset[str]]:
    """Per methoderol de methode-skills waarvan hij secties draagt, uit het methodepakket."""
    return {rol: frozenset(pakket["secties"][s]["skill"] for s in secties) for rol, secties in pakket["rollen"].items()}


def grenzen() -> Grenzen:
    """Waaruit een profiel mag kiezen, uit de registers van graph-qa. De tools van een connector noemt een profiel niet
    met de hand: het noemt de connector, en krijgt dan zijn tools."""
    return Grenzen(
        tools=frozenset(t["name"] for t in TOOLS) - CONNECTOR_TOOLS | frozenset(JAS_TOOL_NAMEN),
        skills=frozenset(PAKKET["skills"]),
        connectors=frozenset(CONNECTORS),
        sjablonen=frozenset(SJABLONEN),
        methoderollen=frozenset(PAKKET["rollen"]),
        methode_tools={"wetsanalyse": TOOLS_VAN_WETSANALYSE},
        rol_methodes=rol_methodes(),
    )


def laad(register: dict = REGISTER) -> dict[str, Agentprofiel]:
    g = grenzen()
    return {naam: valideer(Agentprofiel(**velden), g) for naam, velden in register["profielen"].items()}


#: Elk profiel op naam, gevalideerd.
PROFIELEN: dict[str, Agentprofiel] = laad()

#: De profielen die een model mag kiezen, op naam.
KIESBAAR: tuple[str, ...] = tuple(n for n, p in PROFIELEN.items() if p.kiesbaar)


def versie(profiel: Agentprofiel) -> str:
    """De hash van een profiel: twaalf hextekens over al zijn velden. Verandert het profiel, dan verandert het gedrag.
    Dezelfde waarde staat in `model_aanroep`, in de contextopbouw en in de catalogus."""
    velden = json.dumps(profiel.model_dump(), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(velden.encode()).hexdigest()[:12]


def tools_van(profiel: Agentprofiel) -> frozenset[str] | None:
    """De tools die een agent met dit profiel mag krijgen: zijn eigen, plus die van de connectors die hij noemt
    (ADR-013). `None` is elke tool. Of een connector in een beurt aanstaat, beslist `tools.toegestane_tools`."""
    if profiel.tools is None:
        return None
    return frozenset(profiel.tools).union(*(CONNECTORS[c].tools for c in profiel.connectors))


def bedient(naam: str, connector: str) -> bool:
    """Of het profiel `naam` de connector noemt. Een onbekende naam bedient niets."""
    return naam in PROFIELEN and connector in PROFIELEN[naam].connectors
