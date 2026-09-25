"""Inventaris van de annotatiedata van de legacy-keten (ADR-001 PR 18) – ALLEEN LEZEN.

Draait in de api-container van één straat, met dezelfde configuratie, via de workflow
`inventaris-legacy-annotaties.yml`. Wijzigt niets: geen enkele schrijfactie, en de transactie is
read-only. De uitkomst is de basis voor een apart besluit over wat er weg mag.

Wat hij telt:
- v1 (contract 1): `annotatie_documenten` (gedeelde lagen en per-gebruiker-documenten) en
  `annotatie_audit`, plus de v1-graphs in GraphDB (`urn:jas:graph:*` buiten `:v2:`).
- v2 (contract 2): elementen naar herkomst – agent zonder `trace` (legacy-keten), agent mét `trace`
  (hybride keten), mens – en hoeveel daarvan een beslissing van een jurist dragen; lagen, dekking,
  batches, snapshots en audit; de v2-graphs.
- chatberichten die naar een annotatie verwijzen (`annotatie_doel`/`annotatie_slug`).
"""
import asyncio
import json
from collections import Counter

import httpx
from sqlalchemy import func, select, text

from app import db
from app.config import get_settings

MARKER = "ANNOTATIE_INVENTARIS_OK"


async def _tel(conn, tabel) -> int:
    return (await conn.execute(select(func.count()).select_from(tabel))).scalar_one()


async def _graphs(cfg) -> dict:
    if not cfg.graphdb_url:
        return {"graafprojectie_actief": False}
    repo = cfg.graphdb_url.rstrip("/") + "/repositories/" + cfg.graphdb_repository
    query = """SELECT ?g (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o }
  FILTER(STRSTARTS(STR(?g), "urn:jas:graph:")) } GROUP BY ?g"""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(repo, data={"query": query}, headers={"Accept": "application/sparql-results+json"})
        r.raise_for_status()
    rijen = [(b["g"]["value"], int(b["n"]["value"])) for b in r.json()["results"]["bindings"]]
    soort = Counter()
    triples = Counter()
    for g, n in rijen:
        if g.startswith("urn:jas:graph:v2:"):
            k = "v2_laag"
        elif g == "urn:jas:graph:register:v2":
            k = "v2_register"
        elif g == "urn:jas:graph:register":
            k = "v1_register"
        else:
            k = "v1_overig"      # v1-lagen en de v1-ontologiegraaf
        soort[k] += 1
        triples[k] += n
    return {"graafprojectie_actief": True, "graphs": dict(soort), "triples": dict(triples)}


async def main():
    cfg = get_settings()
    db.init_engine(cfg.database_url)
    uit: dict = {}
    async with db.get_engine().connect() as conn:
        if conn.dialect.name == "postgresql":
            await conn.execute(text("SET TRANSACTION READ ONLY"))

        # --- v1
        docs = (await conn.execute(select(
            db.annotatie_documenten.c.laag_sleutel, db.annotatie_documenten.c.samengevoegd_in,
            db.annotatie_documenten.c.elementen))).all()
        v1_elementen = sum(len(r.elementen or []) for r in docs)
        v1_beslist = sum(1 for r in docs for e in (r.elementen or []) if e.get("beslissingen"))
        uit["v1"] = {
            "documenten": len(docs),
            "gedeelde_lagen": sum(1 for r in docs if r.laag_sleutel),
            "per_gebruiker": sum(1 for r in docs if not r.laag_sleutel and not r.samengevoegd_in),
            "samengevoegd": sum(1 for r in docs if r.samengevoegd_in),
            "elementen": v1_elementen,
            "elementen_met_beslissing": v1_beslist,
            "auditregels": await _tel(conn, db.annotatie_audit),
        }

        # --- v2
        herkomst = Counter()
        beslist = Counter()
        lagen_per_soort: dict[str, set] = {}
        rows = (await conn.execute(select(db.annotatie_v2_elementen.c.laag_id,
                                          db.annotatie_v2_elementen.c.inhoud))).all()
        for laag_id, e in rows:
            if e.get("herkomst") == "mens":
                k = "mens"
            elif e.get("trace"):
                k = "agent_hybride"
            else:
                k = "agent_legacy"
            herkomst[k] += 1
            if e.get("beslissingen"):
                beslist[k] += 1
            lagen_per_soort.setdefault(k, set()).add(laag_id)
        alleen_legacy = lagen_per_soort.get("agent_legacy", set()) - lagen_per_soort.get(
            "agent_hybride", set()) - lagen_per_soort.get("mens", set())
        status = Counter(r[0] for r in (await conn.execute(select(db.annotatie_v2_lagen.c.status))).all())
        uit["v2"] = {
            "lagen": await _tel(conn, db.annotatie_v2_lagen),
            "lagen_per_status": dict(status),
            "lagen_met_alleen_legacy": len(alleen_legacy),
            "elementen": dict(herkomst),
            "elementen_met_beslissing": dict(beslist),
            "dekking": await _tel(conn, db.annotatie_v2_dekking),
            "batches": await _tel(conn, db.annotatie_v2_batches),
            "snapshots": await _tel(conn, db.annotatie_v2_snapshots),
            "auditregels": await _tel(conn, db.annotatie_v2_audit),
        }

        # --- verwijzingen vanuit gesprekken (niet om te wissen: om te weten wat er gaat bungelen)
        verwijzend = (await conn.execute(select(func.count()).select_from(db.gesprek_berichten).where(
            text("inhoud::text LIKE '%annotatie_doel%' OR inhoud::text LIKE '%annotatie_slug%'")
            if conn.dialect.name == "postgresql" else text("0")))).scalar_one()
        uit["gesprekken"] = {
            "gesprekken": await _tel(conn, db.gesprekken),
            "berichten": await _tel(conn, db.gesprek_berichten),
            "berichten_met_annotatieverwijzing": verwijzend,
        }
        await conn.rollback()

    uit["graaf"] = await _graphs(cfg)
    print(json.dumps(uit, ensure_ascii=False, sort_keys=True), flush=True)
    print(MARKER, flush=True)


asyncio.run(main())
