"""De officiële publicaties van KOOP via SRU 2.0 – de transportlaag onder de Kamerstuktools (ADR-013).

Alleen lezen, alleen vaste hosts: de zoekdienst (`repository.overheid.nl/sru`) en de documenten in diezelfde
repository. De URL van een document komt uit het SRU-record (`itemUrl manifestation="xml"`), nooit van het model;
een record dat naar een andere host wijst, wordt geweigerd. De query bouwt `agent/tools/kamerstuk_tools.py`.

Gecachet per identifier, met de teksthash en de versie van KOOP: een citaat blijft zo herleidbaar naar de tekst die
Lex las. Een Kamerstuk kan na publicatie veranderen – de onopgemaakte versie wordt vervangen door de opgemaakte, en er
zijn herdruk en rectificatie (`w.documentstatus`, `w.versieinformatie`, `dt.modified`; handleiding SRU 2.0). Daarom het
cachebeleid (review ADR-013, punt 3):

- binnen `VERS_S` na lezen of valideren een hit zonder aanroep (pagineren in één gesprek);
- daarna één lichte metadatavraag; de XML komt alleen opnieuw als `dt.modified`, de status of de versie veranderde, en
  dan logt de adapter `kamerstuk_gewijzigd` met de oude en de nieuwe hash;
- is de dienst bij die validatie onbereikbaar, dan de bewaarde versie met `gevalideerd=False`: niets stil, en een korte
  storing breekt het lezen niet. Een miss zonder dienst blijft een fout;
- hoogstens `MAX_CACHE` documenten en `MAX_CACHE_BYTES` aan XML, de oudste eerst eruit.
"""
from __future__ import annotations

import logging
import re
import threading
import time
import xml.etree.ElementTree as ET
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, replace
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
MAX_CACHE_BYTES = 32 * 1024 * 1024
#: Zo lang na lezen of valideren geldt een document zonder nieuwe vraag aan de dienst.
VERS_S = 15 * 60


#: Waarom een stuk of een zoekvraag niet bruikbaar was. Eén foutcode voor alles ("bron_onbereikbaar") maskeerde de
#: oorzaak: een stuk met alleen een PDF heette onbereikbaar, en Lex zei dat het misschien niet bestond (acceptatie
#: 9 nov 2026, gesprek e906567a).
FOUTCODES = ("onbereikbaar", "geweigerd", "niet_gevonden", "alleen_pdf")


#: Het filter op Kamerstukken zonder bijlagen; `tools/kamerstuk_tools.py` bouwt er de zoekvragen op.
_KAMERSTUK = "c.product-area==officielepublicaties AND w.publicatienaam==Kamerstuk AND dt.type==Kamerstuk"
_DOSSIER_NUMMER_RE = re.compile(r"^kst-(\d{4,6}(?:-[0-9A-Za-z]{1,6})?)-([0-9A-Z]{1,6})(?:-n\d+)?$")


def dossier_en_nummer(ident: str) -> tuple[str, str] | None:
    """(dossier, nummer) uit een id als kst-36200-IX-2 of kst-32740-1-n1; None voor een id zonder die vorm
    (kst-1278484, het id van een onopgemaakt stuk)."""
    m = _DOSSIER_NUMMER_RE.match(ident or "")
    return (m.group(1), m.group(2)) if m else None


class KamerstukFout(RuntimeError):
    """De zoekdienst of het document was niet bruikbaar, met de reden (`FOUTCODES`) en, als die er is, het record."""

    def __init__(self, melding: str, *, code: str = "onbereikbaar", record: "Record | None" = None):
        super().__init__(melding)
        self.code = code
        self.record = record


@dataclass(frozen=True)
class Record:
    """Eén SRU-record, met de velden uit de beschrijving (`bronmodel.connectors.KAMERSTUKKEN.metadata`)."""
    id: str
    titel: str
    #: `dt.date`: de datum van het stuk zelf. Niet de publicatiedatum: die kan weken later liggen.
    datum: str
    vergaderjaar: str
    #: `w.dossiernummer`, alle; het eerste is het hoofddossier.
    dossiers: tuple[str, ...]
    ondernummer: str
    #: Leeg als KOOP het stuk (nog) niet als XML heeft: een onopgemaakt stuk heeft vaak alleen een PDF.
    xml_url: str
    #: `dt.modified`: wanneer KOOP de publicatie het laatst bijwerkte.
    gewijzigd: str = ""
    #: `w.documentstatus`: Onopgemaakt, Opgemaakt of Opgemaakt na onopgemaakt.
    documentstatus: str = ""
    #: `w.versieinformatie` en `w.versienummer` (herdruk, rectificatie, n1), samen.
    versie: str = ""
    #: `dt.available`: wanneer KOOP het stuk publiceerde.
    gepubliceerd: str = ""
    #: `w.documenttitel` en `w.dossiertitel`: de titel van het stuk en van het hoofddossier, elk apart.
    documenttitel: str = ""
    dossiertitel: str = ""
    #: `w.subrubriek`: het soort stuk ("Memorie van toelichting", "Motie", "Brief regering").
    soort: str = ""
    #: `dt.creator`: de Tweede of de Eerste Kamer.
    kamer: str = ""
    #: `w.indiener`, alle.
    indieners: tuple[str, ...] = ()
    #: De PDF-manifestatie, als die er is.
    pdf_url: str = ""

    @property
    def leesbaar(self) -> bool:
        return bool(self.xml_url)

    @property
    def stand(self) -> tuple[str, str, str]:
        """Wat de versie van het document bepaalt; verandert dit, dan is de XML opnieuw nodig."""
        return self.gewijzigd, self.documentstatus, self.versie


@dataclass(frozen=True)
class Document:
    id: str
    xml: bytes
    hash: str
    gewijzigd: str = ""
    documentstatus: str = ""
    versie: str = ""
    #: Onwaar als de dienst bij het valideren niet te bereiken was: dan is dit de bewaarde versie.
    gevalideerd: bool = True
    #: Het SRU-record waaruit het document kwam: de metadata van het stuk (datum, soort, dossier).
    record: Record | None = None


@dataclass
class _Plek:
    doc: Document
    stand: tuple[str, str, str]
    gezien: float


def _tekst(e: ET.Element, pad: str) -> str:
    v = e.find(pad, _NS)
    return (v.text or "").strip() if v is not None else ""


def lees_records(xml: bytes) -> tuple[int, list[Record]]:
    """(totaal, records) uit een searchRetrieveResponse. Een SRU-diagnose is een fout, geen lege lijst."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise KamerstukFout(f"onleesbaar SRU-antwoord: {exc}", code="geweigerd") from exc
    if (diag := root.find(".//diag:message", _NS)) is not None:
        raise KamerstukFout(f"de zoekdienst weigerde de vraag: {(diag.text or '').strip()}", code="geweigerd")
    totaal = int(_tekst(root, "sru:numberOfRecords") or 0)
    uit: list[Record] = []
    for rec in root.iterfind(".//sru:record", _NS):
        urls = {u.get("manifestation"): (u.text or "").strip() for u in rec.iterfind(".//gzd:itemUrl", _NS)}

        def alle(pad: str) -> tuple[str, ...]:
            return tuple(t for d in rec.iterfind(pad, _NS) if (t := (d.text or "").strip()))

        uit.append(Record(
            id=_tekst(rec, ".//dcterms:identifier"), titel=_tekst(rec, ".//dcterms:title"),
            # Eerst nam de adapter `available or date`, en die liggen soms weken uit elkaar (live, 9 nov 2026: een
            # brief van 25 september, gepubliceerd op 9 november). Nu elk apart; zonder `dt.date` de publicatiedatum.
            datum=_tekst(rec, ".//dcterms:date") or _tekst(rec, ".//dcterms:available"),
            gepubliceerd=_tekst(rec, ".//dcterms:available"),
            vergaderjaar=_tekst(rec, ".//ow:vergaderjaar"), dossiers=alle(".//ow:dossiernummer"),
            ondernummer=_tekst(rec, ".//ow:ondernummer"), xml_url=urls.get("xml", ""), pdf_url=urls.get("pdf", ""),
            gewijzigd=_tekst(rec, ".//dcterms:modified"), documentstatus=_tekst(rec, ".//ow:documentstatus"),
            versie=" ".join(v for v in (_tekst(rec, ".//ow:versieinformatie"), _tekst(rec, ".//ow:versienummer")) if v),
            documenttitel=_tekst(rec, ".//ow:documenttitel"), dossiertitel=_tekst(rec, ".//ow:dossiertitel"),
            soort=_tekst(rec, ".//ow:subrubriek"), kamer=_tekst(rec, ".//dcterms:creator"),
            indieners=alle(".//ow:indiener")))
    return totaal, uit


class SruKamerstukken:
    """De echte bron; tests gebruiken een nep met dezelfde twee methoden."""

    def __init__(self, *, sru_url: str = SRU_URL, timeout: float = 20.0, client: httpx.Client | None = None,
                 klok: Callable[[], float] = time.monotonic):
        self._url = sru_url
        self._client = client or httpx.Client(timeout=timeout, follow_redirects=False)
        self._cache: OrderedDict[str, _Plek] = OrderedDict()
        self._lock = threading.Lock()
        self._klok = klok

    def _get(self, url: str, **params) -> bytes:
        u = urlparse(url)
        if u.scheme != "https" or u.hostname not in _HOSTS:
            raise KamerstukFout(f"host buiten de allowlist: {u.hostname}", code="geweigerd")
        try:
            r = self._client.get(url, params=params or None)
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise KamerstukFout(f"de officiële publicaties zijn niet bereikbaar: {type(exc).__name__}",
                                code="onbereikbaar") from exc
        return r.content

    def zoek(self, cql: str, *, start: int = 1, maximum: int = 50) -> tuple[int, list[Record]]:
        return lees_records(self._get(self._url, query=cql, startRecord=start, maximumRecords=maximum))

    def record(self, ident: str) -> Record:
        """Het record van een stuk. Staat het id niet bij KOOP, dan op dossier en nummer: een herdruk heeft een eigen id
        (kst-32740-1 bestaat niet, kst-32740-1-n1 wel) en een onopgemaakt stuk ook (32140 nr. 342 is kst-1278484).
        Een stuk met alleen een PDF is `alleen_pdf`, met het record erbij: het bestaat, maar de tekst is niet te lezen."""
        _, records = self.zoek(f"c.product-area==officielepublicaties AND dt.identifier=={ident}", maximum=1)
        kandidaten = [r for r in records if r.id == ident]
        if not kandidaten and (dn := dossier_en_nummer(ident)) is not None:
            _, records = self.zoek(f'{_KAMERSTUK} AND w.dossiernummer=="{dn[0]}" AND w.ondernummer=="{dn[1]}"', maximum=10)
            # Alleen een stuk waarvan dit het hoofddossier is: een motie in vier dossiers heeft één nummer, in het eerste.
            kandidaten = [r for r in records if r.dossiers[:1] == (dn[0],) and r.ondernummer == dn[1]]
        rec = next((r for r in kandidaten if r.xml_url), kandidaten[0] if kandidaten else None)
        if rec is None:
            raise KamerstukFout(f"{ident} staat niet in de officiële publicaties", code="niet_gevonden")
        if not rec.xml_url:
            raise KamerstukFout(f"{rec.id} staat bij KOOP alleen als PDF", code="alleen_pdf", record=rec)
        return rec

    def document(self, ident: str) -> Document:
        with self._lock:
            plek = self._cache.get(ident)
            if plek is not None:
                self._cache.move_to_end(ident)
                if self._klok() - plek.gezien < VERS_S:
                    return plek.doc
        try:
            rec = self.record(ident)
        except KamerstukFout as exc:
            # Alleen een storing mag de bewaarde versie geven; een stuk dat er niet meer is, is geen storing.
            if plek is None or exc.code != "onbereikbaar":
                raise
            logger.warning("kamerstuk niet gevalideerd", extra={"kamerstuk": ident, "bron_hash": plek.doc.hash})
            return replace(plek.doc, gevalideerd=False)
        if plek is not None and plek.stand == rec.stand:
            with self._lock:
                plek.gezien = self._klok()
            return plek.doc
        xml = self._get(rec.xml_url)
        doc = Document(rec.id, xml, tekst_hash(xml.decode("utf-8", errors="replace")), gewijzigd=rec.gewijzigd,
                       documentstatus=rec.documentstatus, versie=rec.versie, record=rec)
        if plek is not None and plek.doc.hash != doc.hash:
            logger.info("kamerstuk_gewijzigd", extra={"kamerstuk": ident, "oude_hash": plek.doc.hash, "bron_hash": doc.hash,
                                                      "gewijzigd": rec.gewijzigd, "documentstatus": rec.documentstatus})
        logger.info("kamerstuk opgehaald", extra={"kamerstuk": ident, "bron_hash": doc.hash, "omvang": len(xml)})
        with self._lock:
            self._cache[ident] = _Plek(doc, rec.stand, self._klok())
            self._cache.move_to_end(ident)
            while len(self._cache) > MAX_CACHE or (
                    len(self._cache) > 1 and sum(len(p.doc.xml) for p in self._cache.values()) > MAX_CACHE_BYTES):
                self._cache.popitem(last=False)
        return doc

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:  # noqa: BLE001 – best-effort, zoals MCPClient.close
            pass
