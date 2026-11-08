"""
De gesprekken-resource (gemount onder /v1/gesprekken): de persistente chatgeschiedenis van de werkplek.

**Per-gebruiker gescopet** – anders dan het client-gescopete annotatie-domein. De identiteit komt uit
de vertrouwde `X-User-Id`-header die de BFF uit de ingelogde sessie zet (`huidige_userid`, hergebruikt
uit de auth-router); de router zit achter de client-bearer (`require_client`), zoals de auth-router.
404 (niet 403) bij andermans gesprek, zodat het bestaan niet lekt.

POST   /v1/gesprekken                       – nieuw gesprek
GET    /v1/gesprekken?limit=&offset=&werkgebied_id=&ouder_id=&gearchiveerd=&q=
                                            – eigen gesprekken (samenvatting, nieuwste eerst);
                                              `q` zoekt in de titel en de tekst van de berichten
GET    /v1/gesprekken/{id}                  – volledig gesprek (met berichten)
POST   /v1/gesprekken/{id}/berichten        – bericht toevoegen
PATCH  /v1/gesprekken/{id}                  – titel, werkgebied (koppelen/loskoppelen), archief
DELETE /v1/gesprekken/{id}                  – verwijder eigen gesprek
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..agent_toegang import AGENT_CLIENT
from ..auth import huidige_client, require_client
from ..deps import get_gesprek_store
from ..gesprek_contracts import (
    Bericht, BerichtInvoer, Gesprek, GesprekCreate, GesprekPatch, GesprekSamenvatting, Rol,
)
from ..gesprek_store import GesprekStore
from .. import artefact_versies, werkgebied_store
from .auth import actieve_userid

logger = logging.getLogger("wetsanalyse.gesprekken")

router = APIRouter(prefix="/gesprekken", tags=["gesprekken"], dependencies=[Depends(require_client)])


async def _gesprek_or_404(store: GesprekStore, gesprek_id: str, user_id: str) -> Gesprek:
    """Laadt het gesprek en dwingt eigenaarschap af. 404 (niet 403) bij mismatch – lekt niet."""
    gesprek = await store.laad_gesprek(gesprek_id)
    if gesprek is None or gesprek.user_id != user_id:
        raise HTTPException(status_code=404, detail=f"Onbekend gesprek: {gesprek_id}")
    return gesprek


async def _eigen_gesprek_of_404(store: GesprekStore, gesprek_id: str, user_id: str) -> None:
    """Zelfde controle, zonder de berichten te laden: voor schrijfroutes, die elke beurt langskomen."""
    if await store.eigenaar_van(gesprek_id) != user_id:
        raise HTTPException(status_code=404, detail=f"Onbekend gesprek: {gesprek_id}")


async def _bestaand_werkgebied(werkgebied_id: str) -> None:
    """Werkgebieden zijn gedeeld, dus bestaan is genoeg; een gearchiveerd werkgebied telt niet."""
    if werkgebied_id:
        await werkgebied_store.haal(werkgebied_id)


async def _geldige_ouder(store: GesprekStore, req: GesprekCreate, user_id: str):
    """Een deelgesprek (ADR-012) hangt onder een eigen gesprek in hetzelfde werkgebied, één niveau diep. De regie
    hoort dan bij die ouder. Een ouder van een ander geeft 404, zoals elk vreemd gesprek."""
    if not req.ouder_id:
        if req.regie_id:
            raise HTTPException(422, {"fout": "regie_zonder_ouder", "melding": "Een regie hoort bij een regiegesprek."})
        return
    ouder = await store.laad_gesprek(req.ouder_id)
    if ouder is None or ouder.user_id != user_id:
        raise HTTPException(404, f"Onbekend gesprek: {req.ouder_id}")
    if not req.werkgebied_id or ouder.werkgebied_id != req.werkgebied_id:
        raise HTTPException(409, {"fout": "ander_werkgebied",
                                  "melding": "Een deelgesprek hoort bij het werkgebied van zijn ouder."})
    if ouder.ouder_id:
        raise HTTPException(409, {"fout": "te_diep", "melding": "Een deelgesprek heeft zelf geen deelgesprekken."})
    if req.regie_id:
        from .. import regie_store
        regie = await regie_store.haal(req.werkgebied_id, req.regie_id)
        if regie.gesprek_id != req.ouder_id:
            raise HTTPException(409, {"fout": "andere_regie", "melding": "De regie hoort bij een ander gesprek."})
        if regie.user_id != user_id:
            raise HTTPException(404, f"Onbekende regie: {req.regie_id}")
        return regie
    return None


def _agent_mag_alleen_een_deelgesprek(req: GesprekCreate, regie) -> None:
    """Het agent-token (graph-qa) maakt alleen het deelgesprek van een regie die loopt (ADR-012), voor de gebruiker van
    die regie. Een los gesprek, of een gesprek onder een afgeronde of verweesde regie, maakt alleen de webapp: anders kan
    het agent-token namens elke `X-User-Id` gesprekken aanmaken."""
    if huidige_client.get() != AGENT_CLIENT:
        return
    if not (req.ouder_id and req.regie_id) or regie is None:
        raise HTTPException(403, {"fout": "alleen_deelgesprek",
                                  "melding": "Lex maakt alleen een deelgesprek van een regie."})
    if regie.status != "loopt":
        raise HTTPException(409, {"fout": "regie_afgerond", "melding": "De regie loopt niet meer."})


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Gesprek)
async def maak_gesprek(
    req: GesprekCreate,
    user_id: str = Depends(actieve_userid),
    store: GesprekStore = Depends(get_gesprek_store),
):
    await _bestaand_werkgebied(req.werkgebied_id)
    _agent_mag_alleen_een_deelgesprek(req, await _geldige_ouder(store, req, user_id))
    gesprek = Gesprek(id=uuid.uuid4().hex[:16], user_id=user_id, titel=req.titel,
                      werkgebied_id=req.werkgebied_id, ouder_id=req.ouder_id, regie_id=req.regie_id)
    await store.maak_gesprek(gesprek)
    return await store.laad_gesprek(gesprek.id)


@router.get("", response_model=list[GesprekSamenvatting])
async def lijst_gesprekken(
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    werkgebied_id: str | None = Query(None, description='Leeg ("") = alleen losse gesprekken.'),
    ouder_id: str | None = Query(None, max_length=64, description='De deelgesprekken van één gesprek; "" = alleen gesprekken zonder ouder.'),
    gearchiveerd: bool | None = Query(None, description="Weglaten = actief én gearchiveerd."),
    q: str = Query("", max_length=200, description="Zoek in de titel en de tekst van de berichten."),
    user_id: str = Depends(actieve_userid),
    store: GesprekStore = Depends(get_gesprek_store),
):
    return await store.lijst_samenvattingen(user_id, limit, offset, werkgebied_id, gearchiveerd, zoek=q,
                                            ouder_id=ouder_id)


@router.get("/{gesprek_id}", response_model=Gesprek)
async def haal_gesprek(
    gesprek_id: str,
    user_id: str = Depends(actieve_userid),
    store: GesprekStore = Depends(get_gesprek_store),
):
    return await _gesprek_or_404(store, gesprek_id, user_id)


@router.post("/{gesprek_id}/berichten", status_code=status.HTTP_201_CREATED, response_model=Bericht)
async def voeg_bericht_toe(
    gesprek_id: str,
    req: BerichtInvoer,
    user_id: str = Depends(actieve_userid),
    store: GesprekStore = Depends(get_gesprek_store),
):
    await _eigen_gesprek_of_404(store, gesprek_id, user_id)
    if req.rol == Rol.assistant and req.artefact and req.run_id:
        # De versie van het artefact bij deze beurt (`artefact_versies`): een gemak, nooit een voorwaarde.
        try:
            versie = await artefact_versies.leg_vast(gesprek_id, req.run_id, req.artefact.model_dump())
        except Exception:  # noqa: BLE001
            logger.warning("artefact: geen momentopname", extra={"categorie": "technisch"}, exc_info=True)
            versie = None
        if versie:
            req.artefact.ref = {**req.artefact.ref, "versie": versie}
    return await store.voeg_bericht_toe(gesprek_id, req)


@router.patch("/{gesprek_id}", response_model=Gesprek)
async def wijzig_gesprek(
    gesprek_id: str,
    req: GesprekPatch,
    user_id: str = Depends(actieve_userid),
    store: GesprekStore = Depends(get_gesprek_store),
):
    await _eigen_gesprek_of_404(store, gesprek_id, user_id)
    if req.werkgebied_id:
        await _bestaand_werkgebied(req.werkgebied_id)
    await store.wijzig_gesprek(gesprek_id, titel=req.titel, werkgebied_id=req.werkgebied_id,
                               gearchiveerd=req.gearchiveerd)
    return await store.laad_gesprek(gesprek_id)


@router.delete("/{gesprek_id}", status_code=status.HTTP_204_NO_CONTENT)
async def verwijder_gesprek(
    gesprek_id: str,
    user_id: str = Depends(actieve_userid),
    store: GesprekStore = Depends(get_gesprek_store),
):
    await _eigen_gesprek_of_404(store, gesprek_id, user_id)
    await store.verwijder_gesprek(gesprek_id)
