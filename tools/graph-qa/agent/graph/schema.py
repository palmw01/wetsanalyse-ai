"""
Schema-introspectie van de kennisgraaf, met in-proces cache.

Geen hardgecodeerde omvang/regelingen in de system-prompt: het model vraagt de live tellingen
op via de graph_schema-tool i.p.v. te vertrouwen op bevroren cijfers die verouderen zodra de
graaf groeit.

Het antwoord draagt ook de **T-Box**: welke klassen en predicaten er bestaan en wat ze betekenen.
Die staat in de graaf (`urn:bwb:graph:ontologie`, met `rdfs:label` en `rdfs:comment`); zonder
haar moet het model bij `raw_sparql` predicaatnamen raden, en een geraden predicaat matcht niets
**zonder foutmelding** – stille onvolledigheid, veroorzaakt door het model.

De cache heeft een TTL: de import-job draait wekelijks en de container leeft maandenlang, dus een
cache die nooit ongeldig wordt laat de tellingen willekeurig ver achterlopen op de graaf, en juist
die cijfers zijn de reden dat deze tool bestaat.
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
        "  owl:sameAs-tweelingen van wetten.overheid.nl dubbel.\n"
        # De JAS-annotatielagen staan in dezelfde graaf. Ze dragen BWB-id's in
        # hun IRI en citeren wettekst in oa:exact, dus een vrije query kan ze tegenkomen.
        "  urn:jas:… zijn JAS-annotaties: afgeleide duiding door Lex en juristen, GEEN wettekst\n"
        "  en GEEN vindplaats. Citeer ze nooit als bron; de wet staat alleen onder "
        f"{queries.NS}.\n\n"
        "REGELINGEN IN DE GRAAF:\n"
        f"{regelingen}"
    )
    _gezet_op = time.monotonic()
    return _cache
