"""De contracten van een regie (ADR-012): het object dat de regisseur van graph-qa bij de api bijhoudt.

graph-qa leest de contracten uit deze bron (`tools/graph-qa/tests/test_regie_contract.py`), zoals bij de
andere runsoorten; een veld hier hoort daar ook."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Opdracht = Literal["bronnen", "annoteren"]
RegieStatus = Literal["loopt", "klaar", "gestopt", "mislukt"]
EINDSTANDEN = ("klaar", "gestopt", "mislukt")


class RegieStart(BaseModel):
    """Een regie begint in een regiegesprek, met het plan dat de jurist bevestigde."""
    gesprek_id: str = Field(min_length=1, max_length=64)
    opdracht: Opdracht
    plan_id: str = Field(pattern=r"^[A-Za-z0-9]{8,64}$")
    plan: dict = Field(default_factory=dict)
    budget_aandeel: int = Field(default=0, ge=0)


class RegieWijziging(BaseModel):
    """`loopt` is een teken van leven (de hartslag); een eindstand sluit de regie af, met de uitkomst."""
    status: RegieStatus
    uitkomst: dict | None = None


class Regie(BaseModel):
    id: str
    werkgebied_id: str
    gesprek_id: str
    user_id: str
    opdracht: Opdracht
    plan_id: str
    plan: dict = {}
    status: RegieStatus
    uitkomst: dict = {}
    budget_aandeel: int = 0
    gestart: datetime | None = None
    hartslag: datetime | None = None
    afgerond: datetime | None = None
