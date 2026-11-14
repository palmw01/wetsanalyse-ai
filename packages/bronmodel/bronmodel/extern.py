"""Vindplaatsen buiten de wettekst: parlementaire stukken, bekendmakingen, uitspraken en EU-recht (ADR-013).

`vindplaats.vindplaats` blijft over de BWB gaan: tientallen aanroepers nemen aan dat een vindplaats een
BWB-id en een `urn:bwb:`-IRI heeft. Een externe bron heeft een eigen, officiële identifier en krijgt
daarom een eigen soort, `ExterneVindplaats`, met een `brontype`. Wettekst is `wettekst`; de rest is
een bron die je mag citeren, maar die niet onderbouwt wat de wet zegt.

Herkend worden alleen identifiers met een vaste, officiële vorm, en nooit een los nummer:

- de publicaties van KOOP (officielebekendmakingen.nl): `kst-36123-3`, `blg-1012345`, `h-tk-20232024-12-3`,
  `ah-tk-20232024-123` (parlementair, brontype `kamerstuk`) en `stb-2023-123`, `stcrt-2023-12345`
  (`bekendmaking`);
- ECLI (`ECLI:NL:HR:2020:1234`, ook van andere landen en van het Hof van Justitie): `uitspraak`;
- EU-recht met prefix `CELEX:32016R0679` of als ELI-URI (`http://data.europa.eu/eli/reg/2016/679/oj`): `eu`;
- een bepaling uit een toestand van het BWB die Lex live las, buiten de kennisgraaf (connector `wetgeving_live`):
  `bwbt:BWBR0015703:2026-07-01_0:artikel:31`, brontype `wettekst_live`. Na `bwbt:` staan het BWB-id, de toestand zoals
  het repository hem noemt en de staart van de graaf-IRI (`urn:bwb:BWBR0015703:artikel:31` na een import). Een jci of een
  `urn:bwb:`-IRI kan het niet zijn: die opent de werkplek uit de graaf, en de graaf draagt ook jci's met `g=`/`z=`;
- het kenmerk van een kennisgroepstandpunt van de Belastingdienst (`KG:013:2026:4`, id `kg:013:2026:4`): brontype
  `standpunt`. Een standpunt is beleid van de Belastingdienst, geen wet en geen rechtspraak
  (`docs/architectuur/plan-connector-kennisgroepen.md`). Alleen de vaste vorm met drie cijfers voor de kennisgroep en vier
  voor het jaar; een afwijkende titel bij de bron normaliseert de connector zelf.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote

#: De brontypen, in de volgorde waarin de werkplek ze toont. `wettekst` is de BWB (`vindplaats`).
BRONTYPEN = ("wettekst", "wettekst_live", "kamerstuk", "bekendmaking", "uitspraak", "standpunt", "eu")

_STOP = r"(?![0-9A-Za-z])"
_KOOP_RE = re.compile(
    r"(?<![0-9A-Za-z-])(kst|blg|h-tk|h-ek|ah-tk|ah-ek|stb|stcrt)-[0-9A-Za-z]+(?:-[0-9A-Za-z]+)*" + _STOP)
_ECLI_RE = re.compile(r"(?<![0-9A-Za-z])ECLI:[A-Z]{2}:[A-Z0-9]{1,7}:\d{4}:[A-Z0-9.]{1,25}", re.I)
_CELEX_RE = re.compile(r"(?<![0-9A-Za-z])CELEX:([0-9CE]\d{4}[A-Z]{1,2}\d{4}[0-9A-Z_]*(?:\(\d{2}\))?)", re.I)
_ELI_RE = re.compile(r"https?://data\.europa\.eu/eli/[a-z_]+/\d{4}/\d+(?:/[0-9A-Za-z_-]+)*")
#: Het kenmerk van een kennisgroepstandpunt: kennisgroep (3 cijfers), jaar, volgnummer. Niet midden in een woord of een
#: langer kenmerk, en niet gevolgd door nog een `:`-deel.
_KG_RE = re.compile(r"(?<![0-9A-Za-z:])KG:(\d{3}):((?:19|20)\d{2}):(\d{1,4})(?![0-9A-Za-z]|:\d)", re.I)
#: De publieke vindplaats van een standpunt: de site kent geen URL op het kenmerk, wel een zoekopdracht die precies het
#: standpunt vindt (getoetst 13 nov 2026). De connector geeft bij het lezen de echte link (`stuk.link`).
KG_ZOEK_URL = "https://kennisgroepen.belastingdienst.nl/?s="
#: De sleutels van de staart, zoals de importer ze in de graaf-IRI schrijft (`Vocab.by_ref_key`); een waarde is
#: percent-escaped, dus zonder dubbele punt.
_BWBT_SLEUTELS = r"(?:hoofdstuk|titeldeel|afdeling|paragraaf|artikel|lid|o|bijlage|divisie|id)"
_BWBT_RE = re.compile(r"(?<![0-9A-Za-z])bwbt:(BWB[RV]\d+)(?::(\d{4}-\d{2}-\d{2}_\d+))?"
                      r"((?::" + _BWBT_SLEUTELS + r":[0-9A-Za-z%_~-](?:[0-9A-Za-z%._~-]*[0-9A-Za-z%_~-])?)*)"
                      r"(?![0-9A-Za-z%_~:-]|\.[0-9A-Za-z])")
_BWBT_NAAM = {"o": "onderdeel"}

_PARLEMENTAIR = {"kst", "blg", "h-tk", "h-ek", "ah-tk", "ah-ek"}
_KAMER = {"tk": "II", "ek": "I"}
_EU_SOORT = {"R": "Verordening", "L": "Richtlijn", "D": "Besluit", "reg": "Verordening", "dir": "Richtlijn",
             "dec": "Besluit"}


@dataclass(frozen=True)
class ExterneVindplaats:
    """`id` is de canonieke identifier (de sleutel in de bronnenlijst), `uri` de publieke vindplaats en `label`
    leesbaar ("Kamerstukken 36123, nr. 3")."""

    brontype: str
    id: str
    uri: str
    label: str


def _koop(ident: str) -> ExterneVindplaats:
    # Het voorvoegsel is altijd kleine letters; een Romeins hoofdstuk van de begroting niet (kst-36200-VII-2).
    soort, _, rest = ident.partition("-")
    soort = soort.lower()
    if soort in {"h", "ah"}:
        kamer, _, rest = rest.partition("-")
        soort = f"{soort}-{kamer.lower()}"
    ident = f"{soort}-{rest}"
    delen = rest.split("-")
    if soort == "kst" and len(delen) >= 2:
        # Een herdruk of rectificatie heeft een achtervoegsel (kst-32740-1-n1): dat is de versie, geen nummer. Het label
        # was eerst "Kamerstukken 32740 1, nr. n1".
        versie = delen.pop() if len(delen) >= 3 and re.fullmatch(r"n\d+", delen[-1]) else ""
        label = f"Kamerstukken {' '.join(delen[:-1]).upper()}, nr. {delen[-1]}" + (f" (versie {versie})" if versie else "")
    elif soort in {"stb", "stcrt"} and len(delen) >= 2 and delen[0].isdigit():
        afk = "Stb." if soort == "stb" else "Stcrt."
        versie = delen.pop() if len(delen) >= 3 and re.fullmatch(r"n\d+", delen[-1]) else ""
        # Een Staatscourant van vóór 2009 is één uitgave met veel items: stcrt-2008-122-p18-SC86213 staat op pagina 18
        # van nummer 122. Het label noemt de pagina; het id blijft de sleutel.
        pagina = next((d[1:] for d in delen[2:] if re.fullmatch(r"p\d+", d)), "")
        label = (f"{afk} {delen[0]}, {delen[1]}" + (f", p. {pagina}" if pagina else "")
                 + (f" (versie {versie})" if versie else ""))
    elif soort.startswith(("h-", "ah-")):
        kamer = _KAMER[soort.rsplit("-", 1)[1]]
        naam = "Aanhangsel Handelingen" if soort.startswith("ah") else "Handelingen"
        jaar, *nummers = delen
        if re.fullmatch(r"\d{8}", jaar):
            jaar = f"{jaar[:4]}/{jaar[6:]}"
        label = f"{naam} {kamer} {jaar}" + (f", nr. {nummers[0]}" if nummers else "") + (
            f", item {nummers[1]}" if len(nummers) > 1 else "")
    else:
        label = ident
    brontype = "kamerstuk" if soort in _PARLEMENTAIR else "bekendmaking"
    return ExterneVindplaats(brontype, ident, f"https://zoek.officielebekendmakingen.nl/{ident}", label)


def _bwbt(m: re.Match[str]) -> ExterneVindplaats:
    """`bwbt:BWBR0015703:2026-07-01_0:artikel:31` → "BWBR0015703, artikel 31 (toestand 2026-07-01_0)". Zonder toestand
    (`bwbt:BWBR0015703:artikel:31`) is het een verzoek: de leestool kiest de toestand op de peildatum, en het `stuk` dat
    hij teruggeeft draagt hem altijd. Het label uit het id kent de citeertitel niet; dat geeft de leestool."""
    bwb, versie, staart = m.group(1), m.group(2) or "", m.group(3) or ""
    delen = staart.strip(":").split(":") if staart else []
    paren = list(zip(delen[::2], delen[1::2]))
    plek = ", ".join(f"{_BWBT_NAAM.get(k, k)} {unquote(v)}" for k, v in paren if k != "id")
    label = bwb + (f", {plek}" if plek else "") + (f" (toestand {versie})" if versie else "")
    ident = f"bwbt:{bwb}" + (f":{versie}" if versie else "") + staart
    datum = versie.split("_", 1)[0]
    uri = f"https://wetten.overheid.nl/{bwb}/{datum}" if datum else f"https://wetten.overheid.nl/{bwb}"
    return ExterneVindplaats("wettekst_live", ident, uri, label)


def bwbt_delen(ident: str) -> tuple[str, str, tuple[tuple[str, str], ...]] | None:
    """(bwb_id, toestand, (sleutel, waarde)…) uit een `bwbt:`-id, met de waarden ontsleuteld; None als het er geen is."""
    m = _BWBT_RE.fullmatch((ident or "").strip())
    if not m:
        return None
    delen = (m.group(3) or "").strip(":").split(":") if m.group(3) else []
    return m.group(1), m.group(2) or "", tuple((k, unquote(v)) for k, v in zip(delen[::2], delen[1::2]))


def _ecli(ident: str) -> ExterneVindplaats:
    ident = ident.upper().rstrip(".")
    uri = f"https://deeplink.rechtspraak.nl/uitspraak?id={ident}" if ident.startswith("ECLI:NL:") else ""
    return ExterneVindplaats("uitspraak", ident, uri, ident)


def kg_id(groep: str | int, jaar: str | int, nummer: str | int) -> str:
    """Het canonieke id van een standpunt: `kg:013:2026:4` (kennisgroep met drie cijfers, nummer zonder voorloopnullen)."""
    return f"kg:{int(groep):03d}:{int(jaar)}:{int(nummer)}"


def kg_kenmerk(ident: str) -> str:
    """Het kenmerk zoals de Belastingdienst het schrijft, bij een id: `kg:013:2026:4` → `KG:013:2026:4`."""
    return ident.upper()


def _kg(m: re.Match[str]) -> ExterneVindplaats:
    ident = kg_id(m.group(1), m.group(2), m.group(3))
    kenmerk = kg_kenmerk(ident)
    return ExterneVindplaats("standpunt", ident, KG_ZOEK_URL + kenmerk.replace(":", "%3A"), f"Kennisgroepstandpunt {kenmerk}")


def _celex(nummer: str) -> ExterneVindplaats:
    nummer = nummer.upper()
    label = f"CELEX {nummer}"
    if m := re.fullmatch(r"3(\d{4})([RLD])(\d{4})", nummer):
        label = f"{_EU_SOORT[m.group(2)]} (EU) {m.group(1)}/{int(m.group(3))}"
    ident = f"CELEX:{nummer}"
    return ExterneVindplaats("eu", ident, f"https://eur-lex.europa.eu/legal-content/NL/TXT/?uri={ident}", label)


def _eli(uri: str) -> ExterneVindplaats:
    uri = "http://" + uri.split("://", 1)[1]  # de ELI-URI is canoniek http
    soort, jaar, nummer = uri.split("/eli/", 1)[1].split("/")[:3]
    label = f"{_EU_SOORT.get(soort, soort.capitalize())} {jaar}/{nummer}"
    # De id is de canonieke ELI (http); de link gaat over https.
    return ExterneVindplaats("eu", uri, "https://" + uri.split("://", 1)[1], label)


_BWB_BRON_RE = re.compile(r"^(Stb|Stcrt)\.?\s*(\d{4})\s*[-,]\s*(?:nr\.?\s*)?(\d{1,6})$", re.I)


def koop_id_uit_bron(bron: str) -> str | None:
    """Het id van een bekendmaking uit de vorm van de BWB-brondata: "Stb.2009-610" → "stb-2009-610",
    "Stcrt.2016-69107" → "stcrt-2016-69107". De importer schrijft die vorm in `bwb:bron` en
    `bwb:inwerkingtredingsbron`; een andere vorm (een Tractatenblad, een lege waarde) geeft None."""
    m = _BWB_BRON_RE.fullmatch((bron or "").strip())
    return f"{m.group(1).lower()}-{m.group(2)}-{int(m.group(3))}" if m else None


def bwb_bron_van(ident: str) -> str | None:
    """De vorm van de BWB-brondata bij een id: "stb-2009-610" → "Stb.2009-610" (de omkering van `koop_id_uit_bron`).
    Een herdruk, een oud Stcrt-id of iets anders geeft None: die vorm schrijft de BWB niet."""
    m = re.fullmatch(r"(stb|stcrt)-(\d{4})-(\d{1,6})", (ident or "").strip())
    return f"{'Stb' if m.group(1) == 'stb' else 'Stcrt'}.{m.group(2)}-{m.group(3)}" if m else None


def externe_vindplaats(ref: str) -> ExterneVindplaats | None:
    """De externe vindplaats van een verwijzing die precies één identifier is, of None."""
    ref = (ref or "").strip().rstrip(",;\\")
    for patroon, maak in ((_KOOP_RE, _koop), (_ECLI_RE, _ecli), (_ELI_RE, _eli)):
        if patroon.fullmatch(ref.rstrip(".")):
            return maak(ref.rstrip("."))
    if m := _BWBT_RE.fullmatch(ref.rstrip(".")):
        return _bwbt(m)
    if m := _CELEX_RE.fullmatch(ref.rstrip(".")):
        return _celex(m.group(1))
    if m := _KG_RE.fullmatch(ref.rstrip(".")):
        return _kg(m)
    return None


def externe_verwijzingen_met_plek(tekst: str) -> list[tuple[int, ExterneVindplaats]]:
    """(plek, vindplaats) van elke externe vindplaats in een tekst, ontdubbeld op `id` (de eerste plek telt), in de
    volgorde van de tekst. De plek komt uit het patroon, niet uit een zoekopdracht naar het id: een ECLI in kleine
    letters staat in de tekst anders dan zijn canonieke vorm."""
    gevonden: list[tuple[int, ExterneVindplaats]] = []
    for patroon, maak in ((_KOOP_RE, _koop), (_ECLI_RE, _ecli), (_ELI_RE, _eli)):
        gevonden += [(m.start(), maak(m.group(0).rstrip("."))) for m in patroon.finditer(tekst or "")]
    gevonden += [(m.start(), _celex(m.group(1))) for m in _CELEX_RE.finditer(tekst or "")]
    gevonden += [(m.start(), _bwbt(m)) for m in _BWBT_RE.finditer(tekst or "")]
    gevonden += [(m.start(), _kg(m)) for m in _KG_RE.finditer(tekst or "")]
    uit: dict[str, tuple[int, ExterneVindplaats]] = {}
    for plek, vp in sorted(gevonden, key=lambda p: p[0]):
        uit.setdefault(vp.id, (plek, vp))
    return list(uit.values())


def externe_verwijzingen(tekst: str) -> list[ExterneVindplaats]:
    """Elke externe vindplaats in een tekst, ontdubbeld op `id`, in de volgorde van de tekst."""
    return [vp for _, vp in externe_verwijzingen_met_plek(tekst)]
