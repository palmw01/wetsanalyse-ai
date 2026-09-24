"""De hybride annotatienode (ADR-001 PR 9): dezelfde voorbereiding als de legacy-annoteerder,
daarna `jas_pipeline.keten.analyseer` in plaats van één grote annotatieprompt.

Wat deze node níét doet: een volledige set laten genereren, een Critic de hele set laten
herbeoordelen, of bij een haperende parser terugvallen op de legacy-prompt. Een gedegradeerde
taalanalyse staat in de meting en in de statusregel; de gerichte reviewer (PR 12) en de resolver
(PR 13) komen tussen deze node en `emit`.
"""
from __future__ import annotations

from typing import Any

from langgraph.config import get_stream_writer

from ..annotatie import aanduiding_in_woorden
from ..bron_annotatie import bevroren_markeringen
from ..doel import _kandidaten_uit_json
from ..jas_pipeline.keten import analyseer
from ..narratie import _stap
from ..state import State
from .annotatie import _bereid_voor, _doel_event
from .context import Bouw


def _melding(meting: dict[str, Any], voorstellen: int) -> str:
    status = meting.get("per_status", {})
    delen = [f"{meting.get('kandidaten', 0)} kandidaten", f"{meting.get('deterministisch', 0)} zonder model",
             f"{meting.get('llm_calls', 0)} modelaanroep(en)", f"{voorstellen} voorgesteld"]
    if status.get("UNCERTAIN"):
        delen.append(f"{status['UNCERTAIN']} onzeker")
    if meting.get("gedegradeerd"):
        delen.append(f"zonder zinsontleding voor {len(meting['gedegradeerd'])} bronnode(s)")
    ongedekt = sum(len(b.get("ongedekt", [])) for b in (meting.get("dekking") or {}).values())
    if ongedekt:
        # Geen recall-claim: dit zijn zinsdelen waar geen enkele detector iets vond. De jurist
        # hoort te weten dat die niet beoordeeld zijn, niet dat ze leeg zijn.
        delen.append(f"{ongedekt} zinsdeel/-delen zonder kandidaat")
    return " · ".join(delen)


def hybride_annoteer_node(b: Bouw, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    if state.get("annotaties_lezen"):
        raise ValueError("Een leesroute mag geen annotatie produceren")
    kandidaten = _kandidaten_uit_json(state.get("answer", ""))
    if kandidaten:                       # een onderwerp in plaats van een bepaling: de jurist kiest
        writer({"type": "kandidaten", "kandidaten": kandidaten})
        melding = f"Ik vond {len(kandidaten)} bepalingen over dit onderwerp. Kies welke je wilt laten annoteren."
        writer({"type": "token", "content": melding})
        return {"answer": melding, "voorstellen": [], "messages": [{"role": "assistant", "content": melding}]}

    voorbereid = _bereid_voor(b, state, writer)
    if "klaar" in voorbereid:
        return voorbereid["klaar"]
    doel, bron, hergebruik = voorbereid["doel"], voorbereid["bron"], voorbereid["hergebruik"]
    soort, aanduiding, lid = voorbereid["soort"], voorbereid["aanduiding"], doel.get("lid", "")
    plek = aanduiding_in_woorden(aanduiding, lid, soort)
    _stap(writer, "Detectie", f"leest {plek} ({len(bron['corpus'])} tekens)")

    uitkomst = analyseer(
        snapshot=bron["bron_snapshot"], corpus_segmenten=bron["corpus_segmenten"], corpus=bron["corpus"],
        llm=b.llm, model=b.model, settings=b.settings, lid=lid,
        vindplaats=f"{doel.get('bwbId', '')} {plek}",
        hergebruikte_nodes=frozenset(bron.get("hergebruikte_nodes") or []),
    )
    _stap(writer, "Classificatie", _melding(uitkomst.meting, len(uitkomst.voorstellen)))
    writer({"type": "doel", "doel": _doel_event(doel, bron)})

    hybride = {"meting": uitkomst.meting,
               "beslissingen": [x.model_dump(mode="json") for x in uitkomst.beslissingen],
               "detectoren": [list(d) for d in uitkomst.fusie.detectoren],
               "overgeslagen": [o.model_dump() for o in uitkomst.fusie.overgeslagen]}
    eigen = bevroren_markeringen(bron)
    if not uitkomst.voorstellen and not eigen:
        leeg = f"Ik vond geen JAS-elementen om te markeren in {plek}."
        writer({"type": "token", "content": leeg})
        return {"answer": leeg, "voorstellen": [], "verworpen_fragmenten": [], **bron,
                "hergebruik": hergebruik or {}, "hybride": hybride,
                "messages": [{"role": "assistant", "content": leeg}]}
    return {"voorstellen": uitkomst.voorstellen + eigen, "verworpen_fragmenten": [], **bron,
            "hergebruik": hergebruik or {}, "hybride": hybride, "answer": ""}
