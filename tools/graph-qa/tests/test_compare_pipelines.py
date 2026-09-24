"""Het A/B-harnas (ADR-001 PR 16), offline: identieke bron voor beide routes, eerlijke naamgeving."""
from __future__ import annotations

from agent.config import Settings
from eval.compare_pipelines import ROUTES, _NepLLM, analyseer, markdown, meet
from eval.keten_fixture import ketensettings, laad_cases


def _rapport(herhalingen=2):
    cases = laad_cases(["IW01", "AWB04"])
    rapport = {"casussen": cases, "runs": []}
    meet(cases, herhalingen, ketensettings(Settings()), _NepLLM, rapport)
    return rapport


def test_beide_routes_krijgen_elke_casus_in_elke_ronde():
    r = _rapport()
    assert {(x["route"], x["casus"], x["ronde"]) for x in r["runs"]} == {
        (route, c, ronde) for route in ROUTES for c in ("IW01", "AWB04") for ronde in (1, 2)}
    assert not any(x["fout"] for x in r["runs"])


def test_analyse_noemt_recall_ankerdekking_zolang_de_referentie_provisional_is():
    a = analyseer(_rapport())
    assert a["referentie_status"] == "provisional" and a["recall_heet"] == "ankerdekking"
    assert "annotation recall" not in markdown(a).replace("geen annotation recall", "")


def test_hybride_route_levert_ook_zonder_model_stabiele_voorstellen_op():
    a = analyseer(_rapport())["routes"]["hybrid_v1"]
    assert a["stabiliteit"]["detectie_stabiel"] == 1.0 and a["efficientie"]["zonder_model"] > 0
    assert a["efficientie"]["human_review"] > 0       # wat het nep-model niet besliste, gaat naar de jurist
