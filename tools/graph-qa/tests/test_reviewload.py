"""Classifier-contract en reviewload (onderzoek-empirische-validatie §6, §9; validatieplan V5).

Alleen rapportage: de afhandeling, de reviewer-prompt en de resolutietabel blijven gelijk."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace as NS

from agent.jas_pipeline.onzekerheid import Twijfel
from agent.jas_pipeline.review import _prompt, valideer
from agent.jas_pipeline.reviewload import splits
from eval.fouttaxonomie import _vervallen
from eval.metrieken import contract_metrieken
from test_hybride_keten import KetenLLM, _draai, _elementen

T4 = json.loads((Path(__file__).parent / "fixtures" / "t4_li95_spoor.json").read_text(encoding="utf-8"))


def _t4():
    """Beslissingen, twijfels, transities en register uit de T4-spoorvelden."""
    beslissingen, twijfels, transities, register = [], [], [], []
    for e in T4["elementen"]:
        t = e["trace"]
        label, b = t["kandidaat"]["label"], t["beslissing"]
        beslissingen.append(NS(label=label, status=b["status"]))
        twijfels += [NS(label=label, **w) for w in t["twijfel"]]
        transities += [NS(label=label, **r) for r in t["resolutie"]]
        register.append({"door": b["door"], "mogelijke_klassen": t["kandidaat"]["mogelijke_klassen"],
                         "vervallen": list(_vervallen(t["kandidaat"]["bewijs"])),
                         "classifier_reden": next((w["detail"] for w in t["twijfel"] if w["detail"]), b["reden"])})
    return beslissingen, twijfels, transities, register


def test_t4_twaalf_gele_kaarten_zijn_twaalf_contractfouten_en_nul_juridische_vragen():
    beslissingen, twijfels, transities, _ = _t4()
    r = splits(beslissingen, twijfels, transities)
    assert r["human_review"] == 12
    assert r["classifier_contract_failure"] == 12 and r["juridisch"] == 0 and r["technisch"] == 12
    assert r["substantive_legal_review"] == 0 and r["reviewer_ongeldig"] == 12


def test_t4_contractmetrieken():
    *_, register = _t4()
    m = contract_metrieken(register, T4["granulariteit"],
                           [{"reden": "CLASSIFIER_ABSTAIN", "regel": "R-ONGELDIG"}] * 12)
    assert m["invalid_class_selections"] == 12 and m["leakage_count"] == 12
    assert m["leakage_uit_specificiteit"] == 9          # type A: Variabele was door voorrang weggehaald
    assert m["invalid_tool_outputs"] == 0 and m["contract_error_rate"] == 12 / m["modelbeslissingen"]
    assert m["reviewer_contract_error_rate"] == 1.0


def test_substantieve_twijfel_blijft_juridisch():
    b = [NS(label="C1", status="HUMAN_REVIEW"), NS(label="C2", status="HUMAN_REVIEW"), NS(label="C3", status="ACCEPTED")]
    t = [NS(label="C1", reden="DETECTOR_CONFLICT", detail="sterk bewijs voor Tijdsaanduiding"),
         NS(label="C2", reden="DEGRADED_PARSE", detail="")]
    tr = [NS(label="C1", regel="R-CONFLICT-KEEP"), NS(label="C2", regel="R-DEGRADED")]
    r = splits(b, t, tr)
    assert (r["juridisch"], r["technisch"], r["degraded_parse_review"], r["detector_conflict_review"]) == (1, 1, 1, 1)


def test_reviewer_bewaart_ruwe_uitvoer_en_reden_van_ongeldigheid():
    t = [Twijfel(label="C1", reden="DETECTOR_CONFLICT", huidig="Rechtsobject", alternatieven=("Tijdsaanduiding",))]
    [o] = valideer(t, [{"geval": "C1", "actie": "CHANGE", "klasse": "Variabele en variabelewaarde"}])
    assert not o.geldig and o.ruw == {"actie": "CHANGE", "klasse": "Variabele en variabelewaarde"}
    assert "geen alternatief" in o.ongeldig_omdat
    [o] = valideer(t, None)
    assert o.ruw is None and o.ongeldig_omdat == "geen tool-aanroep"
    [o] = valideer(t, [{"geval": "C1", "actie": "KEEP", "klasse": ""}])
    assert o.geldig and o.ongeldig_omdat == ""


def test_de_categorie_komt_niet_in_de_reviewer_prompt():
    k = NS(span=NS(tekst="één maand"))
    t = Twijfel(label="C1", reden="CLASSIFIER_ABSTAIN", alternatieven=("Tijdsaanduiding",),
                detail="CLASSIFIER_ONGELDIGE_KLASSE:Variabele en variabelewaarde",
                categorie="CLASSIFIER_CONTRACT_ERROR")
    assert _prompt([t], {"C1": k}, "tekst") == _prompt([t.model_copy(update={"categorie": ""})], {"C1": k}, "tekst")


def test_keten_splitst_de_reviewload_en_noemt_een_storing_een_storing():
    llm = KetenLLM(kies=lambda toegestaan: "Plaatsaanduiding")     # buiten elk contract
    events = _draai(llm)
    meting = next(e for e in events if e["type"] == "run")["run"]["instellingen"]["meting"]
    rl = meting["reviewload"]
    assert rl["human_review"] > 0 and rl["classifier_contract_failure"] == rl["human_review"]
    assert rl["juridisch"] == 0
    geel = [e for e in _elementen(events) if e.get("aandacht") == "geel"]
    assert geel and all(e["critic"].startswith("Technische storing") for e in geel)
    assert all(t["categorie"] == "CLASSIFIER_CONTRACT_ERROR" for e in geel for t in e["trace"]["twijfel"])
    # De reviewer kreeg geen tool-aanroep terug: dat staat nu in het spoor, niet alleen "R-ONGELDIG".
    assert all(r["ongeldig_omdat"] == "geen tool-aanroep" for e in geel for r in e["trace"]["resolutie"])
    # Geen promptwijziging: de nieuwe categorie komt in geen enkele modelaanroep voor.
    assert not any("CLASSIFIER_CONTRACT_ERROR" in json.dumps(c, default=str) for c in llm.calls)
