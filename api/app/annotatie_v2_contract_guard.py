"""Expliciete cutover: gemengde applicatieversies mogen geen artikellagen terugschrijven."""
from fastapi import HTTPException, Request

from .config import get_settings


def contract_versie() -> int:
    return get_settings().annotatie_contract_versie


def require_v2(request: Request):
    if not request.url.path.endswith("/capabilities") and contract_versie() != 2:
        raise HTTPException(503, "Bronnode-annotaties zijn nog niet geactiveerd.")


def require_legacy_write(request: Request):
    if (contract_versie() == 2 and request.method in {"POST", "PUT", "PATCH"}
            and not request.url.path.endswith("/export")):
        raise HTTPException(409, "Annotaties gebruiken nu bronnode-lagen; vernieuw de toepassing.")


def require_legacy_migration():
    if contract_versie() == 2:
        raise HTTPException(409, "De artikelmigratie is niet beschikbaar bij bronnode-lagen.")
