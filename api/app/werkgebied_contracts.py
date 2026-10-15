"""Wirecontract voor werkgebieden (spoor D, levering 1)."""
from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class Status(str, Enum):
    in_voorbereiding = "in_voorbereiding"
    actief = "actief"
    afgerond = "afgerond"


class Bereik(str, Enum):
    node = "node"                      # alleen deze bronnode
    onderliggend = "onderliggend"      # deze bronnode met alles eronder (standaard: het hele artikel)


class Rol(str, Enum):
    analyseren = "analyseren"          # de elementen horen bij de werkvoorraad
    context = "context"                # ondersteunt (bv. een definitie), geen werkvoorraad


_DATUM = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _peildatum(v: str | None) -> str | None:
    if v in (None, ""):
        return None
    if not _DATUM.match(v):
        raise ValueError("peildatum als JJJJ-MM-DD")
    return v


class WerkgebiedInvoer(BaseModel):
    naam: str = Field(min_length=1, max_length=200)
    analysevraag: str = Field(default="", max_length=4000)
    afbakening: str = Field(default="", max_length=4000)
    peildatum: str | None = None

    @field_validator("peildatum")
    @classmethod
    def _p(cls, v: str | None) -> str | None:
        return _peildatum(v)

    @field_validator("naam")
    @classmethod
    def _naam(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("naam is verplicht")
        return v.strip()


class WerkgebiedWijziging(BaseModel):
    verwachte_revisie: int = Field(ge=1)
    naam: str | None = Field(default=None, min_length=1, max_length=200)
    analysevraag: str | None = Field(default=None, max_length=4000)
    afbakening: str | None = Field(default=None, max_length=4000)
    peildatum: str | None = None
    status: Status | None = None

    @field_validator("peildatum")
    @classmethod
    def _p(cls, v: str | None) -> str | None:
        return _peildatum(v)


class BronselectieInvoer(BaseModel):
    """Een bepaling toevoegen: via de bron-IRI, of via regeling + artikel (+ lid)."""

    verwachte_revisie: int = Field(ge=1)
    bron_iri: str = ""
    bwb_id: str = ""
    artikel: str = ""
    lid: str = ""
    bereik: Bereik = Bereik.onderliggend
    rol: Rol = Rol.analyseren
    reden: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def _doel(self) -> BronselectieInvoer:
        if not self.bron_iri and not (self.bwb_id and self.artikel):
            raise ValueError("geef een bron_iri, of een bwb_id met artikel")
        return self


class BronselectieWijziging(BaseModel):
    verwachte_revisie: int = Field(ge=1)
    rol: Rol | None = None
    reden: str | None = Field(default=None, max_length=2000)
