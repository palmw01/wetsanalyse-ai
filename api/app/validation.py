"""Canonieke JAS-klassenlijst — de enige bron voor de klassevalidatie in het annotatiedomein.

De waarden komen uit `jas_klassen.py`; het annotatiedomein (`routers/annotatie.py`) valideert de
klasse van een voorgesteld element hiertegen en de export gebruikt de volgorde en de labelkleuren.

> Dit was een runtime-import uit een script in de wetsanalyse-skill, waardoor het productie-image die
> skill moest meedragen om te kunnen starten. De skill draagt de methode, niet de code; de lijst
> staat daarom in `jas_klassen.py`.

> De vroegere brongetrouwheid-/schema-checks van de (verwijderde) `/v1/projects`-analyse-pijplijn
> stonden hier ook; die zijn weg. Brongetrouwheid wordt nu afgedwongen in graph-qa (grounding) en de
> frontend (`segmenteer`), niet server-side in de api.
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
