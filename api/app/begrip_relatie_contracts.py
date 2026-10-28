"""Wirecontract voor begripsrelaties en opvolging (spoor D, fase F2)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# De vier relaties van de keten (`begrippen_pipeline.model.Hypothese`, zonder zelfde betekenis) en
# `verwant`, de enige zwakke: die vraagt een toelichting. `opvolging` maakt alleen de api zelf
# (nieuwe betekenis, combineren).
RelatieType = Literal["kwalificatie", "inclusie", "uitsluiting", "hierarchie", "verwant"]
TYPEN = ("kwalificatie", "inclusie", "uitsluiting", "hierarchie", "verwant", "opvolging")


class RelatieInvoer(BaseModel):
    """Een relatie vastleggen: zelf (van, naar, type) of als akkoord op een voorstel van Lex (`voorstel_id`)."""

    voorstel_id: str | None = Field(default=None, max_length=64)
    van_begrip: str | None = Field(default=None, max_length=64)
    naar_begrip: str | None = Field(default=None, max_length=64)
    type: RelatieType | None = None
    toelichting: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def _vorm(self):
        if self.voorstel_id is None and not (self.van_begrip and self.naar_begrip and self.type):
            raise ValueError("geef een voorstel_id, of van_begrip, naar_begrip en type")
        if self.voorstel_id is None and self.type == "verwant" and not self.toelichting.strip():
            raise ValueError("een relatie 'verwant' vraagt een toelichting")
        return self


class Reden(BaseModel):
    reden: str = Field(min_length=1, max_length=2000)

    @field_validator("reden")
    @classmethod
    def _reden(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("reden is verplicht")
        return v.strip()


class NieuweBetekenis(Reden):
    verwachte_revisie: int = Field(ge=1)


class Combineren(Reden):
    """Het begrip in de url blijft; `ander_begrip_id` wordt vervangen."""

    verwachte_revisie: int = Field(ge=1)
    ander_begrip_id: str = Field(min_length=1, max_length=64)
    ander_revisie: int = Field(ge=1)
