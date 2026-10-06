"""Syntactische en structurele detectoren (ADR-001)."""
from __future__ import annotations

import pytest

from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles, kandidaten_van
from agent.jas_pipeline.detectoren.structuur import BetekenisDetector
from agent.jas_pipeline.detectoren.syntactisch import (
    BijzinDetector, GevolgDetector, LogischeOperatorDetector, NaamwoordgroepDetector, NominalisatieDetector,
    NormDetector,
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
                                      LogischeOperatorDetector(), GevolgDetector()], ids=lambda d: d.naam)
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
    """Regressievloer, geen doel: gemeten 86% (provisional, ontwikkelsplit)."""
    from eval.kandidaat_eval import meet
    m = meet()
    assert m["candidate_recall"] >= 0.80, m["per_klasse"]
    assert m["kandidaten_per_referentie"] <= 5.0, "kandidaatexplosie"


def test_of_binnen_een_naamwoordgroep_is_geen_operator(parser):
    """'verplichting of onthouden aanspraak' verbindt woorden, geen zinsdelen."""
    t = "een door een bestuursorgaan wegens een overtreding opgelegde verplichting of onthouden aanspraak;"
    assert LogischeOperatorDetector().detecteer(_bron(t, parser)).kandidaten == ()


def test_naamwoordelijk_gezegde_is_geen_naamwoordgroep(parser):
    """spaCy tagt "invorderbaar" als NOUN; zonder deze regel wordt het een OBJECT_NP-kandidaat met de
    hele zin als grens, en kiest het model Variabele."""
    tekst = "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet."
    kandidaten = NaamwoordgroepDetector().detecteer(_bron(tekst, parser)).kandidaten
    assert "invorderbaar" not in {k.span.tekst for k in kandidaten}
    assert not [o for k in kandidaten for o in k.span_options if o.span.tekst == tekst[:-1]]
    # De echte naamwoordgroepen blijven.
    assert {"Een belastingaanslag", "het aanslagbiljet"} <= _grenzen(kandidaten)


def test_gezegde_met_lidwoord_blijft_een_naamwoordgroep(parser):
    kandidaten = NaamwoordgroepDetector().detecteer(_bron("Belastingplichtige is de natuurlijke persoon.", parser)).kandidaten
    assert any("natuurlijke persoon" in g for g in _grenzen(kandidaten))


# --- gevolgdetector: een rechtsgevolg als eigen hoofdzin -------------------------------------------

def _gevolg(tekst, parser):
    return [(k.span.tekst, k.possible_classes, k.evidence[0].code)
            for k in GevolgDetector().detecteer(_bron(tekst, parser)).kandidaten]


@pytest.mark.parametrize("tekst,verwacht", [
    # positief
    ("De vordering vervalt na vijf jaar.",
     [("De vordering vervalt na vijf jaar", ("Rechtsbetrekking", "Rechtsfeit"), "LEGAL_EFFECT_CLAUSE")]),
    ("De verplichting gaat over op de erfgenamen.",
     [("De verplichting gaat over op de erfgenamen", ("Rechtsbetrekking", "Rechtsfeit"), "LEGAL_EFFECT_CLAUSE")]),
    ("Artikel 4 vindt toepassing.", [("Artikel 4 vindt toepassing", ("Rechtsbetrekking",), "APPLICABILITY_CONSEQUENCE")]),
    # negatief: in een bijzin is het een voorwaarde of beperking, geen gevolg van de bepaling
    ("Indien de vordering vervalt, betaalt de ontvanger terug.", []),
    ("De beschikking die vervalt, wordt ingetrokken.", []),
    ("Hij betaalt de boete.", []),
    # rand: ontkend of als schakelbepaling is het geen toepasselijkheidsgevolg
    ("Artikel 4 vindt geen toepassing.", []),
    ("Artikel 4 vindt overeenkomstige toepassing.", []),
    # overlap: twee nevengeschikte gevolgen zijn twee kandidaten, niet één
    ("De termijn vervalt en de schuld ontstaat.",
     [("De termijn vervalt", ("Rechtsbetrekking", "Rechtsfeit"), "LEGAL_EFFECT_CLAUSE"),
      ("de schuld ontstaat", ("Rechtsbetrekking", "Rechtsfeit"), "LEGAL_EFFECT_CLAUSE")]),
])
def test_gevolgdetector(parser, tekst, verwacht):
    assert _gevolg(tekst, parser) == verwacht


def test_gevolgclause_laat_de_voorwaarde_weg_en_biedt_segment_en_predicaat_als_optie(parser):
    tekst = "Indien de aanslag is vastgesteld, vindt het eerste lid toepassing."
    [k] = GevolgDetector().detecteer(_bron(tekst, parser)).kandidaten
    assert k.span.tekst == "vindt het eerste lid toepassing"
    assert {o.soort: o.span.tekst for o in k.span_options} == {"segment": tekst, "predicaat": "vindt"}


def test_gevolgdetector_vindt_nooit_een_predicaat_in_een_bijzin(parser):
    """Invariant over de ontwikkelcasussen: elke gevolgkandidaat hangt aan de hoofdzin."""
    from agent.jas_pipeline.detectoren.syntactisch import _in_hoofdzin
    from eval import casusbron
    for c in [*casusbron.laad(), *casusbron.laad("concept")]:
        a = parser.analyseer(c["tekst"])
        for k in GevolgDetector().detecteer(BronTekst.van_tekst(c["id"], c["tekst"], analyse=a)).kandidaten:
            koppen = [t.i for t in a.tokens if k.span.start <= t.start < k.span.eind and t.deprel in {"root", "conj", "parataxis"}]
            assert any(_in_hoofdzin(a, i) for i in koppen), (c["id"], k.span.tekst)


# --- referent: een zaak of handeling is geen rechtssubject ------------------------------------------

def test_zaak_en_rol_zijn_disjunct_ook_via_het_einde_van_het_lemma():
    from agent.jas_pipeline.detectoren.regels import woordenlijsten
    zaken = woordenlijsten()["ZAAK"].split("|")
    rollen = woordenlijsten()["ROL"].split("|")
    assert not [r for r in rollen if any(r.lower().endswith(z) for z in zaken)]


@pytest.mark.parametrize("tekst,np,met_rs", [
    ("Het aanslagbiljet vermeldt de dagtekening.", "Het aanslagbiljet", False),
    ("Een belastingaanslag is invorderbaar.", "Een belastingaanslag", False),
    ("De toepassing van het eerste lid leidt tot een bedrag.", "De toepassing", False),
    ("De belastingschuldige is verplicht te betalen.", "De belastingschuldige", True),
    ("De inspecteur is bevoegd de aanslag te verminderen.", "De inspecteur", True),
    ("Hij is verplicht de aanslag te betalen.", "Hij", True),
])
def test_referent_bepaalt_of_rechtssubject_een_hypothese_is(parser, tekst, np, met_rs):
    k = next(k for k in NaamwoordgroepDetector().detecteer(_bron(tekst, parser)).kandidaten if k.span.tekst == np)
    assert ("Rechtssubject" in k.possible_classes) is met_rs
    if not met_rs:
        assert k.evidence[0].code in {"THING_NP", "ACTION_NP"} and "Rechtsobject" in k.possible_classes


def test_beperkende_bijzin_bij_een_zaak_biedt_geen_rechtssubject_aan(parser):
    zaak = BijzinDetector().detecteer(_bron("Het aanslagbiljet dat is verzonden, is geldig.", parser)).kandidaten
    persoon = BijzinDetector().detecteer(_bron("De belanghebbende die bezwaar maakt, betaalt.", parser)).kandidaten
    assert zaak and all("Rechtssubject" not in k.possible_classes for k in zaak)
    assert all(e.regel == "jas.voorwaarde.beperkende_bijzin_bij_zaak" for k in zaak for e in k.evidence)
    assert persoon and all("Rechtssubject" in k.possible_classes for k in persoon)


def test_geen_fusiekandidaat_met_een_zaak_als_kop_krijgt_rechtssubject(parser):
    """Invariant over v1, diagnostiek en concepten: de klassenunie lekt Rechtssubject niet terug,
    tenzij een detector op dezelfde span een persoon zag."""
    import json
    from pathlib import Path

    from agent.jas_pipeline.fusie import fuseer
    from eval import casusbron
    diag = json.loads((Path(__file__).parent / "fixtures/detector_audit_diagnostiek.json").read_text())
    for c in [*casusbron.laad(), *casusbron.laad("concept"), *diag]:
        f = fuseer(detecteer_alles(_bron(c["tekst"], parser)))
        zaak = {b.kandidaat_id for b in f.bijdragen for e in b.bewijs if e.code in {"THING_NP", "ACTION_NP"}}
        persoon = {b.kandidaat_id for b in f.bijdragen for e in b.bewijs
                   if e.code in {"ROLE_NOUN", "PERSON_PRONOUN"} or e.detector == "subject"}
        for k in f.kandidaten:
            if k.id in zaak - persoon:
                assert "Rechtssubject" not in k.possible_classes, (c["id"], k.span.tekst)


# --- nominalisatie: de context bepaalt of Voorwaarde een hypothese is ----------------------------

@pytest.mark.parametrize("tekst,np,klassen,regel", [
    # referentiemoment achter een tijdvoorzetsel
    ("De termijn vervalt één maand na de dagtekening van het aanslagbiljet.", "de dagtekening van het aanslagbiljet",
     ("Rechtsfeit",), "jas.feit.nominalisatie_referentiemoment"),
    ("Sinds de bekendmaking van het besluit loopt de termijn.", "de bekendmaking van het besluit",
     ("Rechtsfeit",), "jas.feit.nominalisatie_referentiemoment"),
    # onderwerp in een voorwaardelijke bijzin
    ("Indien de toepassing van het eerste lid niet leidt tot een bedrag, vervalt de aanslag.",
     "de toepassing van het eerste lid", ("Rechtsfeit", "Rechtsobject"), "jas.feit.nominalisatie_in_voorwaarde"),
    # elders blijft Voorwaarde mogelijk ('tot' en 'voor' zijn bewust geen tijdvoorzetsel)
    ("De last is gericht op het voorkomen van herhaling van een overtreding.", "het voorkomen van herhaling",
     ("Rechtsfeit", "Voorwaarde", "Rechtsobject"), "jas.feit.nominalisatie_van"),
    ("Nadere regels worden gesteld voor de toepassing van deze wet.", "de toepassing van deze wet",
     ("Rechtsfeit", "Voorwaarde", "Rechtsobject"), "jas.feit.nominalisatie_van"),
])
def test_nominalisatiecontext(parser, tekst, np, klassen, regel):
    k = next(k for k in NominalisatieDetector().detecteer(_bron(tekst, parser)).kandidaten if k.span.tekst.startswith(np))
    assert k.possible_classes == klassen and k.evidence[0].regel == regel
