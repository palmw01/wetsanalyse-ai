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
