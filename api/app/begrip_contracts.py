"""Wirecontract voor begrippen (spoor D, levering 2).

Een begrip is een analyse-uitkomst binnen één werkgebied, nooit een wettelijke definitie. De inhoud
houdt definitie, letterlijke herkomst en toelichting uit elkaar (PLAN D, uitgangspunt 4).
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator

from .validation import GELDIGE_JAS_KLASSEN


class Herkomst(str, Enum):
    letterlijk = "letterlijk"          # de definitie staat zo in de bron
    samengesteld = "samengesteld"      # uit meerdere bronpassages samengesteld
    geformuleerd = "geformuleerd"      # door de analist geformuleerd


class Oordeel(str, Enum):
    wel = "wel"
    niet = "niet"
    onzeker = "onzeker"


class KoppelRol(str, Enum):
    duiding = "duiding"                # het element duidt dit begrip aan (primair: één per element)
    definitie = "definitie"            # het element ondersteunt de definitie (bv. een brondefinitie)
    context = "context"                # het element geeft context, draagt het begrip niet


class Beoordeling(str, Enum):
    open = "open"
    akkoord = "akkoord"
    afgewezen = "afgewezen"


class Voorbeeld(BaseModel):
    tekst: str = Field(min_length=1, max_length=2000)
    oordeel: Oordeel
    toelichting: str = Field(default="", max_length=2000)


class BegripInhoud(BaseModel):
    """Alles optioneel behalve de naam: een begrip groeit. De accorderingspoort vraagt de rest."""

    naam: str = Field(min_length=1, max_length=200)
    alternatieve_termen: list[str] = Field(default_factory=list, max_length=50)
    context: str = Field(default="", max_length=4000)
    jas_klasse: str = ""
    # Dezelfde vaste lijst als bij een annotatie-element (`annotatie_v2_contracts.Element`).
    jas_subtype: str = Field(default="", pattern=r"^(|variabele|variabelewaarde|parameter|parameterwaarde|delegatiebevoegdheid|delegatie-invulling)$")
    geldigheid: str = Field(default="", max_length=1000)
    definitie: str = Field(default="", max_length=8000)
    definitie_herkomst: Herkomst | None = None
    uitleg: str = Field(default="", max_length=8000)
    onderbouwing: str = Field(default="", max_length=8000)
    voorbeelden: list[Voorbeeld] = Field(default_factory=list, max_length=100)
    eigenschappen: dict[str, str] = Field(default_factory=dict)
    open_vragen: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("naam")
    @classmethod
    def _naam(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("naam is verplicht")
        return v.strip()

    @field_validator("alternatieve_termen", "open_vragen")
    @classmethod
    def _lijst(cls, v: list[str]) -> list[str]:
        return [t.strip() for t in v if t.strip()]

    @field_validator("jas_klasse")
    @classmethod
    def _klasse(cls, v: str) -> str:
        if v and v not in GELDIGE_JAS_KLASSEN:
            raise ValueError(f"onbekende JAS-klasse: {v}")
        return v


class BegripInvoer(BaseModel):
    """Een nieuw begrip, eventueel meteen met de elementen waaruit het ontstaat."""

    inhoud: BegripInhoud
    element_ids: list[str] = Field(default_factory=list, max_length=200)
    rol: KoppelRol = KoppelRol.duiding


class BegripWijziging(BaseModel):
    verwachte_revisie: int = Field(ge=1)
    inhoud: BegripInhoud


class KoppelInvoer(BaseModel):
    verwachte_revisie: int = Field(ge=1)
    element_ids: list[str] = Field(min_length=1, max_length=200)
    rol: KoppelRol = KoppelRol.duiding
    motivatie: str = Field(default="", max_length=4000)


class KoppelWijziging(BaseModel):
    verwachte_revisie: int = Field(ge=1)
    rol: KoppelRol | None = None
    motivatie: str | None = Field(default=None, max_length=4000)
    beoordeling: Beoordeling | None = None


class Revisie(BaseModel):
    verwachte_revisie: int = Field(ge=1)
