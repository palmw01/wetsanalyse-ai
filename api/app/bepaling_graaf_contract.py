"""Wat de graaf over één bepaling weet, als contract: gedeeld door het paneel naast het gesprek en het werkgebiedrapport.

ADR-008 (*Detail bij een antwoord*) en ADR-009: geen gedeeld blokkenmodel tussen gesprek en rapport, wel één graaflezing per
bepaling (`bepaling_graaf`, ADR-009 is de eigenaar). `Structuurdeel`, `Verwijzing` en `RegelingInfo` zijn de bouwstenen die het
rapport ook gebruikt; `BepalingDetail` is wat het paneel toont. Alles komt letterlijk uit de graaf, zonder model: een waarde die de graaf niet heeft, is leeg en wordt niet geraden.
"""
from __future__ import annotations

from typing import Literal

from bronmodel.antwoord import Vindplaats
from pydantic import BaseModel, ConfigDict

VERSIE = 1
#: Zoveel voorbeelden draagt een telling: het paneel noemt het aantal en de eerste paar, nooit een lange lijst.
MAX_VOORBEELDEN = 10
#: Zoveel uitgaande verwijzingen toont het paneel; daarboven zegt `verwijst_naar_volledig` het.
MAX_UITGAAND = 50


class _Deel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Structuurdeel(_Deel):
    """Een deel boven de bepaling in de opbouw van haar regeling (hoofdstuk, afdeling, paragraaf, divisie, artikel)."""

    soort: str
    nummer: str = ""
    #: Het opschrift (`bwb:titel`), als de graaf er een heeft.
    titel: str = ""
    iri: str


class Verwijzing(_Deel):
    """Eén verwijzing in de tekst, met de ankertekst letterlijk. `van` is het lid of onderdeel waar ze staat."""

    van: Vindplaats
    naar: Vindplaats
    anker: str = ""
    #: Staat het doel in de graaf? Een regeling buiten de import is niet te openen.
    in_graaf: bool = True
    #: Staat het doel in het werkgebied (zelf, of een van zijn delen)? Alleen het rapport vult het; het paneel kent geen dossier.
    in_dossier: bool = False
    door: Literal["bron"] = "bron"


class RegelingInfo(_Deel):
    """De regeling zoals de graaf haar kent (WTI en toestand)."""

    bwb_id: str
    citeertitel: str
    geldig_vanaf: str | None = None
    geldig_tot: str | None = None
    soort: str = ""
    afkorting: str = ""
    #: `bwb:eerstverantwoordelijke`
    verantwoordelijke: str = ""
    #: TOOI-IRI van de verantwoordelijke organisatie
    organisatie: str = ""
    toestand_url: str = ""
    #: De regeling op wetten.overheid.nl
    url: str = ""


class Telling(_Deel):
    """Een aantal met de eerste voorbeelden: wat het paneel noemt zonder honderd regels te tonen."""

    aantal: int = 0
    #: Onwaar als het aantal niet geteld kon worden en de rijen op hun grens stonden: dan is het "minstens" `aantal`.
    volledig: bool = True
    items: list[Vindplaats] = []


class BepalingDetail(_Deel):
    schema_versie: int = VERSIE
    bron_iri: str
    #: Onwaar als de graaf niet te lezen was: dan staat er niets, en zegt het paneel dat. Nooit een stille leegte.
    beschikbaar: bool = True
    vindplaats: Vindplaats
    plaats: list[Structuurdeel] = []
    status: str = ""
    inwerking: str | None = None
    terugwerkend_tot: str | None = None
    #: De publicatie van de laatste wijziging (`bwb:bron`, bv. "Stb.2009-610").
    gewijzigd_bij: str = ""
    #: De toestand van de regeling die de graaf draagt.
    geldig_vanaf: str | None = None
    geldig_tot: str | None = None
    toestand_url: str = ""
    verwijst_naar: list[Verwijzing] = []
    #: Het echte aantal uitgaande verwijzingen; `verwijst_naar` draagt er hoogstens `MAX_UITGAAND`.
    verwijst_naar_aantal: int = 0
    verwijst_naar_volledig: bool = True
    verwezen_door: Telling = Telling()
    grondslag_voor: Telling = Telling()
    bevoegdheid_voor: Telling = Telling()
    genoemd_in: Telling = Telling()
    definieert: list[str] = []
