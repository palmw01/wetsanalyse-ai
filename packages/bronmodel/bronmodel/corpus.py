"""Onveranderlijke bronspans en de vertaling tussen analysecorpus en bronnode.

Een analyse leest de tekst van meerdere bronnodes als één corpus: de niet-lege segmenten van een
snapshot, samengevoegd met één lege regel ertussen. Een annotatie wordt daarentegen vastgelegd per
bronnode, in Unicode-codepoints binnen de eigen tekst van die node. `CorpusMap` is de enige plek
die tussen die twee rekent; `Span` is het bronfragment dat daaruit komt en dat nergens meer
verschuift.

De offsets volgen Python-strings, dus codepoints: dezelfde eenheid als `valideer_ankers`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SCHEIDING = "\n\n"


class SpanFout(ValueError):
    """Een span valt buiten zijn node of klopt niet met de letterlijke brontekst."""


@dataclass(frozen=True, slots=True)
class Span:
    """Een letterlijk fragment van één bronnode: [start, eind) in codepoints."""

    bron_iri: str
    start: int
    eind: int
    tekst: str
    bron_hash: str

    def anker(self) -> dict[str, Any]:
        """De ankervorm van het api-contract (`annotatie_v2_contracts.Anker`)."""
        return {"bron_iri": self.bron_iri, "start": self.start, "eind": self.eind,
                "tekst": self.tekst, "bron_hash": self.bron_hash}


@dataclass(frozen=True, slots=True)
class CorpusSegment:
    """Waar de tekst van één bronnode in het corpus staat."""

    bron_iri: str
    corpus_start: int
    corpus_eind: int
    tekst: str
    bron_hash: str


class CorpusMap:
    """Het corpus van een snapshot plus de exacte plaats van elke node erin."""

    def __init__(self, segmenten: list[dict[str, Any]]):
        delen: list[str] = []
        plaatsen: list[CorpusSegment] = []
        positie = 0
        for segment in segmenten:
            tekst = segment["tekst"]
            if not tekst.strip():
                continue
            if delen:
                positie += len(SCHEIDING)
            plaatsen.append(CorpusSegment(segment["bron_iri"], positie, positie + len(tekst),
                                          tekst, segment["bron_hash"]))
            delen.append(tekst)
            positie += len(tekst)
        self.corpus = SCHEIDING.join(delen)
        self.segmenten: tuple[CorpusSegment, ...] = tuple(plaatsen)
        self._per_iri = {s.bron_iri: s for s in plaatsen}
        self._bron = {s["bron_iri"]: s for s in segmenten}

    def segment(self, bron_iri: str) -> CorpusSegment:
        try:
            return self._per_iri[bron_iri]
        except KeyError as exc:
            raise SpanFout("Bronnode valt buiten dit corpus") from exc

    def span(self, bron_iri: str, start: int, eind: int) -> Span:
        """Een gecontroleerde span op een node; de tekst komt uit de bron, nooit van de aanroeper."""
        segment = self.segment(bron_iri)
        if type(start) is not int or type(eind) is not int or not 0 <= start < eind <= len(segment.tekst):
            raise SpanFout("Ongeldige lokale posities")
        return Span(bron_iri, start, eind, segment.tekst[start:eind], segment.bron_hash)

    def naar_spans(self, start: int, eind: int) -> list[Span]:
        """Het corpusbereik [start, eind) als spans per node, in bronvolgorde.

        Een bereik dat over een scheiding heen loopt wordt per node opgeknipt; de scheiding zelf
        hoort bij geen enkele node en valt weg. Een bereik dat alleen scheiding raakt levert [].
        """
        uit: list[Span] = []
        for s in self.segmenten:
            links, rechts = max(start, s.corpus_start), min(eind, s.corpus_eind)
            if links >= rechts:
                continue
            a, z = links - s.corpus_start, rechts - s.corpus_start
            uit.append(Span(s.bron_iri, a, z, s.tekst[a:z], s.bron_hash))
        return uit

    def naar_corpus(self, span: Span) -> tuple[int, int]:
        """De corpusoffsets van een node-span; faalt als de span niet (meer) bij de bron hoort."""
        s = self.segment(span.bron_iri)
        if span.bron_hash != s.bron_hash or s.tekst[span.start:span.eind] != span.tekst:
            raise SpanFout("Span komt niet overeen met de letterlijke bron")
        return s.corpus_start + span.start, s.corpus_start + span.eind

    def als_dicts(self) -> list[dict[str, Any]]:
        """De segmenten in de vorm die de agent-state draagt: de bronnode plus corpusoffsets."""
        return [{**self._bron[s.bron_iri], "corpus_start": s.corpus_start,
                 "corpus_eind": s.corpus_eind} for s in self.segmenten]
