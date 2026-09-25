"""Dekkingsboekhouding (ADR-001 PR 10): A is een invariant, B is zichtbaar, C staat hier niet."""
from __future__ import annotations

import pytest

from agent.jas_pipeline.besluit import deterministisch, onzeker
from agent.jas_pipeline.dekking import DIMENSIES, DekkingsFout, controleer_a, ongedekt, structureel
from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles, standaard_detectoren
from agent.jas_pipeline.fusie import fuseer
from agent.jas_pipeline.taal import NullProvider, SpacyProvider

TEKST = "De ontvanger verleent binnen zes weken uitstel, indien hij daarom verzoekt. Zo is het."


def _keten(provider):
    bron = BronTekst.van_tekst("urn:t", TEKST, analyse=provider.analyseer(TEKST))
    resultaten = detecteer_alles(bron)
    return bron, resultaten, fuseer(resultaten)


def test_a_gooit_bij_een_kandidaat_zonder_beslissing():
    _, _, f = _keten(NullProvider())
    beslissingen = [deterministisch(k) or onzeker(k, "test") for k in f.kandidaten]
    telling = controleer_a(f, beslissingen)
    assert telling["UNHANDLED"] == 0 and sum(telling.values()) == len(f.kandidaten)
    with pytest.raises(DekkingsFout):
        controleer_a(f, beslissingen[1:])


def test_b_zonder_parser_zegt_welke_dimensies_niet_draaiden():
    bron, resultaten, f = _keten(NullProvider())
    b = structureel(f, [bron], {"urn:t": {r.detector for r in resultaten}})["urn:t"]["dimensies"]
    assert b["tijd"] == "uitgevoerd" and b["normatieve relatie"] == "uitgevoerd"
    assert b["object"] == "overgeslagen" and b["handeling/gebeurtenis"] == "overgeslagen"
    assert b["actor"] == "gedeeltelijk"            # het rollexicon draaide, de naamwoordgroepen niet


def test_b_met_parser_is_volledig_uitgevoerd():
    p = SpacyProvider("nl_core_news_md")
    if p.analyseer("x").gedegradeerd:
        pytest.skip("nl_core_news_md niet geïnstalleerd")
    bron, resultaten, f = _keten(p)
    b = structureel(f, [bron], {"urn:t": {r.detector for r in resultaten}})["urn:t"]["dimensies"]
    assert set(b.values()) == {"uitgevoerd"}


def test_ongedekt_noemt_zinsdelen_zonder_kandidaat():
    bron, _, f = _keten(NullProvider())
    assert [d["tekst"] for d in ongedekt(f, bron)] == ["Zo is het."]
    d, = ongedekt(f, bron)
    assert bron.tekst[d["start"]:d["eind"]] == "Zo is het."


def test_elke_detector_draagt_een_dimensie_en_elke_dimensie_bestaat():
    namen = {d.naam for d in standaard_detectoren()}
    in_dimensies = {d for ds in DIMENSIES.values() for d in ds}
    assert namen == in_dimensies, namen ^ in_dimensies
    assert len(DIMENSIES) == 12


def test_hybride_meting_draagt_a_en_b(monkeypatch):
    from test_hybride_keten import KetenLLM, _draai
    run = next(e for e in _draai(KetenLLM()) if e["type"] == "run")["run"]
    meting = run["instellingen"]["meting"]
    assert meting["per_status"]["UNHANDLED"] == 0
    assert sum(meting["per_status"].values()) == meting["kandidaten"]
    [(iri, b)] = meting["dekking"].items()
    assert iri.endswith(":lid:1") and len(b["dimensies"]) == 12
