"""Voorstellen van Lex (spoor D, levering 3) onder `/v1/werkgebieden/{id}`: runs van de
begrippenketen en de betekenisgroepen. Gedeeld zoals de werkgebieden; elke route vraagt een actieve
gebruiker, die als actor in de audit komt.

De routes `…/uitkomst`, `…/loopt`, `…/mislukt`, `…/batches/{id}` en `…/verdieping` (PUT) zijn voor graph-qa; de BFF van de werkplek laat ze
niet door (`frontend/lib/werkgebied.ts:isWerkgebiedRoute`), en de api toetst de uitkomst tegen het
eigen manifest."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from . import begrippen_run_store as store, begrippen_verdieping as verdieping, werkgebied_store
from .auth import require_client
from .begrippen_run_contracts import (
    BatchInvoer, GroepBesluit, GroepKoppeling, MisluktInvoer, Overname, UitkomstInvoer, VerdiepingInvoer, VraagBesluit,
)
from .routers.auth import actieve_userid
from .werkgebieden import resolve_bron

router = APIRouter(prefix="/werkgebieden/{werkgebied_id}", tags=["begrippen-runs"],
                   dependencies=[Depends(require_client)])


@router.post("/begrippen-runs")
async def post_run(werkgebied_id: str, response: Response, actor: str = Depends(actieve_userid)):
    run, nieuw = await store.start(await werkgebied_store.haal(werkgebied_id), actor, resolve_bron)
    response.status_code = 201 if nieuw else 200
    return {**run, "nieuw": nieuw}


# Vóór `/begrippen-runs/{run_id}`, anders leest de router "laatste" als een run-id.
@router.get("/begrippen-runs/laatste")
async def get_laatste(werkgebied_id: str, actor: str = Depends(actieve_userid)):
    return {"run": await store.laatste(await werkgebied_store.haal(werkgebied_id), resolve_bron)}


@router.get("/begrippen-runs/{run_id}")
async def get_run(werkgebied_id: str, run_id: str, manifest: bool = False, actor: str = Depends(actieve_userid)):
    return await store.haal(werkgebied_id, run_id, met_manifest=manifest)


@router.post("/begrippen-runs/{run_id}/loopt")
async def post_loopt(werkgebied_id: str, run_id: str, actor: str = Depends(actieve_userid)):
    return await store.loopt(werkgebied_id, run_id)


@router.put("/begrippen-runs/{run_id}/uitkomst")
async def put_uitkomst(werkgebied_id: str, run_id: str, req: UitkomstInvoer, actor: str = Depends(actieve_userid)):
    return await store.zet_uitkomst(werkgebied_id, run_id, req, actor)


@router.post("/begrippen-runs/{run_id}/mislukt")
async def post_mislukt(werkgebied_id: str, run_id: str, req: MisluktInvoer, actor: str = Depends(actieve_userid)):
    return await store.mislukt(werkgebied_id, run_id, req.reden)


# --- de verdieping (fase C): het model op twijfelparen en kaarten ----------------------------------

@router.get("/verdieping")
async def get_verdieping(werkgebied_id: str, actor: str = Depends(actieve_userid)):
    """Wat het model nog moet doen voor de laatste klare run, met de klare batches, schatting en budget."""
    return await verdieping.werkvoorraad(werkgebied_id, actor)


@router.put("/begrippen-runs/{run_id}/batches/{batch_id}")
async def put_batch(werkgebied_id: str, run_id: str, batch_id: str, req: BatchInvoer,
                    actor: str = Depends(actieve_userid)):
    return await verdieping.zet_batch(werkgebied_id, run_id, batch_id, req, actor)


@router.put("/begrippen-runs/{run_id}/verdieping")
async def put_verdieping(werkgebied_id: str, run_id: str, req: VerdiepingInvoer, actor: str = Depends(actieve_userid)):
    return await verdieping.zet_verdieping(werkgebied_id, run_id, req, actor)


@router.post("/begrippen-runs/{run_id}/vragen/{kandidaat_id}")
async def post_vraag(werkgebied_id: str, run_id: str, kandidaat_id: str, req: VraagBesluit,
                     actor: str = Depends(actieve_userid)):
    return await store.vraag(werkgebied_id, run_id, kandidaat_id, req.antwoord, actor)


@router.get("/groepen")
async def get_groepen(werkgebied_id: str, actor: str = Depends(actieve_userid)):
    return await store.groepen(werkgebied_id)


@router.post("/groepen/overnemen", status_code=201)
async def post_overnemen(werkgebied_id: str, req: Overname, actor: str = Depends(actieve_userid)):
    return await store.overnemen(await werkgebied_store.haal(werkgebied_id), req, actor, resolve_bron)


@router.post("/groepen/{groep_id}/koppelen")
async def post_koppelen(werkgebied_id: str, groep_id: str, req: GroepKoppeling, actor: str = Depends(actieve_userid)):
    return await store.koppelen(await werkgebied_store.haal(werkgebied_id), groep_id, req, actor, resolve_bron)


@router.post("/groepen/{groep_id}/afwijzen")
async def post_afwijzen(werkgebied_id: str, groep_id: str, req: GroepBesluit, actor: str = Depends(actieve_userid)):
    await store.besluit(werkgebied_id, groep_id, "afgewezen", req.reden, actor)
    return await store.groepen(werkgebied_id)


@router.post("/groepen/{groep_id}/parkeren")
async def post_parkeren(werkgebied_id: str, groep_id: str, req: GroepBesluit, actor: str = Depends(actieve_userid)):
    await store.besluit(werkgebied_id, groep_id, "geparkeerd", req.reden, actor)
    return await store.groepen(werkgebied_id)


@router.post("/groepen/{groep_id}/heropenen")
async def post_heropenen(werkgebied_id: str, groep_id: str, actor: str = Depends(actieve_userid)):
    """Een afwijzing of parkering terugdraaien. Een overgenomen groep heropen je via het begrip."""
    await store.heropen_groep(werkgebied_id, groep_id, actor)
    return await store.groepen(werkgebied_id)
