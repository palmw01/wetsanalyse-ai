"""Onderhoud van begrippen (spoor D, fase F1): herbeoordelen, herkoppelen, bevestigen en de dekking
van een werkgebied. Gedeeld zoals de werkgebieden; elke route vraagt een actieve gebruiker."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from . import begrip_onderhoud_store as store, werkgebied_store
from .auth import require_client
from .begrip_onderhoud_contracts import Bevestiging, BuitenBehandeling, Herkoppeling
from .routers.auth import actieve_userid
from .werkgebieden import resolve_bron

router = APIRouter(prefix="/werkgebieden/{werkgebied_id}", tags=["begrippen"],
                   dependencies=[Depends(require_client)])


@router.get("/herbeoordelingen")
async def get_herbeoordelingen(werkgebied_id: str, begrip_id: str | None = Query(None, max_length=64),
                               actor: str = Depends(actieve_userid)):
    return await store.herbeoordelingen(await werkgebied_store.haal(werkgebied_id), resolve_bron, begrip_id)


@router.post("/begrippen/{begrip_id}/koppelingen/{koppeling_id}/herkoppelen")
async def post_herkoppelen(werkgebied_id: str, begrip_id: str, koppeling_id: str, req: Herkoppeling,
                           actor: str = Depends(actieve_userid)):
    return await store.herkoppel(await werkgebied_store.haal(werkgebied_id), begrip_id, koppeling_id, req, actor,
                                 resolve_bron)


@router.post("/begrippen/{begrip_id}/koppelingen/{koppeling_id}/bevestigen")
async def post_bevestigen(werkgebied_id: str, begrip_id: str, koppeling_id: str, req: Bevestiging,
                          actor: str = Depends(actieve_userid)):
    return await store.bevestig(await werkgebied_store.haal(werkgebied_id), begrip_id, koppeling_id, req, actor,
                                resolve_bron)


@router.get("/dekking")
async def get_dekking(werkgebied_id: str, actor: str = Depends(actieve_userid)):
    return await store.dekking(await werkgebied_store.haal(werkgebied_id), resolve_bron)


@router.post("/dekking/buiten-behandeling")
async def post_buiten_behandeling(werkgebied_id: str, req: BuitenBehandeling, actor: str = Depends(actieve_userid)):
    return await store.zet_buiten_behandeling(await werkgebied_store.haal(werkgebied_id), req, actor, resolve_bron)


@router.delete("/dekking/buiten-behandeling/{element_id}")
async def delete_buiten_behandeling(werkgebied_id: str, element_id: str, actor: str = Depends(actieve_userid)):
    await werkgebied_store.haal(werkgebied_id)
    return await store.terug_in_behandeling(werkgebied_id, element_id, actor)
