"""Bronnen vinden met Lex (spoor D, fase A) onder `/v1/werkgebieden/{id}`: runs van de ontdekmethoden
en de kandidaatbepalingen. Gedeeld zoals de werkgebieden; elke route vraagt een actieve gebruiker, die
als actor in de audit komt.

De routes `…/uitkomst`, `…/loopt` en `…/mislukt` zijn voor graph-qa; de BFF van de werkplek laat ze
niet door, en de api toetst de uitkomst tegen de eigen invoer."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from . import bronnen_run_store as store, bronselectie, werkgebied_store
from .auth import require_client
from .bronnen_run_contracts import BronnenMislukt, BronnenUitkomst
from .bronselectie_contracts import GenoemdVoorstel, KandidaatBesluit, StatusActie
from .routers.auth import actieve_userid
from .werkgebieden import geverifieerde_bron

router = APIRouter(prefix="/werkgebieden/{werkgebied_id}", tags=["bronnen-runs"],
                   dependencies=[Depends(require_client)])


class StartRun(BaseModel):
    """Optioneel: de versie van de zoekcode van graph-qa. Een andere versie is een andere run."""
    zoekversie: str = Field(default="", max_length=64, pattern=r"^[A-Za-z0-9._-]*$")


@router.post("/bronnen-runs")
async def post_run(werkgebied_id: str, response: Response, body: StartRun | None = None,
                   actor: str = Depends(actieve_userid)):
    run, nieuw = await store.start(await werkgebied_store.haal(werkgebied_id), actor,
                                   zoekversie=(body.zoekversie if body else ""))
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


async def _bron_van(werkgebied_id: str, kandidaat_id: str) -> dict:
    """De bron van een kandidaat, geverifieerd zoals bij zelf opnemen; een onbekende kandidaat geeft
    daarna in de store 404."""
    bron_iri = await store.bron_iri_van(werkgebied_id, kandidaat_id)
    if not bron_iri:
        return {"bron_iri": ""}
    return await geverifieerde_bron({"bron_iri": bron_iri})


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
        kandidaat = await store.bron_iri_van(werkgebied_id, kandidaat_id)
        iri = req.bron_iri or kandidaat
        if kandidaat and not bronselectie.onder(iri, kandidaat):
            raise HTTPException(422, {"fout": "niet_onder_kandidaat",
                                      "melding": "Kies de bepaling zelf, of een lid of onderdeel ervan."})
        if iri and iri not in {b["bron_iri"] for b in wg["bronnen"]}:
            bron = await geverifieerde_bron({"bron_iri": iri})
    await bronselectie.besluit(werkgebied_id, deelvraag_id, kandidaat_id, req, bron, actor)
    return await bronselectie.overzicht(werkgebied_id, na=deelvraag_id)


@router.post("/bronselectie/{deelvraag_id}/voorstellen")
async def post_bronselectie_voorstel(werkgebied_id: str, deelvraag_id: str, req: GenoemdVoorstel,
                                     actor: str = Depends(actieve_userid)):
    """Een bepaling die de analist zelf noemt, als voorstel bij één deelvraag: daarna staat ze in het paneel met de
    voorstellen van Lex, en daar besluit de analist. De api verifieert haar in de graaf."""
    await werkgebied_store.haal(werkgebied_id)                 # 404 vóór de graaf wordt gevraagd
    bron = await geverifieerde_bron({"bron_iri": req.bron_iri})
    await bronselectie.noem(werkgebied_id, deelvraag_id, req, bron, actor)
    return await bronselectie.overzicht(werkgebied_id, na=deelvraag_id)
