"""Read-only bronresolver: alleen de expliciete BWB-named graph, nooit annotatie-union."""
from __future__ import annotations

import re

import httpx
from bronmodel import BronFout, bouw_snapshot, bron_query, parse_rows

from .config import get_settings


async def resolve_bron(doel: dict) -> dict:
    settings = get_settings()
    if not settings.graphdb_url:
        raise ConnectionError("De brongraaf is niet geconfigureerd")
    iri = str(doel.get("bron_iri") or doel.get("bronnode_id") or "")
    bwb = str(doel.get("bwb_id") or doel.get("bwbId") or "").strip().upper()
    if iri:
        match = re.fullmatch(r"urn:bwb:(BWB[RV]\d+)(?::[^<>\s\"{}|^`\\]*)?", iri)
        if not match or (bwb and bwb != match.group(1)):
            raise BronFout("Ongeldige bronnode")
        bwb = match.group(1)
    query = bron_query(bwb)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{settings.graphdb_url}/repositories/{settings.graphdb_repository}",
            data={"query": query}, headers={"Accept": "application/sparql-results+json"},
        )
        response.raise_for_status()
    return bouw_snapshot(parse_rows(response.json()), bwb_id=bwb, bron_iri=iri,
                         artikel=str(doel.get("artikel") or doel.get("nummer") or ""),
                         lid=str(doel.get("lid") or ""))
