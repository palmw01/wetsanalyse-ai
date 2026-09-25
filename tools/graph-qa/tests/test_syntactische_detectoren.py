"""Syntactische en structurele detectoren (ADR-001 PR 7)."""
from __future__ import annotations

import pytest

from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles, kandidaten_van
from agent.jas_pipeline.detectoren.structuur import BetekenisDetector
from agent.jas_pipeline.detectoren.syntactisch import (
    BijzinDetector, LogischeOperatorDetector, NaamwoordgroepDetector, NominalisatieDetector, NormDetector,
)
from agent.jas_pipeline.taal import NullProvider, SpacyProvider


@pytest.fixture(scope="module")
def parser():
    p = SpacyProvider("nl_core_news_md")
    if p.analyseer("x").gedegradeerd:
        pytest.skip("nl_core_news_md niet geïnstalleerd (uv sync --extra nlp)")
    return p


def _bron(tekst, parser=None, **kw):
    return BronTekst.van_tekst("urn:test", tekst, analyse=parser.analyseer(tekst) if parser else None, **kw)


def _grenzen(kandidaten):
    return {k.span.tekst for k in kandidaten} | {o.span.tekst for k in kandidaten for o in k.span_options}


# --- geen stille terugval ----------------------------------------------------------------------

@pytest.mark.parametrize("detector", [NaamwoordgroepDetector(), BijzinDetector(), NominalisatieDetector(),
                                      LogischeOperatorDetector()], ids=lambda d: d.naam)
def test_zonder_parse_slaat_een_parsedetector_zich_zichtbaar_over(detector):
    for bron in (_bron("De inspecteur stelt de aanslag vast."),
                 BronTekst.van_tekst("urn:test", "x", analyse=NullProvider().analyseer("x"))):
        r = detector.detecteer(bron)
        assert r.overgeslagen and r.reden and r.kandidaten == ()


def test_norm_werkt_ook_zonder_parse_en_neemt_het_normsegment():
    tekst = "Bij voetgangerslichten betekent:\nc. rood licht: voetgangers mogen niet meer beginnen over te steken; reeds overstekende voetgangers moeten doorlopen."
    ks = NormDetector().detecteer(_bron(tekst)).kandidaten
    assert [k.span.tekst for k in ks] == ["voetgangers mogen niet meer beginnen over te steken;",
                                          "reeds overstekende voetgangers moeten doorlopen."]
    assert ks[0].possible_classes[0] == "Rechtsbetrekking"


def test_norm_herkent_normatief_adjectief_en_vaste_uitdrukking():
    ks = NormDetector().detecteer(_bron("Een belastingaanslag is invorderbaar zes weken na de dagtekening.")).kandidaten
    assert ks[0].evidence[0].regel == "jas.betrekking.normatief_adjectief"
    ks = NormDetector().detecteer(_bron("De verzekerde heeft aanspraak op een zorgtoeslag.")).kandidaten
    assert ks[0].evidence[0].regel == "jas.betrekking.vaste_uitdrukking"


def test_delegatieformule_is_geen_rechtsbetrekking():
    assert NormDetector().detecteer(_bron("Bij regeling van Onze Minister kunnen nadere regels worden gesteld.")).kandidaten == ()


# --- met parse -------------------------------------------------------------------------------

def test_naamwoordgroep_biedt_kern_en_volle_groep(parser):
    ks = NaamwoordgroepDetector().detecteer(_bron("De verzekerde met een partner heeft aanspraak op een zorgtoeslag.", parser)).kandidaten
    assert {"De verzekerde", "een zorgtoeslag"} <= _grenzen(ks)
    assert "De verzekerde met een partner" in _grenzen(ks)


def test_naamwoordgroep_in_een_verwijzing_is_geen_kandidaat(parser):
    ks = NaamwoordgroepDetector().detecteer(_bron("Het bepaalde in artikel 9, derde lid, is van toepassing.", parser)).kandidaten
    assert not any("lid" == k.span.tekst.split()[-1] for k in ks)


def test_als_bijzin_is_voorwaarde_maar_als_bedoeld_in_niet(parser):
    ks = BijzinDetector().detecteer(_bron("Als de aanvrager niet tijdig betaalt, vervalt het recht.", parser)).kandidaten
    assert any(k.span.tekst.startswith("Als de aanvrager") and "Voorwaarde" in k.possible_classes for k in ks)
    ks = BijzinDetector().detecteer(_bron("De aanslag als bedoeld in artikel 9 is invorderbaar.", parser)).kandidaten
    assert not any(e.regel == "jas.voorwaarde.als_bijzin" for k in ks for e in k.evidence)


def test_beperkende_relatieve_bijzin(parser):
    ks = BijzinDetector().detecteer(_bron("Voor een partner die geen verzekerde is, geldt dit niet.", parser)).kandidaten
    assert "een partner die geen verzekerde is" in _grenzen(ks)


def test_nominalisatie_is_kandidaat_rechtsfeit(parser):
    ks = NominalisatieDetector().detecteer(_bron("Na het indienen van een bezwaarschrift beslist de inspecteur.", parser)).kandidaten
    assert any("indienen van een bezwaarschrift" in k.span.tekst and k.possible_classes[0] == "Rechtsfeit" for k in ks)


def test_en_tussen_clauses_is_operator_maar_niet_binnen_een_opsomming_van_objecten(parser):
    ks = LogischeOperatorDetector().detecteer(_bron("De inspecteur stelt de aanslag vast en hij verzendt het aanslagbiljet.", parser)).kandidaten
    assert [k.span.tekst for k in ks] == ["en"]
    ks = LogischeOperatorDetector().detecteer(_bron("Hij betaalt de loonbelasting en de omzetbelasting.", parser)).kandidaten
    assert ks == ()


# --- structuur: betekenisregel ------------------------------------------------------------------

def test_betekenisregel_levert_de_term_als_kandidaat_voorwaarde():
    ks = BetekenisDetector().detecteer(_bron("Bij voetgangerslichten betekent:\na. groen licht: voetgangers mogen oversteken;")).kandidaten
    assert [k.span.tekst for k in ks] == ["groen licht"] and ks[0].possible_classes[0] == "Voorwaarde"
    ks = BetekenisDetector().detecteer(_bron("Geel knipperlicht betekent: gevaarlijk punt;")).kandidaten
    assert [k.span.tekst for k in ks] == ["Geel knipperlicht"]


def test_de_aanhef_zelf_is_geen_betekenisterm():
    assert BetekenisDetector().detecteer(_bron("Bij voetgangerslichten betekent:")).kandidaten == ()


# --- de hele laag ---------------------------------------------------------------------------

def test_detectie_met_parse_is_deterministisch(parser):
    tekst = "Indien de verzekerde niet binnen zes weken betaalt, is hij een boete van € 23 verschuldigd."
    assert detecteer_alles(_bron(tekst, parser)) == detecteer_alles(_bron(tekst, parser))


def test_ankerdekking_zakt_niet_onder_de_gemeten_vloer(parser):
    """Regressievloer, geen doel: 86% gemeten op 24 sep 2026 (provisional, ontwikkelsplit)."""
    from eval.kandidaat_eval import meet
    m = meet()
    assert m["candidate_recall"] >= 0.80, m["per_klasse"]
    assert m["kandidaten_per_referentie"] <= 5.0, "kandidaatexplosie"


def test_of_binnen_een_naamwoordgroep_is_geen_operator(parser):
    """PR 17 (Operator-F1 26% in de A/B): 'verplichting of onthouden aanspraak' verbindt woorden, geen zinsdelen."""
    t = "een door een bestuursorgaan wegens een overtreding opgelegde verplichting of onthouden aanspraak;"
    assert LogischeOperatorDetector().detecteer(_bron(t, parser)).kandidaten == ()
