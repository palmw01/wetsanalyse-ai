"""Afleidingsregels-API (activiteit 3b, ADR-018), onder `/v1/werkgebieden/{id}/regels` en `…/parameterwaarden`.
Gedeeld zoals de begrippen; elke route vraagt een actieve gebruiker, die als actor in de revisies en de audit komt.
Stijl C: de store gooit de fouten, de router is dun."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query

from . import regel_store as store, werkgebied_store
from .auth import require_client
from .regel_contracts import (
    Accordering, Afwijzing, DragersToevoegen, DragerWijziging, ParameterWaardeInvoer, RegelAanmaak, RegelWijziging,
    Revisie, VoorbeeldBeoordeling,
)
from .routers.auth import actieve_userid
from .werkgebieden import resolve_bron

router = APIRouter(prefix="/werkgebieden/{werkgebied_id}", tags=["afleidingsregels"],
                   dependencies=[Depends(require_client)])
#: De regels over werkgebieden heen, alleen lezen: het overzicht in de zijbalk (zoals `GET /v1/begrippen`).
overzicht_router = APIRouter(prefix="/regels", tags=["afleidingsregels"], dependencies=[Depends(require_client)])

RegelStatusFilter = Literal["concept", "geaccordeerd", "geaccordeerd_als_beleidsregel", "afgewezen", "vervangen"]
#: `kort`: alleen de stand (revisie, status, poort, signalen; bij een drager ook die drager), B1. De standaard blijft de
#: kaart, want de werkplek leest die.
Vorm = Literal["volledig", "kort"]


def _vorm(regel: dict, vorm: str, drager_id: str | None = None) -> dict:
    return store.kort(regel, drager_id) if vorm == "kort" else regel


@overzicht_router.get("")
async def get_overzicht(q: str = Query("", max_length=200), status: list[RegelStatusFilter] = Query(default=[]),
                        werkgebied_id: str | None = Query(None, max_length=64), mijn: bool = False,
                        actor: str = Depends(actieve_userid)):
    return await store.overzicht(q, list(status), werkgebied_id, actor if mijn else None)


@router.get("/regels")
async def get_lijst(werkgebied_id: str, vorm: Vorm = "volledig", actor: str = Depends(actieve_userid)):
    return {"regels": [_vorm(r, vorm) for r in await store.lijst(werkgebied_id)]}


@router.post("/regels", status_code=201)
async def post_regel(werkgebied_id: str, req: RegelAanmaak, vorm: Vorm = "volledig", actor: str = Depends(actieve_userid)):
    return _vorm(await store.maak(await werkgebied_store.haal(werkgebied_id), req, actor, resolve_bron), vorm)


# Vóór `/regels/{regel_id}`, anders leest de router "hierarchie" als een regel-id.
@router.get("/regels/hierarchie")
async def get_hierarchie(werkgebied_id: str, actor: str = Depends(actieve_userid)):
    """De afleidingshiërarchie, afgeleid: pijlen, de volgorde van onder naar boven, basisgegevens en signalen."""
    return await store.hierarchie(werkgebied_id)


@router.get("/regels/{regel_id}")
async def get_regel(werkgebied_id: str, regel_id: str, vorm: Vorm = "volledig", actor: str = Depends(actieve_userid)):
    return _vorm(await store.haal(werkgebied_id, regel_id), vorm)


@router.get("/regels/{regel_id}/poort")
async def get_poort(werkgebied_id: str, regel_id: str, actor: str = Depends(actieve_userid)):
    """Wat er openstaat voor accorderen, zonder de kaart (B1): de stand, de poort, de signalen en de gaten."""
    regel = await store.haal(werkgebied_id, regel_id)
    return {**store.stand(regel), "gaten": regel["gaten"]}


@router.get("/regels/{regel_id}/dragers")
async def get_dragers(werkgebied_id: str, regel_id: str, actor: str = Depends(actieve_userid)):
    """De dragers smal (B1): per drager rol, geval, oordeel, actualiteit, klasse, tekst en vindplaats, zonder ankers."""
    regel = await store.haal(werkgebied_id, regel_id)
    return {"id": regel["id"], "revisie": regel["revisie"], "status": regel["status"],
            "dragers": [store.smalle_drager(d) for d in regel["dragers"]]}


@router.patch("/regels/{regel_id}")
async def patch_regel(werkgebied_id: str, regel_id: str, req: RegelWijziging, vorm: Vorm = "volledig",
                      actor: str = Depends(actieve_userid)):
    werkgebied = await werkgebied_store.haal(werkgebied_id)
    return _vorm(await store.wijzig(werkgebied, regel_id, req, actor, resolve_bron), vorm)


@router.post("/regels/{regel_id}/voorbeelden/{nr}/oordeel")
async def post_voorbeeld_oordeel(werkgebied_id: str, regel_id: str, nr: int, req: VoorbeeldBeoordeling,
                                 vorm: Vorm = "volledig", actor: str = Depends(actieve_userid)):
    """Het oordeel over voorbeeld `nr` (vanaf 1). De PATCH van de regel zet nooit een oordeel (B4)."""
    return _vorm(await store.beoordeel_voorbeeld(werkgebied_id, regel_id, nr, req, actor), vorm)


@router.delete("/regels/{regel_id}")
async def delete_regel(werkgebied_id: str, regel_id: str, verwachte_revisie: int = Query(ge=1),
                       actor: str = Depends(actieve_userid)):
    return await store.verwijder(werkgebied_id, regel_id, verwachte_revisie, actor)


@router.post("/regels/{regel_id}/dragers")
async def post_dragers(werkgebied_id: str, regel_id: str, req: DragersToevoegen, vorm: Vorm = "volledig",
                       actor: str = Depends(actieve_userid)):
    await store.haal(werkgebied_id, regel_id)          # 404 vóór de graaf wordt gevraagd
    return _vorm(await store.voeg_dragers_toe(await werkgebied_store.haal(werkgebied_id), regel_id, req, actor,
                                              resolve_bron), vorm)


@router.patch("/regels/{regel_id}/dragers/{drager_id}")
async def patch_drager(werkgebied_id: str, regel_id: str, drager_id: str, req: DragerWijziging, vorm: Vorm = "volledig",
                       actor: str = Depends(actieve_userid)):
    return _vorm(await store.wijzig_drager(werkgebied_id, regel_id, drager_id, req, actor), vorm, drager_id)


@router.delete("/regels/{regel_id}/dragers/{drager_id}")
async def delete_drager(werkgebied_id: str, regel_id: str, drager_id: str, verwachte_revisie: int = Query(ge=1),
                        vorm: Vorm = "volledig", actor: str = Depends(actieve_userid)):
    return _vorm(await store.verwijder_drager(werkgebied_id, regel_id, drager_id, verwachte_revisie, actor), vorm)


@router.post("/regels/{regel_id}/accorderen")
async def post_accorderen(werkgebied_id: str, regel_id: str, req: Accordering, vorm: Vorm = "volledig",
                          actor: str = Depends(actieve_userid)):
    return _vorm(await store.accordeer(werkgebied_id, regel_id, req.verwachte_revisie, req.reden, actor), vorm)


@router.post("/regels/{regel_id}/heropenen")
async def post_heropenen(werkgebied_id: str, regel_id: str, req: Revisie, vorm: Vorm = "volledig",
                         actor: str = Depends(actieve_userid)):
    return _vorm(await store.heropen(werkgebied_id, regel_id, req.verwachte_revisie, actor), vorm)


@router.post("/regels/{regel_id}/afwijzen")
async def post_afwijzen(werkgebied_id: str, regel_id: str, req: Afwijzing, vorm: Vorm = "volledig",
                        actor: str = Depends(actieve_userid)):
    return _vorm(await store.wijs_af(werkgebied_id, regel_id, req, actor), vorm)


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
