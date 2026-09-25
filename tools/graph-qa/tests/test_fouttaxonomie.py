"""Fouttaxonomie v2 (onderzoek-empirische-validatie §8, validatieplan V3)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.fouttaxonomie import (
    ALLEEN_SECUNDAIR, CODES, TECHNISCH, JURIDISCH, Kandidaat, Voorstel, classificeer, pas_toe, tel, uit_elementen,
)

T, RO, VAR, VW = "Tijdsaanduiding", "Rechtsobject", "Variabele en variabelewaarde", "Voorwaarde"
T4 = json.loads((Path(__file__).parent / "fixtures" / "t4_li95_spoor.json").read_text(encoding="utf-8"))


def _k(label="C1", s=0, e=10, klassen=(RO, VAR), codes=("OBJECT_NP",), **kw) -> Kandidaat:
    return Kandidaat(label=label, bron="b", start=s, eind=e, klassen=tuple(klassen), codes=frozenset(codes), **kw)


def _v(label="C1", s=0, e=10, klasse=RO, **kw) -> Voorstel:
    return Voorstel(label=label, bron="b", start=s, eind=e, klasse=klasse, **kw)


def _g(s=0, e=10, klasse=RO, gid="G1", **kw) -> dict:
    return {"gid": gid, "start": s, "eind": e, "klasse": klasse, **kw}


def _een(gold, voorstellen, kandidaten, **kw):
    uit = classificeer(gold, voorstellen, kandidaten, bron="b", **kw)
    assert len(uit.fouten) == 1, uit.fouten
    f = uit.fouten[0]
    return f.primair, f.secundair, f.soort


# --- de 12 HUMAN_REVIEW-gevallen van LI §9.5 (T4, §3.2) -----------------------------------------

def test_t4_twaalf_human_reviews_zijn_contractfouten_geen_juridische_twijfel():
    voorstellen, kandidaten = uit_elementen(T4["elementen"], granulariteit=T4["granulariteit"])
    geel = [v for v in voorstellen if v.human_review]
    assert len(geel) == 12
    # Gold volgens §3.2: overal is Tijdsaanduiding de juiste lezing.
    gold = [_g(v.start, v.eind, T, gid=v.label) for v in geel]
    fouten = {f.gid: f for f in classificeer(gold, voorstellen, kandidaten, bron="").fouten if f.gid}

    type_a = {"C003", "C004", "C009", "C011", "C014", "C016", "C031", "C033", "C043"}
    type_b = {"C029", "C034", "C035"}
    assert set(fouten) == type_a | type_b
    for label in type_a:        # voorrang haalde Variabele weg; het model koos hem toch via de batch-enum
        f = fouten[label]
        assert (f.primair, set(f.secundair), f.soort) == (
            "CLASSIFIER_CONTRACT_ERROR", {"CLASSIFIER_CROSS_CANDIDATE_LEAKAGE", "HYPOTHESIS_ERROR"}, TECHNISCH), label
    for label in type_b:        # Tijdsaanduiding werd niet aangeboden; het model zag hem wel
        f = fouten[label]
        assert (f.primair, set(f.secundair), f.soort) == (
            "POSSIBLE_CLASS_ERROR", {"CLASSIFIER_CONTRACT_ERROR", "CLASSIFIER_CROSS_CANDIDATE_LEAKAGE"}, JURIDISCH), label
    contract = [f for f in fouten.values() if "CLASSIFIER_CONTRACT_ERROR" in (f.primair, *f.secundair)]
    assert len(contract) == 12


def test_zonder_bekende_batchindeling_wordt_leakage_niet_geraden():
    voorstellen, kandidaten = uit_elementen(T4["elementen"])
    geel = [v for v in voorstellen if v.human_review]
    gold = [_g(v.start, v.eind, T, gid=v.label) for v in geel]
    fouten = [f for f in classificeer(gold, voorstellen, kandidaten).fouten if f.gid]
    assert not any("CLASSIFIER_CROSS_CANDIDATE_LEAKAGE" in f.secundair for f in fouten)


# --- per code een geconstrueerd geval -----------------------------------------------------------

def test_correct_is_geen_fout():
    uit = classificeer([_g()], [_v()], [_k(door="model", status="ACCEPTED", klasse=RO)])
    assert uit.fouten == [] and uit.correct == 1


def test_candidate_missed():
    assert _een([_g(20, 30)], [], []) == ("CANDIDATE_MISSED", (), JURIDISCH)


def test_detector_span_error_met_richting():
    assert _een([_g(0, 10, T)], [_v(s=0, e=20, klasse=T)], [_k(s=0, e=20, klassen=(T,), codes=("TEMPORAL_DURATION",),
                                                           door="regel")]) == \
        ("DETECTOR_SPAN_ERROR", ("SPAN_TOO_WIDE",), JURIDISCH)
    assert _een([_g(0, 20, T)], [_v(s=0, e=10, klasse=T)], [_k(klassen=(T,), door="regel")])[1] == ("SPAN_TOO_NARROW",)


def test_gold_grens_als_spanoptie_is_een_keuzefout():
    k = _k(s=0, e=20, opties=((0, 10),), door="model", klasse=RO)
    assert _een([_g(0, 10)], [_v(s=0, e=20)], [k]) == ("CLASSIFIER_ERROR", ("SPAN_TOO_WIDE",), JURIDISCH)


def test_classifier_error_en_gemiste_twijfel_bij_sterk_bewijs():
    k = _k(klassen=(T, RO), codes=("TEMPORAL_DURATION", "OBJECT_NP"), door="model", klasse=RO)
    assert _een([_g(klasse=T)], [_v(klasse=RO)], [k]) == ("CLASSIFIER_ERROR", ("UNCERTAINTY_ERROR",), JURIDISCH)
    # Als twijfel voorgelegd is de onzekerheid niet tekortgeschoten.
    assert _een([_g(klasse=T)], [_v(klasse=RO, human_review=True)], [k])[1] == ()
    # Zonder sterk bewijs voor de gold-klasse was er geen waarneembaar signaal.
    k2 = _k(klassen=(T, RO), door="model", klasse=RO)
    assert _een([_g(klasse=T)], [_v(klasse=RO)], [k2]) == ("CLASSIFIER_ERROR", (), JURIDISCH)


def test_model_wijst_af_bij_sterk_bewijs():
    k = _k(klassen=(T,), codes=("TEMPORAL_DATE", "OBJECT_NP"), door="model", status="REJECTED")
    assert _een([_g(klasse=T)], [], [k]) == ("CLASSIFIER_ERROR", ("UNCERTAINTY_ERROR",), JURIDISCH)


def test_possible_class_error_en_hypothesis_error():
    assert _een([_g(klasse=VW)], [_v()], [_k(door="model", klasse=RO)])[0] == "POSSIBLE_CLASS_ERROR"
    # De juiste klasse was er wel, maar voorrang haalde hem weg.
    k = _k(klassen=(T,), vervallen=(VAR,), door="regel", klasse=T)
    assert _een([_g(klasse=VAR)], [_v(klasse=T)], [k])[0] == "HYPOTHESIS_ERROR"
    # Hele kandidaat door voorrang afgewezen.
    k = _k(klassen=(RO,), door="specificiteit", status="REJECTED")
    assert _een([_g()], [], [k]) == ("HYPOTHESIS_ERROR", (), TECHNISCH)


def test_abstain_en_validatiefout():
    k = _k(door="model", status="HUMAN_REVIEW", reden="R-ABSTAIN-HUMAN")
    k = Kandidaat(**{**k.__dict__, "reden": "CLASSIFIER_OMITTED"})
    assert _een([_g()], [_v(human_review=True, klasse=RO)], [k]) == ("CLASSIFIER_ABSTAIN", (), TECHNISCH)
    k = _k(door="model", status="REJECTED", reden="VALIDATION_ERROR:V_SPAN")
    assert _een([_g()], [], [k]) == ("VALIDATION_ERROR", (), TECHNISCH)


def test_reviewfouten():
    # De classifier had gelijk, de reviewer veranderde het.
    k = _k(door="model", klasse=RO)
    assert _een([_g()], [_v(klasse=VAR, resolutie=("R-CONFLICT-CHANGE",))], [k]) == ("REVIEW_ERROR", (), JURIDISCH)
    # De classifier had ongelijk en de review hield het in stand: primair classifier, secundair review.
    k = _k(door="model", klasse=VAR)
    assert _een([_g()], [_v(klasse=VAR, resolutie=("R-CONFLICT-KEEP",))], [k])[:2] == (
        "CLASSIFIER_ERROR", ("REVIEW_ERROR",))
    # Juiste klasse, maar de reviewer gaf ongeldige uitvoer.
    k = _k(door="model", klasse=RO)
    assert _een([_g()], [_v(human_review=True, resolutie=("R-ONGELDIG",))], [k]) == (
        "REVIEW_CONTRACT_ERROR", (), TECHNISCH)


def test_overbodige_voorstellen():
    assert _een([], [_v(klasse=T)], [_k(klassen=(T,), door="regel", klasse=T)]) == ("DETECTOR_ERROR", (), TECHNISCH)
    assert _een([], [_v()], [_k(door="model", klasse=RO)]) == ("CLASSIFIER_ERROR", (), JURIDISCH)


def test_debatable_telt_nergens_mee():
    uit = classificeer([_g(klasse=T, annotation_status="debatable")], [_v(klasse=RO)], [_k(door="model", klasse=RO)])
    assert uit.fouten == [] and uit.debatable == 1 and uit.correct == 0
    t = tel([uit])
    assert t["debatable"] == 1 and t["primair"] == {} and t["correct"] == 0


def test_handmatige_correctie_uit_de_checklist():
    uit = classificeer([_g(20, 30)], [], [], correcties={"G1": {"primair": "PARSER_ERROR",
                                                                "secundair": ["DETECTOR_ERROR"]}})
    f = uit.fouten[0]
    assert (f.primair, f.secundair, f.soort, f.handmatig) == ("PARSER_ERROR", ("DETECTOR_ERROR",), TECHNISCH, True)
    assert tel([uit])["handmatig"] == 1
    for fout in ("SPAN_TOO_WIDE", "FRAME_ERROR", "GEEN_CODE"):
        with pytest.raises(ValueError):
            pas_toe(f, {"primair": fout})


def test_elke_code_heeft_laag_en_soort_zoals_het_ontwerp():
    assert len(CODES) == 29
    assert ALLEEN_SECUNDAIR <= set(CODES)
    assert {c for c, (_, s) in CODES.items() if s == "evaluatie"} == {"REFERENCE_ERROR", "MATCHING_ERROR"}
