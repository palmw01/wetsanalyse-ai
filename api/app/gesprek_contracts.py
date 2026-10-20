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
from typing import Literal

from pydantic import BaseModel, Field, model_validator


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


class Artefact(BaseModel):
    """Wat een beurt van Lex oplevert om te beoordelen: een annotatie, de begripsvoorstellen van een
    werkgebied, of (later) afleidingsregels. De werkplek toont het als chip en opent het in het
    artefactpaneel naast de chat; de inhoud zelf leeft in de api, het bericht verwijst ernaar.

    `ref` hangt af van de soort – annotatie: `{bron_iri, label?, snapshot_id?}`; begrippen:
    `{werkgebied_id, run_id}` (de voorstellen van een run) of `{werkgebied_id, begrip_id, kaart_run_id?,
    actie?}` (één begrip, fase F4: een kaartactie vanuit het gesprek); bronnen (kandidaatbepalingen van een bronnenrun): `{werkgebied_id,
    run_id}`; werkgebied (een werkgebied dat Lex in het gesprek samenstelde, activiteit 1):
    `{werkgebied_id}`; regels: nog niet in gebruik (gereserveerd)."""

    soort: Literal["annotatie", "begrippen", "bronnen", "werkgebied", "regels"]
    ref: dict
    titel: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def _ref(self) -> "Artefact":
        nodig = {"annotatie": ("bron_iri",), "begrippen": ("werkgebied_id", "run_id"),
                 "bronnen": ("werkgebied_id", "run_id"), "werkgebied": ("werkgebied_id",),
                 "regels": ()}[self.soort]
        if self.soort == "begrippen" and self.ref.get("begrip_id"):
            nodig = ("werkgebied_id", "begrip_id")
        ontbreekt = [k for k in nodig if not isinstance(self.ref.get(k), str) or not self.ref.get(k)]
        if ontbreekt:
            raise ValueError(f"ref van een {self.soort}-artefact mist {', '.join(ontbreekt)}")
        return self


class ReeksPlek(BaseModel):
    """Waar dit bericht staat in een reeks: meerdere leden van één artikel, of de nieuwe bepalingen
    van een werkgebied, geannoteerd in één run (graph-qa `agent/reeks.py`). Elk lid krijgt een eigen bericht met een eigen `run_id`
    (`<run>.<n>`); dit veld laat de werkplek ze na herladen weer als één reeks tonen."""

    run_id: str = Field(min_length=1, max_length=128)
    index: int = Field(ge=0, le=59)
    # Een werkgebied kan één nieuwe bepaling hebben; een reeks van de keuzekaart heeft er minstens twee.
    totaal: int = Field(ge=1, le=60)
    ouder: str = Field(default="", max_length=300)


class Bevestiging(BaseModel):
    """Een opdracht die Lex niet zonder akkoord start (spoor D, fase B): de werkplek toont er een knop
    bij, ook na herladen. Klikken start de run met `bevestigd: aantal`; is de werkvoorraad intussen
    veranderd, dan weigert graph-qa en komt er een nieuwe bevestiging."""

    # `begrippen_verdiepen` (fase C): het model op twijfelparen en kaarten; `aantal` telt die samen.
    soort: Literal["werkgebied_annoteren", "begrippen_verdiepen"]
    werkgebied_id: str = Field(pattern=r"^[A-Za-z0-9-]{1,64}$")
    aantal: int = Field(ge=0, le=100_000)
    schatting: int | None = Field(default=None, ge=0)


class VraagOptie(BaseModel):
    """Eén voorstel op een vraagkaart. `bron` draagt bij een regeling of onderdeel waar het in de graaf
    staat (`{bwb_id, iri?, label?}`): zo'n optie komt uit de graaf, nooit uit het model."""

    label: str = Field(min_length=1, max_length=300)
    waarde: str = Field(min_length=1, max_length=4000)
    bron: dict = {}
    # De tweede regel onder de optie ("wet · 2 hoofdstukken over box 3"): uit de graaf, nooit van het model.
    omschrijving: str = Field(default="", max_length=300)


# De stappen van het samenstellen, in de volgorde van graph-qa (`agent/werkgebied_intake.STAPPEN`):
# startactiviteit a, dan activiteit 1 – de bronnen pas als vraag en deelvragen er zijn (Handleiding 1f).
IntakeStap = Literal["naam", "aanleiding", "context", "doel", "analysevraag", "praktijkvoorbeeld",
                     "deelvragen", "buiten", "regelingen", "onderdelen", "samenvatting"]


class Vraagkaart(BaseModel):
    """Een vraag van Lex bij het samenstellen van een werkgebied (activiteit 1): één stap, met
    voorstellen en een eigen antwoord. De werkplek toont hem als kaartje, ook na herladen; een klik
    start de volgende run met `intake_actie`. De stapvolgorde is van graph-qa, niet van het model.

    `vooringevuld` zijn de waarden die Lex uit de eerste zin haalde: voorgeselecteerd, nooit stil
    aangenomen. Een samenvattingskaart (`soort: samenvatting`) draagt in `samenvatting` wat er
    aangemaakt wordt: `{naam, aanleiding, context, doel, analysevraag, praktijkvoorbeeld,
    deelvragen[], afbakening, bronnen[]}`."""

    intake_id: str = Field(pattern=r"^[A-Za-z0-9-]{1,64}$")
    soort: Literal["vraag", "samenvatting"] = "vraag"
    stap: IntakeStap
    nr: int = Field(ge=1, le=20)
    totaal: int = Field(ge=1, le=20)
    vraag: str = Field(min_length=1, max_length=500)
    toelichting: str = Field(default="", max_length=1000)
    opties: list[VraagOptie] = Field(default_factory=list, max_length=20)
    meerkeuze: bool = False
    vrije_tekst: bool = True
    overslaanbaar: bool = True
    vooringevuld: list[str] = Field(default_factory=list, max_length=20)
    samenvatting: dict = {}
    # Bladeren zoals bij Claude (‹ n van 5 ›): `terug` = er is een eerdere stap, `beantwoord` = deze stap
    # had al een antwoord (na terugbladeren), dus › mag.
    terug: bool = False
    beantwoord: bool = False


class IntakeAntwoord(BaseModel):
    """Op het user-bericht van een klik op een vraagkaartje: daaraan herkent de werkplek na herladen een
    antwoord, en onderscheidt hij het van een getypte tussenvraag (die de "Vragen"-kaart onderbreekt)."""

    intake_id: str = Field(pattern=r"^[A-Za-z0-9-]{1,64}$")
    stap: IntakeStap
    actie: Literal["antwoord", "overslaan", "wijzig", "aanmaken", "afbreken"] = "antwoord"


class Bericht(BaseModel):
    """Eén beurt in het gesprek. Assistent-berichten dragen optioneel `denk`/`bronnen`, of een
    verwijzing naar een annotatie-document (`annotatie_slug`) of bronnode (`annotatie_doel`).

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
    # Lex hergebruikte (een deel van) de gedeelde annotatielaag: welke leden, en hoe ver de review
    # was. Zonder dit veld is na herladen niet meer te zien dat er niets nieuws is geannoteerd.
    hergebruik: dict = {}
    # Wat de annotatieketen wel en niet kon bekijken (dimensies per bronnode, ongedekte zinsdelen met
    # offsets, procesdekking, de fasen met hun duur) – zodat een heropend gesprek het nog toont.
    dekking: dict = {}
    # Het overzicht van een onderwerp ("welke artikelen gaan over X"), deterministisch uit de graaf
    # opgebouwd door graph-qa: per regeling de delen met hun bepalingen, wat er verder over gaat, de
    # definitie en het trefwoord. De werkplek toont het als blok en opent er de 3D-graaf mee.
    overzicht: dict = {}
    # Bronnode-annotatie (contract 2): de verwijzing die `annotatie_slug` voor een artikeldocument is.
    annotatie_doel: AnnotatieDoel | None = None
    # Het uitvoeringsspoor van de beurt ("Graaf geraadpleegd · N aanroepen"), ook na herladen.
    tool_executions: list[dict] = []
    # Van welke agent-run deze beurt de uitkomst is. Dient als idempotentiesleutel: dezelfde run mag
    # maar één assistent-bericht opleveren, ook als er twee tabbladen meekeken.
    run_id: str = ""
    reeks: ReeksPlek | None = None
    # Wat deze beurt opleverde om te beoordelen (chip + artefactpaneel). Oudere annotatieberichten
    # hebben alleen `annotatie_doel`; de werkplek leidt daar zelf een annotatie-artefact uit af.
    artefact: Artefact | None = None
    bevestiging: Bevestiging | None = None
    vraagkaart: Vraagkaart | None = None
    intake_antwoord: IntakeAntwoord | None = None
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
    hergebruik: dict = {}
    dekking: dict = {}
    overzicht: dict = {}
    annotatie_doel: AnnotatieDoel | None = None
    # Een beurt levert er hooguit enkele tientallen; de grens is een vangnet, geen verwachting.
    tool_executions: list[dict] = Field(default_factory=list, max_length=200)
    run_id: str = ""
    reeks: ReeksPlek | None = None
    artefact: Artefact | None = None
    bevestiging: Bevestiging | None = None
    vraagkaart: Vraagkaart | None = None
    intake_antwoord: IntakeAntwoord | None = None


class GesprekSamenvatting(BaseModel):
    """Lichte lijst-weergave voor de sidebar (chatgeschiedenis)."""

    id: str
    titel: str = ""
    aantal_berichten: int = 0
    updated: datetime | None = None
