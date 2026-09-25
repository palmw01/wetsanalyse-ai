"""Graafcontrole: klopt de annotatiegraaf met Postgres, en is hij netjes opgebouwd?

De projectie (`graaf_projectie_v2`) schrijft; deze module controleert achteraf, alleen lezend. Vier
vragen, elk apart gerapporteerd:

1. **Consistentie** – staat elke laag uit Postgres in het register en als named graph, met dezelfde
   revisie; en staat er niets in de graaf dat Postgres niet (meer) kent (verweesd)?
2. **Bouw** – is de opgehaalde graph *isomorf* met wat `bouw_graaf` nú uit de Postgres-stand zou
   maken? Dat vangt elke drift tussen projectiecode en opgeslagen graaf: een half geschreven graph,
   een oudere projector, een handmatige wijziging, een schemawijziging die nog niet overal landde.
3. **SHACL** – conform `shapes/jas-v2.ttl`, per niveau (`rdf` / `jas_model`), via `shacl.valideer`.
4. **Invarianten** – de wettekst blijft schoon: geen subject onder `urn:bwb:`, geen `urn:bwb-ns:`-
   predicaat en geen schema-axioma's (domain/range/subClassOf/sameAs) in een `urn:jas:graph:*`.

Een laag die nog niet geprojecteerd is (`geprojecteerd_revisie < revisie`) heet **achterstand**,
geen afwijking: de directe projectie en de reconcile-lus halen die in. Pas als de graaf iets anders
zegt dan Postgres terwijl hij bij is, is het een afwijking.

Een onbereikbare graaf is nooit "alles in orde": dan is `graaf_beschikbaar` False en `in_orde` None.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from rdflib import Graph, Literal
from rdflib.compare import isomorphic
from sqlalchemy import select

from . import db
from .config import get_settings
from .graaf_projectie_v2 import (JAS, REGISTER, VOCAB_SCHEMA, VOCABULAIRE, _lit, _repo, _select, bouw_graaf,
                                 graph_iri, laag_iri, vocabulaire)

logger = logging.getLogger(__name__)

_INVARIANTEN = {
    "geen_bwb_subject": '''ASK { GRAPH ?g { ?s ?p ?o }
  FILTER(STRSTARTS(STR(?g), "urn:jas:graph:") && isIRI(?s) && STRSTARTS(STR(?s), "urn:bwb:")) }''',
    "geen_bwb_predicaat": '''ASK { GRAPH ?g { ?s ?p ?o }
  FILTER(STRSTARTS(STR(?g), "urn:jas:graph:") && STRSTARTS(STR(?p), "urn:bwb-ns:")) }''',
    "geen_schema_axioma": '''ASK { GRAPH ?g { ?s ?p ?o }
  FILTER(STRSTARTS(STR(?g), "urn:jas:graph:") && ?p IN (
    <http://www.w3.org/2000/01/rdf-schema#domain>, <http://www.w3.org/2000/01/rdf-schema#range>,
    <http://www.w3.org/2000/01/rdf-schema#subPropertyOf>, <http://www.w3.org/2000/01/rdf-schema#subClassOf>,
    <http://www.w3.org/2002/07/owl#sameAs>)) }''',
}
_REGISTER_QUERY = f'''PREFIX jas: <urn:jas-ns:>
SELECT ?id ?g ?rev WHERE {{ GRAPH <{REGISTER}> {{ ?laag jas:laagId ?id ; jas:inGraaf ?g ; jas:revisie ?rev }} }}'''
_V2_GRAPHS_QUERY = '''SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o }
  FILTER(STRSTARTS(STR(?g), "urn:jas:graph:v2:")) }'''


async def _ask(client: httpx.AsyncClient, query: str) -> bool:
    r = await client.post(_repo(), data={"query": query}, headers={"Accept": "application/sparql-results+json"})
    r.raise_for_status()
    return bool(r.json().get("boolean"))


async def _haal_graph(client: httpx.AsyncClient, iri: str) -> Graph:
    r = await client.get(_repo() + "/rdf-graphs/service", params={"graph": iri}, headers={"Accept": "text/turtle"})
    if r.status_code == 404:
        return Graph()
    r.raise_for_status()
    return Graph().parse(data=r.text, format="turtle")


async def _postgres() -> tuple[list[dict], dict[str, list[dict]]]:
    async with db.get_engine().connect() as conn:
        lagen = [dict(r) for r in (await conn.execute(select(db.annotatie_v2_lagen))).mappings().all()]
        rows = (await conn.execute(select(db.annotatie_v2_elementen.c.laag_id,
                                          db.annotatie_v2_elementen.c.inhoud))).all()
    per_laag: dict[str, list[dict]] = {}
    for laag_id, inhoud in rows:
        per_laag.setdefault(laag_id, []).append(inhoud)
    return lagen, per_laag


def _verschil(verwacht: Graph, echt: Graph) -> dict[str, int]:
    """Een ruwe maat voor hoe ver twee niet-isomorfe graphs uiteenlopen (blanke nodes tellen mee)."""
    return {"triples_verwacht": len(verwacht), "triples_in_graaf": len(echt)}


def _pyshacl_aanwezig() -> bool:
    try:
        import pyshacl  # noqa: F401
    except ImportError:
        return False
    return True


async def controleer(*, shacl: bool = True) -> dict[str, Any]:
    """Volledige controle. `shacl=False` voor de lichte variant in de reconcile-lus."""
    uit: dict[str, Any] = {"graaf_beschikbaar": False, "in_orde": None, "lagen": 0, "achterstand": [],
                           "afwijkingen": [], "verweesd": [], "invarianten": {}, "vocabulaire": None,
                           "shacl": None}
    lagen, elementen = await _postgres()
    uit["lagen"] = len(lagen)
    if not get_settings().graphdb_url:
        uit["reden"] = "graafprojectie_uit"
        return uit
    prov = get_settings().jas_projectie_prov
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            register = {r["id"]: r for r in await _select(client, _REGISTER_QUERY)}
            v2_graphs = {r["g"] for r in await _select(client, _V2_GRAPHS_QUERY)}
            uit["graaf_beschikbaar"] = True
            shacl_uit: dict[str, Any] = {"beschikbaar": _pyshacl_aanwezig(), "conform": True, "bevindingen": []}
            for laag in sorted(lagen, key=lambda x: x["id"]):
                lid, rev = laag["id"], int(laag["revisie"])
                if int(laag.get("geprojecteerd_revisie") or 0) < rev:
                    uit["achterstand"].append({"laag_id": lid, "revisie": rev,
                                               "geprojecteerd": int(laag.get("geprojecteerd_revisie") or 0)})
                    continue
                reg = register.get(lid)
                if reg is None:
                    uit["afwijkingen"].append({"laag_id": lid, "soort": "niet_in_register"})
                    continue
                if reg["g"] != str(graph_iri(lid)):
                    uit["afwijkingen"].append({"laag_id": lid, "soort": "verkeerde_graph", "detail": reg["g"]})
                if int(reg["rev"]) != rev:
                    uit["afwijkingen"].append({"laag_id": lid, "soort": "registerrevisie",
                                               "detail": {"postgres": rev, "register": int(reg["rev"])}})
                echt = await _haal_graph(client, str(graph_iri(lid)))
                if not len(echt):
                    uit["afwijkingen"].append({"laag_id": lid, "soort": "graph_ontbreekt"})
                    continue
                graaf_rev = echt.value(laag_iri(lid), JAS.revisie)
                if graaf_rev != Literal(rev):
                    uit["afwijkingen"].append({"laag_id": lid, "soort": "graphrevisie",
                                               "detail": {"postgres": rev, "graph": str(graaf_rev)}})
                verwacht = bouw_graaf(laag, elementen.get(lid, []), prov=prov)
                if not isomorphic(verwacht, echt):
                    uit["afwijkingen"].append({"laag_id": lid, "soort": "inhoud_wijkt_af",
                                               "detail": _verschil(verwacht, echt)})
                if shacl:
                    from .shacl import valideer
                    r = valideer(echt)
                    shacl_uit["beschikbaar"] = r["beschikbaar"]
                    if r["beschikbaar"] and not r["conform"]:
                        shacl_uit["conform"] = False
                        for niveau in ("rdf", "jas_model"):
                            shacl_uit["bevindingen"] += [{"laag_id": lid, "niveau": niveau, **b} for b in r[niveau]]
            bekend = {laag["id"] for laag in lagen}
            uit["verweesd"] = sorted(
                [{"soort": "registratie", "laag_id": i} for i in register if i not in bekend]
                + [{"soort": "graph", "graph": g} for g in v2_graphs
                   if g not in {str(graph_iri(i)) for i in bekend}], key=str)
            for naam, query in _INVARIANTEN.items():
                uit["invarianten"][naam] = not await _ask(client, query)
            versie, _ttl = vocabulaire()
            uit["vocabulaire"] = {"versie": versie, "aanwezig": await _ask(client, (
                f"ASK {{ GRAPH <{VOCABULAIRE}> {{ <{VOCAB_SCHEMA}> <{JAS.vocabulaireVersie}> {_lit(versie)} }} }}"))}
            if shacl:
                uit["shacl"] = shacl_uit
    except (httpx.HTTPError, ConnectionError, ValueError) as exc:
        logger.warning("graafcontrole_onbeschikbaar", extra={"fouttype": type(exc).__name__})
        uit["graaf_beschikbaar"] = False
        uit["reden"] = "graaf_onbeschikbaar"
        return uit
    uit["in_orde"] = (not uit["afwijkingen"] and not uit["verweesd"] and all(uit["invarianten"].values())
                      and uit["vocabulaire"]["aanwezig"]
                      and (not shacl or uit["shacl"]["conform"] is not False))
    return uit


async def log_stand() -> dict[str, Any]:
    """Lichte variant voor de reconcile-lus: geen SHACL, één logregel. Faalt nooit naar boven."""
    try:
        uit = await controleer(shacl=False)
    except Exception as exc:  # noqa: BLE001 – een diagnose mag de lus niet breken
        logger.warning("graafcontrole_fout", extra={"fouttype": type(exc).__name__})
        return {}
    if uit["graaf_beschikbaar"]:
        aantal = (len(uit["afwijkingen"]) + len(uit["verweesd"]) + sum(not v for v in uit["invarianten"].values())
                  + (not uit["vocabulaire"]["aanwezig"]))
        (logger.warning if aantal else logger.info)("annotatie_graafcontrole", extra={
            "annotatie_graaf_afwijking": aantal, "lagen": uit["lagen"], "achterstand": len(uit["achterstand"])})
    return uit
