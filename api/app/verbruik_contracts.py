"""Contracten voor het tokenbudget: het beleid en de stand van één gebruiker.

Plain Pydantic (zoals `user.py`); de persistentie zit in `verbruik.py`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .user import _utcnow

# Vanaf dit percentage waarschuwen we de gebruiker. Bewust hier, náást de blokkadegrens, en niet in
# de frontend: anders kan de balk oranje worden op een ander moment dan waarop de tekst dat zegt.
WAARSCHUWINGSDREMPEL = 90

# De gebruikte tokens per venster; ook de bovengrens van het percentage. Boven de 100 doortellen
# heeft geen zin voor de UI (de meter zit vol), maar het ruwe `gebruikt` blijft ongekapt.
VOL = 100


class BudgetBeleid(BaseModel):
    """Het systeembrede beleid: hoe lang een venster duurt, en vanaf wanneer gerekend.

    Hoeveel tokens iemand heeft staat niet hier maar bij zijn rol (`RolBudget`).
    """

    periode_dagen: int = 7
    # Vast anker: alle vensters worden hiervandaan geteld, dus iedereen reset tegelijk.
    anker: datetime = Field(default_factory=_utcnow)
    # Uit = wel meten, niet begrenzen.
    actief: bool = True
    updated_by: str = ""
    updated: datetime = Field(default_factory=_utcnow)


class RolBudget(BaseModel):
    """Het tokenbudget van één rol, per venster."""

    rol: str
    tokens: int
    updated_by: str = ""
    updated: datetime | None = None


class Verbruiksstand(BaseModel):
    """Waar één gebruiker staat in het huidige venster.

    `budget` is het budget van zijn `rol`. `percentage` is gekapt op 100 zodat de meter niet overloopt; `gebruikt` is dat niet – een overschrijding hoort
    zichtbaar te blijven voor de beheerder.
    """

    userid: str = ""
    gebruikt: int = 0
    budget: int = 0
    percentage: int = 0
    resterend: int = 0
    # Wanneer de teller weer op nul staat. Dit is een berekening op het anker, geen geplande taak.
    reset_op: datetime = Field(default_factory=_utcnow)
    waarschuwing: bool = False
    geblokkeerd: bool = False
    # False = de begrenzing staat uit; er wordt dan wel geboekt maar niets tegengehouden.
    actief: bool = True
    # Leeg als er geen account bij hoort (een boeking op een tokenlabel).
    rol: str = ""
    # De laatste reset door een beheerder in dit venster; None = geen. Iets anders dan `reset_op`,
    # het einde van het venster: een reset verschuift dat einde niet.
    gereset_op: datetime | None = None
    # Wie dat deed. Alleen ingevuld voor het beheeroverzicht (`verbruik.standen`).
    gereset_door: str = ""
