"""Linked Data Overheid en de open data van de Rechtspraak – de transportlaag onder de Rechtspraaktools (ADR-013).

Alleen lezen, alleen vaste hosts:

- **LiDO** (`linkeddata.overheid.nl/service`, KOOP, CC0): welke uitspraken een wetsartikel noemen;
- **de BWB-zoekdienst** (`zoekservice.overheid.nl/sru`): de toestanddatums van een regeling, voor de terugval;
- **de Rechtspraak** (`data.rechtspraak.nl/uitspraken/content`, Public Domain Mark): de tekst van één uitspraak.

De URL's bouwt deze module, nooit het model; `agent/tools/rechtspraak_tools.py` kiest alleen artikel en ECLI.

Wat de spike van 10 nov 2026 liet zien (`docs/architectuur/metingen/lido-spike-2026-11-10/`), en hoe het hier zit:

- **Een link hangt aan een versie van het artikel**, niet aan het artikel: een uitspraak landt op de versie die gold
  op haar eigen datum (art. 9 Iw: 12 uitspraken op de huidige versie, 196 over alle versies). `koppelingen` loopt
  daarom van de nieuwste versie terug: de vorige versie is die op de dag vóór de begindatum.
- **Twee manieren om een versie te vinden**, en geen van beide is overal compleet. `juriconnect-ref` (bwb-id en
  artikel, met een datum) vond bij de Iw de meeste versies, maar geeft bij de Awb niets. De volledige jci met de datum
  van een bestaande BWB-toestand werkt overal, maar vond bij de Iw minder. Dus eerst de ref, en alleen als die niets
  geeft de jci. LiDO kent geen relatie "vorige versie", dus een lijst is altijd "ten minste deze".
- **De nieuwste toestand kent LiDO vaak nog niet**: de jci-route probeert de nieuwste toestanden tot er één bekend is.
- **`get-links` breekt soms stil af**: HTTP 200 met een JSON-foutmelding midden in de XML (4 % van de versies bij de
  Iw). Elk antwoord wordt eerst als XML gelezen; lukt dat niet, dan dezelfde links uit het RDF-formaat. Lukt ook dat
  niet, dan staat die versie in `onvolledig` – nooit stil een kortere lijst.
- **Begrensd**: hoogstens `MAX_AANROEPEN` per artikel en `MAX_PAGINAS` per versie. Wat daarbuiten valt, staat in
  `onvolledig`, met de telling van LiDO zelf (`totaal_lido`).

Gecachet per artikel (`VERS_S`) en per ECLI, begrensd op aantal en (uitspraken) op bytes. Een uitspraak verandert na
publicatie (een inhoudsindicatie of relatie komt erbij): na `VERS_S` vraagt de adapter alleen de metadata
(`return=META`) en haalt de tekst pas opnieuw als `dcterms:modified` verschilt (log `uitspraak_gewijzigd`). Is de
Rechtspraak dan niet bereikbaar, dan de bewaarde versie met `gevalideerd=False`, nooit stil. Een citaat blijft
herleidbaar via de teksthash.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
import threading
import time
import xml.etree.ElementTree as ET
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from urllib.parse import urlparse

import httpx
from bronmodel import tekst_hash

logger = logging.getLogger("graph_qa.rechtspraak")

LIDO_URL = "https://linkeddata.overheid.nl/service"
BWB_SRU_URL = "https://zoekservice.overheid.nl/sru/Search"
RECHTSPRAAK_URL = "https://data.rechtspraak.nl/uitspraken/content"
_HOSTS = {"linkeddata.overheid.nl", "zoekservice.overheid.nl", "data.rechtspraak.nl"}

#: Zo lang geldt een opgehaalde lijst of uitspraak zonder nieuwe vraag aan de dienst. LiDO werkt de links per import
#: bij (de laatste was 2 jul 2026), dus een paar uur is ruim veilig.
VERS_S = 6 * 3600
MAX_CACHE = 64
#: Hoogstens zoveel XML aan uitspraken in de cache; een uitspraak van de Raad van State is al gauw een halve MB.
MAX_CACHE_BYTES = 32 * 1024 * 1024
#: Per artikel hoogstens zoveel aanroepen naar LiDO (versies vinden plus links ophalen). Iw art. 36 kostte er 15.
MAX_AANROEPEN = 80
#: Per versie hoogstens zoveel pagina's van `get-links` (50 per pagina). Awb art. 8:57 noemt er meer dan 10.000.
MAX_PAGINAS = 20
RIJEN = 50
#: Hoogstens zoveel verzoeken per seconde per host. De open data van de Rechtspraak vraagt er hoogstens 10 en "houd
#: rekening met andere gebruikers"; LiDO en de BWB-zoekdienst zijn gedeelde diensten van KOOP. Eén artikel kan tot
#: `MAX_AANROEPEN` aanroepen kosten, dus zonder begrenzer gingen die in één ademteug.
PER_SECONDE = 5
#: Wachttijd voor de ene herhaling na een storing.
HERHAAL_S = 1.0
#: Hoe ver terug: het BWB begint in 2002, LiDO ook.
BEGIN = "2002-01-01"
MAX_VERSIES = 40

FOUTCODES = ("onbereikbaar", "geweigerd", "niet_gevonden")

_RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
_RL = "{http://linkeddata.overheid.nl/terms/}"
_ID_RE = re.compile(r"<id>([^<]+)</id>")


class RechtspraakFout(RuntimeError):
    """LiDO of de Rechtspraak was niet bruikbaar, met de reden (`FOUTCODES`)."""

    def __init__(self, melding: str, *, code: str = "onbereikbaar"):
        super().__init__(melding)
        self.code = code


@dataclass(frozen=True)
class Link:
    """Eén uitspraak die een versie van het artikel noemt."""
    ecli: str
    #: De titel zoals LiDO die van de Rechtspraak overneemt ("ECLI:… - Hoge Raad, 21-01-2022 / 21/00733"); leeg uit RDF.
    titel: str
    #: "Door computer herkende referentie" (LinkExtractor) of "Redactionele referentie".
    soort_link: str
    versie: str


@dataclass(frozen=True)
class Koppelingen:
    """Wat LiDO bij een artikel noemt, over alle gevonden versies."""
    links: tuple[Link, ...]
    versies: tuple[str, ...]
    #: Versies waarvan niet alles binnenkwam (plafond of kapotte antwoorden), met de reden.
    onvolledig: tuple[tuple[str, str], ...] = ()
    #: De route waarlangs de versies gevonden zijn: "ref" of "jci".
    route: str = ""
    #: Per versie hoeveel jurisprudentie LiDO zelf telt (facet van de eerste pagina).
    totaal_lido: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Document:
    id: str
    xml: bytes
    hash: str
    gewijzigd: str = ""
    #: False als de bewaarde versie niet opnieuw getoetst kon worden (de Rechtspraak was niet bereikbaar).
    gevalideerd: bool = True


def _ids(tekst: str) -> list[str]:
    """De versie-id's in een `get-id`-antwoord; LiDO geeft soms een tweede, kapotte zonder BWB-id ("/bwb/id//…")."""
    return [i for i in _ID_RE.findall(tekst or "") if "/bwb/id//" not in i]


def begindatum(versie: str) -> str:
    """`…/bwb/id/BWBR0004770/2910654/2016-05-01/2016-05-01` → 2016-05-01 (de geldigheid; de zichtdatum staat erna)."""
    delen = versie.rstrip("/").split("/")
    return delen[-2] if len(delen) >= 2 else ""


def _dag_ervoor(datum: str) -> str | None:
    try:
        return (dt.date.fromisoformat(datum) - dt.timedelta(days=1)).isoformat()
    except ValueError:
        return None


def _met_datum(jci: str, datum: str) -> str:
    jci = re.sub(r"&z=[0-9-]+", f"&z={datum}", jci)
    jci = re.sub(r"&g=[0-9-]+", f"&g={datum}", jci)
    if "&g=" not in jci:
        jci += f"&z={datum}&g={datum}"
    return jci


def _gewijzigd_in(root: ET.Element) -> str:
    return next(((e.text or "").strip() for e in root.iter() if e.tag.endswith("modified")), "")


def _gewijzigd(tekst: str) -> str:
    """`dcterms:modified` uit een antwoord met alleen de metadata (`return=META`); leeg als het niet te lezen is, en dan
    haalt de adapter de tekst opnieuw – liever een aanroep te veel dan een verouderde uitspraak."""
    try:
        return _gewijzigd_in(ET.fromstring(tekst))
    except ET.ParseError:
        return ""


def _groep(uri: str) -> str:
    if "/jurisprudentie/id/" in uri:
        return "Jurisprudentie"
    return "Wet" if "/bwb/id/" in uri else "Overig"


def links_xml(tekst: str, versie: str) -> tuple[list[Link], int, int | None]:
    """(links, aantal items op de pagina, telling van LiDO) uit één pagina van `get-links` als XML. Een ongeldig
    antwoord is een `ET.ParseError`; de aanroeper valt dan terug op RDF."""
    root = ET.fromstring(tekst)
    subjecten = [x for x in root if x.tag == "subject"]
    if not subjecten:
        return [], 0, None
    titels = {x.get("id"): next((c.text or "" for c in x if c.tag.endswith("title")), "") for x in subjecten[1:]}
    uit: list[Link] = []
    for el in subjecten[0]:
        if not el.tag.endswith("inkomende-links"):
            continue
        for ln in el:
            doel = ln.get("idref") or ""
            if ln.get("groep") == "Jurisprudentie" or _groep(doel) == "Jurisprudentie":
                uit.append(Link(doel.rstrip("/").rsplit("/", 1)[-1], (titels.get(doel) or "").strip(),
                                ln.get("label") or "", versie))
    telling = None
    for facet in root.iter("facet"):
        if facet.get("name") == "obj_type":
            for i in facet:
                if i.get("name") == "Jurisprudentie":
                    telling = int(i.text or 0)
            telling = telling or 0
    return uit, len(subjecten) - 1, telling


def links_rdf(tekst: str, versie: str) -> list[Link]:
    """Dezelfde inkomende jurisprudentielinks uit het RDF-formaat (`get-links` zonder `output=xml`), zonder titel."""
    uit: list[Link] = []
    for d in ET.fromstring(tekst).iter(f"{_RDF}Description"):
        typ = d.find(f"{_RDF}type")
        if typ is None or not typ.get(f"{_RDF}resource", "").endswith("/LinkAct"):
            continue
        van, naar, lt = (d.find(f"{_RL}{n}") for n in ("linktVan", "linktNaar", "heeftLinktype"))
        if van is None or naar is None or naar.get(f"{_RDF}resource") != versie:
            continue
        bron = van.get(f"{_RDF}resource", "")
        if _groep(bron) != "Jurisprudentie":
            continue
        soort = (lt.get(f"{_RDF}resource", "") if lt is not None else "")
        label = "Door computer herkende referentie" if soort.endswith("lx-referentie") else "Redactionele referentie"
        uit.append(Link(bron.rstrip("/").rsplit("/", 1)[-1], "", label, versie))
    return uit


@dataclass
class _Plek:
    waarde: object
    gezien: float


class LidoRechtspraak:
    """De echte bron; tests gebruiken een nep met dezelfde twee methoden (`koppelingen`, `document`)."""

    def __init__(self, *, lido_url: str = LIDO_URL, bwb_sru_url: str = BWB_SRU_URL,
                 rechtspraak_url: str = RECHTSPRAAK_URL, timeout: float = 20.0, client: httpx.Client | None = None,
                 klok: Callable[[], float] = time.monotonic, slaap: Callable[[float], None] = time.sleep):
        self._lido, self._sru, self._rs = lido_url.rstrip("/"), bwb_sru_url, rechtspraak_url
        self._client = client or httpx.Client(timeout=timeout, follow_redirects=False,
                                              headers={"User-Agent": "wetsanalyse-graph-qa (alleen lezen)"})
        self._cache: OrderedDict[str, _Plek] = OrderedDict()
        self._lock = threading.Lock()
        self._klok = klok
        self._slaap = slaap
        self._beurt: dict[str, float] = {}
        self._beurt_lock = threading.Lock()

    # --- transport -------------------------------------------------------------------------------------------------

    def _wacht(self, host: str) -> None:
        """Hoogstens `PER_SECONDE` verzoeken per host, over threads heen: elk verzoek krijgt een eigen tijdvak."""
        with self._beurt_lock:
            nu = self._klok()
            start = max(nu, self._beurt.get(host, 0.0))
            self._beurt[host] = start + 1.0 / PER_SECONDE
        if start > nu:
            self._slaap(start - nu)

    def _get(self, url: str, **params) -> str:
        u = urlparse(url)
        if u.scheme != "https" or u.hostname not in _HOSTS:
            raise RechtspraakFout(f"host buiten de allowlist: {u.hostname}", code="geweigerd")
        for poging in range(2):
            self._wacht(u.hostname)
            try:
                r = self._client.get(url, params=params or None)
            except httpx.HTTPError as exc:
                if poging == 0:
                    self._slaap(HERHAAL_S)
                    continue
                raise RechtspraakFout(f"{u.hostname} is niet bereikbaar: {type(exc).__name__}") from exc
            # LiDO geeft soms even een 400 of 5xx op een verzoek dat een tel later lukt (live, 10 nov 2026): één keer
            # opnieuw, zodat één hik geen gat in de lijst wordt.
            if poging == 0 and (r.status_code >= 500 or (r.status_code == 400 and u.hostname == "linkeddata.overheid.nl")):
                self._slaap(HERHAAL_S)
                continue
            break
        if r.status_code == 404:
            raise RechtspraakFout(f"{u.hostname} kent het niet (404)", code="niet_gevonden")
        # De BWB-zoekdienst geeft soms HTTP 406 met een geldig antwoord (zoals de importer weet): de inhoud telt.
        if r.status_code == 406 and u.hostname == "zoekservice.overheid.nl" and "searchRetrieveResponse" in r.text:
            return r.text
        if r.status_code >= 400:
            raise RechtspraakFout(f"{u.hostname} gaf HTTP {r.status_code}")
        return r.text

    def _uit_cache(self, sleutel: str):
        with self._lock:
            plek = self._cache.get(sleutel)
            if plek is not None and self._klok() - plek.gezien < VERS_S:
                self._cache.move_to_end(sleutel)
                return plek.waarde
        return None

    def _in_cache(self, sleutel: str, waarde: object) -> None:
        with self._lock:
            self._cache[sleutel] = _Plek(waarde, self._klok())
            self._cache.move_to_end(sleutel)
            while len(self._cache) > MAX_CACHE or (len(self._cache) > 1 and sum(
                    len(p.waarde.xml) for p in self._cache.values() if isinstance(p.waarde, Document)) > MAX_CACHE_BYTES):
                self._cache.popitem(last=False)

    # --- versies ---------------------------------------------------------------------------------------------------

    def _toestanden(self, bwb_id: str) -> list[str]:
        tekst = self._get(self._sru, operation="searchRetrieve", version="2.0", **{"x-connection": "BWB"},
                          maximumRecords="1000", query=f"dcterms.identifier={bwb_id}")
        return sorted(set(re.findall(r"/(\d{4}-\d{2}-\d{2})_\d+/xml/", tekst)))

    def _versies(self, bwb_id: str, artikel: str, jci: str, teller: list[int]) -> tuple[list[str], str]:
        def get_id(**params) -> str | None:
            if teller[0] >= MAX_AANROEPEN:
                return None
            teller[0] += 1
            gevonden = _ids(self._get(f"{self._lido}/get-id", **params))
            return gevonden[0] if gevonden else None

        def loop(eerste: str | None, vorige: Callable[[str], str | None]) -> list[str]:
            uit: list[str] = []
            vid = eerste
            while vid and vid not in uit and len(uit) < MAX_VERSIES:
                uit.append(vid)
                begin = begindatum(vid)
                if not begin or begin <= BEGIN:
                    break
                vid = vorige(begin)
            return uit

        ref = f"{bwb_id}&artikel={artikel}"
        eerste = get_id(**{"juriconnect-ref": ref})
        if eerste:
            def via_ref(begin: str) -> str | None:
                dag = _dag_ervoor(begin)
                return get_id(**{"juriconnect-ref": f"{ref}&g={dag}&z={dag}"}) if dag else None
            return loop(eerste, via_ref), "ref"
        if not jci:
            return [], ""
        toestanden = self._toestanden(bwb_id)
        # De nieuwste toestand kent LiDO vaak nog niet (de import loopt achter): de nieuwste die hij wel kent.
        eerste = next((v for d in reversed(toestanden[-6:]) if (v := get_id(juriconnect=_met_datum(jci, d)))), None)

        def via_jci(begin: str) -> str | None:
            eerder = [d for d in toestanden if d < begin]
            return get_id(juriconnect=_met_datum(jci, eerder[-1])) if eerder else None
        return loop(eerste, via_jci), "jci"

    # --- koppelingen -----------------------------------------------------------------------------------------------

    def koppelingen(self, bwb_id: str, artikel: str, jci: str = "") -> Koppelingen:
        """De uitspraken die LiDO bij dit artikel noemt, over alle versies die te vinden zijn."""
        sleutel = f"k|{bwb_id}|{artikel}"
        if (bewaard := self._uit_cache(sleutel)) is not None:
            return bewaard  # type: ignore[return-value]
        teller = [0]
        versies, route = self._versies(bwb_id, artikel, jci, teller)
        links: list[Link] = []
        onvolledig: list[tuple[str, str]] = []
        totaal: dict[str, int] = {}
        for v in versies:
            start, paginas = 0, 0
            while True:
                if teller[0] >= MAX_AANROEPEN or paginas >= MAX_PAGINAS:
                    onvolledig.append((v, "plafond"))
                    break
                teller[0] += 1
                paginas += 1
                tekst = self._get(f"{self._lido}/get-links", id=v, output="xml", rows=str(RIJEN), start=str(start))
                try:
                    deel, items, telling = links_xml(tekst, v)
                except ET.ParseError:
                    # Afgebroken XML (een JSON-fout midden in het antwoord): dezelfde links uit RDF.
                    logger.warning("lido_xml_afgebroken", extra={"versie": v, "start": start})
                    teller[0] += 1
                    try:
                        links += links_rdf(self._get(f"{self._lido}/get-links", id=v, max="5000"), v)
                    except (ET.ParseError, RechtspraakFout):
                        onvolledig.append((v, "onleesbaar"))
                    break
                if telling is not None and start == 0:
                    totaal[v] = telling
                links += deel
                if items < RIJEN:
                    break
                start += RIJEN
        uit = Koppelingen(tuple(links), tuple(versies), tuple(onvolledig), route, totaal)
        logger.info("lido_koppelingen", extra={"bwb_id": bwb_id, "artikel": artikel, "versies": len(versies),
                                                "links": len(links), "aanroepen": teller[0], "route": route,
                                                "onvolledig": len(onvolledig)})
        self._in_cache(sleutel, uit)
        return uit

    # --- de uitspraak zelf -----------------------------------------------------------------------------------------

    def document(self, ecli: str) -> Document:
        sleutel = f"d|{ecli}"
        with self._lock:
            plek = self._cache.get(sleutel)
            if plek is not None:
                self._cache.move_to_end(sleutel)
                if self._klok() - plek.gezien < VERS_S:
                    return plek.waarde  # type: ignore[return-value]
        bewaard: Document | None = plek.waarde if plek is not None else None  # type: ignore[assignment]
        if bewaard is not None:
            try:
                gewijzigd = _gewijzigd(self._get(self._rs, id=ecli, **{"return": "META"}))
            except RechtspraakFout as exc:
                # Alleen een storing mag de bewaarde versie geven; een uitspraak die er niet meer is, is geen storing.
                if exc.code != "onbereikbaar":
                    raise
                logger.warning("uitspraak niet gevalideerd", extra={"ecli": ecli, "bron_hash": bewaard.hash})
                return replace(bewaard, gevalideerd=False)
            if gewijzigd and gewijzigd == bewaard.gewijzigd:
                with self._lock:
                    plek.gezien = self._klok()  # type: ignore[union-attr]
                return bewaard
        tekst = self._get(self._rs, id=ecli)
        try:
            root = ET.fromstring(tekst)
        except ET.ParseError as exc:
            raise RechtspraakFout(f"de Rechtspraak gaf geen leesbare XML voor {ecli}", code="geweigerd") from exc
        if not any(e.tag.endswith("identifier") and (e.text or "").strip() == ecli for e in root.iter()):
            raise RechtspraakFout(f"{ecli} staat niet in de open data van de Rechtspraak", code="niet_gevonden")
        doc = Document(ecli, tekst.encode("utf-8"), tekst_hash(tekst), _gewijzigd_in(root))
        if bewaard is not None and bewaard.hash != doc.hash:
            logger.info("uitspraak_gewijzigd", extra={"ecli": ecli, "oude_hash": bewaard.hash, "bron_hash": doc.hash,
                                                      "gewijzigd": doc.gewijzigd})
        logger.info("uitspraak opgehaald", extra={"ecli": ecli, "bron_hash": doc.hash, "omvang": len(doc.xml)})
        self._in_cache(sleutel, doc)
        return doc

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:  # noqa: BLE001 – best-effort, zoals MCPClient.close
            pass
