"""Wirecontract voor begrippen (spoor D, levering 2; slank volgens NL-SBB sinds spoor I1).

Een begrip is een analyse-uitkomst binnen één werkgebied, nooit een wettelijke definitie. De inhoud
volgt NL-SBB: term (naam, alternatieve termen), definitie, uitleg, context (toelichting) en
voorbeelden. Wat een oude rij nog meer draagt (JAS-duiding, begripstype, onderbouwing …) valt bij het
lezen weg (`extra="ignore"`).
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    model_config = ConfigDict(extra="ignore")

    tekst: str = Field(min_length=1, max_length=2000)
    oordeel: Oordeel


class BegripInhoud(BaseModel):
    """Alles optioneel behalve de naam: een begrip groeit. De accorderingspoort vraagt de rest."""

    model_config = ConfigDict(extra="ignore")

    naam: str = Field(min_length=1, max_length=200)
    alternatieve_termen: list[str] = Field(default_factory=list, max_length=50)
    # NL-SBB `skos:scopeNote`: de grenzen of het gebruik van het begrip (in beeld: *Toelichting*).
    context: str = Field(default="", max_length=4000)
    definitie: str = Field(default="", max_length=8000)
    # De api rekent herkomst en `definitie_door` bij elke schrijfactie (`begrip_store.met_afgeleid`); wat
    # een client meestuurt telt niet. Letterlijk is alleen een overgenomen brondefinitie.
    definitie_herkomst: Herkomst | None = None
    # Wie de definitie voorstelde (fase E): `lex` als ze van een voorstel van Lex komt en ongewijzigd
    # is overgenomen, `analist` zodra een mens de tekst schreef of aanpaste; leeg = onbekend of geen
    # definitie.
    definitie_door: Literal["", "analist", "lex"] = ""
    # NL-SBB `rdfs:comment`: in eenvoudige taal (B1), gericht op begrijpen.
    uitleg: str = Field(default="", max_length=8000)
    voorbeelden: list[Voorbeeld] = Field(default_factory=list, max_length=100)

    @field_validator("naam")
    @classmethod
    def _naam(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("naam is verplicht")
        return v.strip()

    @field_validator("alternatieve_termen")
    @classmethod
    def _lijst(cls, v: list[str]) -> list[str]:
        return [t.strip() for t in v if t.strip()]


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


# --- Lezen over werkgebieden heen (fase F4) -----------------------------------------------------

class BegripStatus(str, Enum):
    concept = "concept"
    geaccordeerd = "geaccordeerd"
    vervangen = "vervangen"


class BegripZoekvraag(BaseModel):
    """Zoeken in de begrippen van alle actieve werkgebieden (`GET /v1/begrippen`). graph-qa
    (`search_begrippen`) vraagt niets wat hier niet staat – `tests/test_contract_drift.py` daar."""

    q: str = Field(default="", max_length=200)
    status: list[BegripStatus] = Field(default_factory=list, max_length=3)
    werkgebied_id: str | None = Field(default=None, max_length=64)
    # Het werkgebied van de vrager: zijn begrippen staan bij een gelijke treffer vooraan.
    eerst: str | None = Field(default=None, max_length=64)


class BegripVerificatie(BaseModel):
    """Kandidaten uit de graaf laten bevestigen (`POST /v1/begrippen/verifieer`). `werkgebieden`: ook van
    deze werkgebieden de projectiehash van nu, als er geen begrip van gevonden is."""

    ids: list[str] = Field(default_factory=list, max_length=50)
    werkgebieden: list[str] = Field(default_factory=list, max_length=50)
