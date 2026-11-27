"""Afleidingsregels naar de kennisgraaf (ADR-018 §7; rapport *regels-herleidbaarheid*, 20 nov 2026).

De regels staan in de named graph van hun werkgebied (`urn:wa:graph:werkgebied:<id>`), naast het begrippenkader: dat is
één graph met één PUT, dus de begrippenprojectie (`begrip_projectie.invoer` en `bouw_graaf`) neemt ze mee. Hier staan
de invoer uit Postgres en de triples; projecteren, register, reconcile en graafcontrole zijn die van de begrippen.

- **Alle regels, met hun status** (besluit van 20 nov 2026): ook concept, afgewezen en vervangen. Het doel is dat elke
  regel naar de wettekst te herleiden is; `wa:status` zegt wat geaccordeerd is.
- **De weg naar de wettekst**: regel → `wa:drager` (rol, geval, beoordeling) → `wa:element` (de W3C-annotatie in de
  JAS-laag, `urn:jas:element:*`) → `oa:hasTarget/oa:hasSource` → de bronnode (`urn:bwb:…`, met `bwb:jci` of
  `bwb:bronUrl` en `bwb:tekst`). De regel draagt ook `wa:rustOp` (de dragende markeringen) en `prov:wasDerivedFrom` (de
  bronnodes van zijn grondslag), zodat één SPARQL-stap volstaat.
- **Een voorbeeld** (`wa:Voorbeeld`) draagt zijn invoer (in tekst en per invoerbegrip, `wa:waarde`), het geval
  (`wa:inGeval`), de gevallen eronder (`wa:gevalVan`), de verwachte uitkomst en het oordeel.
- **Een voorwaarde** is een knoop met haar tekst, `wa:rustOp` naar haar markeringen en `wa:gevalVan` naar het geval
  van een andere regel. Een groep (`alle`, `een_van`) is een `wa:Voorwaardengroep` met `wa:deel`.
- **Geen subject onder `urn:bwb:`** en geen personen: wie iets deed, staat in Postgres.
- Zuiver: `invoer` leest, `bouw` schrijft triples in een gegeven graph. `conformiteit` is diagnostisch (SHACL,
  `shapes/regels-wa.ttl`), nooit in het schrijfpad.
"""
from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

from rdflib import Graph, Literal, Namespace, RDF, URIRef
from sqlalchemy import select

from . import db
from .graaf_projectie_v2 import element_iri
from .regeltekst import genoemde_begrippen, regeltekst

WA = Namespace("urn:wa-ns:")
DCT = Namespace("http://purl.org/dc/terms/")
PROV = Namespace("http://www.w3.org/ns/prov#")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")
SH = Namespace("http://www.w3.org/ns/shacl#")
SHAPES = Path(__file__).parent / "shapes" / "regels-wa.ttl"
from .regel_contracts import DRAGEND  # noqa: E402  (één plek, bevinding 12)


def regel_iri(regel_id: str) -> URIRef:
    return URIRef(f"urn:wa:regel:{regel_id}")


def geval_iri(regel_id: str, nr: int) -> URIRef:
    return URIRef(f"urn:wa:regel:{regel_id}:geval:{nr}")


def _t(waarde) -> str | None:
    return db.aware(waarde).isoformat() if waarde else None


async def invoer(conn, werkgebied_id: str) -> list[dict[str, Any]]:
    """De regels van één werkgebied met hun dragers en de afgeleide regeltekst, als JSON-vorm (voor de hash)."""
    r, d, b = db.regels, db.regel_dragers, db.begrippen
    rows = (await conn.execute(select(r).where(r.c.werkgebied_id == werkgebied_id).order_by(r.c.id))).all()
    if not rows:
        return []
    dragers: dict[str, list[dict]] = {}
    for x in (await conn.execute(select(d).where(d.c.werkgebied_id == werkgebied_id, d.c.verwijderd.is_(None))
                                 .order_by(d.c.id))).all():
        bewijs = x.bewijs or {}
        dragers.setdefault(x.regel_id, []).append({
            "id": x.id, "element_id": x.element_id, "rol": x.rol, "geval": x.geval, "beoordeling": x.beoordeling,
            "element_hash": bewijs.get("element_hash", ""), "tekst": bewijs.get("tekst", ""),
            "bron": sorted({a["bron_iri"] for a in bewijs.get("ankers") or [] if a.get("bron_iri")})
                    or ([bewijs["eigenaar_iri"]] if bewijs.get("eigenaar_iri") else [])})
    ids = sorted({i for x in rows for i in genoemde_begrippen(x.inhoud)})
    namen = {x.id: (x.inhoud or {}).get("naam", "") for x in (await conn.execute(
        select(b.c.id, b.c.inhoud).where(b.c.id.in_(ids))))} if ids else {}
    return [{"id": x.id, "status": x.status, "revisie": x.revisie, "herkomst": x.herkomst, "inhoud": x.inhoud,
             "regeltekst": regeltekst(x.inhoud, namen), "vervangen_door": x.vervangen_door or "",
             "opvolger_van": x.opvolger_van or "", "geaccordeerd_op": _t(x.geaccordeerd_op),
             "geaccordeerd_revisie": x.geaccordeerd_revisie, "dragers": dragers.get(x.id, [])} for x in rows]


def _nl(tekst: str) -> Literal:
    return Literal(tekst, lang="nl")


def bouw(g: Graph, kader: URIRef, regels: list[dict[str, Any]]) -> None:
    """De triples van de regels van één werkgebied, in `g`. Een verwijzing naar een regel die hier niet staat, wijst
    naar de regel-IRI (en een onbekend geval naar de regel), zodat er niets stil wegvalt."""
    from .begrip_projectie import begrip_iri
    g.bind("prov", PROV)
    labels = {x["id"]: [gv.get("label", "") for gv in x["inhoud"].get("gevallen", [])] for x in regels}

    def doel(v: dict) -> URIRef:
        lb = labels.get(v["regel_id"])
        if lb is None:
            return regel_iri(v["regel_id"])
        nr = lb.index(v["geval"]) + 1 if v.get("geval") in lb else (1 if len(lb) == 1 else 0)
        return geval_iri(v["regel_id"], nr) if nr else regel_iri(v["regel_id"])

    for x in regels:
        i, rid = x["inhoud"], x["id"]
        rg = regel_iri(rid)
        g.add((rg, RDF.type, WA.Afleidingsregel))
        g.add((rg, WA.inKader, kader))
        g.add((rg, WA.status, Literal(x["status"])))
        g.add((rg, WA.revisie, Literal(x["revisie"])))
        g.add((rg, WA.soort, Literal(i["soort"])))
        g.add((rg, WA.brontype, Literal(i.get("brontype", "wet"))))
        g.add((rg, WA.herkomst, Literal(x["herkomst"])))
        g.add((rg, WA.regelbegrip, begrip_iri(i["regelbegrip_id"])))
        g.add((rg, WA.uitvoer, begrip_iri(i["uitvoer_begrip_id"])))
        if i.get("onderwerp_begrip_id"):
            g.add((rg, WA.onderwerp, begrip_iri(i["onderwerp_begrip_id"])))
        if x["regeltekst"]["tekst"]:
            g.add((rg, WA.regeltekst, _nl(x["regeltekst"]["tekst"])))
        if x["status"] in ("geaccordeerd", "geaccordeerd_als_beleidsregel") and x.get("geaccordeerd_op"):
            g.add((rg, WA.geaccordeerdOp, Literal(x["geaccordeerd_op"], datatype=XSD.dateTime)))
            g.add((rg, WA.geaccordeerdRevisie, Literal(x["geaccordeerd_revisie"])))
        if x["vervangen_door"]:
            g.add((rg, DCT.isReplacedBy, regel_iri(x["vervangen_door"])))
        if x["opvolger_van"]:
            g.add((rg, DCT.replaces, regel_iri(x["opvolger_van"])))
        for n, inv in enumerate(i.get("invoer", []), start=1):
            node = URIRef(f"{rg}:invoer:{n}")
            g.add((rg, WA.invoer, node))
            g.add((node, RDF.type, WA.Invoer))
            g.add((node, WA.begrip, begrip_iri(inv["begrip_id"])))
            g.add((node, WA.rol, Literal(inv.get("rol", "invoer"))))
            g.add((node, WA.volgorde, Literal(n)))
        teksten = {gv["label"]: gv["tekst"] for gv in x["regeltekst"].get("gevallen", [])}
        for n, gv in enumerate(i.get("gevallen", []), start=1):
            gi = geval_iri(rid, n)
            g.add((rg, WA.geval, gi))
            g.add((gi, RDF.type, WA.Geval))
            g.add((gi, WA.volgorde, Literal(n)))
            g.add((gi, WA.voorrang, Literal(int(gv.get("voorrang", 0) or 0))))
            if gv.get("label"):
                g.add((gi, WA.label, Literal(gv["label"])))
            if teksten.get(gv.get("label", "")):
                g.add((gi, WA.regeltekst, _nl(teksten[gv.get("label", "")])))
            for t in gv.get("uitkomst", []):
                if t.get("begrip_id"):
                    g.add((gi, WA.gebruiktBegrip, begrip_iri(t["begrip_id"])))
            if gv.get("voorwaarden"):
                g.add((gi, WA.voorwaarden, _voorwaarde(g, URIRef(f"{gi}:voorwaarde:1"), gv["voorwaarden"], doel)))
        per_label = {gv.get("label", ""): geval_iri(rid, n) for n, gv in enumerate(i.get("gevallen", []), start=1)}
        enkel = geval_iri(rid, 1) if len(per_label) == 1 else None
        # De voorbeelden: invoer per invoerbegrip, het gekozen geval en de verwachte uitkomst, met het oordeel.
        for n, v in enumerate(i.get("voorbeelden", []), start=1):
            vb = URIRef(f"{rg}:voorbeeld:{n}")
            g.add((rg, WA.voorbeeld, vb))
            g.add((vb, RDF.type, WA.Voorbeeld))
            g.add((vb, WA.volgorde, Literal(n)))
            g.add((vb, WA.voorbeeldInvoer, _nl(v.get("invoer", ""))))
            g.add((vb, WA.verwachteUitkomst, _nl(v.get("uitkomst", ""))))
            g.add((vb, WA.oordeel, Literal(v.get("oordeel", "open"))))
            if (gi := per_label.get(v.get("geval") or "") or enkel) is not None:
                g.add((vb, WA.inGeval, gi))
            for m, w in enumerate(v.get("waarden") or [], start=1):
                wn = URIRef(f"{vb}:waarde:{m}")
                g.add((vb, WA.waarde, wn))
                g.add((wn, WA.begrip, begrip_iri(w["begrip_id"])))
                g.add((wn, WA.waarde, Literal(w["waarde"])))
            for geval in v.get("van_geval") or []:
                # Niet `x`: dat is de regel van de buitenste lus, en die is hieronder nog nodig voor de dragers.
                g.add((vb, WA.gevalVan, doel(geval)))
        for d in x["dragers"]:
            dn = URIRef(f"urn:wa:regeldrager:{d['id']}")
            g.add((rg, WA.drager, dn))
            g.add((dn, RDF.type, WA.Regeldrager))
            g.add((dn, WA.rol, Literal(d["rol"])))
            g.add((dn, WA.beoordeling, Literal(d["beoordeling"])))
            g.add((dn, WA.element, element_iri(d["element_id"])))
            g.add((dn, WA.elementHash, Literal(d["element_hash"])))
            if d["tekst"]:
                g.add((dn, WA.passage, Literal(d["tekst"])))
            if d["geval"] and d["geval"] in per_label:
                g.add((dn, WA.inGeval, per_label[d["geval"]]))
            for bron in d["bron"]:
                g.add((dn, WA.bron, URIRef(bron)))
            if d["beoordeling"] != "afgewezen" and d["rol"] in DRAGEND:
                g.add((rg, WA.rustOp, element_iri(d["element_id"])))
                if d["rol"] == "grondslag":
                    for bron in d["bron"]:
                        g.add((rg, PROV.wasDerivedFrom, URIRef(bron)))


def _voorwaarde(g: Graph, node: URIRef, v: dict, doel) -> URIRef:
    if "delen" in v:
        g.add((node, RDF.type, WA.Voorwaardengroep))
        g.add((node, WA.verband, Literal(v.get("verband", "alle"))))
        for n, deel in enumerate(v["delen"], start=1):
            kind = _voorwaarde(g, URIRef(f"{node}.{n}"), deel, doel)
            g.add((node, WA.deel, kind))
            g.add((kind, WA.volgorde, Literal(n)))
        return node
    g.add((node, RDF.type, WA.Voorwaarde))
    g.add((node, WA.tekst, _nl(v["tekst"])))
    if v.get("niet"):
        g.add((node, WA.niet, Literal(True)))
    for e in v.get("element_ids") or []:
        g.add((node, WA.rustOp, element_iri(e)))
    if v.get("geval_van"):
        g.add((node, WA.gevalVan, doel(v["geval_van"])))
    return node


# --- conformiteit (diagnostisch) ------------------------------------------------------------------

@cache
def _shapes() -> Graph:
    return Graph().parse(SHAPES, format="turtle")


def conformiteit(g: Graph) -> dict[str, Any]:
    """Per regel: conform de eigen shapes (geen Violation op de regel, een geval of een drager) en de meldingen.
    Zonder pyshacl `beschikbaar: False` en `conform: None`, nooit "conform"."""
    regels = sorted(str(r) for r in g.subjects(RDF.type, WA.Afleidingsregel))
    try:
        from pyshacl import validate
    except ImportError:
        return {"beschikbaar": False, "regels": {r: {"conform": None, "meldingen": []} for r in regels}}
    uit = {r: {"conform": True, "meldingen": []} for r in regels}
    _c, rapport, _ = validate(g, shacl_graph=_shapes(), advanced=True, inference="none")
    for res in rapport.subjects(RDF.type, SH.ValidationResult):
        focus = str(rapport.value(res, SH.focusNode))
        regel = next((r for r in regels if focus == r or focus.startswith(r + ":")), None)
        if regel is None:
            regel = next((str(s) for s in g.subjects(WA.drager, URIRef(focus))), None)
        if regel is None:
            continue
        ernst = "fout" if rapport.value(res, SH.resultSeverity) == SH.Violation else "waarschuwing"
        uit[regel]["meldingen"].append({"ernst": ernst, "pad": str(rapport.value(res, SH.resultPath) or ""),
                                        "melding": str(rapport.value(res, SH.resultMessage) or "")})
        if ernst == "fout":
            uit[regel]["conform"] = False
    for v in uit.values():
        v["meldingen"].sort(key=lambda m: (m["ernst"], m["pad"], m["melding"]))
    return {"beschikbaar": True, "regels": uit}


#: De rooktest op de herleidbaarheid in de graaf (graafcontrole): per geprojecteerde regel of elke markering waarop hij
#: rust in een JAS-laag staat met een bronnode die tekst en een weg naar de wettekst (jci of anker) heeft. Een regel
#: zonder grondslag in de graaf telt ook.
NIET_HERLEIDBAAR = """PREFIX wa: <urn:wa-ns:> PREFIX oa: <http://www.w3.org/ns/oa#> PREFIX bwb: <urn:bwb-ns:>
SELECT ?regel ?el WHERE {
  GRAPH ?w { ?regel a wa:Afleidingsregel . OPTIONAL { ?regel wa:rustOp ?el } }
  FILTER(STRSTARTS(STR(?w), "urn:wa:graph:werkgebied:"))
  FILTER(!BOUND(?el) || NOT EXISTS {
    GRAPH ?j { ?el oa:hasTarget/oa:hasSource ?bron } FILTER(STRSTARTS(STR(?j), "urn:jas:graph:"))
    GRAPH ?b { ?bron bwb:tekst ?tekst . { ?bron bwb:jci ?jci } UNION { ?bron bwb:bronUrl ?url } }
    FILTER(STRSTARTS(STR(?b), "urn:bwb:graph:")) })
} LIMIT 201"""
#: Zoveel rijen toont de rooktest; de query vraagt er één meer, zodat `regels_niet_herleidbaar_volledig` kan zeggen of
#: de lijst afgekapt is (review regelstapel 20 nov 2026, bevinding 11: tel nooit een begrensde lijst als totaal).
MAX_NIET_HERLEIDBAAR = 200
