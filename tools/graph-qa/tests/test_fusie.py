"""Kandidaatfusie en JAS-specificiteit over geneste spans (ADR-001 PR 8)."""
from __future__ import annotations

import pytest
from bronmodel import Span, tekst_hash

from agent.jas_klassen import REGELS, RegelType
from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
from agent.jas_pipeline.fusie import fuseer
from agent.jas_pipeline.kandidaten import (
    BronSpan, Candidate, CandidateStatus, DetectorResult, Evidence, SpanOption,
)
from agent.jas_pipeline.specificiteit import FUNCTIECODES, pas_toe

T, P, V, O = "Tijdsaanduiding", "Parameter en parameterwaarde", "Variabele en variabelewaarde", "Rechtsobject"
TEKST = "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet."


def _span(fragment, tekst=TEKST, iri="urn:t"):
    s = tekst.index(fragment)
    return Span(iri, s, s + len(fragment), fragment, tekst_hash(tekst))


def _k(fragment, klassen, code, detector="d", opties=(), tekst=TEKST):
    return Candidate.maak(_span(fragment, tekst), klassen, [Evidence(detector=detector, code=code)],
                          [SpanOption(soort=s, span=BronSpan.van(_span(f, tekst))) for f, s in opties])


def _r(*ks, naam="d"):
    return DetectorResult(detector=naam, versie="1", bron_iri="urn:t", kandidaten=ks)


def test_zelfde_span_wordt_een_kandidaat_met_al_het_bewijs():
    a = _k("zes weken", [T], "TEMPORAL_DURATION", "tijd")
    b = _k("zes weken", [O], "NOUN_PHRASE", "np")
    [k] = fuseer([_r(a, naam="tijd"), _r(b, naam="np")]).kandidaten
    assert {e.detector for e in k.evidence} >= {"tijd", "np"}
    assert k.possible_classes[0] == T and O in k.possible_classes


def test_fusie_verandert_geen_offset_en_is_deterministisch():
    """Eigenschap over echte detectoruitvoer: elke span en optie is letterlijk en onveranderd."""
    tekst = ("De dwangsom bedraagt de eerste veertien dagen € 23 per dag, binnen zes weken na de "
             "dagtekening, indien de verzekerde in Nederland woont.")
    resultaten = detecteer_alles(BronTekst.van_tekst("urn:t", tekst))
    voor = {(k.span.start, k.span.eind) for r in resultaten for k in r.kandidaten}
    f = fuseer(resultaten)
    assert {(k.span.start, k.span.eind) for k in f.kandidaten} == voor
    for k in f.kandidaten:
        assert tekst[k.span.start:k.span.eind] == k.span.tekst
        assert all(tekst[o.span.start:o.span.eind] == o.span.tekst for o in k.span_options)
        assert k.span.sleutel() not in {o.span.sleutel() for o in k.span_options}
    assert fuseer(resultaten) == f


def test_labels_zijn_uniek_en_in_bronvolgorde():
    f = fuseer(detecteer_alles(BronTekst.van_tekst("urn:t", TEKST)))
    labels = [k.label for k in f.kandidaten]
    assert labels == [f"C{i:03d}" for i in range(1, len(labels) + 1)]
    assert f.per_label()["C001"].span.start == min(k.span.start for k in f.kandidaten)


def test_relaties_nesting_en_overlap():
    a = _k("zes weken na de dagtekening", [T], "TEMPORAL_DURATION")
    b = _k("zes weken", [T], "TEMPORAL_DURATION")
    c = _k("de dagtekening van het aanslagbiljet", ["Rechtsfeit"], "NOMINALIZED_ACTION")
    f = fuseer([_r(a, b, c)])
    soorten = {(f.per_id()[r.van].span.tekst, f.per_id()[r.naar].span.tekst, r.soort) for r in f.relaties}
    assert ("zes weken na de dagtekening", "zes weken", "bevat") in soorten
    assert ("zes weken na de dagtekening", "de dagtekening van het aanslagbiljet", "overlapt") in soorten


def test_overgeslagen_detector_blijft_zichtbaar():
    f = fuseer([DetectorResult(detector="bijzin", versie="1", bron_iri="urn:t", overgeslagen=True,
                               reden="geen parse")])
    assert [(o.detector, o.reden) for o in f.overgeslagen] == [("bijzin", "geen parse")]


# --- specificiteit -----------------------------------------------------------------------------

def test_iw01_geen_parameter_op_de_duur_binnen_de_tijdsaanduiding():
    """De IW01-bevinding (evaluatie-methode.md): 'zes weken' kreeg naast de Tijdsaanduiding een
    Parameterlabel. Binnen een Tijdsaanduiding met dezelfde functie vervalt dat (JAS-PRIORITY-001)."""
    tijd = _k("zes weken na de dagtekening van het aanslagbiljet", [T], "TEMPORAL_DURATION",
              opties=[("zes weken", "kern")])
    duur_als_waarde = _k("zes weken", [P, V], "NUMBER")
    f = fuseer([_r(tijd, duur_als_waarde)])
    k = next(k for k in f.kandidaten if k.span.tekst == "zes weken")
    assert k.status is CandidateStatus.REJECTED
    assert any(e.regel == "JAS-PRIORITY-001" and e.code == "PRIORITY_APPLIED" for e in k.evidence)


def test_zelfde_span_met_tijd_en_parameter_houdt_alleen_tijd():
    [k] = pas_toe((_k("zes weken", [T, P, O], "TEMPORAL_DURATION"),))
    assert k.possible_classes == (T, O) and k.status is CandidateStatus.UNHANDLED
    assert k.evidence[-1].regel == "JAS-PRIORITY-001"


def test_plaats_prioriteit_binnen_een_plaatsaanduiding():
    tekst = "Deze regeling geldt in de gemeente Amsterdam."
    plaats = _k("in de gemeente Amsterdam", ["Plaatsaanduiding"], "LOCATION_NAME", tekst=tekst)
    naam = _k("de gemeente Amsterdam", [V, "Rechtssubject"], "LOCATION_NAME", tekst=tekst)
    [_, k] = sorted(pas_toe((plaats, naam)), key=lambda k: k.span.start)
    assert k.possible_classes == ("Rechtssubject",)
    assert any(e.regel == "JAS-PRIORITY-002" for e in k.evidence)


def test_een_bedrag_binnen_een_termijn_is_niet_dezelfde_functie():
    tekst = "binnen zes weken na betaling van € 23"
    tijd = _k("binnen zes weken na betaling van € 23", [T], "TEMPORAL_DURATION", tekst=tekst)
    bedrag = _k("€ 23", [P, V], "MONEY_AMOUNT", tekst=tekst)
    assert pas_toe((tijd, bedrag))[1] == bedrag


def test_elke_prioriteitsregel_heeft_een_functiecode():
    for r in REGELS:
        if r.type is RegelType.PRIORITEIT:
            rang = dict(r.priority)
            assert max(rang, key=rang.get) in FUNCTIECODES, r.id


def test_iw01_end_to_end_via_de_detectoren():
    f = fuseer(detecteer_alles(BronTekst.van_tekst("urn:t", TEKST)))
    tijd = [k for k in f.kandidaten if T in k.possible_classes]
    assert any(k.span.tekst == "zes weken na de dagtekening van het aanslagbiljet" for k in tijd)
    assert not any(k.span.tekst == "zes weken" and {P, V} & set(k.possible_classes)
                   and k.status is not CandidateStatus.REJECTED for k in f.kandidaten)
