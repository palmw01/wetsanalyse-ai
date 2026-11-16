"""Gedeeld voor de hele suite."""
from __future__ import annotations

import pytest

from agent import narratie


@pytest.fixture(autouse=True)
def _denkproces_zonder_lege_plekken(monkeypatch):
    """Elke regel van het denkproces die een test laat maken, is heel: geen "(art. )", geen "None", geen dubbele spatie
    (`narratie.lege_plekken`; E2E Rekeningafspraken 16 nov 2026, D-1). Zo toetst de hele suite de vorm, voor elke route,
    elk profiel en elke bron, en niet één lijst voorbeelden."""
    monkeypatch.setattr(narratie, "STRIKT", True)
