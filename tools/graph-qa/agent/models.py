"""
Pydantic-modellen voor request/response van de graph-qa API.
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class BestaandElement(BaseModel):
    """Een element dat al in het annotatie-document staat, meegestuurd door de werkplek.

    De werkplek stuurt deze context mee bij adviesvragen. De annotatieketen haalt actuele
    menselijke markeringen zelfstandig uit de API op.
    """

    id: str = ""
    klasse: str = ""
    tekst: str = ""
    lid: str = ""
    herkomst: str = "agent"        # agent | mens


class ChatContext(BaseModel):
    """Waar de vraag over gaat. Alleen ingevuld als de werkplek een specifieke bepaling of markering
    in beeld heeft; bij een gewone vraag blijft dit leeg."""

    slug: str = ""
    bron_iri: str = ""
    snapshot_id: str = ""
    bwbId: str = ""
    artikel: str = ""
    lid: str = ""
    element_id: str = ""
    klasse: str = ""
    fragment: str = ""             # de selectie of de tekst van het element
    corpus: str = ""               # de getoonde artikeltekst
    bestaande_elementen: list[BestaandElement] = []


class AgentDoel(BaseModel):
    """De bepaling die geannoteerd moet worden, als de aanroeper die al weet.

    De werkplek kent hem vaak: een open document, een item uit de werkvoorraad, of een kandidaat die
    de jurist zojuist aanklikte. Meesturen scheelt de supervisor-call én de hele ophaal-agent, maar
    het echte winstpunt is dat de agent dan niet meer kán uitkomen bij een ándere bepaling dan de
    jurist aanwees. Zonder doel gaat de beurt de gewone weg: supervisor → ophaal-agent.
    """

    bron_iri: str = ""
    bwbId: str = ""
    artikel: str = ""
    lid: str = ""
    nummer: str = ""          # decimale bepaling (beleidsregel/circulaire), bv. "9.1"
    citeertitel: str = ""
    # Een artikel met leden (of een divisie met subbepalingen) levert standaard een keuzekaart op in
    # plaats van één analyse over het geheel. `geheel` slaat die keuze bewust over – voor metingen
    # die hele artikelen vergelijken, niet voor de werkplek.
    geheel: bool = False


class IntakeActie(BaseModel):
    """Een klik op een vraagkaartje bij het samenstellen van een werkgebied (activiteit 1,
    `agent/werkgebied_intake.py`). `stap` is de stap waarop geklikt werd: hoort die niet meer bij de
    intake, dan toont Lex het huidige kaartje opnieuw in plaats van stil iets anders te doen."""

    intake_id: str = Field(pattern=r"^[A-Za-z0-9-]{1,64}$")
    stap: Literal["naam", "aanleiding", "context", "doel", "analysevraag", "praktijkvoorbeeld", "deelvragen",
                  "buiten", "regelingen", "bepalingen", "samenvatting"]
    # Bij de bepalingen: het kaartje van welke deelvraag (0-based); een ander deel is een oud kaartje.
    deel: int = Field(default=0, ge=0, le=19)
    actie: Literal["antwoord", "overslaan", "wijzig", "aanmaken", "afbreken"] = "antwoord"
    keuzes: list[str] = Field(default_factory=list, max_length=20)
    tekst: str = Field(default="", max_length=4000)
    # Meer dan één eigen antwoord (de deelvragen, `meer_tekst` op het kaartje).
    teksten: list[str] = Field(default_factory=list, max_length=20)
    # Bij `wijzig`: naar welke stap, en bij de bepalingen naar welk deel.
    naar: str = ""
    naar_deel: int = Field(default=0, ge=0, le=19)


# Routes op een werkgebied die in werkgebied en gesprek schrijven; alleen via `POST /v1/runs`.
WERKGEBIED_MODI = ("werkgebied_annoteren", "begrippen_verdiepen")

_ID = r"^[A-Za-z0-9-]{1,64}$"


class Onderwerp(BaseModel):
    """Het object waarop de analist *Vraag Lex* koos (spoor F, F3b): een deelvraag, een bronselectie, een
    kandidaat van Lex, een begrip of het werkgebied zelf. De browser stuurt alleen soort en id's; wat
    het object is, haalt `agent/onderwerp.py` bij de api. Context, geen filter – net als de focus.

    Een markering is hier geen soort: die vraag blijft de adviesvraag (`modus: "advies"` met
    `context`), byte-gelijk aan wat de werkplek al stuurde."""

    soort: Literal["deelvraag", "bron", "kandidaat", "begrip", "werkgebied"]
    werkgebied_id: str = Field(pattern=_ID)
    # Het id van het object binnen het werkgebied; bij soort `werkgebied` leeg.
    id: str = Field(default="", pattern=r"^[A-Za-z0-9-]{0,64}$")
    # Hoe de werkplek het object noemt; alleen voor wanneer de api het niet (meer) kent.
    label: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def _id_hoort_bij_de_soort(self) -> "Onderwerp":
        if self.soort != "werkgebied" and not self.id:
            raise ValueError(f"een onderwerp van soort '{self.soort}' vraagt een id")
        return self


# Een klik op een suggestie bij *Vraag Lex* (F3b, F3c): een vaste handeling die zonder model naar haar agent en
# taak gaat (`agents/register.py`). `werkgebied_annoteren` (en `deelvragen_annoteren`: alleen de bronnen onder
# de deelvragen, of onder de aangewezen deelvraag) is de reeks over het werkgebied: die loopt als eigen stroom
# (`werkgebied_annotatie_beurt`), met en zonder `bevestigd`.
ACTIE_TAAK: dict[str, tuple[str, str]] = {
    "werkgebied_annoteren": ("annotatie", "werkgebied"),
    "deelvragen_annoteren": ("annotatie", "deelvragen"),
    "deelvragen_voorstellen": ("deelvragen", "voorstellen"),
    "deelvraag_herformuleren": ("deelvragen", "verbeteren"),
    "deelvraag_splitsen": ("deelvragen", "verbeteren"),
    "bronnen_zoeken": ("deelvragen", "bronnen_zoeken"),
    "dekking": ("deelvragen", "dekking"),
    "begrippen_voorstellen": ("begrippen", "voorstellen"),
    "begrippen_meedenken": ("begrippen", "meedenken"),
    "brondefinitie": ("begrippen", "brondefinitie"),
    "scherper": ("begrippen", "scherper"),
    "voorbeelden": ("begrippen", "voorbeelden"),
    "betekenisverschil": ("begrippen", "betekenisverschil"),
    "begrip_uitwerken": ("begrippen", "uitwerken"),
    "relaties": ("begrippen", "relaties"),
}
Actie = Literal["werkgebied_annoteren", "deelvragen_annoteren", "deelvragen_voorstellen", "deelvraag_herformuleren", "deelvraag_splitsen",
                "bronnen_zoeken", "dekking", "begrippen_voorstellen", "begrippen_meedenken", "brondefinitie",
                "scherper", "voorbeelden", "betekenisverschil", "begrip_uitwerken", "relaties"]
# Acties die eerst om een bevestiging vragen; alleen daar hoort `bevestigd` bij.
BEVESTIG_ACTIES = ("werkgebied_annoteren", "deelvragen_annoteren", "begrippen_meedenken")


class ChatRequest(BaseModel):
    question: str
    conversation_id: str | None = None  # stuur mee voor gespreksgeheugen
    doel: AgentDoel | None = None
    # "advies" = een vraag bij een bestaande annotatie. De supervisor kiest dan niet zelf, maar
    # routeert hard naar de antwoord-worker: zo kan een adviesvraag structureel geen annotatie
    # wijzigen (die route emit simpelweg geen doel/element-events).
    # "werkgebied_annoteren" = de nieuwe bepalingen van het werkgebied annoteren (fase B,
    # `agent/werkgebied_annotatie.py`); zonder `bevestigd` alleen het voorstel.
    # "begrippen_verdiepen" = het model op twijfelparen en kaarten (fase C); de werkplek stuurt het nog
    # bij de bevestigingsknop. Het wordt de actie `begrippen_meedenken` (de begrippen-agent).
    modus: Literal["auto", "advies", "annotaties_lezen", "werkgebied_annoteren", "begrippen_verdiepen"] = "auto"
    context: ChatContext | None = None
    # Een al geannoteerd artikel wordt hergebruikt (`auto`), tenzij de jurist expliciet om een nieuwe
    # ronde vraagt (`opnieuw`). Die voegt toe aan de gedeelde laag; wat beoordeeld is blijft staan.
    hergebruik: Literal["auto", "opnieuw"] = "auto"
    # Meerdere onderdelen van één artikel, gekozen op de keuzekaart: één run die ze na elkaar
    # annoteert, elk met een eigen laag, batch en review (`agent/reeks.py`). Sluit `doel` uit.
    doelen: list[AgentDoel] | None = Field(default=None, min_length=2, max_length=60)
    # De werkplek is geopend vanuit een werkgebied (spoor D, fase AF2): de context van de beurt, het
    # werkgebied van de agents, en in de antwoordroute staan zijn begrippen vooraan (`search_begrippen`).
    werkgebied_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9-]{1,64}$")
    # Het aantal bepalingen dat de analist bevestigde (fase B). Wijkt de actuele werkvoorraad af,
    # dan begint de run niet; zonder dit veld noemt Lex alleen wat er te doen is.
    bevestigd: int | None = Field(default=None, ge=0, le=100_000)
    # Wat er bij `werkgebied_annoteren` meegaat: het hele werkgebied, of alleen de bronnen onder de
    # actieve deelvragen (met `deelvraag_id`: onder die ene). De bevestigingsknop stuurt het terug.
    bereik: Literal["werkgebied", "deelvragen"] = "werkgebied"
    deelvraag_id: str = Field(default="", pattern=r"^[A-Za-z0-9-]{0,64}$")
    # Een klik op een vraagkaartje (activiteit 1): de supervisor stuurt de beurt dan zonder modelaanroep
    # naar de werkgebied-worker, en geen van de harde werkgebiedroutes neemt hem over.
    intake_actie: IntakeActie | None = None
    # Waar de analist *Vraag Lex* op koos (F3b); de beurt krijgt het object als contextblok mee.
    onderwerp: Onderwerp | None = None
    # Een klik op een suggestie (F3b): een vaste handeling, zonder model gerouteerd (`ACTIE_TAAK`).
    actie: Actie | None = None

    @model_validator(mode="after")
    def _actie_kiest_de_route(self) -> "ChatRequest":
        """Een actie is een vaste handeling: de supervisor kiest er zonder model agent en taak bij. Alleen
        `werkgebied_annoteren` zet de modus: met `bevestigd` is dat de reeks (`_stroom_voor`). De modus
        `begrippen_verdiepen` van de bevestigingsknop wordt de actie `begrippen_meedenken`. Staat vóór de
        andere validators, zodat die de modus toetsen die de actie koos."""
        if self.modus == "begrippen_verdiepen" and self.actie is None:
            self.actie, self.modus = "begrippen_meedenken", "auto"
            if not self.werkgebied_id:
                raise ValueError("modus 'begrippen_verdiepen' vraagt een werkgebied_id")
        if self.actie is None:
            return self
        if self.modus != "auto":
            raise ValueError("geef 'actie' of 'modus', niet allebei")
        if self.doel is not None or self.doelen is not None or self.intake_actie is not None:
            raise ValueError("een actie kiest zelf wat ze doet; geef geen 'doel', 'doelen' of 'intake_actie'")
        if not self.werkgebied_id and self.onderwerp is not None:
            self.werkgebied_id = self.onderwerp.werkgebied_id
        if not self.werkgebied_id:
            raise ValueError(f"de actie '{self.actie}' vraagt een werkgebied_id of een onderwerp")
        if self.bevestigd is not None and self.actie not in BEVESTIG_ACTIES:
            raise ValueError("'bevestigd' hoort bij een actie die om bevestiging vraagt")
        if self.actie == "werkgebied_annoteren":
            self.modus = "werkgebied_annoteren"
        if self.actie == "deelvragen_annoteren":
            self.modus, self.bereik = "werkgebied_annoteren", "deelvragen"
            if not self.deelvraag_id and self.onderwerp is not None and self.onderwerp.soort == "deelvraag":
                self.deelvraag_id = self.onderwerp.id
        return self

    @property
    def is_werkgebied_annotatie(self) -> bool:
        """De reeks over het werkgebied (fase B): de modus of de actie, nooit een tekstpatroon. Zonder
        `bevestigd` levert hij het voorstel, met `bevestigd` de annotaties."""
        return bool(self.werkgebied_id) and self.modus == "werkgebied_annoteren"

    @model_validator(mode="after")
    def _begrippen_horen_bij_een_werkgebied(self) -> "ChatRequest":
        if self.modus in WERKGEBIED_MODI and not self.werkgebied_id:
            raise ValueError(f"modus '{self.modus}' vraagt een werkgebied_id")
        if self.modus in WERKGEBIED_MODI and (self.doel is not None or self.doelen is not None):
            raise ValueError(f"de route '{self.modus}' kiest zelf wat ze doet; geef geen 'doel' of 'doelen'")
        if self.bevestigd is not None and self.modus != "werkgebied_annoteren" and self.actie not in BEVESTIG_ACTIES:
            raise ValueError("'bevestigd' hoort bij modus 'werkgebied_annoteren' of een actie die om bevestiging vraagt")
        if (self.bereik != "werkgebied" or self.deelvraag_id) and self.modus != "werkgebied_annoteren":
            raise ValueError("'bereik' en 'deelvraag_id' horen bij het annoteren van het werkgebied")
        if self.deelvraag_id and self.bereik != "deelvragen":
            raise ValueError("'deelvraag_id' hoort bij bereik 'deelvragen'")
        return self

    @model_validator(mode="after")
    def _advies_heeft_een_onderwerp(self) -> "ChatRequest":
        """Een adviesvraag zonder context is geen adviesvraag.

        Elk veld van ChatContext heeft een lege default, dus een leeg of half gevuld blok kwam er
        stilzwijgend doorheen: `_advies_context` bouwde er een kop-zonder-inhoud van en het model
        antwoordde over "de markering" zonder te weten welke. Dat is precies het soort fout dat
        niemand ziet — er komt gewoon een vaag antwoord uit.

        De eis is bewust laag: een fragment óf een bepaling. De werkplek stuurt beide (zie
        `vraagContextVan` in frontend/lib/annotatie.ts), dus dit vangt een programmeerfout of een
        andere client, niet normaal gebruik.
        """
        if self.modus != "advies":
            return self
        c = self.context
        if c is None or not (c.fragment.strip() or c.bwbId.strip() or c.bron_iri.strip()):
            raise ValueError(
                "modus 'advies' vraagt een context met minimaal een fragment, bwbId of bron_iri; "
                "zonder onderwerp is er niets om over te adviseren"
            )
        return self

    @model_validator(mode="after")
    def _reeks_is_een_keuze(self) -> "ChatRequest":
        """Een reeks bestaat uit opties van de keuzekaart: elk met een `bron_iri`, gewoon annoteren.

        Of ze onder één artikel hangen weet dit model niet – dat toetst de reeks tegen de brongraaf
        (`bronmodel.gedeelde_bepaling`) voordat er iets draait."""
        if self.doelen is None:
            return self
        if self.doel is not None:
            raise ValueError("geef 'doel' of 'doelen', niet allebei")
        if self.modus != "auto":
            raise ValueError("een reeks is een annotatieopdracht; 'modus' moet 'auto' zijn")
        if any(not d.bron_iri.strip() for d in self.doelen):
            raise ValueError("elk onderdeel van een reeks heeft een bron_iri")
        return self


class RunStart(BaseModel):
    """Wat een client van een run weet zónder mee te kijken.

    `vraag` zit erbij omdat een tabblad dat halverwege aanhaakt anders tokens uit het niets krijgt:
    de vraag hoort bij de run, niet bij het tabblad dat hem startte. `volgende_seq` en `weggevallen`
    zeggen waar de eventlog staat, zodat aanhaken vanaf het juiste punt kan.
    """

    run_id: str
    conversation_id: str = ""
    vraag: str = ""
    status: str = "loopt"          # loopt | klaar | gestopt | mislukt
    volgende_seq: int = 0
    weggevallen: int = 0


class Source(BaseModel):
    label: str
    uri: str
    # Herkomst-velden (additief; de frontend-BFF leest alleen label + uri).
    iri: str | None = None
    jci: str | None = None
    origin_tool: str | None = None
    # De bronnode volgens `bronmodel.vindplaats` (additief): één bepaling is één bron, of hij nu als
    # graaf-IRI of als jci in de trace stond. `regeling` is de citeertitel, ingevuld in finalize.
    bron_iri: str | None = None
    bwb_id: str | None = None
    soort: str | None = None
    regeling: str | None = None


# --- Annotatie (JAS) ---------------------------------------------------------

class AnnotatieAlternatief(BaseModel):
    """Een kandidaat-klasse bij twijfel, met korte motivatie (disambiguatie)."""

    klasse: str
    motivatie: str = ""


class Anker(BaseModel):
    """Exacte positie van een fragment in de samengevoegde brontekst.

    De offsets slaan op de samengevoegde brontekst die het documentpaneel toont – bij een
    per-lid-annotatie is dat alleen die lid-tekst. `bron_hash` is een FNV-1a 32-bit vingerafdruk;
    de UI gebruikt hem om te detecteren of de brontekst verschoven is na een herimport.
    De context-velden (`voor`/`na`) maken het mogelijk het juiste voorkomen van een herhaald
    fragment te kiezen als de offsets verouderd zijn.
    """

    lid: str = ""
    start: int = 0
    eind: int = 0
    voor: str = ""        # tot 48 tekens originele tekst vóór het fragment
    na: str = ""          # tot 48 tekens originele tekst erna
    bron_hash: str = ""   # FNV-1a 32-bit hash van de brontekst, als hex-string
    # Dezelfde hash over alleen het lidsegment ("2. tekst…"). Zie `annotatie.lid_hashes`: daaraan ziet
    # de gedeelde laag per lid of de wettekst sinds de annotatie veranderde.
    lid_hash: str = ""


class AgentRun(BaseModel):
    """De herkomst van één annotatiebeurt: wélk model de voorstellen maakte.

    Reist als `run`-event mee naar de werkplek, die het bij de api vastlegt. Zonder deze gegevens
    is achteraf niet te zeggen waar een markering vandaan komt – precies wat een export moet dragen
    en wat de latere promotie naar de graaf als provenance nodig heeft.
    """

    model: str = ""
    provider: str = ""
    agent_versie: str = ""
    stop_reden: str = ""
    # Wat deze beurt deed en onder welke omstandigheden – voor herleidbaarheid, niet als sleutel voor
    # hergebruik: de gedeelde laag is "de laatste stand", niet "de uitkomst van deze promptversie".
    modus: str = ""              # nieuw | opnieuw | hergebruik
    leden: list[str] = []        # de leden die deze beurt (her)annoteerde of hergebruikte
    prompt_hash: str = ""
    methode_versie: str = ""     # hash over de JAS-klassen en de prioriteitsregels
    instellingen: dict = {}
    tijd: datetime | None = None


class AnnotatieVoorstel(BaseModel):
    """Eén door de agent voorgesteld JAS-annotatie-element voor een artikel.

    `tekst` is een letterlijk fragment uit de artikeltekst; `grounded`/`vindplaats` worden
    server-side ingevuld door de brongetrouwheid-check (nooit door het model).
    """

    # Stabiel id, hier toegekend (niet door het model): dezelfde span met dezelfde klasse krijgt in
    # elke run hetzelfde id, zodat de api het element bij een volgende ronde herkent.
    id: str = ""
    klasse: str
    tekst: str
    lid: str = ""
    toelichting: str = ""
    alternatieven: list[AnnotatieAlternatief] = []
    grounded: bool = False
    vindplaats: str = ""               # bwbId/artikel/lid/jci-notatie
    anker: Anker | None = None         # exacte positie in het corpus; de keten zet hem naast `ankers`
    ankers: list[dict[str, Any]] = []   # gevalideerde lokale bronankers, ook bij overspannende elementen
    aandacht: str = ""                 # "" | groen | geel | rood – gezet door de resolver (geel = keuze voor de jurist)
    review_uitleg: str = ""            # uitleg van de gerichte review bij het aandacht-niveau
    # JAS-subtype binnen een samengevoegde klasse (variabele/variabelewaarde, parameter/parameterwaarde,
    # delegatiebevoegdheid/delegatie-invulling). Alleen gezet waar het deterministisch vaststaat
    # (`jas_pipeline/subtype.py`); leeg = onbepaald, nooit geraden.
    jas_subtype: str = ""
    # Herkomstspoor uit de hybride keten (ADR-001); kan leeg zijn. Zie
    # `jas_pipeline/keten.py` voor de inhoud en `tests/test_provenance_element.py` voor de vragen
    # (opdracht §40) die het moet kunnen beantwoorden.
    trace: dict[str, Any] = {}


class Verbruiksmeter:
    """Telt het tokenverbruik van één beurt op, over alle LLM-calls heen.

    De Anthropic-SDK geeft bij elk antwoord een `usage`-blok terug.
    Deze meter vangt het op, zodat de api kan boeken hoeveel een gebruiker verbruikte.

    Er is één instantie per beurt (de adapter wordt per beurt gebouwd), en hij telt op met een
    lock: de graph-nodes zijn synchroon en LangGraph kan takken parallel draaien, dus twee calls
    kunnen tegelijk terugkomen.

    Wat waar staat: `invoer` is bij Anthropic de NIET-gecachte rest; het volle promptvolume is
    invoer + cache_lees + cache_schrijf. Alle vier gaan apart naar de api, die beslist hoe ze wegen.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.invoer = 0
        self.uitvoer = 0
        self.cache_lees = 0
        self.cache_schrijf = 0
        self.calls = 0

    def tel_response(self, resp: Any) -> None:
        """Neem het `usage`-blok van één antwoord op. Zonder usage (of bij een fake) telt het niets."""
        u = getattr(resp, "usage", None)
        if u is None:
            return
        with self._lock:
            self.calls += 1
            self.invoer += int(getattr(u, "input_tokens", 0) or 0)
            self.uitvoer += int(getattr(u, "output_tokens", 0) or 0)
            self.cache_lees += int(getattr(u, "cache_read_input_tokens", 0) or 0)
            self.cache_schrijf += int(getattr(u, "cache_creation_input_tokens", 0) or 0)

    @property
    def totaal(self) -> int:
        return self.invoer + self.uitvoer + self.cache_lees + self.cache_schrijf

    def als_dict(self) -> dict[str, int]:
        return {
            "invoer": self.invoer,
            "uitvoer": self.uitvoer,
            "cache_lees": self.cache_lees,
            "cache_schrijf": self.cache_schrijf,
            "calls": self.calls,
        }
