"""WP-D: schema-introspectie draait de introspectiequery's en cachet ze."""
from __future__ import annotations

import pytest

from agent.graph import schema
from fakes import FakeGraph


@pytest.fixture(autouse=True)
def _clear_cache():
    schema.reset_cache()
    yield
    schema.reset_cache()


def test_graph_schema_bevat_tellingen_vocabulaire_en_regelingen():
    g = FakeGraph(result="DATA")
    out = schema.graph_schema(g)
    assert "AANTALLEN PER TYPE" in out
    assert "REGELINGEN" in out
    assert "VOCABULAIRE" in out, "zonder de T-Box moet het model predicaatnamen raden"
    assert "IRI-PATRONEN" in out
    assert len(g.queries) == 3  # count_by_type + ontologie + list_regelingen


def test_graph_schema_wordt_gecachet():
    g = FakeGraph(result="DATA")
    schema.graph_schema(g)
    schema.graph_schema(g)  # tweede aanroep
    assert len(g.queries) == 3  # graaf niet opnieuw geraakt


def test_de_cache_verloopt():
    """Een eeuwige cache liegt: de import-job draait wekelijks, de container leeft langer.

    Dit was geen theoretisch risico – de tellingen zijn juist de reden dat deze tool bestaat, en
    een bevroren getal is erger dan geen getal omdat het er gezaghebbend uitziet.
    """
    g = FakeGraph(result="DATA")
    schema.graph_schema(g)
    schema._gezet_op -= schema.TTL_SECONDEN + 1
    schema.graph_schema(g)
    assert len(g.queries) == 6, "na de TTL moet de graaf opnieuw worden bevraagd"
