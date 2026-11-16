"""Gedeeld voor de hele suite.

De tests staan in een map per mechanisme (`tests/README.md`). De hulpmodules (`fakes`, `bron_fakes`) staan hier, en een
test leest soms een helper uit een test in een andere map (`from test_subagent import …`). Daarom gaan alle mappen op het
importpad, zodat dat niet afhangt van welk bestand pytest eerst verzamelde.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HIER = Path(__file__).resolve().parent
for _map in sorted(p for p in _HIER.iterdir() if p.is_dir() and any(p.glob("test_*.py"))):
    if str(_map) not in sys.path:
        sys.path.insert(0, str(_map))

from agent import narratie, procestoestand


@pytest.fixture(autouse=True)
def _denkproces_zonder_lege_plekken(monkeypatch):
    """Elke regel van het denkproces die een test laat maken, is heel: geen "(art. )", geen "None", geen dubbele spatie
    (`narratie.lege_plekken`; E2E Rekeningafspraken 16 nov 2026, D-1). Zo toetst de hele suite de vorm, voor elke route,
    elk profiel en elke bron, en niet één lijst voorbeelden."""
    monkeypatch.setattr(narratie, "STRIKT", True)


@pytest.fixture(autouse=True)
def _procestoestand_per_test():
    """Elke test begint en eindigt zonder procesbrede toestand (caches, de modelkeuze; `agent/procestoestand.py`).
    Anders hangt een uitkomst af van de volgorde: `test_sjablonen` faalde na `test_eval` (Lex Bench §14.1)."""
    procestoestand.reset()
    yield
    procestoestand.reset()
