"""Read-only bronresolver: alleen de expliciete BWB-named graph, nooit annotatie-union."""
from __future__ import annotations

import re

import httpx
from bronmodel import BronFout, bouw_snapshot, bron_query, parse_rows

from .config import get_settings


def bwb_van(doel: dict) -> str:
    """Het BWB-id van een doel, getoetst tegen de bron-IRI als die er is."""
    iri = str(doel.get("bron_iri") or doel.get("bronnode_id") or "")
    bwb = str(doel.get("bwb_id") or doel.get("bwbId") or "").strip().upper()
    if iri:
        match = re.fullmatch(r"urn:bwb:(BWB[RV]\d+)(?::[^<>\s\"{}|^`\\]*)?", iri)
        if not match or (bwb and bwb != match.group(1)):
            raise BronFout("Ongeldige bronnode")
        bwb = match.group(1)
    return bwb


async def haal_bronrijen(bwb: str) -> list[dict]:
    """De hele bronboom van één regeling: één SPARQL-query op de BWB-named graph."""
    settings = get_settings()
    if not settings.graphdb_url:
        raise ConnectionError("De brongraaf is niet geconfigureerd")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{settings.graphdb_url}/repositories/{settings.graphdb_repository}",
            data={"query": bron_query(bwb)}, headers={"Accept": "application/sparql-results+json"},
        )
        response.raise_for_status()
    return parse_rows(response.json())


def snapshot_uit(rijen: list[dict], bwb: str, doel: dict) -> dict:
    """De snapshot van één doel uit al opgehaalde rijen: meerdere doelen in dezelfde regeling delen zo
    één bronboom (`/samenhang/meer`)."""
    return bouw_snapshot(rijen, bwb_id=bwb, bron_iri=str(doel.get("bron_iri") or doel.get("bronnode_id") or ""),
                         artikel=str(doel.get("artikel") or doel.get("nummer") or ""),
                         lid=str(doel.get("lid") or ""))


async def resolve_bron(doel: dict) -> dict:
    bwb = bwb_van(doel)
    return snapshot_uit(await haal_bronrijen(bwb), bwb, doel)
