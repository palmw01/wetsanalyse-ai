"""Wirecontract voor de bronselectie per deelvraag (spoor J).

De voortgang is de stand van het wérk aan een deelvraag, los van haar inhoudelijke status (`actief`,
`vervangen`) en van de dekkingscheck (`gedekt`, `geen_bron`). Geen rij betekent `niet_gestart`.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

#: De sleutel van de analysevraag zelf, voor een werkgebied zonder deelvragen.
ANALYSEVRAAG = "analysevraag"


class Voortgang(str, Enum):
    niet_gestart = "niet_gestart"
    in_behandeling = "in_behandeling"
    voorlopig_afgerond = "voorlopig_afgerond"   # de analist sluit af; open punten mogen blijven staan
    beoordeeld = "beoordeeld"                   # door de poort: niets open, de analist bevestigt


class Fase(str, Enum):
    kern = "kern"                          # A: bepalingen die de vraag zelf regelen
    afhankelijkheden = "afhankelijkheden"  # C: definities, uitzonderingen, voorwaarden, delegaties
    afronden = "afronden"                  # D: wat er ligt en wat openstaat


class OpenPunt(BaseModel):
    tekst: str = Field(min_length=1, max_length=1000)


class StatusActie(BaseModel):
    """`openen` maakt de deelvraag de actieve (en start haar als dat nog niet gebeurd was) en draagt geen
    revisie: het is navigeren. De andere acties wijzigen de stand en dragen de revisie van de voortgang
    in beeld (412). Staat de voortgang al waar de actie heen wil, dan gebeurt er niets – een tweede klik
    of een opnieuw afgespeelde actie is geen conflict."""

    actie: Literal["openen", "fase", "afronden", "beoordelen", "heropenen"]
    verwachte_revisie: int | None = Field(default=None, ge=0)
    fase: Fase | None = None
    open_punten: list[OpenPunt] | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def _velden(self):
        if self.actie == "fase" and self.fase is None:
            raise ValueError("fase hoort bij actie fase")
        if self.actie != "openen" and self.verwachte_revisie is None:
            raise ValueError("verwachte_revisie is verplicht bij deze actie")
        return self


class KandidaatBesluit(BaseModel):
    """Een besluit over een kandidaat bij één deelvraag.

    - `opnemen` koppelt de bepaling aan deze deelvraag (en neemt haar zo nodig eerst op in het werkgebied);
      dat wijzigt de scope en draagt de revisie van het werkgebied. `rol` is de rol bij díé deelvraag.
    - `loskoppelen` haalt de koppeling met deze deelvraag weg; de bronselectie zelf blijft.
    - `uitsluiten` geldt voor deze deelvraag. Met `overal` geldt een uitsluiting voor het hele werkgebied: dan
      stelt Lex de bepaling bij geen enkele deelvraag meer voor. Een *later* bestaat niet: wie de vragen
      doorloopt, kiest; wat niet gekozen is, is niet gekozen.
    - `heropenen` haalt het besluit bij deze deelvraag weg (met `overal` ook het werkgebiedbrede)."""

    besluit: Literal["opnemen", "loskoppelen", "uitsluiten", "heropenen"]
    verwachte_revisie: int | None = Field(default=None, ge=1)
    rol: Literal["analyseren", "context"] | None = None
    reden: str = Field(default="", max_length=2000)
    overal: bool = False

    @model_validator(mode="after")
    def _velden(self):
        if self.besluit in ("opnemen", "loskoppelen") and self.verwachte_revisie is None:
            raise ValueError("verwachte_revisie is verplicht bij opnemen en loskoppelen")
        if self.besluit == "uitsluiten" and not self.reden.strip():
            raise ValueError("uitsluiten vraagt een reden")
        return self
