"""Fase 0 — unit-tests voor de nieuwe annotatie-scorers.

Dekt:
  - _token_iou            : degenerate + normale gevallen
  - _koppel               : alle drie matchingspassen, one-to-one garantie
  - span_exact_match      : alleen span-niveau, ongeacht klasse
  - span_iou              : gemiddelde IoU inclusief ongematchte voorstellen
  - classification_accuracy : alleen over exact-span-matches, None bij geen data
  - candidate_recall      : span-dekking, klasseloos
  - verworpen_per_100     : aandeel hallucinaties
"""
from __future__ import annotations

import pytest

from eval.scoring import (
    _koppel,
    _token_iou,
    candidate_recall,
    classification_accuracy,
    span_exact_match,
    span_iou,
    verworpen_per_100,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _e(tekst: str, klasse: str = "Rechtssubject") -> dict:
    return {"tekst": tekst, "klasse": klasse}


def _g(tekst: str, klasse: str = "Rechtssubject") -> dict:
    """Gold-element (zelfde structuur als element)."""
    return {"tekst": tekst, "klasse": klasse}


# ---------------------------------------------------------------------------
# _token_iou
# ---------------------------------------------------------------------------

class TestTokenIou:
    def test_identiek(self):
        assert _token_iou("de belastingschuldige", "de belastingschuldige") == 1.0

    def test_deelverzameling(self):
        # {"de", "belasting"} ∩ {"de", "belasting", "schuldig"} = {"de","belasting"}, union=3
        iou = _token_iou("de belasting", "de belasting schuldig")
        assert abs(iou - 2/3) < 1e-9

    def test_geen_overlap(self):
        assert _token_iou("alfa", "beta") == 0.0

    def test_beide_leeg(self):
        assert _token_iou("", "") == 1.0

    def test_een_leeg(self):
        assert _token_iou("iets", "") == 0.0
        assert _token_iou("", "iets") == 0.0

    def test_case_insensitive(self):
        assert _token_iou("De Belasting", "de belasting") == 1.0


# ---------------------------------------------------------------------------
# _koppel — matching-volgorde
# ---------------------------------------------------------------------------

class TestKoppel:
    def test_exact_span_exact_klasse(self):
        v = [_e("de belastingschuldige", "Rechtssubject")]
        g = [_g("de belastingschuldige", "Rechtssubject")]
        paren = _koppel(v, g)
        assert len(paren) == 1
        voorstel, gold = paren[0]
        assert gold is not None
        assert gold["klasse"] == "Rechtssubject"

    def test_exact_span_verkeerde_klasse_pas2(self):
        """Pas 2: span matcht exact, klasse verschilt."""
        v = [_e("de belastingschuldige", "Rechtsobject")]
        g = [_g("de belastingschuldige", "Rechtssubject")]
        paren = _koppel(v, g)
        _, gold = paren[0]
        assert gold is not None  # span matcht, dus gekoppeld
        assert gold["klasse"] == "Rechtssubject"

    def test_iou_pas3(self):
        """Pas 3: geen exacte match, hoogste IoU wint."""
        v = [_e("de belastingschuldige moet")]          # extra token
        g = [_g("de belastingschuldige")]
        paren = _koppel(v, g)
        _, gold = paren[0]
        assert gold is not None

    def test_one_to_one(self):
        """Eén gold-element kan maar één keer gekoppeld worden."""
        v = [
            _e("de belastingschuldige", "Rechtssubject"),
            _e("de belastingschuldige", "Rechtsobject"),  # zelfde span, andere klasse
        ]
        g = [_g("de belastingschuldige", "Rechtssubject")]
        paren = _koppel(v, g)
        assert len(paren) == 2
        gekoppeld = [gold for _, gold in paren if gold is not None]
        assert len(gekoppeld) == 1, "gold mag maar één keer gekoppeld worden"

    def test_geen_gold(self):
        v = [_e("de belastingschuldige")]
        paren = _koppel(v, [])
        assert paren[0][1] is None

    def test_leeg(self):
        assert _koppel([], []) == []
        assert _koppel([], [_g("x")]) == []


# ---------------------------------------------------------------------------
# span_exact_match
# ---------------------------------------------------------------------------

class TestSpanExactMatch:
    def test_alles_exact(self):
        v = [_e("de belastingschuldige"), _e("de aangifte", "Rechtsobject")]
        g = [_g("de belastingschuldige"), _g("de aangifte", "Rechtsobject")]
        assert span_exact_match(v, g) == 1.0

    def test_span_mismatch_klasse_correct(self):
        """Span iets anders → geen exact match, ongeacht klasse."""
        v = [_e("de belastingschuldige moet", "Rechtssubject")]
        g = [_g("de belastingschuldige", "Rechtssubject")]
        score = span_exact_match(v, g)
        assert score == 0.0

    def test_leeg_voorgesteld(self):
        assert span_exact_match([], [_g("x")]) == 1.0

    def test_extra_voorstel_drukt_score(self):
        """Twee voorstellen, één correct → 0.5."""
        v = [_e("de belastingschuldige"), _e("onzin")]
        g = [_g("de belastingschuldige")]
        assert span_exact_match(v, g) == 0.5

    def test_normalisatie_witruimte(self):
        """Extra spaties in voorstel mogen score niet breken."""
        v = [_e("de  belastingschuldige")]   # dubbele spatie
        g = [_g("de belastingschuldige")]
        assert span_exact_match(v, g) == 1.0


# ---------------------------------------------------------------------------
# span_iou
# ---------------------------------------------------------------------------

class TestSpanIou:
    def test_perfect(self):
        v = [_e("de belastingschuldige")]
        g = [_g("de belastingschuldige")]
        assert span_iou(v, g) == 1.0

    def test_geen_overlap_geeft_nul(self):
        v = [_e("alfa")]
        g = [_g("beta")]
        assert span_iou(v, g) == 0.0

    def test_ongematch_voorstel_draagt_nul_bij(self):
        """Voorstel zonder gold-partner geeft 0.0 bijdrage — conservatieve schatting."""
        v = [_e("de belastingschuldige"), _e("geheel irrelevant")]
        g = [_g("de belastingschuldige")]
        score = span_iou(v, g)
        # Eerste paar: IoU=1.0, tweede paar: IoU=0.0, gemiddelde over 2 = 0.5
        assert abs(score - 0.5) < 1e-9

    def test_leeg(self):
        assert span_iou([], []) == 1.0
        assert span_iou([], [_g("x")]) == 1.0


# ---------------------------------------------------------------------------
# classification_accuracy
# ---------------------------------------------------------------------------

class TestClassificationAccuracy:
    def test_alles_correct(self):
        v = [_e("de belastingschuldige", "Rechtssubject")]
        g = [_g("de belastingschuldige", "Rechtssubject")]
        assert classification_accuracy(v, g) == 1.0

    def test_span_correct_klasse_fout(self):
        v = [_e("de belastingschuldige", "Rechtsobject")]
        g = [_g("de belastingschuldige", "Rechtssubject")]
        assert classification_accuracy(v, g) == 0.0

    def test_geen_exact_spans_geeft_none(self):
        """Geen enkel exact-span-match → None (niet 0.0)."""
        v = [_e("de belastingschuldige moet")]   # span wijkt af
        g = [_g("de belastingschuldige")]
        assert classification_accuracy(v, g) is None

    def test_gemengd(self):
        """Twee exact-spans: één klasse correct, één fout → 0.5."""
        v = [
            _e("de belastingschuldige", "Rechtssubject"),
            _e("de aangifte", "Rechtssubject"),        # fout: hoort Rechtsobject
        ]
        g = [
            _g("de belastingschuldige", "Rechtssubject"),
            _g("de aangifte", "Rechtsobject"),
        ]
        acc = classification_accuracy(v, g)
        assert acc is not None
        assert abs(acc - 0.5) < 1e-9

    def test_leeg(self):
        assert classification_accuracy([], []) is None


# ---------------------------------------------------------------------------
# candidate_recall
# ---------------------------------------------------------------------------

class TestCandidateRecall:
    def test_perfect(self):
        kand = [{"tekst": "de belastingschuldige"}, {"tekst": "de aangifte"}]
        gold = [_g("de belastingschuldige"), _g("de aangifte")]
        assert candidate_recall(kand, gold) == 1.0

    def test_een_gemist(self):
        kand = [{"tekst": "de belastingschuldige"}]
        gold = [_g("de belastingschuldige"), _g("de aangifte")]
        assert candidate_recall(kand, gold) == 0.5

    def test_geen_gold(self):
        assert candidate_recall([{"tekst": "x"}], []) == 1.0

    def test_kandidaten_zonder_klasse(self):
        """Kandidaten hoeven geen klasse-veld te hebben."""
        kand = [{"span": "de belastingschuldige"}]     # fase 2A-formaat
        gold = [_g("de belastingschuldige")]
        assert candidate_recall(kand, gold) == 1.0

    def test_normalisatie(self):
        kand = [{"tekst": "De  Belastingschuldige"}]   # extra spatie, hoofdletter
        gold = [_g("de belastingschuldige")]
        assert candidate_recall(kand, gold) == 1.0

    def test_partial_span_telt_niet(self):
        """Partiële overlap is geen hit — exacte span vereist."""
        kand = [{"tekst": "de belastingschuldige moet"}]
        gold = [_g("de belastingschuldige")]
        assert candidate_recall(kand, gold) == 0.0


# ---------------------------------------------------------------------------
# verworpen_per_100
# ---------------------------------------------------------------------------

class TestVerworpenPer100:
    def test_geen_verworpen(self):
        elementen = [_e("x"), _e("y")]
        assert verworpen_per_100(elementen, []) == 0.0

    def test_helft_verworpen(self):
        elementen = [_e("x")]
        verworpen = [{"tekst": "y", "klasse": "Rechtssubject", "reden": "niet_letterlijk"}]
        assert verworpen_per_100(elementen, verworpen) == 50.0

    def test_alles_verworpen(self):
        verworpen = [{"tekst": "x", "klasse": "Rechtssubject", "reden": "ongeldige_klasse"}]
        assert verworpen_per_100([], verworpen) == 100.0

    def test_leeg(self):
        assert verworpen_per_100([], []) == 0.0
