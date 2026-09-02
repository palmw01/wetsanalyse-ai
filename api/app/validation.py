"""Canonieke JAS-klassenlijst – de enige bron voor de klassevalidatie in het annotatiedomein.

De waarden komen uit `jas_klassen.py`; het annotatiedomein (`routers/annotatie.py`) valideert de
klasse van een voorgesteld element hiertegen en de export gebruikt de volgorde en de labelkleuren.

> Dit was een runtime-import uit een script in de wetsanalyse-skill, waardoor het productie-image die
> skill moest meedragen om te kunnen starten. De skill draagt de methode, niet de code; de lijst
> staat daarom in `jas_klassen.py`.

> De vroegere brongetrouwheid-/schema-checks van de (verwijderde) `/v1/projects`-analyse-pijplijn
> stonden hier ook; die zijn weg. **Of een fragment letterlijk in de wettekst staat** wordt
> afgedwongen in graph-qa (grounding) en de frontend (`segmenteer`) – de api heeft de wettekst niet,
> die zit in GraphDB.
>
> Dat betekende tot 2 sep 2026 dat de api álles op zijn beloop liet behalve de klasse hierboven, en
> dat is een trust boundary op de verkeerde plek: de api is de partij die vastlegt. Wat hij zonder de
> graaf wél kan toetsen – de samenhang tussen een fragment en zijn anker – staat nu in
> `annotatie_validatie.py`.
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
