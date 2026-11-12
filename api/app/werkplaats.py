"""De werkplaats-API (ADR-016 deel B, stap B1): zelf skills en agentprofielen maken, als concept met versies.

Achter de vlag `WERKPLAATS` (standaard uit, alleen op acceptatie aan): zonder de vlag bestaan de routes niet (404).
Alleen `GET /v1/werkplaats/stand` antwoordt altijd, zodat de werkplek weet of de werkplaats er is.

De rechten (§B4):
- een concept maken en een versie opslaan: de eigenaar. Een analist alleen als het beleid dat toestaat;
- lezen: de eigenaar, iedereen bij een gedeeld onderdeel, een beheerder met 2FA alles;
- intrekken: de eigenaar zijn eigen onderdeel. Een beheerder trekt dat van een ander in via `/v1/admin/werkplaats/*`;
- delen en het beleid: een beheerder met 2FA, onder `/v1/admin/werkplaats/*` (`routers/admin.py`).

De store (`werkplaats_store.py`) toetst en bewaart; deze router toetst alleen wie het vraagt.
"""
from __future__ import annotations

from typing import Any

from bronmodel import werkplaats as wp
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from . import users, werkplaats_store as store
from .auth import require_client
from .config import get_settings
from .routers.auth import actieve_userid

router = APIRouter(prefix="/werkplaats", tags=["werkplaats"], dependencies=[Depends(require_client)])

Bestanden = dict[str, str]


class OnderdeelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    soort: str = Field(max_length=32)
    naam: str = Field(max_length=64)
    # Weggelaten: het lege begin van de soort, met de verplichte velden.
    bestanden: Bestanden | None = None
    toelichting: str = Field(default="", max_length=500)


class VersieIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bestanden: Bestanden
    toelichting: str = Field(default="", max_length=500)
    # De versie waarop deze voortbouwt: is er intussen een nieuwere, dan 409.
    na_versie: int = Field(ge=1)


class ToetsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    soort: str = Field(max_length=32)
    naam: str = Field(max_length=64)
    bestanden: Bestanden


def vereis_aan() -> None:
    """Zonder de vlag bestaat de werkplaats niet."""
    if not get_settings().werkplaats:
        raise HTTPException(404, "De werkplaats staat op deze omgeving niet aan.")


async def _is_beheerder(userid: str) -> bool:
    """Een beheerder met 2FA. Zonder 2FA werkt een beheerder als analist: het beheer blijft dicht."""
    user = await users.get_user(userid)
    return bool(user and user.role == "beheerder" and user.totp_enabled)


async def _mag_maken(userid: str) -> bool:
    return await _is_beheerder(userid) or (await store.beleid())["analist_mag_maken"]


async def _zichtbaar(onderdeel_id: str, userid: str) -> dict[str, Any]:
    """Het onderdeel, als deze gebruiker het mag lezen; anders 404, zodat andermans concept niet te raden is."""
    onderdeel = await store.lees(onderdeel_id)
    gedeeld = onderdeel["gedeeld"] and onderdeel["stand"] != "ingetrokken"
    if onderdeel["eigenaar"] == userid or gedeeld or await _is_beheerder(userid):
        return onderdeel
    raise HTTPException(404, {"melding": "Onbekend onderdeel."})


async def _eigen(onderdeel_id: str, userid: str) -> dict[str, Any]:
    onderdeel = await _zichtbaar(onderdeel_id, userid)
    if onderdeel["eigenaar"] != userid:
        raise HTTPException(403, {"melding": "Alleen de eigenaar wijzigt een concept."})
    return onderdeel


@router.get("/stand")
async def stand(userid: str = Depends(actieve_userid)) -> dict[str, Any]:
    """Of de werkplaats aanstaat, welke soorten er zijn en wat deze gebruiker mag."""
    if not get_settings().werkplaats:
        return {"aan": False}
    beleid = await store.beleid()
    return {
        "aan": True,
        "soorten": [{"naam": s, "label": wp.REGISTER[s].label if s in wp.REGISTER else s, "open": s in wp.REGISTER}
                    for s in wp.SOORTEN],
        "mag_maken": await _mag_maken(userid),
        "beheerder": await _is_beheerder(userid),
        "beleid": beleid,
        "grenzen": {"bestanden": wp.MAX_BESTANDEN, "tekens_per_bestand": wp.MAX_TEKENS_BESTAND, "tekens": wp.MAX_TEKENS,
                    "versies": wp.MAX_VERSIES, "onderdelen": wp.MAX_ONDERDELEN},
    }


@router.get("/onderdelen", dependencies=[Depends(vereis_aan)])
async def lijst(soort: str | None = Query(default=None, max_length=32),
                userid: str = Depends(actieve_userid)) -> list[dict[str, Any]]:
    return await store.lijst(userid, alles=await _is_beheerder(userid), soort=soort)


@router.post("/onderdelen", status_code=201, dependencies=[Depends(vereis_aan)])
async def maak(body: OnderdeelIn, userid: str = Depends(actieve_userid)) -> dict[str, Any]:
    if not await _mag_maken(userid):
        raise HTTPException(403, {"melding": "Een beheerder heeft het maken van concepten voor analisten uitgezet."})
    return await store.maak(body.soort, body.naam, userid, body.bestanden, body.toelichting)


@router.post("/toets", dependencies=[Depends(vereis_aan)])
async def toets(body: ToetsIn, _userid: str = Depends(actieve_userid)) -> dict[str, Any]:
    """Poort 1 zonder op te slaan, voor de editor."""
    bevindingen = store.toets(body.soort, body.naam, body.bestanden)
    return {"geldig": not bevindingen, "bevindingen": bevindingen, "hash": wp.hash_van(body.bestanden)}


@router.get("/onderdelen/{onderdeel_id}", dependencies=[Depends(vereis_aan)])
async def lees(onderdeel_id: str, userid: str = Depends(actieve_userid)) -> dict[str, Any]:
    return await _zichtbaar(onderdeel_id, userid)


@router.get("/onderdelen/{onderdeel_id}/versies/{nummer}", dependencies=[Depends(vereis_aan)])
async def versie(onderdeel_id: str, nummer: int, userid: str = Depends(actieve_userid)) -> dict[str, Any]:
    onderdeel = await _zichtbaar(onderdeel_id, userid)
    v = await store.versie(onderdeel_id, nummer)
    return {**v, "bruikbaar": store.bruikbaar(v, onderdeel)}


@router.post("/onderdelen/{onderdeel_id}/versies", dependencies=[Depends(vereis_aan)])
async def nieuwe_versie(onderdeel_id: str, body: VersieIn, userid: str = Depends(actieve_userid)) -> dict[str, Any]:
    await _eigen(onderdeel_id, userid)
    return await store.nieuwe_versie(onderdeel_id, body.bestanden, body.toelichting, body.na_versie, userid)


@router.post("/onderdelen/{onderdeel_id}/intrekken", dependencies=[Depends(vereis_aan)])
async def trek_in(onderdeel_id: str, userid: str = Depends(actieve_userid)) -> dict[str, Any]:
    await _eigen(onderdeel_id, userid)
    return await store.trek_in(onderdeel_id, userid)


@router.get("/onderdelen/{onderdeel_id}/audit", dependencies=[Depends(vereis_aan)])
async def audit(onderdeel_id: str, userid: str = Depends(actieve_userid)) -> list[dict[str, Any]]:
    await _zichtbaar(onderdeel_id, userid)
    return await store.audit(onderdeel_id)
