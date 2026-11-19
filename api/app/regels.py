"""Afleidingsregels-API (activiteit 3b, ADR-018), onder `/v1/werkgebieden/{id}/regels` en `…/parameterwaarden`.
Gedeeld zoals de begrippen; elke route vraagt een actieve gebruiker, die als actor in de revisies en de audit komt.
Stijl C: de store gooit de fouten, de router is dun."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from . import regel_store as store, werkgebied_store
from .auth import require_client
from .regel_contracts import (
    Accordering, DragersToevoegen, DragerWijziging, ParameterWaardeInvoer, RegelAanmaak, RegelWijziging, Revisie,
)
from .routers.auth import actieve_userid
from .werkgebieden import resolve_bron

router = APIRouter(prefix="/werkgebieden/{werkgebied_id}", tags=["afleidingsregels"],
                   dependencies=[Depends(require_client)])


class Afwijzing(Revisie):
    reden: str = ""


@router.get("/regels")
async def get_lijst(werkgebied_id: str, actor: str = Depends(actieve_userid)):
    return {"regels": await store.lijst(werkgebied_id)}


@router.post("/regels", status_code=201)
async def post_regel(werkgebied_id: str, req: RegelAanmaak, actor: str = Depends(actieve_userid)):
    return await store.maak(await werkgebied_store.haal(werkgebied_id), req, actor, resolve_bron)


# Vóór `/regels/{regel_id}`, anders leest de router "hierarchie" als een regel-id.
@router.get("/regels/hierarchie")
async def get_hierarchie(werkgebied_id: str, actor: str = Depends(actieve_userid)):
    """De afleidingshiërarchie, afgeleid: pijlen, de volgorde van onder naar boven, basisgegevens en signalen."""
    return await store.hierarchie(werkgebied_id)


@router.get("/regels/{regel_id}")
async def get_regel(werkgebied_id: str, regel_id: str, actor: str = Depends(actieve_userid)):
    return await store.haal(werkgebied_id, regel_id)


@router.patch("/regels/{regel_id}")
async def patch_regel(werkgebied_id: str, regel_id: str, req: RegelWijziging, actor: str = Depends(actieve_userid)):
    return await store.wijzig(werkgebied_id, regel_id, req, actor)


@router.delete("/regels/{regel_id}")
async def delete_regel(werkgebied_id: str, regel_id: str, verwachte_revisie: int = Query(ge=1),
                       actor: str = Depends(actieve_userid)):
    return await store.verwijder(werkgebied_id, regel_id, verwachte_revisie, actor)


@router.post("/regels/{regel_id}/dragers")
async def post_dragers(werkgebied_id: str, regel_id: str, req: DragersToevoegen, actor: str = Depends(actieve_userid)):
    await store.haal(werkgebied_id, regel_id)          # 404 vóór de graaf wordt gevraagd
    return await store.voeg_dragers_toe(await werkgebied_store.haal(werkgebied_id), regel_id, req, actor, resolve_bron)


@router.patch("/regels/{regel_id}/dragers/{drager_id}")
async def patch_drager(werkgebied_id: str, regel_id: str, drager_id: str, req: DragerWijziging,
                       actor: str = Depends(actieve_userid)):
    return await store.wijzig_drager(werkgebied_id, regel_id, drager_id, req, actor)


@router.delete("/regels/{regel_id}/dragers/{drager_id}")
async def delete_drager(werkgebied_id: str, regel_id: str, drager_id: str, verwachte_revisie: int = Query(ge=1),
                        actor: str = Depends(actieve_userid)):
    return await store.verwijder_drager(werkgebied_id, regel_id, drager_id, verwachte_revisie, actor)


@router.post("/regels/{regel_id}/accorderen")
async def post_accorderen(werkgebied_id: str, regel_id: str, req: Accordering, actor: str = Depends(actieve_userid)):
    return await store.accordeer(werkgebied_id, regel_id, req.verwachte_revisie, req.reden, actor)


@router.post("/regels/{regel_id}/heropenen")
async def post_heropenen(werkgebied_id: str, regel_id: str, req: Revisie, actor: str = Depends(actieve_userid)):
    return await store.heropen(werkgebied_id, regel_id, req.verwachte_revisie, actor)


@router.post("/regels/{regel_id}/afwijzen")
async def post_afwijzen(werkgebied_id: str, regel_id: str, req: Afwijzing, actor: str = Depends(actieve_userid)):
    return await store.wijs_af(werkgebied_id, regel_id, req.verwachte_revisie, req.reden, actor)


@router.get("/regels/{regel_id}/revisies")
async def get_revisies(werkgebied_id: str, regel_id: str, limit: int = Query(100, ge=1, le=500),
                       actor: str = Depends(actieve_userid)):
    return {"revisies": await store.revisies(werkgebied_id, regel_id, limit)}


@router.get("/parameterwaarden")
async def get_parameterwaarden(werkgebied_id: str, actor: str = Depends(actieve_userid)):
    return {"parameterwaarden": await store.parameterwaarden(werkgebied_id)}


@router.post("/parameterwaarden", status_code=201)
async def post_parameterwaarde(werkgebied_id: str, req: ParameterWaardeInvoer, actor: str = Depends(actieve_userid)):
    return await store.voeg_parameterwaarde_toe(werkgebied_id, req, actor)


@router.delete("/parameterwaarden/{waarde_id}")
async def delete_parameterwaarde(werkgebied_id: str, waarde_id: str, actor: str = Depends(actieve_userid)):
    return await store.verwijder_parameterwaarde(werkgebied_id, waarde_id, actor)
