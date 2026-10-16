"""Lex naast de kaart (spoor D, fase E), onder `/v1/werkgebieden/{id}/begrippen/{begrip_id}`: kaartruns
en de voorstellen per veld. Gedeeld zoals de begrippen; elke route vraagt een actieve gebruiker.

`…/kaart-runs/{run}` (GET met `invoer`), `…/loopt`, `…/mislukt` en `…/uitkomst` zijn voor graph-qa; de
BFF van de werkplek laat ze niet door (`frontend/lib/werkgebied.ts:isWerkgebiedRoute`)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from . import begrip_voorstel_store as store, werkgebied_store
from .auth import require_client
from .begrip_voorstel_contracts import KaartMislukt, KaartRunStart, KaartUitkomst, VoorstelAfwijzing, VoorstelOvername
from .routers.auth import actieve_userid
from .werkgebieden import resolve_bron

router = APIRouter(prefix="/werkgebieden/{werkgebied_id}/begrippen/{begrip_id}", tags=["begrip-voorstellen"],
                   dependencies=[Depends(require_client)])


@router.post("/kaart-runs")
async def post_run(werkgebied_id: str, begrip_id: str, req: KaartRunStart, response: Response,
                   actor: str = Depends(actieve_userid)):
    run, nieuw = await store.start(await werkgebied_store.haal(werkgebied_id), begrip_id, req, actor, resolve_bron)
    response.status_code = 201 if nieuw else 200
    return {**run, "nieuw": nieuw}


@router.get("/kaart-runs/{run_id}")
async def get_run(werkgebied_id: str, begrip_id: str, run_id: str, invoer: bool = False,
                  actor: str = Depends(actieve_userid)):
    return await store.haal_run(werkgebied_id, begrip_id, run_id, met_invoer=invoer)


@router.post("/kaart-runs/{run_id}/loopt")
async def post_loopt(werkgebied_id: str, begrip_id: str, run_id: str, actor: str = Depends(actieve_userid)):
    return await store.loopt(werkgebied_id, begrip_id, run_id)


@router.post("/kaart-runs/{run_id}/mislukt")
async def post_mislukt(werkgebied_id: str, begrip_id: str, run_id: str, req: KaartMislukt,
                       actor: str = Depends(actieve_userid)):
    return await store.mislukt(werkgebied_id, begrip_id, run_id, req.reden)


@router.put("/kaart-runs/{run_id}/uitkomst")
async def put_uitkomst(werkgebied_id: str, begrip_id: str, run_id: str, req: KaartUitkomst,
                       actor: str = Depends(actieve_userid)):
    return await store.zet_uitkomst(werkgebied_id, begrip_id, run_id, req, actor, resolve_bron)


@router.get("/voorstellen")
async def get_voorstellen(werkgebied_id: str, begrip_id: str, actor: str = Depends(actieve_userid)):
    """De voorstellen van Lex bij dit begrip, per actie de laatste run, en schatting en budget voor de knoppen."""
    return {**await store.voorstellen(werkgebied_id, begrip_id),
            "schatting": await store.schatting(actor), "budget": await store.budget(actor)}


@router.post("/voorstellen/{voorstel_id}/overnemen")
async def post_overnemen(werkgebied_id: str, begrip_id: str, voorstel_id: str, req: VoorstelOvername,
                         actor: str = Depends(actieve_userid)):
    return await store.overnemen(werkgebied_id, begrip_id, voorstel_id, req, actor)


@router.post("/voorstellen/{voorstel_id}/afwijzen")
async def post_afwijzen(werkgebied_id: str, begrip_id: str, voorstel_id: str, req: VoorstelAfwijzing,
                        actor: str = Depends(actieve_userid)):
    return await store.afwijzen(werkgebied_id, begrip_id, voorstel_id, req.reden, actor)
