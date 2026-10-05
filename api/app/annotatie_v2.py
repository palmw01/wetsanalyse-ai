"""Bronnode-API. Elke lees- en schrijfactie vereist een actieve gebruiker."""
from __future__ import annotations

import json
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
import httpx
from bronmodel import BronFout

from . import annotatie_export as export
from . import annotatie_v2_store as store
from . import samenhang as samenhang_mod
from .annotatie_v2_contracts import Batch, Beslissing, Doel, Element, Zoekvraag
from .auth import require_client
from .bron_resolver import resolve_bron as _resolve_bron
from .routers.auth import actieve_userid
from .graaf_projectie_v2 import verklaringen

router = APIRouter(prefix="/annotatie", tags=["annotatie-bronnodes"],
                   dependencies=[Depends(require_client)])


async def resolve_bron(doel: dict) -> dict:
    try:
        return await _resolve_bron(doel)
    except BronFout as exc:
        raise HTTPException(422, str(exc)) from exc
    except (httpx.HTTPError, ConnectionError) as exc:
        raise HTTPException(503, "De brongraaf is tijdelijk niet beschikbaar.") from exc


def doel_query(bron_iri: str = "", bwb_id: str = "", artikel: str = "", lid: str = "") -> dict:
    return dict(bron_iri=bron_iri, bwb_id=bwb_id, artikel=artikel, lid=lid)



def _provenance(element: dict) -> dict:
    """De run die het element maakte, plus – bij de hybride keten – zijn herkomstspoor per element."""
    run = element.get("geproduceerd_door") or {}
    return {**run, "trace": element["trace"]} if element.get("trace") else run

@router.get("/verklaringen")
async def get_verklaringen(actor: str = Depends(actieve_userid)):
    """Leesbare namen en uitleg van alles wat in een `trace` kan staan – klassen, begrippen, regels,
    detectiecodes, twijfelredenen, resolutie- en validatiecodes. Gegenereerd uit de methode
    (`tools/graph-qa/scripts/genereer_jas_vocabulaire.py`); de werkplek toont de naam en zet het id
    in de tooltip."""
    return verklaringen()


@router.get("/capabilities")
async def capabilities(actor: str = Depends(actieve_userid)):
    """Wat deze api kan; de werkplek toont de samenhangsgraaf alleen als `samenhang` waar is."""
    return {"schema_versie": 2, "samenhang": True}


@router.get("/weergave")
async def get_weergave(doel: dict = Depends(doel_query), actor: str = Depends(actieve_userid)):
    return await store.weergave(await resolve_bron(doel))


@router.get("/samenhang")
async def get_samenhang(doel: dict = Depends(doel_query), actor: str = Depends(actieve_userid)):
    """Bronstructuur, actuele annotaties en letterlijke verwijzingen (één stap) van het artikel
    waartoe het doel behoort – voor de 3D-weergave. Zie `samenhang.py`."""
    return await samenhang_mod.samenhang(await resolve_bron(doel))


@router.get("/dekking")
async def get_dekking(doel: dict = Depends(doel_query), actor: str = Depends(actieve_userid)):
    return await store.dekking(await resolve_bron(doel))


@router.post("/lagen/batch")
async def post_batch(req: Batch, actor: str = Depends(actieve_userid)):
    return await store.batch(req, await resolve_bron(req.doel.model_dump()), actor)


@router.get("/elementen/{element_id}")
async def get_element(element_id: str, actor: str = Depends(actieve_userid)):
    result = await store.detail(element_id)
    # DB-identiteit/historie is waarheid; actualiteit volgt uit huidige gecontroleerde bron.
    owner = result["element"]["eigenaar_iri"]
    law = re.fullmatch(r"urn:bwb:(BWB[RV]\d+)(?::[^<>\s\"{}|^`\\]*)?", owner)
    if law is None:
        raise HTTPException(422, "Opgeslagen bronidentiteit is ongeldig.")
    snapshot = await resolve_bron({"bwb_id": law.group(1)})
    nodes = store.nodes_van(snapshot)
    result["element"]["verouderd"] = result["element"].get("verouderd", False) or any(
        a["bron_iri"] not in nodes or nodes[a["bron_iri"]]["bron_hash"] != a["bron_hash"]
        for a in result["element"]["ankers"])
    result["actuele_snapshot_id"] = snapshot["snapshot_id"]
    result["bronverwijzing"].update(snapshot_id=result["snapshot_id"],
                                    historisch=result["element"]["verouderd"])
    return result


@router.post("/elementen/{element_id}/beslissing")
async def post_beslissing(element_id: str, req: Beslissing, actor: str = Depends(actieve_userid)):
    existing = await store.detail(element_id)
    snapshot = await resolve_bron({"bron_iri": existing["element"]["eigenaar_iri"]})
    return await store.beslis(element_id, req, snapshot, actor)


class MensInvoer(BaseModel):
    doel: Doel
    snapshot_id: str
    verwachte_revisies: dict[str, int] = Field(default_factory=dict)
    element: Element


@router.post("/elementen", status_code=201)
async def post_element(req: MensInvoer, actor: str = Depends(actieve_userid)):
    batch = Batch(batch_id=uuid.uuid4().hex, doel=req.doel, snapshot_id=req.snapshot_id,
                  verwachte_revisies=req.verwachte_revisies, elementen=[req.element])
    result = await store.batch(batch, await resolve_bron(req.doel.model_dump()), actor, mens=True)
    return {"element": result["elementen"][0], "lagen": result["lagen"]}


@router.delete("/elementen/{element_id}")
async def delete_element(element_id: str, verwachte_revisie: int = Query(ge=0),
                         actor: str = Depends(actieve_userid)):
    return await store.verwijder(element_id, verwachte_revisie, actor)


class StatusInvoer(BaseModel):
    status: str
    verwachte_revisie: int = Field(ge=0)


@router.post("/lagen/{laag_id}/status")
async def post_status(laag_id: str, req: StatusInvoer, actor: str = Depends(actieve_userid)):
    layer = await store.laag_detail(laag_id)
    snapshot = await resolve_bron({"bron_iri": layer["bron_iri"]})
    return await store.zet_status(laag_id, req.status, req.verwachte_revisie, actor, snapshot)


@router.get("/lagen/{laag_id}/revisies")
async def get_revisies(laag_id: str, limit: int = Query(100, ge=1, le=500), actor: str = Depends(actieve_userid)):
    """De revisiehistorie van een laag, nieuwste eerst: per revisie wie, wanneer en welke acties.
    Alleen wat er gebeurde – de inhoud van de laag zoals die toen was, bewaart de api niet."""
    return await store.revisies(laag_id, limit)


@router.post("/zoeken")
async def post_zoeken(req: Zoekvraag, actor: str = Depends(actieve_userid)):
    from .annotatie_v2_zoeken import zoek
    return await zoek(req)


@router.get("/node-lagen")
async def node_lagen(mijn: bool = False, bwbId: str = "", limit: int = Query(50, ge=1, le=200),
                     offset: int = Query(0, ge=0), actor: str = Depends(actieve_userid)):
    return await store.overzicht(actor if mijn else None, bwbId, limit, offset)


class VerwijderInvoer(BaseModel):
    bron_iri: str
    snapshot_id: str
    verwachte_revisies: dict[str, int] = Field(default_factory=dict)


@router.post("/weergave/verwijder")
async def post_verwijder(req: VerwijderInvoer, actor: str = Depends(actieve_userid)):
    """Verwijder de annotatie van de bepaling in beeld – uit Postgres én uit de graaf. Elke gebruiker
    mag dit; het staat in de audit. Zie `annotatie_v2_store.verwijder_weergave` voor wat er meegaat."""
    # De bewaarde snapshot eerst: verwijderen hoort niet te hangen aan de bereikbaarheid van de
    # brongraaf. Alleen als deze stand nooit is weggeschreven, vragen we hem opnieuw op.
    # De bewaarde bronboom kan bij een ander doel zijn weggeschreven (het artikel, terwijl nu een lid in
    # beeld is); het doel is hier de gevraagde bronnode.
    try:
        bewaard = await store.historische_snapshot(req.snapshot_id)
        doel = store.nodes_van(bewaard).get(req.bron_iri)
        snapshot = {**bewaard, "doel": doel} if doel else None
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        snapshot = None
    if snapshot is None:
        snapshot = await resolve_bron({"bron_iri": req.bron_iri})
        if snapshot["snapshot_id"] != req.snapshot_id:
            raise HTTPException(409, "Bronstand gewijzigd; laad opnieuw vóór verwijderen.")
    return await store.verwijder_weergave(snapshot, req.verwachte_revisies, actor)


class ExportInvoer(BaseModel):
    bron_iri: str
    snapshot_id: str
    formaat: str = "json"


_EXPORT_MIME = {"json": "application/json", "csv": "text/csv; charset=utf-8", "pdf": "application/pdf",
                "trig": "application/trig"}


@router.post("/weergave/export")
async def post_export(req: ExportInvoer, actor: str = Depends(actieve_userid)):
    """De weergave als bestand: JSON (v3, met schema), CSV, PDF of TriG. De vorm staat in
    `annotatie_export`; hier alleen de bronstand, de audit en de keuze."""
    if req.formaat not in _EXPORT_MIME:
        raise HTTPException(422, "Kies json, csv, pdf of trig.")
    snapshot = await resolve_bron({"bron_iri": req.bron_iri})
    if snapshot["snapshot_id"] != req.snapshot_id:
        raise HTTPException(409, "Bronstand gewijzigd; laad opnieuw vóór exporteren.")
    view = await store.weergave(snapshot)
    view["audit"] = await store.audit_weergave(view)
    view["export"] = {"versie": export.EXPORT_VERSIE, "actor": actor, "op": store.db.utcnow().isoformat()}
    if req.formaat == "json":
        body = export.json_export(view, verklaringen())
    elif req.formaat == "csv":
        body = export.csv_export(view, verklaringen(), _provenance)
    elif req.formaat == "pdf":
        body = export.pdf_export(view, verklaringen())
    else:
        body = export.trig_export(await _laaggrafen(view))
    return Response(body, media_type=_EXPORT_MIME[req.formaat], headers={
        "Content-Disposition": f'attachment; filename="annotaties.{req.formaat}"'})


async def _laaggrafen(view: dict) -> list:
    """Per laag in de weergave de named graph zoals de projectie hem bouwt – dezelfde invoer
    (`laag_invoer`) en dezelfde `bouw_graaf`, zodat de export niets anders zegt dan de kennisgraaf."""
    from sqlalchemy import select

    from .graaf_projectie_v2 import bouw_graaf, graph_iri, laag_invoer
    uit = []
    ids = [laag["id"] for laag in view["lagen"]]
    async with store.leestransactie() as conn:
        rijen = (await conn.execute(select(store.db.annotatie_v2_lagen).where(
            store.db.annotatie_v2_lagen.c.id.in_(ids)))).mappings().all()
        for rij in sorted((dict(r) for r in rijen), key=lambda r: ids.index(r["id"])):
            elementen, dekking = await laag_invoer(conn, rij)
            uit.append((graph_iri(rij["id"]), bouw_graaf(rij, elementen, dekking=dekking)))
    return uit


@router.get("/export-schema")
async def get_export_schema(actor: str = Depends(actieve_userid)):
    """Het JSON-schema van de export (versie 3)."""
    return json.loads(export.SCHEMA_PAD.read_text(encoding="utf-8"))
