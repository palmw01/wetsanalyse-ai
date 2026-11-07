"""Waardensets die de jurist raken, aan beide kanten gelijk (E7).

Een waarde die de api erbij krijgt en de werkplek niet kent, geeft anders geen fout maar een verkeerde chip. De
bestanden worden als tekst gelezen, zodat dit ook rood wordt als alleen de andere kant wijzigt.
"""
from __future__ import annotations

import re

import pytest

from routeboek import FRONTEND, WORTEL

API = WORTEL / "api" / "app"
TYPES = FRONTEND / "lib" / "types.ts"
BRONSELECTIE = FRONTEND / "lib" / "bronselectie.ts"

#: naam in de api, bestand in de api, naam in de frontend, bestand in de frontend
SETS = [
    ("Lifecycle", "annotatie_v2_contracts.py", "Lifecycle", TYPES),
    ("LaagStatus", "annotatie_v2_contracts.py", "DocumentStatus", TYPES),
    ("Voortgang", "bronselectie_contracts.py", "Voortgang", BRONSELECTIE),
    ("KoppelRol", "begrip_contracts.py", "KoppelRol", TYPES),
    ("Beoordeling", "begrip_contracts.py", "KoppelBeoordeling", TYPES),
    ("BegripStatus", "begrip_contracts.py", "BegripStatus", TYPES),
]


def _enum(naam: str, bestand: str) -> set[str]:
    bron = (API / bestand).read_text(encoding="utf-8")
    blok = re.search(rf"^class {naam}\(str, Enum\):\n((?:[ \t]+.*\n|\n)+)", bron, re.M)
    assert blok, f"{naam} niet gevonden in {bestand}"
    return set(re.findall(r'^\s+\w+ = "([^"]+)"', blok.group(1), re.M))


def _union(naam: str, pad) -> set[str]:
    blok = re.search(rf"export type {naam} =([^;]+);", pad.read_text(encoding="utf-8"))
    assert blok, f"type {naam} niet gevonden in {pad.name}"
    return set(re.findall(r'"([^"]+)"', blok.group(1)))


@pytest.mark.parametrize("api_naam, bestand, ts_naam, ts_pad", SETS, ids=[s[0] for s in SETS])
def test_waardenset_is_gelijk(api_naam, bestand, ts_naam, ts_pad):
    assert _enum(api_naam, bestand) == _union(ts_naam, ts_pad)
