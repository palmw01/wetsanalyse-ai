"""De contracten van een delegatie (ADR-016 §A5): het object waarmee graph-qa werk aan kindgesprekken bijhoudt.

Een delegatie veralgemeent de regie van ADR-012. Er zijn twee soorten:

- **`regie`**: de regisseur verdeelt het werk in een werkgebied per deelvraag, met een plan uit code (`opdracht`
  `bronnen` of `annoteren`). Hoogstens één lopende regie per werkgebied;
- **`subagent`**: de centrale agent zet één subagent aan het werk (`opdracht` `subagent`), in een werkgebied of
  daarbuiten. Het plan noemt per taak het profiel, zijn versie en de opdracht.

Voor beide geldt: hoogstens één lopende delegatie per gebruiker (en dus per gesprek).

graph-qa stuurt deze velden: de regisseur (`agent/regie/regisseur.py`) en de subagent van de centrale agent."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Soort = Literal["regie", "subagent"]
Opdracht = Literal["bronnen", "annoteren", "subagent"]
DelegatieStatus = Literal["loopt", "klaar", "gestopt", "mislukt"]
EINDSTANDEN = ("klaar", "gestopt", "mislukt")

#: Welke opdrachten bij welke soort horen.
OPDRACHTEN: dict[str, tuple[str, ...]] = {"regie": ("bronnen", "annoteren"), "subagent": ("subagent",)}


class DelegatieStart(BaseModel):
    """Een delegatie begint in een gesprek van de gebruiker. Een regie hoort bij een werkgebied; een subagent mag ook
    in een los gesprek (`werkgebied_id` leeg). Het werkgebied is altijd dat van het gesprek."""
    soort: Soort = "regie"
    werkgebied_id: str = Field(default="", max_length=64)
    gesprek_id: str = Field(min_length=1, max_length=64)
    opdracht: Opdracht
    plan_id: str = Field(pattern=r"^[A-Za-z0-9]{8,64}$")
    plan: dict = Field(default_factory=dict)
    budget_aandeel: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _past(self) -> DelegatieStart:
        if self.opdracht not in OPDRACHTEN[self.soort]:
            raise ValueError(f"de opdracht {self.opdracht} hoort niet bij een {self.soort}")
        if self.soort == "regie" and not self.werkgebied_id:
            raise ValueError("een regie hoort bij een werkgebied")
        return self


class DelegatieWijziging(BaseModel):
    """`loopt` is een teken van leven (de hartslag); een eindstand sluit de delegatie af, met de uitkomst."""
    status: DelegatieStatus
    uitkomst: dict | None = None


class Delegatie(BaseModel):
    id: str
    soort: Soort = "regie"
    werkgebied_id: str = ""
    gesprek_id: str
    user_id: str
    opdracht: Opdracht
    plan_id: str
    plan: dict = {}
    status: DelegatieStatus
    uitkomst: dict = {}
    budget_aandeel: int = 0
    gestart: datetime | None = None
    hartslag: datetime | None = None
    afgerond: datetime | None = None
