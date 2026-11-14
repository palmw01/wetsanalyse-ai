"""De agentvorm (ADR-016, randvoorwaarde): één Python-basis voor elke agent van de open laag.

Een `Agent` is een Python-object dat uit een gevalideerd `Agentprofiel` is opgebouwd. Het profiel is configuratie; de
agent is de code die haar nakomt. Hij doet twee dingen, en alleen hij:

1. **Hij bezit de antwoordketen** (`voeg_keten_toe`): agent ⇄ tools → sjabloon → verify → correct → finalize, in de ene
   LangGraph-graaf van `orchestrator.build_graph`. Er is geen tweede lus; `tests/test_graafopbouw.py` legt de vorm vast.
2. **Hij roept het model aan** (`ronde`). Elke modelaanroep van een rol met een toollus komt hiervandaan
   (`tests/test_agentvorm.py`). Wat hij meestuurt, volgt uit zijn profiel: de systeemtekst (de identiteit van Lex, de
   methodetekst van zijn rol, zijn instructie), de tools, de sjablonen, het model en de `Rol`.

De specialisten van de supervisor zijn agents met hun eigen profiel; er is geen klasse per specialist. De subklassen
die ADR-016 noemt verschillen alleen in hun eigen tools en hun uitgang: `CentraleAgent` (de overdrachtstools, waaronder
`subagent`) en `Subagent` (één uitgang, het rapport; ADR-016 §A3).

Zonder `Agent` geen modelaanroep, geen tool en geen kind: een profiel draait nooit buiten deze klasse.
"""
from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from bronmodel.agentprofiel import Agentprofiel
from bronmodel.connectors import CONNECTORS

from . import profielen
from .llm_stap import Rol, stroom
from .methode import instructies
from . import overdracht
from .overdracht import CENTRAAL, CENTRAAL_BREED, Overdracht  # noqa: F401 – CENTRAAL: re-export voor de nodes
from .prompts import SYSTEM_PROMPT
from .sjablonen import EXTERN, sjabloon_schemas
from .sjablonen.rapport import NAAM as RAPPORT
from .tools import anthropic_schemas, toegestane_tools

#: Het profiel van een agent zonder naam, of met een naam die niet bestaat.
STANDAARD = "algemeen"

#: De antwoordlus streamt, dus een ruime limiet kost alleen wat er echt geschreven wordt. 4096 kapte lange duidingen af.
MAX_TOKENS_ANTWOORD = 16000
#: De ophaal-agent schrijft geen tekst voor de jurist, alleen tool-aanroepen.
MAX_TOKENS_OPHALEN = 4096

#: Wat bij de `Rol` hoort en niet bij het profiel: de uitvoerruimte en de modelknop (`Settings.model_voor`). Alleen de
#: ophaal-agent heeft een eigen knop; wie een oordeel over wetgeving velt, draait op het sterke model.
_MAX_TOKENS = {Rol.OPHAAL: MAX_TOKENS_OPHALEN}
_MODELKNOP = {Rol.OPHAAL: "ophaal"}


@dataclass(frozen=True)
class Agent:
    """Een agent van de open laag: de antwoordketen met één profiel."""

    profiel: Agentprofiel

    @property
    def naam(self) -> str:
        return self.profiel.naam

    @property
    def versie(self) -> str:
        """De hash van het profiel: dezelfde waarde in `model_aanroep`, in de contextopbouw en in de catalogus."""
        return profielen.versie(self.profiel)

    @property
    def methoderol(self) -> str:
        """De rol uit de skill waarvan hij de methodetekst krijgt (`llm_stap` toetst dat hij er staat)."""
        return self.profiel.rol

    @property
    def rol(self) -> Rol:
        """Wie hij is voor de gedeelde modelstap: de `Rol` met een toollus die zijn methoderol vast draagt (de
        ophaal-agent), anders de antwoordrol."""
        return next((r for r in Rol if r.lus and r.methoderol == self.methoderol), Rol.ANTWOORD)

    @property
    def instructie(self) -> str:
        """De methodetekst van zijn rol, dan de instructie van het profiel."""
        return instructies(self.methoderol) + "\n\n" + self.profiel.instructie

    @property
    def systeemtekst(self) -> str:
        """Het stabiele deel van de systeemprompt: bij elke ronde van elke beurt hetzelfde, met het cachepunt erop."""
        return SYSTEM_PROMPT + f"\n\n{self.instructie}"

    @property
    def tools(self) -> frozenset[str] | None:
        """De tools die hij mag krijgen (`None` is elke tool); of een connector aanstaat, beslist `toolschemas`."""
        return profielen.tools_van(self.profiel)

    @property
    def eigen_tools(self) -> dict[str, Overdracht]:
        """De tools die bij de agent zelf horen en niet bij zijn profiel. Een gewone agent heeft er geen."""
        return {}

    def extern(self, bronstand: dict[str, Any] | None) -> tuple[str, ...]:
        """De connectors die in deze beurt aanstaan en die het profiel noemt (ADR-013). Alleen een agent die met een
        sjabloon afrondt, krijgt het veld voor bronnen naast de wet."""
        if not self.profiel.sjablonen:
            return ()
        return tuple(n for n, s in (bronstand or {}).items()
                     if s.get("aan") and n in CONNECTORS and n in self.profiel.connectors)

    def sjablonen(self, bronstand: dict[str, Any] | None) -> frozenset[str]:
        """De sjablonen waarmee hij in deze beurt afrondt: zijn eigen, en `antwoord_extern` als er een connector
        aanstaat die hij noemt."""
        eigen = frozenset(self.profiel.sjablonen)
        return eigen | {EXTERN} if self.extern(bronstand) else eigen

    def mag(self, tool: str) -> bool:
        """Of deze agent de tool `tool` mag aanroepen. Een gewone agent wordt hier niet op getoetst: zijn toolbereik
        stuurt wat het model ziet (`toolschemas`). De centrale agent wel, zie `CentraleAgent.mag`."""
        return True

    def toolschemas(self, settings: Any, bronnen: Any, bronstand: dict[str, Any] | None, *,
                    werkgebied: bool = True) -> list[dict[str, Any]]:
        """De schema's die het model ziet: zijn tools zonder die van een connector die uit staat, dan zijn eigen tools
        (zonder werkgebied zonder die van het werkgebied: per beurt vast, dus het voorvoegsel blijft binnen de beurt
        gelijk), dan zijn sjablonen."""
        return (anthropic_schemas(only=toegestane_tools(self.tools, settings, bronnen))
                + [o.schema for o in self.eigen_tools.values() if werkgebied or not o.werkgebied]
                + sjabloon_schemas(self.sjablonen(bronstand), extern=self.extern(bronstand)))

    def model(self, settings: Any) -> str:
        return settings.model_voor(_MODELKNOP.get(self.rol, ""))

    def ronde(self, llm: Any, settings: Any, *, systeem: list[str], berichten: list[dict[str, Any]],
              berichtpunten: Any, bronnen: Any, bronstand: dict[str, Any] | None, kader: dict[str, Any],
              werkgebied: bool = True) -> Any:
        """Eén ronde van de toollus: de modelaanroep met wat het profiel meegeeft. Geeft het volledige antwoord terug.

        Geen tekst tijdens het streamen: pas aan het eind van de ronde is bekend of dit narratie is of een eindantwoord,
        en een eindantwoord mag pas na de controle in beeld (`finalize_node`)."""
        with stroom(
            llm, self.rol, methoderol=self.methoderol,
            kader={**kader, "profiel_id": self.naam, "profiel_versie": self.versie},
            model=self.model(settings),
            max_tokens=_MAX_TOKENS.get(self.rol, MAX_TOKENS_ANTWOORD),
            system=systeem,
            tools=self.toolschemas(settings, bronnen, bronstand, werkgebied=werkgebied),
            messages=berichten,
            # Elke toolronde stuurt de hele historie opnieuw: een cache-punt aan het eind maakt die de volgende ronde
            # goedkoop.
            historie_cache=True,
            berichtpunten=berichtpunten,
        ) as stream:
            return stream.final_message()


class CentraleAgent(Agent):
    """De ene agent van de open laag (ADR-016 §A1): hij beantwoordt een gewone vraag zelf, en geeft de beurt met een
    overdrachtstool aan een route in code. Hij verschilt van een andere agent alleen in die eigen tools."""

    @property
    def rol(self) -> Rol:
        return Rol.CENTRAAL

    @property
    def eigen_tools(self) -> dict[str, Overdracht]:
        return overdracht.voor(self.naam)

    def mag(self, tool: str) -> bool:
        """Een tool buiten zijn profiel voert de code niet uit, ook als het model hem toch aanroept: een tool buiten de
        kernset kan alleen na de overdracht `meer_tools`."""
        return self.tools is None or tool in self.tools or tool in self.eigen_tools or tool in self.profiel.sjablonen \
            or tool == EXTERN


#: Wat een subagent bovenop zijn profiel hoort (ADR-016 §A3, §A4). Na de instructie van het profiel, want die zegt
#: waarmee hij als specialist afrondt.
SUBAGENT_INSTRUCTIE = (
    "JE BENT EEN SUBAGENT. Je werkt aan één opdracht van de centrale agent van Lex; je spreekt de gebruiker niet "
    "rechtstreeks. De opdracht staat in het eerste bericht. Doe wat de opdracht vraagt, binnen wat erbij hoort, en haal in "
    "één ronde op wat je samen nodig hebt. Hangt wat je oplevert af van een afbakening of een feit dat de opdracht niet "
    "geeft (een periode, een regeling, welke situatie of lezing), kies die dan niet zelf, ook niet 'de meest recente': rond "
    "af met status vraag en stel de vraag in 'vragen', met wat je al zonder die keuze vond in de bevindingen. Je rondt "
    "altijd af met het sjabloon rapport, als laatste stap en "
    "zonder tekst ernaast: niet met een antwoordsjabloon en niet in tekst, ook niet als het niet lukte (status "
    "niet_gelukt). Weigert de code het rapport, verbeter dan de aanroep zoals de melding zegt en roep het opnieuw aan.")


class Subagent(Agent):
    """Een agent die werkt aan één opdracht van de centrale agent (ADR-016 §A3): zijn eigen profiel, met één uitgang,
    het rapport (§A4). Hij heeft geen eigen tools: geen overdracht en geen `subagent` (één laag)."""

    @property
    def instructie(self) -> str:
        return super().instructie + "\n\n" + SUBAGENT_INSTRUCTIE

    def extern(self, bronstand: dict[str, Any] | None) -> tuple[str, ...]:
        """Het rapport krijgt het veld voor bronnen naast de wet, als er een connector aanstaat die zijn profiel noemt."""
        return tuple(n for n, s in (bronstand or {}).items()
                     if s.get("aan") and n in CONNECTORS and n in self.profiel.connectors)

    def sjablonen(self, bronstand: dict[str, Any] | None) -> frozenset[str]:
        return frozenset({RAPPORT})


def agent_voor(naam: str | None, *, subagent: bool = False) -> Agent:
    """De agent met het profiel `naam`; zonder naam of met een onbekende naam het brede profiel. Met `subagent` dezelfde
    agent als subagent: het profiel van een kiesbare specialist, met het rapport als uitgang."""
    sleutel = (naam or "").strip().lower()
    sleutel = sleutel if sleutel in profielen.PROFIELEN else STANDAARD
    if subagent and sleutel in profielen.KIESBAAR:
        return Subagent(profielen.PROFIELEN[sleutel])
    return (CentraleAgent if sleutel in (CENTRAAL, CENTRAAL_BREED) else Agent)(profielen.PROFIELEN[sleutel])


def agent_van(state: Any) -> Agent:
    """De agent van deze beurt, uit de state: de annotatie-route draait de lus als ophaal-agent, en een beurt met een
    opdracht (`opdracht`, ADR-016 §A3) is een subagent."""
    naam = "retrieval" if state.get("specialist") == "annotatie" else state.get("specialist")
    return agent_voor(naam, subagent=bool(state.get("opdracht")))


def vorm_van(stand: str, gevraagd: str | None) -> str:
    """De agentvorm van een beurt (ADR-016 §A7): `centraal` of `supervisor`. De straat beslist of een run mag kiezen:
    met `uit` nooit, met `meten` draait de supervisor tenzij de run om de centrale agent vraagt, met `aan` omgekeerd."""
    if stand == "meten":
        return "centraal" if gevraagd == "centraal" else "supervisor"
    if stand == "aan":
        return "supervisor" if gevraagd == "supervisor" else "centraal"
    return "supervisor"


def voeg_overdracht_toe(g: Any, add: Callable[[str, Any], None], b: Any) -> None:
    """De node `overdracht` in de graaf: de uitgang van de centrale agent naar een route in code. Alleen op een straat
    waar de centrale agent kan draaien; de doelnodes moeten al geregistreerd zijn."""
    from .overdracht import doelen, overdracht_node, route_na_overdracht

    add("overdracht", functools.partial(overdracht_node, b))
    g.add_conditional_edges("overdracht", functools.partial(route_na_overdracht, b), doelen())


def voeg_keten_toe(g: Any, add: Callable[[str, Any], None], b: Any, *, na_agent: dict[str, str], na_finalize: str) -> None:
    """De antwoordketen in de graaf `g`: agent ⇄ tools → (sjabloon) → verify → (correct) → finalize.

    `add` registreert een node (met de stopbewaking en de span van `build_graph`). `na_agent` zijn de uitgangen van de
    agentnode: de routes die deze graafvorm kent. `na_finalize` is waar de keten eindigt."""
    from .nodes.antwoord import (agent_node, correct_node, finalize_node, route_after_agent, route_after_verify,
                                 route_na_tools, tools_node, verify_node)
    from .nodes.sjabloon import route_na_sjabloon, sjabloon_node

    add("agent", functools.partial(agent_node, b))
    add("tools", functools.partial(tools_node, b))
    add("sjabloon", functools.partial(sjabloon_node, b))
    add("verify", functools.partial(verify_node, b))
    add("correct", functools.partial(correct_node, b))
    add("finalize", functools.partial(finalize_node, b))
    g.add_conditional_edges("tools", functools.partial(route_na_tools, b), {"agent": "agent", "verify": "verify"})
    g.add_conditional_edges("sjabloon", functools.partial(route_na_sjabloon, b), {"verify": "verify", "agent": "agent"})
    g.add_conditional_edges("verify", functools.partial(route_after_verify, b), {"correct": "correct", "finalize": "finalize"})
    g.add_edge("correct", "agent")
    g.add_conditional_edges("agent", functools.partial(route_after_agent, b), na_agent)
    g.add_edge("finalize", na_finalize)
