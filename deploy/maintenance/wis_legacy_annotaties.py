"""Eenmalig: wis alle annotatiedata van vóór ADR-001 PR 18 (POC-data) uit één straat.

Draait in de api-container via `wis-legacy-annotaties.yml`. De workflow zet vóór deze code twee
regels: `DO_WRITE` (False = dry-run) en `VERWACHT` (de aantallen uit de inventaris). Wijkt de stand
daar op één getal van af, dan stopt hij zonder iets te wijzigen – de data is dan veranderd sinds
iemand er "ja" op zei.

Wat er weggaat (besluit gebruiker, 25 sep 2026: "alles annotatie"):
- v1: alle `annotatie_documenten` en hun `annotatie_audit`;
- v2: alle lagen, elementen (ook markeringen en beslissingen van juristen), dekking, batches,
  snapshots en audit. `annotatie_v2_state` blijft: de revisieteller loopt door;
- in chatberichten alleen de verwijzing naar een annotatie (`annotatie_doel`, `annotatie_slug`,
  `annotatie_titel`, `hergebruik`, `ontbrekend`); het bericht zelf blijft;
- in GraphDB de v2-laaggraphs en hun registratie. De v1-graphs blijven: er is geen v1-laag, en de
  v1-ontologie en het v1-register bouwt de draaiende api anders meteen opnieuw op.

Alles in Postgres gebeurt in één transactie, onder hetzelfde schrijversslot als de api
(`annotatie_v2_state` FOR UPDATE) plus een tabelslot op v1.
"""
import asyncio
import base64
import json

import httpx
from sqlalchemy import delete, func, select, text, update

from app import db
from app.config import get_settings
from app.graaf_projectie_v2 import REGISTER, graph_iri, laag_iri

VERWIJZINGEN = ("annotatie_doel", "annotatie_slug", "annotatie_titel", "hergebruik", "ontbrekend")
V2 = ("annotatie_v2_elementen", "annotatie_v2_lagen", "annotatie_v2_dekking", "annotatie_v2_batches",
      "annotatie_v2_snapshots", "annotatie_v2_audit")


def _meld(soort: str, data: dict) -> None:
    print(soort + " " + base64.b64encode(json.dumps(data, sort_keys=True).encode()).decode(), flush=True)


def _verwijst(inhoud) -> bool:
    return isinstance(inhoud, dict) and any(inhoud.get(k) for k in VERWIJZINGEN)


async def _stand(conn) -> tuple[dict, list]:
    tel = {}
    for naam in ("annotatie_documenten", "annotatie_audit", *V2):
        tel[naam] = (await conn.execute(select(func.count()).select_from(getattr(db, naam)))).scalar_one()
    berichten = [(r.id, r.inhoud) for r in (await conn.execute(
        select(db.gesprek_berichten.c.id, db.gesprek_berichten.c.inhoud))).all() if _verwijst(r.inhoud)]
    tel["berichten_met_annotatieverwijzing"] = len(berichten)
    return tel, berichten


async def _v2_graphs(client, repo: str) -> list[str]:
    q = f"""PREFIX jas: <urn:jas-ns:>
SELECT ?id WHERE {{ GRAPH <{REGISTER}> {{ ?laag jas:laagId ?id ; jas:inGraaf ?g }} }}"""
    r = await client.post(repo, data={"query": q}, headers={"Accept": "application/sparql-results+json"})
    r.raise_for_status()
    return sorted(b["id"]["value"] for b in r.json()["results"]["bindings"])


async def main():
    cfg = get_settings()
    db.init_engine(cfg.database_url)
    repo = cfg.graphdb_url.rstrip("/") + "/repositories/" + cfg.graphdb_repository if cfg.graphdb_url else ""
    async with httpx.AsyncClient(timeout=30) as client:
        async with db.get_engine().begin() as conn:
            assert conn.dialect.name == "postgresql", "Alleen voor de PostgreSQL van een straat"
            # Hetzelfde slot als `annotatie_v2_store.schrijftransactie`, zodat geen beurt ertussen schrijft.
            await conn.execute(select(db.annotatie_v2_state).where(db.annotatie_v2_state.c.id == 1).with_for_update())
            await conn.execute(text("LOCK TABLE annotatie_documenten, annotatie_audit IN EXCLUSIVE MODE"))
            stand, berichten = await _stand(conn)
            beschermd = {t: (await conn.execute(text(f'SELECT count(*) FROM "{t}"'))).scalar_one()
                         for t in ("users", "gesprekken", "gesprek_berichten", "token_verbruik")}
            afwijking = {k: (stand.get(k), v) for k, v in VERWACHT.items() if stand.get(k) != v}
            _meld("WIS_STAND", {"dry_run": not DO_WRITE, "stand": stand, "beschermd": beschermd,
                                "afwijking": afwijking})
            if afwijking:
                raise SystemExit("De stand wijkt af van de inventaris; niets gewijzigd: " + json.dumps(afwijking))
            if not DO_WRITE:
                print("ANNOTATIE_WIS_DRY_RUN_OK", flush=True)
                return

            for bid, inhoud in berichten:
                schoon = {k: v for k, v in inhoud.items() if k not in VERWIJZINGEN}
                await conn.execute(update(db.gesprek_berichten).where(
                    db.gesprek_berichten.c.id == bid).values(inhoud=schoon))
            for naam in (*V2, "annotatie_audit", "annotatie_documenten"):
                await conn.execute(delete(getattr(db, naam)))
            na, _ = await _stand(conn)
            assert all(v == 0 for v in na.values()), na
            for t, n in beschermd.items():
                assert (await conn.execute(text(f'SELECT count(*) FROM "{t}"'))).scalar_one() == n, t

        # Na de commit: de v2-graphs. De reconcile-lus van de api zou ze ook opruimen (verweesde
        # projecties); hier gebeurt het direct en controleerbaar, met exact dezelfde bewerking.
        gewist = []
        if repo:
            for laag_id in await _v2_graphs(client, repo):
                stmt = f"""DROP SILENT GRAPH {graph_iri(laag_id).n3()};
DELETE WHERE {{ GRAPH <{REGISTER}> {{ {laag_iri(laag_id).n3()} ?p ?o }} }}"""
                r = await client.post(repo + "/statements", data={"update": stmt})
                r.raise_for_status()
                gewist.append(laag_id)
            assert await _v2_graphs(client, repo) == []
            ask = 'ASK { GRAPH ?g { ?s ?p ?o } FILTER(STRSTARTS(STR(?g), "urn:jas:graph:v2:")) }'
            r = await client.post(repo, data={"query": ask}, headers={"Accept": "application/sparql-results+json"})
            r.raise_for_status()
            assert r.json()["boolean"] is False, "er staat nog een v2-laaggraaf"
        _meld("WIS_KLAAR", {"berichten_opgeschoond": len(berichten), "v2_graphs_gewist": len(gewist)})
        print("ANNOTATIE_WIS_EXECUTED_OK", flush=True)


asyncio.run(main())
