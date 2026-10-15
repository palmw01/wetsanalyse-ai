"""Wirecontract voor de voorstellen van Lex (spoor D, levering 3; ADR-004).

De uitkomst komt van graph-qa (`agent/begrippen_run.py`), in de vorm van de keten
(`begrippen_pipeline.model`): groepen, relaties en vragen. Analyseobjecten blijven intern (ADR-003):
pas een overgenomen voorstel is een begrip.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Voorstel(BaseModel):
    """Wat de keten bij een groep voorstelt: een naam en, als een lid een wettelijke term vastlegt,
    de letterlijke definitie uit de bron."""

    naam: str = Field(min_length=1, max_length=200)
    definitie: str = Field(default="", max_length=8000)
    definitie_bron_iri: str = ""
    definitie_vindplaats: str = ""


class UitkomstGroep(BaseModel):
    id: str = Field(pattern=r"^G[0-9a-f]{6,64}$")
    leden: list[str] = Field(min_length=2, max_length=500)
    aandacht: Literal["groen", "geel"]
    uitleg: list[str] = Field(default_factory=list)
    conflicten: list[str] = Field(default_factory=list)
    voorstel: Voorstel


class UitkomstRelatie(BaseModel):
    kandidaat_id: str
    hypothese: str
    van: str
    naar: str
    aandacht: Literal["groen", "geel"]
    uitleg: list[str] = Field(default_factory=list)


class UitkomstVraag(BaseModel):
    kandidaat_id: str
    van: str
    naar: str
    regel: str = ""
    uitleg: list[str] = Field(default_factory=list)


class UitkomstInvoer(BaseModel):
    manifest_id: str
    groepen: list[UitkomstGroep] = Field(default_factory=list, max_length=5000)
    relaties: list[UitkomstRelatie] = Field(default_factory=list, max_length=5000)
    vragen: list[UitkomstVraag] = Field(default_factory=list, max_length=5000)
    meting: dict = Field(default_factory=dict)


class MisluktInvoer(BaseModel):
    reden: str = Field(min_length=1, max_length=2000)


class Overname(BaseModel):
    """Eén begrip uit één of meer groepen. Meer groepen = combineren; een deel van de leden =
    splitsen of een element eruit halen."""

    groep_ids: list[str] = Field(min_length=1, max_length=50)
    naam: str = Field(min_length=1, max_length=200)
    element_ids: list[str] | None = Field(default=None, max_length=500)
    met_definitie: bool = True


class GroepKoppeling(BaseModel):
    begrip_id: str
    element_ids: list[str] | None = Field(default=None, max_length=500)


class GroepBesluit(BaseModel):
    reden: str = Field(default="", max_length=2000)


class VraagBesluit(BaseModel):
    antwoord: Literal["samen", "apart"]
