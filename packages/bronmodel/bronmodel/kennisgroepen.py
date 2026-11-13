"""De lezer van de kennisgroepstandpunten van de Belastingdienst (plan-connector-kennisgroepen.md).

Gedeeld door de importer (de index in de graaf, `bwb-import --kennisgroepen`) en graph-qa (de leestool van de connector
`kennisgroepen`), zodat beide uit dezelfde publicatie dezelfde tekst, dezelfde rijen, dezelfde hash en dezelfde metadata
afleiden. Alleen de standaardbibliotheek: het transport (HTTP) is van de aanroeper; hier staan de URL's en het lezen.

De bron is de openbare WordPress REST API van https://kennisgroepen.belastingdienst.nl (pagina *Integratie*), CC0. Een
standpunt is **beleid van de Belastingdienst**, bindend voor de inspecteur; geen wet en geen rechtspraak.

Wat de bron levert en wat deze lezer ermee doet (getoetst op alle 1180 publicaties, 13 nov 2026):

- het kenmerk staat alleen in de titel (`KG:013:2026:4 Onderwerp`), soms met `[INGETROKKEN]` of `[VERVALLEN]` ervoor
  en in drie titels in een afwijkende vorm (`KG:2026:211:19`, `KG 202:2025:26`, `KG:204:2023: 5`): `kenmerk_uit_titel`;
- de tekst is HTML met `h2`-koppen (Aanleiding, Vraag, Antwoord, Beschouwing, Voetnoten), `h3`-subkoppen, lijsten,
  tabellen en een blok *Let op!* (`h6`, bijvoorbeeld *Intrekking*): `rijen_uit_html`;
- verwijzingen staan als link (jci, BWB, ECLI, Kamerstuk, Stcrt, EUR-Lex, een ander standpunt, een PDF) of alleen in de
  tekst; elke verwijzing draagt haar herkomst (`link` of `tekst`) en de rij waar ze staat: `verwijzingen`;
- een standpunt dat een ander intrekt, zegt dat in de tekst ("Met dit standpunt wordt … KG:013:2018:0173 …
  ingetrokken"): `vervangt`;
- de metadata komt uit de velden en de taxonomieën (`_embed`): `metadata`.
"""
from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import unquote, urlencode

from . import tekst_hash
from .extern import externe_verwijzingen, kg_id, kg_kenmerk

SITE = "https://kennisgroepen.belastingdienst.nl"
API = SITE + "/wp-json/wp/v2"
HOST = "kennisgroepen.belastingdienst.nl"
#: Meer geeft WordPress niet per pagina.
PER_PAGINA = 100

STATUS_GELDEND = "geldend"
STATUS_INGETROKKEN = "ingetrokken"
STATUS_VERVALLEN = "vervallen"
STATUSSEN = (STATUS_GELDEND, STATUS_INGETROKKEN, STATUS_VERVALLEN)


# ── URL's ──────────────────────────────────────────────────────────────────────────────────────────────────────────

def lijst_url(pagina: int = 1, *, per_pagina: int = PER_PAGINA, gewijzigd_na: str | None = None,
              soort: str = "wt_publication") -> str:
    """De lijst publicaties (`wt_publication`) of nieuwsberichten (`posts`), met de namen van de termen (`_embed`)."""
    params: dict[str, Any] = {"_embed": "1", "per_page": per_pagina, "page": pagina, "orderby": "id", "order": "asc"}
    if gewijzigd_na:
        params["modified_after"] = gewijzigd_na
    return f"{API}/{soort}?{urlencode(params)}"


def item_url(wp_id: int) -> str:
    """Eén publicatie op haar WordPress-id."""
    return f"{API}/wt_publication/{int(wp_id)}?_embed=1"


# ── Kenmerk en status ──────────────────────────────────────────────────────────────────────────────────────────────

_KENMERK_RE = re.compile(r"\bKG\s*[:\s]\s*(\d{3,4})\s*:\s*(\d{3,4})\s*:\s*(\d{1,4})\b", re.I)
_STATUS_RE = re.compile(r"^\W*(ingetrokken|vervallen)\W*", re.I)


def kenmerk_uit_titel(titel: str) -> tuple[str | None, str, str]:
    """(id, status, onderwerp) uit de titel van een publicatie. Het id is canoniek (`kg:013:2026:4`), of None als de
    titel geen kenmerk draagt. Een omgedraaid jaar en kennisgroepnummer (`KG:2026:211:19`) en spaties in plaats van een
    dubbele punt worden gelezen zoals bedoeld: drie cijfers zijn de kennisgroep, vier het jaar."""
    titel = " ".join(_html.unescape(titel or "").replace("\xa0", " ").split())
    status = STATUS_GELDEND
    if m := _STATUS_RE.match(titel):
        status = m.group(1).lower()
        titel = titel[m.end():]
    m = _KENMERK_RE.search(titel)
    if not m:
        return None, status, titel
    a, b, nr = m.groups()
    groep, jaar = (b, a) if len(a) == 4 and len(b) == 3 else (a, b)
    if len(groep) != 3 or len(jaar) != 4:
        return None, status, titel
    onderwerp = (titel[:m.start()] + titel[m.end():]).strip(" -–:")
    return kg_id(groep, jaar, nr), status, onderwerp


# ── HTML naar rijen ────────────────────────────────────────────────────────────────────────────────────────────────

@dataclass
class Link:
    href: str
    tekst: str


@dataclass
class Rij:
    """Eén genummerde passage in documentvolgorde (het leestoolcontract van ADR-013): `soort` is `alinea`, `voetnoot`,
    `tabel` (de kop van een tabel, met de kolommen als `cellen`) of `tabelrij`."""
    nr: int
    tekst: str
    kop: str
    soort: str = "alinea"
    cellen: tuple[str, ...] = ()
    tabel: int = 0
    links: list[Link] = field(default_factory=list)

    def als_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"nr": self.nr, "tekst": self.tekst, "kop": self.kop, "soort": self.soort}
        if self.cellen:
            d["cellen"] = list(self.cellen)
        if self.tabel:
            d["tabel"] = self.tabel
        return d


def _schoon(tekst: str) -> str:
    return " ".join(tekst.replace("\xa0", " ").split())


#: Koppen waaronder de passages voetnoten zijn.
_VOETNOOTKOPPEN = re.compile(r"^voetno(?:ot|ten)$", re.I)
_BLOK = {"p", "li", "figcaption", "blockquote", "dt", "dd", "pre"}
_OVERSLAAN = {"script", "style", "svg", "noscript"}


class _Lezer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rijen: list[Rij] = []
        #: De koppen per niveau (h1–h6); een kop wist de diepere. Het blok *Let op!* (`h6`) is het diepste niveau.
        self.koppen: dict[int, str] = {}
        self._kop_buf: list[str] | None = None
        self._kop_niveau = ""
        self._buf: list[str] | None = None
        self._links: list[Link] = []
        self._a: tuple[str, list[str]] | None = None
        self._overslaan = 0
        self._diepte_blok = 0
        # tabellen
        self._tabel: list[list[str]] | None = None
        self._rij: list[str] | None = None
        self._cel: list[str] | None = None
        self._tabel_links: list[Link] = []
        self._tabellen = 0
        #: Afbeeldingen vóór de eerste rij; ze gaan naar de eerste rij.
        self._los: list[Link] = []

    @property
    def h2(self) -> str:
        return self.koppen.get(2, "")

    @property
    def kop(self) -> str:
        return " › ".join(self.koppen[n] for n in sorted(self.koppen) if self.koppen[n])

    def _tekst_naar(self, data: str) -> None:
        if self._kop_buf is not None:
            self._kop_buf.append(data)
        if self._cel is not None:
            self._cel.append(data)
        elif self._buf is not None:
            self._buf.append(data)
        if self._a is not None:
            self._a[1].append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _OVERSLAAN:
            self._overslaan += 1
            return
        if self._overslaan:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._kop_buf, self._kop_niveau = [], tag
        elif tag == "table":
            self._tabel, self._tabel_links = [], []
        elif tag == "tr" and self._tabel is not None:
            self._rij = []
        elif tag in ("td", "th") and self._rij is not None:
            self._cel = []
        elif tag in _BLOK:
            if self._buf is None:
                self._buf, self._links = [], []
            self._diepte_blok += 1
        elif tag == "br":
            self._tekst_naar(" ")
        elif tag == "img":
            # Een afbeelding staat niet in de tekst, maar het standpunt draagt haar: een bijlage met haar link.
            a = dict(attrs)
            if src := _html.unescape(a.get("src") or ""):
                link = Link(src, _schoon(a.get("alt") or "") or "afbeelding")
                if self._tabel is not None:
                    self._tabel_links.append(link)
                elif self._buf is not None:
                    self._links.append(link)
                elif self.rijen:
                    self.rijen[-1].links.append(link)
                else:
                    self._los.append(link)
        elif tag == "a":
            href = dict(attrs).get("href") or ""
            self._a = (_html.unescape(href), [])

    def handle_endtag(self, tag: str) -> None:
        if tag in _OVERSLAAN:
            self._overslaan = max(0, self._overslaan - 1)
            return
        if self._overslaan:
            return
        if tag == "a" and self._a is not None:
            href, tekst = self._a
            self._a = None
            if href and not href.startswith("#"):
                link = Link(href, _schoon("".join(tekst)))
                (self._tabel_links if self._tabel is not None else self._links).append(link)
        elif tag == self._kop_niveau and self._kop_buf is not None:
            kop = _schoon("".join(self._kop_buf)).rstrip(" :")
            self._kop_buf = None
            niveau = int(tag[1])
            self.koppen = {n: k for n, k in self.koppen.items() if n < niveau}
            self.koppen[niveau] = kop
        elif tag in ("td", "th") and self._cel is not None and self._rij is not None:
            self._rij.append(_schoon("".join(self._cel)))
            self._cel = None
        elif tag == "tr" and self._rij is not None and self._tabel is not None:
            if any(self._rij):
                self._tabel.append(self._rij)
            self._rij = None
        elif tag == "table" and self._tabel is not None:
            self._sluit_tabel()
        elif tag in _BLOK and self._buf is not None:
            self._diepte_blok -= 1
            if self._diepte_blok <= 0:
                self._sluit_blok()

    def handle_data(self, data: str) -> None:
        if not self._overslaan:
            self._tekst_naar(data)

    def _soort(self) -> str:
        return "voetnoot" if _VOETNOOTKOPPEN.match(self.h2 or "") else "alinea"

    def _sluit_blok(self) -> None:
        tekst = _schoon("".join(self._buf or []))
        if tekst:
            self.rijen.append(Rij(len(self.rijen) + 1, tekst, self.kop, self._soort(), links=self._links))
        self._buf, self._links, self._diepte_blok = None, [], 0

    def _sluit_tabel(self) -> None:
        tabel = self._tabel or []
        self._tabel = None
        if not tabel:
            return
        self._tabellen += 1
        kop, *rest = tabel
        self.rijen.append(Rij(len(self.rijen) + 1, " | ".join(kop), self.kop, "tabel", tuple(kop), self._tabellen,
                              links=[]))
        for i, cellen in enumerate(rest):
            links = self._tabel_links if i == 0 else []
            self.rijen.append(Rij(len(self.rijen) + 1, " | ".join(cellen), self.kop, "tabelrij", tuple(cellen),
                                  self._tabellen, links=links))
        if not rest and self._tabel_links:
            self.rijen[-1].links = self._tabel_links

    def close(self) -> None:
        super().close()
        if self._buf is not None:
            self._sluit_blok()
        if self._los and self.rijen:
            self.rijen[0].links[:0] = self._los


def rijen_uit_html(inhoud: str) -> list[Rij]:
    """De tekst van een publicatie als genummerde rijen in documentvolgorde, elk met de kop waaronder ze staat
    ("Beschouwing › Algemeen") en de links erin. De tekst is letterlijk de bron, met alleen de witruimte genormaliseerd."""
    lezer = _Lezer()
    lezer.feed(inhoud or "")
    lezer.close()
    return lezer.rijen


def bron_hash(rijen: list[Rij]) -> str:
    """De hash van de gelezen tekst: dezelfde publicatie geeft in de importer en in de leestool dezelfde hash."""
    return tekst_hash("\n".join(r.tekst for r in rijen))


# ── Verwijzingen ───────────────────────────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Verwijzing:
    """Iets dat een standpunt noemt. `soort` is `bepaling` (een jci), `regeling` (alleen een BWB-id), een brontype uit
    `extern.BRONTYPEN` (`uitspraak`, `kamerstuk`, `bekendmaking`, `eu`, `standpunt`), `publicatie` (een link naar een
    andere publicatie op de site, op haar slug) of `bijlage` (een bestand). `herkomst` is `link` (de Belastingdienst
    linkt zelf) of `tekst` (het id staat alleen in de tekst)."""
    soort: str
    doel: str
    herkomst: str
    rij: int
    tekst: str = ""
    bwb_id: str = ""
    delen: tuple[tuple[str, str], ...] = ()


_JCI_RE = re.compile(r"jci1\.\d+:c:(BWB[RV]\d+)((?:&[^&#\s\"]*)*)", re.I)
_BWB_PAD_RE = re.compile(r"wetten\.overheid\.nl/(BWB[RV]\d+)", re.I)
_PUBLICATIE_RE = re.compile(re.escape(HOST) + r"/publicaties/([^/?#\s]+)", re.I)
#: De delen van een jci die een plek aanwijzen; `z` (zichtdatum) en `g` (geldigheidsdatum) wijzen een versie aan.
_JCI_PLEK = ("boek", "hoofdstuk", "titeldeel", "afdeling", "paragraaf", "artikel", "lid", "onderdeel")


def _jci(href: str) -> tuple[str, tuple[tuple[str, str], ...]] | None:
    m = _JCI_RE.search(unquote(href))
    if not m:
        return None
    delen = tuple((k.lower(), v) for k, _, v in (d.partition("=") for d in m.group(2).split("&") if d)
                  if k.lower() in _JCI_PLEK and v)
    return m.group(1).upper(), delen


def _is_bijlage(href: str) -> bool:
    pad = href.lower().split("?", 1)[0]
    return "/wp-content/uploads/" in pad or pad.endswith((".pdf", ".xlsx", ".xls", ".docx", ".doc"))


def verwijzingen(rijen: list[Rij], eigen_id: str | None = None) -> list[Verwijzing]:
    """Alles wat het standpunt noemt, in documentvolgorde, ontdubbeld op (soort, doel): eerst wat de Belastingdienst
    zelf linkt (`link`), daarna wat alleen in de tekst staat (`tekst`). Het eigen kenmerk telt niet."""
    uit: dict[tuple[str, str], Verwijzing] = {}

    def zet(v: Verwijzing) -> None:
        if v.soort == "standpunt" and v.doel == eigen_id:
            return
        uit.setdefault((v.soort, v.doel), v)

    for r in rijen:
        for link in r.links:
            href = link.href
            if j := _jci(href):
                bwb, delen = j
                doel = f"jci1.3:c:{bwb}" + "".join(f"&{k}={v}" for k, v in delen)
                zet(Verwijzing("bepaling" if any(k == "artikel" for k, _ in delen) else "regeling", doel, "link", r.nr,
                               link.tekst, bwb, delen))
            elif m := _BWB_PAD_RE.search(href):
                zet(Verwijzing("regeling", m.group(1).upper(), "link", r.nr, link.tekst, m.group(1).upper()))
            elif m := _PUBLICATIE_RE.search(href):
                zet(Verwijzing("publicatie", m.group(1).lower(), "link", r.nr, link.tekst))
            elif _is_bijlage(href):
                zet(Verwijzing("bijlage", href, "link", r.nr, link.tekst))
            for vp in externe_verwijzingen(f"{unquote(href)} {link.tekst}"):
                zet(Verwijzing(vp.brontype, vp.id, "link", r.nr, link.tekst))
    for r in rijen:
        for vp in externe_verwijzingen(r.tekst):
            zet(Verwijzing(vp.brontype, vp.id, "tekst", r.nr))
    return list(uit.values())


_INTREKKING_RE = re.compile(r"\b(ingetrokken|intrekking|vervalt|vervallen|komt te vervallen|vervangt|vervangen)\b", re.I)
_ZIN_RE = re.compile(r"(?<=[.;!?])\s+(?=[A-Z])")


def vervangt(rijen: list[Rij], eigen_id: str | None = None) -> list[str]:
    """De standpunten die dit standpunt intrekt of vervangt: een kenmerk in een zin die dat zegt, of onder het blok
    *Let op! Intrekking*. Alleen wat de tekst zegt; dat een standpunt zelf is ingetrokken, staat in de titel."""
    uit: list[str] = []
    for r in rijen:
        zinnen = [r.tekst] if "intrekking" in r.kop.lower() else _ZIN_RE.split(r.tekst)
        for zin in zinnen:
            if "intrekking" not in r.kop.lower() and not _INTREKKING_RE.search(zin):
                continue
            for vp in externe_verwijzingen(zin):
                if vp.brontype == "standpunt" and vp.id != eigen_id and vp.id not in uit:
                    uit.append(vp.id)
    return uit


# ── Metadata ───────────────────────────────────────────────────────────────────────────────────────────────────────

def _termen(item: dict[str, Any], taxonomie: str) -> list[str]:
    return [_schoon(_html.unescape(t.get("name") or "")) for groep in (item.get("_embedded") or {}).get("wp:term") or []
            if isinstance(groep, list) for t in groep if isinstance(t, dict) and t.get("taxonomy") == taxonomie]


def _uniek(waarden: list[str]) -> list[str]:
    uit: list[str] = []
    for w in waarden:
        w = _schoon(w)
        if w and w not in uit:
            uit.append(w)
    return uit


def _datum(waarde: Any) -> str:
    w = str(waarde or "")
    if re.fullmatch(r"\d{8}", w):
        return f"{w[:4]}-{w[4:6]}-{w[6:]}"
    return w[:10] if re.match(r"\d{4}-\d{2}-\d{2}", w) else ""


@dataclass
class Standpunt:
    """Eén gelezen publicatie: het id, de tekst als rijen, alles wat ze noemt en haar metadata in de vaste sleutels
    (`connectors.METADATA_SLEUTELS`)."""
    id: str | None
    wp_id: int
    kenmerk: str
    titel: str
    status: str
    link: str
    slug: str
    gewijzigd_bron: str
    rijen: list[Rij]
    verwijzingen: list[Verwijzing]
    vervangt: list[str]
    metadata: dict[str, Any]
    bron_hash: str

    @property
    def is_standpunt(self) -> bool:
        return self.id is not None and self.metadata.get("soort") == "Standpunt"

    @property
    def label(self) -> str:
        return f"Kennisgroepstandpunt {self.kenmerk}" if self.kenmerk else self.titel


def lees_publicatie(item: dict[str, Any]) -> Standpunt:
    """Eén publicatie uit de API (met `_embed`) als `Standpunt`. Alle velden die de bron levert, komen mee: de
    taxonomieën (kennisgroep, middel, soort), de metadata (belastingsoort, rubriek, subrubriek, vaststellingsdatum), de
    datums, de link en de verwijzingen in de tekst."""
    ruwe_titel = (item.get("title") or {}).get("rendered") or ""
    ident, status, onderwerp = kenmerk_uit_titel(ruwe_titel)
    rijen = rijen_uit_html((item.get("content") or {}).get("rendered") or "")
    noemt = verwijzingen(rijen, ident)
    meta = item.get("meta") or {}
    kennisgroepen = _termen(item, "wt_publication_tag")
    middelen = _termen(item, "wt_publication_category")
    soorten = _termen(item, "message_types")
    belastingsoorten = _uniek(list(meta.get("belastingsoort") or []))
    vastgesteld = _datum(meta.get("cmd_vaststellingsdatum"))
    gepubliceerd = _datum(item.get("date"))
    kenmerk = kg_kenmerk(ident) if ident else ""
    m = re.fullmatch(r"kg:(\d{3}):(\d{4}):(\d+)", ident or "")
    metadata: dict[str, Any] = {
        "titel": onderwerp,
        "soort": soorten[0] if soorten else "",
        "status": status,
        "datum": vastgesteld or gepubliceerd,
        "gepubliceerd": gepubliceerd,
        "gewijzigd": _datum(item.get("modified")),
        "orgaan": kennisgroepen[0] if kennisgroepen else "",
        "rechtsgebied": "; ".join(_uniek(middelen + belastingsoorten)),
        "reeks": _uniek(list(meta.get("rubriek") or []) + list(meta.get("subrubriek") or [])),
        "nummer": str(int(m.group(3))) if m else "",
        "jaar": m.group(2) if m else "",
        "vervangt": vervangt(rijen, ident),
        "noemt": [{"soort": v.soort, "id": v.doel, "herkomst": v.herkomst, "rij": v.rij} for v in noemt
                  if v.soort != "bijlage"],
        "bijlagen": [v.doel for v in noemt if v.soort == "bijlage"],
        "leesbaar": bool(rijen),
    }
    if vastgesteld:
        metadata["vastgesteld"] = vastgesteld
    # De bron-specifieke velden, voor de index en de filters: los van de vaste sleutels, zodat er niets verloren gaat.
    metadata["bron"] = {
        "kennisgroepen": kennisgroepen, "middelen": middelen, "belastingsoorten": belastingsoorten,
        "rubrieken": _uniek(list(meta.get("rubriek") or [])), "subrubrieken": _uniek(list(meta.get("subrubriek") or [])),
        "soorten": soorten, "class_list": list(item.get("class_list") or []),
        "kennisgroep_ids": list(item.get("wt_publication_tag") or []),
        "middel_ids": list(item.get("wt_publication_category") or []),
        "titel_bron": _schoon(_html.unescape(ruwe_titel)),
    }
    return Standpunt(
        id=ident, wp_id=int(item.get("id") or 0), kenmerk=kenmerk, titel=onderwerp, status=status,
        link=str(item.get("link") or ""), slug=str(item.get("slug") or ""), gewijzigd_bron=str(item.get("modified_gmt")
                                                                                              or item.get("modified") or ""),
        rijen=rijen, verwijzingen=noemt, vervangt=metadata["vervangt"], metadata=metadata, bron_hash=bron_hash(rijen))


# ── Nieuwsberichten ────────────────────────────────────────────────────────────────────────────────────────────────

_GEBEURTENIS_RE = (
    ("ingetrokken", re.compile(r"\bingetrokken\b", re.I)),
    ("vervallen", re.compile(r"\bvervallen\b", re.I)),
    ("geactualiseerd", re.compile(r"\b(geactualiseerd|gewijzigd|aangepast|herzien)\b", re.I)),
    ("gepubliceerd", re.compile(r"\b(gepubliceerd|ingenomen|openbaar gemaakt)\b", re.I)),
)


@dataclass(frozen=True)
class Gebeurtenis:
    """Wat een nieuwsbericht over een publicatie meldt: `soort` (gepubliceerd, geactualiseerd, ingetrokken, vervallen
    of `bericht` als de titel het niet zegt), de datum, de link naar het bericht, de publicaties waarnaar het linkt (op
    slug) en de kenmerken die het noemt."""
    soort: str
    datum: str
    link: str
    titel: str
    publicaties: tuple[str, ...]
    kenmerken: tuple[str, ...]


def lees_bericht(item: dict[str, Any]) -> Gebeurtenis:
    titel = _schoon(_html.unescape((item.get("title") or {}).get("rendered") or ""))
    soort = next((s for s, p in _GEBEURTENIS_RE if p.search(titel)), "bericht")
    rijen = rijen_uit_html((item.get("content") or {}).get("rendered") or "")
    noemt = verwijzingen(rijen)
    return Gebeurtenis(
        soort=soort, datum=_datum(item.get("date")), link=str(item.get("link") or ""), titel=titel,
        publicaties=tuple(v.doel for v in noemt if v.soort == "publicatie"),
        kenmerken=tuple(v.doel for v in noemt if v.soort == "standpunt"))
