"""Wirecontract voor begrippen (spoor D, levering 2; slank volgens NL-SBB sinds spoor I1).

Een begrip is een analyse-uitkomst binnen één werkgebied, nooit een wettelijke definitie. De inhoud
volgt NL-SBB: term (naam, alternatieve termen), definitie, uitleg, context (toelichting) en
voorbeelden. Wat een oude rij nog meer draagt (JAS-duiding, begripstype, onderbouwing …) valt bij het
lezen weg (`extra="ignore"`).
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    afgeleid = "afgeleid"              # het element is de afleidingsregel die dit begrip afleidt: een tussenresultaat
    #                                    zonder eigen formulering (M01 §2.2.2 en h.6; M02 §1.2)
    context = "context"                # het element geeft context, draagt het begrip niet


class Beoordeling(str, Enum):
    open = "open"
    akkoord = "akkoord"
    afgewezen = "afgewezen"


class Voorbeeld(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tekst: str = Field(min_length=1, max_length=2000)
    oordeel: Oordeel
    # Waarom de stelling wel of niet waar is (M02 §3.5.5b, M03 ad 3a). Optioneel. Spoor I1 schrapte haar; besluit
    # eigenaar 25 nov 2026 haalt haar terug (plan lessen Termijnen §10, B5).
    toelichting: str = Field(default="", max_length=2000)


#: De soorten waarde die een begrip kan hebben (plan lessen Termijnen-bibliotheek, V2; D5 van het plan afleidingsregels).
WaardeSoort = Literal["ja_nee", "datum", "bedrag", "aantal", "duur", "tekst", "opsomming"]


class Waardebereik(BaseModel):
    """Wat voor waarde een variabele of parameter heeft: zonder waardebereik is een voorbeeld niet te toetsen en een regel
    niet te bouwen. Alles behalve de soort is optioneel; `waarden` alleen bij een opsomming."""
    model_config = ConfigDict(extra="forbid")

    soort: WaardeSoort
    eenheid: str = Field(default="", max_length=80)          # "euro", "dagen", "maanden"
    decimalen: int | None = Field(default=None, ge=0, le=10)
    minimum: str = Field(default="", max_length=40)          # als tekst: een datum, een bedrag of een aantal
    maximum: str = Field(default="", max_length=40)
    waarden: list[str] = Field(default_factory=list, max_length=100)
    toelichting: str = Field(default="", max_length=1000)     # "naar boven afgerond op hele euro's"

    @field_validator("waarden")
    @classmethod
    def _waarden(cls, v: list[str]) -> list[str]:
        uit = [w.strip() for w in v if w.strip()]
        if len({w.casefold() for w in uit}) != len(uit):
            raise ValueError("elke toegestane waarde één keer")
        return uit

    @model_validator(mode="after")
    def _opsomming(self) -> "Waardebereik":
        if self.soort == "opsomming" and not self.waarden:
            raise ValueError("een opsomming noemt haar toegestane waarden")
        if self.soort != "opsomming" and self.waarden:
            raise ValueError("toegestane waarden horen alleen bij een opsomming")
        return self


class KlasseKeuze(BaseModel):
    """De klasse van het begrip als de analist afwijkt van wat de markeringen zeggen: wat de tekst als rechtsobject noemt,
    kan in de regels een ja/nee-kenmerk zijn. Altijd met een reden."""
    model_config = ConfigDict(extra="forbid")

    klasse: str = Field(min_length=1, max_length=80)
    reden: str = Field(min_length=1, max_length=2000)

    @field_validator("klasse")
    @classmethod
    def _klasse(cls, v: str) -> str:
        from .jas_klassen import GELDIGE_JAS_KLASSEN
        if v not in GELDIGE_JAS_KLASSEN:
            raise ValueError("een van de dertien JAS-klassen")
        return v

    @field_validator("reden")
    @classmethod
    def _reden(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("reden is verplicht")
        return v.strip()


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
    # V2 en V4 (plan lessen Termijnen-bibliotheek, besluit gebruiker 24 nov 2026: P15 bijgesteld). Optioneel: een begrip
    # groeit, en de poort vraagt ze niet. De afgeleide klasse rekent de api bij het lezen (`begrip_store.klasse_van`).
    waardebereik: Waardebereik | None = None
    klasse_keuze: KlasseKeuze | None = None
    eigenaar: str = Field(default="", max_length=200)        # wie het begrip beheert (een organisatieonderdeel)

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
    """Een nieuw begrip, met de elementen waaruit het ontstaat. Zonder elementen weigert de store (422 `geen_passage`):
    een begrip rust altijd op minstens één annotatie. Geen `min_length` hier, zodat de fout een melding draagt."""

    inhoud: BegripInhoud
    element_ids: list[str] = Field(default_factory=list, max_length=200)
    rol: KoppelRol = KoppelRol.duiding


class BegripInhoudDeel(BegripInhoud):
    """De velden die een wijziging raakt: wat ontbreekt, blijft zoals het was (Termijnen e2e, 20 nov 2026: een PATCH
    vroeg de hele inhoud, en wat een client wegliet viel weg). De werkplek stuurt alles en merkt geen verschil."""

    naam: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("naam")
    @classmethod
    def _naam(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("naam is verplicht")
        return None if v is None else v.strip()


class BegripWijziging(BaseModel):
    verwachte_revisie: int = Field(ge=1)
    inhoud: BegripInhoudDeel

    @field_validator("inhoud", mode="before")
    @classmethod
    def _deel(cls, v):
        """Een volledige `BegripInhoud` (code die de hele inhoud meegeeft) telt als de velden die erin gezet zijn."""
        return v.model_dump(exclude_unset=True) if isinstance(v, BaseModel) else v
    #: De jurist is akkoord met de nieuwe inhoud: een geaccordeerd begrip wordt in dezelfde transactie opnieuw
    #: geaccordeerd als de poort het toelaat (zoals `KoppelInvoer.akkoord`). Eén aanroep in plaats van twee.
    akkoord: bool = False
    reden: str = Field(default="", max_length=2000)


class KoppelInvoer(BaseModel):
    verwachte_revisie: int = Field(ge=1)
    element_ids: list[str] = Field(min_length=1, max_length=200)
    rol: KoppelRol = KoppelRol.duiding
    motivatie: str = Field(default="", max_length=4000)
    #: De jurist zag de passages en is akkoord: de koppelingen zijn meteen beoordeeld, en een geaccordeerd begrip wordt
    #: opnieuw geaccordeerd als de poort het toelaat (zoals koppelen vanuit een groep). Eén aanroep in plaats van drie.
    akkoord: bool = False
    reden: str = Field(default="", max_length=2000)


class KoppelWijziging(BaseModel):
    verwachte_revisie: int = Field(ge=1)
    rol: KoppelRol | None = None
    motivatie: str | None = Field(default=None, max_length=4000)
    #: Zet de motivatie achter de bestaande (met wie), in plaats van haar te vervangen. Vervangen blijft de standaard
    #: (de werkplek bewerkt de tekst zelf); de vorige tekst staat dan in de audit (`motivatie_voor`).
    motivatie_aanvullen: bool = False
    beoordeling: Beoordeling | None = None


class Revisie(BaseModel):
    verwachte_revisie: int = Field(ge=1)


class Accordering(Revisie):
    """Accorderen zonder reden bestaat niet: de reden staat in de revisie en de audit, naast wie accordeerde."""

    reden: str = Field(min_length=1, max_length=2000)

    @field_validator("reden")
    @classmethod
    def _reden(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("reden is verplicht")
        return v.strip()


class KoppelSelectie(BaseModel):
    """Meer koppelingen van één begrip in één transactie en één revisie: alles of niets."""

    verwachte_revisie: int = Field(ge=1)
    koppeling_ids: list[str] = Field(min_length=1, max_length=500)

    @field_validator("koppeling_ids")
    @classmethod
    def _uniek(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("elke koppeling hoogstens één keer")
        return v


class KoppelBeoordelingen(KoppelSelectie):
    beoordeling: Beoordeling


class GebruikInvoer(BaseModel):
    """Een generiek begrip gebruiken in dit werkgebied (ADR-006)."""

    begrip_id: str = Field(min_length=1, max_length=64)


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
    # Alleen de generieke begrippen (ADR-006), of alleen die van een werkgebied.
    kader: Literal["generiek", "werkgebied"] | None = None


class BegripVerificatie(BaseModel):
    """Kandidaten uit de graaf laten bevestigen (`POST /v1/begrippen/verifieer`). `werkgebieden`: ook van
    deze werkgebieden de projectiehash van nu, als er geen begrip van gevonden is."""

    ids: list[str] = Field(default_factory=list, max_length=50)
    werkgebieden: list[str] = Field(default_factory=list, max_length=50)
