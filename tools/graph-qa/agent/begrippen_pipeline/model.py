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
