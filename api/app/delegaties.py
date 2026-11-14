"""Delegaties onder `/v1/delegaties` (ADR-016 §A5, ADR-012). De regisseur en de centrale agent van graph-qa starten
en sluiten ze; de werkplek leest ze. De router zit achter de client-bearer en vraagt een actieve gebruiker.

POST   /v1/delegaties                    – een delegatie starten (409 `delegatie_loopt_al` als het slot bezet is)
GET    /v1/delegaties?werkgebied_id=     – de laatste delegaties in een werkgebied
GET    /v1/delegaties?gesprek_id=        – de laatste delegaties van een eigen gesprek
GET    /v1/delegaties/{delegatie_id}     – één delegatie
PATCH  /v1/delegaties/{delegatie_id}     – hartslag (`loopt`) of afronden (`klaar`, `gestopt`, `mislukt`)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from . import delegatie_store as store
from .auth import require_client
from .delegatie_contracts import Delegatie, DelegatieStart, DelegatieWijziging
from .routers.auth import actieve_userid

router = APIRouter(prefix="/delegaties", tags=["delegaties"], dependencies=[Depends(require_client)])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Delegatie)
async def post_delegatie(req: DelegatieStart, user_id: str = Depends(actieve_userid)):
    return await store.start(user_id, req)


@router.get("", response_model=list[Delegatie])
async def get_delegaties(werkgebied_id: str | None = Query(None, max_length=64),
                         gesprek_id: str | None = Query(None, max_length=64),
                         limit: int = Query(20, ge=1, le=100), user_id: str = Depends(actieve_userid)):
    if (werkgebied_id is None) == (gesprek_id is None):
        raise HTTPException(422, {"fout": "werkgebied_of_gesprek",
                                  "melding": "Vraag de delegaties van één werkgebied of van één gesprek."})
    return await store.lijst(werkgebied_id=werkgebied_id, gesprek_id=gesprek_id, user_id=user_id, limit=limit)


@router.get("/{delegatie_id}", response_model=Delegatie)
async def get_delegatie(delegatie_id: str, user_id: str = Depends(actieve_userid)):
    return await store.haal(delegatie_id)


@router.patch("/{delegatie_id}", response_model=Delegatie)
async def patch_delegatie(delegatie_id: str, req: DelegatieWijziging, user_id: str = Depends(actieve_userid)):
    return await store.wijzig(delegatie_id, user_id, req)
