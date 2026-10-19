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
    # Gezet door graph-qa bij het samenstellen in het gesprek: maak is dan idempotent op deze id.
    intake_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9-]{1,64}$")

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


# --- Deelvragen (vervolg op F, open keuze 4: optioneel) ---------------------------------------------

class DeelvraagStatus(str, Enum):
    actief = "actief"                  # hoort bij de analyse; de dekkingscheck meet ertegen
    voorgesteld = "voorgesteld"        # een voorstel van Lex, nog niet overgenomen
    afgewezen = "afgewezen"            # Lex stelt hem niet opnieuw voor


def _vraag(v: str) -> str:
    v = " ".join(v.split())
    if not v:
        raise ValueError("vraag is verplicht")
    return v


class DeelvraagInvoer(BaseModel):
    verwachte_revisie: int = Field(ge=1)
    vraag: str = Field(min_length=1, max_length=1000)

    @field_validator("vraag")
    @classmethod
    def _v(cls, v: str) -> str:
        return _vraag(v)


class DeelvraagWijziging(BaseModel):
    """Tekst of volgorde aanpassen, een voorstel overnemen (`status: actief`) of afwijzen (met reden)."""

    verwachte_revisie: int = Field(ge=1)
    vraag: str | None = Field(default=None, min_length=1, max_length=1000)
    volgorde: int | None = Field(default=None, ge=0, le=1000)
    status: DeelvraagStatus | None = None
    reden: str = Field(default="", max_length=2000)

    @field_validator("vraag")
    @classmethod
    def _v(cls, v: str | None) -> str | None:
        return None if v is None else _vraag(v)

    @model_validator(mode="after")
    def _afwijzen(self) -> DeelvraagWijziging:
        if self.status == DeelvraagStatus.afgewezen and not self.reden.strip():
            raise ValueError("afwijzen vraagt een reden")
        return self


class DeelvraagKoppelingen(BaseModel):
    """De bronselecties en begrippen die deze deelvraag beantwoorden – de hele set, niet een verschil."""

    verwachte_revisie: int = Field(ge=1)
    bronnen: list[str] = Field(default_factory=list, max_length=200)
    begrippen: list[str] = Field(default_factory=list, max_length=200)


class DeelvraagVoorstellen(BaseModel):
    """Van graph-qa: Lex splitst de analysevraag. Een voorstel draagt geen revisie; het raakt de scope pas
    als de analist het overneemt."""

    vragen: list[str] = Field(min_length=1, max_length=12)
    model: str = Field(default="", max_length=200)

    @field_validator("vragen")
    @classmethod
    def _v(cls, v: list[str]) -> list[str]:
        uit = [" ".join(x.split())[:1000] for x in v]
        return [x for x in uit if x]
