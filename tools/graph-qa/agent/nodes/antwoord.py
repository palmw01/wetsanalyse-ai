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
from uuid import uuid4

from bronmodel.antwoord import NIET_GETOETST, Antwoord, antwoord_tekst
from bronmodel.connectors import CONNECTORS
from langgraph.config import get_stream_writer

from ..beurtmeting import tel_sjabloon
from ..berichten import (CORRECTIE, _parse_final, _schoon_messages, _trim_messages, beurt_start, met_beurtcontext,
                         venster_telling)
from ..bronregister import bij, controletrace
from ..focus import genoemd_in_antwoord, na_antwoord
from ..grounding import alleen_gelezen_extern, check_grounding, curate_sources, herstel_citaten, live_niet_letterlijk
from ..narratie import _grounding_melding, _stap, _toolregel, ronde_in_denk, zonder_aanloop
from ..overzicht import bronrijen as overzicht_bronrijen
from ..sjablonen import EXTERN, SJABLONEN, Onvulbaar, sjabloon_uit_tekst
from ..sjablonen import vul as sjabloon_vul
from ..sjablonen.extern import MAX_LIJST
from .overzicht import TOOL as OVERZICHT_TOOL
from .sjabloon import vul_aanroep
from ..provenance import alleen_genoemde_regelingen, collect_sources
from ..beweringen import regelingen_genoemd
from ..buiten_graaf import _graafnamen
from ..regelingnamen import met_regelingnamen
from ..resultaat import is_fout
from ..agentvorm import STANDAARD as DEFAULT_SPECIALIST, agent_van
from ..overdracht import OVERDRACHT
from ..state import State
from ..subagent import open_vraag, vraagkaart
from ..bronstand import prompt_blok as bronstand_blok
from ..bronstand import waar as bronstand_waar
from ..tool_execution import execute_tool
from ..tools.annotatie_tools import ANNOTATIE_TOOL_NAMEN, begrens_antwoord
from ..tools.begrip_tools import alleen_begrippen_gezocht, begrens_begrippen_antwoord
from .context import Bouw

logger = logging.getLogger("graph_qa.orchestrator")
# Dezelfde logger als `beurt_meting` (`agent/beurtmeting.py`): de metingen per beurt staan bij elkaar.
_beurtlog = logging.getLogger("graph_qa.beurt")

#: Tools waarmee de agent de weg zoekt: wat ze teruggeven draagt een sjabloonantwoord niet.
_OPZOEKTOOLS = frozenset({"list_regelingen"})

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
    # De agent van deze beurt (ADR-016): het profiel bepaalt de systeemtekst, de tools, de sjablonen, het model en de
    # rol, en de agent doet de modelaanroep. ADR-013: staat er een connector aan die het profiel noemt, dan krijgt elk
    # sjabloon het veld voor bronnen naast de wet (het subsjabloon) en is er het eigen sjabloon `antwoord_extern`.
    agent = agent_van(state)
    extern_aan = bool(agent.extern(state.get("bronstand")))
    sjablonen = agent.sjablonen(state.get("bronstand"))
    stabiel = agent.systeemtekst
    variabel = ""
    if state.get("plan"):
        variabel += f"AANPAK (door jou gepland):\n{state['plan']}"
    if state.get("rapporten"):
        # Na een klik op een vraagkaart van een subagent (ADR-016 §A4): het rapport dat de code ophaalde, met de kop die
        # zegt dat het een gegeven is. Alleen dan: zonder rapporten is het verzoek byte-gelijk.
        variabel += state["rapporten"]
    variabel += b.memory_context(state)
    variabel += b.advies_context(state)
    # Welke bronnen naast de wet aanstaan, en waarom niet (ADR-013): na het cachepunt, want het verschilt per beurt.
    variabel += bronstand_blok(state.get("bronstand") or {}, state.get("zelfstandige_vraag") or state.get("question", ""))
    if extern_aan:
        # Vóór deze regel zei de rol "antwoord gewoon in tekst" bij elke vraag die om meer gaat dan de wettekst, en vroeg
        # de code daarna alsnog om het sjabloon: elk antwoord na een vondst werd twee keer geschreven (iteratie
        # wetgeving_live ronde 4: ~20–25k tokens per vraag, bij alle connectors).
        variabel += AFRONDEN_EXTERN.format(extern=EXTERN)

    # De annotatie-worker produceert JSON, geen leesbaar antwoord – díe narratie tonen we niet
    # (annoteer_node emit straks een korte samenvatting).
    narratie_tonen = state.get("specialist") != "annotatie"
    historie = _schoon_messages(state["messages"])
    # Historie begrenzen (tegen onbegrensde promptgroei in een lange sessie); state blijft heel.
    venster = _trim_messages(historie, b.settings.max_history_chars, state.get("question", ""))
    telling = venster_telling(historie, venster)
    # Voor de contextweergave: waar deze beurt begint, wat het venster van de historie overliet en waar het begint op te
    # ruimen. Het gaat met de rol naar de meter (`llm_stap`, `kader`), niet naar het model.
    meetkader = {"beurt_start": beurt_start(venster, state.get("question", "")), "venster_telling": telling,
                 "historiegrens_tekens": b.settings.max_history_chars}
    if state.get("opdracht"):
        # Een subagent (ADR-016 §A3): zijn eerste bericht is de opdracht van de centrale agent (categorie `opdracht`).
        meetkader["opdracht"] = True
    if not state.get("turns"):
        # E6-C1: hoe vaak valt er gesprek uit het venster? Eén regel per beurt, zonder inhoud.
        _beurtlog.info("venster", extra={
            "categorie": "functioneel",
            "run_id": state.get("run_id", "") or "",
            "chat_session_id": state.get("gesprek_id", "") or "",
            **telling,
            "register_items": len(state.get("bronregister") or []),
        })
    # De context van deze beurt staat ná de historie, als eerste blok van de vraag (`met_beurtcontext`): dan leest de
    # prompt-cache de historie van de vorige beurt in plaats van haar opnieuw te schrijven.
    if state.get("beurtcontext_plek") == "systeem":
        # De meetvlag van ADR-015: de vorm van vóór, het variabele deel in de systeemprompt en geen cachepunten op de
        # berichten. Alleen om beide vormen op dezelfde code te vergelijken.
        systeem, berichtpunten = [stabiel, variabel], ()
    else:
        venster, berichtpunten = met_beurtcontext(venster, state.get("question", ""), variabel)
        systeem = [stabiel]
    final = agent.ronde(b.llm, b.settings, systeem=systeem, berichten=venster, berichtpunten=berichtpunten,
                        bronnen=state.get("bronnen"), bronstand=state.get("bronstand"), kader=meetkader,
                        werkgebied=bool(state.get("werkgebied_id")))

    tool_uses, text_parts = _parse_final(final)
    telling: dict[str, Any] = {}
    if not tool_uses and sjablonen and (aanroep := sjabloon_uit_tekst(text_parts, sjablonen)):
        logger.warning("sjabloon als tekst", extra={"categorie": "functioneel", "run_id": state.get("run_id", ""), "sjabloon": aanroep["name"]})
        tool_uses, text_parts = [aanroep], []
        telling = tel_sjabloon(state, "als_tekst")
    # Een sjabloon rondt af en komt als laatste. Staat hij naast graaftools, dan voert `tools_node` eerst die uit en vult
    # daarna het sjabloon met wat ze opleverden. Eerst viel het sjabloon hier weg en schreef het model het de volgende
    # ronde helemaal opnieuw (~2.000 uitvoertokens); alleen één sjabloon per ronde, het eerste.
    sjabloonaanroepen = [t for t in tool_uses if t["name"] in SJABLONEN]
    if sjabloonaanroepen and len(tool_uses) > 1:
        tool_uses = [t for t in tool_uses if t["name"] not in SJABLONEN] + sjabloonaanroepen[:1]
        telling = tel_sjabloon({**state, **telling}, "uitgesteld")

    # Een overdrachtstool van de agent (ADR-016 §A1) geeft de beurt aan een route in code: alleen die ene aanroep blijft.
    if eigen := [t for t in tool_uses if t["name"] in agent.eigen_tools]:
        tool_uses = eigen[:1]

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

    # Een ronde die afrondt met een sjabloon is het antwoord, geen narratie: wat het model ernaast schreef, zegt het
    # sjabloon opnieuw. Het gaat niet naar het denkproces en niet de historie in (die krijgt de tekst van het sjabloon,
    # `sjabloon_node`); de telling meet hoeveel het model er toch schreef (acceptatie K17: ~1.500 tekens).
    if any(t["name"] in SJABLONEN for t in tool_uses):
        if ernaast := sum(len(p) for p in text_parts if p and p.strip()):
            telling = tel_sjabloon({**state, **telling}, "tekst_ernaast", aantal=ernaast)
        text_parts = []

    if narratie_tonen:
        ronde_in_denk(writer, tool_uses, text_parts, state.get("turns", 0), afronden=SJABLONEN)

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
    upd.update(telling)
    gevonden = _gevonden_zonder_sjabloon(b, state) if not tool_uses and sjablonen else {}
    tekst = "\n\n".join(p for p in text_parts if p)
    lijst = bool(gevonden) and heeft_lijst(tekst)
    if lijst and (omzetting := lijst_omzetten(tekst, gevonden, sjablonen, controletrace(state))) is not None:
        # Een lijst gevonden stukken in tekst zet de code zelf om naar het sjabloon: de stukken die de lijst noemt, met
        # de rest van de tekst als kort antwoord. Het herhaalverzoek kostte de hele context opnieuw en zette er soms
        # stukken bij die niet gevraagd waren (iteratie wetgeving_live ronde 5: I01 en I14 elk een ronde van ~25k, I12
        # 25 paragrafen en twee weigeringen, 213k).
        soort, aanroep = omzetting
        logger.info("lijst in tekst", extra={"categorie": "functioneel", "run_id": state.get("run_id", ""),
                                             "specialist": spec_naam, "uitkomst": soort,
                                             "stukken": len((aanroep or {}).get("input", {}).get("stukken") or [])})
        if aanroep is not None:
            upd["messages"] = [{"role": "assistant", "content": [
                {"type": "tool_use", "id": aanroep["id"], "name": aanroep["name"], "input": aanroep["input"]}]}]
            upd["pending_tools"] = [aanroep]
            upd.update(tel_sjabloon({**state, **upd}, "omgezet"))
            return upd
        lijst = False  # een opbouw of een lijst zonder stukken: de tekst is het antwoord
        upd.update(tel_sjabloon({**state, **upd}, "lijst_aangenomen"))
    if lijst:
        # Eén keer per beurt: een lijst gevonden stukken in tekst mist de links, de zoekvraag en het totaal uit de code.
        # Alleen bij een lijst: tekst zonder lijst is een geldig antwoord, en een tweede ronde kostte de hele context
        # opnieuw. Het verzoek noemt de stukken die de lijst noemt, zodat er geen lijst bij komt die niet gevraagd is
        # (iteratie wetgeving_live ronde 4, I13 en I30: 25 en 17 artikelen onder een opbouw en een telling).
        genoemd = genoemde_stukken(tekst, gevonden)
        logger.info("sjabloon gevraagd", extra={"categorie": "functioneel", "run_id": state.get("run_id", ""),
                                                "specialist": spec_naam, "zoektools": sorted(gevonden),
                                                "genoemd": len(genoemd)})
        upd["messages"] = [{"role": "assistant", "content": assistant_content},
                           {"role": "user", "content": sjabloon_gevraagd(sorted(gevonden), sorted(sjablonen), genoemd)}]
        upd.update(sjabloon_gevraagd=True, sjabloon_nu=True, **tel_sjabloon({**state, **upd}, "gevraagd"))
        return upd
    if not tool_uses:
        if gevonden and not (upd.get("sjabloon_telling") or {}).get("lijst_aangenomen"):
            logger.info("tekst zonder lijst aangenomen", extra={"categorie": "functioneel", "run_id": state.get("run_id", ""),
                                                                "specialist": spec_naam, "zoektools": sorted(gevonden)})
            upd.update(tel_sjabloon({**state, **upd}, "tekst_zonder_lijst"))
        elif sjablonen and not state.get("corrected"):
            logger.info("sjabloon gemist", extra={"categorie": "functioneel", "run_id": state.get("run_id", ""), "specialist": spec_naam})
            upd.update(tel_sjabloon({**state, **upd}, "gemist"))
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
        # Een eigen kanttekening als blokcitaat ("> Let op: …") lijkt een citaat uit de bron (ronde 6, I28): de vorm valt weg,
        # de tekst blijft. Ook in de historie, zodat een vervolgbeurt hem niet als citaat leest.
        antwoord, ontcitaat = kanttekening_als_tekst(antwoord, controletrace(state))
        # Procestaal boven een scheidingslijn ("Nu heb ik … Ik kan het antwoord nu opbouwen. ---") is geen antwoord
        # (nameting #1274, K07): ze gaat naar het denkproces, niet naar de jurist en niet de historie in.
        antwoord, aanloop = zonder_aanloop(antwoord)
        if aanloop:
            writer({"type": "reason", "content": aanloop + "\n\n"})
        if ontcitaat:
            logger.info("blokcitaat zonder bron als tekst", extra={"categorie": "functioneel",
                                                                   "run_id": state.get("run_id", ""), "aantal": ontcitaat})
        if hersteld:
            _stap(writer, "Controle", f"{len(hersteld)} citaat letterlijk gemaakt naar de bron"
                  if len(hersteld) == 1 else f"{len(hersteld)} citaten letterlijk gemaakt naar de bron")
        if hersteld or ontcitaat or aanloop:
            # Ook in de historie: de volgende beurt bouwt voort op het herstelde antwoord.
            assistant_content = [{**blok, "text": zonder_aanloop(kanttekening_als_tekst(
                                     herstel_citaten(blok["text"], controletrace(state))[0], controletrace(state))[0])[0]}
                                 if blok.get("type") == "text" else blok for blok in assistant_content]
            upd["messages"] = [{"role": "assistant", "content": assistant_content}]
        upd["answer"] = antwoord
    return upd

#: Het afronden als er een bron naast de wet aanstaat; in de context van de beurt (`met_beurtcontext`), na de historie.
AFRONDEN_EXTERN = (
    "\n\nAFRONDEN MET EEN BRON NAAST DE WET: vond of las je in deze beurt iets met een tool van zo'n bron, dan schrijf "
    "je geen antwoord in tekst maar rond je af met een sjabloontool, ook als de vraag om uitleg, een telling of een "
    "opbouw gaat. Dit gaat voor 'antwoord in tekst' hierboven. Gaat de vraag alleen over zo'n bron, gebruik dan "
    "{extern} en zet je uitleg in kort_antwoord. Vul 'stukken' alleen als de vraag om een lijst stukken vraagt (welke, "
    "de nieuwste, alle …); bij een telling, een opbouw of een uitleg blijft 'stukken' leeg en noem je het totaal in je "
    "eigen woorden. Heb je dan ook geen passage aan te wijzen, antwoord dan in tekst: een sjabloon zonder stuk en "
    "zonder passage is niet te vullen.")

#: Wat de agent hoort als hij na een vondst van een bronconnector een lijst in tekst schreef (`_gevonden_zonder_sjabloon`).
SJABLOON_GEVRAAGD = ("Je antwoordde met een lijst in tekst, terwijl deze beurt stukken vond of las met {tools}. Roep het "
                     "sjabloon aan ({sjablonen}) met je uitleg in het korte antwoord; herhaal de lijst niet in tekst. "
                     "{stukken} Een gelezen passage die je citeert, wijs je aan in 'extern'.")
_STUKKEN_GENOEMD = "Zet in 'stukken' de stukken die je lijst noemt, en geen andere: {ids}."
_STUKKEN_ONBEKEND = ("Zet in 'stukken' alleen de stukken die je lijst noemt; noemt je lijst geen gevonden stukken, laat "
                     "'stukken' dan leeg.")


def sjabloon_gevraagd(tools: list[str], sjablonen: list[str], genoemd: list[str]) -> str:
    stukken = _STUKKEN_GENOEMD.format(ids=", ".join(genoemd)) if genoemd else _STUKKEN_ONBEKEND
    return SJABLOON_GEVRAAGD.format(tools=", ".join(tools), sjablonen=", ".join(sjablonen), stukken=stukken)


#: Een regel van een opsomming of een tabel in markdown.
_LIJSTREGEL = re.compile(r"^\s*(?:[-*•]\s+|\d+[.)]\s+|\|.*\|\s*$)", re.M)


def heeft_lijst(tekst: str) -> bool:
    """Draagt de tekst een opsomming of tabel (twee regels of meer)? Dan mist hij wat de code bij een lijst toont: de
    link, de zoekvraag en het totaal."""
    return len(_LIJSTREGEL.findall(tekst or "")) >= 2


_BLOKCITAAT = re.compile(r"(?:^[ \t]*>.*(?:\n|$))+", re.MULTILINE)


def kanttekening_als_tekst(tekst: str, trace: Any) -> tuple[str, int]:
    """Een blokcitaat ("> …") dat niet letterlijk in het opgehaalde staat, wordt gewone tekst: de vorm zegt "uit de bron",
    en een eigen kanttekening als citaat kwam als `onbevestigd` door de controle (wetgeving_live ronde 6, I28: "> Let op:
    artikel 33 IW 1990 ziet op …"). Een echt blokcitaat blijft staan. Geeft de tekst en het aantal omgezette blokken."""
    from ..annotatie import _normaliseer, komt_letterlijk_voor
    from ..resultaat import waarden

    if ">" not in (tekst or ""):
        return tekst, 0
    bron = _normaliseer("\n".join(waarden(t) for _, t in trace or [] if t))
    omgezet = 0

    def vervang(m: re.Match[str]) -> str:
        nonlocal omgezet
        blok = m.group(0)
        regels = [re.sub(r"^[ \t]*>[ \t]?", "", r) for r in blok.splitlines()]
        passage = " ".join(regels).strip().strip('"„”“')
        if not passage or komt_letterlijk_voor(bron, passage):
            return blok
        omgezet += 1
        return "\n".join(regels) + ("\n" if blok.endswith("\n") else "")

    return _BLOKCITAAT.sub(vervang, tekst), omgezet


def _kern(label: str) -> str:
    """Het nummer van een stuk uit zijn label: het label vanaf het eerste cijfer ("Artikel 19a" → "19a", "Stb. 2010, 176"
    → "2010, 176", "Kamerstukken 34273, nr. 7" → "34273, nr. 7"). Uit het label, niet uit een vaste vorm, dus voor elke
    connector; leeg als het label geen cijfer draagt."""
    m = re.search(r"\d", label or "")
    return label[m.start():].strip().lower() if m else ""


_OPMAAK = re.compile(r"[*_`§]+")
#: Een kern die alleen een kort nummer is ("4", "19a"): aan het begin van een opsomming even goed een telling.
_KAAL = re.compile(r"\d{1,4}[a-z]{0,3}")


def _begin_van(regel: str) -> str:
    """Waar een lijstregel mee begint: de eerste cel van een tabelrij, of de tekst na het opsommingsteken, zonder opmaak
    ("| **19a** | …" → "19a", "- § 22a Aangifte…" → "22a aangifte…")."""
    r = regel.strip()
    if r.startswith("|"):
        r = r.strip("|").split("|", 1)[0]
    else:
        r = re.sub(r"^(?:[-*•]|\d+[.)])\s+", "", r)
    r = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", r)  # een link: alleen de tekst
    return " ".join(_OPMAAK.sub("", r).split()).lower()


def _noemt(regel: str, paren: list[tuple[str, str]], kernen: dict[str, str]) -> list[str]:
    """De ids die één lijstregel noemt: bij id of label als heel woord, of met haar begin gelijk aan de kern van een label
    die bij één stuk uit de trace hoort (een tabel met kale nummers, wetgeving_live ronde 6, I14: "**19a**")."""
    laag, begin = regel.lower(), _begin_van(regel)
    uit = [ident for ident, label in paren
           if any(n and re.search(rf"(?<!\w){re.escape(n.lower())}(?!\w)", laag) for n in (ident, label))]
    labels = dict(paren)
    for kern, ident in kernen.items():
        if ident in uit or not (begin == kern or re.match(rf"{re.escape(kern)}(?![\w])", begin)):
            continue
        # Een kort kaal nummer aan het begin van een opsomming is vaak een telling ("- **4** nog niet in werking", ronde 7,
        # I30). Dat telt alleen als de regel precies dat nummer is (een tabelcel) of ook het voorvoegsel van het label draagt
        # ("§ 22a …", "Artikel 19a …"); een kern met meer dan een nummer ("2010, 176") is onderscheidend genoeg.
        label = labels.get(ident) or ""
        voor = label[: len(label) - len(kern)].strip().lower()
        if begin != kern and _KAAL.fullmatch(kern) and not (voor and voor in laag):
            continue
        uit.append(ident)
    return uit


def _lijstregels(tekst: str) -> list[str]:
    """De regels van opsommingen en tabellen, zonder de scheidingsregel van een tabel."""
    return [r for r in (tekst or "").splitlines() if _LIJSTREGEL.match(r) and not re.fullmatch(r"\s*\|[\s|:-]*\|\s*", r)]


def genoemde_stukken(tekst: str, gevonden: dict[str, list[tuple[str, str]]]) -> list[str]:
    """De ids van de gevonden of gelezen stukken die de lijst in de tekst noemt, in de volgorde van de trace. Alleen de
    lijstregels tellen, niet de lopende tekst: "van artikel 1 tot en met artikel 86" is geen lijst, en een opsomming van
    statussen noemt geen stuk (ronde 6, I30). Een label telt als heel woord ("Artikel 1" niet in "Artikel 19"), een kaal
    nummer alleen als het bij één stuk hoort."""
    paren = list(dict.fromkeys(p for ps in gevonden.values() for p in ps))
    per_kern: dict[str, set[str]] = {}
    for ident, label in paren:
        if k := _kern(label):
            per_kern.setdefault(k, set()).add(ident)
    kernen = {k: next(iter(ids)) for k, ids in per_kern.items() if len(ids) == 1}
    genoemd = {i for r in _lijstregels(tekst) for i in _noemt(r, paren, kernen)}
    return [ident for ident, _ in paren if ident in genoemd]


def zonder_lijstregels(tekst: str, genoemd: list[str], gevonden: dict[str, list[tuple[str, str]]]) -> str:
    """De tekst zonder de lijstregels die een genoemd stuk noemen; een tabel met zo'n rij gaat er helemaal uit. Wat
    overblijft is de uitleg eromheen."""
    def noemt(regel: str) -> bool:
        return any(i in genoemd for i in genoemde_stukken(regel, gevonden))
    regels = (tekst or "").splitlines()
    tabel = any(r.strip().startswith("|") and noemt(r) for r in regels)
    uit = [r for r in regels if not (_LIJSTREGEL.match(r) and (noemt(r) or (tabel and r.strip().startswith("|"))))]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(uit)).strip()


def lijst_omzetten(tekst: str, gevonden: dict[str, list[tuple[str, str]]], sjablonen: frozenset[str] | set[str],
                   trace: Any) -> tuple[str, dict[str, Any] | None] | None:
    """Een lijst in tekst na een vondst van een connector, zonder modelronde afgehandeld:
    - ("omgezet", aanroep): de stukken die de lijst noemt in het sjabloon `antwoord_extern`, met de rest als kort antwoord;
    - ("aangenomen", None): de lijst noemt geen gevonden stuk en er is niets gelezen (een opsomming van statussen na een
      zoekvraag, I30), of ze noemt meer stukken dan één blok draagt (`MAX_LIJST`; een opbouw, I12): de tekst is het antwoord;
    - None: de lijst noemt geen stuk terwijl er een stuk gelezen is (een tabel met nummers die het model uit de tekst
      afleidde, B22: de passages horen in 'extern'), er staat naast de lijst geen uitleg, of het sjabloon is niet te
      vullen; dan het herhaalverzoek."""
    if EXTERN not in sjablonen:
        return None
    genoemd = genoemde_stukken(tekst, gevonden)
    if not genoemd and set(gevonden) & {c.leestool for c in CONNECTORS.values()}:
        return None
    if not genoemd or len(genoemd) > MAX_LIJST:
        return ("aangenomen", None)
    kort = zonder_lijstregels(tekst, genoemd, gevonden)
    invoer = {"kort_antwoord": kort, "extern": [], "stukken": genoemd, "twijfel": []}
    try:
        sjabloon_vul(EXTERN, invoer, trace)
    except Onvulbaar:
        return None
    return ("omgezet", {"id": f"omgezet_{uuid4().hex[:12]}", "name": EXTERN, "input": invoer})


def _stukken_in(data: dict[str, Any]) -> list[tuple[str, str]]:
    """(id, label) van wat een connectortool teruggaf: het gelezen stuk en de zoekrijen."""
    rijen = [data["stuk"]] if isinstance(data.get("stuk"), dict) else []
    rijen += [r for r in data.get("resultaten") or [] if isinstance(r, dict) and not isinstance(data.get("stuk"), dict)]
    return [(str(r.get("id")), str(r.get("label") or "")) for r in rijen if r.get("id")]


def _gevonden_zonder_sjabloon(b: Bouw, state: State) -> dict[str, list[tuple[str, str]]]:
    """Per tool van een bronconnector die deze beurt iets vond of las, de stukken (id, label), als de agent het sjabloon
    nog niet gevraagd is en er nog een ronde over is; anders leeg. Zonder sjabloon kwam een lijst gevonden stukken als
    tekst, zonder links, zoekvraag of totaal, soms als markdown-tabel (iteratie 11 nov 2026: bekendmakingen B03, B05,
    B18, B20; rechtspraak R06, R17, R18, R22, R23). Hoogstens één keer per beurt (`sjabloon_gevraagd`), en niet na een
    correctieronde. Of het verzoek ook komt, beslist de lijst in de tekst (`heeft_lijst`)."""
    if state.get("sjabloon_gevraagd") or state.get("corrected") or state.get("turns", 0) + 1 >= b.settings.max_turns:
        return {}
    # Ook een gelezen stuk: in tekst noemde het model nummers die het zelf afleidde, zonder citaat (iteratie ronde 2,
    # B22: "25.2.10 (nieuw)" voor "na artikel 25.2.9 een nieuw artikel"). Een fout (alleen PDF, buiten bereik, niet
    # gevonden) telt niet: daar is niets aan te wijzen.
    connectortools = {t for c in CONNECTORS.values() for t in c.tools}
    gevonden: dict[str, list[tuple[str, str]]] = {}
    for naam, resultaat in state.get("source_trace", []):
        if naam in connectortools and not is_fout(resultaat):
            try:
                data = json.loads(resultaat)
            except (TypeError, ValueError):
                continue
            if isinstance(data, dict) and data.get("resultaten"):
                gevonden.setdefault(naam, []).extend(_stukken_in(data))
    return gevonden


def route_after_agent(b: Bouw, state: State) -> str:
    if state.get("sjabloon_nu"):
        return "agent"  # één keer terug: om het sjabloon gevraagd (`_gevonden_zonder_sjabloon`)
    pending = state.get("pending_tools") or []
    if pending and pending[0]["name"] in SJABLONEN:
        return "sjabloon"
    if pending and pending[0]["name"] in OVERDRACHT:
        return "overdracht"
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


#: Wat het model ziet als het een tool aanroept die niet bij het profiel van de centrale agent hoort.
BUITEN_PROFIEL = json.dumps({"status": "unavailable", "volledig": False, "reden": "tool_buiten_profiel",
                             "aanwijzing": "Deze tool heb je nu niet. Roep eerst meer_tools aan."}, ensure_ascii=False)


def tools_node(b: Bouw, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    # Een sjabloon naast graaftools (`agent_node` zet hem achteraan): eerst de graaftools, dan het sjabloon met wat ze
    # opleverden, en alle resultaten in één bericht.
    alle = state.get("pending_tools", [])
    sjabloon = next((t for t in alle if t["name"] in SJABLONEN), None)
    pending = [t for t in alle if t is not sjabloon]
    # Binnen één beurt verandert de graaf niet: dezelfde aanroep nog eens kost alleen tokens (de e2e-test van 5 nov
    # 2026: drie gelijke zoekopdrachten, 63.867 tokens voor één vraag). Elke aanroep krijgt een resultaat, want het
    # model eist er een; alleen de eerste voert hem uit.
    gedaan = _al_gedaan(state)
    uit_te_voeren = list({_sleutel(t): t for t in reversed(pending) if _sleutel(t) not in gedaan}.values())[::-1]
    _stap(writer, "Lex", "; ".join(_toolregel(t) for t in uit_te_voeren) or "gebruikt wat er al is opgehaald")
    trace = list(state.get("source_trace", []))
    results = []
    agent = agent_van(state)
    for tu in pending:
        sleutel = _sleutel(tu)
        if sleutel in gedaan:
            results.append(_tool_result(tu, gedaan[sleutel].removesuffix(HERHAALD) + HERHAALD))
            continue
        if not agent.mag(tu["name"]):
            # De centrale agent riep een tool aan die niet bij zijn profiel hoort (ADR-016 §A1): niet uitvoeren, wel
            # zeggen hoe het wel kan. Het resultaat is geen bron en komt niet in het spoor.
            logger.info("tool buiten profiel", extra={"categorie": "functioneel", "run_id": state.get("run_id", ""),
                                                      "profiel": agent.naam, "tool": tu["name"]})
            results.append(_tool_result(tu, BUITEN_PROFIEL))
            continue
        result_text = execute_tool(b, state, writer, tu, van_model=True)
        gedaan[sleutel] = result_text
        trace.append((tu["name"], result_text))
        results.append(_tool_result(tu, result_text))
    upd: dict[str, Any] = {"source_trace": trace, "pending_tools": []}
    na: list[dict[str, Any]] = []
    if sjabloon is not None:
        blok, na, extra = vul_aanroep(b, {**state, "source_trace": trace}, sjabloon)
        results.append(blok)
        upd.update(extra)
    return {"messages": [{"role": "user", "content": results}, *na], **upd}  # messages: delta


def route_na_tools(b: Bouw, state: State) -> str:
    """Terug naar de agent, tenzij een sjabloon naast de graaftools het antwoord al vulde (`tools_node`)."""
    return "verify" if state.get("antwoord") else "agent"

def verify_node(b: Bouw, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    # Getoetst tegen deze beurt én wat eerder in het gesprek letterlijk is opgehaald: een vervolgantwoord
    # dat een citaat uit het vorige antwoord herhaalt, is niet minder brongetrouw dan dat antwoord.
    # Bij een sjabloon niet de blokken die afgeleide duiding of tekst van de code dragen (`NIET_GETOETST`).
    tekst = antwoord_tekst(Antwoord.model_validate(state["antwoord"]), zonder=NIET_GETOETST) if state.get("antwoord") else state.get("answer", "")
    # De namen van de regelingen in de graaf (per proces bewaard): daarmee is een regeling die nergens vandaan komt een
    # bewering. Alleen opgevraagd als het antwoord iets noemt met de vorm van een regeling; zonder namen geldt de toets niet.
    namen = (_graafnamen(b.graph) or None) if regelingen_genoemd(tekst) else None
    report = check_grounding(tekst, controletrace(state), overzicht=state.get("overzicht") or None, bekend=_bekend(state),
                             regelingen=namen)
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
    r"|(?:de|deze|die|een|mijn)\s+(?:zoek|lees)?tools?\b"
    # Een grens van de code als reden (ronde 5, I12: "kon vanwege de limiet van 25 stukken per bron niet volledig worden
    # opgenomen in de stukkenlijst"): de jurist ziet de lijst, niet de grens van het blok.
    r"|(?:de\s+)?limiet\s+van\s+\d+|stukkenlijst\w*)\b",
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
    if open_ := open_vraag(state.get("subagenten") or []):
        # Een subagent wacht op een antwoord dat de centrale agent niet had (ADR-016 §A4): de beurt eindigt met zijn
        # eerste vraag als kaart, uit code. Een klik gaat zonder model naar `subagent_vervolg`.
        writer({"type": "vraagkaart", "vraagkaart": vraagkaart(open_["delegatie_id"], open_["vragen"], 1)})

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
            # De namen eerst: een regeling die het antwoord bij naam noemt, is aangehaald (K13, ronde 4). De namen staan
            # in een cache per proces, dus de aanroep hieronder vraagt niets opnieuw.
            sources = curate_sources(met_regelingnamen(b.graph, sources), state.get("answer", ""))
    if not state.get("overzicht"):
        # Een bron naast de wet alleen als ze gelezen en genoemd is; een zoekresultaat is geen bron (ADR-013).
        geciteerd = frozenset(b["id"] for b in (state.get("antwoord") or {}).get("blokken") or []
                              if b.get("soort") == "extern" and b.get("id"))
        sources = alleen_gelezen_extern(sources, controletrace(state), state.get("answer", ""),
                                        state.get("question", ""), geciteerd)
    # De namen van de regelingen in de lijst (één query per beurt; na het cureren al uit de cache).
    sources = met_regelingnamen(b.graph, sources)
    if not state.get("overzicht"):
        # In de overzichtsroute zijn de vindplaatsen van het overzicht het antwoord zelf.
        sources = alleen_genoemde_regelingen(sources, state.get("answer", ""))
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
                                                [s["uri"] for s in src_dicts],
                                                genoemd_in_antwoord(state.get("antwoord"), state.get("answer", ""), src_dicts))}
    return upd
