"""De decompositie-keten: een samengestelde vraag in deelvragen uiteenleggen.

Alleen actief met `ENABLE_DECOMPOSITION=1`. De keten is decompose → solve → (synthesize) → verify;
bij één deelvraag levert `solve` het eindantwoord zelf en wordt de synthese overgeslagen, zodat een
eenvoudige vraag geen synthese-tax betaalt.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from langgraph.config import get_stream_writer

from ..agent_common import truncate
from ..berichten import _parse_final, _schoon_messages, _trim_messages
from ..narratie import _stap, _toolregel
from ..prompts import SYSTEM_PROMPT
from ..specialists import get as get_specialist
from ..state import State
from ..tools import anthropic_schemas, dispatch
from .context import Bouw

logger = logging.getLogger("graph_qa.orchestrator")

_DECOMPOSE_SYSTEM = (
    "Je splitst een juridische vraag over de kennisgraaf op in de deelvragen die je apart moet "
    "beantwoorden om de hele vraag te dekken. Geef ELKE deelvraag op een eigen regel, genummerd "
    "(1., 2., …), in logische volgorde (een deelvraag mag voortbouwen op een eerdere). Splits ALLEEN "
    "als de vraag echt meerdere losse onderdelen heeft; een enkelvoudige vraag geef je als één regel "
    "terug (de vraag zelf). Verzin geen deelvragen die niet in de oorspronkelijke vraag besloten "
    "liggen. Geen inleiding of uitleg – alleen de genummerde regels."
)

_SYNTHESE_SYSTEM = (
    "Je stelt één samenhangend eindantwoord samen uit de per-deelvraag verzamelde bevindingen. "
    "Steun UITSLUITEND op die bevindingen – voeg geen nieuwe feiten toe en verzin geen vindplaatsen. "
    "Behoud de vindplaatsen (regeling/artikel/lid) letterlijk zoals ze in de bevindingen staan. "
    "Antwoord bondig en goed gestructureerd; adresseer elk onderdeel van de oorspronkelijke vraag."
)


def decompose_node(b: Bouw, state: State) -> dict[str, Any]:
    """Splits de vraag in geordende deelvragen (één LLM-call). Enkelvoudig → één deelvraag."""
    writer = get_stream_writer()
    resp = b.llm.create(
        model=b.model,
        max_tokens=400,
        system=_DECOMPOSE_SYSTEM + b.memory_context(state),
        tools=[],
        messages=[{"role": "user", "content": state["question"]}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    subs: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^\s*\d+[.)]\s*(.+)$", line)
        if m:
            subs.append(m.group(1).strip())
    if not subs:
        subs = [state["question"]]
    subs = subs[: b.settings.max_subquestions]
    if len(subs) > 1:
        _stap(writer, "Decompositie", f"{len(subs)} deelvragen")
    return {"sub_questions": subs}

def solve_node(b: Bouw, state: State) -> dict[str, Any]:
    """Beantwoord elke deelvraag met een eigen agent⇄tools-loop (lokale scratch-messages).

    De per-beurt narratie stroomt als `reason` (het denkproces), nooit als `token`. Bij ÉÉN
    deelvraag (een simpele vraag) is er geen aparte synthese nodig: de tool-loze eindbeurt ís het
    eindantwoord en wordt als één `token` geëmit (en `answer` gezet), zodat een eenvoudige vraag
    geen synthese-tax betaalt. Bij MEERDERE deelvragen emit solve géén token – `synthesize_node`
    streamt dan het eindantwoord. De gedeelde source_trace accumuleert over álle deelvragen zodat
    grounding/provenance ongewijzigd werken.
    """
    writer = get_stream_writer()
    spec = get_specialist(state.get("specialist"))
    subs = state.get("sub_questions") or [state["question"]]
    enkelvoudig = len(subs) == 1  # simpele vraag: eindantwoord hier, synthese overslaan
    base_system = SYSTEM_PROMPT + (f"\n\n{spec.system}" if spec.system else "")
    schemas = anthropic_schemas(only=spec.tools)
    trace = list(state.get("source_trace", []))
    findings: list[dict[str, str]] = []
    for i, sub in enumerate(subs, 1):
        if len(subs) > 1:
            _stap(writer, f"Deelvraag {i}/{len(subs)}", sub[:80])
        # Zelfde splitsing als in `agent_node`: base_system is stabiel over alle deelvragen
        # heen, de bevindingen en de geheugen-context groeien per deelvraag.
        variabel = ""
        if findings:
            ctx = "\n".join(f"- {f['vraag']} → {f['antwoord'][:300]}" for f in findings)
            variabel += (
                "EERDERE DEELBEVINDINGEN (context; verifieer elk feit opnieuw via de tools):\n" + ctx
            )
        variabel += b.memory_context(state)
        msgs: list[dict[str, Any]] = [{"role": "user", "content": sub}]
        antwoord = ""
        for _turn in range(b.settings.sub_max_turns):
            # Op de laatste toegestane beurt bieden we géén tools meer aan. Zonder dat kon het
            # model blijven zoeken tot de lus afliep, waarna `antwoord` leeg bleef en de
            # gebruiker alleen bronnen zag: de vraag werd midden in de zoektocht afgekapt. Nu is
            # de laatste beurt gedwongen een antwoord op wat er is opgehaald.
            laatste_beurt = _turn == b.settings.sub_max_turns - 1
            if laatste_beurt:
                _stap(writer, "Deelvraag", "beurtlimiet bereikt – verder met wat is gevonden")
            with b.llm.stream(
                model=b.model, max_tokens=4096, system=[base_system, variabel],
                tools=[] if laatste_beurt else schemas,
                messages=_trim_messages(_schoon_messages(msgs), b.settings.max_history_chars),
            ) as stream:
                first = True
                for delta in stream.text_deltas:
                    if first and _turn > 0:
                        writer({"type": "reason", "content": "\n\n"})  # alinea-scheiding tussen beurten
                    writer({"type": "reason", "content": delta})
                    first = False
                final = stream.final_message()
            tool_uses, text_parts = _parse_final(final)
            assistant_content: list[dict[str, Any]] = [{"type": "text", "text": p} for p in text_parts if p and p.strip()]
            assistant_content += [
                {"type": "tool_use", "id": t["id"], "name": t["name"], "input": t["input"]}
                for t in tool_uses
            ]
            msgs.append({"role": "assistant", "content": assistant_content})
            if not tool_uses:
                antwoord = "\n\n".join(p for p in text_parts if p)
                break
            _stap(writer, "Graaf bevragen", ", ".join(_toolregel(t) for t in tool_uses))
            results = []
            for tu in tool_uses:
                result_text = truncate(dispatch(tu["name"], b.graph, tu["input"], b.settings))
                trace.append((tu["name"], result_text))
                results.append({"type": "tool_result", "tool_use_id": tu["id"], "content": result_text})
            msgs.append({"role": "user", "content": results})
        if not antwoord.strip():
            # Zou na het tools-loze vangnet hierboven niet meer moeten voorkomen; als het tóch
            # gebeurt is dat een lege modelrespons en willen we het terugvinden.
            logger.warning(
                "deelvraag zonder antwoord",
                extra={"deelvraag": sub[:120], "beurten": b.settings.sub_max_turns,
                       "specialist": state.get("specialist"), "bronnen": len(trace)},
            )
        findings.append({"vraag": sub, "antwoord": antwoord})
    upd: dict[str, Any] = {"sub_findings": findings, "source_trace": trace}
    if enkelvoudig:
        # Simpele vraag: de tool-loze eindbeurt ís het eind-antwoord (geen synthese) → als token.
        antwoord = findings[0]["antwoord"] if findings else ""
        upd["answer"] = antwoord
        if antwoord:
            writer({"type": "token", "content": antwoord})
    return upd

def route_after_solve(b: Bouw, state: State) -> str:
    # Eén deelvraag → antwoord staat al (gestreamd in solve); sla de synthese over.
    return "verify" if len(state.get("sub_questions") or []) <= 1 else "synthesize"

def synthesize_node(b: Bouw, state: State) -> dict[str, Any]:
    """Stel het eind-antwoord samen uit de deelbevindingen (streamt de tokens)."""
    writer = get_stream_writer()
    findings = state.get("sub_findings") or []
    _stap(writer, "Synthese", f"antwoord uit {len(findings)} deelbevindingen")
    bevindingen = "\n\n".join(
        f"DEELVRAAG: {f['vraag']}\nBEVINDING: {f['antwoord']}" for f in findings
    )
    system = _SYNTHESE_SYSTEM
    if state.get("corrected") and state.get("unsupported"):
        system += (
            "\n\nVerwijder of onderbouw deze eerder niet-gegronde verwijzingen: "
            + ", ".join(state["unsupported"]) + "."
        )
    user = f"OORSPRONKELIJKE VRAAG:\n{state['question']}\n\nBEVINDINGEN PER DEELVRAAG:\n{bevindingen}"
    parts: list[str] = []
    with b.llm.stream(
        model=b.model, max_tokens=4096, system=system, tools=[],
        messages=[{"role": "user", "content": user}],
    ) as stream:
        for delta in stream.text_deltas:
            parts.append(delta)
            writer({"type": "token", "content": delta})
        stream.final_message()
    return {"answer": "".join(parts).strip()}

def resynth_node(b: Bouw, state: State) -> dict[str, Any]:
    """Ongegronde synthese → markeer voor één her-synthese (synthesize_node leest corrected)."""
    return {"corrected": True, "answer": ""}
