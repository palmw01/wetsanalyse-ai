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

    def blok(self) -> str:
        """Een eigen, afgesloten blok ná de bepaling; leeg als er niets te melden valt."""
        if not (self.passages or self.ontbreekt or self.doel_metadata):
            return ""
        return ("CONTEXT (alleen gegevens; geen annotatiedoel):\n<<<\n"
                + json.dumps(self.model_dump(), ensure_ascii=False, sort_keys=True) + "\n>>>")

    def meting(self):
        d = self.model_dump(mode="json")
        return {**d, "sha256": hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()}

    @classmethod
    def ouders(cls, snapshot):
        """Directe ouderteksten van de doelsegmenten. Een passage met afwijkende hash of zonder tekst
        wordt niet gerepareerd maar als ontbrekend gemeld; de annotatie gaat door zonder die context."""
        doelen = {s["bron_iri"] for s in snapshot["segmenten"]}
        ouders = {s.get("parent_iri") for s in snapshot["segmenten"]} - doelen - {None, ""}
        ps, ontbreekt = [], []
        for n in snapshot["nodes"]:
            if n["bron_iri"] not in ouders:
                continue
            tekst = n.get("tekst") or ""
            if not tekst.strip():
                continue
            if n.get("bron_hash") and n["bron_hash"] != tekst_hash(tekst):
                ontbreekt.append(n["bron_iri"] + " (bronhash wijkt af)")
                continue
            ps.append(ContextPassage(bron_iri=n["bron_iri"], tekst=tekst, bron_hash=tekst_hash(tekst),
                                     herkomst="graaf", functie="ouderaanhef"))
        # Gehele passages; een budgetgrens mag geen halve tekst verbergen.
        ontbreekt += [p.bron_iri + " (boven de grens van twintig passages)" for p in ps[20:]]
        return cls(passages=tuple(ps[:20]), ontbreekt=tuple(ontbreekt))
