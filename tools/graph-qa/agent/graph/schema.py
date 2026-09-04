"""
Schema-introspectie van de kennisgraaf, met in-proces cache.

Vervangt de hardgecodeerde omvang/regelingen uit de oude system-prompt: het model
vraagt de live tellingen op via de graph_schema-tool i.p.v. te vertrouwen op
bevroren cijfers die verouderen zodra de graaf groeit.

Sinds 4 sep 2026 draagt het antwoord ook de **T-Box**: welke klassen en predicaten er bestaan en
wat ze betekenen. Die stond al in de graaf (`urn:bwb:graph:ontologie`, met `rdfs:label` en
`rdfs:comment`), maar nergens waar het model hem kon lezen — dus moest het bij `raw_sparql`
predicaatnamen raden, en een geraden predicaat matcht niets **zonder foutmelding**. Dat is dezelfde
stille onvolledigheid als de `bwb:bevat`-bug, alleen dan veroorzaakt door het model.

De cache heeft een TTL. Hij was proces-globaal en werd nooit ongeldig, terwijl de import-job
wekelijks draait en de container maandenlang leeft: de tellingen konden dus willekeurig ver
achterlopen op de graaf, en juist die cijfers zijn de reden dat deze tool bestaat.
"""
from __future__ import annotations

import time

from . import queries
from ..ports import GraphPort

# Een uur. Kort genoeg dat een import binnen een werkdag zichtbaar wordt, lang genoeg dat een
# gesprek met tien graph_schema-aanroepen er één betaalt.
TTL_SECONDEN = 3600.0

_cache: str | None = None
_gezet_op: float = 0.0


def reset_cache() -> None:
    """Leeg de cache (voor tests)."""
    global _cache, _gezet_op
    _cache = None
    _gezet_op = 0.0


def graph_schema(graph: GraphPort) -> str:
    """Geef een (gecachete) samenvatting van omvang, vocabulaire en regelingen van de graaf."""
    global _cache, _gezet_op
    if _cache is not None and (time.monotonic() - _gezet_op) < TTL_SECONDEN:
        return _cache

    counts = graph.sparql(queries.count_by_type())
    vocab = graph.sparql(queries.ontologie())
    regelingen = graph.sparql(queries.list_regelingen())

    _cache = (
        "AANTALLEN PER TYPE (eigen IRI-ruimte, sameAs-tweelingen niet meegeteld):\n"
        f"{counts}\n\n"
        "VOCABULAIRE (klassen, relaties en eigenschappen; gebruik deze namen in raw_sparql):\n"
        f"{vocab}\n\n"
        "IRI-PATRONEN:\n"
        f"  regeling  {queries.NS}{{BWB-id}}\n"
        f"  artikel   {queries.NS}{{BWB-id}}:artikel:{{nr}}\n"
        f"  lid       {queries.NS}{{BWB-id}}:artikel:{{nr}}:lid:{{nr}}\n"
        f"  Filter altijd op STRSTARTS(STR(?s), \"{queries.NS}\") – anders tel je de\n"
        "  owl:sameAs-tweelingen van wetten.overheid.nl dubbel.\n\n"
        "REGELINGEN IN DE GRAAF:\n"
        f"{regelingen}"
    )
    _gezet_op = time.monotonic()
    return _cache
