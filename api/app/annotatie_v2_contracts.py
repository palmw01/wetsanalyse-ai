"""Wirecontract voor bronnode-lagen; offsets zijn Unicode-codepoints."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Doel(BaseModel):
    bron_iri: str = ""
    bwb_id: str = ""
    artikel: str = ""
    lid: str = ""


class Anker(BaseModel):
    bron_iri: str
    start: int = Field(ge=0)
    eind: int = Field(gt=0)
    tekst: str
    bron_hash: str


class Element(BaseModel):
    # Critic/provenancevelden blijven behouden, maar eigenaar/lifecycle worden server-side gezet.
    model_config = ConfigDict(extra="allow")
    id: str = Field(default="", max_length=64)
    klasse: str
    tekst: str
    toelichting: str = ""
    ankers: list[Anker] = Field(min_length=1, max_length=100)
    # Herkomstspoor per element (ADR-001 PR 15). Expliciet in plaats van via `extra`, zodat het
    # contract zegt dat het meereist en tot in de opslag en de export bewaard blijft.
    trace: dict = Field(default_factory=dict)


class Dekking(BaseModel):
    voltooid: bool = False
    bereik: list[str] = Field(default_factory=list)
    parent_context: bool = False
    # Wat de keten per bronnode wel en niet kon bekijken (ADR-001 PR 10): de twaalf
    # detectiedimensies en de ongedekte zinsdelen met offsets – `{bron_iri: {dimensies, ongedekt}}`.
    # Geen recall; een meting van de detectoren. Expliciet in het model, anders valt hij stil weg.
    structureel: dict = Field(default_factory=dict)
    # Procesdekking (A): per kandidaatstatus het aantal; UNHANDLED is altijd 0.
    proces: dict = Field(default_factory=dict)


class CriticSuggestie(BaseModel):
    element_id: str = Field(min_length=1, max_length=64)
    aandacht: Literal["groen", "geel", "rood"]
    motivatie: str
    voorstel_klasse: str = ""
    voorstel_tekst: str = ""


class Batch(BaseModel):
    batch_id: str = Field(min_length=1, max_length=128)
    doel: Doel
    snapshot_id: str
    verwachte_revisies: dict[str, int] = Field(default_factory=dict)
    elementen: list[Element] = Field(default_factory=list, max_length=5000)
    dekking: Dekking = Field(default_factory=Dekking)
    run: dict = Field(default_factory=dict)
    suggesties: list[CriticSuggestie] = Field(default_factory=list, max_length=1000)


class Beslissing(BaseModel):
    type: Literal["approve", "reject", "heropen", "comment", "edit"]
    verwachte_revisies: dict[str, int]
    snapshot_id: str
    wijziging: dict = Field(default_factory=dict)
    comment: str = ""
    review_reason: str | None = None


class Zoekvraag(BaseModel):
    bron_iri: str = ""
    bronnode_id: str = ""
    bwb_id: str = ""
    klasse: str = ""
    jas_klassen: list[str] = Field(default_factory=list)
    tekst: str = ""
    lifecycle: list[str] = Field(default_factory=list)
    laagstatus: list[str] = Field(default_factory=list)
    tekstveld: Literal["citaat", "toelichting", "beide"] = "beide"
    match: Literal["exact", "bevat"] = "bevat"
    scope: Literal["node", "subtree"] = "subtree"
    inclusief_verouderd: bool = False
    bronversie: str = ""
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    cursor: str = Field(default="", max_length=2048)

    @field_validator("lifecycle", mode="before")
    @classmethod
    def _legacy_lifecycle(cls, value):
        return [value] if isinstance(value, str) and value else ([] if value == "" else value)

    @model_validator(mode="after")
    def _filters(self):
        from .validation import GELDIGE_JAS_KLASSEN
        from .annotatie_contracts import Lifecycle, DocumentStatus
        if self.bron_iri and self.bronnode_id and self.bron_iri != self.bronnode_id:
            raise ValueError("Tegenstrijdige bronselectie.")
        self.bron_iri = self.bron_iri or self.bronnode_id
        if self.klasse:
            self.jas_klassen = list(dict.fromkeys([*self.jas_klassen, self.klasse]))
        if set(self.jas_klassen) - GELDIGE_JAS_KLASSEN:
            raise ValueError("Onbekende JAS-klasse.")
        if set(self.lifecycle) - {x.value for x in Lifecycle}:
            raise ValueError("Onbekende lifecycle.")
        if set(self.laagstatus) - {x.value for x in DocumentStatus}:
            raise ValueError("Onbekende laagstatus.")
        return self
