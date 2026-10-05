"""Conceptcasussen (docs/wetsanalyse/referentieset/concept/): ook een voorstel is brongetrouw."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from agent.jas_klassen import GELDIGE_JAS_KLASSEN

MAP = Path(__file__).resolve().parents[3] / "docs" / "wetsanalyse" / "referentieset" / "concept"
CASUSSEN = sorted(MAP.glob("*.json"))


@pytest.mark.parametrize("pad", CASUSSEN, ids=lambda p: p.stem)
def test_conceptcasus_is_letterlijk_en_niet_beoordeeld(pad):
    c = json.loads(pad.read_text(encoding="utf-8"))
    tekst = c["tekst"]
    assert hashlib.sha256(tekst.encode()).hexdigest() == c["tekst_sha256"]
    assert c["referentie_status"] == "provisional", "een concept is nooit adjudicated"
    gids = {g["gid"] for g in c["gold"]}
    assert len(gids) == len(c["gold"])
    for g in c["gold"]:
        s, e = g["start"], g["eind"]
        assert tekst[s:e] == g["tekst"], g["gid"]
        assert (s == 0 or not tekst[s - 1].isalnum()) and (e == len(tekst) or not tekst[e].isalnum()), g["gid"]
        assert g["klasse"] in GELDIGE_JAS_KLASSEN, g["gid"]
        assert g["adjudicatie"] is None
        assert all(r["doel"] in gids for r in g["relaties"]), g["gid"]


def test_er_is_minstens_een_conceptcasus():
    assert CASUSSEN
