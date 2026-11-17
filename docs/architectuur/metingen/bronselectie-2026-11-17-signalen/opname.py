"""Stap 1: een vaste opname per regeling – eenheden (lid, artikel zonder leden, divisie) met tekst, koppen en
inkomende verwijzingen. Alleen lezen. Elke query wordt tegen een COUNT getoetst (de MCP kapt grote antwoorden af).
Schrijft opname/<bwb>.json."""
import json, os, sys
import graaf
from agent.graph.queries import BEVAT

P = "PREFIX bwb: <urn:bwb-ns:> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
PAG = 250


def alle(select, waar, orde):
    n = int(graaf.select(P + f"SELECT (COUNT(*) AS ?n) WHERE {{ {waar} }}")[0]["n"])
    uit, off = [], 0
    while off < n:
        rs = graaf.select(P + f"SELECT {select} WHERE {{ {waar} }} ORDER BY {orde} LIMIT {PAG} OFFSET {off}")
        if not rs:
            raise RuntimeError("lege pagina")
        uit += rs
        off += len(rs)
    if len(uit) != n:
        raise RuntimeError(f"telling {len(uit)} != {n}")
    return uit


def eenheden(r):
    return f"""{{ ?u a bwb:Lid }} UNION {{ ?u a bwb:Artikel FILTER NOT EXISTS {{ ?u bwb:heeftLid ?x }} }} UNION {{ ?u a bwb:Divisie }}
      FILTER(STRSTARTS(STR(?u), "urn:bwb:{r}:"))"""


def opname(r):
    pad = f"opname/{r}.json"
    e = {}
    leeg = lambda: {"tekst": "", "kop": [], "label": ""}
    for x in alle("?u ?d ?t", eenheden(r) + " OPTIONAL { ?u (bwb:heeftOnderdeel)* ?d . ?d bwb:tekst ?t }", "?u ?d"):
        u = e.setdefault(x["u"], leeg())
        if x.get("t"):
            u["tekst"] += " " + x["t"]
    for x in alle("?u ?l", eenheden(r) + " ?u rdfs:label ?l", "?u ?l"):
        e.setdefault(x["u"], leeg())["label"] = x["l"]
    for x in alle("?u ?a ?l", eenheden(r) + f" ?a ({BEVAT})+ ?u . ?a rdfs:label ?l FILTER(?a != <urn:bwb:{r}>)", "?u ?a ?l"):
        e.setdefault(x["u"], leeg())["kop"].append(x["l"])
    ink = alle("?doel ?bron ?anker", f"""?v bwb:naar ?doel . FILTER(STRSTARTS(STR(?doel), "urn:bwb:{r}:"))
        ?bron bwb:heeftVerwijzing ?v . OPTIONAL {{ ?v bwb:ankerTekst ?anker }}""", "?doel ?bron ?anker")
    bronnen = sorted({x["bron"] for x in ink})
    teksten = {}
    for i in range(0, len(bronnen), 60):
        w = " ".join(f"<{b}>" for b in bronnen[i:i + 60])
        for x in alle("?bron ?t", f"VALUES ?bron {{ {w} }} ?bron bwb:tekst ?t", "?bron ?t"):
            teksten[x["bron"]] = x["t"]
    for x in ink:
        x["t"] = teksten.get(x["bron"], "")
    json.dump({"eenheden": e, "inkomend": ink}, open(pad, "w"), ensure_ascii=False)
    print(r, len(e), "eenheden,", len(ink), "verwijzingen", flush=True)


if __name__ == "__main__":
    os.makedirs("opname", exist_ok=True)
    for r in sys.argv[1:]:
        opname(r)
