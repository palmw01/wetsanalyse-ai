"""Het A/B-harnas (ADR-001 PR 16), offline: identieke bron voor beide routes, eerlijke naamgeving."""
from __future__ import annotations

from agent.config import Settings
from eval.compare_pipelines import MEETBAAR, _NepLLM, analyseer, markdown, meet
from eval.keten_fixture import ketensettings, laad_cases


def _rapport(herhalingen=2):
    cases = laad_cases(["IW01", "AWB04"])
    rapport = {"casussen": cases, "runs": []}
    meet(cases, herhalingen, ketensettings(Settings()), _NepLLM, rapport)
    return rapport


def test_elke_route_krijgt_elke_casus_in_elke_ronde():
    r = _rapport()
    assert {(x["route"], x["casus"], x["ronde"]) for x in r["runs"]} == {
        (route, c, ronde) for route in MEETBAAR for c in ("IW01", "AWB04") for ronde in (1, 2)}
    assert not any(x["fout"] for x in r["runs"])


def test_analyse_noemt_recall_ankerdekking_zolang_de_referentie_provisional_is():
    a = analyseer(_rapport())
    assert a["referentie_status"] == "provisional" and a["recall_heet"] == "ankerdekking"
    assert "annotation recall" not in markdown(a).replace("geen annotation recall", "")


def test_hybride_route_levert_ook_zonder_model_stabiele_voorstellen_op():
    a = analyseer(_rapport())["routes"]["hybrid_v1"]
    assert a["stabiliteit"]["detectie_stabiel"] == 1.0 and a["efficientie"]["zonder_model"] > 0
    assert a["efficientie"]["human_review"] > 0       # wat het nep-model niet besliste, gaat naar de jurist


def test_debatable_telt_niet_mee_en_fouten_volgen_taxonomie_v2():
    r = _rapport(herhalingen=1)
    a = analyseer(r)["routes"]["hybrid_v1"]
    assert set(a["foutcategorieen"]) == {"primair", "secundair", "per_soort", "correct", "debatable", "handmatig"}
    assert a["debatable_uitgesloten"] == 0
    # Maak één referentie-element debatable: het verdwijnt uit teller én noemer.
    iw01 = next(c for c in r["casussen"] if c["id"] == "IW01")
    r2 = {**r, "casussen": [{**c, "gold": [{**g, "annotation_status": "debatable"} if g["gid"] == "E03" else g
                                           for g in c["gold"]]} if c is iw01 else c for c in r["casussen"]]}
    b = analyseer(r2)["routes"]["hybrid_v1"]
    assert b["debatable_uitgesloten"] == 1 and b["foutcategorieen"]["debatable"] == 1


def test_oud_rapport_met_casussen_in_het_formaat_van_voor_v1_blijft_analyseerbaar():
    r = _rapport(herhalingen=1)
    oud = [{**{k: v for k, v in c.items() if k not in ("gold", "vindplaats")}, "artikel": c["vindplaats"],
            "annotaties": [{"id": g["gid"], "start": g["start"], "end": g["eind"], "tekst": g["tekst"],
                            "klasse": g["klasse"], "motivatie": g["motivatie"]} for g in c["gold"]]}
           for c in r["casussen"]]
    assert analyseer({**r, "casussen": oud})["routes"]["hybrid_v1"]["micro_f1"] == \
        analyseer(r)["routes"]["hybrid_v1"]["micro_f1"]
