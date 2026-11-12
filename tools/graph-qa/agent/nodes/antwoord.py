"""De antwoord-keten: agent ⇄ tools → verify → (correct) → finalize.

De weg die een gewone vraag aflegt. `verify` toetst de grounding deterministisch — geen tweede
LLM-oordeel — en `correct` krijgt hoogstens één corrigerende poging. `finalize` verzamelt de
bronnen uit de tool-trace, nooit uit de prozatekst van het model.
"""
from __future__ import annotations

import re

from dataclasses import replace

import json
import logging
from collections import Counter
from typing import Any

from bronmodel.antwoord import NIET_GETOETST, Antwoord, antwoord_tekst
from bronmodel.connectors import CONNECTORS
from langgraph.config import get_stream_writer

from ..berichten import CORRECTIE, _parse_final, _schoon_messages, _trim_messages, beurt_start, venster_telling
from ..bronregister import bij, controletrace
from ..focus import na_antwoord
from ..grounding import alleen_gelezen_extern, check_grounding, curate_sources, herstel_citaten, live_niet_letterlijk
from ..narratie import _grounding_melding, _stap, _toolregel, ronde_in_denk
from ..overzicht import bronrijen as overzicht_bronrijen
from ..sjablonen import EXTERN, SJABLONEN, sjabloon_schemas, sjabloon_uit_tekst
from .overzicht import TOOL as OVERZICHT_TOOL
from ..prompts import SYSTEM_PROMPT
from ..provenance import collect_sources
from ..regelingnamen import met_regelingnamen
from ..resultaat import is_fout
from ..specialists import DEFAULT as DEFAULT_SPECIALIST
from ..specialists import get as get_specialist
from ..specialists import methoderol as specialist_methoderol
from ..llm_stap import Rol, stroom
from ..state import State
from ..bronstand import prompt_blok as bronstand_blok
from ..bronstand import waar as bronstand_waar
from ..tools import anthropic_schemas, toegestane_tools
from ..tool_execution import execute_tool
from ..tools.annotatie_tools import ANNOTATIE_TOOL_NAMEN, begrens_antwoord
from ..tools.begrip_tools import alleen_begrippen_gezocht, begrens_begrippen_antwoord
from .context import Bouw

logger = logging.getLogger("graph_qa.orchestrator")
# Dezelfde logger als `beurt_meting` (`agent/beurtmeting.py`): de metingen per beurt staan bij elkaar.
_beurtlog = logging.getLogger("graph_qa.beurt")

#: Tools waarmee de agent de weg zoekt: wat ze teruggeven draagt een sjabloonantwoord niet.
_OPZOEKTOOLS = frozenset({"list_regelingen"})


#: De antwoordlus streamt, dus een ruime limiet kost alleen wat er echt geschreven wordt. 4096 kapte lange duidingen af.
MAX_TOKENS_ANTWOORD = 16000
#: De ophaal-agent schrijft geen tekst voor de jurist, alleen tool-aanroepen.
MAX_TOKENS_OPHALEN = 4096

GEWEIGERD = "Op deze vraag kan ik geen antwoord geven: het model weigerde hem te beantwoorden. Stel de vraag eventueel anders."
AFGEKAPT_ZONDER_TEKST = "Ik kon deze vraag niet afronden: het antwoord paste niet in één beurt. Stel de vraag gerichter."


def agent_node(b: Bouw, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    # Alleen bij de eerste beurt: daarna is elke ronde al herkenbaar aan de graafbevragingen, en
    # zou dit bij elke tool-lus opnieuw voorbijkomen.
    if not state.get("turns"):
        spec_naam = state.get("specialist") or DEFAULT_SPECIALIST
        _stap(writer, "Lex", f"zoekt in {bronstand_waar(state.get('bronstand'))}", route=spec_naam)
    # De annotatie-route draait de agent⇄tools-lus als OPHAAL-agent (retrieval-specialist): hij
    # vindt de exacte bepaling. De JAS-annotatie gebeurt daarna in annoteer_node (pure LLM-call).
    spec_naam = "retrieval" if state.get("specialist") == "annotatie" else state.get("specialist")
    spec = get_specialist(spec_naam)
    # ADR-013: staat er een connector aan die deze rol bedient, dan krijgt elk sjabloon het veld voor bronnen naast de
    # wet (het subsjabloon) en is er het eigen sjabloon `antwoord_extern`. Anders blijven de schema's gelijk.
    rol = spec_naam or DEFAULT_SPECIALIST
    extern_namen = tuple(n for n, s in (state.get("bronstand") or {}).items()
                         if s.get("aan") and n in CONNECTORS and rol in CONNECTORS[n].specialisten) if spec.sjablonen else ()
    extern_aan = bool(extern_namen)
    sjablonen = spec.sjablonen | {EXTERN} if extern_aan else spec.sjablonen
    # Twee delen, en de volgorde is betekenisdragend: het stabiele deel (identiteit +
    # specialist) is bij elke tool-ronde van elke beurt hetzelfde en draagt daarom het
    # prompt-cache-punt; het plan, de geheugen-context en de adviescontext verschillen per
    # beurt en horen er dus áchter. Caching is een prefix-match – één byte verschil vóór het
    # cache-punt maakt de cache waardeloos.
    stabiel = SYSTEM_PROMPT + (f"\n\n{spec.system}" if spec.system else "")
    variabel = ""
    if state.get("plan"):
        variabel += f"AANPAK (door jou gepland):\n{state['plan']}"
    variabel += b.memory_context(state)
    variabel += b.advies_context(state)
    # Welke bronnen naast de wet aanstaan, en waarom niet (ADR-013): na het cachepunt, want het verschilt per beurt.
    variabel += bronstand_blok(state.get("bronstand") or {}, state.get("zelfstandige_vraag") or state.get("question", ""))

    # De annotatie-worker produceert JSON, geen leesbaar antwoord – díe narratie tonen we niet
    # (annoteer_node emit straks een korte samenvatting).
    narratie_tonen = state.get("specialist") != "annotatie"
    historie = _schoon_messages(state["messages"])
    # Historie begrenzen (tegen onbegrensde promptgroei in een lange sessie); state blijft heel.
    venster = _trim_messages(historie, b.settings.max_history_chars, state.get("question", ""))
    if not state.get("turns"):
        # E6-C1: hoe vaak valt er gesprek uit het venster? Eén regel per beurt, zonder inhoud.
        _beurtlog.info("venster", extra={
            "categorie": "functioneel",
            "run_id": state.get("run_id", "") or "",
            "chat_session_id": state.get("gesprek_id", "") or "",
            **venster_telling(historie, venster),
            "register_items": len(state.get("bronregister") or []),
        })
    with stroom(
        b.llm, Rol.OPHAAL if spec_naam == "retrieval" else Rol.ANTWOORD, methoderol=specialist_methoderol(spec_naam),
        # Deze node draait twee verschillende rollen: de OPHAAL-agent (annotatieroute – zoeken
        # en ophalen) en de QA-specialisten (die het antwoord zelf schrijven). Alleen de eerste
        # heeft een eigen modelknop.
        model=b.model_ophaal if spec_naam == "retrieval" else b.model,
        max_tokens=MAX_TOKENS_OPHALEN if spec_naam == "retrieval" else MAX_TOKENS_ANTWOORD,
        system=[stabiel, variabel],
        tools=anthropic_schemas(only=toegestane_tools(spec.tools, b.settings, state.get("bronnen"))) + sjabloon_schemas(sjablonen, extern=extern_namen),
        messages=venster,
        # Elke toolronde stuurt de hele historie opnieuw: een cache-punt aan het eind maakt die de volgende ronde goedkoop.
        historie_cache=True,
    ) as stream:
        # Geen tekst tijdens het streamen: pas aan het eind van de ronde is bekend of dit narratie is
        # of een eindantwoord, en een eindantwoord mag pas na de controle in beeld (`finalize_node`).
        final = stream.final_message()

    tool_uses, text_parts = _parse_final(final)
    if not tool_uses and sjablonen and (aanroep := sjabloon_uit_tekst(text_parts, sjablonen)):
        logger.warning("sjabloon als tekst", extra={"categorie": "functioneel", "run_id": state.get("run_id", ""), "sjabloon": aanroep["name"]})
        tool_uses, text_parts = [aanroep], []
    # Een sjabloon rondt af: staat hij naast graaftools, dan eerst die, en daarna komt hij vanzelf terug.
    if len(tool_uses) > 1:
        tool_uses = [t for t in tool_uses if t["name"] not in SJABLONEN]

    stopreden = getattr(final, "stop_reason", "") or ""
    afgekapt = stopreden == "max_tokens"
    if stopreden == "refusal":
        logger.warning("model weigerde te antwoorden", extra={"categorie": "functioneel", "run_id": state.get("run_id", "")})
        tool_uses, text_parts = [], [GEWEIGERD]
    elif afgekapt:
        # Het laatste blok is halverwege afgebroken: een tool-aanroep daarin heeft halve argumenten, en een aanroep
        # zonder resultaat breekt de volgende beurt. Wat er aan tekst staat blijft, met een zichtbare melding.
        logger.warning("antwoord afgekapt op max_tokens", extra={"categorie": "functioneel", "run_id": state.get("run_id", ""),
                                                                 "tool_aanroepen": len(tool_uses)})
        tool_uses = []
        if not any(p and p.strip() for p in text_parts):
            text_parts = [AFGEKAPT_ZONDER_TEKST]

    # max_turns-vangnet: op de laatste toegestane beurt geen openstaande tool_use persisteren.
    # Anders belandt er een assistant(tool_use) zónder tool_result in de checkpointer (orphan →
    # de volgende beurt in dezelfde conversatie crasht op Anthropic 400) én blijft het antwoord
    # leeg. Laat de tools dan vallen en lever een net eind-antwoord (desnoods een korte melding).
    # Een sjabloon mag de laatste beurt nog afronden, maar een sjabloon dat onvulbaar blijft mag er niet voorbij.
    limiet = b.settings.max_turns if tool_uses and tool_uses[0]["name"] in SJABLONEN else b.settings.max_turns - 1
    if tool_uses and state.get("turns", 0) >= limiet:
        tool_uses = []
        if not any(p and p.strip() for p in text_parts):
            text_parts = [
                "Ik kon deze vraag niet binnen de beurtlimiet afronden; stel 'm eventueel gerichter."
            ]

    if narratie_tonen:
        ronde_in_denk(writer, tool_uses, text_parts, state.get("turns", 0))

    assistant_content: list[dict[str, Any]] = [{"type": "text", "text": p} for p in text_parts if p and p.strip()]
    assistant_content += [
        {"type": "tool_use", "id": t["id"], "name": t["name"], "input": t["input"]}
        for t in tool_uses
    ]

    upd: dict[str, Any] = {
        "messages": [{"role": "assistant", "content": assistant_content}],  # delta (append-reducer)
        "pending_tools": tool_uses,
        "turns": state.get("turns", 0) + 1,
        "afgekapt": afgekapt,
    }
    upd["sjabloon_nu"] = False
    if not tool_uses and sjablonen and (zoektools := _gevonden_zonder_sjabloon(b, state)):
        # Eén keer per beurt: een lijst gevonden stukken in tekst mist de links, de zoekvraag en het totaal uit de code.
        logger.info("sjabloon gevraagd", extra={"categorie": "functioneel", "run_id": state.get("run_id", ""),
                                                "specialist": spec_naam, "zoektools": sorted(zoektools)})
        upd["messages"] = [{"role": "assistant", "content": assistant_content},
                           {"role": "user", "content": SJABLOON_GEVRAAGD.format(
                               tools=", ".join(sorted(zoektools)), sjablonen=", ".join(sorted(sjablonen)))}]
        upd.update(sjabloon_gevraagd=True, sjabloon_nu=True)
        return upd
    if not tool_uses:
        if sjablonen and not state.get("corrected"):
            logger.info("sjabloon gemist", extra={"categorie": "functioneel", "run_id": state.get("run_id", ""), "specialist": spec_naam})
        # De tool-loze beurt is het eindantwoord. Het gaat de state in en pas in `finalize_node` naar
        # de jurist: `verify` kan het nog afkeuren.
        antwoord = "\n\n".join(p for p in text_parts if p)
        if state.get("annotaties_lezen"):
            begrensd = begrens_antwoord(antwoord, state.get("source_trace", []))
            if begrensd != antwoord:
                # Wél melden, anders gebeurt dit volledig stil: in de logs staat dan alleen
                # "antwoord klaar". NIET in `messages` schrijven – die historie gaat via de
                # checkpointer mee naar de volgende beurt, en dan leest het model zijn eigen
                # "ik kon niet raadplegen" als vaststaand feit en probeert het niet opnieuw.
                logger.warning(
                    "leesroute: antwoord begrensd",
                    extra={"categorie": "functioneel", "run_id": state.get("run_id", ""),
                           "annotatietools": sum(1 for naam, _ in state.get("source_trace", [])
                                                 if naam in ANNOTATIE_TOOL_NAMEN)},
                )
            antwoord = begrensd
        elif state.get("begrippen_lezen") or alleen_begrippen_gezocht(state.get("source_trace", [])):
            begrensd = begrens_begrippen_antwoord(antwoord, state.get("source_trace", []))
            if begrensd != antwoord:
                logger.warning("leesroute begrippen: antwoord begrensd",
                               extra={"categorie": "functioneel", "run_id": state.get("run_id", "")})
            antwoord = begrensd
        # Vóór de controle: een bijna-letterlijk citaat (hoofdletter, punt binnen de aanhalingstekens)
        # wordt de brontekst. Anders volgde er een volledige correctieronde voor een afwijking die
        # mechanisch te herstellen is.
        antwoord, hersteld = herstel_citaten(antwoord, controletrace(state))
        if hersteld:
            _stap(writer, "Controle", f"{len(hersteld)} citaat letterlijk gemaakt naar de bron"
                  if len(hersteld) == 1 else f"{len(hersteld)} citaten letterlijk gemaakt naar de bron")
            # Ook in de historie: de volgende beurt bouwt voort op het herstelde antwoord.
            assistant_content = [{**blok, "text": herstel_citaten(blok["text"], controletrace(state))[0]}
                                 if blok.get("type") == "text" else blok for blok in assistant_content]
            upd["messages"] = [{"role": "assistant", "content": assistant_content}]
        upd["answer"] = antwoord
    return upd

#: Wat de agent hoort als hij na een zoekresultaat van een bronconnector in tekst antwoordt (`_gevonden_zonder_sjabloon`).
SJABLOON_GEVRAAGD = ("Je antwoordde in tekst, terwijl deze beurt stukken vond of las met {tools}. Roep het sjabloon aan "
                     "({sjablonen}): wijs de gevonden stukken aan in 'stukken' en de gelezen passages in 'extern', dan "
                     "staan ze erbij met hun link, de zoekvraag en het totaal. Zet je uitleg in het korte antwoord; "
                     "herhaal de lijst niet in tekst.")


def _gevonden_zonder_sjabloon(b: Bouw, state: State) -> set[str]:
    """De tools van een bronconnector die deze beurt iets vonden of lazen, als de agent het sjabloon nog niet gevraagd is en
    er nog een ronde over is; anders leeg. Zonder sjabloon kwam een lijst gevonden stukken als tekst, zonder links,
    zoekvraag of totaal, soms als markdown-tabel (iteratie 11 nov 2026: bekendmakingen B03, B05, B18, B20; rechtspraak R06,
    R17, R18, R22, R23). Hoogstens één keer per beurt (`sjabloon_gevraagd`), en niet na een correctieronde."""
    if state.get("sjabloon_gevraagd") or state.get("corrected") or state.get("turns", 0) + 1 >= b.settings.max_turns:
        return set()
    # Ook een gelezen stuk: in tekst noemde het model nummers die het zelf afleidde, zonder citaat (iteratie ronde 2,
    # B22: "25.2.10 (nieuw)" voor "na artikel 25.2.9 een nieuw artikel"). Een fout (alleen PDF, buiten bereik, niet
    # gevonden) telt niet: daar is niets aan te wijzen.
    connectortools = {t for c in CONNECTORS.values() for t in c.tools}
    gevonden = set()
    for naam, resultaat in state.get("source_trace", []):
        if naam in connectortools and not is_fout(resultaat):
            try:
                data = json.loads(resultaat)
            except (TypeError, ValueError):
                continue
            if isinstance(data, dict) and data.get("resultaten"):
                gevonden.add(naam)
    return gevonden


def route_after_agent(b: Bouw, state: State) -> str:
    if state.get("sjabloon_nu"):
        return "agent"  # één keer terug: om het sjabloon gevraagd (`_gevonden_zonder_sjabloon`)
    pending = state.get("pending_tools") or []
    if pending and pending[0]["name"] in SJABLONEN:
        return "sjabloon"
    if pending and state.get("turns", 0) < b.settings.max_turns:
        return "tools"
    if state.get("specialist") == "annotatie":
        return "annoteer"  # ophaal-agent klaar → de aparte annoteer-stap
    return "verify"


def _sleutel(tu: dict[str, Any]) -> str:
    return tu["name"] + json.dumps(tu.get("input") or {}, sort_keys=True, ensure_ascii=False)


#: Hoe vaak dezelfde aanroep in één beurt mag mislukken voor het resultaat vaststaat. Een tijdelijke fout
#: verdient een tweede kans, een blijvende (ongeldig argument) mag de beurtlimiet niet opeten.
MAX_POGINGEN = 2


def _al_gedaan(state: State) -> dict[str, str]:
    """Wat deze beurt al opvroeg: aanroep → resultaat, uit de berichten van de beurt. Een mislukte aanroep
    telt pas na `MAX_POGINGEN`: een fout zegt niets over de graaf."""
    messages = state.get("messages", [])
    aanroepen: dict[str, str] = {}
    uit: dict[str, str] = {}
    mislukt: Counter[str] = Counter()
    for m in messages[beurt_start(messages, state.get("question", "")):]:
        inhoud = m.get("content")
        for blok in inhoud if isinstance(inhoud, list) else []:
            if not isinstance(blok, dict):
                continue
            if blok.get("type") == "tool_use":
                aanroepen[blok.get("id", "")] = _sleutel(blok)
            elif blok.get("type") == "tool_result" and blok.get("tool_use_id") in aanroepen:
                sleutel = aanroepen[blok["tool_use_id"]]
                mislukt[sleutel] += 1 if blok.get("is_error") else 0
                if not blok.get("is_error") or mislukt[sleutel] >= MAX_POGINGEN:
                    uit[sleutel] = str(blok.get("content", ""))
    return uit


HERHAALD = ("\n\nDezelfde aanroep met dezelfde argumenten is in deze beurt al uitgevoerd; dit is dat resultaat. "
            "Herhaal hem niet, ook niet als er niets gevonden is.")


def _tool_result(tu: dict[str, Any], tekst: str) -> dict[str, Any]:
    """Het resultaat van één aanroep; een fout draagt `is_error`, ook voor `_al_gedaan` straks."""
    fout = is_fout(tekst.removesuffix(HERHAALD))
    return {"type": "tool_result", "tool_use_id": tu["id"], "content": tekst, **({"is_error": True} if fout else {})}


def tools_node(b: Bouw, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    pending = state.get("pending_tools", [])
    # Binnen één beurt verandert de graaf niet: dezelfde aanroep nog eens kost alleen tokens (de e2e-test van 5 nov
    # 2026: drie gelijke zoekopdrachten, 63.867 tokens voor één vraag). Elke aanroep krijgt een resultaat, want het
    # model eist er een; alleen de eerste voert hem uit.
    gedaan = _al_gedaan(state)
    uit_te_voeren = list({_sleutel(t): t for t in reversed(pending) if _sleutel(t) not in gedaan}.values())[::-1]
    _stap(writer, "Lex", "; ".join(_toolregel(t) for t in uit_te_voeren) or "gebruikt wat er al is opgehaald")
    trace = list(state.get("source_trace", []))
    results = []
    for tu in pending:
        sleutel = _sleutel(tu)
        if sleutel in gedaan:
            results.append(_tool_result(tu, gedaan[sleutel].removesuffix(HERHAALD) + HERHAALD))
            continue
        result_text = execute_tool(b, state, writer, tu)
        gedaan[sleutel] = result_text
        trace.append((tu["name"], result_text))
        results.append(_tool_result(tu, result_text))
    return {
        "messages": [{"role": "user", "content": results}],  # delta
        "source_trace": trace,
        "pending_tools": [],
    }

def verify_node(b: Bouw, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    # Getoetst tegen deze beurt én wat eerder in het gesprek letterlijk is opgehaald: een vervolgantwoord
    # dat een citaat uit het vorige antwoord herhaalt, is niet minder brongetrouw dan dat antwoord.
    # Bij een sjabloon niet de blokken die afgeleide duiding of tekst van de code dragen (`NIET_GETOETST`).
    tekst = antwoord_tekst(Antwoord.model_validate(state["antwoord"]), zonder=NIET_GETOETST) if state.get("antwoord") else state.get("answer", "")
    report = check_grounding(tekst, controletrace(state), overzicht=state.get("overzicht") or None, bekend=_bekend(state))
    # Wettekst uit een sjabloon staat zonder aanhalingstekens, dus de toets ziet "niets te controleren". Maar de code
    # toonde hem uit de tool-rijen, met de vindplaats erbij: de melding dat er geen vindplaats is, zou onwaar zijn.
    if report.niveau == "onbepaald" and not report.onbevestigd and (state.get("antwoord") or {}).get("doelen"):
        report = replace(report, niveau="gegrond")
    # Wettekst van overheid.nl in het blok `extern` (ADR-013 fase 1e): elke passage moet letterlijk een gelezen rij van dat
    # stuk zijn. Zo ja, dan is dat dezelfde zekerheid als wettekst uit de graaf in een sjabloon; zo nee, dan is het niet
    # letterlijk, en dat keurt de controle af.
    heeft_live, niet_live = live_niet_letterlijk(state.get("antwoord"), controletrace(state))
    if niet_live:
        report = replace(report, grounded=False, niveau="ongegrond",
                         niet_letterlijk=[*report.niet_letterlijk, *niet_live])
    elif heeft_live and report.niveau == "onbepaald" and not report.onbevestigd:
        report = replace(report, niveau="gegrond")
    # Deze controle heeft geen eigen narratie (geen LLM), dus zonder deze regel gebeurt er iets
    # wezenlijks – de brongetrouwheidstoets – zonder dat de jurist het ziet. De tijdlijn wordt
    # bij de beurt bewaard, dus dit is tegelijk het spoor waarop je achteraf terugvalt.
    # Een feit in de toelichting dat niet in het opgehaalde staat (een datum, een nummer, een telling, een instantie;
    # `beweringen`): eerst één correctieronde, net als een vindplaats zonder bron; staat het er daarna nog, dan is het
    # onbevestigd (Rechtspraak ronde 4, 12 nov 2026: "dossier 20588" en een intrekking bij het verkeerde dossier stonden
    # als feit in de toelichting, en de controle zag ze niet).
    if report.beweringen and not state.get("corrected") and b.settings.grounding_correct and not state.get("overzicht"):
        report = replace(report, grounded=False, niveau="ongegrond")
    elif report.beweringen:
        report = replace(report, onbevestigd=[*report.onbevestigd, *report.beweringen])
        logger.info("grounding: beweringen na de correctie", extra={"categorie": "functioneel",
                                                                    "run_id": state.get("run_id", ""),
                                                                    "aantal": len(report.beweringen)})
    _stap(writer, "Controle", _grounding_melding(report))
    if report.onbevestigd:
        # Alleen het aantal: hiermee is vals alarm te meten voordat dit signaal zwaarder mag wegen.
        logger.info("grounding: niet teruggevonden in het opgehaalde",
                    extra={"categorie": "functioneel", "run_id": state.get("run_id", ""), "aantal": len(report.onbevestigd)})
    return {
        "grounded": report.grounded,
        "cited": len(report.cited),
        "unsupported": report.unsupported,
        "niet_letterlijk": report.niet_letterlijk,
        "onbevestigd": report.onbevestigd,
        "beweringen": report.beweringen if not report.grounded else [],
        "grounding_niveau": report.niveau,
    }


def _bekend(state: State) -> str:
    """Wat de jurist zelf schreef of vastlegde: de vraag, het dossier van het werkgebied, het aangewezen object. Een feit
    daaruit is geen bewering van Lex."""
    return "\n".join(str(state.get(k) or "") for k in ("question", "zelfstandige_vraag", "werkgebied_context",
                                                         "onderwerp_context"))


def route_after_verify(b: Bouw, state: State) -> str:
    if state.get("overzicht"):
        # De tekst komt uit het overzicht zelf; een correctieronde zou het model alsnog laten
        # schrijven. Keurt de controle iets af, dan is dat een fout in `samenvatting` – zichtbaar in
        # het grounding-event, niet stil weggepoetst.
        return "finalize"
    if not state.get("grounded", True) and b.settings.grounding_correct and not state.get("corrected"):
        return "correct"
    return "finalize"

def correct_node(b: Bouw, state: State) -> dict[str, Any]:
    """Eén herkansing op wat de groundingcontrole afkeurde.

    De controle keurt twee dingen af en die vragen een ándere correctie: `unsupported` (verzonnen
    vindplaatsen) en `niet_letterlijk` (tekst die als citaat is gepresenteerd maar niet letterlijk
    in de bron staat). Wie alleen naar `unsupported` kijkt, stuurt bij een antwoord dat alléén op
    het tweede struikelt een volledige extra LLM-call de deur uit met de instructie "je noemde
    verwijzing(en) `` die niet uit de graaf kwamen": een lege opsomming en een verwijt dat niet
    klopt.
    """
    writer = get_stream_writer()
    unsupported = state.get("unsupported") or []
    niet_letterlijk = state.get("niet_letterlijk") or []
    beweringen = state.get("beweringen") or []

    opdrachten: list[str] = []
    if unsupported:
        opdrachten.append(
            f"Je noemde verwijzing(en) {', '.join(unsupported)} die niet uit de graaf-resultaten "
            "kwamen. Onderbouw ze met de tools of verwijder ze."
        )
    if niet_letterlijk:
        # Het fragment zelf mee, afgekapt: zonder de tekst weet het model niet wélk citaat het
        # moet herstellen, en met zeven lange passages loopt de prompt onnodig vol.
        passages = "; ".join(f'"{c[:120]}…"' if len(c) > 120 else f'"{c}"' for c in niet_letterlijk)
        opdrachten.append(
            f"Deze passages staan tussen aanhalingstekens maar niet letterlijk in de opgehaalde "
            f"tekst: {passages}. Herstel ze woord voor woord zoals ze in de bron staan, of "
            "verwijder de aanhalingstekens en geef het in je eigen woorden weer. Weglatingen met (...), "
            "eigen samenvattingen tussen [ ] en vet of cursief binnen een citaat maken het een "
            "parafrase – die presenteer je niet als citaat."
        )

    if beweringen:
        opdrachten.append(
            f"Je schreef als feit {', '.join(beweringen)}, maar dat staat niet in wat je in deze beurt opgehaald of gelezen "
            "hebt. Haal het op met de tools en noem de bron, of laat het weg; schrijf geen datum, nummer, aantal of "
            "instantie uit eigen kennis."
        )
    wat = " en ".join(
        deel for deel in (
            "niet-onderbouwde verwijzingen" if unsupported else "",
            "citaten die niet letterlijk zijn" if niet_letterlijk else "",
            "feiten zonder bron" if beweringen else "",
        ) if deel
    )
    _stap(writer, "Correctie", f"antwoord bijstellen op {wat}")
    # Het bericht staat als user-bericht in de historie, maar komt van de controle. Zonder die
    # afbakening antwoordde het model de jurist met "U heeft gelijk …" over het afgekeurde citaat:
    # dat meta-antwoord werd het zichtbare antwoord én het laatste wat Lex in die beurt "zei", zodat
    # een vervolgvraag ("en lid 2?") op het citaat werd betrokken in plaats van op de vraag.
    return {
        "messages": [{"role": "user", "content": CORRECTIE + " ".join(opdrachten) + _HERSCHRIJF}],
        "corrected": True,
        "answer": "",
        "antwoord": {},
    }


_HERSCHRIJF = (
    "\n\nDit bericht komt van de brongetrouwheidscontrole, niet van de jurist; de jurist ziet het niet. "
    "Schrijf je VOLLEDIGE antwoord op de oorspronkelijke vraag opnieuw, met deze correctie verwerkt – "
    "je nieuwe antwoord vervangt het vorige; rondde je af met een sjabloontool, doe dat dan opnieuw. Reageer niet op deze melding: geen 'u heeft gelijk', geen "
    "excuus, geen verwijzing naar het vorige antwoord."
)

def hergebruikte_bronnen(register, antwoord: str, al) -> list:
    """Bronnen uit het register waarvan het antwoord de regeling (BWB-id) noemt en die er nog niet staan."""
    from ..grounding import _BWB_RE

    bwbs = set(_BWB_RE.findall(antwoord or ""))
    if not bwbs:
        return []
    bekend = {s.uri for s in al}
    return [s for s in collect_sources([(n, t) for n, t in register])
            if s.uri not in bekend and (m := _BWB_RE.search(s.uri)) and m.group(0) in bwbs]


#: Woorden die alleen in de werking van Lex bestaan, nooit in een antwoord aan de jurist: het sjabloon en zijn tools.
_INTERN = re.compile(
    r"\b(?:sjablo(?:on|nen)\w*|antwoord_(?:bepaling|duiding|extern|begrip|annotaties)|brongetrouwheidscontrole"
    # Systeemtaal over de eigen werking (Bekendmakingen B15, 11 nov 2026: "de regels van deze werkplek").
    r"|(?:de\s+)?regels\s+van\s+(?:deze|de)\s+werkplek|systeemprompt|mijn\s+instructies|toolaanroep\w*"
    # Wat het model zegt als het vaste antwoord niet lukte, over de vorm in plaats van over de wet (wetgeving_live ronde
    # 2, I13: "Ik geef de uitleg daarom in tekst, met verwijzing naar de gelezen stukken."; I28: "Ik geef de vergelijking
    # daarom in tekst weer").
    r"|(?:ik\s+geef|geef\s+ik)\s+(?:de|het|mijn|deze)\s+\w+\s+(?:daarom\s+|dus\s+|hier\s+)?in\s+(?:gewone\s+|vrije\s+)?tekst"
    r"|(?:de\s+)?code\s+herkent\s+(?:ze|het|dit|deze)\b"
    # Een tool als vertelstem (ronde 4, I20: "De tool meldt uitdrukkelijk dat …"): de jurist kent geen tools, alleen bronnen.
    r"|(?:de|deze|die|een|mijn)\s+(?:zoek|lees)?tools?\b)\b",
    re.IGNORECASE)
_ZIN = re.compile(r"[^.!?\n]*[.!?]?[ \t]*")


def _lex_zonder_interne_taal(antwoord: dict[str, Any]) -> dict[str, Any] | None:
    """Het sjabloon met de blokken van Lex (`door: "lex"`) zonder interne taal, of None als er niets te halen was. Een
    blok dat zo leeg wordt, valt weg."""
    gewijzigd, blokken = False, []
    for blok in antwoord.get("blokken") or []:
        if blok.get("door") == "lex":
            blok = dict(blok)
            if isinstance(blok.get("tekst"), str) and (t := zonder_interne_taal(blok["tekst"])) != blok["tekst"]:
                gewijzigd, blok["tekst"] = True, t
                if not t:
                    continue
            if isinstance(blok.get("punten"), list):
                punten = [p for p in (zonder_interne_taal(str(x)) for x in blok["punten"]) if p]
                if punten != blok["punten"]:
                    gewijzigd, blok["punten"] = True, punten
                    if not punten:
                        continue
        blokken.append(blok)
    return {**antwoord, "blokken": blokken} if gewijzigd else None


def zonder_interne_taal(tekst: str) -> str:
    """De tekst zonder de zinnen die over de interne werking gaan (het sjabloon, de tool, de controle). Per regel en per
    zin, zodat de rest van het antwoord blijft staan; een regel die zo leeg wordt, vervalt."""
    if not _INTERN.search(tekst or ""):
        return tekst
    regels = []
    for regel in tekst.split("\n"):
        if not _INTERN.search(regel):
            regels.append(regel)
            continue
        rest = "".join(z for z in _ZIN.findall(regel) if z and not _INTERN.search(z)).strip()
        if rest:
            regels.append(rest)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(regels)).strip()


def finalize_node(b: Bouw, state: State) -> dict[str, Any]:
    writer = get_stream_writer()

    # Vangnet tegen een stil leeg antwoord. Dat kan gebeuren als de agent een lege tekstbeurt
    # levert, of nadat correct_node het antwoord heeft gewist voor een grounding-correctie die
    # daarna niets oplevert. De gebruiker zag dan alleen de bronnen en de frontend-fallback
    # "(geen antwoord)" – zonder spoor in de logs. Liever een eerlijke melding, en altijd een
    # logregel zodat het volgende geval terug te vinden is.
    antwoord = state.get("answer", "") or ""
    if state.get("antwoord") and (blokken := _lex_zonder_interne_taal(state["antwoord"])) is not None:
        # Een sjabloon: alleen wat Lex schreef (toelichting, kort antwoord, twijfel) kan interne taal dragen; de rest komt
        # uit de bron. Daarna de vaste tekst opnieuw, zodat tekst en blokken gelijk blijven.
        logger.warning("interne taal uit het antwoord gehaald", extra={"categorie": "functioneel",
                                                                         "run_id": state.get("run_id", "")})
        schoon_antwoord = Antwoord.model_validate(blokken)
        antwoord = antwoord_tekst(schoon_antwoord)
        state = {**state, "antwoord": schoon_antwoord.model_dump(), "answer": antwoord}
    if not state.get("antwoord") and (schoon := zonder_interne_taal(antwoord)) != antwoord:
        # Na een geweigerd sjabloon schreef het model de weigering naar de jurist ("Het sjabloon detecteert elke
        # verwijzing …", iteratie ronde 1, I28). Interne taal hoort nooit in het antwoord; de zin gaat eruit, met een spoor.
        logger.warning("interne taal uit het antwoord gehaald", extra={"categorie": "functioneel",
                                                                         "run_id": state.get("run_id", "")})
        antwoord = schoon
        state = {**state, "answer": antwoord}
    if not antwoord.strip():
        reden = "grounding-correctie leverde geen antwoord" if state.get("corrected") else "lege antwoordbeurt"
        logger.warning(
            "leeg antwoord in finalize",
            extra={
                "reden": reden,
                "turns": state.get("turns", 0),
                "specialist": state.get("specialist"),
                "grounded": state.get("grounded", True),
                "unsupported": state.get("unsupported", []),
                "bronnen": len(state.get("source_trace", []) or []),
            },
        )
        antwoord = (
            "Ik kon op basis van de geraadpleegde bronnen geen antwoord formuleren. "
            "De gevonden bronnen staan hieronder; stel de vraag eventueel gerichter "
            "(bijvoorbeeld met een specifiek artikel of lid)."
        )
        state = {**state, "answer": antwoord}

    # De enige plek in de antwoordketen die `token` uitstuurt: dit is de tekst die de controle zag. Een
    # controle die volgt op publicatie houdt niets tegen, en een tekst blijft dan naast zijn correctie
    # staan. Keurde de laatste ronde hem af, dan gaat hij mee met het oordeel in het grounding-event.
    if state.get("antwoord"):
        writer({"type": "antwoord", "antwoord": state["antwoord"]})
    writer({"type": "token", "content": antwoord})

    if state.get("overzicht"):
        # De overzichtsroute: de bronnen zijn de vindplaatsen van het overzicht, en hangen dus niet af
        # van de tekst – geen cureren op de proza, geen bronnen van eerder.
        sources = collect_sources([(OVERZICHT_TOOL, overzicht_bronrijen(state["overzicht"]))])
    elif state.get("antwoord"):
        # Een sjabloon draagt zijn vindplaatsen zelf; cureren op de proza heeft dan geen zin. Zonder doelen (een
        # leemte) rust de toelichting op wat er verder is opgehaald, en dat moet herleidbaar blijven.
        # Een vervolgvraag kan op een eerdere beurt rusten, dus de doelen zoek je in de hele controletrace.
        # Een regeling opzoeken is geen bron: daarmee vond Lex alleen het BWB-id.
        # Een stuk waaruit het blok `extern` citeert, is ook een vindplaats van het antwoord: met doelen viel het anders
        # weg (meting bekendmakingen B04: alleen art. 36 lid 2, niet het gelezen Stb. 2010, 176).
        doelen = ({d["iri"] for d in state["antwoord"].get("doelen") or []}
                  | ({b["id"] for b in state["antwoord"].get("blokken") or []
                      if b.get("soort") == "extern" and b.get("id")} if state["antwoord"].get("doelen") else set()))
        sources = ([s for s in collect_sources(controletrace(state)) if s.uri in doelen] if doelen
                   else collect_sources([(n, t) for n, t in state.get("source_trace", []) if n not in _OPZOEKTOOLS]))
    else:
        sources = collect_sources(state.get("source_trace", []))
        # Bronnen uit eerdere beurten alleen als het antwoord hun regeling noemt: anders vult elke
        # vervolgvraag de lijst met alles wat het gesprek ooit ophaalde.
        sources += hergebruikte_bronnen(state.get("bronregister") or [], state.get("answer", ""), sources)
        if b.settings.curate_sources:
            sources = curate_sources(sources, state.get("answer", ""))
    if not state.get("overzicht"):
        # Een bron naast de wet alleen als ze gelezen en genoemd is; een zoekresultaat is geen bron (ADR-013).
        geciteerd = frozenset(b["id"] for b in (state.get("antwoord") or {}).get("blokken") or []
                              if b.get("soort") == "extern" and b.get("id"))
        sources = alleen_gelezen_extern(sources, controletrace(state), state.get("answer", ""),
                                        state.get("question", ""), geciteerd)
    # Na het cureren: alleen de namen van regelingen die in de lijst blijven (één query per beurt).
    sources = met_regelingnamen(b.graph, sources)
    src_dicts = [s.model_dump() for s in sources]
    _stap(writer, "Klaar", f"{len(src_dicts)} bron" + ("nen" if len(src_dicts) != 1 else ""))
    writer({"type": "sources", "sources": src_dicts})
    writer({
        "type": "grounding",
        "grounded": state.get("grounded", True),
        "cited": state.get("cited", 0),
        "unsupported": state.get("unsupported", []),
        "niet_letterlijk": state.get("niet_letterlijk", []),
        "niveau": state.get("grounding_niveau", "gegrond"),
        **({"afgekapt": True} if state.get("afgekapt") else {}),
        **({"onbevestigd": state["onbevestigd"]} if state.get("onbevestigd") else {}),
    })
    # entiteit-tier: alleen nieuwe IRI's toevoegen (append-reducer + dedup).
    existing = set(state.get("entities_seen") or [])
    new = [s["uri"] for s in src_dicts if s["uri"] not in existing]
    upd: dict[str, Any] = {"sources": src_dicts, "entities_seen": new,
                           "bronregister": bij(state.get("bronregister"), state.get("source_trace")),
                           "focus": na_antwoord(state.get("focus"), state.get("specialist", ""),
                                                [s["uri"] for s in src_dicts])}
    return upd
