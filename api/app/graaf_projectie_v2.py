"""Bronnode-projectie en echte, getypeerde SPARQL-zoekopdrachten.

Elke graph draagt zelf de DB-revisie; register én graph moeten overeenkomen.
Een zoekfout is nooit een lege annotatielaag. De API verifieert de kandidaten en
het volledige manifest tegen PostgreSQL voordat zij volledigheid claimt.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef
from sqlalchemy import select, update

from . import db
from .config import get_settings

JAS = Namespace("urn:jas-ns:")
OA = Namespace("http://www.w3.org/ns/oa#")
PROV = Namespace("http://www.w3.org/ns/prov#")
REGISTER = URIRef("urn:jas:graph:register:v2")
SCHEMA = URIRef("urn:jas:projectieschema:v2")
logger = logging.getLogger(__name__)
_locks: dict[str, asyncio.Lock] = {}
# Directe projectie na een commit, zoals v1 (`graaf_projectie.na_mutatie`): alleen aan als de lus
# draait (GRAPHDB_URL gezet). De taken houden we vast, anders ruimt de garbage collector ze op.
_actief = False
_taken: set[asyncio.Task] = set()


VOCABULAIRE = URIRef("urn:jas:graph:vocabulaire")
VOCABULAIRE_TTL = Path(__file__).parent / "vocabulaire" / "jas-vocabulaire.ttl"
VOCABULAIRE_JSON = Path(__file__).parent / "vocabulaire" / "verklaringen.json"
VOCAB_SCHEMA = URIRef("urn:jas-ns:schema:jas-1.0.10")


def klasse_iri(naam: str) -> URIRef:
    """`Delegatiebevoegdheid en delegatie-invulling` → `urn:jas-ns:klasse:DelegatiebevoegdheidEnDelegatieInvulling`.

    Zelfde regel als `tools/graph-qa/scripts/genereer_jas_vocabulaire.slug`; `test_vocabulaire.py`
    bewaakt dat elke klasse van de api zo een concept in de vocabulaire vindt."""
    return URIRef("urn:jas-ns:klasse:" + "".join(d[:1].upper() + d[1:] for d in re.split(r"[\s\-]+", naam.strip()) if d))


@lru_cache(maxsize=1)
def vocabulaire() -> tuple[str, str]:
    """(versie, turtle) van de gegenereerde vocabulaire."""
    ttl = VOCABULAIRE_TTL.read_text(encoding="utf-8")
    versie = json.loads(VOCABULAIRE_JSON.read_text(encoding="utf-8"))["vocabulaire_versie"]
    return versie, ttl


@lru_cache(maxsize=1)
def verklaringen() -> dict:
    return json.loads(VOCABULAIRE_JSON.read_text(encoding="utf-8"))


async def zorg_voor_vocabulaire(client: httpx.AsyncClient) -> bool:
    """Zet de vocabulairegraaf neer als hij ontbreekt of een andere versie draagt. True = geschreven.

    De graaf is niet-persistent; na een herstart bouwt de reconcile-lus hem zo opnieuw op, net als de lagen."""
    versie, ttl = vocabulaire()
    r = await client.post(_repo(), data={"query": f'ASK {{ GRAPH <{VOCABULAIRE}> {{ <{VOCAB_SCHEMA}> '
                                                  f'<{JAS.vocabulaireVersie}> {_lit(versie)} }} }}'},
                          headers={"Accept": "application/sparql-results+json"})
    r.raise_for_status()
    if r.json().get("boolean"):
        return False
    r = await client.put(_repo() + "/rdf-graphs/service", params={"graph": str(VOCABULAIRE)},
                         content=ttl.encode("utf-8"), headers={"Content-Type": "text/turtle"})
    r.raise_for_status()
    logger.info("annotatie_vocabulaire_geprojecteerd", extra={"versie": versie})
    return True


def graph_iri(laag_id: str) -> URIRef:
    from urllib.parse import quote
    return URIRef("urn:jas:graph:v2:" + quote(laag_id, safe=""))


def laag_iri(laag_id: str) -> URIRef:
    from urllib.parse import quote
    return URIRef("urn:jas:laag:v2:" + quote(laag_id, safe=""))


def element_iri(element_id: str) -> URIRef:
    from urllib.parse import quote
    return URIRef("urn:jas:element:" + quote(element_id, safe=""))


def bouw_graaf(laag: dict, elementen: list[dict], prov: bool = False) -> Graph:
    g = Graph()
    owner = laag_iri(laag["id"])
    g.add((owner, RDF.type, JAS.AnnotatieLaag))
    for p, v in ((JAS.laagId, laag["id"]), (JAS.revisie, laag["revisie"]),
                 (JAS.status, laag["status"]), (JAS.schemaVersie, 2)):
        g.add((owner, p, Literal(v)))
    g.add((owner, JAS.bepaling, URIRef(laag["bron_iri"])))
    for element in elementen:
        e = element_iri(element["id"])
        g.add((e, RDF.type, JAS.Markering))
        g.add((e, JAS.inLaag, owner))
        for p, value in ((JAS.elementId, element["id"]), (JAS.klasseNaam, element["klasse"]),
                         (JAS.lifecycle, element.get("lifecycle", "")),
                         (JAS.verouderd, bool(element.get("verouderd", False))),
                         (JAS.tekst, element.get("tekst", "")),
                         (JAS.toelichting, element.get("toelichting", ""))):
            g.add((e, p, Literal(value)))
        body = BNode()
        g.add((e, OA.hasBody, body))
        g.add((body, RDF.type, OA.TextualBody))
        g.add((body, RDF.value, Literal(element.get("toelichting", ""))))
        for index, anker in enumerate(element.get("ankers", [])):
            target, position, quote = BNode(), BNode(), BNode()
            g.add((e, OA.hasTarget, target))
            g.add((target, RDF.type, OA.SpecificResource))
            g.add((target, OA.hasSource, URIRef(anker["bron_iri"])))
            g.add((target, JAS.volgorde, Literal(index)))
            g.add((target, JAS.bronHash, Literal(anker["bron_hash"])))
            g.add((target, JAS.snapshotId, Literal(element.get("snapshot_id", ""))))
            g.add((target, OA.hasSelector, position))
            g.add((position, RDF.type, OA.TextPositionSelector))
            g.add((position, OA.start, Literal(anker["start"])))
            g.add((position, OA.end, Literal(anker["eind"])))
            g.add((target, OA.hasSelector, quote))
            g.add((quote, RDF.type, OA.TextQuoteSelector))
            g.add((quote, OA.exact, Literal(anker["tekst"])))
        if prov and element.get("trace"):
            _prov(g, e, element["trace"])
    return g


def _prov(g: Graph, e: URIRef, spoor: dict) -> None:
    """Herkomst als PROV-O: welke pijplijn en wie besliste (regel, model, specificiteit).

    Bewust zonder personen – de graaf heeft geen authenticatie, dus beslissingen van juristen
    blijven in Postgres – en zonder domain/range (invariant 3). Modelherkomst is geen juridische
    autoriteit; het zegt alleen hoe het voorstel ontstond.
    """
    beslissing = spoor.get("beslissing") or {}
    activiteit = BNode()
    g.add((e, PROV.wasGeneratedBy, activiteit))
    g.add((activiteit, RDF.type, PROV.Activity))
    g.add((activiteit, PROV.wasAssociatedWith, URIRef("urn:jas:agent:pijplijn:" + str(spoor.get("pijplijn", "onbekend")))))
    g.add((activiteit, JAS.beslistDoor, Literal(str(beslissing.get("door", "")))))
    g.add((activiteit, JAS.jasVersie, Literal(str(spoor.get("jas_versie", "")))))
    for regel in sorted({b.get("regel", "") for b in (spoor.get("kandidaat") or {}).get("bewijs", []) if b.get("regel")}):
        g.add((activiteit, JAS.regel, Literal(regel)))


def _lit(value: Any) -> str:
    # JSON escaping is the SPARQL string-literal subset; never executable query input.
    return json.dumps(str(value), ensure_ascii=False)


def zoek_query(filters: dict, limit: int = 10001) -> str:
    clauses = []
    if "scoped_nodes" in filters:
        iris = filters["scoped_nodes"]
        if not all(re.fullmatch(r"urn:bwb:(BWB[RV]\d+)(?::[^<>\s\"{}|^`\\]*)?", str(i)) for i in iris):
            raise ValueError("Ongeldige bronscope")
        values = " ".join(URIRef(i).n3() for i in iris)
        clauses.append(f"FILTER EXISTS {{ VALUES ?geraakt {{ {values} }} ?e oa:hasTarget/oa:hasSource ?geraakt }}")
    source = filters.get("bronnode_id") or filters.get("bron_iri")
    if source:
        match = re.fullmatch(r"urn:bwb:(BWB[RV]\d+)(?::[^<>\s\"{}|^`\\]*)?", str(source))
        if not match:
            raise ValueError("Ongeldige bronnode")
        if filters.get("scope", "subtree") == "node":
            clauses.append(f"FILTER EXISTS {{ ?e oa:hasTarget/oa:hasSource <{source}> }}")
        else:
            from bronmodel import PAD
            clauses.append(f"FILTER EXISTS {{ ?e oa:hasTarget/oa:hasSource ?bron . "
                           f"GRAPH <urn:bwb:graph:{match.group(1)}> {{ <{source}> {PAD}* ?bron }} }}")
    elif filters.get("bwb_id"):
        bwb = str(filters["bwb_id"])
        if not re.fullmatch(r"BWB[RV]\d+", bwb):
            raise ValueError("Ongeldige regeling")
        clauses.append("FILTER EXISTS { ?e oa:hasTarget/oa:hasSource ?bron . FILTER("
                       f"STR(?bron) = {_lit('urn:bwb:' + bwb)} || STRSTARTS(STR(?bron), {_lit('urn:bwb:' + bwb + ':')})"
                       ") }")
    for key, var in (("jas_klassen", "klasse"), ("lifecycle", "lifecycle"),
                     ("laagstatus", "laagstatus")):
        values = filters.get(key) or []
        if values:
            clauses.append(f"FILTER(?{var} IN ({', '.join(_lit(v) for v in values)}))")
    if not filters.get("inclusief_verouderd", False):
        clauses.append("FILTER(?verouderd = false)")
    if not filters.get("lifecycle"):
        clauses.append('FILTER(?lifecycle != "rejected")')
    text = filters.get("tekst") or filters.get("query")
    if text:
        field = filters.get("tekstveld", "beide")
        variables = ["tekst", "toelichting"] if field == "beide" else ["tekst" if field == "citaat" else "toelichting"]
        if filters.get("match", "bevat") == "exact":
            expressions = [f"STR(?{v}) = {_lit(text)}" for v in variables]
        else:
            expressions = [f"CONTAINS(LCASE(STR(?{v})), LCASE({_lit(text)}))" for v in variables]
        clauses.append("FILTER(" + " || ".join(expressions) + ")")
    # Scope is validated in PostgreSQL against the canonical snapshot. Fetch IDs only;
    # multi-target annotations cannot multiply rows or split a page.
    return f'''PREFIX jas: <urn:jas-ns:>
PREFIX oa: <http://www.w3.org/ns/oa#>
PREFIX bwb: <urn:bwb-ns:>
SELECT DISTINCT ?id WHERE {{
 GRAPH <{REGISTER}> {{ <{SCHEMA}> jas:versie 2 . ?laag jas:inGraaf ?g ; jas:revisie ?rev . }}
 GRAPH ?g {{
  ?laag jas:revisie ?rev ; jas:status ?laagstatus .
  ?e a jas:Markering ; jas:inLaag ?laag ; jas:elementId ?id ;
     jas:klasseNaam ?klasse ; jas:lifecycle ?lifecycle ; jas:verouderd ?verouderd ;
     jas:tekst ?tekst ; jas:toelichting ?toelichting .
  {' '.join(clauses)}
 }}
}} ORDER BY ?id LIMIT {max(1, min(10001, int(limit)))}'''


def _repo() -> str:
    cfg = get_settings()
    if not cfg.graphdb_url:
        raise ConnectionError("Annotatiegraaf is niet geconfigureerd")
    return f"{cfg.graphdb_url}/repositories/{cfg.graphdb_repository}"


async def _select(client: httpx.AsyncClient, query: str) -> list[dict]:
    r = await client.post(_repo(), data={"query": query}, headers={"Accept": "application/sparql-results+json"})
    r.raise_for_status()
    from bronmodel import parse_rows
    return parse_rows(r.json())


async def zoek_kandidaten(filters: dict) -> dict:
    manifest_query = f'''PREFIX jas: <urn:jas-ns:>
SELECT ?id ?rev WHERE {{ GRAPH <{REGISTER}> {{ <{SCHEMA}> jas:versie 2 .
 ?laag jas:inGraaf ?g ; jas:revisie ?rev ; jas:laagId ?id . }}
 GRAPH ?g {{ ?laag jas:revisie ?rev ; jas:schemaVersie 2 . }} }}'''
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(_repo(), data={"query": f"ASK {{ GRAPH <{REGISTER}> {{ <{SCHEMA}> <{JAS.versie}> 2 }} }}"},
                                  headers={"Accept": "application/sparql-results+json"})
            r.raise_for_status()
            if not r.json().get("boolean"):
                return {"ids": [], "manifest": {}, "beschikbaar": False, "reden": "projectie_herstelt"}
            before = await _select(client, manifest_query)
            ids = await _select(client, zoek_query(filters))
            after = await _select(client, manifest_query)
        manifest = {r["id"]: int(r["rev"]) for r in after}
        return {"ids": [r["id"] for r in ids[:10000]], "manifest": manifest, "beschikbaar": True,
                "truncated": len(ids) > 10000,
                "gewijzigd": {r["id"]: int(r["rev"]) for r in before} != manifest}
    except (httpx.HTTPError, ConnectionError, ValueError) as exc:
        logger.warning("annotatiezoekgraaf_onbeschikbaar", extra={"fouttype": type(exc).__name__})
        return {"ids": [], "manifest": {}, "beschikbaar": False, "reden": "graaf_onbeschikbaar"}


async def projecteer(laag_id: str) -> bool:
    """Het rowlock beschermt ook tegen een oudere projector in een ander proces."""
    async with _locks.setdefault(laag_id, asyncio.Lock()):
        async with db.get_engine().begin() as conn:
            row = (await conn.execute(select(db.annotatie_v2_lagen).where(
                db.annotatie_v2_lagen.c.id == laag_id).with_for_update())).mappings().first()
            if row is None:
                return False
            laag = dict(row)
            elements = (await conn.execute(select(db.annotatie_v2_elementen.c.inhoud).where(
                db.annotatie_v2_elementen.c.laag_id == laag_id))).scalars().all()
            data = bouw_graaf(laag, list(elements), prov=get_settings().jas_projectie_prov)
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.put(_repo() + "/rdf-graphs/service", params={"graph": str(graph_iri(laag_id))},
                                     content=data.serialize(format="turtle").encode(),
                                     headers={"Content-Type": "text/turtle"})
                r.raise_for_status()
                # Update only this registry entry: parallel different-layer projectors cannot
                # overwrite each other's registry contributions.
                owner = laag_iri(laag_id).n3()
                statement = f'''PREFIX jas: <urn:jas-ns:>
DELETE {{ GRAPH <{REGISTER}> {{ {owner} ?p ?o }} }}
INSERT {{ GRAPH <{REGISTER}> {{
 <{SCHEMA}> jas:versie 2 . {owner} jas:inGraaf {graph_iri(laag_id).n3()} ;
 jas:laagId {_lit(laag_id)} ; jas:revisie {int(laag['revisie'])} .
}} }} WHERE {{ OPTIONAL {{ GRAPH <{REGISTER}> {{ {owner} ?p ?o }} }} }}'''
                r = await client.post(_repo() + "/statements", data={"update": statement})
                r.raise_for_status()
            await conn.execute(update(db.annotatie_v2_lagen).where(db.annotatie_v2_lagen.c.id == laag_id)
                               .values(geprojecteerd_revisie=laag["revisie"]))
    return True


def activeer(aan: bool) -> None:
    global _actief
    _actief = aan


async def stop() -> None:
    activeer(False)
    for taak in list(_taken):
        taak.cancel()
    await asyncio.gather(*_taken, return_exceptions=True)


def na_mutatie(laag_ids) -> None:
    """Best-effort, op de achtergrond, direct na de commit. Een GraphDB die hapert mag geen beslissing
    van een jurist laten falen: mislukt het, dan blijft de laag vuil en neemt `lus` hem mee."""
    if not _actief:
        return

    async def _doe(laag_id: str):
        try:
            await projecteer(laag_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("annotatie_v2_projectie_uitgesteld",
                           extra={"laag_id": laag_id, "fouttype": type(exc).__name__})

    for laag_id in dict.fromkeys(laag_ids):
        taak = asyncio.get_running_loop().create_task(_doe(laag_id))
        _taken.add(taak)
        taak.add_done_callback(_taken.discard)


async def reconcile() -> int:
    async with db.get_engine().connect() as conn:
        lagen = (await conn.execute(select(db.annotatie_v2_lagen))).mappings().all()
    # Actual graph revisions detect loss even if PostgreSQL still says 'projected'.
    state = await zoek_kandidaten({"limit": 1})
    manifest = state.get("manifest", {})
    count = 0
    for row in lagen:
        if manifest.get(row["id"]) != row["revisie"] or row["geprojecteerd_revisie"] != row["revisie"]:
            count += bool(await projecteer(row["id"]))
    if not lagen:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(_repo() + "/statements", data={"update":
                f"INSERT DATA {{ GRAPH <{REGISTER}> {{ <{SCHEMA}> <{JAS.versie}> 2 }} }}"})
            r.raise_for_status()
    await verwijder_verweesde_projecties()
    async with httpx.AsyncClient(timeout=20) as client:
        await zorg_voor_vocabulaire(client)
    return count


async def verwijder_verweesde_projecties(limit: int = 50) -> int:
    """Ruim uitsluitend geregistreerde v2-afgeleiden zonder Postgres-laag op.

Het globale schrijversslot sluit creatie van dezelfde laag tussen de DB-controle
en het verwijderen uit. Normale projecties lopen buiten dit slot; dat voorkomt
een lockcyclus met hun per-laag rowlocks.
"""
    from .annotatie_v2_store import schrijftransactie
    query = f'''PREFIX jas: <urn:jas-ns:>
SELECT ?id ?laag ?g WHERE {{ GRAPH <{REGISTER}> {{
  ?laag jas:laagId ?id ; jas:inGraaf ?g .
}} }} ORDER BY ?id'''
    removed = 0
    async with db.get_engine().connect() as conn:
        live_ids = set((await conn.execute(select(db.annotatie_v2_lagen.c.id))).scalars())
    async with httpx.AsyncClient(timeout=20) as client:
        registered = await _select(client, query)
        for item in registered:
            if removed >= limit:
                break
            layer_id = item.get("id", "")
            if layer_id in live_ids:
                continue  # normale lagen vragen geen exclusief schrijversslot
            if (not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", layer_id)
                    or item.get("laag") != str(laag_iri(layer_id))
                    or item.get("g") != str(graph_iri(layer_id))):
                continue  # nooit een willekeurige of legacy-graaf uit registratiegegevens wissen
            async with schrijftransactie() as conn:
                exists = (await conn.execute(select(db.annotatie_v2_lagen.c.id).where(
                    db.annotatie_v2_lagen.c.id == layer_id))).first()
                if exists:
                    continue
                statement = f'''DROP SILENT GRAPH {graph_iri(layer_id).n3()};
DELETE WHERE {{ GRAPH <{REGISTER}> {{ {laag_iri(layer_id).n3()} ?p ?o }} }}'''
                response = await client.post(_repo() + "/statements", data={"update": statement})
                response.raise_for_status()
                removed += 1
    if removed:
        logger.info("annotatie_v2_verweesde_projecties_verwijderd", extra={"aantal": removed})
    return removed


async def lus(interval: float = 30, controle_elke: int = 10) -> None:
    ronde = 0
    while True:
        try:
            count = await reconcile()
            if count:
                logger.info("annotatie_v2_geprojecteerd", extra={"aantal": count})
            # Elke paar rondes de lichte graafcontrole (zonder SHACL): een logregel met
            # `annotatie_graaf_afwijking`, zodat Grafana een graaf die stil uit de pas loopt laat zien.
            ronde += 1
            if ronde % controle_elke == 0:
                from .graafcontrole import log_stand
                await log_stand()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("annotatie_v2_projectie_uitgesteld", extra={"fouttype": type(exc).__name__})
        await asyncio.sleep(interval)
