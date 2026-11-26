"""Padcontrole voor paden en argumenten die van buiten komen (CLI, omgeving).

Een script dat een pad uit `argv` leest en opent, kan door wie het aanroept – ook een agent – overal op de schijf
lezen of schrijven. `veilig_pad` laat alleen een pad toe dat, na het oplossen van `..` en symlinks, binnen een van
de toegestane basismappen valt: de map van waaruit het script draait, de thuismap en de tijdelijke map. Een geldig
pad komt er ongewijzigd uit (als absoluut pad); `/etc/passwd` of `../../..` naar buiten wordt geweigerd.

`veilig_argument` doet hetzelfde voor een waarde die als argument naar een extern commando gaat: alleen een
onschuldige vorm, en nooit iets dat met `-` begint (dan zou het als optie gelezen worden).

Dit bestand staat in vier onderdelen in identieke vorm (`tools/graph-qa/eval/`, `tools/bwb-import/app/`,
`deploy/azure/`, `scripts/`), omdat die geen gedeeld pakket hebben. `tests/poort/test_padcontrole.py` bewaakt dat
de kopieën gelijk blijven en toetst het gedrag.
"""
from __future__ import annotations

import argparse
import os
import re
import tempfile
from collections.abc import Iterable
from pathlib import Path

#: Een argument voor een extern commando: letters, cijfers en `._:/@=+-`, niet beginnend met `-`.
ARGUMENT = re.compile(r"^[A-Za-z0-9_.:/@=+][A-Za-z0-9_.:/@=+-]*$")


class OnveiligPad(argparse.ArgumentTypeError, ValueError):
    """Een pad of argument dat buiten de toegestane vorm valt. Ook een ValueError, en argparse toont de melding."""


def basismappen() -> list[str]:
    """De mappen waarbinnen een pad van buiten mag vallen, canoniek. De wortel van het bestandssysteem telt nooit als
    basismap (een container zet `HOME` soms op `/`): dan zou elk pad passen."""
    mappen = (os.path.realpath(m) for m in (os.getcwd(), os.path.expanduser("~"), tempfile.gettempdir()))
    return [m for m in mappen if os.path.dirname(m) != m]


def veilig_pad(pad: str | os.PathLike[str], basis: Iterable[str | os.PathLike[str]] | None = None) -> Path:
    """Het canonieke pad van `pad`, als het binnen een basismap valt; anders `OnveiligPad`."""
    opgelost = os.path.realpath(os.path.expanduser(os.fspath(pad)))
    toegestaan = [os.path.realpath(os.fspath(b)) for b in basis] if basis is not None else basismappen()
    for map_ in toegestaan:
        if opgelost == map_ or opgelost.startswith(map_.rstrip(os.sep) + os.sep):
            return Path(opgelost)
    raise OnveiligPad(f"pad {os.fspath(pad)!r} valt buiten de toegestane mappen")


def veilig_argument(waarde: str, patroon: re.Pattern[str] = ARGUMENT) -> str:
    """`waarde` als die de onschuldige vorm heeft; anders `OnveiligPad`."""
    if not patroon.match(waarde):
        raise OnveiligPad(f"argument {waarde!r} heeft geen toegestane vorm")
    return waarde
