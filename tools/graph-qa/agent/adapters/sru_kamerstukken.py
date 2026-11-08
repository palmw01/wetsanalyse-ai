"""De officiële publicaties van KOOP via SRU 2.0 – de transportlaag onder de Kamerstuktools (ADR-013).

Alleen lezen, alleen vaste hosts: de zoekdienst (`repository.overheid.nl/sru`) en de documenten in diezelfde
repository. De URL van een document komt uit het SRU-record (`itemUrl manifestation="xml"`), nooit van het model;
een record dat naar een andere host wijst, wordt geweigerd. De query bouwt `agent/tools/kamerstuk_tools.py`.

Gecachet per identifier, met de teksthash: een citaat blijft zo herleidbaar naar de tekst die Lex las.
"""
from __future__ import annotations

import logging
import threading
import xml.etree.ElementTree as ET
from collections import OrderedDict
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from bronmodel import tekst_hash

logger = logging.getLogger("graph_qa.kamerstukken")

SRU_URL = "https://repository.overheid.nl/sru"
_HOSTS = {"repository.overheid.nl"}
_NS = {
    "sru": "http://docs.oasis-open.org/ns/search-ws/sruResponse",
    "dcterms": "http://purl.org/dc/terms/",
    "ow": "http://standaarden.overheid.nl/wetgeving/",
    "gzd": "http://standaarden.overheid.nl/sru",
    "diag": "http://docs.oasis-open.org/ns/search-ws/diagnostic",
}
MAX_CACHE = 64


class KamerstukFout(RuntimeError):
    """De zoekdienst of het document was niet bruikbaar (onbereikbaar, een diagnose, een vreemde host)."""


@dataclass(frozen=True)
class Record:
    id: str
    titel: str
    datum: str
    vergaderjaar: str
    dossiers: tuple[str, ...]
    ondernummer: str
    xml_url: str


@dataclass(frozen=True)
class Document:
    id: str
    xml: bytes
    hash: str


def _tekst(e: ET.Element, pad: str) -> str:
    v = e.find(pad, _NS)
    return (v.text or "").strip() if v is not None else ""


def lees_records(xml: bytes) -> tuple[int, list[Record]]:
    """(totaal, records) uit een searchRetrieveResponse. Een SRU-diagnose is een fout, geen lege lijst."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise KamerstukFout(f"onleesbaar SRU-antwoord: {exc}") from exc
    if (diag := root.find(".//diag:message", _NS)) is not None:
        raise KamerstukFout(f"de zoekdienst weigerde de vraag: {(diag.text or '').strip()}")
    totaal = int(_tekst(root, "sru:numberOfRecords") or 0)
    uit: list[Record] = []
    for rec in root.iterfind(".//sru:record", _NS):
        xml_url = next((u.text or "" for u in rec.iterfind(".//gzd:itemUrl", _NS)
                        if u.get("manifestation") == "xml"), "")
        uit.append(Record(
            id=_tekst(rec, ".//dcterms:identifier"), titel=_tekst(rec, ".//dcterms:title"),
            datum=_tekst(rec, ".//dcterms:available") or _tekst(rec, ".//dcterms:date"),
            vergaderjaar=_tekst(rec, ".//ow:vergaderjaar"),
            dossiers=tuple((d.text or "").strip() for d in rec.iterfind(".//ow:dossiernummer", _NS)),
            ondernummer=_tekst(rec, ".//ow:ondernummer"), xml_url=xml_url.strip()))
    return totaal, uit


class SruKamerstukken:
    """De echte bron; tests gebruiken een nep met dezelfde twee methoden."""

    def __init__(self, *, sru_url: str = SRU_URL, timeout: float = 20.0, client: httpx.Client | None = None):
        self._url = sru_url
        self._client = client or httpx.Client(timeout=timeout, follow_redirects=False)
        self._cache: OrderedDict[str, Document] = OrderedDict()
        self._lock = threading.Lock()

    def _get(self, url: str, **params) -> bytes:
        u = urlparse(url)
        if u.scheme != "https" or u.hostname not in _HOSTS:
            raise KamerstukFout(f"host buiten de allowlist: {u.hostname}")
        try:
            r = self._client.get(url, params=params or None)
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise KamerstukFout(f"de officiële publicaties zijn niet bereikbaar: {type(exc).__name__}") from exc
        return r.content

    def zoek(self, cql: str, *, start: int = 1, maximum: int = 50) -> tuple[int, list[Record]]:
        return lees_records(self._get(self._url, query=cql, startRecord=start, maximumRecords=maximum))

    def document(self, ident: str) -> Document:
        with self._lock:
            if (doc := self._cache.get(ident)) is not None:
                self._cache.move_to_end(ident)
                return doc
        _, records = self.zoek(f"c.product-area==officielepublicaties AND dt.identifier=={ident}", maximum=1)
        rec = next((r for r in records if r.id == ident and r.xml_url), None)
        if rec is None:
            raise KamerstukFout(f"{ident} staat niet (als XML) in de officiële publicaties")
        xml = self._get(rec.xml_url)
        doc = Document(ident, xml, tekst_hash(xml.decode("utf-8", errors="replace")))
        logger.info("kamerstuk opgehaald", extra={"kamerstuk": ident, "bron_hash": doc.hash, "omvang": len(xml)})
        with self._lock:
            self._cache[ident] = doc
            while len(self._cache) > MAX_CACHE:
                self._cache.popitem(last=False)
        return doc

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:  # noqa: BLE001 – best-effort, zoals MCPClient.close
            pass
