"""De meting van de proef `model_kiest` (pilot LB3): welke sets ze meet en dat ze zonder commit niet start. Zonder model
en zonder graaf; de meting zelf draait alleen met akkoord, via `azure-infra` → `eval` → `bronselectie_model`."""
from __future__ import annotations

import pytest

from eval import bronselectie_model_meting as m


def test_de_sets_hebben_deelvragen_en_een_verwachting():
    sets = m.sets(m.lezer(True))
    assert [n for n, _ in sets] == [*m.SETS, *m.CASUSSEN]
    for naam, s in sets:
        assert s["deelvragen"], naam
        assert s["verwacht"], naam
        assert {v["deelvraag"] for v in s["verwacht"]} <= set(range(len(s["deelvragen"]))), naam


def test_zonder_commit_start_de_meting_niet(monkeypatch):
    monkeypatch.delenv("LEX_REVISIE", raising=False)
    with pytest.raises(SystemExit, match="LEX_REVISIE"):
        m.lezer(False)


def test_de_routes_bestaan():
    assert m.STANDAARD in m.ROUTES


def test_geen_eval_rekent_zelf_de_wortel_uit():
    """In het image staat een eval op `/app/eval/`: vier mappen omhoog bestaat daar niet en brak de meting bij het
    importeren (17 nov 2026, IndexError). De wortel komt uit één helper, `eval/wortel.py`."""
    from pathlib import Path

    evals = Path(__file__).resolve().parents[2] / "eval"
    fout = [p.name for p in evals.glob("*.py") if p.name != "wortel.py" and "parents[3]" in p.read_text(encoding="utf-8")]
    assert not fout, f"reken de wortel niet zelf uit, gebruik eval.wortel: {fout}"
