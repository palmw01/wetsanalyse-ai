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
from ..bronselectie import is_bronselectievraag
from ..models import ACTIE_TAAK, BRONSELECTIE_ACTIES, INTAKE_ACTIES
from ..focus import bij_advies, bij_onderwerp
from ..narratie import _stap
from ..state import State
from ..methode import instructies
from ..berichten import eerdere_beurten
from ..agents import register
from ..supervisor import INTAKE_SYSTEM, SUPERVISOR_SYSTEM, VERVOLG_SYSTEM, parse_supervisor, parse_taak, parse_vraag
from ..overzicht import is_overzichtsvraag
from ..tools.annotatie_tools import is_leesvraag
from ..tools.begrip_tools import is_begrip_leesvraag
from ..werkgebied_intake import is_aanvullen, is_open, is_werkgebiedvraag, kaart
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


def _begrippen_lees(writer, vraag: str) -> dict[str, Any]:
    _stap(writer, "Lex", "raadpleegt vastgelegde begrippen")
    return {"specialist": "begrippen_lezen", "worker_plan": ["begrippen_lezen"],
            "worker_idx": 0, "plan": "vastgelegde begrippen raadplegen" + _herschreven(vraag),
            "afwijzen": False, "annotaties_lezen": False, "begrippen_lezen": True}


def _overzicht(writer, vraag: str) -> dict[str, Any]:
    """Een overzichtsvraag: hard naar de overzichtsroute, zoals een leesvraag naar de leesroute. Het
    overzicht bouwt `overzicht_bouwen` uit de graaf; de algemene specialist duidt het daarna."""
    _stap(writer, "Lex", "overzicht van een onderwerp")
    return {
        "specialist": "algemeen", "worker_plan": ["algemeen"], "worker_idx": 0,
        "plan": "overzicht van een onderwerp" + _herschreven(vraag), "afwijzen": False,
        "annotaties_lezen": False, "overzicht_route": True,
    }


def _werkgebied(writer, waarom: str, *, aanvullen: bool = False) -> dict[str, Any]:
    """Samenstellen van een werkgebied (activiteit 1), of het dossier van het werkgebied van het gesprek
    aanvullen: de werkgebied-worker, geen specialist."""
    _stap(writer, "Lex", waarom)
    return {"specialist": "werkgebied", "worker_plan": ["werkgebied"], "worker_idx": 0,
            "plan": "het dossier aanvullen" if aanvullen else "een werkgebied samenstellen", "afwijzen": False,
            "annotaties_lezen": False, "intake_modus": "aanvullen" if aanvullen else ""}


def _bronselectie(writer, waarom: str) -> dict[str, Any]:
    """De bronselectie per deelvraag (spoor J): de bronselectie-worker, op de stand die de api bewaart."""
    _stap(writer, "Lex", waarom)
    return {"specialist": "bronselectie", "worker_plan": ["bronselectie"], "worker_idx": 0,
            "plan": "de bronnen per deelvraag bepalen", "afwijzen": False, "annotaties_lezen": False,
            "intake_modus": ""}


def _agent(writer, state: State, agent: str, taak: str, vraag: str, *, actie: str = "") -> dict[str, Any]:
    """Eén taak van een agent (F3c): de node `agent_taak` voert hem uit. De parameters komen uit wat er
    ligt – werkgebied, het aangewezen object (of dat in de focus), en wat code uit de vraag kan lezen."""
    onderwerp = state.get("onderwerp") or (state.get("focus") or {}).get("onderwerp") or {}
    parameters = register.parameters(agent, taak, vraag=vraag or state.get("question", ""), onderwerp=onderwerp,
                                     werkgebied_id=state.get("werkgebied_id", ""), actie=actie,
                                     bevestigd=state.get("bevestigd"))
    _stap(writer, "Supervisor", f"kiest de {register.NAAM.get(agent, agent)} · taak {taak or '?'}"
          + (" (suggestie)" if actie else ""))
    return {"specialist": "agent_taak", "worker_plan": ["agent_taak"], "worker_idx": 0,
            "plan": f"{agent}: {taak}", "afwijzen": False, "annotaties_lezen": False,
            "agent_taak": {"agent": agent, "taak": taak, "parameters": parameters}}


def _open_kaartje(state: State) -> str:
    intake = state.get("intake") or {}
    if not is_open(intake):
        return ""
    try:
        wat = ("vult met de gebruiker het dossier van het werkgebied aan" if is_aanvullen(intake)
               else "stelt met de gebruiker een werkgebied samen")
        return INTAKE_SYSTEM.format(wat=wat, vraag=kaart(intake)["vraag"])
    except Exception:  # noqa: BLE001 – een onleesbare intake is geen reden om de beurt te laten vallen
        return ""


def _herschreven(vraag: str) -> str:
    return f"\nDe vraag, zelfstandig geformuleerd: {vraag}" if vraag else ""


def supervisor_node(b: Bouw, state: State) -> dict[str, Any]:
    """`kies`, en een object dat de analist met *Vraag Lex* aanwees (F3b) wordt het onderwerp van het
    gesprek: de focus houdt het vast voor de vervolgvraag zonder chip. Het onderwerp is een hint, geen
    route – de keuze zelf verandert er niet door."""
    upd = _kies(b, state)
    if state.get("onderwerp") and "focus" not in upd:
        upd = {**upd, "focus": bij_onderwerp(state.get("focus"), state.get("onderwerp"))}
    return upd


def _kies(b: Bouw, state: State) -> dict[str, Any]:
    """Bepaalt de worker-keten (antwoord/annotatie) voor deze vraag; zet de eerste worker actief.

    In een lopend gesprek leest hij eerst het gesprek: een vervolgvraag wordt herschreven tot een
    zelfstandige vraag (`zelfstandige_vraag`), en dáárop draaien de harde regels en de keuze. Bij de
    eerste vraag van een gesprek is er niets te herschrijven en blijft alles zoals het was."""
    writer = get_stream_writer()
    modus = state.get("modus", "auto")

    # Een klik op een vraagkaartje, of een verzoek om een werkgebied samen te stellen: vóór alles en
    # zonder modelaanroep. De klik weet al waar hij bij hoort; de startzin heeft een vaste vorm.
    if state.get("intake_actie"):
        if str((state.get("intake_actie") or {}).get("intake_id", "")).startswith("bs-"):
            return _bronselectie(writer, "verwerkt je keuze in de bronselectie")
        return _werkgebied(writer, "verwerkt het antwoord op het kaartje")
    if state.get("actie") in BRONSELECTIE_ACTIES:
        return _bronselectie(writer, "pakt de bronselectie op waar die was")
    if state.get("actie") in INTAKE_ACTIES:
        # Een klik op *Vul het dossier aan*: de vraagkaarten van de intake, op het werkgebied van het gesprek.
        return _werkgebied(writer, "vult met je het dossier aan", aanvullen=True)
    if (actie := state.get("actie")) and actie in ACTIE_TAAK:
        # Een klik op een suggestie: agent en taak liggen vast, dus geen modelaanroep – net als een doel.
        agent, taak = ACTIE_TAAK[actie]
        return _agent(writer, state, agent, taak, "", actie=actie)
    if modus == "auto" and state.get("werkgebied_id") and is_bronselectievraag(state.get("question", "")):
        return _bronselectie(writer, "bepaalt met je de bronnen per deelvraag")
    if modus == "auto" and is_werkgebiedvraag(state.get("question", "")):
        return _werkgebied(writer, "stelt met je een werkgebied samen")

    gesprek = _vervolgcontext(b, state)
    # Vóór de annotatie-leesvraag: "welke begrippen hebben we" noemt geen annotatie, maar "welke
    # begrippen rusten op deze markering" wel – het begrip is dan het onderwerp.
    begripvraag = modus == "auto" and is_begrip_leesvraag(state.get("question", ""))
    if begripvraag and not gesprek:
        return _begrippen_lees(writer, "")
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
                b.memory_context(state) + ((VERVOLG_SYSTEM + "\n" + gesprek) if gesprek else "")
                + _open_kaartje(state)],
        tools=[],
        messages=[{"role": "user", "content": state["question"]}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    vraag = parse_vraag(text) if gesprek else ""
    zelfstandig = vraag or state.get("question", "")
    upd: dict[str, Any] = {"zelfstandige_vraag": vraag}
    if vraag and vraag != state.get("question"):
        _stap(writer, "Supervisor", f"leest de vraag als: {vraag[:120]}")

    # Een leesvraag in de vraag zoals de analist haar stelde, gaat altijd voor.
    if begripvraag:
        return {**upd, **_begrippen_lees(writer, vraag)}
    if leesvraag:
        return {**upd, **_lees(writer, vraag)}

    worker_plan, plan, afwijzen = parse_supervisor(text)
    taak = parse_taak(text)
    agent = worker_plan[0] if worker_plan and worker_plan[0] in ("deelvragen", "begrippen") else \
        "annotatie" if worker_plan and worker_plan[0] == "annotatie" and taak in ("werkgebied", "deelvragen") else ""
    if agent and not afwijzen:
        # Koos het model een agent, dan mag het herschrijven die keuze niet omzetten: "Is deelvraag 2 al
        # gedekt?" werd herschreven tot "…gedekt door de annotaties?" en viel dan in de leesroute
        # (eval 21 okt 2026, 3 van 3 runs). De regels hieronder gelden alleen voor de andere workers.
        return {**upd, **_agent(writer, state, agent, taak, zelfstandig)}

    # De harde regel ná het lezen van het gesprek: "welke zijn er nog meer?" na een vraag over
    # rechtssubjecten is pas als herschreven vraag herkenbaar als leesvraag.
    if modus == "auto" and is_begrip_leesvraag(zelfstandig):
        return {**upd, **_begrippen_lees(writer, vraag)}
    if is_leesvraag(zelfstandig, modus):
        return {**upd, **_lees(writer, vraag)}
    if is_overzichtsvraag(zelfstandig):
        return {**upd, **_overzicht(writer, vraag)}

    plan += _herschreven(vraag)
    if afwijzen:
        # Buiten de scope. Dit hoort hier te eindigen en niet als "AANPAK: AFWIJZEN" de
        # systeemprompt van een specialist in te gaan, waar een tweede modelbeslissing bepaalt
        # wat er gebeurt – dat kost minstens één extra call en is bovendien geen garantie.
        _stap(writer, "Supervisor", "buiten de wet- en regelgeving in de graaf")
        return {**upd, "specialist": "", "plan": plan, "worker_plan": [], "worker_idx": 0,
                "afwijzen": True, "annotaties_lezen": False}
    eerste = worker_plan[0]
    if eerste == "werkgebied" and taak == "bronselectie":
        return {**upd, **_bronselectie(writer, "bepaalt met je de bronnen per deelvraag")}
    if eerste == "werkgebied" and taak == "aanvullen":
        return {**upd, **_werkgebied(writer, "vult met je het dossier aan", aanvullen=True)}
    if eerste == "werkgebied":
        return {**upd, **_werkgebied(writer, "stelt met je een werkgebied samen")}
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
    if state.get("specialist") == "werkgebied":
        return "werkgebied_intake"
    if state.get("specialist") == "bronselectie":
        return "bronselectie"
    if state.get("specialist") == "agent_taak":
        return "agent_taak"
    if state.get("overzicht_route"):
        # Eerst het overzicht bouwen, dan duiden – ook met decompositie aan.
        return "overzicht_bouwen"
    if state.get("begrippen_lezen"):
        return "begrippen_zoeken"
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
