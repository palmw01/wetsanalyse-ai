"""Eén bronidentiteit en ankerbasis voor API en agent; geen modelbeslissingen.

De importer levert eigen tekst per node. Nummers/labels worden bewust niet in die
tekst geplakt: offsets zijn Unicode-codepoints binnen het exacte tekstliteral.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any, Callable

RELATIES = ("heeftHoofdstuk", "heeftTiteldeel", "heeftAfdeling", "heeftParagraaf",
            "heeftArtikel", "heeftLid", "heeftOnderdeel", "heeftDivisie", "heeftBijlage")
TYPEN = ("Regeling", "Hoofdstuk", "Titeldeel", "Afdeling", "Paragraaf", "Artikel",
         "Lid", "Onderdeel", "Divisie", "Bijlage")
PAD = "(" + "|".join("bwb:" + r for r in RELATIES) + ")"
_BWB = re.compile(r"^BWB[RV]\d+$")
_IRI = re.compile(r"^urn:bwb:(BWB[RV]\d+)(?::[^<>\s\"{}|^`\\]*)?$")


class BronFout(ValueError):
    """Een bron ontbreekt, is dubbelzinnig of heeft geen consistente boom."""


def tekst_hash(tekst: str) -> str:
    return hashlib.sha256(tekst.encode("utf-8")).hexdigest()


def bron_query(bwb_id: str, *, limit: int | None = None, offset: int = 0) -> str:
    if not _BWB.fullmatch(bwb_id):
        raise BronFout("Ongeldig BWB-id")
    types = " ".join("bwb:" + t for t in TYPEN)
    query = f'''PREFIX bwb: <urn:bwb-ns:>
SELECT DISTINCT ?node ?type ?parent ?nummer ?label ?titel ?tekst ?vorige ?jci ?url ?toestand ?citeertitel WHERE {{
 GRAPH <urn:bwb:graph:{bwb_id}> {{
  VALUES ?type {{ {types} }}
  ?node a ?type .
  OPTIONAL {{ ?parent {PAD} ?node }}
  OPTIONAL {{ ?node bwb:nummer ?nummer }}
  OPTIONAL {{ ?node bwb:label ?label }}
  OPTIONAL {{ ?node bwb:titel ?titel }}
  OPTIONAL {{ ?node bwb:tekst ?tekst }}
  OPTIONAL {{ ?node bwb:volgtOp ?vorige }}
  OPTIONAL {{ ?node bwb:jci ?jci }}
  OPTIONAL {{ ?node <http://www.w3.org/2002/07/owl#sameAs> ?url }}
  OPTIONAL {{ <urn:bwb:{bwb_id}> bwb:toestandUrl ?toestand }}
  OPTIONAL {{ <urn:bwb:{bwb_id}> bwb:citeertitel ?citeertitel }}
 }}
}} ORDER BY ?node'''
    if limit is not None:
        if not 1 <= limit <= 100 or offset < 0:
            raise BronFout("Ongeldige bronpagina")
        query += f" LIMIT {int(limit)} OFFSET {int(offset)}"
    return query


def parse_rows(result: Any) -> list[dict[str, str]]:
    """GraphDB JSON en de SPARQL-TSV uit de bestaande MCP-poort."""
    if isinstance(result, str):
        try:
            decoded = json.loads(result)
            result = decoded
        except json.JSONDecodeError:
            pass
    if isinstance(result, dict):
        if "results" not in result:
            raise BronFout("Geen SPARQL SELECT-resultaat")
        return [{k: v.get("value", "") for k, v in row.items()}
                for row in result["results"].get("bindings", [])]
    if isinstance(result, list):
        return result
    if not isinstance(result, str):
        raise BronFout("Onbekend bronresultaat")
    lines = result.splitlines()
    if not lines or not lines[0].startswith("?"):
        raise BronFout("Ongeldig SPARQL-TSV-resultaat")
    keys = [k.lstrip("?") for k in lines[0].split("\t")]

    def decode(term: str) -> str:
        if term.startswith("<") and term.endswith(">"):
            return term[1:-1]
        if term.startswith('"'):
            try:
                return json.JSONDecoder().raw_decode(term)[0]
            except ValueError as exc:
                raise BronFout("Ongeldig tekstliteral") from exc
        return term
    return [{k: decode(v) for k, v in zip(keys, line.split("\t"))}
            for line in lines[1:] if line.strip()]


def _sort(waarde: str) -> tuple:
    if re.fullmatch(r"[IVXLCDM]+", waarde):
        roman = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
        total, previous = 0, 0
        for character in reversed(waarde):
            number = roman[character]
            total += -number if number < previous else number
            previous = max(previous, number)
        return ((0, total),)
    return tuple((0, int(x)) if x.isdigit() else (1, x.casefold())
                 for x in re.findall(r"\d+|\D+", waarde))


def subtree(nodes: list[dict], bron_iri: str) -> list[dict]:
    by_id = {n["bron_iri"]: n for n in nodes}
    if bron_iri not in by_id:
        raise BronFout("De gevraagde bronnode bestaat niet")
    selected = {bron_iri}
    # Canonieke nodes zijn pre-order, maar deze functie accepteert ook test/inputlijsten.
    while True:
        newer = selected | {n["bron_iri"] for n in nodes if n.get("parent_iri") in selected}
        if newer == selected:
            break
        selected = newer
    return [n for n in nodes if n["bron_iri"] in selected]


def eigenaar(nodes: list[dict], iris: list[str]) -> str:
    """Diepste gezamenlijke bestaande ouder; geen verzonnen lid- of artikelnode."""
    by_id = {n["bron_iri"]: n for n in nodes}
    if not iris or any(i not in by_id for i in iris):
        raise BronFout("Anker heeft geen bekende bronnode")
    paths = []
    for iri in iris:
        path = []
        while iri:
            if iri in path or iri not in by_id:
                raise BronFout("Bronboom is onvolledig of cyclisch")
            path.append(iri)
            iri = by_id[iri].get("parent_iri", "")
        paths.append(path)
    for iri in paths[0]:
        if all(iri in p for p in paths[1:]):
            return iri
    raise BronFout("Ankers horen niet bij dezelfde bronboom")


def valideer_ankers(snapshot: dict, ankers: list[dict]) -> str:
    nodes = {n["bron_iri"]: n for n in snapshot["nodes"]}
    if not ankers:
        raise BronFout("Een annotatie vereist minimaal één bronanker")
    last = None
    for a in ankers:
        node = nodes.get(a.get("bron_iri"))
        if node is None:
            raise BronFout("Ankerbron bestaat niet in deze snapshot")
        start, eind = a.get("start"), a.get("eind")
        if type(start) is not int or type(eind) is not int or not 0 <= start < eind <= len(node["tekst"]):
            raise BronFout("Ongeldige lokale ankerposities")
        if a.get("bron_hash") != node["bron_hash"] or a.get("tekst") != node["tekst"][start:eind]:
            raise BronFout("Anker komt niet overeen met de letterlijke bron")
        if a.get("snapshot_id", snapshot["snapshot_id"]) != snapshot["snapshot_id"]:
            raise BronFout("Ankers combineren verschillende snapshots")
        key = (node["volgorde"], start, eind)
        if last and (key < last or (key[0] == last[0] and start < last[2])):
            raise BronFout("Ankers staan niet in bronvolgorde of overlappen")
        last = key
    return eigenaar(snapshot["nodes"], [a["bron_iri"] for a in ankers])


def bouw_snapshot(rows: list[dict], *, bron_iri: str = "", bwb_id: str,
                  artikel: str = "", lid: str = "") -> dict:
    nodes: dict[str, dict] = {}
    toestanden = set()
    for row in rows:
        iri, kind = row.get("node", ""), row.get("type", "").removeprefix("urn:bwb-ns:")
        if kind not in TYPEN or not _IRI.fullmatch(iri) or _IRI.fullmatch(iri).group(1) != bwb_id:
            raise BronFout("Onbekende of bronvreemde node")
        item = {"bron_iri": iri, "parent_iri": row.get("parent", ""), "type": kind,
                "nummer": row.get("nummer", ""), "label": row.get("label") or row.get("titel")
                or f"{kind} {row.get('nummer', '')}".strip(), "tekst": row.get("tekst", ""),
                "bwb_id": bwb_id, "vorige": row.get("vorige", ""), "url": row.get("url", ""),
                "jci": row.get("jci", "")}
        item["bron_hash"] = tekst_hash(item["tekst"])
        if iri in nodes and nodes[iri] != item:
            raise BronFout(f"Dubbelzinnige bronnode: {iri}")
        nodes[iri] = item
        if row.get("toestand"):
            toestanden.add(row["toestand"])
    if not nodes or f"urn:bwb:{bwb_id}" not in nodes:
        raise BronFout("Regeling niet gevonden in de brongraaf")
    if len(toestanden) > 1:
        raise BronFout("Meerdere bronstanden in één regeling")
    children: dict[str, list[dict]] = defaultdict(list)
    for n in nodes.values():
        if n["parent_iri"] and n["parent_iri"] not in nodes:
            raise BronFout("Ontbrekende ouder in de bronboom")
        children[n["parent_iri"]].append(n)
    ordered, visited = [], set()

    def visit(parent: str, depth: int = 0):
        if depth > 100:
            raise BronFout("Bronboom is te diep")
        remaining = sorted(children[parent], key=lambda n: (_sort(n["nummer"]), n["bron_iri"]))
        sibling_ids = {n["bron_iri"] for n in remaining}
        done = set()
        while remaining:
            ready = next((n for n in remaining if n["vorige"] not in sibling_ids or n["vorige"] in done), None)
            if ready is None or ready["bron_iri"] in visited:
                raise BronFout("Cyclische bronvolgorde")
            remaining.remove(ready)
            visited.add(ready["bron_iri"])
            done.add(ready["bron_iri"])
            ready["volgorde"] = len(ordered)
            ordered.append(ready)
            visit(ready["bron_iri"], depth + 1)
    visit("")
    if len(visited) != len(nodes):
        raise BronFout("Niet alle nodes zijn verbonden")
    if not bron_iri:
        if artikel:
            candidates = [n for n in ordered if n["type"] in {"Artikel", "Divisie"}
                          and n["nummer"].strip() == artikel.strip()]
            if len(candidates) != 1:
                raise BronFout("Bepaling niet gevonden of dubbelzinnig; kies een bronnode")
            bron_iri = candidates[0]["bron_iri"]
            if lid:
                candidates = [n for n in children[bron_iri] if n["type"] == "Lid"
                              and n["nummer"].strip().lstrip("0") == lid.strip().lstrip("0")]
                if len(candidates) != 1:
                    raise BronFout("Het gevraagde lid bestaat niet of is dubbelzinnig")
                bron_iri = candidates[0]["bron_iri"]
        elif lid:
            raise BronFout("Een lid vereist een artikel")
        else:
            bron_iri = f"urn:bwb:{bwb_id}"
    chosen = subtree(ordered, bron_iri)
    target = nodes[bron_iri]
    parents = []
    parent = target["parent_iri"]
    while parent:
        parents.append(nodes[parent])
        parent = nodes[parent]["parent_iri"]
    article = next((n["nummer"] for n in [target, *parents] if n["type"] in {"Artikel", "Divisie"}), "")
    lidnummer = next((n["nummer"] for n in [target, *parents] if n["type"] == "Lid"), "")
    canonical = json.dumps({"nodes": ordered, "toestand": sorted(toestanden)}, ensure_ascii=False,
                           sort_keys=True, separators=(",", ":"))
    titel = next((r["citeertitel"] for r in rows if r.get("citeertitel")), bwb_id)
    path = [n for n in [*reversed(parents), target] if n["type"] != "Regeling"]
    # Detailkop: wet + concrete vindplaats, niet alleen "Lid 1". Bronlabels zelf
    # blijven los van de tekst waar de ankers tegen worden gecontroleerd.
    begin = next((i for i, n in enumerate(path) if n["type"] in {"Artikel", "Divisie"}), 0)
    label = titel + (" – " + ", ".join(n["label"] for n in path[begin:]) if path else "")
    return {"schema_versie": 2, "snapshot_id": tekst_hash(canonical),
            "doel": {**target, "artikel": article, "lid": lidnummer, "label": label,
                     "citeertitel": titel, "bronpad": [n["bron_iri"] for n in path]},
            "nodes": ordered, "segmenten": [n for n in chosen if n["tekst"].strip()],
            "voorouders": list(reversed(parents)), "toestand": next(iter(toestanden), "")}


def resolve(graph_query: Callable[[str], Any], *, bron_iri: str = "", bwb_id: str = "",
            artikel: str = "", lid: str = "") -> dict:
    if bron_iri:
        match = _IRI.fullmatch(bron_iri)
        if not match or (bwb_id and bwb_id != match.group(1)):
            raise BronFout("Ongeldige bron-IRI of regeling")
        bwb_id = match.group(1)
    bwb_id = bwb_id.strip().upper()
    # De MCP-server kapt grote TSV-responses af (256 kB). Lees begrensde pagina's;
    # een kapot literal is een fout, nooit stil een onvolledige snapshot.
    rows = []
    for offset in range(0, 100000, 100):
        page = parse_rows(graph_query(bron_query(bwb_id, limit=100, offset=offset)))
        rows.extend(page)
        if len(page) < 100:
            break
    else:
        raise BronFout("Bronboom overschrijdt de maximale paginalimiet")
    return bouw_snapshot(rows, bron_iri=bron_iri,
                         bwb_id=bwb_id, artikel=artikel, lid=lid)
