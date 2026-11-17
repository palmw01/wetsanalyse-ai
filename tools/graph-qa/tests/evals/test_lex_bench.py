"""De scorekaart van Lex Bench, arm L1 (plan §5, LB1): de rekenregels en wat een blinde casus niet prijsgeeft.

Offline, tegen de opnames van de graaf: geen model, nul tokens. De uitkomst zelf is geen pin (plan §4.5, §20.4): deze
tests toetsen de vorm en de rekenregels, niet de score.
"""
from __future__ import annotations

import json

import pytest

from eval import lex_bench as lb

pytestmark = pytest.mark.risico("R15", laag=1)


def test_een_maat_draagt_teller_en_noemer():
    assert lb._maat(7, 12) == {"teller": 7, "noemer": 12, "waarde": 0.583}
    assert lb._maat(0, 0) == {"teller": 0, "noemer": 0, "waarde": None}, "een lege noemer is geen nul"


def test_het_manifest_klopt_met_de_sets_van_nu():
    m = lb.laad_manifest()
    assert m["hash"] == lb.versiehash(m["casussen"])
    assert [c["casus_id"] for c in m["casussen"]] == [c for c, _, _ in lb.CASUSSEN]
    assert lb.bouw_manifest()["hash"] == m["hash"], "een set veranderde: maak een nieuwe versie van het manifest"


def test_de_scorekaart_rekent_met_de_tellingen_van_de_set():
    casus = lb.laad_manifest()["casussen"][-1]
    k = lb.scoor_casus(casus)
    m = k["maten"]
    assert m["recall"]["noemer"] == casus["verwacht"]
    assert k["categorieen"]["lex_mist"] == m["recall"]["noemer"] - m["recall"]["teller"]
    assert k["categorieen"]["lex_onterecht"] == len(k["verschillen"]["lex_onterecht"])
    # Jaccard: wat Lex raakt, gedeeld door wat er samen staat; nooit boven de recall of de precisie.
    assert m["overlap"]["waarde"] <= min(m["recall"]["waarde"], m["precisie"]["waarde"])
    assert {k["categorieen"]["team_mist"], k["categorieen"]["twijfel"]} == {0}, "die vragen de reviewer (LB2)"


def test_een_blinde_casus_geeft_geen_bepalingen_prijs():
    casus = {**lb.laad_manifest()["casussen"][-1], "gebruik": "blind"}
    k = lb.scoor_casus(casus)
    assert "verschillen" not in k
    assert "bron_iri" not in json.dumps(k)


def test_het_rapport_houdt_blind_en_ontwikkeling_apart_en_heeft_geen_totaal():
    kaart = {"maten": {"recall": lb._maat(1, 2)},
             "categorieen": {"lex_mist": 1, "lex_onterecht": 0, "team_mist": 0, "twijfel": 0}}
    kaarten = [{**kaart, "casus_id": "A", "gebruik": "ontwikkeling", "niveau": "moeilijk"},
               {**kaart, "casus_id": "B", "gebruik": "blind", "niveau": "moeilijk"}]
    rijen = lb.rapport_per_niveau(kaarten)
    assert [(r["gebruik"], r["casussen"]) for r in rijen] == [("ontwikkeling", ["A"]), ("blind", ["B"])]


def test_een_meetmap_wordt_niet_overschreven(tmp_path):
    (tmp_path / "bestaat").mkdir()
    with pytest.raises(SystemExit, match="niet overschreven"):
        lb.run_l1("x", "2026-11-17", tmp_path / "bestaat")


def test_het_dashboard_laat_de_bepalingen_van_een_blinde_casus_weg(tmp_path):
    map_ = tmp_path / "lex-bench-2026-11-17-x"
    map_.mkdir()
    kaart = {"casus_id": "A", "gebruik": "blind", "verschillen": {"lex_mist": [{"bron_iri": "urn:bwb:geheim"}]}}
    (map_ / "run.json").write_text(json.dumps({"datum": "2026-11-17"}), encoding="utf-8")
    (map_ / "rapport.json").write_text(json.dumps({"casussen": [kaart], "per_niveau": []}), encoding="utf-8")
    data = lb.dashboard_data(tmp_path)
    assert "urn:bwb:geheim" not in json.dumps(data)
    assert data["risicos"]["risicos"], "de risicomatrix staat erbij"
