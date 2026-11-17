"""Tegenfeitelijke meting mag syntactische dekking niet als juridische dekking tellen."""
from agent.jas_pipeline.detectoren import BronTekst
from agent.jas_pipeline.kandidaten import Candidate, DetectorResult, Evidence
from eval.detector_audit import scenario, samenvatting


def test_np_neutraliseren_verwijdert_geen_span_en_generiek_blokkeert_sterk_niet():
    bron = BronTekst.van_tekst("test", "zes weken auto")
    tijd = Candidate.maak(bron.span(0, 9), ["Tijdsaanduiding"],
                          [Evidence(detector="tijd", code="TEMPORAL_DURATION")])
    def np(s, e):
        return Candidate.maak(bron.span(s, e), ["Rechtsobject", "Rechtssubject", "Variabele en variabelewaarde"],
                              [Evidence(detector="naamwoordgroep", code="OBJECT_NP")])
    rs = [DetectorResult(detector="tijd", versie="1", bron_iri="test", kandidaten=(tijd,)),
          DetectorResult(detector="naamwoordgroep", versie="1", bron_iri="test", kandidaten=(np(0, 9), np(10, 14)))]
    s0, s1, s2 = (scenario(rs, s) for s in ("S0", "S1", "S2"))
    assert len(s0) == len(s1) == 2 and len(s2) == 1
    assert s1[0]["possible_classes"] == ["Tijdsaanduiding"]
    # Sinds audit D05 is OBJECT_NP generiek: het blokkeert sterk tijdbewijs niet meer (S0 en S1).
    assert s0[0]["route"] == s1[0]["route"] == "regel"
    assert s1[1]["possible_classes"] == [] and s1[1]["route"] == "zonder_hypothese"
    assert s2[0]["route"] == "regel"
    refs = [{"id": "test/a", "bron": "test", "start": 10, "eind": 14, "klasse": "Rechtsobject"}]
    m = samenvatting(s1, refs, {"test": bron.tekst})
    assert m["ankers_core"] == 1 and m["ankers_met_klasse"] == 0
    assert m["zonder_hypothese"] == 1 and m["classifier_kandidaten"] == 0


def test_ankerbijdrage_onderscheidt_herhaalde_tekst_op_andere_offsets():
    refs = [{"id": "a/1", "bron": "a", "start": 0, "eind": 4, "klasse": "Rechtsobject"},
            {"id": "a/2", "bron": "a", "start": 5, "eind": 9, "klasse": "Rechtsobject"}]
    r = {"id": "K1", "bron": "a", "start": 0, "eind": 4, "possible_classes": ["Rechtsobject"],
         "opties": [], "route": "model", "bewijs": []}
    m = samenvatting([r], refs, {"a": "auto auto"})
    assert m["ankers_core"] == m["ankers_met_klasse"] == 1
    assert m["gedekte_ankers"] == ["a/1"]
