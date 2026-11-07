"""De weg naar de kennisgraaf: het endpoint van de repository en één SPARQL-SELECT.

Elke module die de graaf leest – de projecties, de graafcontrole, de leesroutes en de routers – gebruikt deze twee,
in plaats van `_repo` en `_select` uit `graaf_projectie_v2` te lenen. `bron_resolver` haalt de bronboom ook hier op.
Een niet-geconfigureerde graaf is een `ConnectionError`; elke aanroeper vertaalt dat al naar "graaf weg".
"""
from __future__ import annotations

import httpx
from bronmodel import parse_rows

from .config import get_settings

ACCEPT = {"Accept": "application/sparql-results+json"}


def repo() -> str:
    """Het endpoint van de repository; daaronder `/statements` en `/rdf-graphs/service`."""
    cfg = get_settings()
    if not cfg.graphdb_url:
        raise ConnectionError("De kennisgraaf is niet geconfigureerd")
    return f"{cfg.graphdb_url}/repositories/{cfg.graphdb_repository}"


async def sparql_select(client: httpx.AsyncClient, query: str) -> list[dict]:
    """De rijen van één SELECT, als `{variabele: waarde}` (`bronmodel.parse_rows`)."""
    r = await client.post(repo(), data={"query": query}, headers=ACCEPT)
    r.raise_for_status()
    return parse_rows(r.json())


async def sparql_ask(client: httpx.AsyncClient, query: str) -> bool:
    """Het antwoord van één ASK."""
    r = await client.post(repo(), data={"query": query}, headers=ACCEPT)
    r.raise_for_status()
    return bool(r.json().get("boolean"))
