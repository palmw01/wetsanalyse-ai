"""De slotregel van de api en die van de werkplek draaien op dezelfde gevallen (E2)."""
import json
from pathlib import Path

import pytest

from app.annotatie_v2_store import slot_van

GEVALLEN = json.loads((Path(__file__).resolve().parents[2] / "frontend" / "lib" / "slotregel.json").read_text("utf-8"))


@pytest.mark.parametrize("geval", GEVALLEN, ids=lambda g: g["geval"])
def test_slotregel(geval):
    assert slot_van(geval["element"], geval["laag_status"]) == geval["slot"]
