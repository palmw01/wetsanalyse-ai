"""De hybride annotatieketen als één pure functie (ADR-001 PR 9).

    bronsegmenten → taalanalyse → detectoren → fusie + specificiteit
                  → deterministische besluiten → classifier op labels → voorstellen

Uitvoer is een lijst `AnnotatieVoorstel`-dicts in exact de vorm die de legacy-annoteerder oplevert
(met `ankers` per bronnode en `anker` op het corpus). Daardoor lopen `emit`, de api en de werkplek
ongewijzigd door; de hybride route vervangt alleen wat ervóór zit.

Een voorstel komt er alleen voor een geaccepteerde beslissing. Afgewezen en onzekere kandidaten
verdwijnen niet: ze staan in `Uitkomst.beslissingen` en gaan mee naar de provenance en de
dekkingsboekhouding (PR 10). Er valt hier nooit iets terug naar een volledige LLM-annotatie.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from functools import cache
from typing import Any

from bronmodel import CorpusMap, Span

from ..annotatie import _maak_anker
from ..models import AnnotatieAlternatief, AnnotatieVoorstel
from .besluit import Beslissing, deterministisch
from .classificatie import batches, classificeer, optie_ids, promptversie
from .detectoren import BronTekst, detecteer_alles
from .fusie import Fusie, fuseer
from .kandidaten import Candidate, CandidateStatus
from .profielen import laad
from .taal import maak_provider


@cache
def _provider(spec: str):
    return maak_provider(spec)


@dataclass
class Uitkomst:
    voorstellen: list[dict[str, Any]]
    fusie: Fusie
    beslissingen: list[Beslissing]
    meting: dict[str, Any] = field(default_factory=dict)


def _bronteksten(segmenten: list[dict[str, Any]], nodes: list[dict[str, Any]], taal: str) -> list[BronTekst]:
    """Per niet-leeg segment een BronTekst, met de tekst van de ouder als context (aanhef)."""
    per_iri = {n["bron_iri"]: n for n in nodes}
    provider = _provider(taal)
    uit = []
    for s in segmenten:
        if not s["tekst"].strip():
            continue
        ouder = per_iri.get(s.get("parent_iri", ""), {})
        uit.append(BronTekst(s["bron_iri"], s["tekst"], s["bron_hash"], analyse=provider.analyseer(s["tekst"]),
                             context=ouder.get("tekst", "")))
    return uit


def _grens(k: Candidate, optie: str) -> tuple[int, int]:
    return optie_ids(k)[optie] if optie else (k.span.start, k.span.eind)


def _toelichting(k: Candidate, b: Beslissing) -> str:
    """Eén zin voor de jurist: welke herkenningsvraag past, en waarop de kandidaat berustte."""
    vraag = laad()[b.klasse].official_recognition_intent
    signalen = ", ".join(sorted({e.code.lower().replace("_", " ") for e in k.evidence if e.code != "PRIORITY_APPLIED"}))
    wie = "herkend aan een vast patroon" if b.door == "regel" else "gekozen uit de mogelijke klassen"
    return f"{b.klasse}, {wie} ({signalen}). Herkenningsvraag: {vraag}"


def _voorstel(k: Candidate, b: Beslissing, kaart: CorpusMap, corpus: str, lid: str, vindplaats: str) -> dict[str, Any]:
    start, eind = _grens(k, b.optie)
    seg = kaart.segment(k.span.bron_iri)
    span = Span(k.span.bron_iri, start, eind, seg.tekst[start:eind], seg.bron_hash)
    c_start, c_eind = kaart.naar_corpus(span)
    anker = _maak_anker(corpus, c_start, c_eind, lid)
    alternatieven = [AnnotatieAlternatief(klasse=c, motivatie="ook mogelijk volgens de detectie")
                     for c in k.possible_classes if c != b.klasse] if b.door == "model" else []
    return AnnotatieVoorstel(
        # Deterministisch: dezelfde span met dezelfde klasse krijgt in elke run hetzelfde id, dus de
        # api herkent het element bij een volgende ronde en de stabiliteitsmeting kan vergelijken.
        id=hashlib.sha256(f"{k.id}\x1f{b.klasse}\x1f{start}:{eind}".encode()).hexdigest()[:12],
        klasse=b.klasse, tekst=span.tekst, lid=lid, toelichting=_toelichting(k, b),
        alternatieven=alternatieven, grounded=True, vindplaats=vindplaats,
        anker=anker, ankers=[span.anker()],
    ).model_dump()


def analyseer(*, snapshot: dict[str, Any], corpus_segmenten: list[dict[str, Any]], corpus: str,
              llm: Any, model: str, settings: Any, lid: str = "", vindplaats: str = "",
              hergebruikte_nodes: set[str] | frozenset[str] = frozenset()) -> Uitkomst:
    teksten = [t for t in _bronteksten(snapshot["segmenten"], snapshot["nodes"], settings.taal_provider)
               if t.bron_iri not in hergebruikte_nodes]
    resultaten = [r for t in teksten for r in detecteer_alles(t)]
    fusie = fuseer(resultaten)
    meting: dict[str, Any] = {"llm_calls": 0, "kandidaten": len(fusie.kandidaten),
                              "gedegradeerd": sorted({t.bron_iri for t in teksten if t.analyse and t.analyse.gedegradeerd}),
                              "taal_model": next((t.analyse.model for t in teksten if t.analyse), ""),
                              "classifier_prompt": promptversie()}

    beslissingen: list[Beslissing] = []
    naar_model: list[Candidate] = []
    for k in fusie.kandidaten:
        b = deterministisch(k) if (settings.deterministisch_accepteren or k.status is CandidateStatus.REJECTED) else None
        if b is None:
            naar_model.append(k)
        else:
            beslissingen.append(b)
    for batch in batches(naar_model, settings.classifier_granulariteit):
        beslissingen += classificeer(llm, model, batch, corpus, settings.classifier_temperature, meting)

    kaart = CorpusMap(corpus_segmenten)
    per_id = fusie.per_id()
    voorstellen, gezien = [], set()
    for b in sorted(beslissingen, key=lambda b: b.label):
        if b.status is not CandidateStatus.ACCEPTED:
            continue
        v = _voorstel(per_id[b.kandidaat_id], b, kaart, corpus, lid, vindplaats)
        sleutel = (v["ankers"][0]["bron_iri"], v["ankers"][0]["start"], v["ankers"][0]["eind"], v["klasse"])
        if sleutel not in gezien:                 # twee kandidaten die op dezelfde optie uitkomen
            gezien.add(sleutel)
            voorstellen.append(v)
    meting["deterministisch"] = sum(b.door != "model" for b in beslissingen)
    meting["per_status"] = {s.value: sum(b.status is s for b in beslissingen) for s in CandidateStatus}
    return Uitkomst(voorstellen, fusie, beslissingen, meting)
