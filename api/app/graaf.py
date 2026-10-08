"""De complete graaf: alle regelingen (of een keuze) met structuur, verwijzingen en markeringen.

Voor de graafweergave in de werkplek, die de hele kennisgraaf moet kunnen tonen – geen grens op het
aantal delen. De vorm is die van `samenhang.py` (`Knoop`/`Relatie`), zodat de werkplek één model
heeft, ongeacht of hij één artikel of alles laadt.

Kosten en cache. Per regeling is de bronboom één SPARQL-query (Awb: ~2.300 knopen) en de
verwijzingen nog één. Beide veranderen alleen bij een herimport, dus ze worden per proces bewaard
onder `(bwb_id, bwb:toestandUrl)`: een nieuwe toestand van de regeling geeft vanzelf een nieuwe
sleutel. Markeringen veranderen per beoordeling en komen altijd vers uit Postgres. De `versie` in het
antwoord is de hash van de toestanden: daarop cachet de werkplek de layout.

Tekst zit bewust niet in de knopen: de complete graaf is zo ~2 MB in plaats van tientallen; de
werkplek haalt de tekst van een gekozen bepaling op als die nodig is.
"""
from __future__ import annotations

import asyncio
import logging
import re

import httpx

from . import annotatie_v2_store as store
from .bron_resolver import haal_bronrijen, snapshot_uit
from .graaf_projectie_v2 import _select
from .samenhang import _PREFIXES, Knoop, Relatie, bronknoop, markeringen, verwijzingen

logger = logging.getLogger(__name__)

# Hoeveel regelingtoestanden het proces bewaart: ruim boven het aantal regelingen in de graaf, zodat
# een herimport (nieuwe toestand naast de oude, tot die vervalt) nooit de hele cache verdringt.
MAX_CACHE = 64
_CACHE: dict[tuple[str, str], dict] = {}
_SLOTEN: dict[str, asyncio.Lock] = {}


def _toestanden_query(bwbs: list[str]) -> str:
    filter_ = ("VALUES ?bwbId { " + " ".join(f'"{b}"' for b in bwbs) + " }") if bwbs else ""
    return _PREFIXES + f"""SELECT ?bwbId ?toestand ?citeertitel WHERE {{
  {filter_}
  ?regeling a bwb:Regeling ; bwb:bwbId ?bwbId .
  FILTER(STRSTARTS(STR(?regeling), "urn:bwb:BWB"))
  OPTIONAL {{ ?regeling bwb:toestandUrl ?toestand }}
  OPTIONAL {{ ?regeling bwb:citeertitel ?citeertitel }}
}} ORDER BY ?bwbId"""


def _verwijzingen_query(bwb: str) -> str:
    """Alle verwijzingen ván deze regeling, uit haar eigen named graph (zonder LIMIT: de graaf is het
    doel, niet één artikel). Het label van het doel komt uit de hele graaf."""
    return _PREFIXES + f"""SELECT ?van ?naar ?anker ?label ?stub WHERE {{
  GRAPH <urn:bwb:graph:{bwb}> {{ ?van bwb:heeftVerwijzing ?v . ?v bwb:naar ?naar . OPTIONAL {{ ?v bwb:ankerTekst ?anker }} }}
  OPTIONAL {{ ?naar rdfs:label ?label }}
  OPTIONAL {{ ?naar bwb:doelLabel ?stub }}
}} ORDER BY ?van ?naar"""


async def _regeling(client: httpx.AsyncClient, bwb: str, toestand: str) -> dict:
    """Structuur en uitgaande verwijzingen van één regeling, uit de cache of vers."""
    sleutel = (bwb, toestand)
    if sleutel in _CACHE:
        return _CACHE[sleutel]
    async with _SLOTEN.setdefault(bwb, asyncio.Lock()):
        if sleutel in _CACHE:           # een gelijktijdig verzoek haalde hem intussen op
            return _CACHE[sleutel]
        snapshot = snapshot_uit(await haal_bronrijen(bwb), bwb, {})
        rijen = await _select(client, _verwijzingen_query(bwb))
        deel = {"nodes": store.nodes_van(snapshot), "citeertitel": snapshot.get("citeertitel", ""),
                "verwijzingen": rijen}
        for oud in [k for k in _CACHE if k[0] == bwb]:
            del _CACHE[oud]             # een vorige toestand van deze regeling is voorbij
        while len(_CACHE) >= MAX_CACHE:
            del _CACHE[next(iter(_CACHE))]
        _CACHE[sleutel] = deel
        return deel


_BWB = re.compile(r"^BWB[RV]\d+$")


async def graaf(bwbs: list[str] | None = None) -> dict:
    """De graaf van de gekozen regelingen (leeg = alle) als `{versie, regelingen, knopen, relaties}`.

    Een BWB-id gaat letterlijk een SPARQL-query in: alleen de vorm `BWBR…`/`BWBV…` wordt aangenomen."""
    if any(not _BWB.match(b) for b in bwbs or []):
        raise ValueError("Ongeldig BWB-id.")
    async with httpx.AsyncClient(timeout=60) as client:
        toestanden = [r for r in await _select(client, _toestanden_query(sorted(set(bwbs or []))))
                      if r.get("bwbId")]
        delen = [(r, await _regeling(client, r["bwbId"], r.get("toestand", ""))) for r in toestanden]

    knopen: dict[str, Knoop] = {}
    relaties: list[Relatie] = []
    alle_nodes: dict[str, dict] = {}
    for r, deel in delen:
        nodes = deel["nodes"]
        alle_nodes.update(nodes)
        for node in sorted(nodes.values(), key=lambda n: n.get("volgorde", 0)):
            knoop = bronknoop(node).model_copy(update={"tekst": ""})
            if node.get("type") == "Regeling":
                knoop = knoop.model_copy(update={"label": r.get("citeertitel") or deel["citeertitel"] or knoop.label})
            knopen[node["bron_iri"]] = knoop
            if node.get("parent_iri") in nodes:
                relaties.append(Relatie(bron=node["parent_iri"], doel=node["bron_iri"], soort="bevat", groep="structuur"))

    m_knopen, m_relaties = markeringen(await store.actuele_elementen(alle_nodes), set(knopen))
    knopen.update({k.id: k for k in m_knopen})
    relaties += m_relaties
    relaties += verwijzingen([("uit", rij) for _, deel in delen for rij in deel["verwijzingen"]], knopen)

    versie = store.digest(sorted((r["bwbId"], r.get("toestand", "")) for r, _ in delen))
    return {
        "schema_versie": 1,
        "versie": versie,
        "regelingen": [{"bwb_id": r["bwbId"], "citeertitel": r.get("citeertitel") or deel["citeertitel"],
                        "toestand": r.get("toestand", "")} for r, deel in delen],
        "knopen": [k.model_dump() for k in knopen.values()],
        "relaties": [rel.model_dump() for rel in relaties],
    }


def leeg_cache() -> None:
    """Voor tests en na een bewuste herimport."""
    _CACHE.clear()

