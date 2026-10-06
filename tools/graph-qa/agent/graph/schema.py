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
from typing import Any

from . import queries
from .results import parse_select
from ..ports import GraphPort

# Een uur. Kort genoeg dat een import binnen een werkdag zichtbaar wordt, lang genoeg dat een
# gesprek met tien graph_schema-aanroepen er één betaalt.
TTL_SECONDEN = 3600.0

_cache: dict[str, Any] | None = None
_gezet_op: float = 0.0


def reset_cache() -> None:
    """Leeg de cache (voor tests)."""
    global _cache, _gezet_op
    _cache = None
    _gezet_op = 0.0


def graph_schema(graph: GraphPort) -> dict[str, Any]:
    """Omvang, vocabulaire en regelingen van de graaf, gestructureerd (gecachet).

    De vocabulaire zijn de rijen die de tool pagineert (`tools._h_schema`); omvang, IRI-patronen en
    regelingen zijn klein en komen op elke pagina mee."""
    global _cache, _gezet_op
    if _cache is not None and (time.monotonic() - _gezet_op) < TTL_SECONDEN:
        return _cache

    aantallen = parse_select(graph.sparql(queries.count_by_type()))
    vocabulaire = parse_select(graph.sparql(queries.ontologie()))
    regelingen = parse_select(graph.sparql(queries.list_regelingen()))
    _cache = {
        "aantallen": aantallen,
        "vocabulaire": vocabulaire,
        "regelingen": [{k: v for k, v in r.items() if v} for r in regelingen],
        "iri_patronen": {
            "regeling": f"{queries.NS}{{BWB-id}}",
            "artikel": f"{queries.NS}{{BWB-id}}:artikel:{{nr}}",
            "lid": f"{queries.NS}{{BWB-id}}:artikel:{{nr}}:lid:{{nr}}",
        },
        "toelichting": (
            "Aantallen per type in de eigen IRI-ruimte; de vocabulaire zijn de namen voor raw_sparql. "
            f'Filter altijd op STRSTARTS(STR(?s), "{queries.NS}") – anders tel je de owl:sameAs-tweelingen '
            "van wetten.overheid.nl dubbel. urn:jas:… zijn JAS-annotaties: afgeleide duiding door Lex en "
            f"juristen, GEEN wettekst en GEEN vindplaats; de wet staat alleen onder {queries.NS}."
        ),
    }
    _gezet_op = time.monotonic()
    return _cache
