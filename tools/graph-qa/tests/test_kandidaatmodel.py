"""Het kandidaatmodel (ADR-001 PR 5): stabiele identiteit, bewijsplicht, geen verzonnen klassen."""
from __future__ import annotations

import json

import pytest
from bronmodel import CorpusMap, tekst_hash
from pydantic import ValidationError

from agent.jas_pipeline.kandidaten import (
    GEEN_ANNOTATIE, BronSpan, Candidate, CandidateStatus, DetectorResult, Evidence, SpanOption,
    kandidaat_id, label_kandidaten,
)

TEKST = "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet."
KAART = CorpusMap([{"bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:1", "tekst": TEKST,
                    "bron_hash": tekst_hash(TEKST)}])
IRI = "urn:bwb:BWBR0004770:artikel:9:lid:1"
DUUR = Evidence(detector="temporeel", code="TEMPORAL_DURATION", regel="jas.tijd.duur")


def _span(fragment: str):
    start = TEKST.index(fragment)
    return KAART.span(IRI, start, start + len(fragment))


def test_id_is_stabiel_en_hangt_alleen_aan_bron_en_offsets():
    a = Candidate.maak(_span("zes weken"), ["Tijdsaanduiding"], [DUUR])
    b = Candidate.maak(_span("zes weken"), ["Parameter en parameterwaarde"],
                       [Evidence(detector="numeriek", code="NUMBER")])
    assert a.id == b.id == kandidaat_id(IRI, a.span.start, a.span.eind)
    assert a.id != Candidate.maak(_span("zes weken na de dagtekening van het aanslagbiljet"),
                                  ["Tijdsaanduiding"], [DUUR]).id


def test_span_komt_uit_de_bron():
    k = Candidate.maak(_span("zes weken"), ["Tijdsaanduiding"], [DUUR])
    assert k.span.tekst == TEKST[k.span.start:k.span.eind] == "zes weken"
    assert k.span.bron_hash == tekst_hash(TEKST)


def test_geen_verzonnen_klasse_en_geen_kandidaat_zonder_klasse_of_bewijs():
    with pytest.raises(ValidationError):
        Candidate.maak(_span("zes weken"), ["Termijn"], [DUUR])
    with pytest.raises(ValidationError):
        Candidate.maak(_span("zes weken"), [], [DUUR])
    with pytest.raises(ValidationError):
        Candidate.maak(_span("zes weken"), ["Tijdsaanduiding"], [])


def test_klassen_worden_ontdubbeld_en_geen_annotatie_is_altijd_toegestaan():
    k = Candidate.maak(_span("zes weken"), ["Tijdsaanduiding", "Voorwaarde", "Tijdsaanduiding"], [DUUR])
    assert k.possible_classes == ("Tijdsaanduiding", "Voorwaarde")
    assert k.toegestane_beslissingen() == ("Tijdsaanduiding", "Voorwaarde", GEEN_ANNOTATIE)


def test_nieuwe_kandidaat_is_onbehandeld_en_onveranderlijk():
    k = Candidate.maak(_span("zes weken"), ["Tijdsaanduiding"], [DUUR])
    assert k.status is CandidateStatus.UNHANDLED
    with pytest.raises(ValidationError):
        k.status = CandidateStatus.ACCEPTED  # type: ignore[misc]


def test_labels_in_bronvolgorde_langste_eerst_en_deterministisch():
    kort = Candidate.maak(_span("zes weken"), ["Tijdsaanduiding"], [DUUR])
    lang = Candidate.maak(_span("zes weken na de dagtekening van het aanslagbiljet"), ["Tijdsaanduiding"], [DUUR])
    subj = Candidate.maak(_span("Een belastingaanslag"), ["Rechtsobject"],
                          [Evidence(detector="np", code="NOUN_PHRASE", relatie="nsubj")])
    for volgorde in ([kort, lang, subj], [subj, kort, lang]):
        assert [(k.label, k.span.tekst) for k in label_kandidaten(volgorde)] == [
            ("C001", "Een belastingaanslag"),
            ("C002", "zes weken na de dagtekening van het aanslagbiljet"),
            ("C003", "zes weken"),
        ]


def test_serialiseert_naar_json_en_terug():
    optie = SpanOption(soort="np", span=BronSpan.van(_span("de dagtekening van het aanslagbiljet")))
    k = Candidate.maak(_span("zes weken na de dagtekening van het aanslagbiljet"),
                       ["Tijdsaanduiding", "Rechtsfeit"], [DUUR], [optie])
    r = DetectorResult(detector="temporeel", versie="1", bron_iri=IRI, kandidaten=(k,))
    terug = DetectorResult.model_validate(json.loads(r.model_dump_json()))
    assert terug == r


def test_een_overgeslagen_detector_zegt_waarom():
    r = DetectorResult(detector="conditioneel", versie="1", bron_iri=IRI, overgeslagen=True,
                       reden="geen parse: spaCy-model niet beschikbaar")
    assert r.overgeslagen and not r.kandidaten and r.reden
