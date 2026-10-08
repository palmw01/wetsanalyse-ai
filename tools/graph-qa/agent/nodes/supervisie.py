"""De supervisie-keten: welke worker draait er, en is de vraag er überhaupt een voor ons.

De supervisor kiest per vraag een worker-keten en een specialist. Hij heeft bewust géén tools en
kijkt niet in de graaf: een afwijzing bij twijfel is duurder dan een zoekpoging die niets vindt.
Zijn antwoord wordt hard gesaneerd (`parse_supervisor`), zodat een verzonnen workernaam nergens
toe leidt. `advance` bepaalt daarna of er nog een worker volgt.
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.config import get_stream_writer

from ..aanwijzing import lees_aanwijzing, melding_meerdere
from ..doel import _heeft_opgegeven_doel
from ..focus import bij_advies
from ..narratie import _stap
from ..state import State
from ..methode import instructies
from ..berichten import eerdere_beurten
from ..supervisor import SUPERVISOR_SYSTEM, VERVOLG_SYSTEM, parse_supervisor, parse_vraag
from ..overzicht import is_overzichtsvraag
from ..tools.annotatie_tools import is_leesvraag
from .context import Bouw

logger = logging.getLogger("graph_qa.orchestrator")


def _vervolgcontext(b: Bouw, state: State) -> str:
    """Het gesprek tot nu toe, voor de supervisor. Leeg bij de eerste vraag van een gesprek."""
    beurten = eerdere_beurten(state.get("messages") or [], state.get("question", ""))
    if not beurten:
        return ""
    regels = ["", "GESPREK TOT NU TOE (oudste eerst):"]
    for vraag, antwoord in beurten:
        regels += [f"Jurist: {vraag}", f"Lex: {antwoord or '(geen antwoord)'}"]
    return "\n".join(regels)


def _lees(writer, vraag: str) -> dict[str, Any]:
    _stap(writer, "Lex", "raadpleegt bestaande annotaties")
    return {"specialist": "annotaties_lezen", "worker_plan": ["annotaties_lezen"],
            "worker_idx": 0, "plan": "bestaande annotaties raadplegen" + _herschreven(vraag),
            "afwijzen": False, "annotaties_lezen": True}


def _overzicht(writer, vraag: str) -> dict[str, Any]:
    """Een overzichtsvraag: hard naar de overzichtsroute, zoals een leesvraag naar de leesroute. Het
    overzicht bouwt `overzicht_bouwen` uit de graaf; de algemene specialist duidt het daarna."""
    _stap(writer, "Lex", "overzicht van een onderwerp")
    return {
        "specialist": "algemeen", "worker_plan": ["algemeen"], "worker_idx": 0,
        "plan": "overzicht van een onderwerp" + _herschreven(vraag), "afwijzen": False,
        "annotaties_lezen": False, "overzicht_route": True,
    }


def _herschreven(vraag: str) -> str:
    return f"\nDe vraag, zelfstandig geformuleerd: {vraag}" if vraag else ""


def supervisor_node(b: Bouw, state: State) -> dict[str, Any]:
    """Bepaalt de worker-keten (antwoord/annotatie) voor deze vraag; zet de eerste worker actief.

    In een lopend gesprek leest hij eerst het gesprek: een vervolgvraag wordt herschreven tot een
    zelfstandige vraag (`zelfstandige_vraag`), en dáárop draaien de harde regels en de keuze. Bij de
    eerste vraag van een gesprek is er niets te herschrijven en blijft alles zoals het was."""
    writer = get_stream_writer()
    modus = state.get("modus", "auto")

    gesprek = _vervolgcontext(b, state)
    leesvraag = is_leesvraag(state.get("question", ""), modus)
    if leesvraag and (not gesprek or _heeft_opgegeven_doel(state)):
        # Een leesvraag kan topologisch geen annotatie worden – ook niet met een doel erbij: dan is
        # het doel het zoekbereik. Zonder gesprek valt er niets te herschrijven, dus geen LLM-call.
        return _lees(writer, "")

    if _heeft_opgegeven_doel(state) and modus != "advies":
        # De aanroeper weet welke bepaling geannoteerd moet worden. Dan is er niets te kiezen en
        # niets te zoeken: geen supervisor-call, en `_entry_node` slaat de ophaal-agent over.
        # Wat de router zou beslissen is hier al bekend, en wat de ophaal-agent zou vinden staat
        # er al – inclusief de zekerheid dat het de bepaling is die de jurist aanwees.
        doel = state.get("opgegeven_doel") or {}
        aanduiding = doel.get("artikel") or doel.get("nummer") or ""
        _stap(writer, "Lex", f"annoteert de aangewezen bepaling (art. {aanduiding})")
        return {
            "specialist": "annotatie", "worker_plan": ["annotatie"], "worker_idx": 0,
            "plan": "annotatie van een aangewezen bepaling", "afwijzen": False, "annotaties_lezen": False,
        }

    if modus != "advies" and not gesprek and is_overzichtsvraag(state.get("question", "")):
        # Zonder gesprek valt er niets te herschrijven: geen LLM-call, de vorm van de vraag beslist.
        return _overzicht(writer, "")

    if modus == "advies":
        # Een adviesvraag bij een bestaande annotatie: geen LLM-keuze, hard naar de
        # duiding-specialist. Dat is een topologische garantie in plaats van een belofte in een
        # prompt – de antwoord-route emit geen `doel`/`element`-events, dus advies vragen kán de
        # annotatie niet wijzigen. Scheelt bovendien een LLM-call.
        _stap(writer, "Lex", "advies bij een bestaande markering")
        return {
            "specialist": "duiding", "worker_plan": ["duiding"], "worker_idx": 0,
            "plan": "adviesvraag bij een bestaande annotatie", "annotaties_lezen": False,
            # Het aangewezen element blijft het onderwerp, ook als de volgende vraag zonder chip komt.
            "focus": bij_advies(state.get("focus"), state.get("context")),
        }

    resp = b.llm.create(
        model=b.model_router,
        max_tokens=400,
        system=[SUPERVISOR_SYSTEM + "\n\n" + instructies("supervisor"),
                b.memory_context(state) + ((VERVOLG_SYSTEM + "\n" + gesprek) if gesprek else "")],
        tools=[],
        messages=[{"role": "user", "content": state["question"]}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    vraag = parse_vraag(text) if gesprek else ""
    zelfstandig = vraag or state.get("question", "")
    upd: dict[str, Any] = {"zelfstandige_vraag": vraag}
    if vraag and vraag != state.get("question"):
        _stap(writer, "Supervisor", f"leest de vraag als: {vraag[:120]}")

    # De harde regel ná het lezen van het gesprek: "welke zijn er nog meer?" na een vraag over
    # rechtssubjecten is pas als herschreven vraag herkenbaar als leesvraag.
    if leesvraag or is_leesvraag(zelfstandig, modus):
        return {**upd, **_lees(writer, vraag)}
    if is_overzichtsvraag(zelfstandig):
        return {**upd, **_overzicht(writer, vraag)}

    worker_plan, plan, afwijzen = parse_supervisor(text)
    plan += _herschreven(vraag)
    if afwijzen:
        # Buiten de scope. Dit hoort hier te eindigen en niet als "AANPAK: AFWIJZEN" de
        # systeemprompt van een specialist in te gaan, waar een tweede modelbeslissing bepaalt
        # wat er gebeurt – dat kost minstens één extra call en is bovendien geen garantie.
        _stap(writer, "Supervisor", "buiten de wet- en regelgeving in de graaf")
        return {**upd, "specialist": "", "plan": plan, "worker_plan": [], "worker_idx": 0,
                "afwijzen": True, "annotaties_lezen": False}
    eerste = worker_plan[0]
    if eerste == "annotatie":
        # Eén artikel per annotatievraag. Meer artikelen is een werkgebied afbakenen – een andere
        # functie. Deterministisch en vóór de ophaal-agent: die zou er anders stil één uitkiezen.
        aanwijzing = lees_aanwijzing(zelfstandig)
        if aanwijzing.meerdere_artikelen:
            _stap(writer, "Lex", f"meer dan één artikel genoemd ({', '.join(aanwijzing.artikelen)})")
            return {**upd, "specialist": "", "plan": plan, "worker_plan": [], "worker_idx": 0,
                    "afwijzen": True, "afwijs_melding": melding_meerdere(aanwijzing.artikelen),
                    "annotaties_lezen": False}
    _stap(writer, "Supervisor", f"kiest de {eerste}-worker · {plan.splitlines()[0][:80]}")
    return {**upd, "specialist": eerste, "plan": plan, "worker_plan": worker_plan, "worker_idx": 0,
            "afwijzen": False, "annotaties_lezen": False}

def _entry_node(b: Bouw, state: State) -> str:
    """Ingang voor de huidige worker: de annotatie-worker draait altijd de agent⇄tools-lus; een
    antwoord-worker gaat in decompositie-modus langs decompose, anders ook langs de agent-lus.

    Wees de vraag afgewezen, dan gaat er geen enkele worker draaien – dat is de hele winst."""
    if state.get("afwijzen"):
        return "afwijzen"
    if state.get("overzicht_route"):
        # Eerst het overzicht bouwen, dan duiden – ook met decompositie aan.
        return "overzicht_bouwen"
    if state.get("annotaties_lezen"):
        # Eerst zoeken, dan formuleren – ook met decompositie aan: `solve_node` bouwt de agent-lus
        # na en zou de zoekstap dubbel doen.
        return "annotaties_zoeken"
    if state.get("specialist") == "annotatie":
        # Doel al bekend → recht naar de annoteerder; de agent⇄tools-lus zou alleen opzoeken
        # wat de aanroeper al meestuurde. `annoteer_node` haalt het corpus zelf gericht op.
        return "annoteer" if _heeft_opgegeven_doel(state) else "agent"
    return "decompose" if b.settings.enable_decomposition else "agent"

def advance_node(b: Bouw, state: State) -> dict[str, Any]:
    """Ga naar de volgende worker in de keten; reset de per-worker werkvelden."""
    idx = state.get("worker_idx", 0) + 1
    plan = state.get("worker_plan") or []
    upd: dict[str, Any] = {"worker_idx": idx}
    if idx < len(plan):
        upd.update({
            "specialist": plan[idx], "turns": 0, "corrected": False, "answer": "",
            # Ook de annotatie-velden: een volgende worker begint schoon, anders zou een tweede
            # annotatie in dezelfde beurt de voorstellen van de eerste uitsturen.
            "voorstellen": [], "analyse": {},
        })
    return upd

def route_after_advance(b: Bouw, state: State) -> str:
    plan = state.get("worker_plan") or []
    if state.get("worker_idx", 0) < len(plan):
        return _entry_node(b, state)
    return "einde"


def afwijs_node(b: Bouw, state: State) -> dict[str, Any]:
    """De supervisor plaatste de vraag buiten de wetgeving: hier eindigt de beurt.

    Kort en zonder verwijt, met de uitnodiging erbij – een afwijzing die alleen "dat doe ik niet"
    zegt laat iemand raden wat dan wel kan. Geen tools, geen bronnen, geen tweede LLM-call.

    Deze tekst zegt bewust NIET "staat niet in mijn kennisgraaf". Dit pad is er voor vragen die
    buiten de wetgeving vallen (het weer, programmeren), en dat weet de supervisor zonder te
    kijken. Of een bepáálde regeling in de graaf zit weet hij juist níét – hij heeft geen tools —
    en die vraag hoort dus naar de antwoord-worker, die zoekt en het zelf zegt als hij niets
    vindt. Anders wijst een gok een vraag af waar wel degelijk iets over te vinden was: "de
    milieuwet" leverde een afwijzing op terwijl art. 36 IW 1990 de Wet belastingen op
    milieugrondslag noemt.
    """
    writer = get_stream_writer()
    if state.get("afwijs_melding"):
        melding = state["afwijs_melding"]
        writer({"type": "token", "content": melding})
        _stap(writer, "Klaar", "niet geannoteerd – vraag opnieuw voor één artikel")
        return {"answer": melding, "messages": [{"role": "assistant", "content": melding}]}
    melding = (
        "Deze vraag gaat niet over Nederlandse wet- en regelgeving, dus daar kan ik je niet mee "
        "helpen. Vraag me gerust naar een bepaling, een begrip of de samenhang tussen artikelen "
        "— of laat me een artikel annoteren volgens het JAS."
    )
    writer({"type": "token", "content": melding})
    _stap(writer, "Klaar", "niet beantwoord – buiten de wetgeving")
    return {"answer": melding, "messages": [{"role": "assistant", "content": melding}]}
