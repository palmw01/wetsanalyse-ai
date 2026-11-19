"""Wirecontract voor afleidingsregels (activiteit 3b, ADR-018).

Een regel leidt precies één begrip af (de uitvoer) uit andere begrippen (de invoer), en heeft een begrip voor zichzelf
("bepalen <uitvoer>"). Hij heeft altijd één of meer gevallen: een regel met één geval heeft één rij (ADR-018 §3). Een
geval heeft voorwaarden (een boom van "alle" en "één van") en een uitkomst (begrippen, operatorbegrippen en vaste tekst
op volgorde). De regeltekst wordt afgeleid (`regeltekst.py`), nooit getypt; de toelichting is vrij.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_ID = r"^[A-Za-z0-9._:-]{1,64}$"


class RegelSoort(str, Enum):
    rekenregel = "rekenregel"          # een hoogte, aantal, duur of datum
    beslisregel = "beslisregel"        # ja of nee, ook: bestaat een recht of bevoegdheid
    specialisatie = "specialisatie"    # hoort een rechtssubject of rechtsobject tot een groep


class Brontype(str, Enum):
    wet = "wet"
    beleid = "beleid"                  # de grondslag is een beleidsregel: accorderen geeft `geaccordeerd_als_beleidsregel`


class DragerRol(str, Enum):
    grondslag = "grondslag"            # de Afleidingsregel, of de formulering van het afgeleide begrip (ADR-018 §2)
    voorwaarde = "voorwaarde"
    invoer = "invoer"
    uitvoer = "uitvoer"
    tijd = "tijd"
    context = "context"


class Beoordeling(str, Enum):
    open = "open"
    akkoord = "akkoord"
    afgewezen = "afgewezen"


class VoorbeeldOordeel(str, Enum):
    open = "open"                      # nog niet beoordeeld (een voorstel van Lex)
    juist = "juist"                    # de uitkomst is juridisch juist
    onjuist = "onjuist"                # de regel geeft een uitkomst die niet klopt
    kan_niet = "kan_niet"              # deze invoer mag zich niet voordoen


class Term(BaseModel):
    """Eén stuk van een uitkomst. `begrip` en `operator` verwijzen naar een begrip (een operatorbegrip ontstaat op een
    gemarkeerde formulering, #1766); `tekst` is vaste taal van het patroon of een tijdsaanduiding ("een maand na")."""
    model_config = ConfigDict(extra="ignore")

    soort: Literal["begrip", "operator", "tekst"]
    begrip_id: str = Field(default="", max_length=64)
    tekst: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def _vorm(self) -> "Term":
        if self.soort in ("begrip", "operator") and not self.begrip_id:
            raise ValueError(f"een {self.soort} verwijst naar een begrip")
        if self.soort == "tekst" and not self.tekst.strip():
            raise ValueError("een tekst is niet leeg")
        return self


class Voorwaarde(BaseModel):
    """Een blad: de omschrijving "indien …" in eigen woorden, met de markeringen waarop ze rust."""
    model_config = ConfigDict(extra="ignore")

    tekst: str = Field(min_length=1, max_length=1000)
    element_ids: list[str] = Field(default_factory=list, max_length=20)
    niet: bool = False


class Voorwaarden(BaseModel):
    """Een groep: alle delen moeten gelden, of ten minste één. Genest tot elke diepte (M02 §3.5.5)."""
    model_config = ConfigDict(extra="ignore")

    verband: Literal["alle", "een_van"] = "alle"
    delen: list[Union["Voorwaarden", Voorwaarde]] = Field(min_length=1, max_length=40)


class Geval(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str = Field(default="", max_length=80)
    voorwaarden: Voorwaarden | None = None
    uitkomst: list[Term] = Field(min_length=1, max_length=40)
    voorrang: int = Field(default=0, ge=0, le=100)      # hoger gaat voor bij overlap (R7: rij 2 gaat voor)


class Invoer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    begrip_id: str = Field(pattern=_ID)
    rol: Literal["invoer", "parameter"] = "invoer"


class RegelVoorbeeld(BaseModel):
    model_config = ConfigDict(extra="ignore")

    geval: str = Field(default="", max_length=80)         # het label; leeg bij een regel met één geval
    invoer: str = Field(min_length=1, max_length=2000)
    uitkomst: str = Field(min_length=1, max_length=2000)
    oordeel: VoorbeeldOordeel = VoorbeeldOordeel.open
    toelichting: str = Field(default="", max_length=2000)


class RegelInhoud(BaseModel):
    model_config = ConfigDict(extra="ignore")

    soort: RegelSoort
    regelbegrip_id: str = Field(pattern=_ID)
    uitvoer_begrip_id: str = Field(pattern=_ID)
    # Bij een beslisregel of specialisatie: over wie of wat de regel beslist ("Een natuurlijke persoon is …").
    onderwerp_begrip_id: str = Field(default="", max_length=64)
    invoer: list[Invoer] = Field(default_factory=list, max_length=40)
    gevallen: list[Geval] = Field(min_length=1, max_length=40)
    voorbeelden: list[RegelVoorbeeld] = Field(default_factory=list, max_length=100)
    toelichting: str = Field(default="", max_length=8000)
    brontype: Brontype = Brontype.wet
    # Het lidwoord van de uitvoer in het taalpatroon ("Het termijnbedrag moet …"): het begrip draagt het niet.
    lidwoord: Literal["de", "het", ""] = "de"

    @field_validator("gevallen")
    @classmethod
    def _labels(cls, v: list[Geval]) -> list[Geval]:
        if len(v) > 1:
            labels = [g.label.strip() for g in v]
            if not all(labels):
                raise ValueError("bij meer gevallen heeft elk geval een label")
            if len(set(labels)) != len(labels):
                raise ValueError("de labels van de gevallen zijn uniek")
        return v

    @model_validator(mode="after")
    def _uitvoer_niet_invoer(self) -> "RegelInhoud":
        if any(i.begrip_id == self.uitvoer_begrip_id for i in self.invoer):
            raise ValueError("de uitvoer is geen invoer van dezelfde regel")
        return self


class DragerInvoer(BaseModel):
    element_id: str = Field(pattern=_ID)
    rol: DragerRol
    geval: str = Field(default="", max_length=80)


class RegelAanmaak(BaseModel):
    inhoud: RegelInhoud
    # De grondslag is verplicht: een regel zonder grondslag in de tekst bestaat niet (ADR-018 §2, #1760).
    dragers: list[DragerInvoer] = Field(min_length=1, max_length=60)
    herkomst: Literal["lex", "jurist", "import"] = "jurist"


class Revisie(BaseModel):
    verwachte_revisie: int = Field(ge=1)


class RegelWijziging(Revisie):
    inhoud: RegelInhoud


class DragersToevoegen(Revisie):
    dragers: list[DragerInvoer] = Field(min_length=1, max_length=60)


class DragerWijziging(Revisie):
    beoordeling: Beoordeling


class Accordering(Revisie):
    reden: str = Field(default="", max_length=2000)


class ParameterWaardeInvoer(BaseModel):
    parameter_begrip_id: str = Field(pattern=_ID)
    waarde_begrip_id: str = Field(default="", max_length=64)
    waarde: str = Field(min_length=1, max_length=200)
    eenheid: str = Field(default="", max_length=40)
    geldig_vanaf: str = Field(default="", pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    geldig_tot: str = Field(default="", pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    element_id: str = Field(default="", max_length=64)
    getoetst: str = Field(default="", max_length=500)
