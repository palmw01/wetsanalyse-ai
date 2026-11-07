"""Kleine taalkundige lijsten die api en agent allebei lezen; geen beleid.

Elke gebruiker neemt zijn eigen stuk van een lijst (`RANGTELWOORDEN[:12]`): hoe ver een herkenner telt is zijn
keuze, de spelling en de volgorde staan hier één keer. De BWB-importer gebruikt dit pakket niet en houdt een eigen
kopie; een drifttest in `tools/bwb-import/tests` bewaakt die.
"""
from __future__ import annotations

import re
import unicodedata

#: De rangtelwoorden van "eerste" tot "vijfentwintigste", op volgorde: `RANGTELWOORDEN[n - 1]` hoort bij n.
RANGTELWOORDEN = (
    "eerste", "tweede", "derde", "vierde", "vijfde", "zesde", "zevende", "achtste", "negende", "tiende",
    "elfde", "twaalfde", "dertiende", "veertiende", "vijftiende", "zestiende", "zeventiende", "achttiende",
    "negentiende", "twintigste", "eenentwintigste", "tweeëntwintigste", "drieëntwintigste", "vierentwintigste",
    "vijfentwintigste",
)


def rangnummers(tot: int) -> dict[str, int]:
    """{"eerste": 1, …} tot en met het rangtelwoord van `tot`."""
    return {woord: n for n, woord in enumerate(RANGTELWOORDEN[:tot], start=1)}


def normaliseer_vraag(vraag: str) -> str:
    """Zonder hoofdletters, diakrieten en leestekens: "Wanneer is een aanslag invorderbaar?" en
    "wanneer is een aanslag invorderbaar" zijn dezelfde vraag. De api en de agent vergelijken deelvragen hiermee,
    dus beide kanten moeten dezelfde sleutel afleiden."""
    t = unicodedata.normalize("NFKD", vraag.casefold())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", t).split())


#: Een bron-IRI zoals het bronmodel hem kent: `urn:bwb:<BWB-id>`, eventueel met een pad erachter. Groep 1 is het
#: BWB-id. Gebruik `fullmatch`. Bewust ruimer dan `graph.queries._BRON_IRI_RE` in graph-qa: die bewaakt wat er in
#: een SPARQL-query mag, deze wat een bronnode kan heten.
BRON_IRI_PATROON = r"urn:bwb:(BWB[RV]\d+)(?::[^<>\s\"{}|^`\\]*)?"
BRON_IRI = re.compile(BRON_IRI_PATROON)
