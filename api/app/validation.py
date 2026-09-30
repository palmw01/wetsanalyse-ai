"""Canonieke JAS-klassenlijst – de enige bron voor de klassevalidatie in het annotatiedomein.

De waarden komen uit `jas_klassen.py`; het annotatiedomein valideert de klasse van een element
hiertegen. De lijst staat in de api zelf en niet in de wetsanalyse-skill: het productie-image hoort
geen skill mee te dragen om te kunnen starten.

> **Of een fragment letterlijk in de wettekst staat** toetsen graph-qa (grounding) en de frontend
> (`segmenteer`); de api heeft de wettekst niet. Wat de api wél toetst – dat een anker exact het
> fragment van de bronnode aanwijst – staat in `annotatie_v2_store.valideer`.
"""

from __future__ import annotations

from .jas_klassen import (
    GELDIGE_JAS_KLASSEN,
    JAS_KLASSE_KLEUREN,
    JAS_KLASSEN_VOLGORDE,
    JAS_TEKSTKLEUR,
    jas_sorteersleutel,
)

__all__ = [
    "GELDIGE_JAS_KLASSEN",
    "JAS_KLASSEN_VOLGORDE",
    "JAS_KLASSE_KLEUREN",
    "JAS_TEKSTKLEUR",
    "jas_sorteersleutel",
]
