"""Regies onder `/v1/werkgebieden/{id}/regies` (ADR-012). De regisseur van graph-qa start en sluit ze; de werkplek
leest ze. Zoals de werkgebieden zit de router achter de client-bearer en vraagt hij een actieve gebruiker.

POST   …/regies              – een regie starten (409 `regie_loopt_al` als er al een loopt)
GET    …/regies              – de laatste regies in het werkgebied
GET    …/regies/{regie_id}   – één regie
PATCH  …/regies/{regie_id}   – hartslag (`loopt`) of afronden (`klaar`, `gestopt`, `mislukt`)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from . import regie_store as store
from .auth import require_client
from .regie_contracts import Regie, RegieStart, RegieWijziging
from .routers.auth import actieve_userid

router = APIRouter(prefix="/werkgebieden/{werkgebied_id}/regies", tags=["regies"],
                   dependencies=[Depends(require_client)])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Regie)
async def post_regie(werkgebied_id: str, req: RegieStart, user_id: str = Depends(actieve_userid)):
    return await store.start(werkgebied_id, user_id, req)


@router.get("", response_model=list[Regie])
async def get_regies(werkgebied_id: str, limit: int = Query(20, ge=1, le=100),
                     user_id: str = Depends(actieve_userid)):
    return await store.lijst(werkgebied_id, limit)


@router.get("/{regie_id}", response_model=Regie)
async def get_regie(werkgebied_id: str, regie_id: str, user_id: str = Depends(actieve_userid)):
    return await store.haal(werkgebied_id, regie_id)


@router.patch("/{regie_id}", response_model=Regie)
async def patch_regie(werkgebied_id: str, regie_id: str, req: RegieWijziging,
                      user_id: str = Depends(actieve_userid)):
    return await store.wijzig(werkgebied_id, regie_id, user_id, req)
