"""De officiële publicaties van KOOP via SRU 2.0 – de gedeelde transportlaag onder de connectors Kamerstukken en
Staatsblad en Staatscourant (ADR-013).

Alleen lezen, alleen vaste hosts: de zoekdienst (`repository.overheid.nl/sru`) en de documenten in diezelfde
repository. De URL van een document komt uit het SRU-record (`itemUrl manifestation="xml"`), nooit van het model;
een record dat naar een andere host wijst, wordt geweigerd. De zoekvragen bouwen de tools (`agent/tools/`); wat per
publicatie verschilt (het filter, hoe een id dat KOOP niet kent alsnog te vinden is, de naam in de logregels) staat in
een dunne subklasse (`sru_kamerstukken.py`, `sru_bekendmakingen.py`).

Gecachet per identifier, met de teksthash en de versie van KOOP: een citaat blijft zo herleidbaar naar de tekst die
Lex las. Een publicatie kan veranderen – de onopgemaakte versie wordt vervangen door de opgemaakte, en er zijn
herdruk en rectificatie (`w.documentstatus`, `w.versieinformatie`, `dt.modified`; handleiding SRU 2.0). Daarom het
cachebeleid (review ADR-013, punt 3):

- binnen `VERS_S` na lezen of valideren een hit zonder aanroep (pagineren in één gesprek);
- daarna één lichte metadatavraag; de XML komt alleen opnieuw als `dt.modified`, de status of de versie veranderde, en
  dan logt de adapter `<soort>_gewijzigd` met de oude en de nieuwe hash;
- is de dienst bij die validatie onbereikbaar, dan de bewaarde versie met `gevalideerd=False`: niets stil, en een korte
  storing breekt het lezen niet. Een miss zonder dienst blijft een fout;
- hoogstens `MAX_CACHE` documenten en `MAX_CACHE_BYTES` aan XML, de oudste eerst eruit.
"""
from __future__ import annotations

import logging
import threading
import time
import xml.etree.ElementTree as ET
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, replace
from urllib.parse import urlparse

import httpx
from bronmodel import tekst_hash

from .http_beleid import STANDAARD, met_herhaling

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
#: Een datum vóór dit jaar is een fout in de metadata (stb-2019-129 heeft `dt.date` 0004-03-01; live, 10 nov 2026):
#: dan telt hij als onbekend.
_EERSTE_JAAR = 1800

#: Waarom een stuk of een zoekvraag niet bruikbaar was. Eén foutcode voor alles ("bron_onbereikbaar") maskeerde de
#: oorzaak: een stuk met alleen een PDF heette onbereikbaar, en Lex zei dat het misschien niet bestond (acceptatie
#: 9 nov 2026, gesprek e906567a).
FOUTCODES = ("onbereikbaar", "bezet", "verzoek_geweigerd", "geweigerd", "niet_gevonden", "alleen_pdf")


class KoopFout(RuntimeError):
    """De zoekdienst of het document was niet bruikbaar, met de reden (`FOUTCODES`) en, als die er is, het record."""

    def __init__(self, melding: str, *, code: str = "onbereikbaar", record: "Record | None" = None):
        super().__init__(melding)
        self.code = code
        self.record = record


@dataclass(frozen=True)
class Record:
    """Eén SRU-record van een officiële publicatie, met alle velden die de beschrijvingen van de KOOP-connectors
    gebruiken (`bronmodel.connectors`). Een veld dat de publicatie niet kent, blijft leeg."""
    id: str
    titel: str
    #: `dt.date`: de datum van het stuk zelf. Niet de publicatiedatum: die kan weken later liggen.
    datum: str
    vergaderjaar: str
    #: `w.dossiernummer`, alle; het eerste is het hoofddossier.
    dossiers: tuple[str, ...]
    ondernummer: str
    #: Leeg als KOOP het stuk (nog) niet als XML heeft: een onopgemaakt of oud stuk heeft vaak alleen een PDF.
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
    #: `w.subrubriek`: het soort Kamerstuk ("Memorie van toelichting", "Motie", "Brief regering").
    soort: str = ""
    #: `dt.creator`: wie het stuk uitbracht (de Tweede of de Eerste Kamer, een ministerie).
    kamer: str = ""
    #: `w.indiener`, alle.
    indieners: tuple[str, ...] = ()
    #: De PDF-manifestatie, als die er is.
    pdf_url: str = ""
    #: `w.publicatienaam`: Kamerstuk, Staatsblad, Staatscourant.
    publicatienaam: str = ""
    #: `w.jaargang` en `w.publicatienummer`: het jaar en het nummer van een bekendmaking.
    jaargang: str = ""
    publicatienummer: str = ""
    #: `w.datumOndertekening`: de datum waarop het besluit is ondertekend.
    ondertekend: str = ""
    #: `w.behandeldDossier`: het Kamerdossier van de wet die het Staatsblad bekendmaakt.
    behandeld_dossiers: tuple[str, ...] = ()
    #: `dt.type`: het soort publicatie ("Wet", "AMvB", "ander besluit van algemene strekking").
    type: str = ""
    #: `dt.abstract`: de samenvatting die de publicatie zelf draagt (Staatscourant).
    samenvatting: str = ""

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


def _datum(waarde: str) -> str:
    """Een ISO-datum, of '' bij een datum die niet kan kloppen (vóór `_EERSTE_JAAR`)."""
    return waarde if waarde[:4].isdigit() and int(waarde[:4]) >= _EERSTE_JAAR else ""


def lees_records(xml: bytes, fout: type[KoopFout] = KoopFout) -> tuple[int, list[Record]]:
    """(totaal, records) uit een searchRetrieveResponse. Een SRU-diagnose is een fout, geen lege lijst."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise fout(f"onleesbaar SRU-antwoord: {exc}", code="geweigerd") from exc
    if (diag := root.find(".//diag:message", _NS)) is not None:
        raise fout(f"de zoekdienst weigerde de vraag: {(diag.text or '').strip()}", code="geweigerd")
    totaal = int(_tekst(root, "sru:numberOfRecords") or 0)
    uit: list[Record] = []
    for rec in root.iterfind(".//sru:record", _NS):
        urls = {u.get("manifestation"): (u.text or "").strip() for u in rec.iterfind(".//gzd:itemUrl", _NS)}

        def alle(pad: str) -> tuple[str, ...]:
            return tuple(t for d in rec.iterfind(pad, _NS) if (t := (d.text or "").strip()))

        gepubliceerd = _datum(_tekst(rec, ".//dcterms:available"))
        uit.append(Record(
            id=_tekst(rec, ".//dcterms:identifier"), titel=_tekst(rec, ".//dcterms:title"),
            # Eerst nam de adapter `available or date`, en die liggen soms weken uit elkaar (live, 9 nov 2026: een
            # brief van 25 september, gepubliceerd op 9 november). Nu elk apart; zonder `dt.date` de publicatiedatum.
            datum=_datum(_tekst(rec, ".//dcterms:date")) or gepubliceerd,
            gepubliceerd=gepubliceerd,
            vergaderjaar=_tekst(rec, ".//ow:vergaderjaar"), dossiers=alle(".//ow:dossiernummer"),
            ondernummer=_tekst(rec, ".//ow:ondernummer"), xml_url=urls.get("xml", ""), pdf_url=urls.get("pdf", ""),
            gewijzigd=_tekst(rec, ".//dcterms:modified"), documentstatus=_tekst(rec, ".//ow:documentstatus"),
            versie=" ".join(v for v in (_tekst(rec, ".//ow:versieinformatie"), _tekst(rec, ".//ow:versienummer")) if v),
            documenttitel=_tekst(rec, ".//ow:documenttitel"), dossiertitel=_tekst(rec, ".//ow:dossiertitel"),
            soort=_tekst(rec, ".//ow:subrubriek"), kamer=_tekst(rec, ".//dcterms:creator"),
            indieners=alle(".//ow:indiener"), publicatienaam=_tekst(rec, ".//ow:publicatienaam"),
            jaargang=_tekst(rec, ".//ow:jaargang"), publicatienummer=_tekst(rec, ".//ow:publicatienummer"),
            ondertekend=_datum(_tekst(rec, ".//ow:datumOndertekening")),
            behandeld_dossiers=alle(".//ow:behandeldDossier"), type=_tekst(rec, ".//dcterms:type"),
            samenvatting=_tekst(rec, ".//dcterms:abstract")))
    return totaal, uit


class SruKoop:
    """De echte bron voor één soort publicatie; tests gebruiken een nep met dezelfde twee methoden (`zoek`, `document`).

    Een subklasse zet `SOORT` (de naam in de logregels: `kamerstuk_gewijzigd`), `FOUT` (de foutklasse), `_logger` en
    `_terugval` (de records van een stuk waarvan KOOP het id niet kent: een herdruk heeft een eigen id)."""

    SOORT = "publicatie"
    FOUT: type[KoopFout] = KoopFout
    _logger = logging.getLogger("graph_qa.koop")

    def __init__(self, *, sru_url: str = SRU_URL, timeout: float = 20.0, client: httpx.Client | None = None,
                 klok: Callable[[], float] = time.monotonic, slaap: Callable[[float], None] = time.sleep):
        self._url = sru_url
        self._slaap = slaap
        self._client = client or httpx.Client(timeout=timeout, follow_redirects=False)
        self._cache: OrderedDict[str, _Plek] = OrderedDict()
        self._lock = threading.Lock()
        self._klok = klok

    def _get(self, url: str, **params) -> bytes:
        u = urlparse(url)
        if u.scheme != "https" or u.hostname not in _HOSTS:
            raise self.FOUT(f"host buiten de allowlist: {u.hostname}", code="geweigerd")
        # Het gedeelde beleid (`http_beleid`): een storing gaat opnieuw, en alleen een storing heet "niet bereikbaar"; een
        # 4xx was hier ook "onbereikbaar", zonder herhaling.
        try:
            r = met_herhaling(lambda: self._client.get(url, params=params or None), beleid=STANDAARD,
                              host=u.hostname or "", slaap=self._slaap, logger=self._logger,
                              gebeurtenis="koop_verzoek_mislukt")
        except httpx.HTTPError as exc:
            raise self.FOUT(f"de officiële publicaties zijn niet bereikbaar: {type(exc).__name__}",
                            code="onbereikbaar") from exc
        if r.status_code >= 400:
            code = STANDAARD.foutcode(r.status_code)
            raise self.FOUT(f"de officiële publicaties antwoordden met HTTP {r.status_code}", code=code)
        return r.content

    def zoek(self, cql: str, *, start: int = 1, maximum: int = 50) -> tuple[int, list[Record]]:
        return lees_records(self._get(self._url, query=cql, startRecord=start, maximumRecords=maximum), self.FOUT)

    def _terugval(self, ident: str) -> list[Record]:
        """De kandidaten voor een id dat KOOP niet kent; standaard geen."""
        return []

    def record(self, ident: str) -> Record:
        """Het record van een stuk; staat het id niet bij KOOP, dan via `_terugval`. Een stuk met alleen een PDF is
        `alleen_pdf`, met het record erbij: het bestaat, maar de tekst is niet te lezen."""
        _, records = self.zoek(f"c.product-area==officielepublicaties AND dt.identifier=={ident}", maximum=1)
        kandidaten = [r for r in records if r.id == ident] or self._terugval(ident)
        rec = next((r for r in kandidaten if r.xml_url), kandidaten[0] if kandidaten else None)
        if rec is None:
            raise self.FOUT(f"{ident} staat niet in de officiële publicaties", code="niet_gevonden")
        if not rec.xml_url:
            raise self.FOUT(f"{rec.id} staat bij KOOP alleen als PDF", code="alleen_pdf", record=rec)
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
        except KoopFout as exc:
            # Alleen een storing mag de bewaarde versie geven; een stuk dat er niet meer is, is geen storing.
            if plek is None or exc.code != "onbereikbaar":
                raise
            self._logger.warning(f"{self.SOORT} niet gevalideerd", extra={self.SOORT: ident, "bron_hash": plek.doc.hash})
            return replace(plek.doc, gevalideerd=False)
        if plek is not None and plek.stand == rec.stand:
            with self._lock:
                plek.gezien = self._klok()
            return plek.doc
        xml = self._get(rec.xml_url)
        doc = Document(rec.id, xml, tekst_hash(xml.decode("utf-8", errors="replace")), gewijzigd=rec.gewijzigd,
                       documentstatus=rec.documentstatus, versie=rec.versie, record=rec)
        if plek is not None and plek.doc.hash != doc.hash:
            self._logger.info(f"{self.SOORT}_gewijzigd", extra={
                self.SOORT: ident, "oude_hash": plek.doc.hash, "bron_hash": doc.hash, "gewijzigd": rec.gewijzigd,
                "documentstatus": rec.documentstatus})
        self._logger.info(f"{self.SOORT} opgehaald", extra={self.SOORT: ident, "bron_hash": doc.hash, "omvang": len(xml)})
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
