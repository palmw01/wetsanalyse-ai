"""Overdrachtstools van de centrale agent (ADR-016 §A1): een tool die de beurt aan een route in code geeft.

Een overdrachtstool **bouwt niets na**. Hij zet de state die de route in code nu ook zet en stuurt de beurt naar de node
die er al is; de code vult het antwoord, en het model schrijft er niets overheen. Zo is er per route één implementatie,
of de supervisor haar nu kiest of de centrale agent.

De tools zijn van de agent, niet van het profiel: `CentraleAgent` voegt ze toe (`agentvorm.py`). Een profiel kan ze niet
noemen, en een agent met alle tools (`tools: None`) krijgt ze niet: ze staan niet in de toollaag.

Een nieuwe overdracht is: een `Overdracht` hier, de doelnode in de uitgangen van `overdracht` (`voeg_overdracht_toe`) en
een test in `tests/test_centrale_agent.py`. Kiest de route zelf haar node (het werkgebied: intake, bronselectie of een
agenttaak), dan is `naar` `INGANG`: de node volgt uit de state van de route, met dezelfde `_entry_node` als de supervisor.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langgraph.config import get_stream_writer

from .binnen_scope import niet_afwijzen
from .narratie import _stap
from .state import State

#: `naar` als de route zelf haar node kiest: dezelfde ingang als na de supervisor (`supervisie._entry_node`).
INGANG = "ingang"

#: De profielen van de centrale agent (ADR-016 §A1): de kernset, en dezelfde agent met alle graaftools.
CENTRAAL = "centraal"
CENTRAAL_BREED = "centraal_breed"


@dataclass(frozen=True)
class Overdracht:
    naam: str
    beschrijving: str
    #: De eigenschappen van de invoer (JSON-schema); leeg = geen argumenten.
    invoer: dict[str, Any]
    #: De node waar de beurt heen gaat, of `INGANG`.
    naar: str
    #: `(b, state, invoer) -> de state-update van de route`, of een tekst als de code de overdracht weigert: het model
    #: krijgt die als toolresultaat en werkt verder. `b` is de `Bouw` van de graaf (de graaf voor een controle).
    zet: Callable[[Any, State, dict[str, Any]], dict[str, Any] | str]
    #: De profielen waarvan de agent deze tool krijgt; leeg = elk profiel van de centrale agent.
    van: frozenset[str] = frozenset()
    #: Wat het model ziet als de overdracht slaagt.
    resultaat: str = "Overgedragen."
    #: Bij `INGANG`: de nodes waar de route kan uitkomen (de uitgangen van de node `overdracht`).
    ingangen: tuple[str, ...] = ()

    @property
    def schema(self) -> dict[str, Any]:
        return {"name": self.naam, "description": self.beschrijving, "strict": True,
                "input_schema": {"type": "object", "properties": self.invoer, "required": sorted(self.invoer),
                                 "additionalProperties": False}}


def _wijs_af(_b: Any, state: State, _invoer: dict[str, Any]) -> dict[str, Any] | str:
    """Buiten de wetgeving: de vaste tekst uit code (`afwijs_node`). Een vraag over een bron naast de wet (ADR-013) of een
    vraag die een regeling noemt (ADR-016 ronde 4, K12) is nooit buiten de scope: die weigert de code, zoals ze een
    afwijzing van de supervisor terugdraait (`binnen_scope`, één regel voor beide vormen)."""
    if reden := niet_afwijzen(state.get("question", "")):
        return reden
    return {"afwijzen": True}


def _meer_tools(_b: Any, _state: State, _invoer: dict[str, Any]) -> dict[str, Any]:
    """De overdracht aan het brede profiel, binnen dezelfde beurt: de volgende ronde draait dezelfde agent met alle
    graaftools. Het gesprek van de beurt blijft; alleen het voorvoegsel wisselt."""
    return {"specialist": CENTRAAL_BREED}


def _taakagent(_b: Any, state: State, invoer: dict[str, Any]) -> dict[str, Any] | str:
    """Eén taak van de deelvragen- of begrippenagent: dezelfde `_agent` als na de keuze van de supervisor, met de
    parameters uit wat er ligt (werkgebied, aangewezen object, de vraag). Een taak die niet bij de agent hoort, weigert
    de code met de taken die er wel zijn."""
    from .agents import register
    from .nodes.supervisie import _agent

    agent, taak = invoer.get("agent", ""), invoer.get("taak", "")
    if not register.is_taak(agent, taak):
        return (f"De {register.NAAM.get(agent, agent)} kent de taak '{taak}' niet. Kies uit: "
                f"{', '.join(register.taken(agent)) if agent in register.AGENTS else ''}.")
    return _agent(get_stream_writer(), state, agent, taak, state.get("question", ""))


def _werkgebied(_b: Any, state: State, invoer: dict[str, Any]) -> dict[str, Any]:
    """Het werkgebied samenstellen, het dossier aanvullen of de bronselectie: dezelfde route als bij de supervisor."""
    from .nodes.supervisie import werkgebied_route

    taak = invoer.get("taak", "")
    return werkgebied_route(get_stream_writer(), state, "" if taak == "samenstellen" else taak,
                            state.get("question", ""))


def _toon_bepaling(b: Any, state: State, invoer: dict[str, Any]) -> dict[str, Any] | str:
    """De tekst van een bepaling: dezelfde workflow als de route vóór het model (`bepaling_workflow`, ADR-010 D1), die
    ophaalt en het sjabloon `antwoord_bepaling` vult. Dat sjabloon heeft de centrale agent zelf niet (meetronde S6,
    golden_duiding: "wat betekent lid X" kreeg het bepalingssjabloon). Dezelfde regel als vóór het model: een vraag om
    uitleg of over een stuk naast de wet is geen vraag naar de tekst, en die weigert de code. Het BWB-id moet uit het
    gesprek komen (`id_herkomst`), zoals bij een graaftool. Lukt het ophalen niet, dan werkt dezelfde agent verder."""
    from . import id_herkomst
    from .bepaling_workflow import Bepalingsvraag, is_uitlegvraag
    from .graph import queries
    from .nodes.supervisie import _bepaling

    vraag = state.get("question", "")
    if is_uitlegvraag(vraag):
        return ("Deze vraag vraagt om uitleg, niet alleen om de tekst. Haal de bepaling op met get_artikel, get_lid of "
                "get_bepaling en rond af met antwoord_duiding.")
    artikel, lid = (invoer.get("artikel") or "").strip(), (invoer.get("lid") or "").strip()
    if not queries.is_artikelnummer(artikel):
        return (f"'{artikel}' is geen artikelnummer (een divisie van een beleidsregel lees je met get_bepaling). Toon de "
                "tekst dan zelf, of rond af met antwoord_duiding.")
    bwb_id = (invoer.get("bwb_id") or "").strip().upper()
    if not re.fullmatch(r"BWB[RV]\d{7}", bwb_id):
        return f"'{bwb_id}' is geen BWB-id (BWBR of BWBV met zeven cijfers)."
    if weigering := id_herkomst.toets(TOON_BEPALING, invoer, state, graph=getattr(b, "graph", None)):
        return weigering
    upd = _bepaling(get_stream_writer(), Bepalingsvraag(bwb_id=bwb_id, artikel=artikel, lid=lid))
    # Lukt het ophalen niet, dan gaat de beurt terug naar de agent: dezelfde centrale agent, niet de specialist van de
    # supervisor.
    return {**upd, "specialist": state.get("specialist") or CENTRAAL}


TOON_BEPALING = "toon_bepaling"

#: De specialisten van de supervisor. Valt een vaste route terug op de agent, dan is dat in deze vorm de centrale agent.
_SPECIALISTEN = frozenset({"algemeen", "duiding", "definitie"})


def _vaste_route(regel: str, weigering: str) -> Callable[[Any, State, dict[str, Any]], dict[str, Any] | str]:
    """Een overdracht naar een route op de herschreven vraag (ADR-016 A2-3c): het model geeft de vraag zelfstandig
    geformuleerd, met de regeling, het onderwerp of het dossier uit het gesprek, en de code draait daarop dezelfde regel
    als de supervisor na het herschrijven (`supervisie.NA_HERSCHRIJVEN`). Pakt de regel de vraag niet, dan weigert de
    code met wat wel kan. De vraag wordt `zelfstandige_vraag`: de route en de controle lezen hem zoals bij de supervisor."""

    def zet(b: Any, state: State, invoer: dict[str, Any]) -> dict[str, Any] | str:
        from .nodes.supervisie import na_herschrijven

        vraag = " ".join((invoer.get("vraag") or "").split())
        route = na_herschrijven(b, get_stream_writer(), state, vraag, alleen=regel) if vraag else None
        if route is None:
            return weigering
        if route.get("specialist") in _SPECIALISTEN:
            route = {**route, "specialist": state.get("specialist") or CENTRAAL}
        return {**route, "zelfstandige_vraag": vraag}

    return zet


#: Het argument van een vaste route: de vraag zoals de supervisor haar zou herschrijven.
_VRAAG = {"vraag": {"type": "string", "description": (
    "De vraag van de gebruiker, zelfstandig geformuleerd: zonder 'dat', 'die' of 'en …?', met de regeling, het "
    "artikel, het onderwerp of het werkgebied uit het gesprek erin.")}}

#: De agents die de centrale agent een taak kan geven (ADR-016 A2-3a). De annotatieagent komt met `annoteer` (A2-4).
TAAKAGENTS = ("deelvragen", "begrippen")


def _taken() -> list[str]:
    from .agents import register
    return sorted({t for a in TAAKAGENTS for t in register.taken(a)})


#: De taken van het werkgebied zelf (geen agent): samenstellen is bij de supervisor de lege taak.
WERKGEBIED_TAKEN = ("samenstellen", "aanvullen", "bronselectie")


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
    Overdracht(
        naam=TOON_BEPALING,
        beschrijving=(
            "Roep dit aan als de gebruiker ALLEEN wil weten wat er in een bepaling staat of wat ze regelt ('en lid 2?', "
            "'wat staat er in artikel 9?', 'geef de tekst van dat artikel'). De code haalt de tekst op en toont hem met een "
            "korte toelichting; schrijf zelf niets. Niet voor uitleg ('wat betekent', 'wat houdt in', 'waarom', 'hoe "
            "verhoudt'): die beantwoord je zelf met antwoord_duiding. bwb_id komt uit het gesprek; lid is leeg voor het "
            "hele artikel."),
        invoer={"bwb_id": {"type": "string"},
                "artikel": {"type": "string"}, "lid": {"type": "string"}},
        naar="bepaling_lezen", zet=_toon_bepaling),
    Overdracht(
        naam="toon_overzicht",
        beschrijving=(
            "Roep dit aan als de gebruiker wil weten WELKE bepalingen of artikelen over een onderwerp gaan, ook in een "
            "vervolgvraag ('en over verrekening?'). De code bouwt het overzicht uit de graaf en de werkplek toont het; "
            "schrijf zelf niets. Niet voor wat er in één bepaling staat (toon_bepaling) of voor uitleg."),
        invoer=_VRAAG, naar="overzicht_bouwen",
        zet=_vaste_route("overzicht", "Dit is geen vraag naar welke bepalingen over een onderwerp gaan ('welke artikelen "
                                      "gaan over …'). Beantwoord haar zelf.")),
    Overdracht(
        naam="lees_annotaties",
        beschrijving=(
            "Roep dit aan als de gebruiker vraagt naar BESTAANDE annotaties of markeringen ('welke markeringen zijn er al "
            "bij lid 2?', 'hoeveel rechtssubjecten zijn gemarkeerd?'), ook in een vervolgvraag. De code zoekt ze op; "
            "daarna formuleer je het antwoord. Niet om te annoteren, en niet voor een vraag over de JAS-methode zelf."),
        invoer=_VRAAG, naar="annotaties_zoeken",
        zet=_vaste_route("annotaties", "Dit is geen vraag naar bestaande annotaties of markeringen. Beantwoord haar "
                                       "zelf.")),
    Overdracht(
        naam="lees_begrippen",
        beschrijving=(
            "Roep dit aan als de gebruiker vraagt naar begrippen die al VASTGELEGD zijn ('welke begrippen hebben we al?', "
            "'welke zijn er nog meer?'), ook in een vervolgvraag. De code zoekt ze op; daarna formuleer je het antwoord. "
            "Niet voor de wettelijke definitie van een term, en niet om begrippen voor te stellen (taakagent)."),
        invoer=_VRAAG, naar="begrippen_zoeken",
        zet=_vaste_route("begrippen", "Dit is geen vraag naar vastgelegde begrippen ('welke begrippen hebben we al "
                                      "vastgelegd …'). Beantwoord haar zelf.")),
    Overdracht(
        naam="taakagent",
        beschrijving=(
            "Roep dit aan als de gebruiker in een werkgebied iets met de deelvragen of de begrippen wil laten DOEN. "
            "De agent voert de taak uit en de werkplek toont het voorstel; schrijf zelf niets. "
            "deelvragen: voorstellen (deelvragen opstellen bij de analysevraag), verbeteren (één deelvraag scherper "
            "formuleren of splitsen), dekking (is een deelvraag, of zijn de deelvragen, gedekt door bronnen). "
            "begrippen: voorstellen (begrippen voorstellen uit de annotaties), meedenken (meedenken over twijfelpunten "
            "en definities), brondefinitie (de definitie van een vastgelegd begrip in de wet zoeken), scherper (een "
            "scherpere definitie), uitleg (de uitleg bij een vastgelegd begrip, in eenvoudige taal of B1), voorbeelden "
            "(voorbeelden bij een begrip), betekenisverschil (het verschil tussen twee begrippen), uitwerken (een begrip "
            "volledig uitwerken), relaties (de relaties van een begrip). "
            "Niet voor een vraag om UITLEG over een deelvraag, bron of begrip ('waarom hoort artikel 9 bij deelvraag "
            "2?'), en niet voor de wettelijke definitie van een term: die beantwoord je zelf."),
        invoer={"agent": {"type": "string", "enum": list(TAAKAGENTS)},
                "taak": {"type": "string", "enum": _taken()}},
        naar="agent_taak", zet=_taakagent),
    Overdracht(
        naam="werkgebied",
        beschrijving=(
            "Roep dit aan voor het werkgebied zelf; de werkplek stelt de vragen, schrijf zelf niets. "
            "samenstellen: de gebruiker wil een werkgebied samenstellen of een wetsanalyse beginnen. "
            "aanvullen: de gebruiker wil in een bestaand werkgebied een gegeven van het dossier invullen of wijzigen "
            "(naam, aanleiding, context, doel, analysevraag, praktijkvoorbeeld, thema, afbakening); deelvragen horen bij "
            "taakagent. bronselectie: de gebruiker wil in een werkgebied bronnen of bepalingen zoeken, bepalen of "
            "beoordelen, voor het werkgebied of een deelvraag, of verder met de bronselectie ('help me de bronnen bij "
            "dit werkgebied te bepalen', 'zoek bepalingen bij deelvraag 2')."),
        invoer={"taak": {"type": "string", "enum": list(WERKGEBIED_TAKEN)}},
        naar=INGANG, zet=_werkgebied, ingangen=("werkgebied_intake", "bronselectie", "agent_taak")),
)}


def voor(profiel: str) -> dict[str, Overdracht]:
    """De overdrachtstools van de centrale agent met dit profiel."""
    return {n: o for n, o in OVERDRACHT.items() if not o.van or profiel in o.van}


def overdracht_node(_b: Any, state: State) -> dict[str, Any]:
    """Voer de overdrachtstool van deze ronde uit: het toolresultaat in de historie, de state van de route, en waar de
    beurt heen gaat. Weigert de code, dan gaat de beurt terug naar de agent met de reden."""
    tu = state["pending_tools"][0]
    o = OVERDRACHT[tu["name"]]
    uitkomst = o.zet(_b, state, tu.get("input") or {})
    geweigerd = isinstance(uitkomst, str)

    def resultaat(tekst: str, **extra: Any) -> dict[str, Any]:
        return {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tu["id"], "content": tekst, **extra}]}

    if geweigerd:
        return {"messages": [resultaat(uitkomst, is_error=True)], "pending_tools": [], "overdracht_naar": ""}
    if o.naar == "afwijzen":
        _stap(get_stream_writer(), "Lex", "deze vraag valt buiten de wet- en regelgeving in de graaf", route="afgewezen")
    naar = o.naar
    if naar == INGANG:
        from .nodes.supervisie import _entry_node
        naar = _entry_node(_b, {**state, **uitkomst})
        assert naar in o.ingangen, f"overdracht {o.naam} kwam uit bij {naar}"
    return {"messages": [resultaat(o.resultaat)], "pending_tools": [],
            "overdracht_naar": "" if naar == "agent" else naar, **uitkomst}


def route_na_overdracht(_b: Any, state: State) -> str:
    return state.get("overdracht_naar") or "agent"


def doelen() -> dict[str, str]:
    """De uitgangen van de node `overdracht`: elke doelnode, en terug naar de agent."""
    nodes = {n for o in OVERDRACHT.values() for n in (o.ingangen if o.naar == INGANG else (o.naar,))}
    return {"agent": "agent", **{n: n for n in sorted(nodes)}}
