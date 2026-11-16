"""De ketenrooktest van graph-qa: `GET /health?keten=1` zegt of de graaf regelingen heeft (plan Lex Bench §20.5 stap 5).
Zonder parameter blijft `/health` de lichte liveness voor de probes, zonder graaf."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent.graafpeiling import graafpeiling
from fakes import FakeGraph

pytestmark = pytest.mark.risico("R01")

REGELINGEN = "?regeling\t?citeertitel\n<urn:bwb:BWBR0004770>\t\"Invorderingswet 1990\"\n"


class Kapot:
    def sparql(self, _q):
        raise RuntimeError("Repository inning doesn't exist")

    def close(self):
        pass


def test_de_peiling_onderscheidt_ok_leeg_en_onbereikbaar():
    assert graafpeiling(FakeGraph(result=REGELINGEN)) == "ok"
    assert graafpeiling(FakeGraph(result="?regeling\t?citeertitel\n")) == "leeg"
    assert graafpeiling(Kapot()) == "onbereikbaar"


@pytest.mark.parametrize("graaf,code,stand", [(FakeGraph(result=REGELINGEN), 200, "ok"),
                                              (FakeGraph(result="?regeling\t?citeertitel\n"), 503, "leeg"),
                                              (Kapot(), 503, "onbereikbaar")])
def test_health_met_keten_meldt_de_graaf(monkeypatch, graaf, code, stand):
    import api.main as hoofd
    from agent.adapters import graphdb_graph

    monkeypatch.setattr(graphdb_graph, "make_graph", lambda _s: graaf)
    r = TestClient(hoofd.app).get("/health?keten=1")
    assert (r.status_code, r.json()["graaf"]) == (code, stand)


def test_health_zonder_keten_raakt_de_graaf_niet(monkeypatch):
    import api.main as hoofd
    from agent.adapters import graphdb_graph

    def niet(_s):
        raise AssertionError("de liveness mag de graaf niet vragen")

    monkeypatch.setattr(graphdb_graph, "make_graph", niet)
    r = TestClient(hoofd.app).get("/health")
    assert r.status_code == 200 and "graaf" not in r.json()
