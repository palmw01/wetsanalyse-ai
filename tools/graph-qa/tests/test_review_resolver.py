"""Onzekerheid, gerichte reviewer en resolver (ADR-001 PR 12-13): elke transitie uit de tabel."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from bronmodel import Span, tekst_hash

from agent.jas_pipeline.besluit import Beslissing
from agent.jas_pipeline.kandidaten import Candidate, CandidateStatus, Evidence
from agent.jas_pipeline.onzekerheid import REVIEWBAAR, Twijfel, signaleer
from agent.jas_pipeline.resolver import TABEL, los_op
from agent.jas_pipeline.review import ACTIES, TOOL, Oordeel, beoordeel, valideer
from agent.jas_pipeline.validatie import Bevinding

T, P, F, V = "Tijdsaanduiding", "Parameter en parameterwaarde", "Rechtsfeit", "Voorwaarde"
TEKST = "zes weken na de dagtekening"


def _k(label, klassen, code="NOUN_PHRASE", start=0, eind=9):
    k = Candidate.maak(Span("urn:t", start, eind, TEKST[start:eind], tekst_hash(TEKST)), klassen,
                       [Evidence(detector="d", code=code)])
    return k.model_copy(update={"label": label})


def _b(k, status=CandidateStatus.ACCEPTED, klasse="", door="model"):
    return Beslissing(kandidaat_id=k.id, label=k.label, status=status, klasse=klasse, door=door)


def _v(k, klasse):
    return {"id": f"{k.label}-{klasse}", "klasse": klasse, "tekst": k.span.tekst, "alternatieven": [],
            "aandacht": "", "critic": "", "_label": k.label,
            "ankers": [{"bron_iri": "urn:t", "start": k.span.start, "eind": k.span.eind}]}


def _maak(k, b):
    return _v(k, b.klasse)


def _los(voorstellen, beslissingen, twijfels, oordelen, ks):
    return los_op(voorstellen, beslissingen, twijfels, oordelen, {k.label: k for k in ks}, _maak)


def test_de_tabel_dekt_elke_reviewbare_reden_en_actie():
    assert {(r, a) for r in REVIEWBAAR for a in ACTIES} <= set(TABEL)
    assert ("DEGRADED_PARSE", "-") in TABEL
    assert "rood" not in str(TABEL)


def test_signaleer_ziet_een_detectieconflict_en_een_abstain():
    k1, k2 = _k("C001", [T, F], code="TEMPORAL_DURATION"), _k("C002", [V], start=13, eind=27)
    ks = {k1.id: k1, k2.id: k2}
    tw = signaleer(ks, [_b(k1, klasse=F), _b(k2, CandidateStatus.UNCERTAIN)], [], set())
    assert [(t.label, t.reden, t.huidig, t.alternatieven) for t in tw] == [
        ("C001", "DETECTOR_CONFLICT", F, (T,)), ("C002", "CLASSIFIER_ABSTAIN", "", (V,))]


def test_regelbesluit_en_eensgezind_model_zijn_geen_twijfel():
    k = _k("C001", [T], code="TEMPORAL_DURATION")
    assert signaleer({k.id: k}, [_b(k, klasse=T)], [], set()) == []
    assert signaleer({k.id: k}, [_b(k, klasse=T, door="regel")], [], {"urn:t"}) == []


def test_conflict_keep_blijft_een_conflict_en_gaat_naar_de_jurist():
    k = _k("C001", [T, F], code="TEMPORAL_DURATION")
    tw = Twijfel(label="C001", reden="DETECTOR_CONFLICT", huidig=F, alternatieven=(T,))
    [v], [b], [tr] = _los([_v(k, F)], [_b(k, klasse=F)], [tw], [Oordeel(label="C001", actie="KEEP")], [k])
    assert (v["aandacht"], [a["klasse"] for a in v["alternatieven"]]) == ("geel", [T])
    assert b.status is CandidateStatus.HUMAN_REVIEW and tr.regel == "R-CONFLICT-KEEP"


def test_conflict_change_volgt_het_bewijs_met_de_oude_lezing_als_alternatief():
    k = _k("C001", [T, F], code="TEMPORAL_DURATION")
    tw = Twijfel(label="C001", reden="DETECTOR_CONFLICT", huidig=F, alternatieven=(T,))
    [v], [b], [tr] = _los([_v(k, F)], [_b(k, klasse=F)], [tw], [Oordeel(label="C001", actie="CHANGE", klasse=T)], [k])
    assert (v["klasse"], v["aandacht"], [a["klasse"] for a in v["alternatieven"]]) == (T, "groen", [F])
    assert b.status is CandidateStatus.ACCEPTED and b.klasse == T and tr.regel == "R-CONFLICT-CHANGE"


def test_een_change_tegen_een_jas_voorrangsregel_wordt_niet_uitgevoerd():
    k = _k("C001", [T, P], code="TEMPORAL_DURATION")
    tw = Twijfel(label="C001", reden="ZELFDE_SPAN", huidig=T, alternatieven=(P,))
    vs = [_v(k, T), {**_v(k, P), "id": "x"}]
    uit, [b], [tr] = _los(vs, [_b(k, klasse=T)], [tw], [Oordeel(label="C001", actie="CHANGE", klasse=P)], [k])
    assert tr.regel == "R-PRIORITEIT:JAS-PRIORITY-001"
    assert {v["klasse"] for v in uit} == {T, P} and all(v["aandacht"] == "geel" for v in uit)


def test_abstain_change_maakt_het_voorstel_van_de_reviewer():
    k = _k("C001", [V, F])
    tw = Twijfel(label="C001", reden="CLASSIFIER_ABSTAIN", alternatieven=(V, F))
    [v], [b], _ = _los([], [_b(k, CandidateStatus.UNCERTAIN)], [tw], [Oordeel(label="C001", actie="CHANGE", klasse=F)], [k])
    assert (v["klasse"], v["aandacht"], b.status) == (F, "groen", CandidateStatus.ACCEPTED)


def test_abstain_human_legt_alle_klassen_voor():
    k = _k("C001", [V, F])
    tw = Twijfel(label="C001", reden="CLASSIFIER_ABSTAIN", alternatieven=(V, F))
    [v], [b], _ = _los([], [_b(k, CandidateStatus.UNCERTAIN)], [tw], [Oordeel(label="C001", actie="HUMAN_REVIEW")], [k])
    assert v["aandacht"] == "geel" and [a["klasse"] for a in v["alternatieven"]] == [F]
    assert b.status is CandidateStatus.HUMAN_REVIEW


def test_zelfde_span_change_houdt_een_functie_en_wijst_de_ander_af():
    k1, k2 = _k("C001", [V, F]), _k("C002", [F, V])
    tw = Twijfel(label="C001", reden="ZELFDE_SPAN", huidig=V, alternatieven=(F,))
    uit, bs, [tr] = _los([_v(k1, V), _v(k2, F)], [_b(k1, klasse=V), _b(k2, klasse=F)], [tw],
                         [Oordeel(label="C001", actie="CHANGE", klasse=F)], [k1, k2])
    assert [(v["klasse"], [a["klasse"] for a in v["alternatieven"]]) for v in uit] == [(F, [V])]
    assert {b.label: b.status for b in bs} == {"C001": CandidateStatus.REJECTED, "C002": CandidateStatus.ACCEPTED}


def test_zelfde_span_keep_laat_beide_functies_staan():
    k1, k2 = _k("C001", [V, F]), _k("C002", [F, V])
    tw = Twijfel(label="C001", reden="ZELFDE_SPAN", huidig=V, alternatieven=(F,))
    uit, _, _ = _los([_v(k1, V), _v(k2, F)], [_b(k1, klasse=V), _b(k2, klasse=F)], [tw],
                     [Oordeel(label="C001", actie="KEEP")], [k1, k2])
    assert sorted((v["klasse"], v["aandacht"]) for v in uit) == [(F, "groen"), (V, "groen")]


def test_gedegradeerd_gaat_zonder_reviewer_naar_de_jurist():
    k = _k("C001", [V, F])
    tw = Twijfel(label="C001", reden="DEGRADED_PARSE", huidig=V, alternatieven=(F,))
    [v], [b], [tr] = _los([_v(k, V)], [_b(k, klasse=V)], [tw], [], [k])
    assert v["aandacht"] == "geel" and b.status is CandidateStatus.HUMAN_REVIEW and tr.regel == "R-DEGRADED"


# --- de reviewer --------------------------------------------------------------------------------

def test_reviewer_ziet_alleen_de_twijfelgevallen_en_kan_niets_buiten_zijn_geval():
    k1, k2 = _k("C001", [T, F], code="TEMPORAL_DURATION"), _k("C002", [V], start=13, eind=27)
    tw = [Twijfel(label="C001", reden="DETECTOR_CONFLICT", huidig=F, alternatieven=(T,))]
    calls = []

    class LLM:
        def create(self, **kw):
            calls.append(kw)
            return SimpleNamespace(stop_reason="tool_use", content=[SimpleNamespace(
                type="tool_use", name=TOOL, input={"oordelen": [
                    {"geval": "C001", "actie": "CHANGE", "klasse": T},
                    {"geval": "C002", "actie": "CHANGE", "klasse": F}]})])
    [o] = beoordeel(LLM(), "m", tw, {"C001": k1, "C002": k2}, TEKST)
    assert (o.label, o.actie, o.klasse) == ("C001", "CHANGE", T)
    prompt = calls[0]["messages"][0]["content"]
    assert "C001" in prompt and "C002" not in prompt
    schema = calls[0]["tools"][0]
    assert schema["strict"] and schema["input_schema"]["properties"]["oordelen"]["items"]["properties"]["geval"]["enum"] == ["C001"]


@pytest.mark.parametrize("item", [None, {"geval": "C001", "actie": "CHANGE", "klasse": P},
                                  {"geval": "C001", "actie": "SLOOP", "klasse": ""}])
def test_onbruikbaar_reviewer_oordeel_wordt_human_review(item):
    tw = [Twijfel(label="C001", reden="DETECTOR_CONFLICT", huidig=F, alternatieven=(T,))]
    [o] = valideer(tw, [item] if item else [])
    assert (o.actie, o.geldig) == ("HUMAN_REVIEW", False)


def test_zelfde_span_waarschuwing_wordt_een_twijfel():
    k = _k("C001", [V, F])
    tw = signaleer({k.id: k}, [], [Bevinding(code="W_ZELFDE_SPAN", label="C001", detail=f"{F}, {V}",
                                             ernst="waarschuwing")], set())
    assert [(t.reden, t.huidig, t.alternatieven) for t in tw] == [("ZELFDE_SPAN", F, (V,))]
