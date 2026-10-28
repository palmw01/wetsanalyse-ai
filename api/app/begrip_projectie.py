"""Begrippen naar de kennisgraaf: NL-SBB-projectie, conformiteit en Turtle-export (spoor D, fase F3).

Per werkgebied één named graph `urn:wa:graph:werkgebied:<id>`: het begrippenkader als
`skos:ConceptScheme`, elk begrip als `skos:Concept` volgens NL-SBB 1.0.0 (ADR-003), plus eigen predicaten
onder `urn:wa-ns:` voor wat NL-SBB niet kent – status, revisie, herkomst van de definitie,
de koppelingen met hun bewijsstand en de begripsrelaties met hun juridische type.

- **Postgres is de waarheid, de graaf een herbouwbare projectie** – net als de JAS-lagen
  (`graaf_projectie_v2`). `invoer` leest alles wat de graaf nodig heeft; `bouw_graaf` is zuiver.
  Dezelfde invoer geeft dezelfde graph, en `invoer_hash` is de stand die het register draagt.
- **Direct na de commit, de lus als vangnet.** Elke audited werkgebiedmutatie noteert het werkgebied
  op de verbinding (`werkgebied_store._audit` → `db.noteer_na_commit`); na de commit projecteert
  `na_mutatie` op de achtergrond. `reconcile` vergelijkt de hash in het register met Postgres, dus ook
  een lege GraphDB na een herstart wordt weer gevuld, en ruimt graphs van gearchiveerde of lege
  werkgebieden op. Twee projectoren tegelijk kunnen in de verkeerde volgorde schrijven; de volgende
  ronde ziet dan een afwijkende hash en herstelt het.
- **Alle begrippen met hun status** (besloten 16 okt 2026): concept, geaccordeerd en vervangen. De
  export neemt standaard alleen de geaccordeerde (`alleen_geaccordeerd`).
- **Begrippen zijn analyse-uitkomsten, geen wettelijke definities** – het kader zegt dat zelf.
- **Geen personen** in de graaf (geen authenticatie op GraphDB); wie iets deed staat in Postgres.
- **De wettekst blijft schoon**: geen subject onder `urn:bwb:`. Een bronnode is alleen object
  (`wa:bron`).
- **Relaties houden hun type** (ADR-003): `wa:kwalificeert`, `wa:omvat`, `wa:omvatNiet`, `wa:heeftSoort`,
  `wa:verwantMet`, plus een `wa:Begripsrelatie` met herkomst en toelichting. Alleen een hiërarchie heeft
  daarnaast een SKOS-tegenhanger (`isothes:broaderGeneric`, precies genus–soort); opvolging is
  `dct:isReplacedBy`/`dct:replaces`.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from functools import cache
from pathlib import Path
from typing import Any

import httpx
from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from sqlalchemy import select

from . import db
from .config import get_settings
from .graaf_projectie_v2 import _lit, _repo, _select, element_iri

logger = logging.getLogger(__name__)

WA = Namespace("urn:wa-ns:")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
DCT = Namespace("http://purl.org/dc/terms/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
PROV = Namespace("http://www.w3.org/ns/prov#")
ISOTHES = Namespace("http://purl.org/iso25964/skos-thes#")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")
SH = Namespace("http://www.w3.org/ns/shacl#")

SCHEMA_VERSIE = 1
REGISTER = URIRef("urn:wa:graph:register:begrippen")
NL_SBB_VERSIE = "1.0.0"
NL_SBB = URIRef("https://docs.geostandaarden.nl/nl-sbb/def-st-nl-sbb-20241010/")
SHAPES = Path(__file__).parent / "shapes"
TOELICHTING = "Begrippen zijn analyse-uitkomsten van dit werkgebied, geen wettelijke definities."

# type → (predicaat van → naar). De richting volgt de opslag (fase F2): bij `hierarchie` is `van` de
# bredere term en `naar` de soort ("naar is een soort van").
RELATIE_PREDICAAT = {"kwalificatie": WA.kwalificeert, "inclusie": WA.omvat, "uitsluiting": WA.omvatNiet,
                     "hierarchie": WA.heeftSoort, "verwant": WA.verwantMet}
DRAGEND = {"duiding", "definitie"}
_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")

_actief = False
_taken: set[asyncio.Task] = set()
_locks: dict[str, asyncio.Lock] = {}
_geschreven: dict[str, str | None] = {}     # wat dit proces het laatst schreef (hash of weg)


def graph_iri(werkgebied_id: str) -> URIRef:
    return URIRef("urn:wa:graph:werkgebied:" + werkgebied_id)


def kader_iri(werkgebied_id: str) -> URIRef:
    return URIRef(f"urn:wa:kader:{werkgebied_id}")


def begrip_iri(begrip_id: str) -> URIRef:
    return URIRef(f"urn:wa:begrip:{begrip_id}")


# --- invoer uit Postgres -----------------------------------------------------------------------

def _t(waarde) -> str | None:
    return db.aware(waarde).isoformat() if waarde else None


async def invoer(conn, werkgebied_id: str) -> dict | None:
    """Alles wat de graph van dit werkgebied draagt, als JSON-vorm. None = geen graph: het werkgebied
    bestaat niet, is gearchiveerd of heeft geen begrippen."""
    w, b, k, r = db.werkgebieden, db.begrippen, db.begrip_koppelingen, db.begrip_relaties
    wg = (await conn.execute(select(w).where(w.c.id == werkgebied_id))).first()
    if wg is None or wg.gearchiveerd is not None:
        return None
    begrippen = (await conn.execute(select(b).where(b.c.werkgebied_id == werkgebied_id, b.c.verwijderd.is_(None))
                                    .order_by(b.c.id))).all()
    if not begrippen:
        return None
    koppelingen = (await conn.execute(select(k).where(k.c.werkgebied_id == werkgebied_id, k.c.verwijderd.is_(None))
                                      .order_by(k.c.id))).all()
    relaties = (await conn.execute(select(r).where(r.c.werkgebied_id == werkgebied_id, r.c.verwijderd.is_(None),
                                                   r.c.beoordeling == "akkoord").order_by(r.c.id))).all()
    from .begrip_store import definitie_onderbouwing      # begrip_store schrijft; de projectie leest alleen
    onderbouwing = {}
    for x in begrippen:
        o = await definitie_onderbouwing(conn, x.id, x.inhoud)
        iris = sorted({f["bron_iri"] for f in (o or {}).get("fragmenten") or []}
                      | ({o["definitie_bron_iri"]} if o and o.get("definitie_bron_iri") else set()))
        if iris:
            onderbouwing[x.id] = iris
    per_begrip: dict[str, list[dict]] = {}
    for x in koppelingen:
        bewijs = x.bewijs or {}
        ankers = bewijs.get("ankers") or []
        per_begrip.setdefault(x.begrip_id, []).append({
            "id": x.id, "element_id": x.element_id, "rol": x.rol, "beoordeling": x.beoordeling,
            "element_hash": (x.bevestigingen or [{}])[-1].get("element_hash") or bewijs.get("element_hash", ""),
            "vindplaats": bewijs.get("vindplaats", ""), "tekst": bewijs.get("tekst", ""),
            "bron": sorted({a["bron_iri"] for a in ankers if a.get("bron_iri")}) or
                    ([bewijs["eigenaar_iri"]] if bewijs.get("eigenaar_iri") else [])})
    return {
        "schema": SCHEMA_VERSIE,
        "werkgebied": {"id": wg.id, "naam": wg.naam, "analysevraag": wg.analysevraag or "", "thema": wg.thema or ""},
        "begrippen": [{"id": x.id, "status": x.status, "revisie": x.revisie, "inhoud": x.inhoud,
                       "geaccordeerd_op": _t(x.geaccordeerd_op), "geaccordeerd_revisie": x.geaccordeerd_revisie,
                       "gewijzigd": _t(x.gewijzigd), "koppelingen": per_begrip.get(x.id, []),
                       # Spoor M: de bronnen waarop de overgenomen definitie rust (alleen als die er zijn,
                       # zodat de hash van een werkgebied zonder zulke definitie gelijk blijft).
                       **({"onderbouwing": onderbouwing[x.id]} if x.id in onderbouwing else {})}
                      for x in begrippen],
        "relaties": [{"id": x.id, "van": x.van_begrip, "naar": x.naar_begrip, "type": x.type,
                      "herkomst": x.herkomst, "toelichting": x.toelichting or ""} for x in relaties],
    }


def invoer_hash(inv: dict) -> str:
    return hashlib.sha256(json.dumps(inv, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:32]


# --- de graph ----------------------------------------------------------------------------------

def _nl(tekst: str) -> Literal:
    return Literal(tekst, lang="nl")


def alleen_geaccordeerd(inv: dict) -> dict:
    """De exportstand: alleen geaccordeerde begrippen, en relaties waarvan beide kanten meegaan."""
    ids = {b["id"] for b in inv["begrippen"] if b["status"] == "geaccordeerd"}
    return {**inv, "begrippen": [b for b in inv["begrippen"] if b["id"] in ids],
            "relaties": [r for r in inv["relaties"] if r["van"] in ids and r["naar"] in ids]}


def bouw_graaf(inv: dict, paginas: dict[str, str] | None = None, uitgevers: dict[str, str] | None = None) -> Graph:
    """De named graph van één werkgebied. `paginas` (bron-IRI → URL op wetten.overheid.nl) en `uitgevers`
    (bron-IRI → TOOI-organisatie, spoor I6) alleen bij de export: de projectie leunt niet op de brongraaf,
    zodat ze uit Postgres alleen te herbouwen is."""
    g = Graph()
    for prefix, ns in (("skos", SKOS), ("dct", DCT), ("foaf", FOAF), ("wa", WA), ("isothes", ISOTHES)):
        g.bind(prefix, ns)
    wg = inv["werkgebied"]
    kader = kader_iri(wg["id"])
    g.add((kader, RDF.type, SKOS.ConceptScheme))
    g.add((kader, DCT.title, _nl(wg["naam"])))
    if wg["analysevraag"].strip():
        g.add((kader, DCT.description, _nl(wg["analysevraag"])))
    g.add((kader, RDFS.comment, _nl(TOELICHTING)))
    # Spoor I6: het thema van het werkgebied, een TOOI-URI uit tooitop.
    if wg.get("thema"):
        g.add((kader, DCT.subject, URIRef(wg["thema"])))
    g.add((kader, WA.werkgebiedId, Literal(wg["id"])))
    g.add((kader, WA.schemaVersie, Literal(SCHEMA_VERSIE)))
    g.add((kader, WA.projectieHash, Literal(invoer_hash(inv))))
    for b in inv["begrippen"]:
        _begrip(g, kader, b, paginas or {}, uitgevers or {})
    aanwezig = {b["id"] for b in inv["begrippen"]}
    for r in inv["relaties"]:
        if r["van"] not in aanwezig or r["naar"] not in aanwezig:
            continue
        van, naar = begrip_iri(r["van"]), begrip_iri(r["naar"])
        if r["type"] == "opvolging":
            g.add((van, DCT.isReplacedBy, naar))
            g.add((naar, DCT.replaces, van))
        else:
            g.add((van, RELATIE_PREDICAAT[r["type"]], naar))
            if r["type"] == "hierarchie":
                g.add((naar, ISOTHES.broaderGeneric, van))
        n = URIRef("urn:wa:relatie:" + r["id"])
        g.add((n, RDF.type, WA.Begripsrelatie))
        g.add((n, WA.van, van))
        g.add((n, WA.naar, naar))
        g.add((n, WA.type, Literal(r["type"])))
        g.add((n, WA.herkomst, Literal(r["herkomst"])))
        if r["toelichting"]:
            g.add((n, WA.toelichting, _nl(r["toelichting"])))
    return g


def _begrip(g: Graph, kader: URIRef, b: dict, paginas: dict[str, str], uitgevers: dict[str, str]) -> None:
    c, i = begrip_iri(b["id"]), b["inhoud"]
    g.add((c, RDF.type, SKOS.Concept))
    g.add((c, SKOS.inScheme, kader))
    g.add((c, SKOS.prefLabel, _nl(i["naam"])))
    for term in i.get("alternatieve_termen") or []:
        g.add((c, SKOS.altLabel, _nl(term)))
    if (i.get("definitie") or "").strip():
        g.add((c, SKOS.definition, _nl(i["definitie"])))
    if (i.get("uitleg") or "").strip():
        g.add((c, RDFS.comment, _nl(i["uitleg"])))
    if (i.get("context") or "").strip():
        g.add((c, SKOS.scopeNote, _nl(i["context"])))
    # NL-SBB `skos:example` is een voorbeeld van het begrip: alleen *wel*. Een tegenvoorbeeld en een
    # grensgeval toetsen de afbakening; ze gaan mee onder een eigen predicaat, niet als voorbeeld.
    for v in i.get("voorbeelden") or []:
        p = {"wel": SKOS.example, "niet": WA.tegenvoorbeeld, "onzeker": WA.grensgeval}.get(v.get("oordeel"))
        if p is not None:
            g.add((c, p, _nl(v["tekst"])))
    g.add((c, WA.status, Literal(b["status"])))
    g.add((c, WA.revisie, Literal(b["revisie"])))
    for p, k in ((WA.definitieHerkomst, "definitie_herkomst"), (WA.definitieDoor, "definitie_door")):
        if i.get(k):
            g.add((c, p, Literal(i[k])))
    if b["status"] == "geaccordeerd" and b.get("geaccordeerd_op"):
        g.add((c, WA.geaccordeerdOp, Literal(b["geaccordeerd_op"], datatype=XSD.dateTime)))
        g.add((c, WA.geaccordeerdRevisie, Literal(b["geaccordeerd_revisie"])))
    bronnen: set[tuple[str, str]] = set()
    for k in b["koppelingen"]:
        n = URIRef("urn:wa:koppeling:" + k["id"])
        g.add((c, WA.koppeling, n))
        g.add((n, RDF.type, WA.Koppeling))
        g.add((n, WA.rol, Literal(k["rol"])))
        g.add((n, WA.beoordeling, Literal(k["beoordeling"])))
        g.add((n, WA.element, element_iri(k["element_id"])))
        g.add((n, WA.elementHash, Literal(k["element_hash"])))
        if k["tekst"]:
            g.add((n, WA.passage, Literal(k["tekst"])))
        for bron in k["bron"]:
            g.add((n, WA.bron, URIRef(bron)))
            if k["rol"] in DRAGEND and k["beoordeling"] != "afgewezen":
                bronnen.add((bron, k["vindplaats"]))
    # Spoor M: de bronnen waarop de overgenomen definitie rust, ook een contextbron zonder passage. Een
    # bron die alleen onderzocht is maar niet gekozen, wordt geen bron.
    onderbouwing = set(b.get("onderbouwing") or [])
    bronnen |= {(bron, "") for bron in onderbouwing if not any(x == bron for x, _ in bronnen)}
    # NL-SBB: de bron als `dct:source` → brondocument. Eén per bronnode van een dragende passage.
    for bron, vindplaats in sorted(bronnen):
        doc = URIRef("urn:wa:bron:" + hashlib.sha256(f"{b['id']}\x1f{bron}".encode()).hexdigest()[:16])
        if bron in onderbouwing:
            g.add((doc, WA.rol, Literal("definitieonderbouwing")))
        g.add((c, DCT.source, doc))
        g.add((doc, RDF.type, FOAF.Document))
        g.add((doc, WA.bron, URIRef(bron)))
        if vindplaats:
            g.add((doc, RDFS.label, _nl(vindplaats)))
            g.add((doc, DCT.bibliographicCitation, Literal(vindplaats)))
        if paginas.get(bron):
            g.add((doc, FOAF.page, URIRef(paginas[bron])))
        if uitgevers.get(bron):
            g.add((doc, DCT.publisher, URIRef(uitgevers[bron])))


# --- conformiteit ------------------------------------------------------------------------------

@cache
def _shapes() -> tuple[Graph, Graph]:
    return (Graph().parse(SHAPES / f"nl-sbb-{NL_SBB_VERSIE}.ttl", format="turtle"),
            Graph().parse(SHAPES / "begrippen-wa.ttl", format="turtle"))


def _onder(g: Graph, focus) -> URIRef | None:
    """Het begrip waar een bevinding bij hoort: het begrip zelf, of het begrip boven een koppeling of bron."""
    if (focus, RDF.type, SKOS.Concept) in g:
        return focus
    for p in (WA.koppeling, DCT.source):
        for s in g.subjects(p, focus):
            return s
    return None


def conformiteit(g: Graph) -> dict[str, Any]:
    """Per begrip: conform NL-SBB (geen Violation op het begrip of zijn bronnen) en de meldingen, per
    laag (`nl_sbb` / `eigen`). Diagnostisch (ADR-003, besloten 16 okt 2026): accorderen blijft mogelijk.
    Zonder pyshacl `beschikbaar: False` en `conform: None` per begrip – nooit "conform"."""
    begrippen = sorted(str(c) for c in g.subjects(RDF.type, SKOS.Concept))
    try:
        from pyshacl import validate
    except ImportError:
        return {"beschikbaar": False, "nl_sbb_versie": NL_SBB_VERSIE,
                "begrippen": {c: {"conform": None, "meldingen": []} for c in begrippen}, "kader": []}
    uit = {c: {"conform": True, "meldingen": []} for c in begrippen}
    kader: list[dict] = []
    for laag, shapes in zip(("nl_sbb", "eigen"), _shapes()):
        _conform, rapport, _ = validate(g, shacl_graph=shapes, advanced=True, inference="none")
        for r in rapport.subjects(RDF.type, SH.ValidationResult):
            focus = rapport.value(r, SH.focusNode)
            ernst = "fout" if rapport.value(r, SH.resultSeverity) == SH.Violation else "waarschuwing"
            melding = {"laag": laag, "ernst": ernst, "pad": str(rapport.value(r, SH.resultPath) or ""),
                       "melding": str(rapport.value(r, SH.resultMessage) or "")}
            begrip = _onder(g, focus)
            if begrip is None:
                kader.append(melding)
                continue
            uit[str(begrip)]["meldingen"].append(melding)
            if laag == "nl_sbb" and ernst == "fout":
                uit[str(begrip)]["conform"] = False
    for v in uit.values():
        v["meldingen"].sort(key=lambda m: (m["laag"], m["ernst"], m["pad"], m["melding"]))
    return {"beschikbaar": True, "nl_sbb_versie": NL_SBB_VERSIE, "begrippen": uit, "kader": kader}


# --- export ------------------------------------------------------------------------------------

_PAGINA_QUERY = """PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX bwb: <urn:bwb-ns:>
SELECT ?s ?jci ?url WHERE {{ VALUES ?s {{ {waarden} }}
  OPTIONAL {{ GRAPH ?g {{ ?s owl:sameAs ?jci }} FILTER(STRSTARTS(STR(?g), "urn:bwb:graph:")) }}
  OPTIONAL {{ GRAPH ?h {{ ?s bwb:bronUrl ?url }} FILTER(STRSTARTS(STR(?h), "urn:bwb:graph:")) }} }}"""
_BWB_IRI = re.compile(r"urn:bwb:BWB[RV]\d+(?::[^<>\s\"{}|^`\\]*)?")


async def paginas(bronnen: set[str]) -> dict[str, str]:
    """Bron-IRI → de jci op wetten.overheid.nl (anders de vindplaats-URL). Best-effort: zonder graaf
    gaat de export zonder `foaf:page`; de bron-IRI staat er altijd."""
    iris = sorted(i for i in bronnen if _BWB_IRI.fullmatch(i))
    if not iris or not get_settings().graphdb_url:
        return {}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            rijen = await _select(client, _PAGINA_QUERY.format(waarden=" ".join(URIRef(i).n3() for i in iris)))
    except (httpx.HTTPError, ConnectionError, ValueError) as exc:
        logger.warning("begrippen_export_paginas_onbeschikbaar", extra={"fouttype": type(exc).__name__})
        return {}
    uit: dict[str, str] = {}
    for r in rijen:
        url = r.get("jci") or r.get("url")
        if url and (r["s"] not in uit or r.get("jci")):
            uit[r["s"]] = url
    return uit


_UITGEVER_QUERY = """PREFIX bwb: <urn:bwb-ns:>
SELECT ?r ?org WHERE {{ VALUES ?r {{ {waarden} }}
  GRAPH ?g {{ ?r bwb:eerstverantwoordelijkeOrganisatie ?org }} FILTER(STRSTARTS(STR(?g), "urn:bwb:graph:")) }}"""


def _regeling(bron: str) -> str:
    return ":".join(bron.split(":")[:3])


async def uitgevers(bronnen: set[str]) -> dict[str, str]:
    """Bron-IRI → de TOOI-organisatie van haar regeling (`bwb:eerstverantwoordelijkeOrganisatie`, spoor I6),
    voor `dct:publisher` op het brondocument. Best-effort, net als `paginas`."""
    iris = sorted(i for i in bronnen if _BWB_IRI.fullmatch(i))
    regelingen = sorted({_regeling(i) for i in iris})
    if not regelingen or not get_settings().graphdb_url:
        return {}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            rijen = await _select(client, _UITGEVER_QUERY.format(waarden=" ".join(URIRef(r).n3() for r in regelingen)))
    except (httpx.HTTPError, ConnectionError, ValueError) as exc:
        logger.warning("begrippen_export_uitgevers_onbeschikbaar", extra={"fouttype": type(exc).__name__})
        return {}
    per = {r["r"]: r["org"] for r in rijen if r.get("org", "").startswith("https://identifier.overheid.nl/tooi/")}
    return {i: per[_regeling(i)] for i in iris if _regeling(i) in per}


async def export_turtle(werkgebied_id: str, alles: bool) -> bytes:
    """De Turtle-export: dezelfde `bouw_graaf` als de projectie (standaard alleen geaccordeerd), met
    `foaf:page` naar de wettekst, de NL-SBB-versie en per begrip `wa:nlSbbConform`."""
    from fastapi import HTTPException

    async with db.get_engine().connect() as conn:
        w = db.werkgebieden
        wg = (await conn.execute(select(w).where(w.c.id == werkgebied_id))).first()
        if wg is None or wg.gearchiveerd is not None:
            raise HTTPException(404, "Werkgebied bestaat niet.")
        inv = await invoer(conn, werkgebied_id) or {
            "schema": SCHEMA_VERSIE, "werkgebied": {"id": wg.id, "naam": wg.naam, "analysevraag": wg.analysevraag or "",
                                                    "thema": wg.thema or ""},
            "begrippen": [], "relaties": []}
    if not alles:
        inv = alleen_geaccordeerd(inv)
    bronnen = {bron for b in inv["begrippen"] for k in b["koppelingen"] for bron in k["bron"]} \
        | {bron for b in inv["begrippen"] for bron in b.get("onderbouwing") or []}
    pag, uitg = await paginas(bronnen), await uitgevers(bronnen)
    nu = db.utcnow().isoformat()

    def bouw() -> bytes:
        g = bouw_graaf(inv, pag, uitg)
        kader = kader_iri(werkgebied_id)
        g.add((kader, DCT.conformsTo, NL_SBB))
        g.add((kader, WA.nlSbbVersie, Literal(NL_SBB_VERSIE)))
        g.add((kader, WA.exportOmvang, Literal("alle" if alles else "geaccordeerd")))
        g.add((kader, PROV.generatedAtTime, Literal(nu, datatype=XSD.dateTime)))
        c = conformiteit(g)
        for iri, stand in c["begrippen"].items():
            if stand["conform"] is not None:
                g.add((URIRef(iri), WA.nlSbbConform, Literal(stand["conform"])))
        g.bind("prov", PROV)
        return g.serialize(format="turtle").encode("utf-8")

    # rdflib en SHACL zijn pure Python: in een thread, zodat de event loop van de api vrij blijft.
    return await asyncio.to_thread(bouw)


async def conformiteit_van(werkgebied_id: str) -> dict[str, Any]:
    """De diagnose voor de werkplek: per begrip-id `{conform, meldingen}` over de projectiestand."""
    async with db.get_engine().connect() as conn:
        inv = await invoer(conn, werkgebied_id)
    if inv is None:
        return {"beschikbaar": True, "nl_sbb_versie": NL_SBB_VERSIE, "begrippen": {}, "kader": []}
    c = await asyncio.to_thread(lambda: conformiteit(bouw_graaf(inv)))
    prefix = str(begrip_iri(""))
    return {**c, "begrippen": {iri[len(prefix):]: v for iri, v in c["begrippen"].items()}}


# --- projectie ---------------------------------------------------------------------------------

def _register_statement(werkgebied_id: str, hash_: str | None) -> str:
    k = kader_iri(werkgebied_id).n3()
    weg = f"DELETE WHERE {{ GRAPH <{REGISTER}> {{ {k} ?p ?o }} }}"
    if hash_ is None:
        return f"DROP SILENT GRAPH {graph_iri(werkgebied_id).n3()};\n{weg}"
    return (f"{weg};\nINSERT DATA {{ GRAPH <{REGISTER}> {{ {k} <{WA.inGraaf}> {graph_iri(werkgebied_id).n3()} ; "
            f"<{WA.werkgebiedId}> {_lit(werkgebied_id)} ; <{WA.projectieHash}> {_lit(hash_)} ; "
            f"<{WA.schemaVersie}> {SCHEMA_VERSIE} }} }}")


async def projecteer(werkgebied_id: str, zeker: bool = False) -> str:
    """Zet de graph van één werkgebied neer, of haalt hem weg als er niets (meer) te projecteren is.
    `geschreven` | `verwijderd` | `ongewijzigd`. Het leesslot op het werkgebied wacht een lopende
    schrijftransactie af, zodat een projectie direct na de commit de nieuwe stand leest.

    Zonder `zeker` slaat hij over wat dit proces al zo schreef (een mutatie die de graph niet raakt, zoals
    een ander werkgebiedveld of een dekkingsbesluit); `reconcile` schrijft altijd, want hij kijkt naar de
    graaf zelf."""
    async with _locks.setdefault(werkgebied_id, asyncio.Lock()):
        async with db.get_engine().begin() as conn:
            w = db.werkgebieden
            await conn.execute(select(w.c.id).where(w.c.id == werkgebied_id).with_for_update(read=True))
            inv = await invoer(conn, werkgebied_id)
        stand = invoer_hash(inv) if inv is not None else None
        if not zeker and werkgebied_id in _geschreven and _geschreven[werkgebied_id] == stand:
            return "ongewijzigd"
        async with httpx.AsyncClient(timeout=30) as client:
            if inv is None:
                r = await client.post(_repo() + "/statements", data={"update": _register_statement(werkgebied_id, None)})
                r.raise_for_status()
                _geschreven[werkgebied_id] = None
                return "verwijderd"
            data = await asyncio.to_thread(lambda: bouw_graaf(inv).serialize(format="turtle").encode())
            r = await client.put(_repo() + "/rdf-graphs/service", params={"graph": str(graph_iri(werkgebied_id))},
                                 content=data, headers={"Content-Type": "text/turtle"})
            r.raise_for_status()
            r = await client.post(_repo() + "/statements", data={"update": _register_statement(werkgebied_id, stand)})
            r.raise_for_status()
            _geschreven[werkgebied_id] = stand
    return "geschreven"


_REGISTER_QUERY = f"""SELECT ?id ?hash ?g WHERE {{ GRAPH <{REGISTER}> {{
  ?k <{WA.werkgebiedId}> ?id ; <{WA.projectieHash}> ?hash ; <{WA.inGraaf}> ?g ; <{WA.schemaVersie}> {SCHEMA_VERSIE} }} }}"""
# Welke werkgebied-graphs er echt staan: via het kader in de graph zelf (een predicaatindex, geen scan
# over alle graphs), zodat een verloren graph met een blijvende registerregel ook opvalt.
_GRAPHS_QUERY = f"""SELECT DISTINCT ?g WHERE {{ GRAPH ?g {{ ?k <{WA.werkgebiedId}> ?id }}
  FILTER(STRSTARTS(STR(?g), "urn:wa:graph:werkgebied:")) }}"""


async def register() -> dict[str, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        return {r["id"]: r for r in await _select(client, _REGISTER_QUERY)}


async def postgres_stand() -> dict[str, dict]:
    """Per werkgebied met iets te projecteren: de invoer."""
    async with db.get_engine().connect() as conn:
        ids = sorted(set((await conn.execute(select(db.begrippen.c.werkgebied_id).where(
            db.begrippen.c.verwijderd.is_(None)))).scalars()))
        uit = {}
        for wid in ids:
            inv = await invoer(conn, wid)
            if inv is not None:
                uit[wid] = inv
    return uit


async def reconcile() -> int:
    """Projecteer wat afwijkt van het register, en ruim graphs op van werkgebieden zonder begrippen."""
    stand, reg = await postgres_stand(), await register()
    async with httpx.AsyncClient(timeout=20) as client:
        graphs = {r["g"] for r in await _select(client, _GRAPHS_QUERY)}
    teller = 0
    for wid, inv in stand.items():
        if reg.get(wid, {}).get("hash") != invoer_hash(inv) or str(graph_iri(wid)) not in graphs:
            await projecteer(wid, zeker=True)
            teller += 1
    prefix = str(graph_iri(""))
    wees = set(reg) | {g[len(prefix):] for g in graphs}
    for wid in sorted(wees - set(stand)):
        if _ID.fullmatch(wid):          # nooit een willekeurige graaf uit registergegevens wissen
            await projecteer(wid, zeker=True)
            teller += 1
    if teller:
        logger.info("begrippen_geprojecteerd", extra={"aantal": teller})
    return teller


def activeer(aan: bool) -> None:
    global _actief
    _actief = aan
    if aan:
        db.na_commit_haak("werkgebieden", na_mutatie)


async def stop() -> None:
    activeer(False)
    for taak in list(_taken):
        taak.cancel()
    await asyncio.gather(*_taken, return_exceptions=True)


def na_mutatie(werkgebied_ids) -> None:
    """Best-effort, op de achtergrond. Een haperende GraphDB laat een besluit nooit falen; de lus haalt in."""
    if not _actief:
        return

    async def _doe(wid: str):
        try:
            await projecteer(wid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("begrippen_projectie_uitgesteld", extra={"werkgebied_id": wid, "fouttype": type(exc).__name__})

    try:
        lus = asyncio.get_running_loop()
    except RuntimeError:
        return
    for wid in sorted(set(werkgebied_ids)):
        taak = lus.create_task(_doe(wid))
        _taken.add(taak)
        taak.add_done_callback(_taken.discard)

