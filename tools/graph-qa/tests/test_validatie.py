"""Deterministische validatie (ADR-001 PR 11): elke structurele mutatie wordt gevangen."""
from __future__ import annotations

import copy

import pytest
from bronmodel import CorpusMap, bouw_snapshot

from agent.bron_annotatie import corpus_segmenten
from agent.jas_pipeline.besluit import Beslissing
from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
from agent.jas_pipeline.fusie import fuseer
from agent.jas_pipeline.kandidaten import CandidateStatus
from agent.jas_pipeline.keten import _voorstel
from agent.jas_pipeline.validatie import valideer

TEKST = "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet."
ROWS = [{"node": "urn:bwb:BWBR0004770", "type": "urn:bwb-ns:Regeling", "tekst": ""},
        {"node": "urn:bwb:BWBR0004770:artikel:9", "parent": "urn:bwb:BWBR0004770", "type": "urn:bwb-ns:Artikel",
         "nummer": "9", "tekst": ""},
        {"node": "urn:bwb:BWBR0004770:artikel:9:lid:1", "parent": "urn:bwb:BWBR0004770:artikel:9",
         "type": "urn:bwb-ns:Lid", "nummer": "1", "tekst": TEKST}]
PROV = {"model": "m", "classifier_prompt": "p"}


@pytest.fixture()
def opzet():
    snap = bouw_snapshot(ROWS, bwb_id="BWBR0004770", artikel="9", lid="1")
    corpus, segs = corpus_segmenten(snap["segmenten"])
    seg = snap["segmenten"][0]
    fusie = fuseer(detecteer_alles(BronTekst(seg["bron_iri"], seg["tekst"], seg["bron_hash"])))
    k = next(k for k in fusie.kandidaten if k.span.tekst.startswith("zes weken na"))
    b = Beslissing(kandidaat_id=k.id, label=k.label, status=CandidateStatus.ACCEPTED,
                   klasse="Tijdsaanduiding", door="model")
    v = _voorstel(k, b, CorpusMap(segs), corpus, "1", "BWBR0004770 art. 9 lid 1")
    return snap, fusie.per_id(), k, b, v


def _code(opzet, v=None, b=None, prov=PROV):
    snap, per_id, _k, b0, v0 = opzet
    goed, bev = valideer([(v or v0, b or b0)], per_id, snap, prov)
    fouten = [x.code for x in bev if x.ernst == "fout"]
    return fouten[0] if fouten else ("ok" if goed else "weg")


def test_een_geldig_voorstel_komt_erdoor(opzet):
    assert _code(opzet) == "ok"


@pytest.mark.parametrize("mutatie,code", [
    (lambda v: v["ankers"][0].update(tekst="zes weken"), "V_ANKER"),
    (lambda v: v["ankers"][0].update(eind=v["ankers"][0]["eind"] + 1), "V_ANKER"),
    (lambda v: v["ankers"][0].update(bron_hash="0" * 64), "V_ANKER"),
    (lambda v: v["ankers"][0].update(bron_iri="urn:bwb:BWBR0004770:artikel:9:lid:9"), "V_ANKER"),
    (lambda v: v.update(tekst="iets anders"), "V_ANKER"),
    (lambda v: v.update(klasse="Termijn"), "V_KLASSE"),
])
def test_elke_mutatie_van_het_voorstel_wordt_gevangen(opzet, mutatie, code):
    v = copy.deepcopy(opzet[4])
    mutatie(v)
    assert _code(opzet, v=v) == code


def test_een_grens_die_geen_optie_was_wordt_gevangen(opzet):
    snap, _, k, _, v = opzet
    v = copy.deepcopy(v)
    tekst = snap["segmenten"][0]["tekst"]
    s = tekst.index("weken na")
    v["ankers"] = [{**v["ankers"][0], "start": s, "eind": s + 8, "tekst": "weken na"}]
    v["tekst"] = "weken na"
    assert _code(opzet, v=v) == "V_GRENS"


def test_een_klasse_die_voor_de_kandidaat_niet_mocht(opzet):
    _, _, k, b, v = opzet
    b2 = b.model_copy(update={"klasse": "Brondefinitie"})
    v2 = {**v, "klasse": "Brondefinitie"}
    assert "Brondefinitie" not in k.possible_classes
    assert _code(opzet, v=v2, b=b2) == "V_KLASSE"


def test_status_kandidaat_en_provenance(opzet):
    _, _, _, b, _ = opzet
    assert _code(opzet, b=b.model_copy(update={"status": CandidateStatus.UNCERTAIN})) == "V_STATUS"
    assert _code(opzet, b=b.model_copy(update={"kandidaat_id": "Konbekend"})) == "V_KANDIDAAT"
    assert _code(opzet, prov={}) == "V_PROVENANCE"


def test_zelfde_span_met_twee_klassen_is_een_waarschuwing_geen_fout(opzet):
    snap, per_id, k, b, v = opzet
    per_id = {**per_id, k.id: k.model_copy(update={"possible_classes": ("Tijdsaanduiding", "Rechtsfeit")})}
    b2 = b.model_copy(update={"klasse": "Rechtsfeit"})
    v2 = {**v, "klasse": "Rechtsfeit"}
    goed, bev = valideer([(v, b), (v2, b2)], per_id, snap, PROV)
    assert len(goed) == 2 and [x.code for x in bev] == ["W_ZELFDE_SPAN"]


def test_de_keten_maakt_een_gevalideerde_fout_rejected(monkeypatch):
    """Een beslissing waarvan het voorstel de validatie niet haalt, eindigt als REJECTED met code,
    en het voorstel verlaat de keten niet."""
    from agent.jas_pipeline import keten
    from agent.jas_pipeline.validatie import Bevinding
    from test_hybride_keten import KetenLLM, _draai
    echte = keten.valideer
    rondes = []

    def met_fout(paren, *a):
        goed, bev = echte(paren, *a)
        rondes.append(1)
        if len(rondes) > 1:                  # alleen de eerste validatieronde krijgt de fout
            return goed, bev
        weg = paren[0][1].label
        return [v for v, b in paren[1:]], [*bev, Bevinding(code="V_ANKER", label=weg, detail="test")]
    monkeypatch.setattr(keten, "valideer", met_fout)
    events = _draai(KetenLLM())
    meting = next(e for e in events if e["type"] == "run")["run"]["instellingen"]["meting"]
    assert [v["code"] for v in meting["validatie"]] == ["V_ANKER"]
    assert meting["per_status"]["UNHANDLED"] == 0 and meting["per_status"]["REJECTED"] >= 1
