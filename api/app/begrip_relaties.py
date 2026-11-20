"""Begripsrelaties en opvolging (spoor D, fase F2): relaties lezen, vastleggen, afwijzen, bevestigen en
weghalen; een begrip een nieuwe betekenis geven of twee begrippen combineren."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query

from . import begrip_relatie_store as store
from .auth import require_client
from .begrip_relatie_contracts import Combineren, CombinerenGeneriek, NieuweBetekenis, Reden, RelatieInvoer
from .begrippen import Vorm as BegripVorm, _in_vorm as _begrip_in_vorm
from .routers.auth import actieve_userid

router = APIRouter(prefix="/werkgebieden/{werkgebied_id}", tags=["begrippen"],
                   dependencies=[Depends(require_client)])

Vorm = Literal["lijst", "kort"]


def _in_vorm(lijst: dict, vorm: str) -> dict:
    """`?vorm=kort`: alleen de tellingen in plaats van alle relaties en voorstellen met hun bewijs. Wie veel besluiten na
    elkaar neemt (een MCP-client) leest anders bij elk besluit de hele lijst terug."""
    if vorm != "kort":
        return lijst
    rel = lijst.get("relaties") or []
    return {"relaties": sum(r.get("beoordeling") != "afgewezen" for r in rel),
            "afgewezen": sum(r.get("beoordeling") == "afgewezen" for r in rel),
            "voorstellen": len(lijst.get("voorstellen") or [])}


@router.get("/relaties")
async def get_relaties(werkgebied_id: str, begrip_id: str | None = Query(None, max_length=64),
                       actor: str = Depends(actieve_userid)):
    return await store.lijst(werkgebied_id, begrip_id)


@router.post("/relaties", status_code=201)
async def post_relatie(werkgebied_id: str, req: RelatieInvoer, vorm: Vorm = "lijst",
                       actor: str = Depends(actieve_userid)):
    return _in_vorm(await store.maak(werkgebied_id, req, actor), vorm)


@router.post("/relaties/voorstellen/{voorstel_id}/afwijzen")
async def post_afwijzen(werkgebied_id: str, voorstel_id: str, req: Reden, vorm: Vorm = "lijst",
                        actor: str = Depends(actieve_userid)):
    return _in_vorm(await store.wijs_af(werkgebied_id, voorstel_id, req.reden, actor), vorm)


@router.post("/relaties/{relatie_id}/bevestigen")
async def post_bevestigen(werkgebied_id: str, relatie_id: str, vorm: Vorm = "lijst",
                          actor: str = Depends(actieve_userid)):
    return _in_vorm(await store.bevestig(werkgebied_id, relatie_id, actor), vorm)


@router.delete("/relaties/{relatie_id}")
async def delete_relatie(werkgebied_id: str, relatie_id: str, vorm: Vorm = "lijst",
                         actor: str = Depends(actieve_userid)):
    return _in_vorm(await store.verwijder(werkgebied_id, relatie_id, actor), vorm)


@router.post("/begrippen/{begrip_id}/nieuwe-betekenis", status_code=201)
async def post_nieuwe_betekenis(werkgebied_id: str, begrip_id: str, req: NieuweBetekenis, vorm: BegripVorm = "kaart",
                                actor: str = Depends(actieve_userid)):
    return _begrip_in_vorm(await store.nieuwe_betekenis(werkgebied_id, begrip_id, req, actor), vorm)


@router.post("/begrippen/{begrip_id}/combineren-generiek")
async def post_combineren_generiek(werkgebied_id: str, begrip_id: str, req: CombinerenGeneriek,
                                   actor: str = Depends(actieve_userid)):
    """Een lokaal begrip gaat op in een generiek begrip (ADR-006)."""
    return await store.combineer_met_generiek(werkgebied_id, begrip_id, req, actor)


@router.post("/begrippen/gebruik/{begrip_id}/opvolger")
async def post_opvolger_overnemen(werkgebied_id: str, begrip_id: str, actor: str = Depends(actieve_userid)):
    """Dit werkgebied gaat over op de opvolger van een vervangen generiek begrip."""
    return await store.opvolger_overnemen(werkgebied_id, begrip_id, actor)


@router.post("/begrippen/{begrip_id}/combineren")
async def post_combineren(werkgebied_id: str, begrip_id: str, req: Combineren, vorm: BegripVorm = "kaart",
                          actor: str = Depends(actieve_userid)):
    return _begrip_in_vorm(await store.combineer(werkgebied_id, begrip_id, req, actor), vorm)
