"""Het register van de bronconnectors voor graph-qa (ADR-013): welke de beheerder heeft aangezet."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import connectors
from ..auth import require_client

router = APIRouter(prefix="/connectors", tags=["connectors"], dependencies=[Depends(require_client)])


class Aan(BaseModel):
    aan: list[str]


@router.get("", response_model=Aan)
async def aan_voor_de_agent():
    """Per beurt gelezen door graph-qa; een connector draait alleen als ook de straat hem aanbiedt."""
    return Aan(aan=[c.naam for c in await connectors.lijst() if c.aan])
