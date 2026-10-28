"""Begripsrelaties en opvolging (spoor D, fase F2): relaties lezen, vastleggen, afwijzen, bevestigen en
weghalen; een begrip een nieuwe betekenis geven of twee begrippen combineren."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from . import begrip_relatie_store as store
from .auth import require_client
from .begrip_relatie_contracts import Combineren, NieuweBetekenis, Reden, RelatieInvoer
from .routers.auth import actieve_userid

router = APIRouter(prefix="/werkgebieden/{werkgebied_id}", tags=["begrippen"],
                   dependencies=[Depends(require_client)])


@router.get("/relaties")
async def get_relaties(werkgebied_id: str, begrip_id: str | None = Query(None, max_length=64),
                       actor: str = Depends(actieve_userid)):
    return await store.lijst(werkgebied_id, begrip_id)


@router.post("/relaties", status_code=201)
async def post_relatie(werkgebied_id: str, req: RelatieInvoer, actor: str = Depends(actieve_userid)):
    return await store.maak(werkgebied_id, req, actor)


@router.post("/relaties/voorstellen/{voorstel_id}/afwijzen")
async def post_afwijzen(werkgebied_id: str, voorstel_id: str, req: Reden, actor: str = Depends(actieve_userid)):
    return await store.wijs_af(werkgebied_id, voorstel_id, req.reden, actor)


@router.post("/relaties/{relatie_id}/bevestigen")
async def post_bevestigen(werkgebied_id: str, relatie_id: str, actor: str = Depends(actieve_userid)):
    return await store.bevestig(werkgebied_id, relatie_id, actor)


@router.delete("/relaties/{relatie_id}")
async def delete_relatie(werkgebied_id: str, relatie_id: str, actor: str = Depends(actieve_userid)):
    return await store.verwijder(werkgebied_id, relatie_id, actor)


@router.post("/begrippen/{begrip_id}/nieuwe-betekenis", status_code=201)
async def post_nieuwe_betekenis(werkgebied_id: str, begrip_id: str, req: NieuweBetekenis,
                                actor: str = Depends(actieve_userid)):
    return await store.nieuwe_betekenis(werkgebied_id, begrip_id, req, actor)


@router.post("/begrippen/{begrip_id}/combineren")
async def post_combineren(werkgebied_id: str, begrip_id: str, req: Combineren, actor: str = Depends(actieve_userid)):
    return await store.combineer(werkgebied_id, begrip_id, req, actor)
