"""Tokenbudget – resource voor de ingelogde gebruiker en voor graph-qa (gemount onder /v1/verbruik).

GET  /v1/verbruik           – de eigen stand (meter, resetdatum, waarschuwing, blokkade)
GET  /v1/verbruik/controle  – mag deze gebruiker een beurt starten? (de pre-check van graph-qa)
POST /v1/verbruik           – boek het verbruik van een afgeronde beurt (graph-qa)

Alles achter de client-bearer; de identiteit komt uit de vertrouwde `X-User-Id`-header die de BFF
(en graph-qa) server-side zetten. Dit domein is dus per-gebruiker gescopet zoals de gesprekken:
niemand ziet andermans stand hier. De beheerder heeft daar `/v1/admin/verbruik` voor.

Waarom de api en niet graph-qa de autoriteit is: graph-qa draait met meerdere replica's en houdt
zijn eigen remmen in het procesgeheugen. Een budget dat per replica telt is geen budget.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from .. import verbruik as svc
from ..auth import require_client
from ..verbruik_contracts import Verbruiksstand
from .auth import actieve_userid, huidige_userid

router = APIRouter(
    prefix="/verbruik",
    tags=["verbruik"],
    dependencies=[Depends(require_client)],
)


class VerbruikIn(BaseModel):
    """Het verbruik van één afgeronde agent-beurt.

    `run_id` maakt het boeken idempotent: dezelfde beurt twee keer melden telt één keer.
    """

    bron: str = Field(default="agent", max_length=32)
    model: str = Field(default="", max_length=128)
    invoer: int = Field(default=0, ge=0)
    uitvoer: int = Field(default=0, ge=0)
    cache_lees: int = Field(default=0, ge=0)
    cache_schrijf: int = Field(default=0, ge=0)
    gesprek_id: str = Field(default="", max_length=64)
    run_id: str = Field(default="", max_length=64)


class VerbruikGeboekt(BaseModel):
    # False = er viel niets te boeken, of deze run was al geboekt. Geen fout: de aanroeper mag
    # gerust opnieuw melden.
    geboekt: bool


class Controle(BaseModel):
    toegestaan: bool
    stand: Verbruiksstand


@router.get("", response_model=Verbruiksstand)
async def mijn_verbruik(userid: str = Depends(actieve_userid)):
    return await svc.stand(userid)


@router.get("/controle", response_model=Controle)
async def controle(userid: str = Depends(huidige_userid)):
    """De pre-check vóór een agent-beurt.

    Bewust `huidige_userid` en niet `actieve_userid`: dit is een leesactie zonder gevolgen, en
    graph-qa moet hem kunnen doen zonder dat een cache-miss op het account een beurt tegenhoudt.
    """
    stand = await svc.stand(userid)
    return Controle(toegestaan=not stand.geblokkeerd, stand=stand)


@router.post("", response_model=VerbruikGeboekt, status_code=status.HTTP_201_CREATED)
async def boek_verbruik(body: VerbruikIn, userid: str = Depends(huidige_userid)):
    """Boek het verbruik van een beurt.

    Geen rate limit: dit is een boekhoudkundige melding die precies één keer per beurt komt, en hem
    weigeren zou betekenen dat verbruik stil verdwijnt. De idempotentie op `run_id` beschermt tegen
    herhalingen.
    """
    geboekt = await svc.boek(
        userid,
        bron=body.bron,
        model=body.model,
        invoer=body.invoer,
        uitvoer=body.uitvoer,
        cache_lees=body.cache_lees,
        cache_schrijf=body.cache_schrijf,
        gesprek_id=body.gesprek_id,
        run_id=body.run_id,
    )
    return VerbruikGeboekt(geboekt=geboekt)
