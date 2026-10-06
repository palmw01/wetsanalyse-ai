"""Nederlandse hoofdtelwoorden: herkennen als patroon en omrekenen naar een getal.

De regels kenden een vaste woordenlijst (één … twintig, de tientallen, honderd). Een samenstelling
viel erbuiten: "De termijn bedraagt zes weken" gaf een Tijdsaanduiding, "eenentwintig dagen" niet.
Zo'n gat hangt niet af van juridische interpretatie maar van de spelling, en een lijst kan het niet
dichten – vandaar de opbouwregel hieronder.

Bereik: 0 t/m 999 999 in woorden ("eenentwintig", "tweeëntwintig", "driehonderdvijftig",
"tweeduizend"), plus cijfers. Breuken ("anderhalf", "een half") en rangtelwoorden horen hier niet:
die hebben een andere functie en een eigen patroon (`verwijzingen.RANGTELWOORD`).
"""
from __future__ import annotations

import re

_EENHEDEN = {"een": 1, "één": 1, "twee": 2, "drie": 3, "vier": 4, "vijf": 5, "zes": 6, "zeven": 7,
             "acht": 8, "negen": 9}
_TIENERS = {"tien": 10, "elf": 11, "twaalf": 12, "dertien": 13, "veertien": 14, "vijftien": 15,
            "zestien": 16, "zeventien": 17, "achttien": 18, "negentien": 19}
_TIENTALLEN = {"twintig": 20, "dertig": 30, "veertig": 40, "vijftig": 50, "zestig": 60,
               "zeventig": 70, "tachtig": 80, "negentig": 90}


def _alt(woorden) -> str:
    return "|".join(sorted(woorden, key=len, reverse=True))


_E, _T, _X = _alt(_EENHEDEN), _alt(_TIENERS), _alt(_TIENTALLEN)
# "eenentwintig", "tweeëntwintig" (ook zonder trema geschreven), "vierentachtig". Na honderd en
# duizend volgt het rest-getal er direct achter ("honderdtwintig", "tweeduizendvijftig").
_ONDER_HONDERD = rf"(?:(?:{_E})(?:ën|en)(?:{_X})|{_X}|{_T}|{_E})"
_ONDER_DUIZEND = rf"(?:(?:{_E})?honderd{_ONDER_HONDERD}?|{_ONDER_HONDERD})"
_WOORD = rf"(?:{_ONDER_DUIZEND}?duizend{_ONDER_DUIZEND}?|{_ONDER_DUIZEND}|nul)"

#: Het patroon voor `{TELWOORD}` in de regels: cijfers of een telwoord in woorden.
TELWOORD = rf"(?:\d+|{_WOORD})"

_HEEL = re.compile(rf"^{_WOORD}$", re.IGNORECASE)
_SAMEN = re.compile(rf"^({_E})(?:ën|en)({_X})$")
_ALLE = {**_EENHEDEN, **_TIENERS, **_TIENTALLEN}


def _reken(t: str) -> int:
    if not t:
        return 0
    for woord, factor in (("duizend", 1000), ("honderd", 100)):
        if woord in t:
            voor, _, na = t.partition(woord)
            return factor * (_reken(voor) if voor else 1) + _reken(na)
    if t in _ALLE:
        return _ALLE[t]
    m = _SAMEN.match(t)
    return _EENHEDEN[m.group(1)] + _TIENTALLEN[m.group(2)]


def waarde(tekst: str) -> int | None:
    """Het getal achter een telwoord ("eenentwintig" → 21, "14" → 14); None als het er geen is."""
    t = tekst.strip().lower()
    if t.isdigit():
        return int(t)
    if not _HEEL.match(t):
        return None
    return 0 if t == "nul" else _reken(t)
