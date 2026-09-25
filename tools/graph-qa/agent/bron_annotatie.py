"""Annoteren op canonieke bronsegmenten; lokale posities blijven los van de UI-opmaak."""
from __future__ import annotations

import json
from typing import Any

from bronmodel import BronFout, CorpusMap, resolve, valideer_ankers

from .tool_execution import execute_tool, read_port


def doel_params(doel):
    if doel.get("bron_iri"):
        return {"bron_iri": doel["bron_iri"]}
    return {"bwb_id": doel.get("bwbId") or doel.get("bwb_id") or "",
            "artikel": doel.get("artikel") or doel.get("nummer") or "", "lid": doel.get("lid") or ""}


def corpus_segmenten(segmenten):
    """Het analysecorpus plus per node zijn corpusoffsets; de rekenregel staat in `CorpusMap`."""
    kaart = CorpusMap(segmenten)
    return kaart.corpus, kaart.als_dicts()


def lees_bron(b, state, doel, writer):
    params = doel_params(doel)
    snapshot = json.loads(execute_tool(b, state, writer,
        {"name": "get_bronnode", "input": params}, operation=lambda: resolve(b.graph.sparql, **params)))
    corpus, spans = corpus_segmenten(snapshot["segmenten"])
    return {"corpus": corpus, "bron_snapshot": snapshot, "corpus_segmenten": spans}


AFGEROND = ("deze annotatie is afgerond. Heropen hem in het annotatiepaneel als ik hem opnieuw of "
            "verder moet annoteren")


def controleer_hergebruik(b, state, bron, writer):
    """De API is leidend, ook vlak na een graafherstart; niet stil dubbel annoteren."""
    snapshot = bron["bron_snapshot"]
    params = {"bron_iri": snapshot["doel"]["bron_iri"]}
    coverage = json.loads(execute_tool(b, state, writer,
                                      {"name": "get_annotatiedekking", "input": params}))
    if coverage.get("status") != "ok":
        raise BronFout("De annotatiedekking kon niet betrouwbaar worden gecontroleerd; probeer opnieuw")
    view = json.loads(execute_tool(
        b, state, writer, {"name": "get_annotatieweergave", "input": params},
        operation=lambda: read_port(b, state).weergave(params),
    ))
    if view.get("schema_versie") != 2 or view.get("snapshot_id") != snapshot["snapshot_id"]:
        raise BronFout("De bron veranderde tijdens het ophalen; probeer opnieuw")
    bron = {**bron, "annotatie_weergave": view}
    selected = {s["bron_iri"] for s in snapshot["segmenten"]}
    # Een afgeronde laag is bevroren: de api weigert er nieuwe voorstellen in (409). Dat hoort de
    # jurist vóór de analyse te horen, niet erna. Afgeronde nodes gaan daarom mee als "al
    # geannoteerd", zodat er geen nieuw element in belandt; blijft er dan niets over, dan stopt de
    # beurt meteen.
    afgerond = {laag["bron_iri"] for laag in view.get("lagen") or [] if laag.get("status") == "geaccordeerd"}
    alles_afgerond = bool(selected) and selected <= afgerond
    if state.get("hergebruik_modus") == "opnieuw" or coverage.get("snapshot_id") != snapshot["snapshot_id"]:
        if alles_afgerond:
            raise BronFout(AFGEROND)
        return {**bron, "hergebruikte_nodes": sorted(afgerond & selected)}, None
    completed = set(coverage.get("bereik") or [])
    full = bool(coverage.get("voltooid") and selected <= completed and coverage.get("parent_context"))
    elements = list(view.get("elementen") or [])
    # Hergebruiken mag wel: dat voegt niets toe aan de laag.
    if alles_afgerond and not full:
        raise BronFout(AFGEROND)
    if not completed:
        return {**bron, "hergebruikte_nodes": sorted(afgerond & selected)}, None
    reused = {"slug": params["bron_iri"], "status": "", "bijgewerkt": coverage.get("peilmoment", ""),
              "leden": [{"lid": n.get("nummer", ""), "iri": n["bron_iri"], "hash": n["bron_hash"]}
                        for n in snapshot["segmenten"] if n["bron_iri"] in completed],
              "bereik": sorted(completed & selected), "markeringen": elements,
              "telling": telling(elements), "volledig": full}
    # Nodes die al af zijn (of afgerond) worden niet opnieuw geanalyseerd; daar mag niets meer bij.
    return {**bron, "hergebruikte_nodes": sorted((completed | afgerond) & selected)}, reused


def lokale_elementen(voorstellen: list[dict[str, Any]], state) -> list[dict[str, Any]]:
    snapshot = state["bron_snapshot"]
    kaart = CorpusMap(state["corpus_segmenten"])
    reused = set(state.get("hergebruikte_nodes") or [])
    result = []
    for element in voorstellen:
        if element.get("van_jurist"):
            result.append(element)
            continue
        old = element.get("anker")
        if not old:
            raise BronFout("Een voorgesteld element mist een controleerbaar tekstanker")
        start, end = old["start"], old["eind"]
        anchors = list(element.get("ankers") or [])
        if anchors:
            owner = valideer_ankers(snapshot, anchors)
            if len({a["bron_iri"] for a in anchors}) == 1 and anchors[0]["bron_iri"] in reused:
                continue
            result.append({**{k: v for k, v in element.items() if k != "anker"}, "eigenaar_iri": owner})
            continue
        anchors.extend(span.anker() for span in kaart.naar_spans(start, end))
        owner = valideer_ankers(snapshot, anchors)
        # Een nieuwe parent-analyse mag een gedeeld lokaal element niet opnieuw aanmaken.
        if len({a["bron_iri"] for a in anchors}) == 1 and anchors[0]["bron_iri"] in reused:
            continue
        cleaned = {k: v for k, v in element.items() if k != "anker"}
        result.append({**cleaned, "ankers": anchors, "eigenaar_iri": owner})
    return result






def doel_event(doel, bron):
    snapshot = bron["bron_snapshot"]
    target = snapshot["doel"]
    view = bron.get("annotatie_weergave") or {}
    return {**doel, **target, "bwbId": target.get("bwb_id", ""), "schema_versie": 2,
            "snapshot_id": snapshot["snapshot_id"], "segmenten": snapshot["segmenten"],
            "leden_teksten": [{"lid": target.get("lid", ""), "tekst": bron["corpus"]}],
            "verwachte_revisies": {layer["bron_iri"]: layer["revisie"] for layer in view.get("lagen", [])},
            "bereik": [s["bron_iri"] for s in snapshot["segmenten"]]}


#: Lifecycles waarin een jurist over de markering besliste.
_BEOORDEELD = {"human_approved", "edited"}


def telling(markeringen: list[dict[str, str]]) -> dict[str, int]:
    """Hoeveel markeringen er liggen, en hoe ver de review is."""
    uit = {"markeringen": len(markeringen), "beoordeeld": 0, "afgewezen": 0, "te_beoordelen": 0}
    for m in markeringen:
        lc = m.get("lifecycle", "")
        if lc in _BEOORDEELD:
            uit["beoordeeld"] += 1
        elif lc == "rejected":
            uit["afgewezen"] += 1
        else:
            uit["te_beoordelen"] += 1
    return uit
