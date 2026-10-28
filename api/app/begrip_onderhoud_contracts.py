"""Wirecontract voor het onderhoud van begrippen (spoor D, fase F1): herbeoordelen en dekking."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Herkoppeling(BaseModel):
    """De passage van een koppeling vervangen door haar opvolger. De oude koppeling blijft als historie."""

    verwachte_revisie: int = Field(ge=1)
    element_id: str = Field(min_length=1, max_length=64)
    motivatie: str = Field(default="", max_length=4000)


class Bevestiging(BaseModel):
    """De passage veranderde, maar het begrip klopt nog: een nieuwe bewijsstand naast de oude."""

    verwachte_revisie: int = Field(ge=1)
    motivatie: str = Field(default="", max_length=4000)


class BuitenBehandeling(BaseModel):
    element_ids: list[str] = Field(min_length=1, max_length=500)
    reden: str = Field(min_length=1, max_length=2000)

    @field_validator("reden")
    @classmethod
    def _reden(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("reden is verplicht")
        return v.strip()
