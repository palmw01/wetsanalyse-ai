"""Offset-metrieken en referentiestatus (ADR-001 PR 5b, §13)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.metrieken import (
    GEEN, Ref, classificatie_metrieken, controleer_status, kandidaat_metrieken, kern, laagste_status,
    recall_naam,
)

ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "docs" / "wetsanalyse" / "referentieset" / "cases.json"
GOLDEN = Path(__file__).resolve().parents[1] / "eval" / "golden_annotatie.jsonl"

T, V, P = "Tijdsaanduiding", "Voorwaarde", "Parameter en parameterwaarde"


def test_elke_referentie_heeft_een_geldige_status_en_niets_heet_gold_zonder_adjudicatie():
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    golden = [json.loads(r) for r in GOLDEN.read_text(encoding="utf-8").splitlines() if r.strip()]
    statussen = [controleer_status(c) for c in cases] + [controleer_status(g) for g in golden]
    assert set(statussen) <= {"provisional", "silver", "synthetic"}, "nieuwe status? Leg de adjudicatie vast"
    assert not any("status" in c or "referentie_goedgekeurd" in c for c in cases), "één statusveld"


def test_gold_zonder_adjudicatierecord_wordt_geweigerd():
    with pytest.raises(ValueError):
        controleer_status({"referentie_status": "gold"})
    with pytest.raises(ValueError):
        controleer_status({"referentie_status": "adjudicated", "adjudicatie": {"beoordelaars": ["a"]}})
    with pytest.raises(ValueError):
        controleer_status({"referentie_status": "goud"})
    assert controleer_status({"referentie_status": "gold", "adjudicatie": {
        "beoordelaars": ["a", "b"], "datum": "2026-10-01", "procedure": "dubbel + adjudicatie"}}) == "gold"


def test_recall_heet_alleen_annotation_recall_tegen_gevalideerde_referenties():
    assert recall_naam("provisional") == recall_naam("silver") == "ankerdekking"
    assert recall_naam("adjudicated") == recall_naam("gold") == "annotation_recall"
    assert laagste_status(["gold", "silver", "adjudicated"]) == "silver"


def test_kern_stript_alleen_rand():
    tekst = "Indien x, dan y."
    assert kern(tekst, 0, 10) == (0, 8)


def test_kandidaat_metrieken():
    ref = [Ref("c", 0, 5, T), Ref("c", 10, 20, V), Ref("c", 30, 35, P)]
    kand = [
        {"bron": "c", "start": 0, "eind": 5, "possible_classes": [T, P], "detectors": ["temporeel"]},
        {"bron": "c", "start": 10, "eind": 20, "possible_classes": [T], "detectors": ["temporeel", "cond"]},
        {"bron": "c", "start": 40, "eind": 45, "possible_classes": [P], "detectors": ["numeriek"]},
    ]
    m = kandidaat_metrieken(kand, ref, "provisional")
    assert m["candidate_recall"] == pytest.approx(2 / 3)
    assert m["candidate_recall_met_klasse"] == pytest.approx(1 / 3)   # V staat niet in possible_classes
    assert m["candidate_precision"] == pytest.approx(2 / 3)
    assert m["kandidaten_per_referentie"] == 1.0
    assert m["unieke_bijdrage_per_detector"] == {"temporeel": 1}
    assert m["per_klasse"][P]["candidate_recall"] == 0.0


def test_classificatie_metrieken_en_confusion():
    ref = [Ref("c", 0, 5, T), Ref("c", 10, 20, V), Ref("c", 30, 35, P), Ref("c", 30, 35, T)]
    vs = [Ref("c", 0, 5, T), Ref("c", 10, 20, T), Ref("c", 30, 35, P), Ref("c", 50, 55, V),
          Ref("c", 11, 19, V)]
    m = classificatie_metrieken(vs, ref, "provisional")
    assert m["recall_naam"] == "ankerdekking"
    assert m["confusion"][f"{V} → {T}"] == 1
    assert m["confusion"][f"{T} → {GEEN}"] == 1                     # tweede klasse op 30-35 gemist
    assert m["confusion"][f"{GEEN} → {V}"] == 2                     # 50-55 en 11-19 staan niet in de ref
    assert m["per_klasse"][P] == {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 1, "fp": 0, "fn": 0}
    assert m["per_klasse"][T]["tp"] == 1 and m["per_klasse"][T]["fp"] == 1 and m["per_klasse"][T]["fn"] == 1
    assert m["micro"]["precision"] == pytest.approx(2 / 5)
    assert m["exact_span"] == 1.0                                   # alle drie de ref-posities geraakt
    # V op 10-20 gemist maar 11-19 met dezelfde klasse overlapt: diagnose, geen match.
    assert m["partial_overlap_zelfde_klasse"] == pytest.approx(1 / 2)


def test_niets_te_meten_is_geen_gratis_een():
    m = classificatie_metrieken([], [], "silver")
    assert m["micro"]["precision"] is None and m["macro_f1"] is None and m["exact_span"] is None
    assert kandidaat_metrieken([], [], "silver")["candidate_recall"] is None


def test_elke_referentiemarkering_is_letterlijk_en_ligt_op_woordgrenzen():
    """Een offset midden in een woord telt een correcte keten als fout. Gevonden in de A/B van
    25 sep 2026: 'voetgangers' wees in RVV01–03 naar het begin van 'voetgangerslichten'."""
    import re
    woord = re.compile(r"\w")
    for c in json.loads(CASES.read_text(encoding="utf-8")):
        t = c["tekst"]
        for a in c["annotaties"]:
            s, e = a["start"], a["end"]
            assert t[s:e] == a["tekst"], (c["id"], a["id"])
            assert not (s > 0 and woord.match(t[s - 1]) and woord.match(t[s])), (c["id"], a["id"], "begin")
            assert not (e < len(t) and woord.match(t[e]) and woord.match(t[e - 1])), (c["id"], a["id"], "eind")
