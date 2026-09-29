"""Bevries de vier controlecasussen rechtstreeks uit de graaf; geen XML/web-terugval.

De projectconfig wordt alleen voor de MCP-verbinding gelezen. Credentials komen nooit
in de uitvoer. De oorspronkelijke onderzoeksbronnen worden niet overschreven.
"""
import argparse
from datetime import datetime, timezone
from functools import cache
import json
from pathlib import Path

from bronmodel import bron_query, parse_rows, tekst_hash
from agent.mcp_client import MCPClient
from agent.graph.queries import get_regeling_info
from agent.graph.results import parse_select

ROOT = Path(__file__).resolve().parents[3]
CONTROLES = {
    "IW02": ("BWBR0004770", "36", "1", ""),
    "AWB04": ("BWBR0005537", "4:17", "2", ""),
    "WZT01": ("BWBR0018451", "2", "1", ""),
    "RVV03": ("BWBR0004825", "74", "1", "c"),
}


def haal(graph, vervang=False):
    query = cache(graph.sparql)
    refs = {c["id"]: c for c in json.loads((ROOT / "docs/wetsanalyse/referentieset/v1/cases.json").read_text())}
    uit = []
    controles = dict(CONTROLES)
    if vervang:
        controles.pop("WZT01")
        controles.pop("RVV03")
        controles.update({"AWB-4:17-1": ("BWBR0005537", "4:17", "1", ""),
                          "IW04": ("BWBR0004770", "34", "6", "")})
    for cid, (bwb, artikel, lid, onderdeel) in controles.items():
        def lees_node(iri):
            q = bron_query(bwb).replace("  ?node a ?type .", f"  VALUES ?node {{ <{iri}> }}\n  ?node a ?type .")
            rows = parse_rows(query(q))
            if len(rows) != 1:
                raise ValueError(f"{cid}: concrete bronnode ontbreekt of is dubbelzinnig: {iri}")
            r = rows[0]
            return {"bron_iri": r["node"], "parent_iri": r.get("parent", ""),
                    "type": r["type"].removeprefix("urn:bwb-ns:"), "nummer": r.get("nummer", ""),
                    "label": r.get("label") or r.get("titel") or "", "tekst": r.get("tekst", ""),
                    "bron_hash": tekst_hash(r.get("tekst", "")), "bwb_id": bwb, "volgorde": 0,
                    "jci": r.get("jci", ""), "url": r.get("url", ""), "toestand": r.get("toestand", "")}
        vind = f'''PREFIX bwb: <urn:bwb-ns:>
SELECT DISTINCT ?node WHERE {{ GRAPH <urn:bwb:graph:{bwb}> {{
 ?artikel a bwb:Artikel; bwb:nummer ?a; bwb:heeftLid ?node.
 ?node a bwb:Lid; bwb:nummer ?l.
 FILTER(STR(?a) = "{artikel}" && STR(?l) = "{lid}")
}} }}'''
        gevonden = parse_rows(query(vind))
        if len(gevonden) != 1:
            raise ValueError(f"{cid}: artikel/lid niet eenduidig gevonden: {gevonden}")
        node = lees_node(gevonden[0]["node"])
        if onderdeel:
            q = bron_query(bwb).replace("  ?node a ?type .",
                f'  ?node a ?type . FILTER(?parent = <{node["bron_iri"]}> && STR(?nummer) IN ("{onderdeel}", "{onderdeel}."))')
            matches = parse_rows(query(q))
            if len(matches) != 1:
                raise ValueError(f"{cid}: onderdeel niet eenduidig uit graaf")
            node = lees_node(matches[0]["node"])
        ouders = []
        iri = node["parent_iri"]
        while iri and iri != f"urn:bwb:{bwb}":
            if iri in {n["bron_iri"] for n in ouders}:
                raise ValueError("cyclische oudercontext")
            n = lees_node(iri)
            ouders.append(n)
            iri = n["parent_iri"]
        # Gerichte onderzoekssnapshot: geen aanspraak op de volledige bronboom-ID.
        ns = [*reversed(ouders), node]
        for i, n in enumerate(ns):
            n["volgorde"] = i
        snap = {"schema_versie": 2, "snapshot_id": tekst_hash(json.dumps(ns, sort_keys=True)),
                "snapshot_soort": "gerichte_graafnodes_geen_volledige_bronboom",
                "nodes": ns, "segmenten": [node], "doel": node,
                "voorouders": list(reversed(ouders)), "toestand": node["toestand"]}
        info = parse_select(query(get_regeling_info(bwb)))
        if len(info) != 1:
            raise ValueError(f"{cid}: regelingmetadata niet eenduidig")
        # Alleen de geselecteerde eigen node; parentaanhef blijft apart in snapshot/context.
        if len(snap["segmenten"]) != 1:
            raise ValueError(f"{cid}: verwacht één eigen bronsegment")
        node = snap["segmenten"][0]
        context = [n for n in snap["voorouders"] if n["tekst"].strip()]
        # Eerste lid bij een vervolgonderdeel/-lid geeft zijn expliciete aanhef of hoofdregel.
        if cid == "AWB04":
            eerste = parse_rows(query(vind.replace(f'STR(?l) = "{lid}"', 'STR(?l) = "1"')))
            if len(eerste) != 1:
                raise ValueError("hoofdregel ontbreekt in graaf")
            context.append(lees_node(eerste[0]["node"]))
        toestand = info[0].get("geldigVanaf") or snap.get("toestand") or "onbekend"
        status = info[0].get("soort") or "onbekend"
        def passage(n):
            return {"bron_iri": n["bron_iri"], "tekst": n["tekst"], "bron_hash": n["bron_hash"],
                    "herkomst": "graaf", "toestand": toestand, "juridische_status": status,
                    "functie": "ouderaanhef" if n in snap["voorouders"] else "expliciete hoofdregel"}
        chosen = {n["bron_iri"]: n for n in [*snap["voorouders"], *snap["segmenten"]]}
        klein = {**snap, "nodes": list(chosen.values())}
        uit.append({"id": cid, "snapshot": klein, "herkomst": "graaf", "metadata": info[0],
                    "context": [passage(n) for n in context], "toestand": toestand,
                    "juridische_status": status, "opgehaald_op": datetime.now(timezone.utc).isoformat(),
                    "historische_fixture_identiek": node["tekst"] == refs[cid]["tekst"] if cid in refs else None,
                    "historische_fixture_hash": refs[cid]["tekst_sha256"] if cid in refs else None})
        print(cid, len(node["tekst"]), "codepoints; graaftekst vastgelegd", flush=True)
    return {"schema_versie": 1, "herkomst": "graaf", "controles": uit, "vervanging": {"WZT01": "AWB-4:17-1", "RVV03": "IW04"} if vervang else {},
            "reden_vervanging": "WZT en RVV ontbreken in repository inning; geen externe terugvaltekst." if vervang else ""}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--projectconfig", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--vervang-ontbrekende", action="store_true")
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    cfg = json.loads(args.projectconfig.read_text())["projects"][str(ROOT)]["mcpServers"]["graphdb"]
    client = MCPClient(url=cfg["url"], token=cfg["headers"]["Authorization"].removeprefix("Bearer "), repository_id="inning")
    try:
        uit = haal(client, args.vervang_ontbrekende)
    finally:
        client.close()
    with args.output.open("x") as f:
        json.dump(uit, f, indent=2, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    main()
