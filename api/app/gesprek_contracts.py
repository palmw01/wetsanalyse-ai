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

from bronmodel.antwoord import Antwoord
from bronmodel.connectors import NAMEN as CONNECTOR_NAMEN
from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator


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
    `{werkgebied_id}`; deelvraag (één deelvraag, F3d): `{werkgebied_id, deelvraag_id}`; begrip (één begrip,
    F3d): `{werkgebied_id, begrip_id, kaart_run_id?, actie?}` – bewaarde berichten van vóór F3d dragen
    dat als begrippen mét `begrip_id`; bronselectie (de bronselectie per deelvraag, spoor J): `{werkgebied_id,
    deelvraag_id?}`; regie (een regie over deelgesprekken, ADR-012): `{werkgebied_id, regie_id}`; regels: nog niet in
    gebruik (gereserveerd)."""

    soort: Literal["annotatie", "begrippen", "bronnen", "werkgebied", "deelvraag", "begrip", "bronselectie", "regie",
                   "regels"]
    ref: dict
    titel: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def _ref(self) -> "Artefact":
        nodig = {"annotatie": ("bron_iri",), "begrippen": ("werkgebied_id", "run_id"),
                 "bronnen": ("werkgebied_id", "run_id"), "werkgebied": ("werkgebied_id",),
                 "deelvraag": ("werkgebied_id", "deelvraag_id"), "begrip": ("werkgebied_id", "begrip_id"),
                 "bronselectie": ("werkgebied_id",), "regie": ("werkgebied_id", "regie_id"),
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
    # `regie` (ADR-012): het plan van een regie; `aantal` telt de deelgesprekken, `plan_id` is wat de knop bevestigt.
    soort: Literal["werkgebied_annoteren", "begrippen_verdiepen", "regie"]
    werkgebied_id: str = Field(pattern=r"^[A-Za-z0-9-]{1,64}$")
    aantal: int = Field(ge=0, le=100_000)
    schatting: int | None = Field(default=None, ge=0)
    # Bij `werkgebied_annoteren`: het hele werkgebied, of alleen de bronnen onder de deelvragen (met
    # `deelvraag_id`: onder die ene). De knop start dan hetzelfde bereik.
    bereik: Literal["werkgebied", "deelvragen"] = "werkgebied"
    deelvraag_id: str = Field(default="", pattern=r"^[A-Za-z0-9-]{0,64}$")
    # Bij `begrippen_verdiepen` (spoor M): de inhoud van de werkvoorraad die de knop bevestigt. De knop
    # stuurt hem terug; wijkt hij af, dan begint Lex niet, ook niet bij een gelijk aantal.
    werkvoorraad_id: str = Field(default="", pattern=r"^(W[0-9a-f]{16})?$")
    # Bij `regie`: het plan dat de knop bevestigt en de opdracht die hij start.
    plan_id: str = Field(default="", pattern=r"^([0-9a-f]{16})?$")
    opdracht: Literal["", "bronnen", "annoteren"] = ""

    @model_serializer(mode="wrap")
    def _zonder_lege_werkvoorraad(self, handler):
        """Zonder werkvoorraad of plan (annoteren, of een bericht van vóór spoor M) blijft het bericht zoals het was."""
        data = handler(self)
        if isinstance(data, dict):
            for veld in ("werkvoorraad_id", "plan_id", "opdracht"):
                if not data.get(veld):
                    data.pop(veld, None)
        return data


def _zonder_lege_deelvraag(self, handler):
    """Een lege `deelvraag_id` (alles buiten de bronselectie) valt weg: zo blijft een kaartje van de intake,
    en elk bewaard bericht, precies zoals het was."""
    data = handler(self)
    if isinstance(data, dict) and not data.get("deelvraag_id"):
        data.pop("deelvraag_id", None)
    # Zo ook de standaardweergave (`kaart`): alleen het compacte kaartje van de bronselectie draagt `weergave`.
    if isinstance(data, dict) and data.get("weergave") == "kaart":
        data.pop("weergave", None)
    # En een kaartje zonder eigen regelnaam (`regel`) blijft zoals het was.
    if isinstance(data, dict) and data.get("regel") is None:
        data.pop("regel", None)
    return data


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
IntakeStap = Literal["naam", "aanleiding", "context", "doel", "analysevraag", "praktijkvoorbeeld", "thema",
                     "deelvragen", "buiten", "regelingen", "gebeurtenis", "samenvatting",
                     # Een bewaard kaartje van vóór 4 nov 2026 (de bepalingen per deelvraag) blijft leesbaar.
                     "bepalingen",
                     # De bronselectie per deelvraag (spoor J): dezelfde kaartjes, de stand staat bij de api.
                     "bs_gebeurtenis", "bs_kies", "bs_bepalingen", "bs_afhankelijkheden", "bs_afronden", "bs_verder",
                     "bs_toevoegen",
                     # De keuzekaart van de begrippen-agent: welk begrip bedoel je?
                     "begrip_kiezen"]


class IntakeDeel(BaseModel):
    """Bij de bepalingen: één kaart per deelvraag. `deelvraag` is leeg als er geen deelvragen zijn –
    dan gaat de ene kaart over de analysevraag."""

    index: int = Field(ge=0, le=19)
    totaal: int = Field(ge=1, le=20)
    deelvraag: str | None = Field(default=None, max_length=1000)


class Regel(BaseModel):
    """Wat één invoerregel op een kaartje is: de naam ("deelvraag", "bepaling") en een voorbeeld als placeholder."""

    enkel: str = Field(min_length=1, max_length=40)
    voorbeeld: str = Field(default="", max_length=200)


class Vraagkaart(BaseModel):
    """Een vraag van Lex bij het samenstellen van een werkgebied (activiteit 1): één stap, met
    voorstellen en een eigen antwoord. De werkplek toont hem als kaartje, ook na herladen; een klik
    start de volgende run met `intake_actie`. De stapvolgorde is van graph-qa, niet van het model.

    `vooringevuld` zijn de waarden die Lex uit de eerste zin haalde: voorgeselecteerd, nooit stil
    aangenomen. Een samenvattingskaart (`soort: samenvatting`) draagt in `samenvatting` wat er
    aangemaakt wordt: `{naam, aanleiding, context, doel, analysevraag, praktijkvoorbeeld,
    deelvragen[], afbakening, bronnen[]}`.

    `modus: aanvullen` is hetzelfde kaartje op een bestaand werkgebied: alleen de gevraagde velden van
    het dossier, en de samenvatting draagt `{wijzigingen: [{veld, label, toen, nu}]}` met *Opslaan*."""

    intake_id: str = Field(pattern=r"^[A-Za-z0-9-]{1,64}$")
    # `begrip`: de begrippen-agent vraagt welk begrip de analist bedoelt (`intake_id` `bk-<werkgebied>`).
    # `bronselectie` (spoor J): de kaartjes van de bronselectie per deelvraag; `intake_id` is dan
    # `bs-<werkgebied>` en `deelvraag_id` de deelvraag waar het kaartje over gaat.
    modus: Literal["samenstellen", "aanvullen", "bronselectie", "begrip"] = "samenstellen"
    deelvraag_id: str = Field(default="", pattern=r"^[A-Za-z0-9-]{0,64}$")
    soort: Literal["vraag", "samenvatting"] = "vraag"
    stap: IntakeStap
    # Negen vaste stappen plus één kaart per deelvraag (hoogstens twintig).
    nr: int = Field(ge=1, le=40)
    totaal: int = Field(ge=1, le=40)
    deel: IntakeDeel | None = None
    vraag: str = Field(min_length=1, max_length=500)
    toelichting: str = Field(default="", max_length=1000)
    opties: list[VraagOptie] = Field(default_factory=list, max_length=20)
    meerkeuze: bool = False
    vrije_tekst: bool = True
    # Meer dan één eigen antwoord: één regel is één ding, en de werkplek biedt "+ Nog een …" en stuurt `teksten`.
    meer_tekst: bool = False
    # Wat één regel is (`{enkel: "bepaling", voorbeeld: "artikel 9 lid 2 Invorderingswet 1990"}`): de werkplek noemt
    # de regels daarnaar. Leeg = de deelvragen (zo oud als het veld).
    regel: Regel | None = None
    overslaanbaar: bool = True
    vooringevuld: list[str] = Field(default_factory=list, max_length=20)
    samenvatting: dict = {}
    # `paneel` (bronselectie, 3 nov 2026): een compact kaartje dat naar het paneel verwijst; beslissen gebeurt
    # daar, en *Klaar* (`actie: klaar`) gaat verder. `samenvatting` draagt dan `{kandidaten, opgenomen}`.
    weergave: Literal["kaart", "paneel"] = "kaart"
    # Bladeren zoals bij Claude (‹ n van 5 ›): `terug` = er is een eerdere stap, `beantwoord` = deze stap
    # had al een antwoord (na terugbladeren), dus › mag.
    terug: bool = False
    beantwoord: bool = False

    _serialiseer = model_serializer(mode="wrap")(_zonder_lege_deelvraag)


class BevestigingAntwoord(BaseModel):
    """Op het user-bericht dat een `bevestiging` beantwoordt: gestart (de knop) of geannuleerd. Daaraan
    ziet de werkplek na herladen dat het voorstel erboven afgehandeld is, en toont hij geen knop meer."""

    keuze: Literal["gestart", "geannuleerd"]


class IntakeAntwoord(BaseModel):
    """Op het user-bericht van een klik op een vraagkaartje: daaraan herkent de werkplek na herladen een
    antwoord, en onderscheidt hij het van een getypte tussenvraag (die de "Vragen"-kaart onderbreekt)."""

    intake_id: str = Field(pattern=r"^[A-Za-z0-9-]{1,64}$")
    stap: IntakeStap
    deel: int | None = Field(default=None, ge=0, le=19)
    actie: Literal["antwoord", "overslaan", "wijzig", "aanmaken", "opslaan", "afbreken", "klaar"] = "antwoord"
    deelvraag_id: str = Field(default="", pattern=r"^[A-Za-z0-9-]{0,64}$")

    _serialiseer = model_serializer(mode="wrap")(_zonder_lege_deelvraag)


class BeurtUitkomst(BaseModel):
    """Hoe een beurt afliep, als dat iets anders is dan gewoon klaar (graph-qa `agent/beurt.py`). De werkplek toont
    hetzelfde live en na herladen. Een run zonder uitkomst op zijn bericht is een ouder bericht, of gewoon klaar."""

    status: Literal["klaar", "mislukt", "gestopt"]
    melding: str = Field(default="", max_length=2000)


#: Hoeveel modelaanroepen één `contextopbouw` hooguit opsomt: gelijk aan `MAX_AANROEPEN` van de meter in graph-qa.
MAX_CONTEXT_AANROEPEN = 60


class Contextopbouw(BaseModel):
    """Hoe de verzoeken van één beurt waren opgebouwd en wat de beurt kostte (plan contextweergave, ADR-015).

    Graph-qa rekent het uit aan het eind van de beurt (`agent/contextopbouw.py`) en zet het op het bericht; de api
    bewaart het en geeft het terug. Alleen tellingen en korte vingerafdrukken, nooit inhoud. Geen veld heet `token`:
    de logredactie laat een veld met die naam weg.

    - `agenten`: per rol met een toollus de context: het laatste verzoek (`laatste`, met `delen` per categorie) en het
      eerste (`begin`: warm of koud);
    - `verbruik`: per rol wat de aanroepen samen kostten, ook de losse stappen;
    - `som`: wat de beurt in totaal kostte, gelijk aan wat naar `/v1/verbruik` ging;
    - `aanroepen`: het detail per modelaanroep, begrensd.

    De lagen daaronder zijn van graph-qa en blijven vrij (`dict`): een nieuw veld per categorie vraagt hier geen
    wijziging. Een nieuw veld op dit niveau wel; `tools/graph-qa/tests/test_contextopbouw.py` vergelijkt beide kanten.
    Iedereen ziet hetzelfde: er is geen rolfilter."""

    model_config = ConfigDict(extra="ignore")

    versie: int = Field(ge=1, le=99)
    run_id: str = Field(default="", max_length=128)
    # De run die deze startte (een kind van een regie, ADR-012; straks een subagent, ADR-016). Leeg = geen ouder.
    ouder_run_id: str = Field(default="", max_length=128)
    # Het profiel van een subagent (ADR-016). Leeg tot de agentvorm er is.
    profiel_id: str = Field(default="", max_length=128)
    profiel_versie: str = Field(default="", max_length=64)
    agenten: list[dict] = Field(default_factory=list, max_length=16)
    verbruik: list[dict] = Field(default_factory=list, max_length=64)
    som: dict = {}
    aanroepen: list[dict] = Field(default_factory=list, max_length=MAX_CONTEXT_AANROEPEN)


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
    # Het antwoord als sjabloon (ADR-008): de blokken die de werkplek tekent. Zonder sjabloon leeg, en dan is
    # `tekst` het antwoord.
    antwoord: Antwoord | None = None
    # Bronnode-annotatie (contract 2): de verwijzing die `annotatie_slug` voor een artikeldocument is.
    annotatie_doel: AnnotatieDoel | None = None
    # Het uitvoeringsspoor van de beurt ("Bronnen geraadpleegd · N aanroepen"), ook na herladen.
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
    bevestiging_antwoord: BevestigingAntwoord | None = None
    intake_antwoord: IntakeAntwoord | None = None
    # Hoe de beurt afliep, als dat niet gewoon klaar was: dezelfde melding live en na herladen.
    uitkomst: BeurtUitkomst | None = None
    # Het oordeel van de brongetrouwheidstoets (graph-qa `grounding`-event), met `afgekapt` als het antwoord niet paste.
    grounding: dict = {}
    # De opbouw van de context en het verbruik van deze beurt. Oudere berichten en beurten zonder model hebben het niet.
    contextopbouw: Contextopbouw | None = None
    created: datetime | None = None


#: De namen uit de connectorbeschrijving (`bronmodel.connectors`), dezelfde als het register.
ConnectorNaam = Literal[CONNECTOR_NAMEN]  # type: ignore[valid-type]


class Gesprek(BaseModel):
    """Eén chat-gesprek van een gebruiker, met zijn berichten."""

    id: str
    user_id: str = ""
    titel: str = ""
    # Leeg = een los gesprek. Met een werkgebied krijgt elke beurt dat dossier als context mee.
    werkgebied_id: str = ""
    # Een deelgesprek (ADR-012, ADR-016 §A3): de ouder en de delegatie die het startte, en het profiel van de subagent
    # dat op het gesprek vastligt (leeg bij een regie). Leeg = geen.
    ouder_id: str = ""
    delegatie_id: str = ""
    profiel: str = ""
    gearchiveerd: datetime | None = None
    # ADR-013: de bronconnectors die in dit gesprek aanstaan; None = de standaard (werkgebied, anders de beheerder).
    connectors: list[str] | None = None
    berichten: list[Bericht] = []
    created: datetime | None = None
    updated: datetime | None = None


# --- invoer / uitvoer --------------------------------------------------------

class GesprekCreate(BaseModel):
    titel: str = ""
    werkgebied_id: str = ""
    # Een deelgesprek (ADR-012, ADR-016 §A3): de ouder is een eigen gesprek in hetzelfde werkgebied (of allebei los),
    # zelf zonder ouder; de delegatie hoort bij die ouder. `profiel` is het profiel van de subagent.
    ouder_id: str = Field(default="", max_length=64)
    delegatie_id: str = Field(default="", max_length=64)
    profiel: str = Field(default="", pattern=r"^([a-z][a-z0-9_]{0,63})?$")


class GesprekPatch(BaseModel):
    """Alleen wat meekomt verandert. `werkgebied_id: ""` koppelt het gesprek los."""

    titel: str | None = None
    werkgebied_id: str | None = None
    gearchiveerd: bool | None = None
    # ADR-013: het menu *Bronnen en tools*. Meegestuurd als `null` = terug naar de standaard; weggelaten = ongewijzigd.
    connectors: list[ConnectorNaam] | None = Field(default=None, max_length=8)


#: De groepen die je in één keer opruimt (instellingen → Gesprekken). **Recent** = actief en los, zoals de sidebar
#: ze toont; **archief** = alles wat gearchiveerd is, ook uit een werkgebied. Actieve gesprekken in een werkgebied
#: vallen er bewust buiten: die horen bij het werk aan dat werkgebied.
GesprekGroep = Literal["recent", "archief"]

#: Hoeveel ids één bulkverzoek hooguit draagt: ruim boven een opruimbeurt, en een grens op de body.
MAX_BULK = 2000


class GesprekTelling(BaseModel):
    recent: int
    archief: int


class GesprekIds(BaseModel):
    ids: list[str]


class GesprekkenBulk(BaseModel):
    """Een opruimbeurt: de groep én de ids die de BFF net ophaalde. De api wist alleen de doorsnede (eigen, in de groep,
    in de lijst), zodat een gesprek dat tussendoor ontstond niet meegaat zonder dat het geheugen van Lex gewist is."""

    groep: GesprekGroep
    ids: list[str] = Field(default_factory=list, max_length=MAX_BULK)


class GesprekkenBulkUitkomst(BaseModel):
    aantal: int
    ids: list[str]


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
    antwoord: Antwoord | None = None
    annotatie_doel: AnnotatieDoel | None = None
    # Een beurt levert er hooguit enkele tientallen; de grens is een vangnet, geen verwachting.
    tool_executions: list[dict] = Field(default_factory=list, max_length=200)
    run_id: str = ""
    reeks: ReeksPlek | None = None
    artefact: Artefact | None = None
    bevestiging: Bevestiging | None = None
    bevestiging_antwoord: BevestigingAntwoord | None = None
    vraagkaart: Vraagkaart | None = None
    intake_antwoord: IntakeAntwoord | None = None
    uitkomst: BeurtUitkomst | None = None
    grounding: dict = {}
    contextopbouw: Contextopbouw | None = None


class BerichtContext(BaseModel):
    """De contextopbouw van één assistentbericht, zonder de rest van het bericht."""

    bericht_id: int | None = None
    run_id: str = ""
    created: datetime | None = None
    contextopbouw: Contextopbouw


class KindContext(BaseModel):
    """Een deelgesprek met de contextopbouw van zijn beurten. Zonder beurten met een meting is `berichten` leeg: de
    run loopt nog, eindigde zonder bericht, of is van vóór de meting."""

    gesprek_id: str
    titel: str = ""
    updated: datetime | None = None
    berichten: list[BerichtContext] = []


class ContextopbouwBoom(BaseModel):
    """De boom bij het lezen: de deelgesprekken van één gesprek (`ouder_id`) met hun contextopbouw. Niets is dubbel
    opgeslagen; de eigen contextopbouw van het gesprek staat op zijn berichten."""

    gesprek_id: str
    kinderen: list[KindContext] = []


class GesprekSamenvatting(BaseModel):
    """Lichte lijst-weergave voor de sidebar (chatgeschiedenis)."""

    id: str
    titel: str = ""
    aantal_berichten: int = 0
    updated: datetime | None = None
    werkgebied_id: str = ""
    # De naam erbij, zodat de sidebar per werkgebied kan groeperen zonder tweede call.
    werkgebied_naam: str = ""
    ouder_id: str = ""
    delegatie_id: str = ""
    profiel: str = ""
    gearchiveerd: datetime | None = None
