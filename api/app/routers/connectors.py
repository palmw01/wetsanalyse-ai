"""Het register van de bronconnectors voor graph-qa (ADR-013): welke de beheerder heeft aangezet."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import connectors
from ..auth import require_client

router = APIRouter(prefix="/connectors", tags=["connectors"], dependencies=[Depends(require_client)])


class Beschikbaar(BaseModel):
    naam: str
    label: str
    brontype: str


class Aan(BaseModel):
    aan: list[str]
    #: Wat de werkplek in het menu *Bronnen en tools* toont: naam, label en brontype van wat aanstaat.
    connectors: list[Beschikbaar] = []


@router.get("", response_model=Aan)
async def aan_voor_de_agent():
    """Per beurt gelezen door graph-qa (`aan`), en door de werkplek voor het menu. Een connector draait alleen als ook
    de straat hem aanbiedt."""
    aan = [c for c in await connectors.lijst() if c.aan]
    return Aan(aan=[c.naam for c in aan],
               connectors=[Beschikbaar(naam=c.naam, label=c.label, brontype=c.brontype) for c in aan])
