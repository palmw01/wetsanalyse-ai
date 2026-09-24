"""Annoteren op canonieke bronsegmenten; lokale posities blijven los van de UI-opmaak."""
from __future__ import annotations

import json
from uuid import uuid4
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
    return {"corpus": corpus, "artikel_corpus": corpus, "lidstand": [],
            "bron_snapshot": snapshot, "corpus_segmenten": spans}


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
    # jurist vóór een modelronde te horen, niet erna – een volledige ronde kost een minuut en
    # tokens, en "probeer opnieuw" levert daarna precies hetzelfde op. Afgeronde nodes gaan
    # daarom mee als "al geannoteerd", zodat er geen nieuw element in belandt. Alleen als er dan
    # niets overblijft om te doen – geen open node en geen eigen markering van een jurist waar de
    # Critic advies op kan geven (dat mag wél op een afgeronde laag) – stopt de beurt meteen.
    afgerond = {laag["bron_iri"] for laag in view.get("lagen") or [] if laag.get("status") == "geaccordeerd"}
    alles_afgerond = (bool(selected) and selected <= afgerond
                      and not bevroren_markeringen({**bron, "annotatie_weergave": view}))
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
    from .annotatielaag import telling
    reused = {"slug": params["bron_iri"], "status": "", "bijgewerkt": coverage.get("peilmoment", ""),
              "leden": [{"lid": n.get("nummer", ""), "iri": n["bron_iri"], "hash": n["bron_hash"]}
                        for n in snapshot["segmenten"] if n["bron_iri"] in completed],
              "bereik": sorted(completed & selected), "markeringen": elements,
              "telling": telling(elements), "volledig": full}
    # Parent-context blijft volledig beschikbaar voor overspannende regels. De prompt vertelt
    # expliciet welke nodes al af zijn; hun lokale elementen mogen niet opnieuw worden voorgesteld.
    # Afgeronde nodes horen daar ook bij: daar mag niets meer bij.
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


def bron_instructie(bron):
    segments = bron.get("corpus_segmenten") or []
    if not segments:
        return ""
    return ("\n\nBRONNODES: geef bij ELK element een lijst 'ankers' met per fragment "
            "{bron_iri, tekst, start, eind}. start/eind zijn Unicode-codepoints in de eigen tekst "
            "van die node, zonder kop of nummer. Een overspannend element heeft meerdere ankers; "
            "tekst is hun letterlijke fragmenten samengevoegd met één spatie. Geen "
            "verzonnen nodes. Gebruik onderstaande teksten; nummers/labels tellen niet mee.\n"
            + json.dumps([{k: s[k] for k in ("bron_iri", "label", "tekst")} for s in segments], ensure_ascii=False)
            + ("\nDeze nodes zijn lokaal al geannoteerd; doe alleen ontbrekende nodes en "
               "overspannende samenhang, stel hun lokale elementen niet opnieuw voor: "
               + json.dumps(bron["hergebruikte_nodes"]) if bron.get("hergebruikte_nodes") else ""))


def verwerk_bron(llm_text, corpus, bwb_id, artikel, scope_lid, geldige_ids, soort, bron):
    """Behoud bestaande JAS-validatie; ankerkeuze gebeurt per expliciete bronnode."""
    from .annotatie import _parse_elementen, _verwerk, _maak_anker, _voeg_alternatief_toe
    from .models import VerworpenFragment
    spans = bron["corpus_segmenten"]
    by_iri = {s["bron_iri"]: s for s in spans}
    kaart = CorpusMap(spans)
    result, rejected, seen = [], [], {}
    for item in _parse_elementen(llm_text):
        anchors = []
        supplied = item.get("ankers") or []
        try:
            if supplied:
                for raw in supplied:
                    node = by_iri.get(raw.get("bron_iri"))
                    if node is None:
                        raise BronFout("bron_buiten_selectie")
                    text = str(raw.get("tekst", ""))
                    start = raw.get("start")
                    end = raw.get("eind")
                    if type(start) is not int or type(end) is not int or node["tekst"][start:end] != text:
                        if not text or node["tekst"].count(text) != 1:
                            raise BronFout("ambigu_anker")
                        start, end = node["tekst"].index(text), node["tekst"].index(text) + len(text)
                    anchors.append({"bron_iri": node["bron_iri"], "tekst": text, "start": start,
                                    "eind": end, "bron_hash": node["bron_hash"]})
            else:
                text = str(item.get("tekst", ""))
                candidates = [s for s in spans if text and s["tekst"].count(text)]
                if item.get("bron_iri"):
                    candidates = [s for s in candidates if s["bron_iri"] == item["bron_iri"]]
                if len(candidates) != 1 or candidates[0]["tekst"].count(text) != 1:
                    raise BronFout("ambigu_anker_geef_bronnode_en_posities")
                node = candidates[0]
                start = node["tekst"].index(text)
                anchors = [{"bron_iri": node["bron_iri"], "tekst": text, "start": start,
                            "eind": start + len(text), "bron_hash": node["bron_hash"]}]
            valideer_ankers(bron["bron_snapshot"], anchors)
            text = " ".join(a["tekst"] for a in anchors)
            proposals, invalid = _verwerk(json.dumps({"elementen": [{**item, "tekst": text}]}),
                                          text, bwb_id, artikel, scope_lid, geldige_ids, soort)
            rejected.extend(invalid)
            if not proposals:
                continue
            proposal = proposals[0]
            key = tuple((a["bron_iri"], a["start"], a["eind"]) for a in anchors)
            if key in seen:
                _voeg_alternatief_toe(seen[key], proposal.klasse, proposal.toelichting)
                continue
            first, last = anchors[0], anchors[-1]
            proposal.anker = _maak_anker(corpus,
                kaart.segment(first["bron_iri"]).corpus_start + first["start"],
                kaart.segment(last["bron_iri"]).corpus_start + last["eind"], scope_lid or "")
            proposal.ankers = anchors
            if any(previous.id == proposal.id for previous in result):
                proposal.id = uuid4().hex[:12]
            seen[key] = proposal
            result.append(proposal)
        except (BronFout, TypeError, KeyError) as exc:
            rejected.append(VerworpenFragment(klasse=str(item.get("klasse", "")),
                                              tekst=str(item.get("tekst", "")), reden=str(exc)))
    return result, rejected


def doel_event(doel, bron):
    snapshot = bron["bron_snapshot"]
    target = snapshot["doel"]
    view = bron.get("annotatie_weergave") or {}
    return {**doel, **target, "bwbId": target.get("bwb_id", ""), "schema_versie": 2,
            "snapshot_id": snapshot["snapshot_id"], "segmenten": snapshot["segmenten"],
            "leden_teksten": [{"lid": target.get("lid", ""), "tekst": bron["corpus"]}],
            "verwachte_revisies": {layer["bron_iri"]: layer["revisie"] for layer in view.get("lagen", [])},
            "bereik": [s["bron_iri"] for s in snapshot["segmenten"]]}


def bevroren_markeringen(bron):
    """Actuele menselijke markeringen uit de API; alleen advies, nooit nieuwe elementen."""
    snapshot = bron.get("bron_snapshot") or {}
    selected = {node["bron_iri"] for node in snapshot.get("segmenten", [])}
    result = []
    for element in (bron.get("annotatie_weergave") or {}).get("elementen", []):
        if element.get("herkomst") != "mens" or not element.get("id"):
            continue
        anchors = element.get("ankers") or []
        try:
            owner = valideer_ankers(snapshot, anchors)
        except (BronFout, KeyError, TypeError):
            continue
        if owner != element.get("eigenaar_iri") or owner not in selected:
            continue
        if any(a["bron_iri"] not in selected for a in anchors):
            continue
        if element.get("tekst") != " ".join(a["tekst"] for a in anchors):
            continue
        if element.get("lifecycle") in {"rejected"}:
            continue
        result.append({
            "id": element["id"], "klasse": element.get("klasse", ""),
            "tekst": element["tekst"], "ankers": anchors, "lid": "",
            "toelichting": element.get("toelichting", ""), "alternatieven": [],
            "grounded": True, "vindplaats": "", "aandacht": "", "critic": "",
            "van_jurist": True,
        })
    return result
