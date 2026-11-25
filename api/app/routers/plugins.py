"""Het register van de plugins voor graph-qa en de werkplek (plan contenttoets, C4): welke de beheerder aanbiedt."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import plugins
from ..auth import require_client

router = APIRouter(prefix="/plugins", tags=["plugins"], dependencies=[Depends(require_client)])


class Aangeboden(BaseModel):
    naam: str
    label: str
    beschrijving: str
    commando: str


class Aan(BaseModel):
    aan: list[str]
    #: Wat de werkplek in het menu *Bronnen en tools* en bij de commando's toont.
    plugins: list[Aangeboden] = []


@router.get("", response_model=Aan)
async def aangeboden():
    """Wat de beheerder aanbiedt. Een plugin draait alleen als de straat hem ook aanzet (graph-qa, proefvlag)."""
    aan = [p for p in await plugins.lijst() if p.aan]
    return Aan(aan=[p.naam for p in aan],
               plugins=[Aangeboden(naam=p.naam, label=p.label, beschrijving=p.beschrijving, commando=p.commando) for p in aan])
