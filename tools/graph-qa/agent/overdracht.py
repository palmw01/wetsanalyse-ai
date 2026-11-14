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
    #: krijgt die als toolresultaat en werkt verder. `b` is de `Bouw` van de graaf (de graaf voor een controle). Een paar
    #: `(update, tekst)` geeft het toolresultaat zelf (de subagent: zijn rapport).
    zet: Callable[[Any, State, dict[str, Any]], dict[str, Any] | str | tuple[dict[str, Any], str]]
    #: De profielen waarvan de agent deze tool krijgt; leeg = elk profiel van de centrale agent.
    van: frozenset[str] = frozenset()
    #: Wat het model ziet als de overdracht slaagt.
    resultaat: str = "Overgedragen."
    #: Bij `INGANG`: de nodes waar de route kan uitkomen (de uitgangen van de node `overdracht`). Anders de nodes waar `zet`
    #: de beurt behalve naar `naar` nog heen kan sturen (met `overdracht_naar` in zijn update: twee of meer subagents).
    ingangen: tuple[str, ...] = ()
    #: Alleen in een beurt met een werkgebied (in het voorvoegsel alleen daar: per beurt vast, dus de cache blijft).
    werkgebied: bool = False
    #: Of het schema `strict` is. De strict schema's van een verzoek worden samen één grammatica, en die heeft een grens
    #: bij de API ("Schema is too complex for compilation", 400). Een overdracht met een ruime invoer die de code toch
    #: zelf toetst (de delegatietools), is daarom niet strict; `tests/test_strict_grenzen.py` begrenst het geheel.
    strict: bool = True

    @property
    def schema(self) -> dict[str, Any]:
        return {"name": self.naam, "description": self.beschrijving, "strict": self.strict,
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


def _toon_stukken(b: Any, state: State, invoer: dict[str, Any]) -> dict[str, Any] | str:
    """Een lijst stukken uit een bron naast de wet: de regel `lijst` van de supervisor (`bron_lijst.lees`) op de vraag
    die het model zelfstandig formuleerde. De bronkeuze viel vóór de eerste ronde op de getypte vraag; een bron die
    daarbij alleen deze beurt buiten de keuze viel, gaat weer mee (`bronkeuze.heropend`), en de keuze volgt daarna de
    route, zoals bij de supervisor (`_bronkeuze`, `van_route`). Staat de gevraagde bron echt uit, dan dezelfde melding
    als bij de supervisor (`_bron_uit`: de vaste tekst en het event voor *Zet aan*)."""
    from . import bronkeuze, bronstand
    from .nodes.supervisie import _bron_uit, _bronkeuze, na_herschrijven

    vraag = " ".join((invoer.get("vraag") or "").split())
    if not vraag:
        return _GEEN_LIJST
    writer = get_stream_writer()
    stand = state.get("bronstand") or {}
    open_stand = bronkeuze.heropend(stand)
    st = {**state, "bronstand": open_stand}
    route = na_herschrijven(b, writer, st, vraag, alleen="lijst")
    if route is None:
        if (uit := _bron_uit(writer, st, vraag)) is not None:
            return {**uit, "zelfstandige_vraag": vraag}
        return _GEEN_LIJST
    route = {**route, "zelfstandige_vraag": vraag, "specialist": state.get("specialist") or CENTRAAL}
    keuze = _bronkeuze(b, st, route)
    if "bronstand" not in keuze and open_stand != stand:
        writer(bronstand.event(open_stand))
        keuze = {**keuze, "bronstand": open_stand, "bronnen": bronkeuze.actief(open_stand)}
    return {**route, **keuze}


TOON_STUKKEN = "toon_stukken"

SUBAGENT = "subagent"


def _start_kind(b: Any, state: State) -> str:
    """Waarom een subagent hier niet kan starten, of leeg."""
    kinderen = getattr(b, "kinderen", None)
    if kinderen is None or not state.get("gesprek_id") or not getattr(b.settings, "legt_zelf_vast", False):
        return "Een subagent kan hier niet starten. Beantwoord de vraag zelf."
    return ""


def _met_kind(state: State, afloop: Any, kind: dict[str, Any], profiel: str) -> tuple[dict[str, Any], str]:
    """De state-update na een beurt van een kind: zijn toolresultaten in de trace, de afloop bij de subagenten van deze
    beurt (een hervatte vervangt zijn vorige stand), en het rapport als toolresultaat."""
    from . import subagent as sub

    trace = list(state.get("source_trace") or []) + [tuple(x) for x in kind.get("source_trace") or []]
    eerder = [a for a in state.get("subagenten") or [] if a.get("delegatie_id") != afloop.delegatie_id]
    tekst = sub.als_toolresultaat(profiel, afloop.uitkomst, sub.rapport_tekst(afloop, kind))
    return {"source_trace": trace, "subagenten": [*eerder, afloop.als_dict()],
            "rapport_steun": sub.steun_van([kind], state.get("rapport_steun"))}, tekst


def _subagent(b: Any, state: State, invoer: dict[str, Any]) -> tuple[dict[str, Any], str] | dict[str, Any] | str:
    """Subagents (ADR-016 §A3, §A5), één tool voor één tot `MAX_SUBAGENTS` opdrachten.

    - **Eén opdracht**: de code start hem in een kindgesprek, wacht, en geeft zijn rapport als toolresultaat. De centrale
      agent werkt daarna verder in dezelfde beurt; de toolresultaten van het kind gaan mee in de trace, zodat `verify` de
      samenvatting ertegen toetst.
    - **Twee of drie**: de code legt het plan eerst aan de gebruiker voor (`nodes/delegatie_plan.py`); ze beginnen pas na
      de bevestiging (`nodes/subagent_vervolg.py`).

    Eén laag: een subagent heeft deze tool niet (`Subagent` heeft geen eigen tools). Niet strict
    (`tests/test_strict_grenzen.py`), dus de code toetst de vorm zelf."""
    from pydantic import ValidationError

    from . import subagent as sub
    from .agents.uitvoering import draai
    from .models import SubagentOpdracht

    lijst = invoer.get("opdrachten") if isinstance(invoer.get("opdrachten"), list) else []
    if not all(isinstance(o, dict) for o in lijst):
        return "Geef elke opdracht als een object met profiel, doel, onderwerp, oplevering, bronnen en buiten."
    if not 1 <= len(lijst) <= sub.MAX_SUBAGENTS:
        return f"Geef één tot {sub.MAX_SUBAGENTS} opdrachten; meer past niet in één fase."
    plan: list[tuple[str, SubagentOpdracht]] = []
    for o in lijst:
        if o.get("profiel") not in sub.kiesbaar():
            return f"Het profiel '{o.get('profiel', '')}' bestaat niet. Kies uit: {', '.join(sub.kiesbaar())}."
        try:
            plan.append((o["profiel"], SubagentOpdracht(**{v: str(o.get(v) or "").strip() for v in sub.VELDEN})))
        except ValidationError:
            return "Schrijf bij elke opdracht het doel; de andere velden mogen leeg zijn."
    if reden := _start_kind(b, state):
        return reden
    if state.get("subagenten"):
        return "Je zette in deze beurt al een subagent aan het werk. Beantwoord de vraag met zijn rapport."
    if len(plan) > 1:
        return {"subagent_plan": [{"profiel": p, "opdracht": o.model_dump()} for p, o in plan],
                "overdracht_naar": "subagent_plan"}
    profiel, opdracht = plan[0]
    writer = get_stream_writer()
    _stap(writer, "Lex", f"zet een subagent ({profiel}) aan het werk", route=SUBAGENT)
    afloop, kind, weigering = draai(
        lambda stuur: sub.voer_uit(state, profiel, opdracht, stuur, settings=b.settings, kinderen=b.kinderen,
                                   gestopt=lambda: bool(b.stop_check and b.stop_check())),
        loop=b.loop, schrijf=writer)
    if weigering:
        return weigering
    return _met_kind(state, afloop, kind, profiel)


REGIE_PLAN = "regie_plan"


def _regie_plan(b: Any, state: State, invoer: dict[str, Any]) -> dict[str, Any] | str:
    """De regisseur als tool (ADR-016 §A5): het plan per deelvraag komt uit de stand bij de api, zonder tokens, met de
    bevestiging van de regie (`regisseur.voorstel`). De centrale agent stelt het niet zelf op."""
    opdracht = invoer.get("opdracht", "")
    if opdracht not in ("bronnen", "annoteren"):
        return "Kies de opdracht: bronnen of annoteren."
    if not state.get("werkgebied_id"):
        return "Een regie per deelvraag hoort bij een werkgebied, en dit gesprek hoort bij geen werkgebied."
    if not getattr(b.settings, "legt_zelf_vast", False):
        return "Een regie kan hier niet starten. Beantwoord de vraag zelf."
    return {"regie_plan": opdracht}


_GEEN_LIJST = ("De code leest dit niet als een lijstvraag (welke bron, welke volgorde of hoeveel, en waarover). Zoek dan "
               "zelf met de zoektool van de bron.")


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


def _subagent_invoer() -> dict[str, Any]:
    from .subagent import invoer_schema
    return invoer_schema()


#: De opdrachten van `subagent`: per opdracht het profiel en de vaste velden.
_SUBAGENT_INVOER = {"opdrachten": {"type": "array", "items": {
    "type": "object", "properties": _subagent_invoer(), "required": sorted(_subagent_invoer()),
    "additionalProperties": False}}}

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
        naam=TOON_STUKKEN,
        beschrijving=(
            "Roep dit aan als de gebruiker een LIJST of een aantal stukken uit een bron naast de wet vraagt (de nieuwste "
            "Kamerstukken, het laatste stuk van een dossier, uitspraken bij een artikel, hoeveel moties), ook in een "
            "vervolgvraag ('wat is het laatste?'). De code zoekt en de werkplek toont de stukken; schrijf zelf niets. "
            "Niet om één stuk te lezen of voor wat een stuk inhoudt."),
        invoer=_VRAAG, naar=INGANG, zet=_toon_stukken, ingangen=("bron_lijst", "afwijzen")),
    Overdracht(
        naam=SUBAGENT,
        beschrijving=(
            "Zet subagents aan het werk op opdrachten die op zichzelf staan en veel lezen: een reeks uitspraken, "
            "Kamerstukken of publicaties samenvatten, een lang stuk of een heel hoofdstuk doorlopen. Eén opdracht start "
            "meteen en komt terug met een rapport; twee of drie die los van elkaar kunnen, legt de code eerst aan de "
            "gebruiker voor. Een subagent ziet dit gesprek niet: schrijf elke opdracht volledig. Niet voor een vraag die je "
            "in een paar toolrondes zelf beantwoordt, en niet per deelvraag van een werkgebied (regie_plan)."),
        invoer=_SUBAGENT_INVOER, naar="agent", zet=_subagent, strict=False, ingangen=("subagent_plan",)),
    Overdracht(
        naam=REGIE_PLAN,
        beschrijving=(
            "Verdeel het werk per deelvraag van het werkgebied over deelgesprekken, met een plan uit de stand van het "
            "werkgebied. bronnen: de bronnen per deelvraag zoeken. annoteren: wat de gebruiker per deelvraag opnam "
            "annoteren. De werkplek toont het plan met een knop; schrijf zelf niets."),
        invoer={"opdracht": {"type": "string", "enum": ["bronnen", "annoteren"]}}, naar="regie_voorstel", zet=_regie_plan,
        strict=False, werkgebied=True),
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


def voor(profiel: str, *, werkgebied: bool = True) -> dict[str, Overdracht]:
    """De overdrachtstools van de centrale agent met dit profiel; zonder werkgebied zonder die van het werkgebied."""
    return {n: o for n, o in OVERDRACHT.items() if (not o.van or profiel in o.van) and (werkgebied or not o.werkgebied)}


def overdracht_node(_b: Any, state: State) -> dict[str, Any]:
    """Voer de overdrachtstool van deze ronde uit: het toolresultaat in de historie, de state van de route, en waar de
    beurt heen gaat. Weigert de code, dan gaat de beurt terug naar de agent met de reden."""
    tu = state["pending_tools"][0]
    o = OVERDRACHT[tu["name"]]
    uitkomst = o.zet(_b, state, tu.get("input") or {})
    tekst = o.resultaat
    if isinstance(uitkomst, tuple):
        uitkomst, tekst = uitkomst
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
    return {"messages": [resultaat(tekst)], "pending_tools": [],
            "overdracht_naar": "" if naar == "agent" else naar, **uitkomst}


def route_na_overdracht(_b: Any, state: State) -> str:
    return state.get("overdracht_naar") or "agent"


def doelen() -> dict[str, str]:
    """De uitgangen van de node `overdracht`: elke doelnode, en terug naar de agent."""
    nodes = {n for o in OVERDRACHT.values() for n in (o.ingangen if o.naar == INGANG else (o.naar, *o.ingangen))}
    return {"agent": "agent", **{n: n for n in sorted(nodes)}}
