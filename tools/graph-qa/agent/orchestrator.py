"""
LangGraph-orkestrator: plan → retrieve → reason → verify → finalize.

LangGraph levert het toestandsgraaf-substraat (nodes, conditionele edges, streaming,
checkpointing); de domeinlogica blijft die van Fase 1/2 – de nodes roepen de bestaande
LLMPort/GraphPort, de typed tool-registry, provenance en grounding aan. Geen
langchain-chatmodel: Azure Foundry blijft via AnthropicLLM.

Geheugen zit in de state en wordt door de checkpointer (thread_id = conversation_id)
gepersisteerd: `messages` (episodisch, append-reducer) en `entities_seen` (de "in
beeld"-set geraadpleegde bepalingen, semantische/entiteit-tier). De wrapper compileert
`build_graph()` met de gekozen checkpointer.

Streaming loopt via LangGraph's custom-stream (get_stream_writer); answer_stream
consumeert het en houdt het SSE-contract gelijk. Nodes zijn synchroon (threadpool),
zodat de blocking LLM-/MCP-calls de event-loop niet blokkeren.
"""
from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from .agent_common import BeurtGestopt, truncate
from .doel import (  # noqa: F401 – re-export: tests importeren _kandidaten_uit_json hiervandaan
    _bepaal_doel,
    _corpus_uit_trace,
    _corpus_voor_doel,
    _doel_uit_json,
    _doel_uit_toolcalls,
    _heeft_opgegeven_doel,
    _kandidaten_uit_json,
    _ontbrekend_sleutel,
)
from .nodes.antwoord import (
    agent_node,
    correct_node,
    finalize_node,
    route_after_agent,
    route_after_verify,
    tools_node,
    verify_node,
)
from .nodes.annotatie import (
    annoteer_kandidaten_node,
    annoteer_klasseer_node,
    annoteer_node,
    critic_node,
    emit_node,
    herzie_node,
    patch_node,
    route_na_critic,
    route_na_patch,
)
from .nodes.context import Bouw
from .nodes.supervisie import (
    _entry_node,
    advance_node,
    afwijs_node,
    route_after_advance,
    supervisor_node,
)
from .nodes.decompositie import (
    decompose_node,
    resynth_node,
    route_after_solve,
    solve_node,
    synthesize_node,
)
from .berichten import (  # noqa: F401 – re-export: tests en node-modules importeren ze hiervandaan
    MAX_HISTORIE_CHARS,
    _msg_lengte,
    _parse_final,
    _schoon_messages,
    _snoei_historie,
    _trim_messages,
    _voeg_toe_en_snoei,
)
from .narratie import (  # noqa: F401 – re-export, zie hierboven
    _annoteer_melding,
    _critic_melding,
    _grounding_melding,
    _herzien_melding,
    _stap,
    _toolregel,
)
from .state import State
from .config import Settings
from .ports import GraphPort, LLMPort

logger = logging.getLogger("graph_qa.orchestrator")



def build_graph(
    settings: Settings,
    llm: LLMPort,
    graph: GraphPort,
    stop_check: Callable[[], bool] | None = None,
) -> StateGraph:
    """Bouw de (ongecompileerde) toestandsgraaf; de wrapper compileert 'm met een checkpointer."""
    # `model` is het sterke model: annoteerder, Critic, herziener en de QA-specialisten. De router
    # en de ophaal-agent mogen apart worden gezet (`Settings.model_voor`); staat er niets, dan is
    # het alle drie hetzelfde en draait de keten exact als voorheen.
    model = settings.llm_model
    model_router = settings.model_voor("router")
    model_ophaal = settings.model_voor("ophaal")

    def _memory_context(state: State) -> str:
        if not settings.enable_memory_context:
            return ""
        seen = list(dict.fromkeys(state.get("entities_seen") or []))  # dedup, volgorde behouden
        if not seen:
            return ""
        lijst = "\n".join(f"- {u}" for u in seen[-12:])
        return (
            "\n\nGESPREKSCONTEXT – eerder in dit gesprek geraadpleegde bepalingen (alléén als "
            "aanknopingspunt voor verwijzingen als 'dat artikel'; verifieer elk feit opnieuw via "
            f"de tools):\n{lijst}"
        )

    def _corpus(state: State) -> str:
        """De tekst van deze annotatiebeurt. `annoteer_node` haalde hem gericht op en zette hem in de
        state; de terugval is er voor een state van vóór dit veld (een hervatte thread)."""
        return state.get("corpus") or _corpus_uit_trace(state.get("source_trace", []))

    def _advies_context(state: State) -> str:
        """Contextblok voor een adviesvraag: waar gaat het over, en wat mag de agent niet doen.

        De 'wijzig niets'-instructie is hier een toelichting, geen slot – dat slot is topologisch
        (deze route emit geen element-events). Het staat er zodat het antwoord de juiste vorm heeft:
        een onderbouwing, geen voorstel voor een nieuwe annotatie.
        """
        if state.get("modus") != "advies":
            return ""
        c = state.get("context") or {}
        regels = ["", "--- WAAR DE VRAAG OVER GAAT ---"]
        plek = " ".join(x for x in (c.get("bwbId", ""), f"art. {c['artikel']}" if c.get("artikel") else "",
                                    f"lid {c['lid']}" if c.get("lid") else "") if x)
        if plek:
            regels.append(f"Bepaling: {plek}")
        if c.get("klasse"):
            regels.append(f"Voorgestelde JAS-klasse: {c['klasse']}")
        if c.get("fragment"):
            regels.append(f'Fragment: "{c["fragment"]}"')
        if c.get("corpus"):
            regels.append(f"\nArtikeltekst:\n{truncate(str(c['corpus']), 6000)}")
        regels += [
            "--- EINDE ---",
            "",
            "Dit is een ADVIESVRAAG bij een bestaande JAS-annotatie. Geef uitsluitend onderbouwing en "
            "duiding; stel geen nieuwe annotatie voor en zeg niet dat je iets hebt gewijzigd.",
        ]
        # Zonder deze afbakening motiveert het model álle markeringen die het in de gesprekshistorie
        # ziet staan – de annotatiebeurt zit immers in dezelfde thread. Wie één element aanklikt en
        # "motiveer" vraagt, verwacht één motivering. De laatste zin is de tegenkracht tegen dat
        # geheugen: zonder die toevoeging pakt het model er alsnog zijn eerdere voorstellen bij.
        if c.get("fragment"):
            buren = [b for b in (c.get("bestaande_elementen") or []) if isinstance(b, dict)]
            regels += [
                "",
                # Niet "ONDERWERP": dat woord gebruikt de basis-systeemprompt al voor de
                # onderwerp-afbakening van de agent (wel/geen wetgevingsvraag).
                f'AFBAKENING VAN DEZE VRAAG – het gaat over dit ene fragment: "{c["fragment"]}". '
                "Motiveer alleen dat element.",
                "Een andere markering uit dezelfde bepaling mag je erbij halen wanneer die NODIG is om "
                "dit element te onderbouwen – samenhang, afbakening, of het rechtsgevolg waar een "
                "voorwaarde bij hoort. Houd dat kort en breng het terug naar het onderwerp.",
                "Geef die andere markeringen GEEN eigen motivering, ook niet als je ze eerder in dit "
                "gesprek hebt voorgesteld.",
            ]
            if buren:
                # Meesturen in plaats van op het geheugen vertrouwen: anders hangt het antwoord af van
                # wat er toevallig nog in de historie stond, en verschilt het per gesprek.
                regels += [
                    "",
                    "--- ANDERE MARKERINGEN IN DEZE BEPALING (niet motiveren; alleen ter ondersteuning) ---",
                ]
                for b in buren[:20]:
                    klasse = str(b.get("klasse", "")).strip()
                    tekst = truncate(str(b.get("tekst", "")).strip(), 200)
                    if klasse and tekst:
                        regels.append(f'{klasse} – "{tekst}"')
                regels.append("--- EINDE ---")
        return "\n".join(regels)


    # Alles wat een verhuisde node uit deze scope nodig had, expliciet in één object. Nodes die nog
    # closure zijn gebruiken de vrije variabelen rechtstreeks; dat verschil verdwijnt naarmate de
    # rest volgt.
    b = Bouw(
        settings=settings, llm=llm, graph=graph, stop_check=stop_check,
        model=model, model_router=model_router, model_ophaal=model_ophaal,
        memory_context=_memory_context, corpus=_corpus, advies_context=_advies_context,
    )


    g = StateGraph(State)

    def stopbaar(fn):
        """Elke node begint met de vraag of er nog gewerkt moet worden.

        Zo stopt een beurt op een **nodegrens** in plaats van halverwege een LLM-call: de state die
        al gecommit is blijft consistent, en de MCP-verbinding wordt netjes afgesloten. De prijs is
        dat stoppen tijd kost – de lopende stap maakt zichzelf af."""
        @functools.wraps(fn)
        def bewaakt(state: State) -> dict[str, Any]:
            if stop_check is not None and stop_check():
                raise BeurtGestopt()
            return fn(state)
        return bewaakt

    def add(naam: str, fn) -> None:
        """Registreer een node, altijd met de stopbewaking eromheen."""
        g.add_node(naam, stopbaar(fn))

    def annotatieketen() -> str:
        """Registreer de annotatie-worker en zijn edges; geeft de naam van de ingang terug.

        Lineair: annoteer → critic₁ → patch → [herzie → critic₂] → emit, met `emit` als enige
        uitgang zodat de werkplek nooit tussenversies ziet. Geen enkele edge wijst terug naar een
        eerdere stap, dus er is geen cyclus om te laten convergeren.

        Dit blok stond identiek in de decompositie- en de planning-tak. De antwoordketen verschilt
        wél echt tussen die twee (`verify → resynth` versus `verify → correct`), dus die blijft per
        tak apart staan; alleen wat aantoonbaar hetzelfde was is hier samengebracht.
        """
        if settings.enable_kandidaat_splitsing:
            add("annoteer_kandidaten", functools.partial(annoteer_kandidaten_node, b))
            add("annoteer_klasseer", functools.partial(annoteer_klasseer_node, b))
            entry = "annoteer_kandidaten"
        else:
            add("annoteer", functools.partial(annoteer_node, b))
            entry = "annoteer"
        add("critic", functools.partial(critic_node, b))
        add("patch", functools.partial(patch_node, b))
        add("herzie", functools.partial(herzie_node, b))
        add("emit", functools.partial(emit_node, b))

        if settings.enable_kandidaat_splitsing:
            g.add_edge("annoteer_kandidaten", "annoteer_klasseer")
            g.add_edge("annoteer_klasseer", "critic")
        else:
            g.add_edge("annoteer", "critic")
        g.add_conditional_edges("critic", functools.partial(route_na_critic, b), {"patch": "patch", "emit": "emit"})
        g.add_conditional_edges("patch", functools.partial(route_na_patch, b),
                                {"herzie": "herzie", "critic": "critic", "emit": "emit"})
        g.add_edge("herzie", "critic")
        g.add_edge("emit", "advance")
        return entry

    add("verify", functools.partial(verify_node, b))
    add("finalize", functools.partial(finalize_node, b))

    if settings.enable_decomposition:
        # Supervisor → (annotatie: agent⇄tools→annoteer_finalize | antwoord: decompose→solve→…→
        # finalize) → advance → (volgende worker | einde).
        add("supervisor", functools.partial(supervisor_node, b))
        add("decompose", functools.partial(decompose_node, b))
        add("solve", functools.partial(solve_node, b))
        add("synthesize", functools.partial(synthesize_node, b))
        add("resynth", functools.partial(resynth_node, b))
        add("agent", functools.partial(agent_node, b))
        add("tools", functools.partial(tools_node, b))
        add("advance", functools.partial(advance_node, b))
        add("afwijzen", functools.partial(afwijs_node, b))
        # Alle conditional-edges die "annoteer" als doel teruggeven moeten naar de ingang van de
        # keten; bij splitsing is dat `annoteer_kandidaten`.
        _annoteer_entry = annotatieketen()
        entrymap = {"agent": "agent", "annoteer": _annoteer_entry, "decompose": "decompose",
                    "afwijzen": "afwijzen"}
        g.add_edge(START, "supervisor")
        g.add_edge("afwijzen", END)
        g.add_conditional_edges("supervisor", functools.partial(_entry_node, b), entrymap)
        g.add_edge("decompose", "solve")
        g.add_conditional_edges("solve", functools.partial(route_after_solve, b), {"verify": "verify", "synthesize": "synthesize"})
        g.add_edge("synthesize", "verify")
        g.add_conditional_edges("verify", functools.partial(route_after_verify, b), {"correct": "resynth", "finalize": "finalize"})
        g.add_edge("resynth", "synthesize")
        g.add_conditional_edges(
            "agent", functools.partial(route_after_agent, b),
            {"tools": "tools", "verify": "verify", "annoteer": _annoteer_entry},
        )
        g.add_edge("tools", "agent")
        g.add_edge("finalize", "advance")
        g.add_conditional_edges("advance", functools.partial(route_after_advance, b), {**entrymap, "einde": END})
        return g

    # Één-loop-stroom.
    add("agent", functools.partial(agent_node, b))
    add("tools", functools.partial(tools_node, b))
    add("correct", functools.partial(correct_node, b))

    if settings.enable_planning:
        # Supervisor → agent⇄tools → (verify→finalize | annoteer_finalize) → advance → (volgende | einde).
        add("supervisor", functools.partial(supervisor_node, b))
        add("advance", functools.partial(advance_node, b))
        add("afwijzen", functools.partial(afwijs_node, b))
        _annoteer_entry = annotatieketen()
        g.add_edge(START, "supervisor")
        g.add_conditional_edges("supervisor", functools.partial(_entry_node, b),
                                {"agent": "agent", "annoteer": _annoteer_entry, "afwijzen": "afwijzen"})
        g.add_edge("afwijzen", END)
        g.add_conditional_edges(
            "agent", functools.partial(route_after_agent, b),
            {"tools": "tools", "verify": "verify", "annoteer": _annoteer_entry},
        )
        g.add_edge("tools", "agent")
        g.add_conditional_edges("verify", functools.partial(route_after_verify, b), {"correct": "correct", "finalize": "finalize"})
        g.add_edge("correct", "agent")
        g.add_edge("finalize", "advance")
        g.add_conditional_edges("advance", functools.partial(route_after_advance, b),
                                {"agent": "agent", "annoteer": _annoteer_entry,
                                 "afwijzen": "afwijzen", "einde": END})
        return g

    # Geen classificatie (planning off, decomp off): pure QA-agent, ongewijzigd (geen annotatie-route).
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", functools.partial(route_after_agent, b), {"tools": "tools", "verify": "verify"})
    g.add_edge("tools", "agent")
    g.add_conditional_edges("verify", functools.partial(route_after_verify, b), {"correct": "correct", "finalize": "finalize"})
    g.add_edge("correct", "agent")
    g.add_edge("finalize", END)
    return g
