"""Lex Bench, arm T (plan §4.2, LB2): de opdracht van een analist en de controle van zijn formulier.

Geen model: de opdracht is tekst, de controle is code. Wat hier vastligt, is dat de opdracht de verwachting nooit
meegeeft, en dat een formulier met een gat of een dubbele plek niet doorgaat.
"""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from eval import lex_bench_team as team

pytestmark = pytest.mark.risico("R15", laag=1)

DOSSIER = {"naam": "Proef", "analysevraag": "Wanneer?", "regelingen": ["BWBR0004770"],
           "deelvragen": ["Eerste deelvraag?", "Tweede deelvraag?"]}


def _formulier() -> dict:
    bep = {"bron_iri": "urn:bwb:BWBR0004770:artikel:26:lid:1", "rol": "kern", "zoekvraag": "a", "motivering": "draagt",
           "bewijs": {"tool": "bron_lezen", "citaat": "Bij ministeriële regeling worden regels gesteld"}}
    return {"formulier": "lex-bench-formulier-1", "casus_id": "LB-02", "analist": "A", "run": "lb-02-proef-a",
            "deelvragen": [{"deelvraag": 0, "bepalingen": [bep], "uitgesloten": [], "twijfel": []},
                           {"deelvraag": 1, "bepalingen": [], "uitgesloten": [
                               {"bron_iri": "urn:bwb:BWBR0004770:artikel:26a:lid:1", "motivering": "buiten"}],
                            "twijfel": []}]}


def test_het_dossier_draagt_geen_verwachting():
    s = team.laad_casus("LB-02")
    vol = json.loads((team.WORTEL / s["pad"] / "set.json").read_text(encoding="utf-8"))
    d = team.dossier_van(vol)
    assert set(d) <= set(team.DOSSIERVELDEN) and d["deelvragen"] == vol["deelvragen"]
    for veld in ("verwacht", "uitgesloten", "buiten_graaf", "toelichting"):
        assert veld not in d


IN_REPO = [c["casus_id"] for c in json.loads(team.MANIFEST.read_text(encoding="utf-8"))["casussen"] if c.get("pad")]


@pytest.mark.parametrize("casus_id", IN_REPO)
def test_de_opdracht_noemt_geen_bepaling_uit_de_verwachting(casus_id):
    s = team.laad_casus(casus_id)
    vol = json.loads((team.WORTEL / s["pad"] / "set.json").read_text(encoding="utf-8"))
    tekst = team.opdracht(team.dossier_van(vol), casus_id, "A", "lb-02-proef-a")
    assert "## Voor de coördinator" not in tekst, "de werkwijze van de coördinator hoort niet bij de analist"
    for n in team.UITWERKINGEN:
        assert f"Uit de skill wetsanalyse: {n}" in tekst
    for v in vol["verwacht"] + vol.get("uitgesloten", []):
        assert v["bron_iri"] not in tekst, "de briefing of de skill noemt een verwachte bepaling"
        assert not v.get("motivering") or v["motivering"] not in tekst
    assert '"analist": "A"' in tekst and "lb-02-proef-a" in tekst


def test_een_blinde_casus_komt_niet_uit_de_repo(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"versie": "v", "casussen": [{"casus_id": "LB-21", "gebruik": "blind"}]}))
    with pytest.raises(SystemExit, match="--dossier"):
        team.laad_casus("LB-21", manifest)


def test_een_goed_formulier_klopt():
    assert team.controleer(_formulier(), DOSSIER, "LB-02") == []


@pytest.mark.parametrize("breuk, melding", [
    (lambda f: f["deelvragen"].pop(), "verwacht precies [0, 1]"),
    (lambda f: f["deelvragen"][0]["bepalingen"][0]["bewijs"].update(citaat="  "), "citaat: leeg"),
    (lambda f: f["deelvragen"][0]["bepalingen"][0].update(rol="belangrijk"), "rol: 'belangrijk'"),
    (lambda f: f["deelvragen"][0]["bepalingen"][0].update(bron_iri="artikel 26"), "heeft niet de vorm"),
    (lambda f: f["deelvragen"][0]["bepalingen"][0].pop("bewijs"), "bewijs ontbreekt"),
    (lambda f: f.update(verwacht=[]), "onbekend veld verwacht"),
    (lambda f: f["deelvragen"][0]["twijfel"].append(
        {"bron_iri": "urn:bwb:BWBR0004770:artikel:26:lid:1", "reden": "?"}), "staat 2 keer"),
    (lambda f: f.update(casus_id="LB-03"), "verwacht LB-02"),
    (lambda f: f["deelvragen"][1].update(deelvraag=True), "verwacht integer"),
])
def test_een_formulier_met_een_fout_gaat_niet_door(breuk, melding):
    f = copy.deepcopy(_formulier())
    breuk(f)
    fouten = team.controleer(f, DOSSIER, "LB-02")
    assert any(melding in m for m in fouten), fouten


def test_de_cli_geeft_een_fout_als_exitcode(tmp_path, capsys):
    pad = tmp_path / "f.json"
    f = _formulier()
    f["deelvragen"].pop()
    pad.write_text(json.dumps(f))
    assert team.main(["controleer", str(pad), "--casus", "LB-02"]) == 1


# --- samenvoegen en bevriezen (§4.2) ---

CASUS = {"casus_id": "LB-02", "niveau": "moeilijk", "gebruik": "ontwikkeling"}
I1, I2, I3, I4, I5 = (f"urn:bwb:BWBR0004770:artikel:{n}:lid:1" for n in (1, 2, 3, 4, 5))


def _bep(iri, rol="kern"):
    return {"bron_iri": iri, "rol": rol, "zoekvraag": "a", "motivering": f"draagt {iri[-12:]}",
            "bewijs": {"tool": "bron_lezen", "citaat": "letterlijk"}}


def _f(analist, d0, d1=None):
    leeg = {"bepalingen": [], "uitgesloten": [], "twijfel": []}
    return {"formulier": "lex-bench-formulier-1", "casus_id": "LB-02", "analist": analist, "run": f"r-{analist.lower()}",
            "deelvragen": [{"deelvraag": 0, **leeg, **d0}, {"deelvraag": 1, **leeg, **(d1 or {})}]}


def test_samenvoegen_legt_a_en_b_naast_elkaar_zonder_te_kiezen():
    a = _f("A", {"bepalingen": [_bep(I1), _bep(I2, "afhankelijkheid"), _bep(I3)],
                 "uitgesloten": [{"bron_iri": I4, "motivering": "buiten"}]})
    b = _f("B", {"bepalingen": [_bep(I1), _bep(I2, "kern")], "twijfel": [{"bron_iri": I3, "reden": "lid 2?"}],
                 "uitgesloten": [{"bron_iri": I4, "motivering": "erbuiten"}, {"bron_iri": I5, "motivering": "oud"}]})
    t = team.voeg_samen([a, b], DOSSIER, CASUS, "lb-02-proef", "2026-11-17")
    assert [(v["bron_iri"], v["rol"]) for v in t["verwacht"]] == [(I1, "kern"), (I2, "kern")], "bij verschil de zwaarste rol"
    assert {(o["bron_iri"], o["soort"]) for o in t["onenig"]} == {(I2, "rol"), (I3, "alleen_A")}
    drie = next(o for o in t["onenig"] if o["bron_iri"] == I3)
    assert drie["argumenten"]["B"] == {"plek": "twijfel", "motivering": "lid 2?"}, "het standpunt van beide staat erin"
    assert {u["bron_iri"] for u in t["uitgesloten"]} == {I4, I5}
    assert t["verwachting"] == {"opgesteld_door": {"run_id": "lb-02-proef", "analisten": ["A", "B"]},
                                "vastgesteld_door": None, "status": "concept", "datum": "2026-11-17"}


def test_de_teamverwachting_heeft_de_vorm_van_schema_4():
    schema = json.loads((team.BENCH / "bronselectie" / "casus-schema-4.json").read_text(encoding="utf-8"))
    t = team.voeg_samen([_f("A", {"bepalingen": [_bep(I1)]}), _f("B", {"bepalingen": [_bep(I2)]})], DOSSIER, CASUS, "r")
    assert team.schemafouten(t, schema) == []


def test_een_makkelijke_casus_met_een_analist_zet_zijn_twijfel_open():
    a = _f("A", {"bepalingen": [_bep(I1)], "twijfel": [{"bron_iri": I2, "reden": "?"}]})
    t = team.voeg_samen([a], DOSSIER, dict(CASUS, niveau="makkelijk"), "r")
    assert [v["bron_iri"] for v in t["verwacht"]] == [I1]
    assert [(o["bron_iri"], o["soort"]) for o in t["onenig"]] == [(I2, "twijfel")]


def test_samenvoegen_weigert_een_fout_formulier_of_twee_keer_dezelfde_analist():
    with pytest.raises(ValueError, match="verschillende analisten"):
        team.voeg_samen([_f("A", {}), _f("A", {})], DOSSIER, CASUS, "r")
    kapot = _f("B", {})
    kapot["deelvragen"].pop()
    with pytest.raises(ValueError, match="formulier B"):
        team.voeg_samen([_f("A", {}), kapot], DOSSIER, CASUS, "r")


def test_bevriezen_schrijft_eenmalig_met_de_hash(tmp_path):
    a, b = _f("A", {"bepalingen": [_bep(I1)]}), _f("B", {"bepalingen": [_bep(I1)]})
    t = team.voeg_samen([a, b], DOSSIER, CASUS, "r")
    map_ = tmp_path / "team"
    bevroren = team.bevries(t, [a, b], map_)
    assert set(bevroren["sha256"]) == {"teamverwachting.json", "formulier-a.json", "formulier-b.json"}
    for naam, sha in bevroren["sha256"].items():
        assert hashlib.sha256((map_ / naam).read_bytes()).hexdigest() == sha
    with pytest.raises(FileExistsError):
        team.bevries(t, [a, b], map_)


def test_een_blinde_casus_bevriest_niet_in_de_repo():
    t = team.voeg_samen([_f("A", {})], DOSSIER, dict(CASUS, gebruik="blind"), "r")
    with pytest.raises(ValueError, match="buiten de repo"):
        team.bevries(t, [], team.WORTEL / "docs" / "nergens")
    assert not (team.WORTEL / "docs" / "nergens").exists()
