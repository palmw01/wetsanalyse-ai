"""Eenmalige, begrensde opschoning van de expliciet vrijgegeven testlaag.

Uitvoeren in de API-container, met dezelfde configuratie. Geen generieke purge.
Een andere inhoud, een tweede document of menselijke beoordeling stopt de actie.
"""
import asyncio
import json
from datetime import datetime

import httpx
from sqlalchemy import delete, func, select, text
from app import db
from app.annotatie_store import AnnotatieStore
from app.config import get_settings
from app.graaf_projectie import REGISTER, REGISTER_GRAAF, JAS, laag_graaf_iri, laag_iri

SLUG = "cf51263f2e184b80"
UPDATED = datetime.fromisoformat("2026-09-22T11:49:40.776695+00:00")

async def main():
    cfg = get_settings()
    db.init_engine(cfg.database_url)
    store = AnnotatieStore()
    doc = await store.laad_document(SLUG)
    if doc is None:
        raise RuntimeError("Testdocument ontbreekt; geen wijziging uitgevoerd")
    assert doc.bwbId == "BWBR0004770" and doc.artikel == "9"
    assert doc.laag_sleutel == "BWBR0004770:9"
    assert len(doc.elementen) == 7 and not any(e.beslissingen for e in doc.elementen)
    assert db.aware(doc.updated) == UPDATED
    repo = cfg.graphdb_url.rstrip("/") + "/repositories/" + cfg.graphdb_repository
    graph, owner = laag_graaf_iri(doc), laag_iri(doc)
    async with httpx.AsyncClient(timeout=30) as client:
        async def query(q):
            r = await client.post(repo, data={"query": q}, headers={"Accept": "application/sparql-results+json"})
            r.raise_for_status()
            return r.json()
        source_query = "SELECT (COUNT(*) AS ?n) WHERE { GRAPH <urn:bwb:graph:BWBR0004770> { ?s ?p ?o } }"
        source_before = await query(source_query) if cfg.graphdb_url else None
        if source_before is not None:
            assert int(source_before["results"]["bindings"][0]["n"]["value"]) > 0
        async with db.get_engine().begin() as conn:
            assert conn.dialect.name == "postgresql", "Deze actie is uitsluitend voor acceptatie-PostgreSQL"
            await conn.execute(text("LOCK TABLE annotatie_documenten IN EXCLUSIVE MODE"))
            rows = (await conn.execute(select(db.annotatie_documenten))).mappings().all()
            assert len(rows) == 1 and rows[0]["slug"] == SLUG, "Annotatie-inventaris gewijzigd"
            assert db.aware(rows[0]["updated"]) == UPDATED, "Annotatie gewijzigd"
            if cfg.graphdb_url:
                assert rows[0]["geprojecteerd_tot"] and db.aware(rows[0]["geprojecteerd_tot"]) >= UPDATED, "Projectie nog in uitvoering"
            else:
                assert rows[0]["geprojecteerd_tot"] is None, "Eerdere projectie moet eerst bereikbaar zijn"
            audit_count = (await conn.execute(select(func.count()).select_from(db.annotatie_audit).where(db.annotatie_audit.c.document_slug == SLUG))).scalar_one()
            protected = {}
            for table in ("users", "gesprekken", "gesprek_berichten"):
                exists = (await conn.execute(text("SELECT to_regclass(:name)"), {"name": table})).scalar()
                if exists:
                    protected[table] = (await conn.execute(text(f'SELECT count(*) FROM "{table}"'))).scalar_one()
            print(json.dumps({"dry_run": not DO_WRITE, "slug": SLUG, "elementen": 7, "auditregels": audit_count, "beschermd": protected, "graafprojectie_actief": bool(cfg.graphdb_url)}), flush=True)
            if not DO_WRITE:
                print("ANNOTATIE_CLEANUP_DRY_RUN_OK", flush=True)
                return
            # Alleen de afgeleide graph en haar eigen registratie; geen brongraphs.
            update = f'''DROP SILENT GRAPH <{graph}>;
DELETE WHERE {{ GRAPH <{REGISTER_GRAAF}> {{ <{owner}> ?p ?o }} }};
DELETE DATA {{ GRAPH <{REGISTER_GRAAF}> {{ <{REGISTER}> <{JAS.inLaag}> <{owner}> }} }}'''
            if cfg.graphdb_url:
                r = await client.post(repo + "/statements", data={"update": update})
                r.raise_for_status()
            await conn.execute(delete(db.annotatie_audit).where(db.annotatie_audit.c.document_slug == SLUG))
            result = await conn.execute(delete(db.annotatie_documenten).where(db.annotatie_documenten.c.slug == SLUG))
            assert result.rowcount == 1
            for table, count in protected.items():
                assert (await conn.execute(text(f'SELECT count(*) FROM "{table}"'))).scalar_one() == count
        if cfg.graphdb_url:
            assert not (await query(f"ASK {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}"))["boolean"]
            assert await query(source_query) == source_before
        async with db.get_engine().connect() as conn:
            assert (await conn.execute(select(func.count()).select_from(db.annotatie_documenten))).scalar_one() == 0
        print("ANNOTATIE_CLEANUP_EXECUTED_OK", flush=True)

asyncio.run(main())
