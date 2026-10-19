"""Wirecontract voor bronnen vinden met Lex (spoor D, fase A).

De uitkomst komt van graph-qa (`agent/bronnen_vinden.py`): kandidaatbepalingen met hun rol en per
ontdekmethode het bewijs. Alles zonder model; de methoden zijn graafqueries.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Methode = Literal["overzicht", "deelvraag", "verwijzing_uit", "verwijzing_in", "definitie", "opbouw", "gelijkenis"]
KandidaatRol = Literal["kern", "afhankelijkheid", "aanverwant"]

#: Sterk naar zwak: bij samenvoegen wint de sterkste rol.
ROL_VOLGORDE: dict[str, int] = {"kern": 0, "afhankelijkheid": 1, "aanverwant": 2}


class Bewijs(BaseModel):
    """Waarom één methode deze bepaling vond. `vanuit` is de bepaling in de selectie (leeg bij het
    overzicht: dat zoekt op de analysevraag); `detail` draagt wat de methode zelf weet –
    verwijzings-id, ankertekst en functie, het gedefinieerde begrip, of de zoekterm. Bij `deelvraag` (het
    overzicht op één deelvraag) staan `deelvraag_id` en `vraag` in `detail`."""

    methode: Methode
    vanuit: str = Field(default="", max_length=500)
    detail: dict = Field(default_factory=dict)


class UitkomstKandidaat(BaseModel):
    bron_iri: str = Field(pattern=r"^urn:bwb:BWB[A-Z]\d{7}(:.+)?$", max_length=500)
    label: str = Field(default="", max_length=500)
    bwb_id: str = Field(default="", max_length=32)
    rol: KandidaatRol
    bewijs: list[Bewijs] = Field(min_length=1, max_length=50)


class MethodeMeting(BaseModel):
    """Per methode: hoeveel ze vond en of ze een plafond raakte of de graaf haperde."""

    aantal: int = Field(ge=0)
    volledig: bool = True
    ms: int = Field(default=0, ge=0)


class BronnenUitkomst(BaseModel):
    invoer_id: str = Field(min_length=1, max_length=32)
    kandidaten: list[UitkomstKandidaat] = Field(default_factory=list, max_length=500)
    meting: dict[Methode, MethodeMeting] = Field(default_factory=dict)


class BronnenMislukt(BaseModel):
    reden: str = Field(min_length=1, max_length=2000)


class Opnemen(BaseModel):
    """Een kandidaat opnemen als bronselectie. Zonder `rol`: *analyseren* bij een kernbepaling,
    anders *context*. Opnemen wijzigt de scope, dus het draagt de revisie in beeld."""

    verwachte_revisie: int = Field(ge=1)
    rol: Literal["analyseren", "context"] | None = None
    reden: str = Field(default="", max_length=2000)


class Uitsluiten(BaseModel):
    """Uitsluiten vraagt een reden: anders weet niemand later waarom Lex hem niet meer voorstelt."""

    reden: str = Field(min_length=1, max_length=2000)
