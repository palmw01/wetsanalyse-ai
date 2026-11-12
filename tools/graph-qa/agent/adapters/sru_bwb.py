"""De wettekst van het Basiswettenbestand, live: de bron onder de connector `wetgeving_live` (ADR-013, fase 1e).

Twee vaste hosts, alleen lezen:

- de zoekdienst van de BWB (`zoekservice.overheid.nl/sru/Search`, `x-connection=BWB`): welke regelingen er zijn, met
  hun toestanden (versies) en geldigheid;
- het repository van KOOP (`repository.officiele-overheidspublicaties.nl`): de toestand-XML zelf. De URL komt uit het
  SRU-record (`locatie_toestand`), nooit van het model; een record dat naar een andere host wijst, wordt geweigerd.

**Dezelfde lezer als de importer.** De XML gaat door `bronmodel.bwb` (XSD, parser, bronmeting), de code die de graaf
vult. Een bepaling die via deze connector binnenkomt, heeft dus dezelfde tekst als na een import. De dekking
(`model_tekens` tegen `bron_tekens`) draait bij elke lezing: onder `STANDAARD_DREMPEL` weigert de adapter de toestand
(`onvolledig`), want een tekst waaruit iets is weggevallen, mag Lex niet citeren. Structuur die de lezer niet als eigen
deel kent (`Wet.overgeslagen`) weigert hij niet: de tekst telt mee in de dekking, en de tool meldt het.

**De toestand op een peildatum.** De zoekdienst filtert op `overheidbwb.geldigheidsdatum`; de code toetst de periode
nog eens. Een toestand kan op dezelfde datum twee keer bestaan (`…_0`, `…_1`: dezelfde geldigheid, een later
zichtmoment, bv. een herstelde fout): dan wint de nieuwste die vandaag zichtbaar is, zoals bij de importer (GR-15).

**Begrensd.** Hoogstens `PER_SECONDE` verzoeken per host, een XML van hoogstens `MAX_XML_BYTES`, en een cache van
geparste toestanden (`MAX_CACHE`, `MAX_CACHE_BYTES` naar de omvang van de XML). Een toestand verandert niet; een
nieuwe toestand heeft een nieuwe URL. De zoekresultaten gelden `VERS_S`.

De zoekdienst geeft soms HTTP 406 met een geldig antwoord (zoals de importer weet): de inhoud telt, niet de status.
"""
from __future__ import annotations

import logging
import threading
import time
import xml.etree.ElementTree as ET
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any
from datetime import date
from urllib.parse import urlparse

import httpx
from bronmodel import tekst_hash
from bronmodel.bwb import TOESTAND_XSD
from bronmodel.bwb.boom import model_tekens, model_tekens_van
from bronmodel.bwb.dekking import STANDAARD_DREMPEL, bron_tekens, bron_tekens_per_artikel
from bronmodel.bwb.models import Wet
from bronmodel.bwb.parser import ParseError, ToestandParser

from .http_beleid import STANDAARD, met_herhaling

logger = logging.getLogger("graph_qa.bwb_live")

SRU_URL = "https://zoekservice.overheid.nl/sru/Search"
REPOSITORY_HOST = "repository.officiele-overheidspublicaties.nl"
_HOSTS = {"zoekservice.overheid.nl", REPOSITORY_HOST}
_NS = {
    "sru": "http://docs.oasis-open.org/ns/search-ws/sruResponse",
    "diag": "http://docs.oasis-open.org/ns/search-ws/diagnostic",
    "gzd": "http://standaarden.overheid.nl/sru",
    "dcterms": "http://purl.org/dc/terms/",
    "overheid": "http://standaarden.overheid.nl/owms/terms/",
    "srubwb": "http://standaarden.overheid.nl/bwb/terms/",
}
PER_SECONDE = 5
HERHAAL_S = 1.0
MAX_XML_BYTES = 25 * 1024 * 1024
MAX_CACHE = 8
MAX_CACHE_BYTES = 40 * 1024 * 1024
VERS_S = 60 * 60
#: "Geen einddatum" in de BWB.
OPEN_EIND = "9999-12-31"

#: Waarom een zoekvraag of een toestand niet bruikbaar was.
FOUTCODES = ("onbereikbaar", "bezet", "verzoek_geweigerd", "geweigerd", "niet_gevonden", "onvolledig", "te_groot")


class BwbFout(RuntimeError):
    """De zoekdienst of de toestand was niet bruikbaar, met de reden (`FOUTCODES`)."""

    def __init__(self, melding: str, *, code: str = "onbereikbaar"):
        super().__init__(melding)
        self.code = code


@dataclass(frozen=True)
class Toestand:
    """Eén toestand (versie) van een regeling, uit de zoekdienst."""

    bwb_id: str
    titel: str
    #: `dcterms:type`: wet, AMvB, ministeriele-regeling, …
    soort: str
    geldig_vanaf: str
    geldig_tot: str
    zicht_vanaf: str
    zicht_tot: str
    xml_url: str
    #: `overheid:authority`: het verantwoordelijke ministerie.
    ministerie: str = ""
    rechtsgebieden: tuple[str, ...] = ()
    #: `dcterms:modified`.
    gewijzigd: str = ""

    @property
    def versie(self) -> str:
        """`2026-07-01_0`: de toestand zoals het repository hem noemt (de map van de XML)."""
        delen = urlparse(self.xml_url).path.strip("/").split("/")
        return delen[2] if len(delen) > 2 else self.geldig_vanaf

    @property
    def link(self) -> str:
        """De publieke vindplaats van deze toestand."""
        return f"https://wetten.overheid.nl/{self.bwb_id}/{self.geldig_vanaf}"

    def geldt_op(self, peildatum: str) -> bool:
        return bool(self.geldig_vanaf) and self.geldig_vanaf <= peildatum <= (self.geldig_tot or OPEN_EIND)


@dataclass(frozen=True)
class Gelezen:
    """Een gelezen toestand: het model van `bronmodel.bwb`, met de hash en de dekking."""

    toestand: Toestand
    wet: Wet = field(repr=False)
    hash: str
    xsd_geldig: bool
    bron_tekens: int
    model_tekens: int
    #: Bij een toestand onder de drempel: de brontekens per artikel (`bwb-ng-variabel-deel`), zodat één artikel dat wél
    #: volledig gelezen is, toch te citeren is (`artikel_volledig`). Leeg bij een volledige toestand.
    per_artikel: dict[str, int] = field(default_factory=dict, repr=False)

    @property
    def dekking(self) -> float:
        return 1.0 if self.bron_tekens <= 0 else self.model_tekens / self.bron_tekens

    @property
    def volledig(self) -> bool:
        return self.bron_tekens > 0 and self.dekking >= STANDAARD_DREMPEL

    def artikel_volledig(self, artikel: Any) -> bool:
        """Is dit artikel volledig gelezen? Bij een volledige toestand altijd; anders per artikel tegen dezelfde drempel."""
        if self.volledig:
            return True
        pad = (getattr(artikel, "id", "") or "").removeprefix(self.toestand.bwb_id)
        bron = self.per_artikel.get(pad, 0)
        return bron > 0 and model_tekens_van(artikel) / bron >= STANDAARD_DREMPEL

    def eis_volledig(self) -> None:
        """Voor wat de hele toestand nodig heeft (de opbouw, zoeken in de tekst): onder de drempel is dat `onvolledig`."""
        if not self.volledig:
            raise BwbFout(f"de toestand {self.toestand.versie} van {self.toestand.bwb_id} is niet volledig te lezen "
                          f"(dekking {self.dekking:.1%})", code="onvolledig")


def _tekst(e: ET.Element, pad: str) -> str:
    v = e.find(pad, _NS)
    return (v.text or "").strip() if v is not None else ""


def lees_records(xml: bytes) -> tuple[int, list[Toestand]]:
    """(totaal, toestanden) uit een searchRetrieveResponse. Een SRU-diagnose is een fout, geen lege lijst."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise BwbFout(f"onleesbaar antwoord van de zoekdienst: {exc}", code="geweigerd") from exc
    if (diag := root.find(".//diag:message", _NS)) is not None:
        detail = _tekst(root, ".//diag:details")
        raise BwbFout(f"de zoekdienst weigerde de vraag: {(diag.text or '').strip()} {detail}".strip(), code="geweigerd")
    totaal = int(_tekst(root, "sru:numberOfRecords") or 0)
    uit: list[Toestand] = []
    for rec in root.iterfind(".//gzd:gzd", _NS):
        xml_url = _tekst(rec, ".//srubwb:locatie_toestand")
        if not xml_url:
            continue
        uit.append(Toestand(
            bwb_id=_tekst(rec, ".//dcterms:identifier"), titel=_tekst(rec, ".//dcterms:title"),
            soort=_tekst(rec, ".//dcterms:type"),
            geldig_vanaf=_tekst(rec, ".//srubwb:geldigheidsperiode_startdatum"),
            geldig_tot=_tekst(rec, ".//srubwb:geldigheidsperiode_einddatum") or OPEN_EIND,
            zicht_vanaf=_tekst(rec, ".//srubwb:zichtperiode_startdatum"),
            zicht_tot=_tekst(rec, ".//srubwb:zichtperiode_einddatum") or OPEN_EIND,
            xml_url=xml_url, ministerie=_tekst(rec, ".//overheid:authority"),
            rechtsgebieden=tuple(dict.fromkeys(
                t for d in rec.iterfind(".//srubwb:rechtsgebied", _NS) if (t := (d.text or "").strip()))),
            gewijzigd=_tekst(rec, ".//dcterms:modified")))
    return totaal, uit


def kies_toestand(toestanden: list[Toestand], peildatum: str, vandaag: str) -> Toestand | None:
    """De toestand die op `peildatum` geldt. Twee met dezelfde geldigheid: de nieuwste die vandaag zichtbaar is (een
    zichtbaarheid die nog moet beginnen telt niet mee, tenzij er geen andere is)."""
    geldig = [t for t in toestanden if t.geldt_op(peildatum)]
    zichtbaar = [t for t in geldig if (t.zicht_vanaf or "") <= vandaag] or geldig
    if not zichtbaar:
        return None
    return max(zichtbaar, key=lambda t: (t.geldig_vanaf, t.zicht_vanaf, t.versie))


@dataclass
class _Plek:
    waarde: object
    gezien: float
    omvang: int = 0


class SruBwb:
    """De echte bron; tests gebruiken een nep met dezelfde methoden (`zoek`, `toestanden`, `toestand_op`, `lees`)."""

    def __init__(self, *, sru_url: str = SRU_URL, timeout: float = 30.0, client: httpx.Client | None = None,
                 klok: Callable[[], float] = time.monotonic, slaap: Callable[[float], None] = time.sleep,
                 vandaag: Callable[[], str] = lambda: date.today().isoformat()):
        self._url = sru_url
        self._client = client or httpx.Client(timeout=timeout, follow_redirects=False,
                                              headers={"User-Agent": "wetsanalyse-graph-qa (alleen lezen)"})
        self._klok, self._slaap, self._vandaag = klok, slaap, vandaag
        self._zoek: OrderedDict[tuple, _Plek] = OrderedDict()
        self._gelezen: OrderedDict[str, _Plek] = OrderedDict()
        self._lock = threading.Lock()
        self._lees_locks: dict[str, threading.Lock] = {}
        self._beurt: dict[str, float] = {}
        self._beurt_lock = threading.Lock()
        self._parser = ToestandParser(schema_path=TOESTAND_XSD)

    # --- transport -------------------------------------------------------------------------------------------------

    def _wacht(self, host: str) -> None:
        """Hoogstens `PER_SECONDE` verzoeken per host, over threads heen."""
        with self._beurt_lock:
            nu = self._klok()
            start = max(nu, self._beurt.get(host, 0.0))
            self._beurt[host] = start + 1.0 / PER_SECONDE
        if start > nu:
            self._slaap(start - nu)

    def _get(self, url: str, *, params: dict[str, str] | None = None, maximum: int | None = None) -> bytes:
        u = urlparse(url)
        if u.scheme != "https" or u.hostname not in _HOSTS:
            raise BwbFout(f"host buiten de allowlist: {u.hostname}", code="geweigerd")
        try:
            r = met_herhaling(lambda: self._client.get(url, params=params), beleid=STANDAARD, host=u.hostname,
                              slaap=self._slaap, logger=logger, gebeurtenis="bwb_verzoek_mislukt",
                              voor_poging=lambda: self._wacht(u.hostname), wacht_s=HERHAAL_S)
        except httpx.HTTPError as exc:
            raise BwbFout(f"{u.hostname} is niet bereikbaar: {type(exc).__name__}") from exc
        if r.status_code == 404:
            raise BwbFout(f"{u.hostname} kent het niet (404)", code="niet_gevonden")
        # 406 met een geldige body is gewoon (de zoekdienst); de inhoud beslist.
        if r.status_code >= 400 and not (r.status_code == 406 and r.content):
            # De code volgt het gedeelde beleid (`http_beleid`): een 4xx is geen storing, een 5xx na de herhalingen wel.
            raise BwbFout(f"{u.hostname} antwoordde met HTTP {r.status_code}", code=STANDAARD.foutcode(r.status_code))
        if not r.content:
            raise BwbFout(f"leeg antwoord van {u.hostname}")
        if maximum is not None and len(r.content) > maximum:
            raise BwbFout(f"de toestand is groter dan {maximum // (1024 * 1024)} MB", code="te_groot")
        return r.content

    # --- zoeken ----------------------------------------------------------------------------------------------------

    def zoek(self, cql: str, *, start: int = 1, maximum: int = 50) -> tuple[int, list[Toestand]]:
        """Toestanden bij een CQL-vraag (gebouwd door de tools, nooit door het model). Gecachet `VERS_S`."""
        sleutel = (cql, start, maximum)
        with self._lock:
            plek = self._zoek.get(sleutel)
            if plek is not None and self._klok() - plek.gezien < VERS_S:
                self._zoek.move_to_end(sleutel)
                return plek.waarde  # type: ignore[return-value]
        params = {"operation": "searchRetrieve", "version": "2.0", "x-connection": "BWB", "query": cql,
                  "startRecord": str(start), "maximumRecords": str(maximum)}
        uitkomst = lees_records(self._get(self._url, params=params))
        with self._lock:
            self._zoek[sleutel] = _Plek(uitkomst, self._klok())
            while len(self._zoek) > 256:
                self._zoek.popitem(last=False)
        return uitkomst

    def toestanden(self, bwb_id: str) -> list[Toestand]:
        """Alle toestanden van een regeling, oudste eerst. Geen enkele: `niet_gevonden`."""
        _, rijen = self.zoek(f"dcterms.identifier={bwb_id}", maximum=1000)
        rijen = [t for t in rijen if t.bwb_id == bwb_id]
        if not rijen:
            raise BwbFout(f"{bwb_id} staat niet in het Basiswettenbestand", code="niet_gevonden")
        return sorted(rijen, key=lambda t: (t.geldig_vanaf, t.zicht_vanaf, t.versie))

    def toestand_op(self, bwb_id: str, peildatum: str | None = None) -> Toestand:
        """De toestand die op `peildatum` (standaard vandaag) geldt."""
        vandaag = self._vandaag()
        peil = peildatum or vandaag
        _, rijen = self.zoek(f"dcterms.identifier={bwb_id} and overheidbwb.geldigheidsdatum={peil}", maximum=20)
        gekozen = kies_toestand([t for t in rijen if t.bwb_id == bwb_id], peil, vandaag)
        if gekozen is None:
            alle = self.toestanden(bwb_id)  # niet_gevonden als de regeling helemaal niet bestaat
            eerste, laatste = alle[0].geldig_vanaf, max(t.geldig_tot for t in alle)
            # De titel erbij: een geraden BWB-id is zo zichtbaar een andere regeling (ronde 3, I20: BWBR0002471 is de
            # Wet op de loonbelasting 1964, gelezen als de Wet op de inkomstenbelasting 1964).
            raise BwbFout(f"{bwb_id} ({alle[-1].titel}) heeft geen toestand die op {peil} geldt (toestanden van {eerste} "
                          f"tot {laatste})", code="niet_gevonden")
        return gekozen

    # --- lezen -----------------------------------------------------------------------------------------------------

    def lees(self, toestand: Toestand) -> Gelezen:
        """De toestand, gelezen met de lezer van de importer. Onder de dekkingsdrempel: `onvolledig`."""
        sleutel = toestand.xml_url
        with self._lock:
            plek = self._gelezen.get(sleutel)
            if plek is not None:
                self._gelezen.move_to_end(sleutel)
                return plek.waarde  # type: ignore[return-value]
            slot = self._lees_locks.setdefault(sleutel, threading.Lock())
        # Eén lezing per toestand tegelijk: twee tools in dezelfde beurt halen hem niet twee keer.
        with slot:
            with self._lock:
                if (plek := self._gelezen.get(sleutel)) is not None:
                    return plek.waarde  # type: ignore[return-value]
            gelezen, omvang = self._haal(toestand)
            with self._lock:
                self._gelezen[sleutel] = _Plek(gelezen, self._klok(), omvang)
                self._gelezen.move_to_end(sleutel)
                while len(self._gelezen) > MAX_CACHE or (
                        len(self._gelezen) > 1 and sum(p.omvang for p in self._gelezen.values()) > MAX_CACHE_BYTES):
                    self._gelezen.popitem(last=False)
                self._lees_locks.pop(sleutel, None)
            return gelezen

    def _haal(self, toestand: Toestand) -> tuple[Gelezen, int]:
        if urlparse(toestand.xml_url).hostname != REPOSITORY_HOST:
            raise BwbFout(f"de toestand wijst naar een andere host: {urlparse(toestand.xml_url).hostname}",
                          code="geweigerd")
        xml = self._get(toestand.xml_url, maximum=MAX_XML_BYTES)
        try:
            wet = self._parser.parse(xml)
        except (ParseError, Exception) as exc:  # noqa: BLE001 – elke leesfout is een onbruikbare toestand
            raise BwbFout(f"de toestand van {toestand.bwb_id} is niet te lezen: {exc}", code="onvolledig") from exc
        if wet.bwb_id != toestand.bwb_id:
            raise BwbFout(f"de toestand draagt {wet.bwb_id}, niet {toestand.bwb_id}", code="geweigerd")
        xsd = self._parser.validate(xml)
        bron, model = bron_tekens(xml), model_tekens(wet)
        gelezen = Gelezen(toestand, wet, tekst_hash(xml.decode("utf-8", errors="replace")), xsd, bron, model)
        logger.info("bwb_toestand opgehaald", extra={
            "bwb_id": toestand.bwb_id, "toestand": toestand.versie, "omvang": len(xml), "bron_hash": gelezen.hash,
            "dekking": round(gelezen.dekking, 5), "xsd_geldig": xsd})
        if wet.overgeslagen:
            # Structuur die de lezer niet als eigen deel kent (een `<divisie>` zonder koplabel in een bijlage): de tekst
            # telt de dekking wel mee. Ontbreekt er echt iets, dan zakt de dekking; een artikel dat daardoor niet te
            # vinden is, geeft "niet gevonden", nooit een verkeerde tekst. De tool zegt het erbij.
            logger.info("bwb_toestand onbekende structuur", extra={
                "bwb_id": toestand.bwb_id, "toestand": toestand.versie, "overgeslagen": list(wet.overgeslagen)})
        if bron <= 0:
            raise BwbFout(f"de toestand {toestand.versie} van {toestand.bwb_id} heeft geen tekst", code="onvolledig")
        if not gelezen.volledig:
            # Onder de drempel: de toestand als geheel is niet te citeren (de opbouw, zoeken), maar een artikel dat zelf
            # volledig gelezen is wel (iteratie ronde 1, I03: de Algemene douanewet op 98,5% weigerde elk artikel). Die
            # keuze maakt `Gelezen.artikel_volledig`; de importer meet de toestand als geheel, en dat blijft zo.
            logger.warning("bwb_toestand onvolledig", extra={
                "bwb_id": toestand.bwb_id, "toestand": toestand.versie, "dekking": round(gelezen.dekking, 5),
                "overgeslagen": list(wet.overgeslagen)})
            gelezen = replace(gelezen, per_artikel=bron_tekens_per_artikel(xml))
        return gelezen, len(xml)

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:  # noqa: BLE001 – best-effort
            pass
