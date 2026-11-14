"""De bron van de connector Kennisgroepstandpunten (plan-connector-kennisgroepen.md, stap 4).

Twee kanten, één object per proces (`connectortools.MODULES`):

- **zoeken** gaat over de index in de graaf (`urn:wa:graph:kennisgroepen`, gevuld door `bwb-import --kennisgroepen`):
  de API van de Belastingdienst kan niet per wetsartikel zoeken, de index wel. De SPARQL bouwt deze module, nooit het
  model; elke waarde van de jurist gaat er alleen als ontsnapte literal in;
- **lezen** gaat live naar de REST API (`/wp-json/wp/v2/wt_publication/<id>`), met de gedeelde lezer
  (`bronmodel.kennisgroepen`, dezelfde als de index), zodat de tekst die Lex citeert de tekst van nu is. Een cache met
  versiecontrole: binnen `VERS_S` geen verzoek; is de bron niet te bereiken, dan de bewaarde versie met
  `gevalideerd: false`.

Het WordPress-id van een kenmerk komt uit de index; staat de index er niet (de graaf werd net herstart), dan zoekt de
adapter het kenmerk bij de API zelf (`?search=`), en kiest alleen de publicatie waarvan de titel precies dat kenmerk draagt.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx
from bronmodel import kennisgroepen as kg

from ..graph.results import parse_select
from .http_beleid import STANDAARD, met_herhaling

logger = logging.getLogger(__name__)

USER_AGENT = "wetsanalyse-graph-qa (connector kennisgroepen; https://github.com/palmw01/wetsanalyse-ai)"
#: Zo lang geldt een gelezen publicatie als vers.
VERS_S = 600.0
MAX_CACHE = 64
#: Hoogstens één verzoek per zoveel seconden naar de site.
PAUZE_S = 0.5

_P = f"PREFIX kgo: <{kg.NS}>\n"
_G = f"<{kg.GRAAF}>"


class KennisgroepenFout(RuntimeError):
    """`code` volgt `http_beleid`: onbereikbaar, bezet, verzoek_geweigerd, niet_gevonden; plus `geen_index`."""

    def __init__(self, code: str, melding: str) -> None:
        super().__init__(melding)
        self.code = code


@dataclass
class Zoekvraag:
    bwb_id: str = ""
    artikel: str = ""
    lid: str = ""
    woorden: tuple[str, ...] = ()
    kennisgroep: str = ""
    middel: str = ""
    rubriek: str = ""
    noemt: str = ""
    vanaf: str = ""
    tot: str = ""
    status: str = kg.STATUS_GELDEND
    volgorde: str = "nieuwste"


@dataclass
class Gevonden:
    totaal: int
    rijen: list[dict[str, str]]
    per_status: dict[str, int] = field(default_factory=dict)
    per_herkomst: dict[str, int] = field(default_factory=dict)
    #: De verdeling van het totaal, geteld in de index (meting 14 nov 2026, vraag 8: zonder telling bladerde het model
    #: door 93 standpunten en schatte het per belastingsoort). Een standpunt met twee belastingsoorten telt bij beide.
    per_belastingsoort: dict[str, int] = field(default_factory=dict)
    per_kennisgroep: dict[str, int] = field(default_factory=dict)


@dataclass
class Gelezen:
    standpunt: kg.Standpunt
    vervangen_door: list[str]
    gebeurtenissen: list[dict[str, str]]
    gevalideerd: bool = True


def literal(waarde: str) -> str:
    """Een waarde van de jurist als SPARQL-literal: alleen ontsnapt, nooit als syntaxis."""
    return '"' + str(waarde).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def _bevat(var: str, waarde: str) -> str:
    return f"CONTAINS(LCASE(STR({var})), {literal(waarde.lower())})"


def patronen(v: Zoekvraag) -> str:
    """Het WHERE-deel binnen de graaf, zonder de status (die telt de per_status-query apart)."""
    d = ["?s a kgo:Standpunt ; kgo:id ?id ; kgo:status ?status ; kgo:datum ?datum ."]
    if v.bwb_id:
        d.append(f"?s kgo:noemt ?n . ?n kgo:bwbId {literal(v.bwb_id)} ; kgo:herkomst ?herkomst .")
        if v.artikel:
            d.append(f"?n kgo:artikel {literal(v.artikel)} .")
            if v.lid:
                # Een vermelding van het hele artikel hoort ook bij een lid; een ander lid niet.
                d.append(f"FILTER NOT EXISTS {{ ?n kgo:lid ?anderlid FILTER(?anderlid != {literal(v.lid)}) }}")
    for i, w in enumerate(v.woorden):
        d.append(f"FILTER EXISTS {{ {{ ?s kgo:titel ?w{i} }} UNION {{ ?s kgo:rij ?r{i} . ?r{i} kgo:tekst ?w{i} }} "
                 f"FILTER({_bevat(f'?w{i}', w)}) }}")
    if v.kennisgroep:
        d.append(f"FILTER EXISTS {{ ?s kgo:kennisgroep ?kgf FILTER({_bevat('?kgf', v.kennisgroep)}) }}")
    if v.middel:
        d.append(f"FILTER EXISTS {{ {{ ?s kgo:middel ?mf }} UNION {{ ?s kgo:belastingsoort ?mf }} "
                 f"FILTER({_bevat('?mf', v.middel)}) }}")
    if v.rubriek:
        d.append(f"FILTER EXISTS {{ {{ ?s kgo:rubriek ?rf }} UNION {{ ?s kgo:subrubriek ?rf }} "
                 f"FILTER({_bevat('?rf', v.rubriek)}) }}")
    if v.noemt:
        d.append(f"?s kgo:noemt ?nd . ?nd kgo:doel {literal(v.noemt)} .")
    if v.vanaf:
        d.append(f"FILTER(STR(?datum) >= {literal(v.vanaf)})")
    if v.tot:
        d.append(f"FILTER(STR(?datum) <= {literal(v.tot)})")
    return "\n".join(d)


def _status_filter(v: Zoekvraag) -> str:
    return "" if v.status == "alle" else f"FILTER(?status = {literal(v.status)})"


def q_pagina(v: Zoekvraag, offset: int, limit: int) -> str:
    richting = "ASC" if v.volgorde == "oudste" else "DESC"
    herkomst = "(GROUP_CONCAT(DISTINCT ?herkomst; separator=\"|\") AS ?herkomsten) " if v.bwb_id else ""
    return (_P + "SELECT ?s ?id ?status ?datum ?kenmerk ?titel ?link ?wp ?gepubliceerd ?gewijzigd ?vastgesteld "
            "(SAMPLE(?kg0) AS ?kennisgroep) (GROUP_CONCAT(DISTINCT ?m0; separator=\"|\") AS ?middelen) "
            "(GROUP_CONCAT(DISTINCT ?r0; separator=\"|\") AS ?rubrieken) "
            "(GROUP_CONCAT(DISTINCT ?vd0; separator=\"|\") AS ?vervangen_door) "
            "(GROUP_CONCAT(DISTINCT ?vt0; separator=\"|\") AS ?vervangt) " + herkomst +
            f"WHERE {{ GRAPH {_G} {{\n{patronen(v)}\n{_status_filter(v)}\n"
            "?s kgo:kenmerk ?kenmerk ; kgo:titel ?titel ; kgo:link ?link ; kgo:wpId ?wp .\n"
            "OPTIONAL { ?s kgo:gepubliceerd ?gepubliceerd } OPTIONAL { ?s kgo:gewijzigd ?gewijzigd }\n"
            "OPTIONAL { ?s kgo:vastgesteld ?vastgesteld } OPTIONAL { ?s kgo:kennisgroep ?kg0 }\n"
            "OPTIONAL { { ?s kgo:middel ?m0 } UNION { ?s kgo:belastingsoort ?m0 } }\n"
            "OPTIONAL { { ?s kgo:rubriek ?r0 } UNION { ?s kgo:subrubriek ?r0 } }\n"
            "OPTIONAL { ?s kgo:vervangenDoorId ?vd0 } OPTIONAL { ?s kgo:vervangtId ?vt0 }\n"
            "} }\nGROUP BY ?s ?id ?status ?datum ?kenmerk ?titel ?link ?wp ?gepubliceerd ?gewijzigd ?vastgesteld\n"
            f"ORDER BY {richting}(?datum) ?id LIMIT {int(limit)} OFFSET {int(offset)}")


def q_tellingen(v: Zoekvraag) -> str:
    herkomst = "?herkomst " if v.bwb_id else ""
    return (_P + f"SELECT ?status {herkomst}(COUNT(DISTINCT ?s) AS ?n) WHERE {{ GRAPH {_G} {{\n{patronen(v)}\n}} }} "
            f"GROUP BY ?status {herkomst}")


#: De velden waarover `q_verdeling` telt, met hun patroon in de index.
VERDELINGEN = {
    "belastingsoort": "{ ?s kgo:middel ?w } UNION { ?s kgo:belastingsoort ?w }",
    "kennisgroep": "?s kgo:kennisgroep ?w .",
}


def q_verdeling(v: Zoekvraag, veld: str) -> str:
    """Hoeveel standpunten van deze zoekvraag (met haar status) er per waarde van `veld` zijn, grootste eerst."""
    return (_P + f"SELECT ?w (COUNT(DISTINCT ?s) AS ?n) WHERE {{ GRAPH {_G} {{\n{patronen(v)}\n{_status_filter(v)}\n"
            f"{VERDELINGEN[veld]}\n}} }} GROUP BY ?w ORDER BY DESC(?n) ?w")


def q_opvolgers(ident: str) -> str:
    """De standpunten die `ident` intrekken of vervangen, ook als `ident` zelf niet gepubliceerd is (een standpunt van
    vóór 2022, alleen via de Woo openbaar)."""
    return (_P + f"SELECT DISTINCT ?id ?status WHERE {{ GRAPH {_G} {{ ?s kgo:vervangtId {literal(ident)} ; kgo:id ?id ; "
            "kgo:status ?status } } ORDER BY ?id")


def q_publicatie(ident: str) -> str:
    return (_P + "SELECT ?wp (GROUP_CONCAT(DISTINCT ?vd; separator=\"|\") AS ?vervangen_door) "
            f"WHERE {{ GRAPH {_G} {{ ?s kgo:id {literal(ident)} ; kgo:wpId ?wp . "
            "OPTIONAL { ?s kgo:vervangenDoorId ?vd } } } GROUP BY ?wp")


def q_gebeurtenissen(wp_id: int) -> str:
    return (_P + "SELECT ?soort ?datum ?link ?titel WHERE { GRAPH " + _G + " { "
            f"<{kg.subject_iri(wp_id)}> kgo:gebeurtenis ?g . ?g kgo:gebeurtenissoort ?soort ; kgo:link ?link . "
            "OPTIONAL { ?g kgo:datum ?datum } OPTIONAL { ?g kgo:titel ?titel } } } ORDER BY ?datum")


def q_index_leeg() -> str:
    """Eén standpunt, of niets: zo onderscheidt `zoek` een lege index van een zoekvraag zonder treffers."""
    return _P + f"SELECT ?s WHERE {{ GRAPH {_G} {{ ?s a kgo:Standpunt }} }} LIMIT 1"


def _select(graph: Any, query: str) -> list[dict[str, str]]:
    if graph is None:
        raise KennisgroepenFout("geen_index", "de index van de kennisgroepstandpunten is niet te bereiken")
    try:
        return parse_select(graph.sparql(query))
    except KennisgroepenFout:
        raise
    except Exception as exc:  # noqa: BLE001 - een haperende graaf is geen "geen standpunten"
        raise KennisgroepenFout("geen_index", f"de index van de kennisgroepstandpunten gaf een fout: {exc}") from exc


class KennisgroepenBron:
    def __init__(self, *, client: httpx.Client | None = None, timeout: float = 30.0, vers_s: float = VERS_S,
                 slaap: Callable[[float], None] = time.sleep, klok: Callable[[], float] = time.monotonic) -> None:
        self._http = client or httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT})
        self._vers_s, self._slaap, self._klok = vers_s, slaap, klok
        self._cache: OrderedDict[int, tuple[float, dict[str, Any]]] = OrderedDict()
        self._lock = threading.Lock()
        self._laatste = 0.0

    # ── zoeken in de index ────────────────────────────────────────────────────────────────────────────────────

    def zoek(self, graph: Any, vraag: Zoekvraag, *, offset: int, limit: int) -> Gevonden:
        per_status: dict[str, int] = {}
        per_herkomst: dict[str, int] = {}
        for r in _select(graph, q_tellingen(vraag)):
            n = int(r.get("n") or 0)
            per_status[r.get("status", "")] = per_status.get(r.get("status", ""), 0) + n
            if r.get("herkomst") and (vraag.status == "alle" or r.get("status") == vraag.status):
                per_herkomst[r["herkomst"]] = per_herkomst.get(r["herkomst"], 0) + n
        totaal = sum(per_status.values()) if vraag.status == "alle" else per_status.get(vraag.status, 0)
        if vraag.bwb_id:
            # Een standpunt met een koppeling via link én via tekst telt in beide herkomsten; het totaal telt het één keer.
            totaal = min(totaal, sum(per_herkomst.values())) if per_herkomst else totaal
        rijen = _select(graph, q_pagina(vraag, offset, limit)) if totaal else []
        verdeling = {veld: {r["w"]: int(r.get("n") or 0) for r in _select(graph, q_verdeling(vraag, veld)) if r.get("w")}
                     for veld in VERDELINGEN} if totaal else {}
        if not per_status:
            # Een lege index is geen "geen standpunten": de import draaide (nog) niet.
            if not _select(graph, q_index_leeg()):
                raise KennisgroepenFout("geen_index", "de index van de kennisgroepstandpunten is leeg; de import heeft "
                                        "nog niet gedraaid")
        return Gevonden(totaal, rijen, per_status, per_herkomst, verdeling.get("belastingsoort", {}),
                        verdeling.get("kennisgroep", {}))

    def opvolgers(self, graph: Any, ident: str) -> list[tuple[str, str]]:
        """(id, status) van de standpunten die `ident` intrekken; leeg als de index het niet weet of er niet is."""
        try:
            return [(r["id"], r.get("status", "")) for r in _select(graph, q_opvolgers(ident)) if r.get("id")]
        except KennisgroepenFout:
            return []

    # ── lezen bij de bron ─────────────────────────────────────────────────────────────────────────────────────

    def _get(self, url: str) -> httpx.Response:
        def doe() -> httpx.Response:
            wacht = PAUZE_S - (self._klok() - self._laatste)
            if wacht > 0:
                self._slaap(wacht)
            self._laatste = self._klok()
            return self._http.get(url)
        try:
            return met_herhaling(doe, beleid=STANDAARD, host=kg.HOST, slaap=self._slaap, logger=logger,
                                 gebeurtenis="kennisgroepen_verzoek_mislukt")
        except httpx.HTTPError as exc:
            raise KennisgroepenFout("onbereikbaar", f"de site van de kennisgroepen is niet te bereiken ({type(exc).__name__})")

    def _item(self, wp_id: int) -> tuple[dict[str, Any], bool]:
        with self._lock:
            bewaard = self._cache.get(wp_id)
        if bewaard and self._klok() - bewaard[0] < self._vers_s:
            return bewaard[1], True
        try:
            r = self._get(kg.item_url(wp_id))
        except KennisgroepenFout:
            if bewaard:
                logger.warning("kennisgroepen: bewaarde versie", extra={"wp_id": wp_id})
                return bewaard[1], False
            raise
        if r.status_code >= 400:
            raise KennisgroepenFout(STANDAARD.foutcode(r.status_code), f"publicatie {wp_id}: HTTP {r.status_code}")
        item = r.json()
        if bewaard and bewaard[1].get("modified_gmt") != item.get("modified_gmt"):
            logger.info("kennisgroepen_gewijzigd", extra={"wp_id": wp_id})
        with self._lock:
            self._cache[wp_id] = (self._klok(), item)
            self._cache.move_to_end(wp_id)
            while len(self._cache) > MAX_CACHE:
                self._cache.popitem(last=False)
        return item, True

    def _wp_via_site(self, ident: str) -> int:
        kenmerk = kg.kg_kenmerk(ident)
        r = self._get(f"{kg.API}/wt_publication?search={quote(kenmerk)}&per_page=20&_fields=id,title")
        if r.status_code >= 400:
            raise KennisgroepenFout(STANDAARD.foutcode(r.status_code), f"zoeken op {kenmerk}: HTTP {r.status_code}")
        for item in r.json():
            if kg.kenmerk_uit_titel((item.get("title") or {}).get("rendered", ""))[0] == ident:
                return int(item["id"])
        raise KennisgroepenFout("niet_gevonden", f"{kenmerk} staat niet bij de gepubliceerde kennisgroepstandpunten")

    def publicatie(self, graph: Any, ident: str) -> Gelezen:
        wp_id, door, geb = 0, [], []
        try:
            rij = next(iter(_select(graph, q_publicatie(ident))), None)
            if rij and rij.get("wp"):
                wp_id = int(rij["wp"])
                door = [d for d in (rij.get("vervangen_door") or "").split("|") if d]
                geb = [{k: v for k, v in g.items() if v} for g in _select(graph, q_gebeurtenissen(wp_id))]
        except KennisgroepenFout:
            logger.info("kennisgroepen: index niet bruikbaar, zoeken bij de site", extra={"id": ident})
        if not wp_id:
            wp_id = self._wp_via_site(ident)
        item, vers = self._item(wp_id)
        return Gelezen(kg.lees_publicatie(item), door, geb, vers)


_ID_RE = re.compile(r"^kg:\d{3}:\d{4}:\d+$")


def is_id(waarde: str) -> bool:
    return bool(_ID_RE.match(waarde or ""))
