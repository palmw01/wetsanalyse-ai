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

from ..doel import _heeft_opgegeven_doel
from ..narratie import _stap
from ..state import State
from ..supervisor import SUPERVISOR_SYSTEM, parse_supervisor
from .context import Bouw

logger = logging.getLogger("graph_qa.orchestrator")


def supervisor_node(b: Bouw, state: State) -> dict[str, Any]:
    """Bepaalt de worker-keten (antwoord/annotatie) voor deze vraag; zet de eerste worker actief."""
    writer = get_stream_writer()

    if _heeft_opgegeven_doel(state):
        # De aanroeper weet welke bepaling geannoteerd moet worden. Dan is er niets te kiezen en
        # niets te zoeken: geen supervisor-call, en `_entry_node` slaat de ophaal-agent over.
        # Wat de router zou beslissen is hier al bekend, en wat de ophaal-agent zou vinden staat
        # er al – inclusief de zekerheid dat het de bepaling is die de jurist aanwees.
        doel = state.get("opgegeven_doel") or {}
        aanduiding = doel.get("artikel") or doel.get("nummer") or ""
        _stap(writer, "Lex", f"annoteert de aangewezen bepaling (art. {aanduiding})")
        return {
            "specialist": "annotatie", "worker_plan": ["annotatie"], "worker_idx": 0,
            "plan": "annotatie van een aangewezen bepaling", "afwijzen": False,
        }

    if state.get("modus") == "advies":
        # Een adviesvraag bij een bestaande annotatie: geen LLM-keuze, hard naar de
        # duiding-specialist. Dat is een topologische garantie in plaats van een belofte in een
        # prompt – de antwoord-route emit geen `doel`/`element`-events, dus advies vragen kán de
        # annotatie niet wijzigen. Scheelt bovendien een LLM-call.
        _stap(writer, "Lex", "advies bij een bestaande markering")
        return {
            "specialist": "duiding", "worker_plan": ["duiding"], "worker_idx": 0,
            "plan": "adviesvraag bij een bestaande annotatie",
        }

    resp = b.llm.create(
        model=b.model_router,
        max_tokens=300,
        system=SUPERVISOR_SYSTEM + b.memory_context(state),
        tools=[],
        messages=[{"role": "user", "content": state["question"]}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    worker_plan, plan, afwijzen = parse_supervisor(text)
    if afwijzen:
        # Buiten de scope. Dit hoort hier te eindigen en niet als "AANPAK: AFWIJZEN" de
        # systeemprompt van een specialist in te gaan, waar een tweede modelbeslissing bepaalt
        # wat er gebeurt – dat kost minstens één extra call en is bovendien geen garantie.
        _stap(writer, "Supervisor", "buiten de wet- en regelgeving in de graaf")
        return {"specialist": "", "plan": plan, "worker_plan": [], "worker_idx": 0,
                "afwijzen": True}
    eerste = worker_plan[0]
    _stap(writer, "Supervisor", f"kiest de {eerste}-worker · {plan[:80]}")
    return {"specialist": eerste, "plan": plan, "worker_plan": worker_plan, "worker_idx": 0,
            "afwijzen": False}

def _entry_node(b: Bouw, state: State) -> str:
    """Ingang voor de huidige worker: de annotatie-worker draait altijd de agent⇄tools-lus; een
    antwoord-worker gaat in decompositie-modus langs decompose, anders ook langs de agent-lus.

    Wees de vraag afgewezen, dan gaat er geen enkele worker draaien – dat is de hele winst."""
    if state.get("afwijzen"):
        return "afwijzen"
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
            # Ook de annotatie-velden: een volgende worker begint schoon, anders zou een
            # tweede annotatie in dezelfde beurt op de rondeteller van de eerste doorbouwen.
            "voorstellen": [], "verworpen_fragmenten": [], "critic_feedback": [],
            "critic_ontbrekend": [], "critic_gefaald": False, "critic_ronde": 0,
            "nieuw_ontbrekend": [], "gemeld_ontbrekend": [], "patch_toegepast": 0,
            "stop_reden": "",
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
    melding = (
        "Deze vraag gaat niet over Nederlandse wet- en regelgeving, dus daar kan ik je niet mee "
        "helpen. Vraag me gerust naar een bepaling, een begrip of de samenhang tussen artikelen "
        "— of laat me een artikel annoteren volgens het JAS."
    )
    writer({"type": "token", "content": melding})
    _stap(writer, "Klaar", "niet beantwoord – buiten de wetgeving")
    return {"answer": melding, "messages": [{"role": "assistant", "content": melding}]}
