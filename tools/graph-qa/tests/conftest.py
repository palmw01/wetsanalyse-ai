"""Gedeeld voor de hele suite."""
from __future__ import annotations

import pytest

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
