"""De gedeelde toestand van de agentgraaf.

Staat apart zodat de node-modules hem kunnen importeren zonder de orchestrator (en daarmee een
circulaire import) binnen te halen.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

# De reducer van `messages` staat in een Annotated en wordt door LangGraph pas op bouwtijd
# geëvalueerd, in de globals van déze module — hij moet hier dus echt geïmporteerd zijn.
from .berichten import _voeg_toe_en_snoei

class State(TypedDict, total=False):
    question: str
    # Episodisch geheugen, gepersisteerd door de checkpointer. De reducer voegt toe én snoeit: zonder
    # dat groeide de bewaarde historie onbeperkt door (inclusief elk tool-resultaat van 8000 tekens),
    # en werd elke checkpoint-write in een lang gesprek trager en dikker. Snoeien gebeurt alleen op
    # een platte user-beurt – een losgeknipt tool_result zou de volgende beurt laten crashen.
    messages: Annotated[list[dict[str, Any]], _voeg_toe_en_snoei]
    entities_seen: Annotated[list[str], operator.add]            # semantisch/entiteit-tier
    specialist: str
    plan: str
    worker_plan: list[str]   # geordende worker-keten (specialist-namen) die de supervisor koos
    afwijzen: bool           # supervisor plaatste de vraag buiten de scope → geen worker draait
    worker_idx: int          # index van de huidige worker in worker_plan
    source_trace: list[tuple[str, str]]
    answer: str
    grounded: bool
    cited: int
    unsupported: list[str]
    niet_letterlijk: list[str]   # als citaat gepresenteerd, maar niet letterlijk in de trace
    grounding_niveau: str        # gegrond | onbepaald | ongegrond
    sources: list[dict[str, Any]]
    pending_tools: list[dict[str, Any]]
    turns: int
    corrected: bool
    # Decompositie (multi-hop): deelvragen + per-deelvraag bevindingen (last-value-wins;
    # solve_node zet ze in één keer). De per-deelvraag agent⇄tools-loop draait lokaal in solve_node.
    sub_questions: list[str]
    sub_findings: list[dict[str, str]]
    # Het doel dat de AANROEPER meegaf ({bwbId, artikel, lid?, citeertitel?}). Weet de werkplek de
    # bepaling al – een open document, een item uit de werkvoorraad, een gekozen kandidaat – dan
    # hoeft niemand hem meer te zoeken: de supervisor doet geen LLM-call en de ophaal-agent draait
    # helemaal niet. Dat scheelt niet alleen calls; het verwijdert de gevaarlijkste faalmodus uit
    # die route, want een ophaal-agent die de verkeerde bepaling kiest levert werk op dat
    # brongetrouw én verkeerd is.
    opgegeven_doel: dict[str, str]
    # De tekst waarop deze annotatiebeurt draait: gericht opgehaald door annoteer_node (zie
    # `_corpus_voor_doel`) en daarna hergebruikt door de Critic en de herziening, zodat alle drie
    # over exact dezelfde bepaling oordelen én er maar één ophaalactie nodig is.
    corpus: str
    # Annotatie: de gegronde voorstellen (als dicts) die annoteer_node maakt; critic_node scoort ze
    # met een aandacht-niveau en emit ze dán pas als `element`-events.
    #
    # Alle annotatie-velden zijn last-value-wins (géén operator.add-reducer): elke node levert de
    # volledige lijst. Met een append-reducer zou de Critic-feedback over rondes heen stapelen en
    # zou een herziening zijn eigen vorige oordeel als actueel aanzien.
    voorstellen: list[dict[str, Any]]
    verworpen_fragmenten: list[dict[str, Any]]   # niet-gegronde citaten, als feedback voor een herziening
    kandidaten_v2a: list[dict[str, Any]]         # fase 2A: gefilterde kandidaten vóór classificatie
    critic_feedback: list[dict[str, Any]]        # [{id, aandacht, motivatie, actie, voorstel_*}]
    critic_ontbrekend: list[dict[str, Any]]
    critic_gefaald: bool
    critic_ronde: int                            # welke Critic-pas: 1 = oordeel, 2 = eindbeoordeling
    # Convergentie. Zonder deze drie draait de lus altijd tot de rondelimiet: de Critic bedenkt elke
    # ronde opnieuw wat er "mist", dus er is altijd een reden om door te gaan.
    nieuw_ontbrekend: list[dict[str, Any]]       # gemist én nog niet eerder gemeld – alleen dit is werk
    gemeld_ontbrekend: list[str]                 # sleutels van alles wat al ooit gemeld is
    patch_toegepast: int                         # hoeveel Critic-aanwijzingen de patcher uitvoerde
    stop_reden: str                              # waaróm de lus eindigde; komt in de tijdlijn
    # Wat de werkplek meestuurt over de bepaling/markering die in beeld staat. `modus == "advies"`
    # betekent: een vraag bij een bestaande annotatie, die niets mag wijzigen.
    modus: str
    context: dict[str, Any]
