"""Begrippen-API (spoor D, levering 2), onder `/v1/werkgebieden/{id}/begrippen`. Gedeeld tussen
analisten zoals de werkgebieden; elke route vraagt een actieve gebruiker, die als actor in de
revisies en de audit komt."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response

from . import begrip_store as store, werkgebied_store
from .auth import require_client
from .begrip_contracts import BegripInvoer, BegripWijziging, KoppelInvoer, KoppelWijziging, Revisie
from .routers.auth import actieve_userid
from .werkgebieden import resolve_bron

router = APIRouter(prefix="/werkgebieden/{werkgebied_id}/begrippen", tags=["begrippen"],
                   dependencies=[Depends(require_client)])

_MIME = {"json": "application/json", "csv": "text/csv; charset=utf-8"}


@router.get("")
async def get_lijst(werkgebied_id: str, actor: str = Depends(actieve_userid)):
    return {"kader_iri": store.kader_iri(werkgebied_id), "begrippen": await store.lijst(werkgebied_id),
            # Welk begrip elk element primair aanduidt: de inventaris toont het bij het element.
            "primair": await store.primaire_duidingen(werkgebied_id)}


@router.post("", status_code=201)
async def post_begrip(werkgebied_id: str, req: BegripInvoer, actor: str = Depends(actieve_userid)):
    return await store.maak(await werkgebied_store.haal(werkgebied_id), req, actor, resolve_bron)


# Vóór `/{begrip_id}`, anders leest de router "export" als een begrip-id.
@router.get("/export")
async def get_export(werkgebied_id: str, formaat: Literal["json", "csv"] = "json",
                     actor: str = Depends(actieve_userid)):
    data = await store.export(werkgebied_id, actor)
    body = store.json_export(data) if formaat == "json" else store.csv_export(data)
    return Response(body, media_type=_MIME[formaat],
                    headers={"Content-Disposition": f'attachment; filename="begrippen.{formaat}"'})


@router.get("/{begrip_id}")
async def get_begrip(werkgebied_id: str, begrip_id: str, actor: str = Depends(actieve_userid)):
    return await store.haal(werkgebied_id, begrip_id)


@router.patch("/{begrip_id}")
async def patch_begrip(werkgebied_id: str, begrip_id: str, req: BegripWijziging,
                       actor: str = Depends(actieve_userid)):
    return await store.wijzig(werkgebied_id, begrip_id, req, actor)


@router.delete("/{begrip_id}")
async def delete_begrip(werkgebied_id: str, begrip_id: str, verwachte_revisie: int = Query(ge=1),
                        actor: str = Depends(actieve_userid)):
    return await store.verwijder(werkgebied_id, begrip_id, verwachte_revisie, actor)


@router.post("/{begrip_id}/koppelingen")
async def post_koppelingen(werkgebied_id: str, begrip_id: str, req: KoppelInvoer,
                           actor: str = Depends(actieve_userid)):
    await store.haal(werkgebied_id, begrip_id)          # 404 vóór de graaf wordt gevraagd
    return await store.koppel(await werkgebied_store.haal(werkgebied_id), begrip_id, req, actor, resolve_bron)


@router.patch("/{begrip_id}/koppelingen/{koppeling_id}")
async def patch_koppeling(werkgebied_id: str, begrip_id: str, koppeling_id: str, req: KoppelWijziging,
                          actor: str = Depends(actieve_userid)):
    return await store.wijzig_koppeling(werkgebied_id, begrip_id, koppeling_id, req, actor)


@router.delete("/{begrip_id}/koppelingen/{koppeling_id}")
async def delete_koppeling(werkgebied_id: str, begrip_id: str, koppeling_id: str,
                           verwachte_revisie: int = Query(ge=1), actor: str = Depends(actieve_userid)):
    return await store.ontkoppel(werkgebied_id, begrip_id, koppeling_id, verwachte_revisie, actor)


@router.post("/{begrip_id}/accorderen")
async def post_accorderen(werkgebied_id: str, begrip_id: str, req: Revisie, actor: str = Depends(actieve_userid)):
    return await store.accordeer(werkgebied_id, begrip_id, req.verwachte_revisie, actor)


@router.post("/{begrip_id}/heropenen")
async def post_heropenen(werkgebied_id: str, begrip_id: str, req: Revisie, actor: str = Depends(actieve_userid)):
    return await store.heropen(werkgebied_id, begrip_id, req.verwachte_revisie, actor)


@router.get("/{begrip_id}/revisies")
async def get_revisies(werkgebied_id: str, begrip_id: str, limit: int = Query(100, ge=1, le=500),
                       actor: str = Depends(actieve_userid)):
    return {"revisies": await store.revisies(werkgebied_id, begrip_id, limit)}
