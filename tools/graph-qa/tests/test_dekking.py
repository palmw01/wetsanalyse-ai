"""Dekkingsboekhouding (ADR-001): A is een invariant, B is zichtbaar, C staat hier niet."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.jas_pipeline.besluit import deterministisch, onzeker
from agent.jas_pipeline.dekking import (
    DIMENSIES, DekkingsFout, alleen_als_geheel, controleer_a, ongedekt, structureel,
)
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
    # De normdetector is lexicaal en draaide; de gevolgdetector vraagt een parse en draaide niet.
    assert b["tijd"] == "gedeeltelijk" and b["normatieve relatie"] == "gedeeltelijk"
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


def test_aangetroffen_telt_per_dimensie_wat_er_voor_haar_klasse_gevonden_werd():
    from agent.jas_klassen import GELDIGE_JAS_KLASSEN
    from agent.jas_pipeline.dekking import DIMENSIEKLASSEN
    assert DIMENSIEKLASSEN.keys() == DIMENSIES.keys()
    assert all(k in GELDIGE_JAS_KLASSEN for ks in DIMENSIEKLASSEN.values() for k in ks)
    p = SpacyProvider("nl_core_news_md")
    if p.analyseer("x").gedegradeerd:
        pytest.skip("nl_core_news_md niet geïnstalleerd")
    bron, resultaten, f = _keten(p)
    a = structureel(f, [bron], {"urn:t": {r.detector for r in resultaten}})["urn:t"]["aangetroffen"]
    assert a.keys() == DIMENSIES.keys()
    # "binnen zes weken" en "indien hij daarom verzoekt" zijn gevonden; een plaats of een definitie niet.
    assert a["tijd"] >= 1 and a["voorwaarde"] >= 1 and a["actor"] >= 1
    assert a["plaats"] == 0 and a["definitie"] == 0 and a["delegatie"] == 0


def _fusie(*spans):
    return SimpleNamespace(kandidaten=[SimpleNamespace(span=SimpleNamespace(bron_iri="urn:t", start=s, eind=e))
                                       for s, e in spans])


def test_een_kandidaat_over_de_hele_zin_dekt_haar_delen_niet():
    """Een normzin-kandidaat raakt de hele zin, en `ongedekt` telt elke overlap: zonder deze lijst
    leek de zin onderzocht terwijl er binnen de zin niets gevonden was."""
    tekst = "Een belastingaanslag is invorderbaar. De ontvanger beslist."
    bron = BronTekst.van_tekst("urn:t", tekst, analyse=NullProvider().analyseer(tekst))
    eerste = tekst.index(".") + 1
    tweede_start = tekst.index("De ontvanger")
    f = _fusie((0, eerste), (tweede_start, tweede_start + len("De ontvanger")))
    assert ongedekt(f, bron) == [], "beide zinnen zijn geraakt"
    geheel = alleen_als_geheel(f, bron)
    assert [d["tekst"] for d in geheel] == ["Een belastingaanslag is invorderbaar."]
    assert tekst[geheel[0]["start"]:geheel[0]["eind"]] == geheel[0]["tekst"]


def test_alleen_als_geheel_staat_in_de_structurele_dekking():
    bron, resultaten, f = _keten(NullProvider())
    per_bron = structureel(f, [bron], {"urn:t": {r.detector for r in resultaten}})["urn:t"]
    assert isinstance(per_bron["alleen_als_geheel"], list)
