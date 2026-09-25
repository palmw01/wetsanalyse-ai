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
    run_id: str
    user_id: str
    annotaties_lezen: bool
    bron_snapshot: dict[str, Any]
    annotatie_weergave: dict[str, Any]
    corpus_segmenten: list[dict[str, Any]]
    hergebruikte_nodes: list[str]
    annotatie_fout: str
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
    # De tekst waarop deze annotatiebeurt draait: de niet-lege bronsegmenten van de snapshot,
    # samengevoegd (`bronmodel.CorpusMap`). Eén ophaalactie, en alles daarna leest deze tekst.
    corpus: str
    # "opnieuw" = de jurist vroeg expliciet om een nieuwe ronde op een al geannoteerde bepaling.
    hergebruik_modus: str
    # Wat er uit de gedeelde laag is hergebruikt (`bron_annotatie.controleer_hergebruik`): leden,
    # telling en of het volledig was. Leeg = niets hergebruikt.
    hergebruik: dict[str, Any]
    # De voorstellen (als dicts, `AnnotatieVoorstel`-vorm) die `annoteer` maakt en `emit` uitstuurt.
    voorstellen: list[dict[str, Any]]
    # Wat de analyse mat en besloot (ADR-001): meting, beslissingen, detectoren, overgeslagen
    # detectoren. Gaat als provenance mee in de `run`.
    analyse: dict[str, Any]
    # Wat de werkplek meestuurt over de bepaling/markering die in beeld staat. `modus == "advies"`
    # betekent: een vraag bij een bestaande annotatie, die niets mag wijzigen.
    modus: str
    context: dict[str, Any]
