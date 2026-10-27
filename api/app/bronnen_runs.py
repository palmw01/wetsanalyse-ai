"""Bronnen vinden met Lex (spoor D, fase A) onder `/v1/werkgebieden/{id}`: runs van de ontdekmethoden
en de kandidaatbepalingen. Gedeeld zoals de werkgebieden; elke route vraagt een actieve gebruiker, die
als actor in de audit komt.

De routes `…/uitkomst`, `…/loopt` en `…/mislukt` zijn voor graph-qa; de BFF van de werkplek laat ze
niet door, en de api toetst de uitkomst tegen de eigen invoer."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from . import annotatie_v2_store, bronnen_run_store as store, bronselectie, werkgebied_store
from .auth import require_client
from .bronnen_run_contracts import BronnenMislukt, BronnenUitkomst, Opnemen, Uitsluiten
from .bronselectie_contracts import KandidaatBesluit, StatusActie
from .werkgebied_contracts import BronselectieInvoer
from .routers.auth import actieve_userid
from .werkgebieden import resolve_bron

router = APIRouter(prefix="/werkgebieden/{werkgebied_id}", tags=["bronnen-runs"],
                   dependencies=[Depends(require_client)])


@router.post("/bronnen-runs")
async def post_run(werkgebied_id: str, response: Response, actor: str = Depends(actieve_userid)):
    run, nieuw = await store.start(await werkgebied_store.haal(werkgebied_id), actor)
    response.status_code = 201 if nieuw else 200
    return {**run, "nieuw": nieuw}


# Vóór `/bronnen-runs/{run_id}`, anders leest de router "laatste" als een run-id.
@router.get("/bronnen-runs/laatste")
async def get_laatste(werkgebied_id: str, actor: str = Depends(actieve_userid)):
    return {"run": await store.laatste(await werkgebied_store.haal(werkgebied_id))}


@router.get("/bronnen-runs/{run_id}")
async def get_run(werkgebied_id: str, run_id: str, invoer: bool = False, actor: str = Depends(actieve_userid)):
    return await store.haal(werkgebied_id, run_id, met_invoer=invoer)


@router.post("/bronnen-runs/{run_id}/loopt")
async def post_loopt(werkgebied_id: str, run_id: str, actor: str = Depends(actieve_userid)):
    return await store.loopt(werkgebied_id, run_id)


@router.put("/bronnen-runs/{run_id}/uitkomst")
async def put_uitkomst(werkgebied_id: str, run_id: str, req: BronnenUitkomst, actor: str = Depends(actieve_userid)):
    return await store.zet_uitkomst(werkgebied_id, run_id, req, actor)


@router.post("/bronnen-runs/{run_id}/mislukt")
async def post_mislukt(werkgebied_id: str, run_id: str, req: BronnenMislukt, actor: str = Depends(actieve_userid)):
    return await store.mislukt(werkgebied_id, run_id, req.reden)


@router.get("/kandidaten")
async def get_kandidaten(werkgebied_id: str, actor: str = Depends(actieve_userid)):
    return await store.kandidaten(werkgebied_id)


@router.post("/kandidaten/{kandidaat_id}/opnemen")
async def post_opnemen(werkgebied_id: str, kandidaat_id: str, req: Opnemen, actor: str = Depends(actieve_userid)):
    await werkgebied_store.haal(werkgebied_id)
    bron = await _bron_van(werkgebied_id, kandidaat_id)
    uit = await store.opnemen(werkgebied_id, kandidaat_id, req, bron, actor)
    return {**uit, "werkgebied": await werkgebied_store.haal(werkgebied_id)}


async def _bron_van(werkgebied_id: str, kandidaat_id: str) -> dict:
    """De bron van een kandidaat, geverifieerd zoals bij zelf opnemen; een onbekende kandidaat geeft
    daarna in de store 404."""
    lijst = await store.kandidaten(werkgebied_id)
    bron_iri = next((k["bron_iri"] for k in lijst["kandidaten"] if k["id"] == kandidaat_id), "")
    if not bron_iri:
        return {"bron_iri": ""}
    return await _geverifieerd({"bron_iri": bron_iri})


async def _geverifieerd(doel_in: dict) -> dict:
    """De bron uit de resolver: canonieke IRI, label, regeling, snapshot en hash. 422 als hij niet bestaat."""
    snapshot = await resolve_bron(doel_in)
    doel = snapshot["doel"]
    node = annotatie_v2_store.nodes_van(snapshot).get(doel["bron_iri"], {})
    return {"bron_iri": doel["bron_iri"], "label": doel.get("label") or node.get("label", ""),
            "bwb_id": doel.get("bwb_id") or node.get("bwb_id", ""),
            "snapshot_id": snapshot.get("snapshot_id", ""), "bron_hash": node.get("bron_hash", "")}


@router.post("/kandidaten/{kandidaat_id}/later")
async def post_later(werkgebied_id: str, kandidaat_id: str, actor: str = Depends(actieve_userid)):
    return await store.later(werkgebied_id, kandidaat_id, actor)


@router.post("/kandidaten/{kandidaat_id}/uitsluiten")
async def post_uitsluiten(werkgebied_id: str, kandidaat_id: str, req: Uitsluiten,
                          actor: str = Depends(actieve_userid)):
    return await store.uitsluiten(werkgebied_id, kandidaat_id, req.reden, actor)


@router.post("/kandidaten/{kandidaat_id}/heropenen")
async def post_heropenen(werkgebied_id: str, kandidaat_id: str, actor: str = Depends(actieve_userid)):
    return await store.heropenen(werkgebied_id, kandidaat_id, actor)


# --- Bronselectie per deelvraag (spoor J) ------------------------------------------------------
# Het overzicht dat Lex, het werkgebiedpaneel en de tab Bronnen delen; `na` is de deelvraag waar de
# analist nu staat (de code kiest de volgende). De deelvraag `analysevraag` is de analysevraag zelf, voor
# een werkgebied zonder deelvragen.

@router.get("/bronselectie")
async def get_bronselectie(werkgebied_id: str, na: str | None = Query(default=None, max_length=64),
                           actor: str = Depends(actieve_userid)):
    return await bronselectie.overzicht(werkgebied_id, na=na)


@router.post("/bronselectie/{deelvraag_id}/status")
async def post_bronselectie_status(werkgebied_id: str, deelvraag_id: str, req: StatusActie,
                                   actor: str = Depends(actieve_userid)):
    await bronselectie.zet_status(werkgebied_id, deelvraag_id, req, actor)
    return await bronselectie.overzicht(werkgebied_id, na=deelvraag_id)


@router.post("/bronselectie/{deelvraag_id}/kandidaten/{kandidaat_id}")
async def post_bronselectie_besluit(werkgebied_id: str, deelvraag_id: str, kandidaat_id: str, req: KandidaatBesluit,
                                    actor: str = Depends(actieve_userid)):
    # Alleen opnemen van een bepaling die nog niet in het werkgebied staat, vraagt de graaf.
    bron = {"bron_iri": ""}
    if req.besluit == "opnemen":
        wg = await werkgebied_store.haal(werkgebied_id)
        lijst = await store.kandidaten(werkgebied_id)
        iri = next((k["bron_iri"] for k in lijst["kandidaten"] if k["id"] == kandidaat_id), "")
        if iri and iri not in {b["bron_iri"] for b in wg["bronnen"]}:
            bron = await _bron_van(werkgebied_id, kandidaat_id)
    await bronselectie.besluit(werkgebied_id, deelvraag_id, kandidaat_id, req, bron, actor)
    return await bronselectie.overzicht(werkgebied_id, na=deelvraag_id)


@router.post("/bronselectie/{deelvraag_id}/bronnen")
async def post_bronselectie_bron(werkgebied_id: str, deelvraag_id: str, req: BronselectieInvoer,
                                 actor: str = Depends(actieve_userid)):
    """Zelf een bepaling als keuze toevoegen bij één deelvraag (bron-IRI, of regeling + artikel (+ lid)); de api
    verifieert haar in de graaf zoals bij zelf opnemen."""
    await werkgebied_store.haal(werkgebied_id)                 # 404 vóór de graaf wordt gevraagd
    bron = await _geverifieerd({"bron_iri": req.bron_iri, "bwb_id": req.bwb_id, "artikel": req.artikel, "lid": req.lid})
    await bronselectie.toevoegen(werkgebied_id, deelvraag_id, req, bron, actor)
    return await bronselectie.overzicht(werkgebied_id, na=deelvraag_id)
