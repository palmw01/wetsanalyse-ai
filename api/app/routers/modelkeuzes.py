"""De modelkeuzes van Lex om te lezen: welk model elk agentprofiel en elke stap nu gebruikt.

Voor graph-qa (`agent/modelkeuze.py`, per beurt met een korte cache) en voor elke ingelogde gebruiker die wil zien welk
model Lex gebruikt. Alleen profielnaam en modelnaam; kiezen staat in `/v1/admin/modelkeuzes`."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import modelkeuzes
from ..auth import require_client

router = APIRouter(prefix="/modelkeuzes", tags=["modelkeuzes"], dependencies=[Depends(require_client)])


@router.get("", response_model=modelkeuzes.Stand)
async def lees():
    return await modelkeuzes.stand()
