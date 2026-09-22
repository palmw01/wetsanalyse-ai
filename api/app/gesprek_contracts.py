"""
Contracten voor het gesprekken-domein (chat-werkruimte).

De persistente **chatgeschiedenis** van de werkplek: per gebruiker een lijst gesprekken, elk met een
geordende reeks berichten. Bewust **los** van het annotatie-domein: een bericht kan naar een
annotatie-document verwijzen (`annotatie_slug` + het leesbare `annotatie_titel`) of naar een
bronnode (`annotatie_doel`, contract 2), maar de
review-state zelf blijft in het annotatie-domein. De berichten dragen de heterogene payload van één chat-beurt (tekst + optioneel
denkproces/bronnen, of een annotatie-verwijzing).
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Rol(str, Enum):
    user = "user"
    assistant = "assistant"


class AnnotatieDoel(BaseModel):
    """De bronnode waar een annotatiebeurt over ging (contract 2). Een bronnode-laag heeft geen slug,
    dus zonder dit doel wijst het bericht na herladen nergens meer naar – dan verdwijnt de chip die
    het annotatiepaneel opent."""

    bron_iri: str
    label: str = ""
    snapshot_id: str = ""


class Bericht(BaseModel):
    """Eén beurt in het gesprek. Assistent-berichten dragen optioneel `denk`/`bronnen`, of een
    verwijzing naar een annotatie-document (`annotatie_slug` + de Critic-`ontbrekend`-suggesties).

    `annotatie_titel` is het leesbare label van dat document op het moment van de beurt ("Wet IB 2001
    – art. 3.1 lid 2"). Het bericht beschrijft zichzelf dus: wordt het document later verwijderd, dan
    blijft het gesprek leesbaar in plaats van terug te vallen op een naamloze verwijzing. Oudere
    berichten hebben het veld niet en leveren "" – dat is geen fout, maar een lege terugval."""

    id: int | None = None
    rol: Rol
    tekst: str = ""
    denk: str = ""
    bronnen: list[dict] = []
    annotatie_slug: str = ""
    annotatie_titel: str = ""
    ontbrekend: list[dict] = []
    # Lex hergebruikte (een deel van) de gedeelde annotatielaag: welke leden, en hoe ver de review
    # was. Zonder dit veld is na herladen niet meer te zien dat er niets nieuws is geannoteerd.
    hergebruik: dict = {}
    # Bronnode-annotatie (contract 2): de verwijzing die `annotatie_slug` voor een artikeldocument is.
    annotatie_doel: AnnotatieDoel | None = None
    # Het uitvoeringsspoor van de beurt ("Graaf geraadpleegd · N aanroepen"), ook na herladen.
    tool_executions: list[dict] = []
    # Van welke agent-run deze beurt de uitkomst is. Dient als idempotentiesleutel: dezelfde run mag
    # maar één assistent-bericht opleveren, ook als er twee tabbladen meekeken.
    run_id: str = ""
    created: datetime | None = None


class Gesprek(BaseModel):
    """Eén chat-gesprek van een gebruiker, met zijn berichten."""

    id: str
    user_id: str = ""
    titel: str = ""
    berichten: list[Bericht] = []
    created: datetime | None = None
    updated: datetime | None = None


# --- invoer / uitvoer --------------------------------------------------------

class GesprekCreate(BaseModel):
    titel: str = ""


class GesprekPatch(BaseModel):
    titel: str


class BerichtInvoer(BaseModel):
    rol: Rol
    tekst: str = ""
    denk: str = ""
    bronnen: list[dict] = []
    annotatie_slug: str = ""
    annotatie_titel: str = ""
    ontbrekend: list[dict] = []
    hergebruik: dict = {}
    annotatie_doel: AnnotatieDoel | None = None
    # Een beurt levert er hooguit enkele tientallen; de grens is een vangnet, geen verwachting.
    tool_executions: list[dict] = Field(default_factory=list, max_length=200)
    run_id: str = ""


class GesprekSamenvatting(BaseModel):
    """Lichte lijst-weergave voor de sidebar (chatgeschiedenis)."""

    id: str
    titel: str = ""
    aantal_berichten: int = 0
    updated: datetime | None = None
