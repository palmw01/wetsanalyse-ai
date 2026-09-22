"""RDF-kandidaten zijn nooit ongecontroleerde annotatie-antwoorden."""
from __future__ import annotations

import logging
import base64
import json
import re

from fastapi import HTTPException
from sqlalchemy import select

from . import db
from .annotatie_v2_contracts import Zoekvraag
from .annotatie_v2_store import bereik_van, nodes_van, publiek_laag, digest, leestransactie, historische_snapshot
from .annotatie_v2 import resolve_bron

logger = logging.getLogger(__name__)


async def _manifest():
    async with leestransactie() as conn:
        layers = (await conn.execute(select(db.annotatie_v2_lagen))).mappings().all()
        epoch = (await conn.execute(select(db.annotatie_v2_state.c.revisie).where(
            db.annotatie_v2_state.c.id == 1))).scalar() or 0
        return {r["id"]: dict(r) for r in layers}, epoch


async def zoek(req: Zoekvraag) -> dict:
    from .graaf_projectie_v2 import zoek_kandidaten
    base = {"resultaten": [], "volledig": False, "peilmoment": db.utcnow().isoformat(),
            "filters": req.model_dump(), "volgende_offset": None, "cursor": None}
    try:
        history = None
        if req.bronversie and req.inclusief_verouderd:
            history = await historische_snapshot(req.bronversie)
            historical_nodes = nodes_van(history)
            root = next(n for n in historical_nodes.values() if not n.get("parent_iri"))
            if req.bwb_id and root.get("bwb_id") != req.bwb_id:
                raise HTTPException(422, "Bronversie hoort bij een andere regeling.")
            target = req.bron_iri or root["bron_iri"]
            if target not in historical_nodes:
                raise HTTPException(404, "Bronnode ontbreekt in deze opgeslagen bronversie.")
            scope = {target} if req.scope == "node" else bereik_van(history, target)
            snapshot = await resolve_bron({"bron_iri": root["bron_iri"]})
        else:
            snapshot = await resolve_bron({"bron_iri": req.bron_iri, "bwb_id": req.bwb_id}) if req.bron_iri or req.bwb_id else None
            scope = ({req.bron_iri} if req.scope == "node" and req.bron_iri else bereik_van(snapshot)) if snapshot else None
        before, epoch = await _manifest()
        query_hash = digest(req.model_dump(exclude={"cursor", "offset"}))
        offset = req.offset
        if req.cursor:
            try:
                cursor = json.loads(base64.urlsafe_b64decode(req.cursor + "=" * (-len(req.cursor) % 4)))
                if (cursor["query"] != query_hash or type(cursor["offset"]) is not int
                        or type(cursor["epoch"]) is not int or cursor["epoch"] < 0
                        or cursor["offset"] < 0 or cursor["offset"] > 10000):
                    raise ValueError("Ongeldige paginering")
            except (ValueError, KeyError, TypeError) as exc:
                raise HTTPException(422, "Ongeldige zoekcursor.") from exc
            if cursor["epoch"] != epoch:
                raise HTTPException(409, "Zoekresultaten gewijzigd; begin opnieuw.")
            offset = cursor["offset"]
        candidates = await zoek_kandidaten({**req.model_dump(),
                                            **({"bron_iri": "", "bronnode_id": ""} if history else {}),
                                            **({"scoped_nodes": sorted(scope)} if scope else {})})
        if not candidates.get("beschikbaar", True):
            return {**base, "status": "unavailable", "reden": "projectie_onbeschikbaar"}
        ids = list(dict.fromkeys(candidates.get("ids", [])))
        async with db.get_engine().connect() as conn:
            rows = (await conn.execute(select(db.annotatie_v2_elementen).where(
                db.annotatie_v2_elementen.c.id.in_(ids)))).mappings().all() if ids else []
        by_id = {r["id"]: r["inhoud"] for r in rows}
        # Ook ancestorlagen kunnen ankers in de selectie dragen. Het hele wetmanifest is
        # bewust conservatief: het bewijst dat zulke overspannende kandidaten niet ontbreken.
        law_nodes = set(nodes_van(snapshot)) if snapshot else None
        if history and law_nodes is not None:
            law_nodes |= set(nodes_van(history))
        relevant = {i: l for i, l in before.items() if law_nodes is None or l["bron_iri"] in law_nodes}
        projected = candidates.get("manifest", {})
        complete = (not candidates.get("truncated", False) and not candidates.get("gewijzigd", False) and
                    all(projected.get(i) == l["revisie"] and l["geprojecteerd_revisie"] == l["revisie"]
                        for i, l in relevant.items()))
        verified = []
        source_cache = {}
        for element_id in ids:
            e = by_id.get(element_id)
            if not e or (e.get("verouderd") and not req.inclusief_verouderd):
                continue
            if scope is not None and not any(a["bron_iri"] in scope for a in e["ankers"]):
                continue
            if req.jas_klassen and e["klasse"] not in req.jas_klassen:
                continue
            if req.lifecycle and e["lifecycle"] not in req.lifecycle:
                continue
            if not req.lifecycle and e["lifecycle"] == "rejected":
                continue
            if req.bronversie and e["snapshot_id"] != req.bronversie:
                continue
            if req.tekst:
                fields = [e["tekst"], e.get("toelichting", "")] if req.tekstveld == "beide" else [
                    e["tekst"] if req.tekstveld == "citaat" else e.get("toelichting", "")]
                if not any((req.tekst == field if req.match == "exact" else req.tekst.lower() in field.lower()) for field in fields):
                    continue
            layer = before.get(e["laag_id"])
            if layer is None:
                complete = False
                continue
            if req.laagstatus and layer["status"] not in req.laagstatus:
                continue
            current = snapshot
            if current is None:
                owner = e["eigenaar_iri"]
                match = re.fullmatch(r"urn:bwb:(BWB[RV]\d+)(?::[^<>\s\"{}|^`\\]*)?", owner)
                if not match:
                    complete = False
                    continue
                law = match.group(1)
                if law not in source_cache:
                    try:
                        source_cache[law] = await resolve_bron({"bwb_id": law})
                    except HTTPException:
                        source_cache[law] = None
                current = source_cache[law]
            if current is None:
                complete = False
                continue
            nodes = nodes_van(current)
            stale = e.get("verouderd", False) or any(a["bron_iri"] not in nodes or nodes[a["bron_iri"]]["bron_hash"] != a["bron_hash"]
                   or nodes[a["bron_iri"]]["tekst"][a["start"]:a["eind"]] != a["tekst"] for a in e["ankers"])
            if stale and not req.inclusief_verouderd:
                continue
            # Een deels buitenliggend element is in dit bereik alleen een verwijzing. De
            # afzonderlijke detailtool kan vervolgens bewust de eigenaar als bereik openen.
            if scope is not None and not {a["bron_iri"] for a in e["ankers"]} <= scope:
                verified.append({"id": e["id"], "eigenaar_iri": e["eigenaar_iri"], "klasse": e["klasse"],
                    "soort": "verwijzing", "label": "Annotatie met een ruimere bronselectie",
                    "laag_revisie": layer["revisie"], "snapshot_id": e["snapshot_id"],
                    "detail_url": f"/v1/annotatie/elementen/{element_id}"})
                continue
            verified.append({**e, "verouderd": stale, "laag": publiek_laag(layer), "bronverwijzing": {
                "bron_iri": e["eigenaar_iri"], "snapshot_id": e["snapshot_id"], "historisch": stale,
                "ankers": e["ankers"], "detail_url": f"/v1/annotatie/elementen/{element_id}"}})
        _, after_epoch = await _manifest()
        if after_epoch != epoch:
            # Geen DB-stand uit twee revisies als actueel presenteren.
            return {**base, "status": "partial", "reden": "gewijzigd_tijdens_zoeken"}
        selected = verified[offset:offset + req.limit]
        has_more = offset + req.limit < len(verified)
        next_cursor = base64.urlsafe_b64encode(json.dumps({"query": query_hash, "epoch": epoch,
            "offset": offset + req.limit}).encode()).decode().rstrip("=") if has_more and complete else None
        result = {**base, "status": "ok" if complete else "partial", "resultaten": selected,
                  "volledig": complete, "manifest_revisie": epoch,
                  "volgende_offset": offset + req.limit if has_more else None, "cursor": next_cursor}
        if not complete:
            result["reden"] = "projectie_achterstand_of_afgekapt"
        logger.info("annotatie_v2_zoeken", extra={"status": result["status"], "kandidaten": len(ids),
                    "geverifieerd": len(verified), "manifest_revisie": epoch})
        return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("annotatie_v2_zoeken_onbeschikbaar")
        return {**base, "status": "unavailable", "reden": "verificatie_onbeschikbaar"}
