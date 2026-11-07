"""`bereik_van` loopt elke knoop één keer: dezelfde uitkomst als per knoop de hele keten, zonder het kwadraat."""
import time

import pytest
from fastapi import HTTPException

from app.annotatie_v2_store import bereik_van, keten


def _stand(nodes: dict, doel: str = "w") -> dict:
    return {"doel": {"bron_iri": doel}, "nodes": {i: {"bron_iri": i, "parent_iri": p} for i, p in nodes.items()}}


BOOM = {"w": None, "a1": "w", "a2": "w", "l1": "a1", "l2": "a1", "o1": "l1"}


@pytest.mark.parametrize("iri", list(BOOM))
def test_gelijk_aan_de_keten_per_knoop(iri):
    stand = _stand(BOOM)
    assert bereik_van(stand, iri) == {k for k in BOOM if iri in keten(stand["nodes"], k)}


def test_zonder_iri_het_doel():
    assert bereik_van(_stand(BOOM, "a1")) == {"a1", "l1", "l2", "o1"}


def test_onbekende_knoop_is_404():
    with pytest.raises(HTTPException) as fout:
        bereik_van(_stand(BOOM), "x")
    assert fout.value.status_code == 404


@pytest.mark.parametrize("nodes", [
    {"w": None, "a": "weg"},                   # ouder ontbreekt
    {"w": None, "a": "b", "b": "a"},           # cyclus naast de boom
    {"w": "weg"},                              # zelfs het doel zelf hangt los
])
def test_onvolledige_structuur_is_422(nodes):
    with pytest.raises(HTTPException) as fout:
        bereik_van(_stand(nodes))
    assert fout.value.status_code == 422


def test_blijft_lineair_op_een_lange_regeling():
    """Een diepe keten van 20.000 knopen: kwadratisch duurt dit minuten, lineair ruim onder de seconde."""
    nodes = {"w": None, **{f"k{i}": (f"k{i - 1}" if i else "w") for i in range(20_000)}}
    start = time.perf_counter()
    assert len(bereik_van(_stand(nodes))) == 20_001
    assert time.perf_counter() - start < 2
