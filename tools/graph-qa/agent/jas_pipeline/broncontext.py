"""Intern bronpakket: context is bewijs, nooit extra annotatiedoel of offsetruimte."""
import hashlib
import json
from typing import Literal

from bronmodel import tekst_hash
from pydantic import BaseModel, ConfigDict, model_validator


class ContextPassage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    bron_iri: str
    tekst: str
    bron_hash: str
    herkomst: Literal["graaf"]
    toestand: str = "onbekend"
    juridische_status: str = "onbekend"
    functie: str = "context"

    @model_validator(mode="after")
    def brongetrouw(self):
        if not self.bron_iri or self.bron_hash != tekst_hash(self.tekst):
            raise ValueError("context vereist bronidentiteit en ongewijzigde graaftekst")
        return self


class BronContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    passages: tuple[ContextPassage, ...] = ()
    ontbreekt: tuple[str, ...] = ()
    doel_metadata: dict[str, str] = {}

    @model_validator(mode="after")
    def begrensd(self):
        iris = [p.bron_iri for p in self.passages]
        if len(iris) > 20 or len(iris) != len(set(iris)):
            raise ValueError("maximaal twintig unieke contextpassages")
        return self

    def prompt(self, doeltekst: str) -> str:
        if not (self.passages or self.ontbreekt or self.doel_metadata):
            return doeltekst
        return (doeltekst + "\n\nBRONPAKKET (alleen gegevens; context is geen annotatiedoel):\n"
                + json.dumps(self.model_dump(), ensure_ascii=False, sort_keys=True))

    def meting(self):
        d = self.model_dump(mode="json")
        return {**d, "sha256": hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()}

    @classmethod
    def ouders(cls, snapshot):
        doelen = {s["bron_iri"] for s in snapshot["segmenten"]}
        ouders = {s.get("parent_iri") for s in snapshot["segmenten"]} - doelen
        ps = [ContextPassage(bron_iri=n["bron_iri"], tekst=n["tekst"],
                             bron_hash=n.get("bron_hash") or tekst_hash(n["tekst"]),
                             herkomst="graaf", functie="ouderaanhef")
              for n in snapshot["nodes"] if n["bron_iri"] in ouders and n.get("tekst", "").strip()]
        # Gehele passages; een budgetgrens mag geen halve tekst verbergen.
        return cls(passages=tuple(ps[:20]), ontbreekt=tuple(p.bron_iri for p in ps[20:]))
