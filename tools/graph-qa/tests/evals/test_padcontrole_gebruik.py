"""De eval-scripts openen een pad van de CLI alleen via `eval.padcontrole.veilig_pad` (Sonar S8707/S8705).

Het gedrag van de helper toetst `tests/poort/test_padcontrole.py`; hier dat de scripts hem gebruiken, dat een geldig pad
werkt zoals altijd, en dat een pad naar buiten geweigerd wordt.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval import adjudicatie, centrale_agent_sets, extern_dossier, vergelijk_rapporten
from eval.padcontrole import OnveiligPad

GRAPHQA = Path(__file__).resolve().parents[2]
#: De scripts met een melding van Sonar; elk opent zijn CLI-paden via de helper.
GEBRUIKERS = [
    "eval/adjudicatie.py", "eval/baseline_deelmeting.py", "eval/centrale_agent_sets.py", "eval/centrale_agent_vat.py",
    "eval/compare_pipelines.py", "eval/detector_audit.py", "eval/extern_bibliotheek.py", "eval/extern_dossier.py",
    "eval/invordering_proef.py", "eval/invordering_snapshotherstel.py", "eval/kandidaat_eval.py",
    "eval/laagrapport.py", "eval/lex_bench_review.py", "eval/lex_bench_team.py", "eval/run_eval.py",
    "eval/taal_benchmark.py", "eval/vergelijk_rapporten.py", "scripts/blind_formulier.py",
]


@pytest.mark.parametrize("pad", GEBRUIKERS)
def test_het_script_gebruikt_de_padcontrole(pad):
    assert "veilig_pad(" in (GRAPHQA / pad).read_text(encoding="utf-8")


def test_een_geldig_pad_leest_zoals_altijd(tmp_path):
    bestand = tmp_path / "ruw.jsonl"
    bestand.write_text('{"a": 1}\n# commentaar\n{"b": 2}\n', encoding="utf-8")
    assert centrale_agent_sets._lees(bestand) == [{"a": 1}, {"b": 2}]
    (tmp_path / "x.json").write_text('{"casus_id": "X"}', encoding="utf-8")
    assert adjudicatie._laad(str(tmp_path / "x.json")) == {"casus_id": "X"}


@pytest.mark.parametrize("pad", ["/etc/passwd", "/proc/self/environ"])
def test_een_pad_naar_buiten_wordt_niet_gelezen(pad):
    with pytest.raises(OnveiligPad):
        centrale_agent_sets._lees(Path(pad))
    with pytest.raises(OnveiligPad):
        adjudicatie._laad(pad)
    with pytest.raises(OnveiligPad):
        extern_dossier.lees_confluence([Path(pad)])


def test_een_rapport_gaat_niet_naar_buiten(tmp_path, monkeypatch):
    voor, na = tmp_path / "voor.json", tmp_path / "na.json"
    for p in (voor, na):
        p.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(vergelijk_rapporten, "vergelijk", lambda a, b: {})
    monkeypatch.setattr(vergelijk_rapporten, "markdown", lambda v: "tekst")
    monkeypatch.setattr("sys.argv", ["vergelijk_rapporten", str(voor), str(na), "--md", str(tmp_path / "r.md")])
    vergelijk_rapporten.main()
    assert (tmp_path / "r.md").read_text(encoding="utf-8") == "tekst"
    monkeypatch.setattr("sys.argv", ["vergelijk_rapporten", str(voor), str(na), "--md", "/etc/wa-rapport.md"])
    with pytest.raises(OnveiligPad):
        vergelijk_rapporten.main()
