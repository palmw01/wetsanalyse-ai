"""Wirecontract voor Lex naast de kaart (spoor D, fase E): kaartruns en kaartvoorstellen.

Een kaartrun is één actie van Lex op één begrip; wat hij oplevert zijn voorstellen per veld. Een
voorstel wijzigt niets: pas `VoorstelOvername` door de analist raakt het begrip.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .begrip_contracts import Oordeel
from .begrippen_run_contracts import KaartFragment

Actie = Literal["brondefinitie", "scherper", "betekenisverschil", "voorbeelden"]
# `context` is het veld toelichting van NL-SBB (`skos:scopeNote`); in beeld heet het *Toelichting*.
Veld = Literal["definitie", "uitleg", "context", "voorbeelden"]

#: Welke velden een actie mag voorstellen.
VELDEN: dict[str, set[str]] = {
    "brondefinitie": {"definitie"},
    "scherper": {"definitie"},
    "betekenisverschil": {"uitleg", "context"},
    "voorbeelden": {"voorbeelden"},
}

#: Acties die het model gebruiken (en dus tokens kosten); brondefinitie is een graafquery.
MODEL_ACTIES = {"scherper", "betekenisverschil", "voorbeelden"}


class KaartRunStart(BaseModel):
    actie: Actie
    # Alleen bij `betekenisverschil`: het begrip waarmee Lex vergelijkt.
    ander_begrip_id: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def _ander(self) -> "KaartRunStart":
        if (self.actie == "betekenisverschil") != bool(self.ander_begrip_id):
            raise ValueError("ander_begrip_id hoort bij betekenisverschil, en alleen daar")
        return self


class DefinitieWaarde(BaseModel):
    definitie: str = Field(min_length=1, max_length=8000)
    herkomst: Literal["letterlijk", "samengesteld", "geformuleerd"]
    fragmenten: list[KaartFragment] = Field(default_factory=list, max_length=60)
    definitie_bron_iri: str = ""
    definitie_vindplaats: str = Field(default="", max_length=500)
    # Waar Lex de brondefinitie vond (fase E, *Zoek de brondefinitie*), van sterk naar zwak.
    vindplaats_soort: Literal["", "werkgebied", "regeling", "definitieverwijzing", "elders"] = ""

    @model_validator(mode="after")
    def _vorm(self) -> "DefinitieWaarde":
        if self.herkomst == "letterlijk" and not self.definitie_bron_iri:
            raise ValueError("een letterlijke definitie noemt haar bron")
        if self.herkomst in ("samengesteld", "geformuleerd") and not self.fragmenten:
            raise ValueError("een samengestelde of geformuleerde definitie noemt haar fragmenten")
        return self


class VoorstelInvoer(BaseModel):
    """Eén voorstel van graph-qa. `definitie` bij het veld definitie; `tekst` bij de andere velden
    (een alinea uitleg, een toelichting, een voorbeeld), met `oordeel` bij een voorbeeld."""

    veld: Veld
    definitie: DefinitieWaarde | None = None
    tekst: str = Field(default="", max_length=4000)
    oordeel: Oordeel | None = None
    fragmenten: list[KaartFragment] = Field(default_factory=list, max_length=60)
    # Bij betekenisverschil: de uitkomst van de vergelijking (de vier van ADR-004).
    vergelijking: Literal["zelfde_betekenis", "verwant", "verschil", "onbeslist"] | None = None
    motivatie: str = Field(default="", max_length=2000)
    aandacht: Literal["groen", "geel"] = "geel"
    aandachtspunten: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _vorm(self) -> "VoorstelInvoer":
        if self.veld == "definitie":
            if self.definitie is None:
                raise ValueError("een definitievoorstel draagt een definitie")
            if self.definitie.herkomst == "geformuleerd" and self.aandacht != "geel":
                raise ValueError("een door Lex geformuleerde definitie is nooit groen")
        elif not self.tekst.strip():
            raise ValueError(f"een voorstel voor {self.veld} draagt een tekst")
        if self.veld == "voorbeelden" and self.oordeel is None:
            raise ValueError("een voorbeeld heeft een verwacht oordeel")
        return self


class KaartUitkomst(BaseModel):
    invoer_id: str = Field(min_length=1, max_length=32)
    voorstellen: list[VoorstelInvoer] = Field(default_factory=list, max_length=20)
    # Waarom er niets (of minder) is, in de woorden van Lex – bv. "Geen brondefinitie gevonden".
    melding: str = Field(default="", max_length=2000)
    model: str = Field(default="", max_length=128)
    promptversie: str = Field(default="", max_length=32)
    tokens: int = Field(default=0, ge=0)
    meting: dict = Field(default_factory=dict)


class KaartMislukt(BaseModel):
    reden: str = Field(default="", max_length=2000)


class VoorstelOvername(BaseModel):
    verwachte_revisie: int = Field(ge=1)
    # Wat de analist anders wil dan het voorstel: de definitie- of veldtekst. Met een andere tekst is
    # het voorstel `aangepast` en de definitie van de analist.
    aanpassing: str | None = Field(default=None, max_length=8000)
    oordeel: Oordeel | None = None       # alleen bij een voorbeeld
    # Bij een verouderd definitievoorstel: de definitie die de analist naast het voorstel zag. Klopt die
    # nog, dan is vervangen een bewuste keuze en mag het; anders weer 409 – nooit stil overschrijven.
    nu_gezien: str | None = Field(default=None, max_length=8000)


class VoorstelAfwijzing(BaseModel):
    reden: str = Field(default="", max_length=2000)
