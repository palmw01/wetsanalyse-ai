"""Wirecontract voor de voorstellen van Lex (spoor D, levering 3; ADR-004).

De uitkomst komt van graph-qa (`agent/begrippen_run.py`), in de vorm van de keten
(`begrippen_pipeline.model`): groepen, relaties en vragen. Analyseobjecten blijven intern (ADR-003):
pas een overgenomen voorstel is een begrip.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Voorstel(BaseModel):
    """Wat de keten bij een groep voorstelt: een naam en, als een lid een wettelijke term vastlegt,
    de letterlijke definitie uit de bron."""

    naam: str = Field(min_length=1, max_length=200)
    definitie: str = Field(default="", max_length=8000)
    definitie_bron_iri: str = ""
    definitie_vindplaats: str = ""


class UitkomstGroep(BaseModel):
    id: str = Field(pattern=r"^G[0-9a-f]{6,64}$")
    leden: list[str] = Field(min_length=2, max_length=500)
    aandacht: Literal["groen", "geel"]
    uitleg: list[str] = Field(default_factory=list)
    conflicten: list[str] = Field(default_factory=list)
    voorstel: Voorstel


class UitkomstRelatie(BaseModel):
    kandidaat_id: str
    hypothese: str
    van: str
    naar: str
    aandacht: Literal["groen", "geel"]
    uitleg: list[str] = Field(default_factory=list)


class UitkomstVraag(BaseModel):
    kandidaat_id: str
    van: str
    naar: str
    regel: str = ""
    uitleg: list[str] = Field(default_factory=list)


class UitkomstInvoer(BaseModel):
    manifest_id: str
    groepen: list[UitkomstGroep] = Field(default_factory=list, max_length=5000)
    relaties: list[UitkomstRelatie] = Field(default_factory=list, max_length=5000)
    vragen: list[UitkomstVraag] = Field(default_factory=list, max_length=5000)
    meting: dict = Field(default_factory=dict)


class MisluktInvoer(BaseModel):
    reden: str = Field(min_length=1, max_length=2000)


class Overname(BaseModel):
    """Eén begrip uit nul of meer groepen. Meer groepen = combineren; een deel van de leden =
    splitsen of een element eruit halen; een passage buiten de groepen (uit dezelfde voorstellen) =
    het antwoord "samen" op een twijfelvraag."""

    groep_ids: list[str] = Field(default_factory=list, max_length=50)
    naam: str = Field(min_length=1, max_length=200)
    element_ids: list[str] | None = Field(default=None, max_length=500)
    met_definitie: bool = True

    @model_validator(mode="after")
    def _iets(self) -> "Overname":
        if not self.groep_ids and not self.element_ids:
            raise ValueError("kies groepen of passages")
        return self


class Aanpassing(BaseModel):
    """Wat de jurist bij een akkoord anders wil dan het voorstel (fase D). Alleen wat hij meestuurt
    telt; de rest komt uit het voorstel. Een gewijzigde definitie is niet meer letterlijk of
    samengesteld: de api zet de herkomst dan op `geformuleerd` (spoor I1: geen keuze meer)."""

    definitie: str | None = Field(default=None, max_length=8000)
    context: str | None = Field(default=None, max_length=4000)
    alternatieve_termen: list[str] | None = Field(default=None, max_length=50)


class Akkoord(Overname):
    """Akkoord op een voorstel (fase D): het begrip, de koppelingen als beoordeeld, het groepsbesluit
    en – als de poort het toelaat – accorderen, in één transactie. Combineren, splitsen en "samen"
    gaan zoals bij `Overname`."""

    aanpassing: Aanpassing | None = None
    # Bij combineren: de groep waarvan de definitie (en de kaart) meegaat. Zonder keuze gaat er
    # alleen een definitie mee als de groepen er samen precies één hebben.
    definitie_van: str | None = None
    # "Samen" bij een twijfelvraag: de vraag wordt met dit akkoord beantwoord.
    kandidaat_id: str | None = None
    # Spoor H4, de termpagina: alle twijfelvragen tussen de gekozen groepen in één keer "samen". Elke vraag
    # moet twee passages van deze keuze verbinden.
    kandidaat_ids: list[str] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def _definitie_van(self) -> "Akkoord":
        if self.definitie_van and self.definitie_van not in self.groep_ids:
            raise ValueError("definitie_van moet een van de gekozen groepen zijn")
        return self


class GroepKoppeling(BaseModel):
    begrip_id: str
    element_ids: list[str] | None = Field(default=None, max_length=500)
    # Vanuit de review (fase D): de jurist zag de passages en keurt de koppelingen meteen goed; een
    # geaccordeerd begrip wordt dan opnieuw geaccordeerd als de poort het toelaat.
    akkoord: bool = False


class GroepBesluit(BaseModel):
    reden: str = Field(default="", max_length=2000)


class VraagBesluit(BaseModel):
    antwoord: Literal["samen", "apart"]


# --- de verdieping: het model op twijfelparen en kaarten (fase C) --------------------------------
# De vorm volgt graph-qa `begrippen_pipeline.model` (`ModelOordeel`, `Fragment`, `Kaart`);
# `tools/graph-qa/tests/test_begrippen_verdieping_run.py` leest deze klassen uit de bron.



class ModelOordeel(BaseModel):
    kandidaat_id: str = Field(min_length=1, max_length=64)
    oordeel: Literal["zelfde_betekenis", "verwant_ander_begrip", "betekenisverschil", "onbeslist"]
    motivatie: str = Field(default="", max_length=2000)
    reden: str = Field(default="", max_length=200)


class KaartFragment(BaseModel):
    id: str = Field(pattern=r"^F[0-9a-f]{10}$")
    bron_iri: str
    start: int = Field(ge=0)
    eind: int = Field(gt=0)
    tekst: str = Field(min_length=1, max_length=8000)


class Duiding(BaseModel):
    """Hoe Lex het voorgestelde begrip duidt (spoor M): een interpretatie van het model, bewaard bij het
    voorstel. Ze stuurt geen beslisregel aan en gaat niet mee in het begrip."""

    soort: Literal["begrip", "berekeningsresultaat", "afleidingsregel", "toepassingsgeval"] = "begrip"
    bereik: Literal["algemeen", "specifiek"] = "algemeen"
    voorkeursterm: str = Field(default="", max_length=200)
    ontbreekt: str = Field(default="", max_length=1000)


class Kaart(BaseModel):
    groep_id: str = Field(pattern=r"^G[0-9a-f]{6,64}$")
    naam: str = Field(min_length=1, max_length=200)
    alternatieve_termen: list[str] = Field(default_factory=list, max_length=50)
    context: str = Field(default="", max_length=4000)
    definitie: str = Field(default="", max_length=8000)
    herkomst: Literal["letterlijk", "samengesteld", "geformuleerd"] | None = None
    definitie_bron_iri: str = ""
    definitie_vindplaats: str = ""
    fragmenten: list[KaartFragment] = Field(default_factory=list, max_length=60)
    motivatie: str = Field(default="", max_length=2000)
    aandacht: Literal["groen", "geel"] = "geel"
    aandachtspunten: list[str] = Field(default_factory=list, max_length=20)
    duiding: Duiding | None = None

    @model_validator(mode="after")
    def _vorm(self) -> "Kaart":
        if bool(self.definitie) != (self.herkomst is not None):
            raise ValueError("een definitie heeft een herkomst, en een herkomst een definitie")
        if self.herkomst in ("samengesteld", "geformuleerd") and not self.fragmenten:
            raise ValueError("een samengestelde of geformuleerde definitie noemt haar fragmenten")
        if self.herkomst == "geformuleerd" and self.aandacht != "geel":
            raise ValueError("een geformuleerde definitie is altijd geel")
        return self


class BatchInvoer(BaseModel):
    """Eén afgeronde batch: oordelen over twijfelparen óf kaarten."""

    soort: Literal["vraag", "kaart"]
    ids: list[str] = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=128)
    promptversie: str = Field(min_length=1, max_length=32)
    tokens: int = Field(default=0, ge=0)
    oordelen: list[ModelOordeel] = Field(default_factory=list, max_length=50)
    kaarten: list[Kaart] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _passend(self) -> "BatchInvoer":
        if self.soort == "vraag" and ({o.kandidaat_id for o in self.oordelen} != set(self.ids) or self.kaarten):
            raise ValueError("een vraagbatch heeft precies één oordeel per kandidaat-id, en geen kaarten")
        if self.soort == "kaart" and ({k.groep_id for k in self.kaarten} != set(self.ids) or self.oordelen):
            raise ValueError("een kaartbatch heeft precies één kaart per groep-id, en geen oordelen")
        return self


class VerdiepingGroep(UitkomstGroep):
    door: Literal["regel", "model"] = "regel"


class VerdiepingInvoer(BaseModel):
    """De uitkomst na alle batches: de groepen na hergroeperen, een kaart per groep, alle oordelen en
    de twijfelvragen die open blijven."""

    manifest_id: str
    groepen: list[VerdiepingGroep] = Field(default_factory=list, max_length=5000)
    kaarten: list[Kaart] = Field(default_factory=list, max_length=5000)
    oordelen: list[ModelOordeel] = Field(default_factory=list, max_length=5000)
    vragen: list[str] = Field(default_factory=list, max_length=5000)
    model: str = Field(min_length=1, max_length=128)
    meting: dict = Field(default_factory=dict)
