"""Open-punten-API (L-X-1, ADR-018 §6), onder `/v1/werkgebieden/{id}/open-punten`.

Gedeeld zoals de regels; elke route vraagt een actieve gebruiker, die als actor in de revisies en de audit komt. Geen
van deze routes staat in `agent_toegang.TOEGESTAAN`: Lex leest de open punten mee in het werkgebied
(`GET /v1/werkgebieden/{id}`, veld `open_punten`) en schrijft er geen. Het besluit (`…/besluit`) is één route voor elke
plek waar de jurist kiest: de regelkaart, de begripskaart, een markering of de keuzekaart in het gesprek.
Stijl C: de store gooit de fouten, de router is dun.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from . import open_punt_store as store
from .auth import require_client
from .open_punt_contracts import Besluit, Omhangen, OpenPuntAanmaak, OpenPuntWijziging, Soort, Status
from .routers.auth import actieve_userid

router = APIRouter(prefix="/werkgebieden/{werkgebied_id}", tags=["open punten"],
                   dependencies=[Depends(require_client)])

Aanhaking = Literal["regel", "geval", "markering", "begrip", "deelvraag", "werkgebied"]


@router.get("/open-punten")
async def get_lijst(werkgebied_id: str, status: Status | None = None, soort: Soort | None = None,
                    aan: Aanhaking | None = Query(None, description="waar het aan hangt: soort, met `aan_id`"),
                    aan_id: str | None = None,
                    regel_id: str | None = Query(None, description="kort voor `aan=regel&aan_id=…`"),
                    actor: str = Depends(actieve_userid)):
    if regel_id:
        if aan and (aan, aan_id) != ("regel", regel_id):
            raise HTTPException(422, {"fout": "aanhaking", "melding": "Geef `regel_id`, of `aan` met `aan_id`."})
        aan, aan_id = "regel", regel_id
    if bool(aan) != bool(aan_id):
        raise HTTPException(422, {"fout": "aanhaking", "melding": "Geef `aan` en `aan_id` samen."})
    hangt_aan = ("regel" if aan == "geval" else aan, aan_id) if aan and aan_id else None
    return {"open_punten": await store.lijst(werkgebied_id, status=status.value if status else None,
                                             soort=soort.value if soort else None, hangt_aan=hangt_aan)}


@router.post("/open-punten", status_code=201)
async def post_punt(werkgebied_id: str, req: OpenPuntAanmaak, actor: str = Depends(actieve_userid)):
    return await store.maak(werkgebied_id, req, actor)


@router.get("/open-punten/{punt_id}")
async def get_punt(werkgebied_id: str, punt_id: str, actor: str = Depends(actieve_userid)):
    return await store.haal(werkgebied_id, punt_id)


@router.patch("/open-punten/{punt_id}")
async def patch_punt(werkgebied_id: str, punt_id: str, req: OpenPuntWijziging, actor: str = Depends(actieve_userid)):
    return await store.wijzig(werkgebied_id, punt_id, req, actor)


@router.post("/open-punten/{punt_id}/besluit")
async def post_besluit(werkgebied_id: str, punt_id: str, req: Besluit, actor: str = Depends(actieve_userid)):
    return await store.besluit(werkgebied_id, punt_id, req, actor)


@router.post("/open-punten/{punt_id}/omhangen")
async def post_omhangen(werkgebied_id: str, punt_id: str, req: Omhangen, actor: str = Depends(actieve_userid)):
    """Alleen waar het punt aan hangt (A2): na een vervanging naar de opvolger, zonder de rest van de inhoud."""
    return await store.omhang(werkgebied_id, punt_id, req, actor)


@router.delete("/open-punten/{punt_id}")
async def delete_punt(werkgebied_id: str, punt_id: str, verwachte_revisie: int = Query(ge=1),
                      reden: str = Query("", max_length=2000, description="verplicht bij een punt dat nog open is"),
                      actor: str = Depends(actieve_userid)):
    return await store.verwijder(werkgebied_id, punt_id, verwachte_revisie, actor, reden)


@router.get("/open-punten/{punt_id}/revisies")
async def get_revisies(werkgebied_id: str, punt_id: str, limit: int = Query(100, ge=1, le=500),
                       actor: str = Depends(actieve_userid)):
    return {"revisies": await store.revisies(werkgebied_id, punt_id, limit)}
