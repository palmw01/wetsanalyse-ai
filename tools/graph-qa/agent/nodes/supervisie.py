"""De ingang van een beurt: de routes in code, en anders de centrale agent (ADR-016 §A1 en §A7).

Sinds A7 is er geen modelstap meer vóór de centrale agent. De ingang kiest zonder model: een klik op een kaart of
suggestie, een aangewezen bepaling, een overzicht, een leesvraag, een genoemd stuk, een lijstvraag, een vraag naar boven
of een route uit `routes.py`. Pakt geen route de vraag, dan beantwoordt de centrale agent haar, en die stuurt met zijn
overdrachten zelf naar een route (afwijzen, annoteren, een werkgebied, de agents). `advance` bepaalt daarna of er nog
een worker volgt. De module heet om historische redenen nog `supervisie`.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from bronmodel.connectors import genoemde_stukken, herkende as bronnen_in_vraag

from langgraph.config import get_stream_writer

from dataclasses import asdict

from ..contenttoets import is_contenttoets
from .. import bronstand
from ..aanwijzing import lees_aanwijzing
from ..agentvorm import CENTRAAL
from ..bepaling_workflow import lees as lees_bepalingsvraag
from ..bepaling_workflow import lees_buiten, wijst_stuk_aan
from ..doel import _heeft_opgegeven_doel
from ..bronselectie import is_bronselectievraag
from ..welke_wijziging import melding as welke_wijziging
from ..overdracht import _delegatie_stand, is_standvraag
from ..models import ACTIE_TAAK, BRONSELECTIE_ACTIES, INTAKE_ACTIES
from ..focus import bij_advies, bij_onderwerp
from ..kaart_beurt import KAARTPREFIX, uit_keuze
from ..narratie import _stap, doel_in_woorden
from ..state import State
from .. import methodekeuze
from ..berichten import eerdere_beurten
from ..agents import register
from ..agents.deelvragen import is_dekkingsvraag
from ..verduidelijken import doorvraag
from ..overzicht import is_overzichtsvraag
from ..tools.annotatie_tools import is_leesvraag
from ..tools.begrip_tools import is_begrip_leesvraag
from ..tools.regel_tools import is_regel_leesvraag
from ..werkgebied_intake import is_open, is_werkgebiedvraag
from . import subagent_route
from ..overdracht import _start_kind
from .context import Bouw

logger = logging.getLogger("graph_qa.orchestrator")

# Wat de jurist in het denkproces ziet: wat Lex gaat doen, niet welke worker of agent het doet (G2b); welke het werd,
# staat in het log.
_WORKER_STAP = {"annotatie": "zoekt de bepaling op om te annoteren"}
_AGENT_STAP = {"deelvragen": "kijkt naar de deelvragen van het werkgebied", "begrippen": "werkt aan de begrippen van het werkgebied",
               "annotatie": "annoteert de bronnen van het werkgebied"}


def _bepaling(writer, bepaling) -> dict[str, Any]:
    """De bepalingsroute (ADR-010, laag 2): de workflow haalt op en vult het sjabloon."""
    _stap(writer, "Lex", "haalt de tekst van de bepaling op", route="bepaling")
    # Alleen de velden met een waarde (plus de drie vaste): de graafroute houdt dezelfde vorm als vóór `live`.
    vraag = {k: v for k, v in asdict(bepaling).items() if v or k in ("bwb_id", "artikel", "lid")}
    return {"specialist": "algemeen", "worker_plan": ["algemeen"], "worker_idx": 0, "plan": "de tekst van een bepaling",
            "afwijzen": False, "annotaties_lezen": False, "bepalingsvraag": vraag}


def _doorvraag(state: State) -> str:
    """De doorvraag van R3 op het volledige vorige antwoord: de keuzevraag staat aan het eind, dus niet ingekort."""
    vorige = eerdere_beurten(state.get("messages") or [], state.get("question", ""), aantal=1, per_bericht=100_000)
    return doorvraag(state.get("question", ""), vorige[-1][1]) if vorige else ""


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
    _stap(writer, "Lex", "raadpleegt bestaande annotaties", route="annotaties_lezen")
    return {"specialist": "annotaties_lezen", "worker_plan": ["annotaties_lezen"],
            "worker_idx": 0, "plan": "bestaande annotaties raadplegen" + _herschreven(vraag),
            "afwijzen": False, "annotaties_lezen": True}


def _begrippen_lees(writer, vraag: str) -> dict[str, Any]:
    _stap(writer, "Lex", "raadpleegt vastgelegde begrippen", route="begrippen_lezen")
    return {"specialist": "begrippen_lezen", "worker_plan": ["begrippen_lezen"],
            "worker_idx": 0, "plan": "vastgelegde begrippen raadplegen" + _herschreven(vraag),
            "afwijzen": False, "annotaties_lezen": False, "begrippen_lezen": True}


def _contenttoets(b: Bouw, writer, state: State) -> dict[str, Any]:
    """`/contenttoets <tekst>` of de actie `contenttoets` (plan contenttoets, C2): zonder model naar het profiel
    `contenttoets`; de node `contenttoets_voorbereiden` zet de content in het bronspoor. Staat de proefvlag uit, of is er
    geen (of te veel) tekst, dan een vaste zin."""
    from .. import contenttoets as ct

    content, _ = ct.ontleed(state.get("question", ""))
    plugins = state.get("plugins")
    reden = (ct.UIT if not b.settings.contenttoets
             else ct.UIT_IN_GESPREK if plugins is not None and "contenttoets" not in plugins
             else ct.melding(content))
    if reden:
        _stap(writer, "Lex", "toetst niet", route="contenttoets")
        return {"specialist": "", "plan": "", "worker_plan": [], "worker_idx": 0, "afwijzen": True,
                "afwijs_melding": reden, "afwijs_stap": "niets getoetst", "annotaties_lezen": False}
    _stap(writer, "Lex", "toetst de content aan de bron", route="contenttoets")
    logger.info("worker gekozen", extra={"categorie": "functioneel", "worker": "contenttoets"})
    return {"specialist": "contenttoets", "worker_plan": ["contenttoets"], "worker_idx": 0,
            "plan": "content toetsen op juistheid en volledigheid", "afwijzen": False, "annotaties_lezen": False,
            "begrippen_lezen": False, "regels_lezen": False, "contenttoets": True}


def _regels_lees(writer, vraag: str) -> dict[str, Any]:
    """Een vraag over de vastgelegde afleidingsregels (ADR-010): de code zoekt eerst (`nodes/regels_lezen.py`), het
    profiel `regels_lezen` formuleert."""
    _stap(writer, "Lex", "raadpleegt vastgelegde afleidingsregels", route="regels_lezen")
    return {"specialist": "regels_lezen", "worker_plan": ["regels_lezen"],
            "worker_idx": 0, "plan": "vastgelegde afleidingsregels raadplegen" + _herschreven(vraag),
            "afwijzen": False, "annotaties_lezen": False, "begrippen_lezen": False, "regels_lezen": True}


def _overzicht(writer, vraag: str) -> dict[str, Any]:
    """Een overzichtsvraag: hard naar de overzichtsroute, zoals een leesvraag naar de leesroute. Het
    overzicht bouwt `overzicht_bouwen` uit de graaf; de algemene specialist duidt het daarna."""
    _stap(writer, "Lex", "maakt een overzicht van het onderwerp", route="overzicht")
    return {
        "specialist": "algemeen", "worker_plan": ["algemeen"], "worker_idx": 0,
        "plan": "overzicht van een onderwerp" + _herschreven(vraag), "afwijzen": False,
        "annotaties_lezen": False, "overzicht_route": True,
    }


def _werkgebied(writer, waarom: str, *, aanvullen: bool = False) -> dict[str, Any]:
    """Samenstellen van een werkgebied (activiteit 1), of het dossier van het werkgebied van het gesprek
    aanvullen: de werkgebied-worker, geen specialist."""
    _stap(writer, "Lex", waarom, route="werkgebied")
    return {"specialist": "werkgebied", "worker_plan": ["werkgebied"], "worker_idx": 0,
            "plan": "het dossier aanvullen" if aanvullen else "een werkgebied samenstellen", "afwijzen": False,
            "annotaties_lezen": False, "intake_modus": "aanvullen" if aanvullen else ""}


def werkgebied_route(writer, state: State, taak: str, vraag: str) -> dict[str, Any]:
    """De route voor het werkgebied, voor de supervisor en de overdracht `werkgebied` van de centrale agent (ADR-016
    A2-3a): de bronselectie, het dossier aanvullen, of samenstellen. In een bestaand werkgebied is een vraag zonder taak
    over zijn deelvragen of bronnen geen verzoek om een nieuw samen te stellen: op acceptatie (7 nov 2026) startte "Welke
    bronnen horen daarbij?" de intake ("Hoe noemen we het werkgebied?"). De stand per deelvraag komt uit de api: de taak
    `dekking`, zonder model."""
    if taak == "bronselectie":
        return _bronselectie(writer, "bepaalt met je de bronnen per deelvraag")
    if taak == "aanvullen":
        return _werkgebied(writer, "vult met je het dossier aan", aanvullen=True)
    if state.get("werkgebied_id") and not is_werkgebiedvraag(vraag):
        return _agent(writer, state, "deelvragen", "dekking", vraag)
    return _werkgebied(writer, "stelt met je een werkgebied samen")


def geen_deelvraag(state: State) -> dict[str, Any] | None:
    """"Zoek de bronnen bij de deelvraag over verjaring" in een werkgebied zonder zo'n deelvraag: een vraag aan de jurist
    uit code, zonder model (agentset V02, A6 run 2: de centrale agent koos zelf de bronselectie, die stil verder ging bij
    deelvraag 3). Dezelfde toets staat in de overdracht `werkgebied` (`overdracht._werkgebied`)."""
    from ..bronselectie import geen_deelvraag_melding

    if not (melding := geen_deelvraag_melding(state.get("question", ""), state.get("werkgebied_context", ""))):
        return None
    _stap(get_stream_writer(), "Lex", "vindt geen deelvraag over dat onderwerp", route="geen_deelvraag")
    return {"specialist": "", "plan": "", "worker_plan": [], "worker_idx": 0, "afwijzen": True,
            "afwijs_melding": melding, "afwijs_stap": "niets gezocht – het werkgebied heeft die deelvraag niet",
            "annotaties_lezen": False}


def _bronselectie(writer, waarom: str) -> dict[str, Any]:
    """De bronselectie per deelvraag (spoor J): de bronselectie-worker, op de stand die de api bewaart."""
    _stap(writer, "Lex", waarom, route="bronselectie")
    return {"specialist": "bronselectie", "worker_plan": ["bronselectie"], "worker_idx": 0,
            "plan": "de bronnen per deelvraag bepalen", "afwijzen": False, "annotaties_lezen": False,
            "intake_modus": ""}


def _agent(writer, state: State, agent: str, taak: str, vraag: str, *, actie: str = "") -> dict[str, Any]:
    """Eén taak van een agent (F3c): de node `agent_taak` voert hem uit. De parameters komen uit wat er
    ligt – werkgebied, het aangewezen object (of dat in de focus), en wat code uit de vraag kan lezen."""
    onderwerp = state.get("onderwerp") or (state.get("focus") or {}).get("onderwerp") or {}
    parameters = register.parameters(agent, taak, vraag=state.get("question", "") or vraag, herschreven=vraag,
                                     onderwerp=onderwerp,
                                     werkgebied_id=state.get("werkgebied_id", ""), actie=actie,
                                     bevestigd=state.get("bevestigd"),
                                     werkvoorraad_id=state.get("werkvoorraad_id", ""))
    _stap(writer, "Lex", _AGENT_STAP.get(agent, "werkt aan het werkgebied"), route=agent)
    logger.info("agent gekozen", extra={"categorie": "functioneel", "agent": agent, "taak": taak, "suggestie": bool(actie)})
    return {"specialist": "agent_taak", "worker_plan": ["agent_taak"], "worker_idx": 0,
            "plan": f"{agent}: {taak}", "afwijzen": False, "annotaties_lezen": False,
            "agent_taak": {"agent": agent, "taak": taak, "parameters": parameters}}


def _begrip_keuze(writer, state: State) -> dict[str, Any]:
    """Een klik op de keuzekaart van de begrippen-agent: de taak zoals de kaart hem noemt, zonder model."""
    actie = state.get("intake_actie") or {}
    keuze = uit_keuze((actie.get("keuzes") or [""])[0] if actie.get("actie") == "antwoord" else "")
    parameters = {"werkgebied_id": str(actie.get("intake_id", "")).removeprefix(KAARTPREFIX),
                  "begrip_id": keuze["begrip_id"], "ander_id": keuze["ander_id"]}
    _stap(writer, "Lex", "verwerkt je keuze", route="begrippen")
    return {"specialist": "agent_taak", "worker_plan": ["agent_taak"], "worker_idx": 0, "plan": f"begrippen: {keuze['taak']}",
            "afwijzen": False, "annotaties_lezen": False,
            "agent_taak": {"agent": "begrippen", "taak": keuze["taak"], "parameters": parameters}}


#: Zo veel genoemde stukken leest de code hoogstens vooraf; meer is een overzicht, en dat zoekt de agent.
MAX_GENOEMD = 3


#: Het artikel dat de vraag noemt ("wat veranderde … aan artikel 1.1.5"). Niet `lees_aanwijzing`: die leest "1.1.5" als
#: artikel 1, lid 1.5.
_GENOEMD_ARTIKEL_RE = re.compile(r"\bartikel\s+(?P<nr>[0-9][0-9A-Za-z:.]{0,19}?)(?=[\s,;?!]|\.(?:\s|$)|$)", re.IGNORECASE)


def _met_filter(leestool: str) -> frozenset[str]:
    """De argumenten van de leestool, uit haar schema."""
    from ..tools import TOOLS
    schema = next((t for t in TOOLS if t["name"] == leestool), {})
    return frozenset((schema.get("input_schema") or {}).get("properties") or {})


def _te_lezen(state: State, vraag: str) -> list[dict[str, Any]]:
    """De leestool-aanroepen voor de stukken die de vraag bij id noemt, van connectors die in deze beurt aanstaan
    (uit de beschrijving: `leestool`, `lees_argument`). Leeg als er niets genoemd is of de connector uit staat.

    Kent de leestool een argument `artikel` en noemt de vraag precies één artikel, dan gaat dat mee: zo staat het
    wijzigingsonderdeel op de eerste pagina, ook als het achteraan het stuk staat (meting bekendmakingen B08). Geeft dat
    niets, dan leest `bron_lezen` het hele stuk."""
    stand = state.get("bronstand") or {}
    artikelen = {m.group("nr").rstrip(".") for m in _GENOEMD_ARTIKEL_RE.finditer(vraag or "")}
    uit: list[dict[str, Any]] = []
    for c, ident in genoemde_stukken(vraag):
        aanroep = {"name": c.leestool, "input": {c.lees_argument: ident}}
        if len(artikelen) == 1 and "artikel" in _met_filter(c.leestool):
            aanroep["input"]["artikel"] = next(iter(artikelen))
        if (stand.get(c.naam) or {}).get("aan") and aanroep not in uit:
            uit.append(aanroep)
    return uit[:MAX_GENOEMD]


#: Een verzoek om te annoteren of te markeren: dat leest de code niet vooraf, de annotatieworker zegt wat er kan.
_ANNOTEER_RE = re.compile(r"\b(?:annote(?:er|ren)|markeer|markeren|classificeer)\b", re.IGNORECASE)
#: Wat een annoteeropdracht over het werkgebied maakt in plaats van over één bepaling: de deelvragen, het werkgebied, of
#: "de bronnen"/"de bepalingen" zonder artikel.
_WG_DEELVRAGEN_RE = re.compile(r"\bdeelvra(?:ag|gen)\b", re.IGNORECASE)
_WG_GEHEEL_RE = re.compile(r"\b(?:werkgebied|bronnen|bepalingen|bronselectie)\b", re.IGNORECASE)
_WG_ARTIKEL_RE = re.compile(r"\b(?:artikel|art\.)\s*\d", re.IGNORECASE)


def werkgebied_annoteeropdracht(vraag: str) -> str:
    """De taak van de annotatie-agent bij een getypte opdracht om het werkgebied te annoteren: `deelvragen` (alles onder
    de deelvragen, of onder de genoemde deelvraag), `werkgebied`, of leeg als het geen opdracht is of over één artikel
    gaat. "Welke bronnen zijn al geannoteerd?" is geen opdracht: "geannoteerd" is geen gebiedende wijs."""
    if not _ANNOTEER_RE.search(vraag) or _WG_ARTIKEL_RE.search(vraag):
        return ""
    if _WG_DEELVRAGEN_RE.search(vraag):
        return "deelvragen"
    return "werkgebied" if _WG_GEHEEL_RE.search(vraag) else ""


#: Een opdracht om te annoteren, in de gebiedende wijs vooraan ("annoteer …", "graag markeren …") of als verzoek ("kun je …
#: annoteren?"). "Welke bepalingen zijn al geannoteerd?" en "wat betekent annoteren?" zijn geen opdracht.
_ANNOTEEROPDRACHT_RE = re.compile(
    r"^\W*(?:(?:graag|svp|alsjeblieft|nu|nog\s+een\s+keer|opnieuw)\s+)?(?:annoteer|markeer|classificeer)\b"
    r"|^\W*(?:kun|kunt|wil|wilt|zou|zoudt)\s+(?:je|jij|u)\b.*\b(?:annoteren|markeren|classificeren)\b",
    re.IGNORECASE | re.DOTALL)


def annoteeropdracht(vraag: str) -> bool:
    """Is dit een opdracht om één bepaling te annoteren die de vraag zelf aanwijst ("annoteer leidraad artikel 1.1.2",
    "kun je artikel 9 lid 1 IW annoteren?")? Dan gaat de beurt in code naar de annotatieketen, zonder de centrale agent.

    Die moest de overdracht `annoteer` zelf kiezen, en deed dat niet altijd: in een gesprek waarin dezelfde bepaling al
    geannoteerd was, schreef hij "de annotatie is al uitgevoerd en staat in de gesprekscontext", zonder tools en zonder
    artefact (acceptatie 23 nov 2026: vier van de vijf keer). De keten hergebruikt een laag die af is zelf, en opent hem
    naast het gesprek. Een opdracht zonder artikel ("annoteer lid 2", "doe hetzelfde voor lid 2") leunt op het gesprek:
    die blijft bij de centrale agent. Meer artikelen tegelijk ook: daar weigert zijn overdracht met een melding."""
    return bool(_ANNOTEEROPDRACHT_RE.search(vraag or "")) and len(lees_aanwijzing(vraag).artikelen) == 1


#: Een verzoek om een bepaling op te nemen of toe te voegen (aan de bronselectie, het werkgebied): dat kan alleen met een
#: bronnode in de graaf.
_OPNEEM_RE = re.compile(r"\b(?:neem\b.*\bop\b|opnemen|voeg\b.*\btoe\b|toevoegen)", re.IGNORECASE)


def _live_aan(state: State) -> bool:
    """Staat de connector `wetgeving_live` in deze beurt aan?"""
    return bool(((state.get("bronstand") or {}).get("wetgeving_live") or {}).get("aan"))


def _buiten_graaf_melding(writer, state: State, vraag: str, buiten: list[Any], graph: Any) -> dict[str, Any] | None:
    """Een vraag over een regeling buiten de kennisgraaf die geen tekst kan krijgen, met een vaste melding zonder model:

    - een verzoek om te **annoteren**: dat vraagt een bronnode in de graaf (meting 11 nov 2026, W16: "Ongeldig BWB-id");
    - een verzoek om **op te nemen** of toe te voegen (bronselectie, werkgebied): idem (controle 11 nov 2026, W15: het
      model schreef "staat nu in de bronselectie");
    - de connector staat **uit**: zeggen dat de regeling niet in de kennisgraaf staat en wie de bron aanzet (W14: vier
      rondes en 46k voor die melding). Zonder connector gaat er geen verzoek naar overheid.nl, dus de herkenning is op
      naam (`buiten_graaf.zonder_zoekdienst`)."""
    from .. import buiten_graaf

    aan = _live_aan(state)
    if aan and (onbekend := buiten_graaf.onbekende(buiten, vraag)):
        _stap(writer, "Lex", "vindt de genoemde regeling niet", route="niet_in_graaf")
        return {"specialist": "", "plan": "", "worker_plan": [], "worker_idx": 0, "afwijzen": True,
                "afwijs_melding": buiten_graaf.melding_onbekend(onbekend),
                "afwijs_stap": "niet gevonden – geen regeling met die naam", "annotaties_lezen": False}
    if not aan and ((state.get("bronstand") or {}).get("wetgeving_live") or {}).get("reden", "straat") == "straat":
        # Een straat zonder de connector (productie): daar is niets aan te zetten, en de agent zegt wat de graaf heeft.
        return None
    titels = ([g.titel for g in buiten if g.bwb_id] if aan else buiten_graaf.zonder_zoekdienst(vraag, graph))
    if not titels:
        return None
    if _ANNOTEER_RE.search(vraag):
        melding, stap = buiten_graaf.melding_annoteren(titels, lezen_kan=aan), "niet geannoteerd – niet in de kennisgraaf"
        _stap(writer, "Lex", "annoteert niet: de regeling staat niet in de kennisgraaf", route="niet_in_graaf")
    elif _OPNEEM_RE.search(vraag):
        melding, stap = buiten_graaf.melding_opnemen(titels, lezen_kan=aan), "niet opgenomen – niet in de kennisgraaf"
        _stap(writer, "Lex", "neemt niet op: de regeling staat niet in de kennisgraaf", route="niet_in_graaf")
    elif not aan:
        stand = state.get("bronstand") or {}
        melding = buiten_graaf.melding_bron_uit(titels, bronstand.uit_zin(stand, "wetgeving_live"))
        stap = "niet gezocht – niet in de kennisgraaf, en de bron staat uit"
        s = stand.get("wetgeving_live") or {"reden": "straat", "label": "Wetgeving buiten de kennisgraaf"}
        _stap(writer, "Lex", f"{s.get('label')} staat uit in deze beurt", route="bron_uit")
        writer({"type": "bron_uit", "bronnen": [{"naam": "wetgeving_live", "label": s.get("label"),
                                                 "reden": s.get("reden", "straat")}]})
    else:
        return None
    return {"specialist": "", "plan": "", "worker_plan": [], "worker_idx": 0, "afwijzen": True,
            "afwijs_melding": melding, "afwijs_stap": stap, "annotaties_lezen": False}


def _buiten_graaf(b: Bouw, state: State, vraag: str) -> list[Any]:
    """De regelingen die de vraag noemt en die niet in de kennisgraaf staan (`agent/buiten_graaf.py`), alleen als de
    connector `wetgeving_live` in deze beurt aanstaat: anders gaat er geen verzoek naar overheid.nl. Een storing is leeg."""
    from datetime import date

    from .. import buiten_graaf
    from ..tools.connectortools import MODULES

    if not _live_aan(state):
        return []
    try:
        bron = MODULES["wetgeving_live"].bron(b.settings)
        return buiten_graaf.genoemd(vraag, b.graph, bron, vandaag=date.today().isoformat())
    except Exception:  # noqa: BLE001 – de herkenning is een hulp, geen voorwaarde
        logger.warning("regelingen buiten de graaf niet herkend", exc_info=True)
        return []


def _keuze_regeling(writer, vraag_terug: str) -> dict[str, Any]:
    """Een afkorting die bij meer regelingen past ("Pw"): de vraag terug, zonder model en zonder te gokken."""
    _stap(writer, "Lex", "vraagt welke regeling je bedoelt", route="regeling_kiezen")
    return {"specialist": "", "plan": "", "worker_plan": [], "worker_idx": 0, "afwijzen": True,
            "afwijs_melding": vraag_terug, "afwijs_stap": "niet gezocht – welke regeling bedoeld is, is niet eenduidig",
            "annotaties_lezen": False}


def _lees_genoemd(writer, aanroepen: list[dict[str, Any]], vraag: str) -> dict[str, Any]:
    """Een vraag die alleen over genoemde stukken gaat: lezen in code, dan formuleert de duiding. Geen supervisorcall."""
    _stap(writer, "Lex", "leest het stuk dat je noemt" if len(aanroepen) == 1 else "leest de stukken die je noemt",
          route="bron_lezen")
    return {"specialist": "duiding", "worker_plan": ["duiding"], "worker_idx": 0, "afwijzen": False,
            "annotaties_lezen": False, "bron_lezen": aanroepen,
            "plan": "Beantwoord de vraag uit de tekst van het genoemde stuk, die al is opgehaald." + _herschreven(vraag)}


def _lijst(state: State, vraag: str, graph: Any = None):
    """De lijstvraag in de vraag (`agent/bron_lijst.py`), voor de connectors die in deze beurt aanstaan. Met de graaf
    leest de code ook een genoemde regeling ("uitspraken bij artikel 36 van de Invorderingswet 1990"), met dezelfde namen
    als het overzicht (`overzicht.regelingen_in_vraag`)."""
    from .. import bron_lijst

    aan = frozenset(n for n, s in (state.get("bronstand") or {}).items() if (s or {}).get("aan"))
    if not aan:
        return None
    return bron_lijst.lees(vraag, aan, regelingen=_regelingen_genoemd(graph) if graph is not None else None)


def _regelingen_genoemd(graph: Any):
    """De regelingen die een tekst bij naam noemt, als (bwb-id, namen): voor de lijstvraag bij een artikel."""
    from .. import overzicht

    def genoemd(tekst: str) -> list[tuple[str, set[str]]]:
        ids = overzicht.regelingen_in_vraag(graph, tekst)
        try:
            namen = {r["bwb_id"]: set(r["namen"]) for r in overzicht._regelingen(graph)}
        except Exception:  # noqa: BLE001 – zonder namenlijst geen route; de agent leest de vraag dan
            return []
        return [(i, namen.get(i, set())) for i in ids]
    return genoemd


def _regelingtitels(graph: Any):
    """De regelingen die een tekst bij naam of afkorting noemt, als (bwb-id, citeertitel): voor een vergelijking van
    regelingen die de code over subagents verdeelt (`subagent_route.plan`)."""
    if graph is None:
        return None
    from .. import overzicht

    return lambda tekst: overzicht.regelingtitels_in_vraag(graph, tekst)


def _bron_lijst(writer, lijst) -> dict[str, Any]:
    """Een lijstvraag: de zoektool in code, zonder model (`nodes/bron_lijst.py`)."""
    from bronmodel.connectors import CONNECTORS

    _stap(writer, "Lex", f"maakt een lijst uit de {CONNECTORS[lijst.connector].label}", route="bron_lijst")
    return {"specialist": "algemeen", "worker_plan": ["algemeen"], "worker_idx": 0, "afwijzen": False,
            "annotaties_lezen": False, "bron_lijst": {"connector": lijst.connector, "tool": lijst.tool, "args": lijst.args,
                                                       "gevraagd": lijst.gevraagd, "tellen": lijst.tellen,
                                                       "verdeling": lijst.verdeling,
                                                       "kanttekening": lijst.kanttekening},
            "plan": "Een lijst stukken uit een bron naast de wet; de zoekvraag staat in de historie."}


def _bron_uit(writer, state: State, vraag: str) -> dict[str, Any] | None:
    """Een vraag die alleen over bronnen naast de wet gaat (ADR-013, `bronmodel.connectors.herkende`), terwijl die
    bronnen in deze beurt uit staan: een eerlijke melding met wie ze aanzet, zonder model en zonder tools. Noemt de
    vraag ook een artikel, dan is er wetgeving te zoeken en beslist de supervisor; het promptblok zegt dan wat uit
    staat. Dezelfde vorm als een afwijzing (`afwijs_melding`), maar het is er geen: de vraag hoort bij de werkplek."""
    genoemd = bronnen_in_vraag(vraag)
    if not genoemd:
        return None
    stand = state.get("bronstand") or {}
    uit = [n for n in genoemd if not (stand.get(n) or {}).get("aan")]
    if len(uit) != len(genoemd) or lees_aanwijzing(vraag).artikelen:
        return None
    labels = ", ".join((stand.get(n) or {}).get("label") or n for n in uit)
    _stap(writer, "Lex", f"{labels} staat uit in deze beurt", route="bron_uit")
    # De werkplek biedt daarmee *Zet aan* aan, als de jurist de bron zelf kan aanzetten (gesprek of werkgebied).
    writer({"type": "bron_uit", "bronnen": [
        {"naam": n, "label": (stand.get(n) or {}).get("label") or n, "reden": (stand.get(n) or {}).get("reden", "straat")}
        for n in uit]})
    logger.info("bron uit", extra={"categorie": "functioneel", "bronnen": ",".join(
        f"{n}:{(stand.get(n) or {}).get('reden', 'straat')}" for n in uit)})
    return {"specialist": "", "plan": "", "worker_plan": [], "worker_idx": 0, "afwijzen": True,
            "afwijs_melding": bronstand.melding_uit(stand, uit),
            "afwijs_stap": "niet gezocht – de gevraagde bron staat uit", "annotaties_lezen": False}


SUBAGENT_PREFIX = "sa-"


def register_kiesbaar() -> frozenset[str]:
    from ..profielen import KIESBAAR
    return frozenset(KIESBAAR)


def _is_planbevestiging(state: State) -> bool:
    """Een klik op de bevestiging van een plan met subagents (`sa_start`), niet op een vraag van een subagent."""
    return (state.get("intake_actie") or {}).get("stap") == "sa_start"


def _subagent_vervolg(b: Bouw, writer, state: State) -> dict[str, Any]:
    """Een klik op de vraagkaart van een subagent: de node `subagent_vervolg`, zonder model. De regel zegt wat de klik
    was: de bevestiging van een plan (`sa_start`) is geen antwoord op een vraag naar boven (E2E 16 nov 2026, D-7)."""
    _stap(writer, "Lex", "verwerkt je keuze over het plan met subagents" if _is_planbevestiging(state)
          else "verwerkt je antwoord voor de subagent", route="subagent")
    return {"specialist": "subagent_vervolg", "plan": "", "worker_plan": ["subagent_vervolg"], "worker_idx": 0,
            "afwijzen": False, "annotaties_lezen": False}


def _markeer_doorvraag(b: Bouw, writer, state: State, dg: dict[str, Any]) -> None:
    """De delegatie op `later_gewijzigd`, met dit deelgesprek (best effort: een storing kost alleen de markering)."""
    if dg.get("delegatie_id") and b.settings.legt_zelf_vast:
        from ..agents.uitvoering import draai
        from .context import met_api

        async def markeer(_stuur) -> None:
            async with met_api(b, state.get("user_id", "")) as api:
                await api.wijzig_delegatie(dg["delegatie_id"], {"later_gewijzigd": True,
                                                                "deelgesprek": state.get("gesprek_id", "") or ""})
        try:
            draai(markeer, loop=b.loop, schrijf=writer)
        except Exception:  # noqa: BLE001 – de markering is een signaal, geen voorwaarde voor de beurt
            logger.warning("deelgesprek: later_gewijzigd niet gezet", extra={"categorie": "technisch"})


def _deelgesprek(b: Bouw, writer, state: State, dg: dict[str, Any]) -> dict[str, Any]:
    """Een beurt van de jurist in het deelgesprek van een subagent: het profiel van het gesprek, en de markering."""
    profiel = dg["profiel"]
    _markeer_doorvraag(b, writer, state, dg)
    _stap(writer, "Lex", f"werkt verder als {profiel}, het profiel van dit deelgesprek", route=profiel)
    logger.info("worker gekozen", extra={"categorie": "functioneel", "worker": profiel, "deelgesprek": True})
    return {"zelfstandige_vraag": "", "specialist": profiel, "plan": "", "worker_plan": [profiel], "worker_idx": 0,
            "afwijzen": False, "annotaties_lezen": False}


#: De eerste regel van het denkproces bij de centrale agent.
NAAR_CENTRAAL = "bekijkt de vraag"


def _naar_centraal(writer, state: State) -> dict[str, Any]:
    """De centrale agent als enige worker van de beurt: de antwoordketen met het profiel `centraal`. Eén korte regel
    als teken van leven, zonder de bronnen die aanstaan: welke Lex echt gebruikt, blijkt uit de toolstappen die volgen
    ("Wetgeving · 1 gevonden"; ADR-016 §A7, de gebruiker begreep "zoekt in de wetgeving en Kamerstukken, …" niet)."""
    _stap(writer, "Lex", NAAR_CENTRAAL, route=CENTRAAL)
    logger.info("worker gekozen", extra={"categorie": "functioneel", "worker": CENTRAAL})
    return {"zelfstandige_vraag": "", "specialist": CENTRAAL, "plan": "", "worker_plan": [CENTRAAL], "worker_idx": 0,
            "afwijzen": False, "annotaties_lezen": False}


def _open_kaartje(state: State) -> bool:
    """Staat er een vraagkaart van het samenstellen of het aanvullen open? Een getypt antwoord erop is geen nieuwe vraag
    (de centrale agent leest de kaart zelf: `overdracht.open_kaartje`)."""
    return bool(is_open(state.get("intake") or {}))


def _herschreven(vraag: str) -> str:
    return f"\nDe vraag, zelfstandig geformuleerd: {vraag}" if vraag else ""


def ingang_node(b: Bouw, state: State) -> dict[str, Any]:
    """`kies`, en een object dat de analist met *Vraag Lex* aanwees (F3b) wordt het onderwerp van het
    gesprek: de focus houdt het vast voor de vervolgvraag zonder chip. Het onderwerp is een hint, geen
    route – de keuze zelf verandert er niet door."""
    upd = _kies(b, state)
    if state.get("onderwerp") and "focus" not in upd:
        upd = {**upd, "focus": bij_onderwerp(state.get("focus"), state.get("onderwerp"))}
    if upd.get("contenttoets"):
        # Een werkwijze met een vast profiel: alleen de bronnen van dat profiel, niet de keuze per vraag.
        return {**upd, **_bronnen_van_profiel(state, upd["specialist"])}
    return {**upd, **_bronkeuze(b, state, upd)}


def _bronnen_van_profiel(state: State, profiel: str) -> dict[str, Any]:
    """De bronstand voor de werkwijze van `profiel` (`bronstand.voor_profiel`): wat het profiel niet noemt, doet niet mee,
    en het event zegt dat aan wie meekijkt. De keuze voor de vervolgvraag (`bronkeuze`) blijft van het gesprek."""
    from ..profielen import PROFIELEN

    stand = state.get("bronstand") or {}
    nieuw = bronstand.voor_profiel(stand, PROFIELEN[profiel].connectors)
    if nieuw is stand:
        return {}
    get_stream_writer()(bronstand.event(nieuw))
    logger.info("bronnen van de werkwijze", extra={"categorie": "functioneel", "bronstand": bronstand.als_tekst(nieuw)})
    return {"bronstand": nieuw, "bronnen": bronstand.actief(nieuw)}


def _bronkeuze(b: Bouw, state: State, upd: dict[str, Any]) -> dict[str, Any]:
    """Alleen de connectors die de vraag of het gesprek noemt (`agent/bronkeuze.py`): de bronnen en de bronstand van deze
    beurt, en de keuze voor de vervolgvraag. Na de keuze van de route, zodat de herschreven vraag meetelt; de route zelf
    verandert er niet door. Een gewijzigde stand gaat opnieuw als `bronstand`-event de stroom in."""
    from .. import bronkeuze
    from ..buiten_graaf import noemt_regeling_buiten_graaf

    stand = state.get("bronstand") or {}
    if len(bronkeuze.actief(stand)) < 2:
        return {}
    teksten = [state.get("question", ""), upd.get("zelfstandige_vraag") or ""]
    buiten = bool((stand.get(bronkeuze.BUITEN_GRAAF) or {}).get("aan")) and any(
        noemt_regeling_buiten_graaf(t, b.graph) for t in teksten if t)
    genoemd = bronkeuze.genoemd(teksten) | bronkeuze.van_route(upd)
    erbij = bronkeuze.filters_in(teksten) | ({bronkeuze.BUITEN_GRAAF} if buiten else set())
    nieuw, keuze = bronkeuze.kies(stand, genoemd, state.get("bronkeuze"), erbij)
    uit: dict[str, Any] = {"bronkeuze": keuze}
    if nieuw is not stand:
        uit.update(bronstand=nieuw, bronnen=bronkeuze.actief(nieuw))
        writer = get_stream_writer()
        writer(bronstand.event(nieuw))
        # Alleen als de keuze verandert: een hervatte beurt of een vervolgvraag met dezelfde bronnen herhaalde de regel
        # (E2E Rekeningafspraken 16 nov 2026, D-15). Het event gaat wel mee: de werkplek toont de stand per beurt.
        if keuze != state.get("bronkeuze") and not state.get("intake_actie"):
            _stap(writer, "Lex", bronstand.keuze_regel(nieuw))
        logger.info("bronnen per vraag", extra={"categorie": "functioneel", "bronstand": bronstand.als_tekst(nieuw)})
    return uit


def _kies(b: Bouw, state: State) -> dict[str, Any]:
    """Bepaalt de worker-keten (antwoord/annotatie) voor deze vraag; zet de eerste worker actief.

    In een lopend gesprek leest hij eerst het gesprek: een vervolgvraag wordt herschreven tot een
    zelfstandige vraag (`zelfstandige_vraag`), en dáárop draaien de harde regels en de keuze. Bij de
    eerste vraag van een gesprek is er niets te herschrijven en blijft alles zoals het was."""
    writer = get_stream_writer()
    modus = state.get("modus", "auto")

    # Een subagent (ADR-016 §A3): de centrale agent koos het profiel en schreef de opdracht. Geen route en geen model:
    # de beurt gaat naar de agent met dat profiel, die met het rapport afrondt.
    if state.get("opdracht"):
        profiel = state.get("specialist") or ""
        _stap(writer, "Lex", f"werkt als subagent ({profiel}) aan de opdracht", route=profiel)
        logger.info("worker gekozen", extra={"categorie": "functioneel", "worker": profiel, "subagent": True})
        return {"zelfstandige_vraag": "", "specialist": profiel, "plan": "", "worker_plan": [profiel], "worker_idx": 0,
                "afwijzen": False, "annotaties_lezen": False}

    # Doorvragen in het deelgesprek van een regiekind (A6 eind, F03): de delegatie hoort het, de beurt loopt verder de
    # gewone weg (het profiel van het kind, `retrieval`, is niet kiesbaar). De eigen beurt van het kind draagt een actie.
    dg = state.get("deelgesprek") or {}
    if dg.get("delegatie_id") and dg.get("profiel") not in register_kiesbaar() and not state.get("actie") \
            and not state.get("intake_actie"):
        _markeer_doorvraag(b, writer, state, dg)

    # Een klik op een vraagkaartje, of een verzoek om een werkgebied samen te stellen: vóór alles en
    # zonder modelaanroep. De klik weet al waar hij bij hoort; de startzin heeft een vaste vorm.
    if state.get("intake_actie"):
        if str((state.get("intake_actie") or {}).get("intake_id", "")).startswith("bs-"):
            return _bronselectie(writer, "verwerkt je keuze in de bronselectie")
        if str((state.get("intake_actie") or {}).get("intake_id", "")).startswith(KAARTPREFIX):
            return _begrip_keuze(writer, state)
        if str((state.get("intake_actie") or {}).get("intake_id", "")).startswith(SUBAGENT_PREFIX):
            return _subagent_vervolg(b, writer, state)
        return _werkgebied(writer, "verwerkt het antwoord op het kaartje")
    if state.get("actie") == "contenttoets" or is_contenttoets(state.get("question", "")):
        # Een plugin naast de wetsanalyse (plan contenttoets): vóór elke andere route, want de content kan alles noemen.
        return _contenttoets(b, writer, state)
    if state.get("actie") == "bepaling_toevoegen":
        return _bronselectie(writer, "zoekt met je een bepaling op")
    if state.get("actie") in BRONSELECTIE_ACTIES:
        # Neutraal: de route weet niet of er al iets lag, en bij de eerste keer lag er niets (E2E 16 nov 2026, D-12).
        return _bronselectie(writer, "werkt met je aan de bronselectie per deelvraag")
    if state.get("actie") in INTAKE_ACTIES:
        # Een klik op *Vul het dossier aan*: de vraagkaarten van de intake, op het werkgebied van het gesprek.
        return _werkgebied(writer, "vult met je het dossier aan", aanvullen=True)
    if (actie := state.get("actie")) and actie in ACTIE_TAAK:
        # Een klik op een suggestie: agent en taak liggen vast, dus geen modelaanroep – net als een doel.
        agent, taak = ACTIE_TAAK[actie]
        return _agent(writer, state, agent, taak, "", actie=actie)
    if not _open_kaartje(state) and (skill := methodekeuze.niet_gekoppeld(state.get("question", ""))):
        # Werk volgens een methode die aan geen rol gekoppeld is (plan methodes scheiden, S1): een vaste zin, geen
        # annotatie volgens het JAS onder een andere naam en geen model. Ook met een aangewezen bepaling, en voor beide
        # vormen. Een getypt antwoord op een vraagkaart is geen verzoek en loopt door.
        _stap(writer, "Lex", "zegt dat annoteren alleen volgens het JAS kan", route="methode_niet_gekoppeld")
        logger.info("verzoek volgens een niet-gekoppelde methode", extra={"categorie": "functioneel", "methode": skill})
        return {"specialist": "", "plan": "", "worker_plan": [], "worker_idx": 0, "afwijzen": True,
                "afwijs_melding": methodekeuze.melding(skill), "afwijs_stap": "niets gestart: deze methode voer ik nog niet uit",
                "annotaties_lezen": False}
    if modus == "auto" and state.get("werkgebied_id") and (melding := geen_deelvraag(state)):
        return melding
    if modus == "auto" and state.get("werkgebied_id") and (taak := werkgebied_annoteeropdracht(state.get("question", ""))):
        # "Annoteer de bronnen onder deelvraag 3 die nog niet geannoteerd zijn" (Termijnen, 19 nov 2026): de centrale
        # agent las het als vraag naar bestaande annotaties en annoteerde niets. Een opdracht om het werkgebied of de
        # bronnen onder de deelvragen te annoteren is de annotatie-agent, met zijn bevestiging, zonder model.
        return _agent(writer, state, "annotatie", taak, "")
    if modus == "auto" and state.get("werkgebied_id") and is_bronselectievraag(state.get("question", "")):
        return _bronselectie(writer, "bepaalt met je de bronnen per deelvraag")
    if modus == "auto" and is_werkgebiedvraag(state.get("question", "")):
        return _werkgebied(writer, "stelt met je een werkgebied samen")
    if modus == "auto" and state.get("werkgebied_id") and is_dekkingsvraag(state.get("question", "")):
        # De stand van het werkgebied staat bij de api: geen LLM-call, en geen model dat een eigen indeling bouwt.
        return _agent(writer, state, "deelvragen", "dekking", "")

    gesprek = _vervolgcontext(b, state)
    if gesprek and modus == "auto" and (melding := _doorvraag(state)):
        # Een open keuzevraag van Lex, en een vervolgvraag die hem niet beantwoordt: opnieuw vragen, niet gokken (R3).
        _stap(writer, "Lex", "vraagt eerst welk artikel je bedoelt", route="verduidelijken")
        return {"specialist": "", "plan": "", "worker_plan": [], "worker_idx": 0, "afwijzen": True,
                "afwijs_melding": melding, "afwijs_stap": "vraagt eerst welk artikel je bedoelt", "annotaties_lezen": False}
    # Vóór de annotatie-leesvraag: "welke begrippen hebben we" noemt geen annotatie, maar "welke
    # begrippen rusten op deze markering" wel – het begrip is dan het onderwerp.
    begripvraag = modus == "auto" and is_begrip_leesvraag(state.get("question", ""))
    if begripvraag and not gesprek:
        return _begrippen_lees(writer, "")
    regelvraag = modus == "auto" and is_regel_leesvraag(state.get("question", ""))
    if regelvraag and not gesprek:
        return _regels_lees(writer, "")
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
        _stap(writer, "Lex", "annoteert de aangewezen bepaling" + (f" ({wat})" if (wat := doel_in_woorden(doel)) else ""),
              route="annotatie")
        return {
            "specialist": "annotatie", "worker_plan": ["annotatie"], "worker_idx": 0,
            "plan": "annotatie van een aangewezen bepaling", "afwijzen": False, "annotaties_lezen": False,
        }

    if modus != "advies" and not gesprek and is_overzichtsvraag(state.get("question", "")):
        # Zonder gesprek valt er niets te herschrijven: geen LLM-call, de vorm van de vraag beslist.
        return _overzicht(writer, "")

    if modus == "auto" and not _open_kaartje(state) and (wijziging := welke_wijziging(state.get("question", ""), b.graph)):
        # "Vóór en na de wijziging" van één artikel, zonder te zeggen welke (agentset V04, A6): de jurist kiest, niet het
        # model. Zonder model; de laatste wijziging uit de graaf staat erbij.
        _stap(writer, "Lex", "vraagt welke wijziging je bedoelt", route="wijziging_kiezen")
        return {"specialist": "", "plan": "", "worker_plan": [], "worker_idx": 0, "afwijzen": True,
                "afwijs_melding": wijziging, "afwijs_stap": "niet vergeleken – welke wijziging bedoeld is, is niet gezegd",
                "annotaties_lezen": False}
    if modus == "auto" and (bepaling := lees_bepalingsvraag(state.get("question", ""), b.graph,
                                                                    live_aan=_live_aan(state))):
        # De tekst van een bepaling (ADR-010, D1): de vraag noemt zelf de regeling en het artikel, dus ook in een gesprek
        # valt er niets te herschrijven. Geen LLM-call; de workflow haalt op en vult het sjabloon.
        return _bepaling(writer, bepaling)

    if modus == "advies":
        # Een adviesvraag bij een bestaande annotatie: geen LLM-keuze, hard naar de
        # duiding-specialist. Dat is een topologische garantie in plaats van een belofte in een
        # prompt – de antwoord-route emit geen `doel`/`element`-events, dus advies vragen kán de
        # annotatie niet wijzigen. Scheelt bovendien een LLM-call.
        _stap(writer, "Lex", "geeft advies bij een bestaande markering", route="advies")
        return {
            "specialist": "duiding", "worker_plan": ["duiding"], "worker_idx": 0,
            "plan": "adviesvraag bij een bestaande annotatie", "annotaties_lezen": False,
            # Het aangewezen element blijft het onderwerp, ook als de volgende vraag zonder chip komt.
            "focus": bij_advies(state.get("focus"), state.get("context")),
        }

    if modus == "auto" and (uit := _bron_uit(writer, state, state.get("question", ""))):
        # Een vraag naar een bron die uit staat: zeggen wie hem aanzet, niet raden of afwijzen (ADR-013).
        return uit
    vraag_nu = state.get("question", "")
    # Een regeling buiten de kennisgraaf (connector wetgeving_live): een dubbelzinnige afkorting is een vraag terug; een
    # eenduidig genoemd artikel leest de code vooraf, in een nieuw gesprek zonder supervisorcall (zoals een genoemd stuk).
    buiten = _buiten_graaf(b, state, vraag_nu) if modus == "auto" else []
    from .. import buiten_graaf
    if (terug := buiten_graaf.keuzevraag(buiten)) and not any(g.bwb_id for g in buiten):
        return _keuze_regeling(writer, terug)
    if modus == "auto" and (melding := _buiten_graaf_melding(writer, state, vraag_nu, buiten, b.graph)):
        return melding
    if modus == "auto" and not _open_kaartje(state) and annoteeropdracht(vraag_nu):
        # Een annoteeropdracht die de bepaling zelf aanwijst: de annotatieketen, ook als dezelfde vraag eerder in het gesprek
        # stond (`annoteeropdracht`). Na de melding voor een regeling buiten de graaf: die annoteert de keten niet.
        _stap(writer, "Lex", _WORKER_STAP["annotatie"], route="annotatie")
        logger.info("worker gekozen", extra={"categorie": "functioneel", "worker": "annotatie", "route": "annoteeropdracht"})
        return {"zelfstandige_vraag": vraag_nu, "specialist": "annotatie", "worker_plan": ["annotatie"], "worker_idx": 0,
                "plan": "annotatie" + _herschreven(vraag_nu), "afwijzen": False, "annotaties_lezen": False}
    if modus == "auto" and (live_bepaling := lees_buiten(vraag_nu, buiten)):
        # De tekst van een artikel buiten de graaf: dezelfde workflow als een artikel uit de graaf (ADR-010, D1), met het
        # hele artikel in het blok `extern` en de controle op letterlijkheid. Ook in een gesprek: de vraag noemt het zelf.
        return _bepaling(writer, live_bepaling)
    if not gesprek and not _ANNOTEER_RE.search(vraag_nu) and not wijst_stuk_aan(vraag_nu) \
            and (live := buiten_graaf.leesaanroepen(buiten)) and len(live) == 1:
        g = next(x for x in buiten if x.bwb_id and x.artikel)
        _stap(writer, "Lex", f"leest artikel {g.artikel} van de {g.titel} bij overheid.nl (niet in de kennisgraaf)",
              route="bron_lezen")
        return {"specialist": "duiding", "worker_plan": ["duiding"], "worker_idx": 0, "afwijzen": False,
                "annotaties_lezen": False, "bron_lezen": live,
                "plan": "Beantwoord de vraag uit de tekst van het genoemde artikel, die al is opgehaald."
                        + buiten_graaf.plan_regel(buiten)}
    if modus == "auto" and (aanroepen := _te_lezen(state, vraag_nu)):
        # De vraag noemt een stuk bij zijn id: lezen in code, zoals een genoemd artikel (acceptatie 8 nov 2026: zes
        # rondes zoeken voor kst-35496-F). Ook in een lopend gesprek: het id staat er letterlijk. Ook met een artikel
        # erbij ("wat zegt de MvT bij Kamerstuk 33755, nr. 3 over artikel 29 IW?"): het stuk gaat voor, met dat artikel als
        # filter (`_te_lezen`); zonder dit las Lex alleen de wettekst (iteratie Kamerstukken K14, 11 nov 2026).
        return _lees_genoemd(writer, aanroepen, "")
    if modus == "auto" and (lijst := _lijst(state, vraag_nu, b.graph)):
        # "Wat is het laatste stuk van dossier 32140?": een zoekvraag met een volgorde, die de code helemaal leest. Ook in
        # een gesprek: de vraag noemt zelf wat er gezocht wordt (acceptatie 9 nov 2026: elf rondes, twee foute antwoorden).
        return _bron_lijst(writer, lijst)

    if (dg := state.get("deelgesprek") or {}).get("profiel") in register_kiesbaar():
        # Doorvragen in het deelgesprek van een subagent (ADR-016 §A4): het profiel ligt op het gesprek vast, en de
        # delegatie hoort dat er later iets veranderde. Geen supervisorstap en geen centrale agent.
        return _deelgesprek(b, writer, state, dg)

    delegatie, opdracht = [], state.get("question", "")
    if modus == "auto":
        titels = _regelingtitels(b.graph)
        # Een antwoord op "welke regeling?" (F02) maakt de vorige opdracht af: de code stelt haar samen.
        if vorige := eerdere_beurten(state.get("messages") or [], opdracht, aantal=1):
            opdracht = subagent_route.aangevuld(opdracht, vorige[-1][0], titels) or opdracht
        delegatie = subagent_route.plan(opdracht, state.get("bronstand"), titels)
    if len(delegatie) > 1 and _start_kind(b, state):
        delegatie = []   # het plan kan niet bewaard en gestart worden: de centrale agent beantwoordt de vraag zelf
    if delegatie:
        # "Vat per uitspraak samen …", "geef per artikel van het hoofdstuk …", "per bron apart" (ADR-016 §A5): subagents
        # in code, met de vraag als opdracht (`nodes/subagent_route.py`). Eén start meteen en de centrale agent vat
        # daarna het rapport samen; twee of drie legt de code eerst aan de jurist voor.
        if len(delegatie) > 1:
            return {"specialist": "subagent_plan", "plan": "", "worker_plan": ["subagent_plan"], "worker_idx": 0,
                    "afwijzen": False, "annotaties_lezen": False, "subagent_plan": subagent_route.als_state(delegatie)}
        # Het profiel dat het werk doet, niet een vaste zin: "het lezen van de reeks" stond ook bij een vraag over de
        # wetsgeschiedenis (E2E 16 nov 2026, D-6). Eén regel: `subagent_route_node` herhaalt hem niet.
        _stap(writer, "Lex", f"geeft de vraag aan een subagent ({delegatie[0][0]})", route="subagent")
        return {"specialist": "subagent_route", "plan": "", "worker_plan": ["subagent_route"], "worker_idx": 0,
                "afwijzen": False, "annotaties_lezen": False, "subagent_plan": subagent_route.als_state(delegatie),
                **({"zelfstandige_vraag": opdracht} if opdracht != state.get("question", "") else {})}

    # ADR-016 §A1 en §A7: geen vaste route pakte de vraag, dus de centrale agent beantwoordt hem. Er is geen modelstap
    # vóór hem en niets wordt herschreven: het gesprek leest hij zelf. Een leesvraag in de vraag zoals de analist haar
    # stelde, gaat ook hier voor: de code zoekt eerst.
    if begripvraag:
        return _begrippen_lees(writer, "")
    if regelvraag:
        return _regels_lees(writer, "")
    if leesvraag:
        return _lees(writer, "")
    if is_standvraag(state.get("question", "")) and isinstance(stand := _delegatie_stand(b, state, {}), tuple):
        # "Wat is er in de deelgesprekken veranderd?" (A6 eind, F03): de code leest de stand per deelgesprek bij de api
        # en geeft hem mee als gegeven; het model riep `delegatie_stand` niet aan en noemde alle drie gewijzigd.
        return {**_naar_centraal(writer, state), "rapporten": stand[1] + "\n\n"}
    return _naar_centraal(writer, state)


def _regel_begrippen(b: Bouw, writer, state: State, vraag: str, zelfstandig: str, modus: str):
    if modus == "auto" and is_begrip_leesvraag(zelfstandig):
        return _begrippen_lees(writer, vraag)
    return None


def _regel_annotaties(b: Bouw, writer, state: State, vraag: str, zelfstandig: str, modus: str):
    if is_leesvraag(zelfstandig, modus):
        return _lees(writer, vraag)
    return None


def _regel_overzicht(b: Bouw, writer, state: State, vraag: str, zelfstandig: str, modus: str):
    if is_overzichtsvraag(zelfstandig):
        return _overzicht(writer, vraag)
    return None


def _regel_bepaling(b: Bouw, writer, state: State, vraag: str, zelfstandig: str, modus: str):
    # "Wat staat er in artikel 9?" na een vraag over de Invorderingswet: pas de herschreven vraag noemt de regeling.
    # Op acceptatie ging zo'n vervolgvraag de open lus in (4 rondes, 18 s) in plaats van de workflow (1 ronde).
    # De regeling raadt de code niet zelf uit de vorige beurt: het model leest het gesprek, de code beslist daarna.
    if modus == "auto" and vraag and (bepaling := lees_bepalingsvraag(zelfstandig, b.graph, live_aan=_live_aan(state),
                                                                         getypt=state.get("question", ""))):
        return _bepaling(writer, bepaling)
    return None


def _regel_buiten(b: Bouw, writer, state: State, vraag: str, zelfstandig: str, modus: str):
    # Hetzelfde voor een regeling buiten de graaf: "En wat staat er in artikel 32?" na artikel 31 Pw noemt de regeling
    # pas herschreven (iteratie ronde 1, I25: anders 4 rondes, 83k en de leden in eigen woorden).
    if modus == "auto" and vraag and _live_aan(state) and (live_bepaling := lees_buiten(
            zelfstandig, _buiten_graaf(b, state, zelfstandig), getypt=state.get("question", ""))):
        return _bepaling(writer, live_bepaling)
    return None


def _regel_dekking(b: Bouw, writer, state: State, vraag: str, zelfstandig: str, modus: str):
    # "Welke bronnen horen daarbij?" is pas herschreven een vraag naar de stand ("… bij de deelvraag '…'"). Op
    # acceptatie ging hij de open lus in: 188 s en 7 rondes voor wat de api zonder model weet.
    if modus == "auto" and vraag and state.get("werkgebied_id") and is_dekkingsvraag(zelfstandig):
        return _agent(writer, state, "deelvragen", "dekking", zelfstandig)
    return None


def _regel_lijst(b: Bouw, writer, state: State, vraag: str, zelfstandig: str, modus: str):
    # "Wat is het laatste stuk?" na een vraag over dossier 32140: pas de herschreven vraag noemt het dossier.
    if modus == "auto" and vraag and (lijst := _lijst(state, zelfstandig, b.graph)):
        return _bron_lijst(writer, lijst)
    return None


#: De regels op de herschreven vraag, in deze volgorde (ADR-016 A2-3c). De supervisor draait ze allemaal na het
#: herschrijven; een overdracht van de centrale agent draait er één, op de vraag die het model zelfstandig formuleerde.
#: Eén regel per route, twee aanroepers: de code beslist in beide vormen of het die route is.
NA_HERSCHRIJVEN = {
    "begrippen": _regel_begrippen,
    "annotaties": _regel_annotaties,
    "overzicht": _regel_overzicht,
    "bepaling": _regel_bepaling,
    "buiten": _regel_buiten,
    "dekking": _regel_dekking,
    "lijst": _regel_lijst,
}


def na_herschrijven(b: Bouw, writer, state: State, vraag: str, *, alleen: str = "") -> dict[str, Any] | None:
    """De route voor een herschreven vraag (`vraag`; leeg = niet herschreven, dan geldt de getypte vraag), of None als
    geen regel haar pakt. Met `alleen` draait één regel uit `NA_HERSCHRIJVEN`."""
    modus = state.get("modus", "auto")
    zelfstandig = vraag or state.get("question", "")
    for naam, regel in NA_HERSCHRIJVEN.items():
        if alleen and naam != alleen:
            continue
        if (route := regel(b, writer, state, vraag, zelfstandig, modus)) is not None:
            return route
    return None


def _entry_node(b: Bouw, state: State) -> str:
    """Ingang voor de huidige worker: een eigen route als die er is, anders de agent⇄tools-lus.

    Wees de vraag afgewezen, dan gaat er geen enkele worker draaien – dat is de hele winst."""
    if state.get("afwijzen"):
        return "afwijzen"
    if state.get("specialist") == "werkgebied":
        return "werkgebied_intake"
    if state.get("specialist") == "bronselectie":
        return "bronselectie"
    if state.get("specialist") == "agent_taak":
        return "agent_taak"
    if state.get("specialist") == "subagent_vervolg":
        return "subagent_vervolg"
    if state.get("specialist") == "subagent_route":
        return "subagent_route"
    if state.get("specialist") == "subagent_plan":
        return "subagent_plan"
    if state.get("bepalingsvraag"):
        return "bepaling_lezen"
    if state.get("bron_lijst"):
        # Een lijstvraag over een bron naast de wet: de zoektool in code (`nodes/bron_lijst.py`), dan de controle.
        return "bron_lijst"
    if state.get("bron_lezen"):
        # Een stuk dat de vraag bij id noemt: eerst lezen (`nodes/bron_lezen.py`), dan formuleren.
        return "bron_lezen"
    if state.get("overzicht_route"):
        # Eerst het overzicht bouwen, dan duiden.
        return "overzicht_bouwen"
    if state.get("begrippen_lezen"):
        return "begrippen_zoeken"
    if state.get("regels_lezen"):
        return "regels_zoeken"
    if state.get("contenttoets"):
        return "contenttoets_voorbereiden"
    if state.get("annotaties_lezen"):
        # Eerst zoeken, dan formuleren.
        return "annotaties_zoeken"
    if state.get("specialist") == "annotatie":
        # Doel al bekend → recht naar de annoteerder; de agent⇄tools-lus zou alleen opzoeken
        # wat de aanroeper al meestuurde. `annoteer_node` haalt het corpus zelf gericht op.
        return "annoteer" if _heeft_opgegeven_doel(state) else "agent"
    return "agent"

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
        _stap(writer, "Klaar", state.get("afwijs_stap") or "niet geannoteerd – vraag opnieuw voor één artikel")
        return {"answer": melding, "messages": [{"role": "assistant", "content": melding}]}
    melding = (
        "Deze vraag gaat niet over Nederlandse wet- en regelgeving, dus daar kan ik je niet mee "
        "helpen. Vraag me gerust naar een bepaling, een begrip of de samenhang tussen artikelen "
        "— of laat me een artikel annoteren volgens het JAS."
    )
    writer({"type": "token", "content": melding})
    _stap(writer, "Klaar", "niet beantwoord – buiten de wetgeving")
    return {"answer": melding, "messages": [{"role": "assistant", "content": melding}]}
