"""Het modelprofiel per rol van Lex, voor graph-qa: welke modelnaam elke rol nu gebruikt."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import modelrollen
from ..auth import require_client

router = APIRouter(prefix="/modelrollen", tags=["modelrollen"], dependencies=[Depends(require_client)])


@router.get("", response_model=modelrollen.VoorDeAgent)
async def voor_de_agent():
    """Gelezen door graph-qa (`agent/modelkeuze.py`, met een korte cache). Alleen bruikbare keuzes; een rol die er niet in
    staat volgt de standaard."""
    return await modelrollen.voor_de_agent()
