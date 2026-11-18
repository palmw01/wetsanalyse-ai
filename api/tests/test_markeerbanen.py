"""Markeerbanen (optie B, voorstel-markeringen-en-diagrammen): dezelfde gevallen als `frontend/lib/markeerbanen.test.ts`,
zodat het rapport en de werkplek dezelfde banen tekenen."""
import json

import pytest

from app.config import PROJECT_ROOT
from app.markeerbanen import markeerbanen

PAD = PROJECT_ROOT / "frontend" / "lib" / "markeerbanen.vectoren.json"


def _gevallen():
    if not PAD.exists():
        return []
    return json.loads(PAD.read_text(encoding="utf-8"))["gevallen"]


@pytest.mark.skipif(not PAD.exists(), reason="frontend niet aanwezig (api-only image)")
@pytest.mark.parametrize("geval", _gevallen(), ids=lambda g: g["naam"])
def test_de_gedeelde_gevallen(geval):
    uit = markeerbanen(geval["lengte"], [tuple(x) for x in geval["spans"]])
    assert uit.aantal == geval["verwacht"]["aantal"]
    assert [[s.start, s.eind, s.vlak, [list(b) for b in s.banen], list(s.eindigt)] for s in uit.stukken] \
        == geval["verwacht"]["stukken"]


def test_wie_een_vlak_heeft_heeft_geen_baan_en_alles_is_te_zien():
    spans = [("a", 0, 8), ("b", 4, 12), ("c", 4, 12), ("d", 10, 15)]
    uit = markeerbanen(20, spans)
    vlakken = {s.vlak for s in uit.stukken if s.vlak}
    assert not vlakken & set(uit.baan)
    assert vlakken | set(uit.baan) == {"a", "b", "c", "d"}


def test_sleutels_mogen_getallen_zijn():
    uit = markeerbanen(10, [(1, 0, 10), (2, 2, 4)])
    assert uit.baan == {1: 0}
    assert [s.vlak for s in uit.stukken] == [None, 2, None]
