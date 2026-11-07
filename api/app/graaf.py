"""De complete graaf: alle regelingen (of een keuze) met structuur, verwijzingen en markeringen.

Voor de graafweergave in de werkplek, die de hele kennisgraaf moet kunnen tonen – geen grens op het
aantal delen. De vorm is die van `samenhang.py` (`Knoop`/`Relatie`), zodat de werkplek één model
heeft, ongeacht of hij één artikel of alles laadt.

Kosten en cache. Per regeling is de bronboom één SPARQL-query (Awb: ~2.300 knopen) en de
verwijzingen nog één. Beide veranderen alleen bij een herimport, dus ze worden per proces bewaard
onder `(bwb_id, bwb:inhoudHash)`: andere tekst geeft vanzelf een nieuwe sleutel, ook bij dezelfde
toestand (een herimport met een andere parser). Een graaf zonder hash valt terug op de toestand. Markeringen veranderen per beoordeling en komen altijd vers uit Postgres. De `versie` in het
antwoord is de hash van de toestanden: daarop cachet de werkplek de layout.

Dezelfde cache draagt de leesroutes van een werkgebied (`lees_bron`). Die haalden elk elke regeling
opnieuw op en bouwden de snapshot, terwijl één scherm er drie tegelijk aanroept. Schrijfroutes doen dat
bewust niet: wat ze vastleggen toetsen ze tegen de bron van nu (`bron_resolver.resolve_bron`).

Tekst zit bewust niet in de knopen: de complete graaf is zo ~2 MB in plaats van tientallen; de
werkplek haalt de tekst van een gekozen bepaling op als die nodig is.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time

import httpx
from bronmodel import BronFout

from . import annotatie_v2_store as store
from .bron_resolver import bwb_van, haal_bronrijen, snapshot_uit
from .graaf_projectie_v2 import _select
from .samenhang import _PREFIXES, Knoop, Relatie, _label, bronknoop, citeertitel_van, markeringen, verwijzingen

logger = logging.getLogger(__name__)

# Hoeveel regelingtoestanden het proces bewaart: ruim boven het aantal regelingen in de graaf, zodat
# een herimport (nieuwe toestand naast de oude, tot die vervalt) nooit de hele cache verdringt.
MAX_CACHE = 64
_CACHE: dict[tuple[str, str], dict] = {}
# Hoe lang een bronboom geldt als de graaf nog geen inhoudshash draagt (een import van vóór F4): een herimport met
# een andere parser verandert de tekst zonder nieuwe toestand. Met `bwb:inhoudHash` is de sleutel de inhoud zelf
# en vervalt deze grens.
GELDIG_S = 600
_SLOTEN: dict[str, asyncio.Lock] = {}


def _toestanden_query(bwbs: list[str]) -> str:
    filter_ = ("VALUES ?bwbId { " + " ".join(f'"{b}"' for b in bwbs) + " }") if bwbs else ""
    return _PREFIXES + f"""SELECT ?bwbId ?toestand ?inhoud ?citeertitel WHERE {{
  {filter_}
  ?regeling a bwb:Regeling ; bwb:bwbId ?bwbId .
  FILTER(STRSTARTS(STR(?regeling), "urn:bwb:BWB"))
  OPTIONAL {{ ?regeling bwb:toestandUrl ?toestand }}
  OPTIONAL {{ ?regeling bwb:inhoudHash ?inhoud }}
  OPTIONAL {{ ?regeling bwb:citeertitel ?citeertitel }}
}} ORDER BY ?bwbId"""


def _verwijzingen_query(bwb: str) -> str:
    """Alle verwijzingen ván deze regeling, uit haar eigen named graph (zonder LIMIT: de graaf is het
    doel, niet één artikel). Het label van het doel komt uit de hele graaf."""
    return _PREFIXES + f"""SELECT ?van ?naar ?anker ?label ?stub ?betrouwbaarheid WHERE {{
  GRAPH <urn:bwb:graph:{bwb}> {{ ?van bwb:heeftVerwijzing ?v . ?v bwb:naar ?naar .
    OPTIONAL {{ ?v bwb:ankerTekst ?anker }} OPTIONAL {{ ?v bwb:betrouwbaarheid ?betrouwbaarheid }} }}
  OPTIONAL {{ ?naar rdfs:label ?label }}
  OPTIONAL {{ ?naar bwb:doelLabel ?stub }}
}} ORDER BY ?van ?naar"""


# De structuur van een regeling (knopen + citeertitel) apart van haar verwijzingen: de plek van een
# bepaling (`plaatsen`) heeft alleen de structuur nodig, en die is per toestand dezelfde.
_STRUCTUUR: dict[tuple[str, str], dict] = {}


def stand_van(rij: dict) -> str:
    """De cachesleutel van een regeling: haar inhoudshash, of anders haar toestand (met een geldigheidsgrens)."""
    return f"inhoud:{rij['inhoud']}" if rij.get("inhoud") else f"toestand:{rij.get('toestand', '')}"


def _bewaard(sleutel: tuple[str, str], cache: dict | None = None) -> dict | None:
    deel = (_STRUCTUUR if cache is None else cache).get(sleutel)
    if deel is None:
        return None
    return deel if sleutel[1].startswith("inhoud:") or time.monotonic() - deel["gehaald"] < GELDIG_S else None


async def _structuur(bwb: str, toestand: str) -> dict:
    """De snapshot, knopen en citeertitel van één regeling, uit de cache of vers (één SPARQL-query)."""
    sleutel = (bwb, toestand)
    if deel := _bewaard(sleutel):
        return deel
    async with _SLOTEN.setdefault(f"structuur:{bwb}", asyncio.Lock()):
        if deel := _bewaard(sleutel):   # een gelijktijdig verzoek haalde hem intussen op
            return deel
        snapshot = snapshot_uit(await haal_bronrijen(bwb), bwb, {})
        deel = {"snapshot": snapshot, "nodes": store.nodes_van(snapshot),
                "citeertitel": citeertitel_van(snapshot), "gehaald": time.monotonic()}
        for oud in [k for k in _STRUCTUUR if k[0] == bwb]:
            del _STRUCTUUR[oud]         # een vorige toestand van deze regeling is voorbij
        while len(_STRUCTUUR) >= MAX_CACHE:
            del _STRUCTUUR[next(iter(_STRUCTUUR))]
        _STRUCTUUR[sleutel] = deel
        return deel


async def lees_bron(doel: dict) -> dict:
    """De bronboom van een regeling voor een leesroute, uit de cache van deze toestand (één lichte query).

    Een `Resolver` zoals `bron_resolver.resolve_bron`, met één verschil: de snapshot gaat over de hele
    regeling, dus `doel` is de wortel en `segmenten` de hele tekst. Leesroutes gebruiken alleen de `nodes` en
    de citeertitel, en die zijn gedeeld: niet wijzigen. Een schrijfroute hoort hier niet."""
    bwb = bwb_van(doel)
    if not _BWB.match(bwb):
        raise BronFout("Ongeldig BWB-id")
    async with httpx.AsyncClient(timeout=30) as client:
        rijen = [r for r in await _select(client, _toestanden_query([bwb])) if r.get("bwbId") == bwb]
    if not rijen:
        raise BronFout("Regeling niet gevonden in de brongraaf")
    deel = await _structuur(bwb, stand_van(rijen[0]))
    if (iri := doel.get("bron_iri")) and iri not in deel["nodes"]:
        raise BronFout("De gevraagde bronnode bestaat niet")
    return deel["snapshot"]


async def _regeling(client: httpx.AsyncClient, bwb: str, toestand: str) -> dict:
    """Structuur en uitgaande verwijzingen van één regeling, uit de cache of vers."""
    sleutel = (bwb, toestand)
    if deel := _bewaard(sleutel, _CACHE):
        return deel
    async with _SLOTEN.setdefault(bwb, asyncio.Lock()):
        if deel := _bewaard(sleutel, _CACHE):   # een gelijktijdig verzoek haalde hem intussen op
            return deel
        structuur = await _structuur(bwb, toestand)
        rijen = await _select(client, _verwijzingen_query(bwb))
        deel = {**structuur, "verwijzingen": rijen}
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
        delen = [(r, await _regeling(client, r["bwbId"], stand_van(r))) for r in toestanden]

    knopen: dict[str, Knoop] = {}
    relaties: list[Relatie] = []
    alle_nodes: dict[str, dict] = {}
    for r, deel in delen:
        nodes = deel["nodes"]
        alle_nodes.update(nodes)
        for node in sorted(nodes.values(), key=lambda n: n.get("volgorde", 0)):
            knoop = bronknoop(node, nodes=nodes).model_copy(update={"tekst": ""})
            if node.get("type") == "Regeling":
                knoop = knoop.model_copy(update={"label": r.get("citeertitel") or deel["citeertitel"] or knoop.label})
            knopen[node["bron_iri"]] = knoop
            if node.get("parent_iri") in nodes:
                relaties.append(Relatie(bron=node["parent_iri"], doel=node["bron_iri"], soort="bevat", groep="structuur"))

    m_knopen, m_relaties = markeringen(await store.actuele_elementen(alle_nodes), set(knopen))
    knopen.update({k.id: k for k in m_knopen})
    relaties += m_relaties
    relaties += verwijzingen([("uit", rij) for _, deel in delen for rij in deel["verwijzingen"]], knopen)

    versie = store.digest(sorted((r["bwbId"], stand_van(r)) for r, _ in delen))
    return {
        "schema_versie": 1,
        "versie": versie,
        "regelingen": [{"bwb_id": r["bwbId"], "citeertitel": r.get("citeertitel") or deel["citeertitel"],
                        "toestand": r.get("toestand", "")} for r, deel in delen],
        "knopen": [k.model_dump() for k in knopen.values()],
        "relaties": [rel.model_dump() for rel in relaties],
    }


_IRI_BWB = re.compile(r"^urn:bwb:(BWB[RV]\d+)(?::.*)?$")
MAX_PLAATSEN = 500


async def plaatsen(iris: list[str]) -> list[dict]:
    """De plek van elke bepaling in haar regeling, voor het groeperen in de werkplek (spoor H): per IRI de
    regeling en het pad eronder – hoofdstuk, afdeling, paragraaf of divisie, artikel, lid, onderdeel – met
    het label zoals de graaf het toont (`_label`, met het nummer) en de documentvolgorde.

    Alleen de structuur, letterlijk uit de bronboom; niets afgeleid. Een IRI die de graaf niet (meer) kent,
    krijgt `pad: []` en `volgorde: None`: de werkplek valt dan terug op wat de IRI zelf zegt. Een IRI gaat
    niet letterlijk een query in; alleen het BWB-id, en dat wordt strikt gelezen."""
    if len(iris) > MAX_PLAATSEN:
        raise ValueError(f"Hoogstens {MAX_PLAATSEN} bepalingen per verzoek.")
    per_bwb: dict[str, list[str]] = {}
    for iri in iris:
        m = _IRI_BWB.match(iri)
        if not m:
            raise ValueError(f"Geen bron-IRI: {iri[:80]}")
        per_bwb.setdefault(m.group(1), []).append(iri)
    async with httpx.AsyncClient(timeout=60) as client:
        toestanden = {r["bwbId"]: r for r in await _select(client, _toestanden_query(sorted(per_bwb))) if r.get("bwbId")}
    uit: dict[str, dict] = {}
    for bwb, lijst in per_bwb.items():
        r = toestanden.get(bwb)
        deel = await _structuur(bwb, stand_van(r)) if r else {"nodes": {}, "citeertitel": ""}
        nodes = deel["nodes"]
        regeling = {"bwb_id": bwb, "citeertitel": (r or {}).get("citeertitel") or deel["citeertitel"]}
        for iri in lijst:
            pad, node, gezien = [], nodes.get(iri), set()
            while node and node.get("type") != "Regeling" and node["bron_iri"] not in gezien:
                gezien.add(node["bron_iri"])
                pad.append({"iri": node["bron_iri"], "type": node.get("type", ""),
                            "nummer": node.get("nummer", ""), "label": _label(node)})
                node = nodes.get(node.get("parent_iri", ""))
            uit[iri] = {"bron_iri": iri, "regeling": regeling, "pad": pad[::-1],
                        "volgorde": nodes[iri].get("volgorde") if iri in nodes else None}
    return [uit[i] for i in dict.fromkeys(iris)]


def leeg_cache() -> None:
    """Voor tests en na een bewuste herimport."""
    _CACHE.clear()
    _STRUCTUUR.clear()

