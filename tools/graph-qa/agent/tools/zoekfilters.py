"""Wat de zoektools van de bronconnectors gemeen hebben bij hun filters (ADR-013): een datum in de vorm van de jurist.

Kamerstukken, Rechtspraak en Staatsblad en Staatscourant nemen alle drie `vanaf`/`tot` aan als JJJJ, JJJJ-MM of
JJJJ-MM-DD. Eén functie, zodat "2024-02" overal op 29 februari eindigt (Rechtspraak maakte er eerst 2024-02-31 van).
"""
from __future__ import annotations

import calendar
import re
from datetime import date

_DATUM_RE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")


def datum(waarde: str, *, eind: bool) -> str:
    """'2024' → 2024-01-01 (of 2024-12-31 als eind), '2024-06' → de eerste of laatste dag, '2024-06-01' blijft.
    Een waarde in een andere vorm, of een datum die niet bestaat, is een `ValueError`."""
    m = _DATUM_RE.fullmatch((waarde or "").strip())
    if not m:
        raise ValueError(waarde)
    jaar, maand, dag = int(m.group(1)), m.group(2), m.group(3)
    if dag:
        return date(jaar, int(maand), int(dag)).isoformat()
    if maand:
        return date(jaar, int(maand), calendar.monthrange(jaar, int(maand))[1] if eind else 1).isoformat()
    return date(jaar, 12, 31).isoformat() if eind else date(jaar, 1, 1).isoformat()
