"""De antwoord-keten: agent ⇄ tools → verify → (correct) → finalize.

De weg die een gewone vraag aflegt. `verify` toetst de grounding deterministisch — geen tweede
LLM-oordeel — en `correct` krijgt hoogstens één corrigerende poging. `finalize` verzamelt de
bronnen uit de tool-trace, nooit uit de prozatekst van het model.
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.config import get_stream_writer

from ..agent_common import truncate
from ..berichten import _parse_final, _schoon_messages, _trim_messages
from ..grounding import check_grounding, curate_sources
from ..narratie import _grounding_melding, _stap, _toolregel
from ..prompts import SYSTEM_PROMPT
from ..provenance import collect_sources
from ..specialists import DEFAULT as DEFAULT_SPECIALIST
from ..specialists import get as get_specialist
from ..state import State
from ..tools import anthropic_schemas, dispatch
from .context import Bouw

logger = logging.getLogger("graph_qa.orchestrator")


def agent_node(b: Bouw, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    # Alleen bij de eerste beurt: daarna is elke ronde al herkenbaar aan de graafbevragingen, en
    # zou dit bij elke tool-lus opnieuw voorbijkomen.
    if not state.get("turns"):
        spec_naam = state.get("specialist") or DEFAULT_SPECIALIST
        _stap(writer, f"Specialist {spec_naam}", "raadpleegt de kennisgraaf")
    # De annotatie-route draait de agent⇄tools-lus als OPHAAL-agent (retrieval-specialist): hij
    # vindt de exacte bepaling. De JAS-annotatie gebeurt daarna in annoteer_node (pure LLM-call).
    spec_naam = "retrieval" if state.get("specialist") == "annotatie" else state.get("specialist")
    spec = get_specialist(spec_naam)
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

    # De annotatie-worker produceert JSON, geen leesbaar antwoord – díe narratie tonen we niet
    # (annoteer_node emit straks een korte samenvatting). De narratie van een gewone worker is de
    # "denkproces"-stroom (reason), niet het antwoord: die scheiden we van het eindantwoord (token).
    stream_naar_denk = state.get("specialist") != "annotatie"
    with b.llm.stream(
        # Deze node draait twee verschillende rollen: de OPHAAL-agent (annotatieroute – zoeken
        # en ophalen) en de QA-specialisten (die het antwoord zelf schrijven). Alleen de eerste
        # heeft een eigen modelknop.
        model=b.model_ophaal if spec_naam == "retrieval" else b.model,
        max_tokens=4096,
        system=[stabiel, variabel],
        tools=anthropic_schemas(only=spec.tools),
        # Historie begrenzen (tegen onbegrensde promptgroei in een lange sessie); state blijft heel.
        messages=_trim_messages(_schoon_messages(state["messages"]), b.settings.max_history_chars),
    ) as stream:
        # Beurt-narratie stroomt per beurt binnen als `reason` (het denkproces). Op een beurt-grens
        # ontbreekt anders een scheiding, zodat "…tegelijkertijd." + "De thesaurus…" aan elkaar
        # plakt. Emit één alinea-scheiding vóór de éérste tekst van een vervolgbeurt (turns>0).
        # Lazy, zodat een tool-only beurt (geen tekst) geen loshangende of dubbele witregel geeft.
        first_delta = True
        for delta in stream.text_deltas:
            if stream_naar_denk:
                if first_delta and state.get("turns", 0) > 0:
                    writer({"type": "reason", "content": "\n\n"})
                writer({"type": "reason", "content": delta})
            first_delta = False
        final = stream.final_message()

    tool_uses, text_parts = _parse_final(final)

    # max_turns-vangnet: op de laatste toegestane beurt geen openstaande tool_use persisteren.
    # Anders belandt er een assistant(tool_use) zónder tool_result in de checkpointer (orphan →
    # de volgende beurt in dezelfde conversatie crasht op Anthropic 400) én blijft het antwoord
    # leeg. Laat de tools dan vallen en lever een net eind-antwoord (desnoods een korte melding).
    if tool_uses and state.get("turns", 0) + 1 >= b.settings.max_turns:
        tool_uses = []
        if not any(p and p.strip() for p in text_parts):
            text_parts = [
                "Ik kon deze vraag niet binnen de beurtlimiet afronden; stel 'm eventueel gerichter."
            ]

    assistant_content: list[dict[str, Any]] = [{"type": "text", "text": p} for p in text_parts if p and p.strip()]
    assistant_content += [
        {"type": "tool_use", "id": t["id"], "name": t["name"], "input": t["input"]}
        for t in tool_uses
    ]

    upd: dict[str, Any] = {
        "messages": [{"role": "assistant", "content": assistant_content}],  # delta (append-reducer)
        "pending_tools": tool_uses,
        "turns": state.get("turns", 0) + 1,
    }
    if not tool_uses:
        # De tool-loze beurt is het eindantwoord: dát is de leesbare `token`-stroom (de annotatie-
        # route levert JSON, geen antwoord – daar geen token; annoteer_node vat samen).
        antwoord = "\n\n".join(p for p in text_parts if p)
        upd["answer"] = antwoord
        if stream_naar_denk and antwoord:
            writer({"type": "token", "content": antwoord})
    return upd

def route_after_agent(b: Bouw, state: State) -> str:
    if state.get("pending_tools") and state.get("turns", 0) < b.settings.max_turns:
        return "tools"
    if state.get("specialist") == "annotatie":
        return "annoteer"  # ophaal-agent klaar → de aparte annoteer-stap
    return "verify"


def tools_node(b: Bouw, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    pending = state.get("pending_tools", [])
    _stap(writer, "Graaf bevragen", ", ".join(_toolregel(t) for t in pending))
    trace = list(state.get("source_trace", []))
    results = []
    for tu in pending:
        result_text = truncate(dispatch(tu["name"], b.graph, tu["input"], b.settings))
        trace.append((tu["name"], result_text))
        results.append({"type": "tool_result", "tool_use_id": tu["id"], "content": result_text})
    return {
        "messages": [{"role": "user", "content": results}],  # delta
        "source_trace": trace,
        "pending_tools": [],
    }

def verify_node(b: Bouw, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    report = check_grounding(state.get("answer", ""), state.get("source_trace", []))
    # Deze controle heeft geen eigen narratie (geen LLM), dus zonder deze regel gebeurt er iets
    # wezenlijks – de brongetrouwheidstoets – zonder dat de jurist het ziet. De tijdlijn wordt
    # bij de beurt bewaard, dus dit is tegelijk het spoor waarop je achteraf terugvalt.
    _stap(writer, "Controle", _grounding_melding(report))
    return {
        "grounded": report.grounded,
        "cited": len(report.cited),
        "unsupported": report.unsupported,
        "niet_letterlijk": report.niet_letterlijk,
        "grounding_niveau": report.niveau,
    }

def route_after_verify(b: Bouw, state: State) -> str:
    if not state.get("grounded", True) and b.settings.grounding_correct and not state.get("corrected"):
        return "correct"
    return "finalize"

def correct_node(b: Bouw, state: State) -> dict[str, Any]:
    """Eén herkansing op wat de groundingcontrole afkeurde.

    De controle keurt twee dingen af en die vragen een ándere correctie. Deze node zag alleen
    `unsupported` (verzonnen vindplaatsen) en zweeg over `niet_letterlijk` (tekst die als citaat
    is gepresenteerd maar niet letterlijk in de bron staat). Bij een antwoord dat alléén op dat
    tweede struikelde – precies wat op dev gebeurde, zeven keer in één antwoord – ging er dus een
    volledige extra LLM-call de deur uit met de instructie "je noemde verwijzing(en) `` die niet
    uit de graaf kwamen": een lege opsomming en een verwijt dat niet klopte.
    """
    writer = get_stream_writer()
    unsupported = state.get("unsupported") or []
    niet_letterlijk = state.get("niet_letterlijk") or []

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
            f"tekst: {passages}. Herstel ze woord voor woord zoals ze in de bron staan, of haal "
            "de aanhalingstekens weg en geef het in je eigen woorden weer. Weglatingen met (...), "
            "eigen samenvattingen tussen [ ] en vet of cursief binnen een citaat maken het een "
            "parafrase – die presenteer je niet als citaat."
        )

    wat = " en ".join(
        deel for deel in (
            "niet-onderbouwde verwijzingen" if unsupported else "",
            "citaten die niet letterlijk zijn" if niet_letterlijk else "",
        ) if deel
    )
    _stap(writer, "Correctie", f"antwoord bijstellen op {wat}")
    return {
        "messages": [{"role": "user", "content": "Let op: " + " ".join(opdrachten)}],
        "corrected": True,
        "answer": "",
    }

def finalize_node(b: Bouw, state: State) -> dict[str, Any]:
    writer = get_stream_writer()

    # Vangnet tegen een stil leeg antwoord. Dat kan gebeuren als de agent een lege tekstbeurt
    # levert, of nadat correct_node het antwoord heeft gewist voor een grounding-correctie die
    # daarna niets oplevert. De gebruiker zag dan alleen de bronnen en de frontend-fallback
    # "(geen antwoord)" – zonder spoor in de logs. Liever een eerlijke melding, en altijd een
    # logregel zodat het volgende geval terug te vinden is.
    antwoord = state.get("answer", "") or ""
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
        writer({"type": "token", "content": antwoord})
        state = {**state, "answer": antwoord}

    sources = collect_sources(state.get("source_trace", []))
    if b.settings.curate_sources:
        sources = curate_sources(sources, state.get("answer", ""))
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
    })
    # entiteit-tier: alleen nieuwe IRI's toevoegen (append-reducer + dedup).
    existing = set(state.get("entities_seen") or [])
    new = [s["uri"] for s in src_dicts if s["uri"] not in existing]
    upd: dict[str, Any] = {"sources": src_dicts, "entities_seen": new}
    # In de decompositie-stroom stroomt het eind-antwoord uit synthesize_node en is het nog niet
    # in het durabele messages-kanaal beland (agent_node doet dat in de één-loop-stroom). Voeg het
    # hier één keer toe zodat het gespreksgeheugen het antwoord onthoudt.
    if b.settings.enable_decomposition:
        upd["messages"] = [
            {"role": "assistant", "content": [{"type": "text", "text": state.get("answer", "")}]}
        ]
    return upd
