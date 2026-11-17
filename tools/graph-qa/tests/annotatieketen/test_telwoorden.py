"""Telwoorden zijn een opbouwregel, geen lijst.

De vaste lijst kende "zes" en "twintig" maar niet "eenentwintig": "De termijn bedraagt zes weken"
gaf een Tijdsaanduiding, "eenentwintig dagen" niet. Cijfers en woorden horen dezelfde functie te
krijgen.
"""
from __future__ import annotations

import re

import pytest

from agent.jas_pipeline.taal.telwoorden import TELWOORD, waarde


@pytest.mark.parametrize(("tekst", "getal"), [
    ("zes", 6), ("één", 1), ("een", 1), ("elf", 11), ("negentien", 19), ("twintig", 20),
    ("eenentwintig", 21), ("tweeëntwintig", 22), ("tweeentwintig", 22), ("negenennegentig", 99),
    ("honderd", 100), ("honderdtwintig", 120), ("driehonderdvijfenzestig", 365),
    ("duizend", 1000), ("tweeduizendvijftig", 2050), ("vijftienduizend", 15000), ("nul", 0),
    ("14", 14), ("Eenentwintig", 21),
])
def test_waarde(tekst, getal):
    assert waarde(tekst) == getal


@pytest.mark.parametrize("tekst", ["zesweken", "drieëntwintigste", "twintigtal", "eentje", "half", ""])
def test_geen_telwoord(tekst):
    assert waarde(tekst) is None


def test_patroon_en_waarde_zijn_het_eens():
    """Wat het patroon herkent, kan `waarde` omrekenen – en omgekeerd: één opbouwregel."""
    heel = re.compile(rf"^{TELWOORD}$", re.IGNORECASE)
    for n in [*range(0, 130), 365, 999, 1000, 2050, 99999]:
        woord = _als_woord(n)
        assert heel.match(woord), woord
        assert waarde(woord) == n, woord


_EEN = ["nul", "een", "twee", "drie", "vier", "vijf", "zes", "zeven", "acht", "negen", "tien", "elf",
        "twaalf", "dertien", "veertien", "vijftien", "zestien", "zeventien", "achttien", "negentien"]
_TIG = {2: "twintig", 3: "dertig", 4: "veertig", 5: "vijftig", 6: "zestig", 7: "zeventig", 8: "tachtig",
        9: "negentig"}


def _als_woord(n: int) -> str:
    if n >= 1000:
        voor, na = divmod(n, 1000)
        return (_als_woord(voor) if voor > 1 else "") + "duizend" + (_als_woord(na) if na else "")
    if n >= 100:
        voor, na = divmod(n, 100)
        return (_als_woord(voor) if voor > 1 else "") + "honderd" + (_als_woord(na) if na else "")
    if n < 20:
        return _EEN[n]
    tien, een = divmod(n, 10)
    if not een:
        return _TIG[tien]
    eerste = _EEN[een]
    return eerste + ("ën" if eerste.endswith("e") else "en") + _TIG[tien]
