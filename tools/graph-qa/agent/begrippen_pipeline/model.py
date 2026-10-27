"""Het datamodel van de begrippenketen (ADR-004).

Wat er in de keten gaat is een **manifest**: een vaste set formuleringen (geannoteerde elementen)
met hun bronstand. Wat eruit komt zijn **kandidaten** (een hypothese over een paar formuleringen,
met bewijs), **betekenisgroepen** (formuleringen die mogelijk één begrip aanduiden) en
**relaties** (kwalificatie, inclusie, uitsluiting, hiërarchie – nooit een samenvoeging).

Bewijs heeft een richting en een ordinale sterkte, geen getal: een getal zou een zekerheid
suggereren die er niet is. Een besluit heeft drie uitkomsten (Fellegi–Sunter): link, non-link en
possible link.

Identiteit is inhoudelijk: dezelfde invoer geeft in elke run dezelfde ID's. Bij een symmetrische
hypothese (zelfde betekenis) telt de volgorde van de leden niet, bij een gerichte (hiërarchie,
kwalificatie) wel.
"""
from __future__ import annotations

import hashlib
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Vast(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _hash(*delen: str) -> str:
    return hashlib.sha256("\x1f".join(delen).encode()).hexdigest()


class Polariteit(str, Enum):
    STEUN = "steun"
    TEGEN = "tegen"
    ONBESLIST = "onbeslist"


class Sterkte(str, Enum):
    """Ordinaal: alleen de volgorde betekent iets."""

    STERK = "sterk"
    MIDDEL = "middel"
    ZWAK = "zwak"


class Hypothese(str, Enum):
    ZELFDE_BETEKENIS = "zelfde_betekenis"
    KWALIFICATIE = "kwalificatie"      # "X geldt als / wordt aangemerkt als Y" – van X naar Y
    INCLUSIE = "inclusie"              # "onder X wordt mede verstaan Y" – Y valt binnen X
    UITSLUITING = "uitsluiting"        # "onder X wordt niet verstaan Y"
    HIERARCHIE = "hierarchie"          # "X, zoals Y" / kop van samenstelling – Y is een soort X

    @property
    def symmetrisch(self) -> bool:
        return self is Hypothese.ZELFDE_BETEKENIS


class Besluit(str, Enum):
    LINK = "link"                      # sterke steun, geen tegenbewijs
    NON_LINK = "non_link"              # sterk tegenbewijs
    POSSIBLE_LINK = "possible_link"    # al het andere: een vraag aan de jurist (of later een model)


class Aandacht(str, Enum):
    GROEN = "groen"
    GEEL = "geel"


# ---------------------------------------------------------------------------------------------
# Invoer
# ---------------------------------------------------------------------------------------------


class Bron(_Vast):
    """Eén bronnode op een vaste stand, met de tekst die de signalen lezen."""

    bron_iri: str
    tekst: str
    bron_hash: str
    label: str = ""                    # "art. 9 lid 1 IW 1990"
    aanhef: str = ""                   # aanhef van de houder ("In deze wet wordt verstaan onder:")
    regeling: str = ""                 # BWB-id, voor het bereik van een definitie


class Formulering(_Vast):
    """Een geannoteerd element: de passage die mogelijk een begrip aanduidt."""

    element_id: str
    bron_iri: str
    start: int = Field(ge=0)
    eind: int = Field(gt=0)
    tekst: str
    jas_klasse: str
    jas_subtype: str = ""
    review_status: str = "voorgesteld"  # lifecycle van het element; onbeoordeeld mag, met voorbehoud

    @model_validator(mode="after")
    def _bereik(self) -> Formulering:
        if self.eind <= self.start:
            raise ValueError("een formulering heeft een positieve lengte")
        return self


class Manifest(_Vast):
    """De vaste invoer van één run. Het id volgt uit de inhoud, niet uit het moment."""

    bronnen: tuple[Bron, ...]
    formuleringen: tuple[Formulering, ...]

    @model_validator(mode="after")
    def _samenhang(self) -> Manifest:
        iris = {b.bron_iri for b in self.bronnen}
        if len(iris) != len(self.bronnen):
            raise ValueError("een bron staat dubbel in het manifest")
        ids = [f.element_id for f in self.formuleringen]
        if len(set(ids)) != len(ids):
            raise ValueError("een element staat dubbel in het manifest")
        per_iri = {b.bron_iri: b for b in self.bronnen}
        for f in self.formuleringen:
            bron = per_iri.get(f.bron_iri)
            if bron is None:
                raise ValueError(f"element {f.element_id} hoort bij een bron buiten het manifest")
            if bron.tekst[f.start:f.eind] != f.tekst:
                raise ValueError(f"element {f.element_id} staat niet letterlijk op zijn anker")
        return self

    @property
    def id(self) -> str:
        delen = sorted(f"{b.bron_iri}@{b.bron_hash}" for b in self.bronnen)
        delen += sorted(f.element_id for f in self.formuleringen)
        return "M" + _hash(*delen)[:16]

    def bron(self, bron_iri: str) -> Bron:
        return next(b for b in self.bronnen if b.bron_iri == bron_iri)

    def formulering(self, element_id: str) -> Formulering:
        return next(f for f in self.formuleringen if f.element_id == element_id)


# ---------------------------------------------------------------------------------------------
# De onderzoeksstand (spoor M): de context naast het manifest
# ---------------------------------------------------------------------------------------------

ONDERZOEK_VERSIE = "1"


class Rol(str, Enum):
    """Waarom een contextbron er is, vanuit het werkgebied gezien."""

    ANALYSEREN = "analyseren"          # binnen een analyseselectie, maar zonder bruikbare annotatie
    CONTEXT = "context"                # binnen een contextselectie
    ONDERZOEK = "onderzoek"            # door de keten zelf gevonden (zelfde artikel, definitie, verwijzing)
    VERGELIJKING = "vergelijking"      # alleen ter vergelijking, niet als onderbouwing


class Reden(str, Enum):
    """Hoe een contextbron gevonden is; ook de volgorde waarin het budget hem toelaat."""

    ZELFDE_ARTIKEL = "zelfde_artikel"
    DEFINITIE_IN_REGELING = "definitie_in_regeling"
    VERWIJZING = "verwijzing"
    CONTEXTSELECTIE = "contextselectie"


class Contextbron(Bron):
    """Een bronnode die de keten onderzoekt zonder dat er een formulering op staat."""

    rol: Rol
    reden: Reden
    voor: tuple[str, ...] = ()         # de element-id's of bron-IRI's die hem aanleverden


class Vergelijkingsbegrip(_Vast):
    """Een bestaand begrip als vergelijkingsmateriaal; nooit een bron, nooit bewijs."""

    id: str
    naam: str
    definitie: str = ""
    status: str = ""
    werkgebied_id: str = ""
    eigen: bool = True                 # uit hetzelfde werkgebied


class Ontbrekend(_Vast):
    """Wat er onderzocht had moeten worden en niet onderzocht is, met de reden."""

    wat: str                           # een bron-IRI, of een omschrijving
    reden: str                         # budget | niet_in_graaf | onbereikbaar | buiten_selectie

    @field_validator("reden")
    @classmethod
    def _reden(cls, r: str) -> str:
        if r not in ("budget", "niet_in_graaf", "onbereikbaar", "buiten_selectie"):
            raise ValueError(f"onbekende reden: {r}")
        return r


def onderzoek_id(manifest_id: str, bronnen: tuple[Contextbron, ...] | list,
                 begrippen: tuple[Vergelijkingsbegrip, ...] | list, versie: str) -> str:
    """Inhoud, geen moment: zelfde manifest, dezelfde contextbronnen op dezelfde stand en dezelfde
    vergelijkingsbegrippen geven hetzelfde id. Het vergelijkingsmateriaal telt mee omdat het in de
    prompt komt; een gewijzigde definitie elders maakt een eerder dossier dus verouderd."""
    delen = [manifest_id, versie]
    delen += sorted(f"{b.bron_iri}@{b.bron_hash}" for b in bronnen)
    delen += sorted(f"{x.id}|{x.status}|{_hash(x.naam, x.definitie)[:12]}" for x in begrippen)
    return "O" + _hash(*delen)[:16]


class Onderzoek(_Vast):
    """De onderzoeksstand van één manifest: welke context er gelezen is, en wat niet.

    Onveranderlijk en inhoudelijk geïdentificeerd, net als het manifest. Een contextbron valt nooit
    samen met een manifestbron: wat geannoteerd is, staat al in het manifest.
    """

    manifest_id: str
    bronnen: tuple[Contextbron, ...] = ()
    begrippen: tuple[Vergelijkingsbegrip, ...] = ()
    ontbrekend: tuple[Ontbrekend, ...] = ()
    versie: str = ONDERZOEK_VERSIE

    @model_validator(mode="after")
    def _samenhang(self) -> Onderzoek:
        iris = [b.bron_iri for b in self.bronnen]
        if len(set(iris)) != len(iris):
            raise ValueError("een contextbron staat dubbel in het onderzoek")
        return self

    @property
    def id(self) -> str:
        return onderzoek_id(self.manifest_id, self.bronnen, self.begrippen, self.versie)

    def past_bij(self, manifest: Manifest) -> Onderzoek:
        """Toets het onderzoek tegen zijn manifest; geeft zichzelf terug of faalt."""
        if self.manifest_id != manifest.id:
            raise ValueError("het onderzoek hoort bij een ander manifest")
        dubbel = {b.bron_iri for b in self.bronnen} & {b.bron_iri for b in manifest.bronnen}
        if dubbel:
            raise ValueError(f"een contextbron is ook een manifestbron: {sorted(dubbel)[0]}")
        return self

    def bron(self, bron_iri: str) -> Contextbron:
        return next(b for b in self.bronnen if b.bron_iri == bron_iri)


class Taalanalyse(_Vast):
    """Wat de taalstap over één formulering vaststelt. Alles herleidbaar tot tokens in de bron."""

    element_id: str
    kern: str                          # lemma van de kern ("belastingaanslag", "termijn")
    kernvorm: str = ""                 # de kern zoals hij in de tekst staat
    term: str                          # kern + vaste modificeerders, zonder lidwoord, kleine letters
    kop: str = ""                      # kop van de samenstelling, als die elders als kern voorkomt
    beperkt: bool = False              # de formulering beperkt de kern (bijzin, voorzetselgroep)
    aanwijzend: bool = False           # begint met "die", "deze", "dat", "dit"
    antecedent_start: int | None = None  # waar een aanwijzende formulering naar terugwijst
    antecedent_eind: int | None = None
    gedegradeerd: bool = False         # zonder volledige parse vastgesteld
    zin: bool = False                  # de span draagt een persoonsvorm: een zin, geen naamwoordgroep


# ---------------------------------------------------------------------------------------------
# Bewijs en kandidaten
# ---------------------------------------------------------------------------------------------


class Bewijs(_Vast):
    """Eén waarneming over een formulering of een paar; herleidbaar tot regel en bronfragment."""

    code: str                          # "ZELFDE_KERN", "GEDEELDE_DEFINITIE", "KWALIFICATIE", …
    polariteit: Polariteit
    sterkte: Sterkte
    regel: str                         # "begrip.kern.lemma"
    versie: str                        # versie van de regel
    fragment: str = ""                 # het letterlijke bronfragment dat het signaal draagt
    bron_iri: str = ""
    detail: str = ""


def kandidaat_id(hypothese: Hypothese, van: str, naar: str) -> str:
    a, b = sorted((van, naar)) if hypothese.symmetrisch else (van, naar)
    return "P" + _hash(hypothese.value, a, b)[:12]


class Kandidaat(_Vast):
    """Een hypothese over twee formuleringen, met alle bewijs ervoor en ertegen.

    Bij een symmetrische hypothese staan de leden gesorteerd; bij een gerichte is `van` de
    algemene of kwalificerende kant zoals de hypothese zegt.
    """

    id: str
    hypothese: Hypothese
    van: str
    naar: str
    bewijs: tuple[Bewijs, ...]

    @field_validator("bewijs")
    @classmethod
    def _bewijs(cls, bewijs: tuple[Bewijs, ...]) -> tuple[Bewijs, ...]:
        if not bewijs:
            raise ValueError("een kandidaat zonder bewijs is een gok")
        return bewijs

    @model_validator(mode="after")
    def _leden(self) -> Kandidaat:
        if self.van == self.naar:
            raise ValueError("een kandidaat verbindt twee verschillende formuleringen")
        if self.id != kandidaat_id(self.hypothese, self.van, self.naar):
            raise ValueError("kandidaat-id volgt niet uit hypothese en leden")
        if self.hypothese.symmetrisch and self.van > self.naar:
            raise ValueError("symmetrische kandidaat met ongesorteerde leden")
        return self

    @classmethod
    def maak(cls, hypothese: Hypothese, van: str, naar: str,
             bewijs: list[Bewijs] | tuple[Bewijs, ...]) -> Kandidaat:
        if hypothese.symmetrisch:
            van, naar = sorted((van, naar))
        return cls(id=kandidaat_id(hypothese, van, naar), hypothese=hypothese, van=van,
                   naar=naar, bewijs=tuple(bewijs))

    def met_bewijs(self, extra: list[Bewijs] | tuple[Bewijs, ...]) -> Kandidaat:
        """Voeg bewijs toe zonder dubbelingen; de volgorde van eerste waarneming blijft."""
        return self.model_copy(update={"bewijs": tuple(dict.fromkeys((*self.bewijs, *extra)))})

    @property
    def leden(self) -> tuple[str, str]:
        return (self.van, self.naar)


# ---------------------------------------------------------------------------------------------
# Uitkomst
# ---------------------------------------------------------------------------------------------


class Beslissing(_Vast):
    """Wat de beslistabel (of later een model) over één kandidaat zei, en waarom."""

    kandidaat_id: str
    besluit: Besluit
    door: str = "regel"                # "regel" | "model" (later)
    regel: str                         # id van de rij in de beslistabel
    reden: str = ""


def groep_id(leden: tuple[str, ...] | list[str]) -> str:
    return "G" + _hash(*sorted(leden))[:12]


class Betekenisgroep(_Vast):
    """Formuleringen die mogelijk één begrip aanduiden. Een voorstel, geen begrip."""

    id: str
    leden: tuple[str, ...]
    kandidaten: tuple[str, ...]        # de link-kandidaten die de groep vormen
    conflicten: tuple[str, ...] = ()   # non-link-kandidaten tussen leden van deze groep
    aandacht: Aandacht
    uitleg: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _vorm(self) -> Betekenisgroep:
        if len(self.leden) < 2:
            raise ValueError("een groep heeft minstens twee leden")
        if tuple(sorted(self.leden)) != self.leden:
            raise ValueError("groepsleden staan gesorteerd")
        if self.id != groep_id(self.leden):
            raise ValueError("groep-id volgt niet uit de leden")
        if self.conflicten and self.aandacht is not Aandacht.GEEL:
            raise ValueError("een groep met een conflict is een vraag (geel)")
        return self

    @classmethod
    def maak(cls, leden: list[str] | tuple[str, ...], kandidaten: list[str] | tuple[str, ...],
             conflicten: list[str] | tuple[str, ...] = (), aandacht: Aandacht = Aandacht.GROEN,
             uitleg: list[str] | tuple[str, ...] = ()) -> Betekenisgroep:
        gesorteerd = tuple(sorted(set(leden)))
        return cls(id=groep_id(gesorteerd), leden=gesorteerd, kandidaten=tuple(sorted(kandidaten)),
                   conflicten=tuple(sorted(conflicten)), aandacht=aandacht, uitleg=tuple(uitleg))


class Vraag(_Vast):
    """Een paar waarover de keten niet beslist: mogelijk hetzelfde begrip (possible link)."""

    kandidaat_id: str
    van: str
    naar: str
    regel: str                         # de rij van de beslistabel
    uitleg: tuple[str, ...] = ()


class Relatie(_Vast):
    """Een getypeerd verband tussen twee formuleringen dat géén samenvoeging is."""

    kandidaat_id: str
    hypothese: Hypothese
    van: str
    naar: str
    aandacht: Aandacht
    uitleg: tuple[str, ...] = ()

    @field_validator("hypothese")
    @classmethod
    def _geen_synoniem(cls, h: Hypothese) -> Hypothese:
        if h is Hypothese.ZELFDE_BETEKENIS:
            raise ValueError("zelfde betekenis is een groep, geen relatie")
        return h


# ---------------------------------------------------------------------------------------------
# De model-laag (spoor D, fase C): bovenop de uitkomst, nooit erin
# ---------------------------------------------------------------------------------------------


class Oordeel(str, Enum):
    """Wat het model over een twijfelpaar zegt (PLAN §D: de uitkomst van een vergelijking)."""

    ZELFDE_BETEKENIS = "zelfde_betekenis"
    VERWANT_ANDER_BEGRIP = "verwant_ander_begrip"
    BETEKENISVERSCHIL = "betekenisverschil"
    ONBESLIST = "onbeslist"


class ModelOordeel(_Vast):
    """Het oordeel over één twijfelvraag. `onbeslist` met een reden is ook wat ongeldige uitvoer wordt."""

    kandidaat_id: str
    oordeel: Oordeel
    motivatie: str = ""
    reden: str = ""                    # waarom er geen bruikbaar oordeel is (code), anders leeg


class Herkomst(str, Enum):
    """Waar een voorgestelde definitie vandaan komt; dezelfde waarden als `begrip_contracts.Herkomst`."""

    LETTERLIJK = "letterlijk"          # de definiens van een begripsbepaling, zonder model
    SAMENGESTELD = "samengesteld"      # letterlijke fragmenten, door het model gekozen op id
    GEFORMULEERD = "geformuleerd"      # door het model geschreven, rustend op genoemde fragmenten


def fragment_id(bron_iri: str, start: int, eind: int) -> str:
    return "F" + _hash(bron_iri, str(start), str(eind))[:10]


class Fragment(_Vast):
    """Een letterlijk stuk brontekst (zin of zinsdeel) dat het model op id kan kiezen."""

    id: str
    bron_iri: str
    start: int = Field(ge=0)
    eind: int = Field(gt=0)
    tekst: str

    @model_validator(mode="after")
    def _id(self) -> Fragment:
        if self.id != fragment_id(self.bron_iri, self.start, self.eind):
            raise ValueError("fragment-id volgt niet uit bron en offsets")
        return self


class Kaart(_Vast):
    """De concept-kaart bij een groep: een voorstel, nooit een begrip."""

    groep_id: str
    naam: str
    alternatieve_termen: tuple[str, ...] = ()
    context: str = ""
    definitie: str = ""
    herkomst: Herkomst | None = None
    definitie_bron_iri: str = ""       # alleen bij letterlijk
    definitie_vindplaats: str = ""
    fragmenten: tuple[Fragment, ...] = ()   # bij samengesteld: de delen; bij geformuleerd: de onderbouwing
    motivatie: str = ""                # van het model, bij samengesteld/geformuleerd
    aandacht: Aandacht = Aandacht.GEEL
    aandachtspunten: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _vorm(self) -> Kaart:
        if bool(self.definitie) != (self.herkomst is not None):
            raise ValueError("een definitie heeft een herkomst, en een herkomst een definitie")
        if self.herkomst in (Herkomst.SAMENGESTELD, Herkomst.GEFORMULEERD) and not self.fragmenten:
            raise ValueError("een samengestelde of geformuleerde definitie noemt haar fragmenten")
        if self.herkomst is Herkomst.GEFORMULEERD and self.aandacht is not Aandacht.GEEL:
            raise ValueError("een geformuleerde definitie is altijd geel")
        return self
