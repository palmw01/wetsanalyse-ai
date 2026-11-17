"""Lex Bench, arm T (plan §4.2, LB2): de opdracht van een analist en de controle van zijn formulier.

Geen model: de opdracht is tekst, de controle is code. Wat hier vastligt, is dat de opdracht de verwachting nooit
meegeeft, en dat een formulier met een gat of een dubbele plek niet doorgaat.
"""
from __future__ import annotations

import copy
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
