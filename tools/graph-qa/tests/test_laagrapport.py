"""Rapport per laag (onderzoek-empirische-validatie §2.2, §9, §14; validatieplan V6), offline."""
from __future__ import annotations

import copy
import re

import pytest

from agent.config import Settings
from eval.compare_pipelines import _NepLLM, meet
from eval.keten_fixture import ketensettings, laad_cases
from eval.laagrapport import CHECKLIST, LAGEN, bouw, checklist, lees_checklist, markdown


@pytest.fixture(scope="module")
def rapport():
    cases = laad_cases(["IW01", "AWB04", "RVV01"])
    r = {"casussen": cases, "runs": []}
    meet(cases, 2, ketensettings(Settings()), _NepLLM, r)
    return r


def test_per_laag_per_familie_en_tekstsoort_zonder_totaalscore(rapport):
    r = bouw(rapport)
    assert set(r["groepen"]) == {"alle", "familie IW", "familie Awb", "familie RVV", "tekstsoort wet",
                                 "tekstsoort amvb"}
    for g in r["groepen"].values():
        assert set(LAGEN) <= set(g) and g["referentie_status"] == "provisional"
    assert not any("totaal" in k or "score" in k for g in r["groepen"].values() for k in g)
    alle = r["groepen"]["alle"]
    assert "ankerdekking" in alle["classificatie"] and "annotation_recall" not in alle["classificatie"]
    f = alle["fouten"]
    assert sum(f["per_soort"].values()) == sum(f["primair"].values())
    assert sum(sum(v.values()) for v in f["per_laag"].values()) == sum(f["primair"].values())
    md = markdown(r)
    assert "Geen totaalscore" in md and re.search(r"\d+% \(\d+/\d+\)", md)   # teller/noemer onder n = 20
    assert all(f"## {laag}" in md for laag in LAGEN)


def test_debatable_valt_buiten_teller_en_noemer(rapport):
    r2 = copy.deepcopy(rapport)
    for c in r2["casussen"]:
        for g in c["gold"]:
            g["annotation_status"] = "debatable"
    alle = bouw(r2)["groepen"]["alle"]
    assert alle["classificatie"]["debatable_uitgesloten"] > 0
    assert alle["fouten"]["primair"].get("CANDIDATE_MISSED", 0) == 0 and alle["fouten"]["correct"] == 0


def test_checklist_bijlage_is_vooringevuld_en_komt_terug_als_correctie(rapport):
    rijen = checklist(rapport)
    assert rijen and all(set(x["antwoorden"]) == {n for n, _ in CHECKLIST} for x in rijen)
    assert all(x["antwoorden"]["span_aanwezig"] in ("kandidaat", "optie", "niet") for x in rijen)
    eerste = rijen[0]
    eerste["correctie"] = {"primair": "PARSER_ERROR", "toelichting": "kopwoord verkeerd"}
    eerste["antwoorden"]["predicaatrelatie_nodig"] = True
    correcties, frames = lees_checklist(rijen)
    assert correcties == {eerste["sleutel"]: eerste["correctie"]}
    assert frames["NormFrame"]["ja"] == 1
    r = bouw(rapport, ingevuld=rijen)
    assert r["handmatige_correcties"] == 1
    # De oorzaak hoort bij het gold-element, dus de correctie geldt in elke herhaling (hier twee).
    assert r["groepen"]["alle"]["fouten"]["primair"].get("PARSER_ERROR") == 2
    assert r["groepen"]["alle"]["fouten"]["handmatig"] == 2


def test_oud_rapport_zonder_register_blijft_te_rapporteren(rapport):
    oud = copy.deepcopy(rapport)
    for run in oud["runs"]:
        run.pop("beslissingen", None)
    r = bouw(oud)["groepen"]["alle"]
    assert r["kandidaatlaag"]["candidate_recall"] is None and r["classificatie"]["micro_f1"] is not None
