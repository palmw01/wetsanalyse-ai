"""V2 poortfixtures voor bestaande Critic-scenario's.

De canned juridische teksten blijven ongewijzigd. Deze adapter levert ze als echte
bronboom aan de resolver en biedt een aparte, lege maar beschikbare annotatie-API.
Geen productie-fallback en geen vervanging van Critic/annotatie-uitkomsten.
"""
import json

from bronmodel import bouw_snapshot
from agent.agent import answer_stream as echte_answer_stream
from agent.graph.results import parse_select


def bronrijen(raw, doel):
    if isinstance(raw, list):
        return raw
    rows = parse_select(raw)
    bwb = doel.get("bwbId") or doel.get("bwb_id") or "BWBR0004770"
    artikel = doel.get("artikel") or doel.get("nummer") or "9"
    reg = f"urn:bwb:{bwb}"
    art = f"{reg}:artikel:{artikel}"
    soort = "Divisie" if "." in artikel else "Artikel"
    result = [{"node": reg, "type": "Regeling", "nummer": "", "tekst": "", "citeertitel": doel.get("citeertitel") or "Invorderingswet 1990"},
              {"node": art, "parent": reg, "type": soort, "nummer": artikel, "tekst": ""}]
    seen = set()
    for row in rows:
        if not any(row.get(k) for k in ("tekst", "lidtekst")):
            continue
        lid = str(row.get("lidnummer") or (row.get("nummer") if soort == "Artikel" else "") or "")
        text = str(row.get("lidtekst") or row.get("tekst") or "")
        if lid:
            iri = f"{art}:lid:{lid}"
            if iri not in seen:
                result.append({"node": iri, "parent": art, "type": "Lid", "nummer": lid, "tekst": text})
                seen.add(iri)
        else:
            result[1]["tekst"] = text
    return result if seen or result[1]["tekst"] else []


class BronGraph:
    def __init__(self, graph, doel):
        self.graph, self.doel, self.snapshot = graph, doel, None

    def __getattr__(self, key):
        return getattr(self.graph, key)

    def sparql(self, query):
        raw = self.graph.sparql(query)
        if "SELECT DISTINCT ?node ?type ?parent" not in query:
            return raw
        rows = bronrijen(raw, self.doel)
        if not rows:
            return []
        self.snapshot = bouw_snapshot(rows, bwb_id=self.doel.get("bwbId") or self.doel.get("bwb_id") or "BWBR0004770",
            artikel=self.doel.get("artikel") or self.doel.get("nummer") or "9", lid=self.doel.get("lid") or "")
        return rows


class LegeAnnotaties:
    def __init__(self, graph, menselijke_markeringen=()):
        self.graph = graph
        self.menselijke_markeringen = menselijke_markeringen
    def dekking(self, _doel):
        return {"status": "ok", "snapshot_id": self.graph.snapshot["snapshot_id"], "voltooid": False,
                "bereik": [], "parent_context": False}
    def weergave(self, _doel):
        elements = []
        for item in self.menselijke_markeringen:
            if item.get("herkomst") != "mens":
                continue
            candidates = [n for n in self.graph.snapshot["segmenten"]
                          if item.get("tekst") and n["tekst"].count(item["tekst"]) == 1
                          and (not item.get("lid") or (n.get("nummer") if n.get("type") == "Lid" else n.get("lid")) == item["lid"])]
            if len(candidates) != 1:
                continue
            node = candidates[0]
            start = node["tekst"].index(item["tekst"])
            elements.append({**item, "eigenaar_iri": node["bron_iri"], "lifecycle": "human_approved",
                "beslissingen": [], "ankers": [{"bron_iri": node["bron_iri"], "start": start,
                    "eind": start + len(item["tekst"]), "tekst": item["tekst"], "bron_hash": node["bron_hash"]}]})
        owners = sorted({e["eigenaar_iri"] for e in elements})
        return {"schema_versie": 2, "snapshot_id": self.graph.snapshot["snapshot_id"],
                "lagen": [{"id": f"laag-{i}", "bron_iri": iri, "revisie": 1, "status": "in_review"}
                          for i, iri in enumerate(owners)], "elementen": elements}


def antwoord_doel(llm):
    for response in getattr(llm, "_responses", []):
        for block in response.content:
            if block.type != "text":
                continue
            try:
                value = json.loads(block.text)
            except (ValueError, TypeError):
                continue
            if isinstance(value, dict) and value.get("bwbId"):
                return value
    return {}


def answer_stream(*args, **kwargs):
    graph = kwargs.get("graph")
    doel = kwargs.get("doel") or antwoord_doel(kwargs.get("llm"))
    if graph is not None and doel:
        wrapped = BronGraph(graph, doel)
        kwargs["graph"] = wrapped
        context = kwargs.get("context") or {}
        if hasattr(context, "model_dump"):
            context = context.model_dump()
        kwargs.setdefault("annotaties", LegeAnnotaties(wrapped, context.get("bestaande_elementen", [])))
    return echte_answer_stream(*args, **kwargs)
