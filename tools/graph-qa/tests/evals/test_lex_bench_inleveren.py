"""Lex Bench: de opdracht en het formulier via de runmap (pilot LB3, bevinding 1 en 5).

De agent leest zijn opdracht zelf (`bench_opdracht_lezen`) en levert in met `bench_inleveren`; de MCP laat deze controle
op elke poging los. Getoetst op de bewaarde pilot: het formulier van LB-08 A met het onbekende veld gaat terug naar de
agent, en de review van LB-07 klopt ook met de uitgebreide kaart. Offline, geen model.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval import lex_bench_inleveren as inl
from eval import lex_bench_review as rv
from eval import lex_bench_team as team

pytestmark = pytest.mark.risico("R15", laag=1)

METING = team.WORTEL / "docs" / "architectuur" / "metingen" / "lex-bench-2026-11-17-pilot"
PILOT = team.BENCH / "bronselectie" / "pilot"


def test_de_runmap_is_die_van_de_checkout_ook_vanuit_een_worktree():
    assert team.lokaal_map(Path("/r/proj/.claude/worktrees/abc")) == Path("/r/proj/docs/acceptatie/lokaal")
    assert team.lokaal_map(Path("/r/proj")) == Path("/r/proj/docs/acceptatie/lokaal")


def test_een_opdracht_in_de_runmap_blijft_staan(tmp_path):
    doel = team.naar_run("lb-10-a", "# tekst\n", {"soort": "analist", "casus": "LB-10"}, tmp_path)
    assert (doel / "opdracht.md").read_text(encoding="utf-8") == "# tekst\n"
    with pytest.raises(FileExistsError):
        team.naar_run("lb-10-a", "# anders\n", {}, tmp_path)
    with pytest.raises(ValueError, match="Een run heet"):
        team.naar_run("../uit", "", {}, tmp_path)


def test_naar_run_zet_alleen_een_regel_op_stdout(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(team, "lokaal_map", lambda wortel=team.WORTEL: tmp_path)
    dossier = PILOT / "lb-08-terugvordering-toeslag" / "set.json"
    assert team.main(["opdracht", "--casus", "LB-08", "--analist", "A", "--run", "lb-08-p-a", "--dossier",
                      str(dossier), "--naar-run"]) == 0
    uit = capsys.readouterr().out
    assert "bench_opdracht_lezen" in uit and "# Lex Bench" not in uit
    controle = json.loads((tmp_path / "lb-08-p-a" / "opdracht.json").read_text(encoding="utf-8"))
    assert controle == {"soort": "analist", "casus": "LB-08", "dossier": str(dossier.resolve())}


def _inleveren(tmp_path: Path, controle: dict, formulier: dict, n: int = 1) -> dict:
    doel = tmp_path / "run-x"
    doel.mkdir(exist_ok=True)
    (doel / "opdracht.json").write_text(json.dumps(controle), encoding="utf-8")
    (doel / f"inlevering-{n}.json").write_text(json.dumps(formulier), encoding="utf-8")
    return inl.controleer("run-x", f"inlevering-{n}.json", tmp_path)


def test_het_formulier_met_het_onbekende_veld_gaat_terug_naar_de_analist(tmp_path):
    controle = {"soort": "analist", "casus": "LB-08",
                "dossier": str(PILOT / "lb-08-terugvordering-toeslag" / "set.json")}
    fout = _inleveren(tmp_path, controle, json.loads((METING / "LB-08" / "formulier-a.origineel.json").read_text()))
    assert fout == {"geldig": False, "fouten": ["$.deelvragen[1].twijfel[0]: onbekend veld rol_placeholder"]}
    goed = _inleveren(tmp_path, controle, json.loads((METING / "LB-08" / "formulier-a.json").read_text()), 2)
    assert goed == {"geldig": True, "fouten": []}


def test_geen_json_is_een_fout_en_geen_crash(tmp_path):
    doel = tmp_path / "run-x"
    doel.mkdir()
    (doel / "opdracht.json").write_text('{"soort": "analist", "casus": "LB-08"}', encoding="utf-8")
    (doel / "inlevering-1.json").write_text("{kapot", encoding="utf-8")
    assert inl.controleer("run-x", "inlevering-1.json", tmp_path)["geldig"] is False
    with pytest.raises(ValueError, match="inlevering"):
        inl.controleer("run-x", "../opdracht.json", tmp_path)


def test_de_review_van_de_pilot_klopt_met_de_uitgebreide_kaart(tmp_path):
    controle = {"soort": "reviewer", "modus": "verschillen", "casus": "LB-07",
                "team": str(METING / "LB-07" / "teamverwachting.json"),
                "dossier": str(PILOT / "lb-07-beslistermijn" / "set.json"),
                "opname": str(METING / "LB-07" / "graafantwoorden.json")}
    review = json.loads((METING / "LB-07" / "review-verschillen.json").read_text(encoding="utf-8"))
    assert _inleveren(tmp_path, controle, review) == {"geldig": True, "fouten": []}


def test_de_tegenlezing_van_de_pilot_klopt(tmp_path):
    controle = {"soort": "reviewer", "modus": "tegenlezen", "casus": "LB-07",
                "dossier": str(PILOT / "lb-07-beslistermijn" / "set.json"),
                "formulier": str(METING / "LB-07" / "formulier-a.json")}
    lezing = json.loads((METING / "LB-07" / "tegenlezing.json").read_text(encoding="utf-8"))
    assert _inleveren(tmp_path, controle, lezing) == {"geldig": True, "fouten": []}


def test_de_reviewer_kent_de_plek_verkeerde_deelvraag():
    schema = json.loads(rv.REVIEW.read_text(encoding="utf-8"))
    assert "verkeerde_deelvraag" in schema["properties"]["oordelen"]["items"]["properties"]["plek"]["enum"]
