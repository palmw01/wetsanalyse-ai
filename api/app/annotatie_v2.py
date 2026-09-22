"""Bronnode-API. Elke lees- en schrijfactie vereist een actieve gebruiker."""
from __future__ import annotations

import csv
import io
import json
import re
import uuid
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
import httpx
from bronmodel import BronFout

from . import annotatie_v2_store as store
from .annotatie_v2_contracts import Batch, Beslissing, Doel, Element, Zoekvraag
from .auth import require_client
from .bron_resolver import resolve_bron as _resolve_bron
from .routers.auth import actieve_userid
from .annotatie_v2_contract_guard import contract_versie, require_v2

router = APIRouter(prefix="/annotatie", tags=["annotatie-bronnodes"],
                   dependencies=[Depends(require_client), Depends(require_v2)])


async def resolve_bron(doel: dict) -> dict:
    try:
        return await _resolve_bron(doel)
    except BronFout as exc:
        raise HTTPException(422, str(exc)) from exc
    except (httpx.HTTPError, ConnectionError) as exc:
        raise HTTPException(503, "De brongraaf is tijdelijk niet beschikbaar.") from exc


def doel_query(bron_iri: str = "", bwb_id: str = "", artikel: str = "", lid: str = "") -> dict:
    return dict(bron_iri=bron_iri, bwb_id=bwb_id, artikel=artikel, lid=lid)


@router.get("/capabilities")
async def capabilities(actor: str = Depends(actieve_userid)):
    return {"schema_versie": contract_versie(), "bronnodes_actief": contract_versie() == 2,
            "schrijfcontract": "bronnode-v2" if contract_versie() == 2 else "artikel-v1"}


@router.get("/weergave")
async def get_weergave(doel: dict = Depends(doel_query), actor: str = Depends(actieve_userid)):
    return await store.weergave(await resolve_bron(doel))


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


@router.post("/zoeken")
async def post_zoeken(req: Zoekvraag, actor: str = Depends(actieve_userid)):
    from .annotatie_v2_zoeken import zoek
    return await zoek(req)


@router.get("/node-lagen")
async def node_lagen(mijn: bool = False, bwbId: str = "", limit: int = Query(50, ge=1, le=200),
                     offset: int = Query(0, ge=0), actor: str = Depends(actieve_userid)):
    return await store.overzicht(actor if mijn else None, bwbId, limit, offset)


class ExportInvoer(BaseModel):
    bron_iri: str
    snapshot_id: str
    formaat: str = "json"


@router.post("/weergave/export")
async def post_export(req: ExportInvoer, actor: str = Depends(actieve_userid)):
    snapshot = await resolve_bron({"bron_iri": req.bron_iri})
    if snapshot["snapshot_id"] != req.snapshot_id:
        raise HTTPException(409, "Bronstand gewijzigd; laad opnieuw vóór exporteren.")
    view = await store.weergave(snapshot)
    view["audit"] = await store.audit_weergave(view)
    view["export"] = {"versie": 2, "actor": actor, "op": store.db.utcnow().isoformat()}
    if req.formaat == "json":
        body = json.dumps(view, ensure_ascii=False, indent=2).encode()
        mime = "application/json"
    elif req.formaat == "csv":
        text = io.StringIO()
        writer = csv.writer(text)
        writer.writerow(["soort", "id", "eigenaar_iri", "klasse", "tekst", "lifecycle", "snapshot_id", "ankers", "beslissingen", "herkomst", "provenance", "laagstatus"])
        # Quotes do not neutralise spreadsheet formula execution.
        def cell(value):
            value = str(value)
            return "'" + value if value[:1] in {"=", "+", "-", "@", "\t", "\r"} else value
        for e in view["elementen"]:
            laagstatus = next((l["status"] for l in view["lagen"] if l["id"] == e["laag_id"]), "")
            writer.writerow(["element"] + [cell(e.get(k, "")) for k in
                ("id", "eigenaar_iri", "klasse", "tekst", "lifecycle", "snapshot_id")]
                + [json.dumps(e["ankers"], ensure_ascii=False), json.dumps(e["beslissingen"], ensure_ascii=False),
                   e["herkomst"], json.dumps(e.get("geproduceerd_door", {}), ensure_ascii=False), laagstatus])
        for ref in view["verwijzingen"]:
            writer.writerow(["verwijzing", ref["id"], ref["eigenaar_iri"], ref["klasse"], ref["label"], "", req.snapshot_id,
                             "[]", "[]", "", "", ""])
        for segment in view["segmenten"]:
            writer.writerow(["brontekst", "", segment["bron_iri"], "", cell(segment["tekst"]), "", req.snapshot_id,
                             "[]", "[]", "", "", ""])
        for audit in view["audit"]:
            writer.writerow(["audit", audit.get("element_id", ""), "", "", "", audit["actie"], req.snapshot_id,
                             "[]", json.dumps(audit, ensure_ascii=False), "", "", ""])
        body, mime = text.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8"
    elif req.formaat == "pdf":
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        output = io.BytesIO()
        styles = getSampleStyleSheet()
        story = [Paragraph(escape(str(view["doel"].get("label", "Annotaties"))), styles["Title"])]
        story.append(Paragraph(escape("Bronstand: " + req.snapshot_id), styles["BodyText"]))
        for layer in view["lagen"]:
            story.append(Paragraph(escape(f"{layer['bron_iri']}: {layer['status']} (revisie {layer['revisie']})"), styles["BodyText"]))
        for segment in view["segmenten"]:
            story.extend([Paragraph(escape(segment.get("tekst", "")), styles["BodyText"]), Spacer(1, 10)])
        for e in view["elementen"]:
            story.extend([Paragraph(escape(f"{e['klasse']}: {e['tekst']} ({e['lifecycle']})"), styles["BodyText"]),
                          Paragraph(escape("Eigenaar: " + e["eigenaar_iri"]), styles["BodyText"]),
                          Paragraph(escape(e.get("toelichting", "")), styles["BodyText"]),
                          Paragraph(escape("Herkomst: " + e["herkomst"] + "; " + json.dumps(e.get("geproduceerd_door", {}), ensure_ascii=False)), styles["BodyText"]),
                          Paragraph(escape("Beoordelingen: " + json.dumps(e["beslissingen"], ensure_ascii=False)), styles["BodyText"]), Spacer(1, 8)])
            for anchor in e["ankers"]:
                story.append(Paragraph(escape(f"Anker: {anchor['bron_iri']} [{anchor['start']}, {anchor['eind']})"), styles["BodyText"]))
                story.append(Paragraph(escape("Bronhash: " + anchor["bron_hash"]), styles["BodyText"]))
                story.append(Paragraph(escape("Fragment: " + anchor["tekst"]), styles["BodyText"]))
        if view["verwijzingen"]:
            story.append(Paragraph("Dit bereik bevat verwijzingen naar annotaties met een ruimere bronselectie.", styles["BodyText"]))
            for ref in view["verwijzingen"]:
                story.append(Paragraph(escape(f"{ref['id']}: {ref['klasse']} — {ref['eigenaar_iri']}"), styles["BodyText"]))
        if view["audit"]:
            story.append(Paragraph("Historie", styles["Heading2"]))
            for audit in view["audit"]:
                story.append(Paragraph(escape(json.dumps(audit, ensure_ascii=False)), styles["BodyText"]))
        SimpleDocTemplate(output).build(story)
        body, mime = output.getvalue(), "application/pdf"
    else:
        raise HTTPException(422, "Kies json, csv of pdf.")
    return Response(body, media_type=mime, headers={
        "Content-Disposition": f'attachment; filename="annotaties.{req.formaat}"'})
