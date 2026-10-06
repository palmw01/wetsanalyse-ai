"""Het meetharnas voor detectorwijzigingen: casusbron, manifest, spreiding, voor/na en vooraf vastgelegde
criteria. Alles offline en zonder model."""
from __future__ import annotations

import copy
import json

import pytest

from agent.config import Settings
from eval import casusbron, manifest
from eval.compare_pipelines import _NepLLM, analyseer, meet
from eval.criteria import evalueer
from eval.detector_audit import klassenverschil
from eval.keten_fixture import ketensettings, laad_cases
from eval.referentieset import ReferentieFout, valideer_concept
from eval.vergelijk_rapporten import Onvergelijkbaar, vergelijk


# --- casusbron -----------------------------------------------------------------------------------

def test_v1_is_de_standaard_en_bevat_alleen_de_ontwikkelsplit():
    v1 = casusbron.laad()
    assert v1 and all(c["split"] == "ontwikkeling" and not c.get("diagnostisch") for c in v1)


def test_concepten_zijn_diagnostisch_en_gevalideerd():
    cs = casusbron.laad("concept:IW05")
    assert [c["id"] for c in cs] == ["IW05"] and cs[0]["diagnostisch"]
    assert casusbron.hashes("concept:IW05")["docs/wetsanalyse/referentieset/concept/IW05.json"]


def test_onbekende_bron_of_casus_wordt_geweigerd():
    with pytest.raises(ValueError):
        casusbron.laad("concept:XX99")
    with pytest.raises(ValueError):
        casusbron.laad("v2")


def test_v1_en_concept_mengen_wordt_geweigerd():
    with pytest.raises(ValueError, match="niet in één aggregaat"):
        casusbron.controleer_niet_gemengd([*casusbron.laad()[:1], *casusbron.laad("concept:IW05")])


def test_held_out_in_een_los_bestand_wordt_geweigerd(tmp_path):
    c = {**casusbron.laad("concept:IW05")[0], "split": "held-out"}
    c.pop("diagnostisch")
    p = tmp_path / "x.json"
    p.write_text(json.dumps([c]), encoding="utf-8")
    with pytest.raises(ValueError, match="held-out"):
        casusbron.laad(f"pad:{p}")


def test_concept_is_altijd_provisional_en_zijn_relaties_wijzen_naar_bestaande_elementen():
    c = copy.deepcopy(casusbron.laad("concept:IW05")[0])
    assert valideer_concept(c) == "provisional"
    with pytest.raises(ReferentieFout):
        valideer_concept({**c, "referentie_status": "adjudicated"})
    c["gold"][5]["relaties"] = [{"soort": "uitkomst_van", "doel": "E99"}]
    with pytest.raises(ReferentieFout, match="onbekende gid"):
        valideer_concept(c)


def test_laad_cases_leest_uit_de_gekozen_bron():
    assert laad_cases(["IW05"], "concept")[0]["diagnostisch"]
    with pytest.raises(ValueError):
        laad_cases(["IW05"])                     # staat niet in v1


# --- manifest ------------------------------------------------------------------------------------

def test_manifest_legt_code_referentie_en_modelinstellingen_vast():
    m = manifest.maak("concept:IW05", settings=ketensettings(Settings()))
    assert m["diagnostisch"] and m["git_sha"] and "fusie" in m["detectoren"]
    assert any(k.endswith("detectoren/syntactisch.py") for k in m["code"])
    assert {"model", "provider", "prompt_hash", "classifier_granulariteit"} <= m["run"].keys()
    assert manifest.verschillen(m, m) == []
    assert manifest.verschillen(m, {**m, "run": {**m["run"], "model": "ander"}}) == ["run.model"]


# --- compare_pipelines: spreiding en elementen ----------------------------------------------------

def _rapport(herhalingen=2, bron="v1", ids=("IW01", "AWB04")):
    cases = laad_cases(list(ids), bron)
    settings = ketensettings(Settings())
    rapport = {"casussen": cases, "runs": [],
               "manifest": {**manifest.maak(bron, settings=settings), "casus_ids": list(ids),
                            "herhalingen": herhalingen, "offline": True}}
    meet(cases, herhalingen, settings, _NepLLM, rapport)
    return rapport


def test_analyse_geeft_spreiding_geel_en_elementen_op_positie():
    a = analyseer(_rapport())["routes"]["hybrid_v1"]
    b = a["spreiding"]["micro_f1"]
    assert b["n"] == 2 and b["min"] <= b["mediaan"] <= b["max"]
    assert 0 <= a["geel_aandeel"] <= 1 and a["spreiding"]["per_klasse_f1"]
    e = next(iter(a["elementen"].values()))
    assert {"casus", "start", "eind", "tekst", "rondes", "klassen", "geel"} <= e.keys()


def test_diagnostische_analyse_is_als_zodanig_gemarkeerd():
    assert analyseer(_rapport(1, "concept:IW05", ("IW05",)))["diagnostisch"]


def test_vergelijken_weigert_wat_niet_vergelijkbaar_is():
    r = _rapport(1)
    assert vergelijk(r, r)["metrics"]["micro_f1"]["delta"] == 0
    with pytest.raises(Onvergelijkbaar, match="herhalingen"):
        vergelijk(r, {**r, "manifest": {**r["manifest"], "herhalingen": 3}})
    with pytest.raises(Onvergelijkbaar, match="run.model"):
        vergelijk(r, {**r, "manifest": {**r["manifest"], "run": {**r["manifest"]["run"], "model": "x"}}})
    with pytest.raises(Onvergelijkbaar, match="zonder manifest"):
        vergelijk(r, {k: v for k, v in r.items() if k != "manifest"})


def test_spreiding_bepaalt_of_een_verschil_een_effect_is():
    from eval.vergelijk_rapporten import _overlap
    assert _overlap({"min": .4, "max": .6}, {"min": .55, "max": .7}) is True
    assert _overlap({"min": .4, "max": .5}, {"min": .55, "max": .7}) is False


# --- detector_audit: verschil op positie ----------------------------------------------------------

def test_klassenverschil_is_op_kernpositie_en_niet_op_id():
    tekst = "Het aanslagbiljet is verzonden."
    voor = [{"id": "a", "start": 0, "eind": 17, "tekst": "Het aanslagbiljet",
             "possible_classes": ["Rechtssubject", "Rechtsobject"]}]
    na = [{"id": "b", "start": 0, "eind": 17, "tekst": "Het aanslagbiljet", "possible_classes": ["Rechtsobject"]},
          {"id": "c", "start": 21, "eind": 30, "tekst": "verzonden", "possible_classes": ["Rechtsfeit"]}]
    v = klassenverschil(voor, na, tekst)
    assert v[0] == {"start": 0, "eind": 17, "tekst": "Het aanslagbiljet", "soort": "klassen",
                    "klassen_bij": [], "klassen_af": ["Rechtssubject"]}
    assert v[1]["soort"] == "nieuw"
    assert klassenverschil(voor, voor, tekst) == []


# --- criteria ------------------------------------------------------------------------------------

def _audit(rijen_iw01, rijen_iw05):
    """Een minimale audit met v1-casus IW01 en conceptcasus IW05 (alleen wat de criteria lezen)."""
    iw01 = next(c for c in casusbron.laad() if c["id"] == "IW01")
    iw05 = casusbron.laad("concept:IW05")[0]
    refs = [{"id": "IW01/E02", "bron": "IW01", "klasse": "Rechtsobject", "start": 0, "eind": 20}]
    return {"referentieankers": refs, "diagnostiek": ["IW05"],
            "scenario": {"S0": {"gedekte_ankers": ["IW01/E02"]}},
            "kandidaat_eval": {"per_klasse": {"Rechtsobject": {"candidate_recall": 1.0, "met_klasse": 1.0}}},
            "per_casus": {"IW01": {"tekst": iw01["tekst"], "scenario": {"S0": rijen_iw01}},
                          "IW05": {"tekst": iw05["tekst"], "diagnostisch": True, "scenario": {"S0": rijen_iw05}}}}


def _rij(start, eind, *klassen):
    return {"start": start, "eind": eind, "tekst": "", "possible_classes": list(klassen)}


def test_criteria_slagen_alleen_als_elke_poortregel_slaagt():
    voor = _audit([_rij(0, 20, "Rechtssubject", "Rechtsobject")], [_rij(189, 206, "Rechtssubject", "Rechtsobject")])
    na = _audit([_rij(0, 20, "Rechtsobject")], [_rij(189, 206, "Rechtsobject"), _rij(296, 433, "Afleidingsregel")])
    criteria = {"naam": "t", "regels": [
        {"id": "1", "soort": "element_kandidaat", "element": "IW05/E05", "klasse": "Afleidingsregel"},
        {"id": "2", "soort": "geen_klasse_op_tekst", "casus": "IW05", "tekst": "het aanslagbiljet",
         "klasse": "Rechtssubject"},
        {"id": "3", "soort": "anker_klasse_behouden", "klasse": "Rechtsobject"},
        {"id": "4", "soort": "recall_niet_lager"}, {"id": "5", "soort": "geen_verloren_ankers"},
        {"id": "6", "soort": "alleen_toegestane_wijzigingen", "toegestaan": {"IW01": ["Een belastingaanslag"]}},
        {"id": "7", "soort": "model_min_niet_lager", "metric": "micro_f1", "poort": False}]}
    u = evalueer(criteria, voor, na)
    assert u["geslaagd"], u
    assert u["regels"][-1]["uitslag"] == "niet_gemeten"       # een waarneming beslist niet
    # Zonder toestemming is dezelfde wijziging een regressie; een poortregel zonder model is niet geslaagd.
    criteria["regels"][5]["toegestaan"] = {}
    assert not evalueer(criteria, voor, na)["geslaagd"]
    criteria["regels"][5]["toegestaan"] = {"IW01": ["Een belastingaanslag"]}
    criteria["regels"][6]["poort"] = True
    assert not evalueer(criteria, voor, na)["geslaagd"]


def test_verdwijnen_is_niet_hetzelfde_als_goed_geklasseerd():
    voor = _audit([], [_rij(189, 206, "Rechtssubject")])
    na = _audit([], [])
    u = evalueer({"regels": [{"id": "x", "soort": "geen_klasse_op_tekst", "casus": "IW05",
                              "tekst": "het aanslagbiljet", "klasse": "Rechtssubject"}]}, voor, na)
    assert not u["geslaagd"]


def test_de_vastgelegde_criteria_zijn_geldig_en_vooraf_gehasht():
    import hashlib
    import re

    import yaml

    from eval.criteria import SOORTEN
    map_ = manifest.ROOT / "docs/architectuur/metingen/hybrid-v1-iw05-fixes-2026-10"
    readme = (map_ / "README.md").read_text(encoding="utf-8")
    for p in sorted((map_ / "criteria").glob("*.yaml")):
        c = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert c["regels"] and all(r["soort"] in SOORTEN for r in c["regels"])
        assert len({r["id"] for r in c["regels"]}) == len(c["regels"])
        # Het criterium mag na de nulmeting niet meer veranderen: de README legt de hash vast.
        assert re.search(rf"{hashlib.sha256(p.read_bytes()).hexdigest()}\s+criteria/{p.name}", readme), p.name
