"""Waar een bepaling staat en hoe ze heet, uit de graaf in plaats van uit haar IRI.

De importer schrijft per knoop `bwb:vindplaats` ("Artikel 9, lid 1", "Artikel 9.2, onderdeel d") en per
onderdeel `bwb:inBepaling` (het lid, artikel, de divisie of bijlage waarin het staat), uit de echte boom.
Voor een wet zegt de IRI hetzelfde (`bronmodel.vindplaats`), maar voor een beleidsregel niet: de IRI
`…:BWBR0024096:artikel:9:o:d` hangt onder divisie 9.2, en `…divisie9%2FTekst%2FOnderdeel._4` onder een knoop
die `…:artikel:9` heet. Wie daar uit de IRI een naam of een ouder afleidt, zit ernaast.

Best-effort: een haperende graaf, of een graaf van vóór de importer die deze predicaten schreef, geeft een
lege plek – de aanroeper valt dan terug op de IRI. Een naam mag een antwoord nooit breken.
"""
from __future__ import annotations

import logging
from typing import Iterable

from .graph.queries import PREFIXES, _iri_veilig, is_bron_iri
from .graph.results import parse_select
from .ports import GraphPort

logger = logging.getLogger(__name__)

PER_QUERY = 100


def q_plekken(iris: list[str]) -> str:
    waarden = " ".join(f"<{_iri_veilig(i)}>" for i in sorted(set(iris)))
    return PREFIXES + f"""SELECT ?node (SAMPLE(?vp) AS ?vindplaats) (SAMPLE(?tt) AS ?titel) (SAMPLE(?bp) AS ?bepaling) WHERE {{
  VALUES ?node {{ {waarden} }}
  OPTIONAL {{ ?node bwb:vindplaats ?vp }}
  OPTIONAL {{ ?node a bwb:Divisie ; bwb:titel ?tt }}
  OPTIONAL {{ ?node bwb:inBepaling ?bp }}
}} GROUP BY ?node ORDER BY ?node"""


def plekken(graph: GraphPort, iris: Iterable[str]) -> dict[str, dict[str, str]]:
    """Per bron-IRI `{vindplaats, titel, bepaling}` zoals de graaf ze kent; een IRI zonder iets ervan
    staat er niet in. `titel` alleen bij een divisie: die draagt haar onderwerp in de titel ("Dagtekening
    aanslagbiljet"), een artikel niet."""
    gevraagd = sorted({i for i in iris if i and is_bron_iri(i)})
    uit: dict[str, dict[str, str]] = {}
    try:
        for start in range(0, len(gevraagd), PER_QUERY):
            for r in parse_select(graph.sparql(q_plekken(gevraagd[start:start + PER_QUERY]))):
                plek = {k: (r.get(k) or "").strip() for k in ("vindplaats", "titel", "bepaling")}
                if any(plek.values()):
                    uit[r["node"]] = plek
    except Exception:  # noqa: BLE001 – een naam mag het antwoord nooit breken
        logger.warning("plekken niet opgehaald", extra={"categorie": "technisch", "aantal": len(gevraagd)},
                       exc_info=True)
    return uit
