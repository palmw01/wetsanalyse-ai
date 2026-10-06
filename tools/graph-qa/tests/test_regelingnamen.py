"""De naam van een regeling in de bronnenlijst: één query per beurt, en een fout kost alleen de naam."""
from __future__ import annotations

import pytest

from agent import regelingnamen as rn
from agent.models import Source
from agent.provenance import collect_sources
from tests.fakes import FakeGraph

_TSV = (
    "?r\t?citeertitel\t?opschrift\n"
    "<urn:bwb:BWBR0004770>\t\"Invorderingswet 1990\"@nl\t\"Wet van 30 mei 1990\"@nl\n"
    "<urn:bwb:BWBR0004766>\t\t\"Uitvoeringsregeling Invorderingswet 1990\"@nl\n"
)


@pytest.fixture(autouse=True)
def _lege_cache():
    rn._CACHE.clear()
    yield
    rn._CACHE.clear()


def test_namen_in_een_query_met_terugval_op_opschrift():
    graph = FakeGraph(result=_TSV)
    namen = rn.regelingnamen(graph, ["BWBR0004770", "BWBR0004766", "BWBR0004770"])
    assert namen == {"BWBR0004770": "Invorderingswet 1990",
                     "BWBR0004766": "Uitvoeringsregeling Invorderingswet 1990"}
    assert len(graph.queries) == 1
    # Uit de cache: geen tweede query.
    rn.regelingnamen(graph, ["BWBR0004770"])
    assert len(graph.queries) == 1


def test_bronnen_krijgen_regeling_en_een_regeling_haar_naam_als_label():
    sources = collect_sources([("t", "urn:bwb:BWBR0004770:artikel:9 en BWBR0004766")])
    rn.met_regelingnamen(FakeGraph(result=_TSV), sources)
    assert [(s.label, s.regeling) for s in sources] == [
        ("Artikel 9", "Invorderingswet 1990"),
        ("Uitvoeringsregeling Invorderingswet 1990", "Uitvoeringsregeling Invorderingswet 1990"),
    ]


def test_een_fout_kost_alleen_de_naam():
    def kapot(_q: str) -> str:
        raise RuntimeError("graaf weg")

    sources = collect_sources([("t", "urn:bwb:BWBR0004770:artikel:9")])
    rn.met_regelingnamen(FakeGraph(results=kapot), sources)
    assert (sources[0].label, sources[0].regeling) == ("Artikel 9", None)


def test_geen_bwb_geen_query():
    graph = FakeGraph(result=_TSV)
    rn.met_regelingnamen(graph, [Source(label="x", uri="https://example.org")])
    assert graph.queries == []
