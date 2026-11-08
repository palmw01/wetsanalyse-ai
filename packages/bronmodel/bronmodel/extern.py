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
- EU-recht met prefix `CELEX:32016R0679` of als ELI-URI (`http://data.europa.eu/eli/reg/2016/679/oj`): `eu`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

#: De brontypen, in de volgorde waarin de werkplek ze toont. `wettekst` is de BWB (`vindplaats`).
BRONTYPEN = ("wettekst", "kamerstuk", "bekendmaking", "uitspraak", "eu")

_STOP = r"(?![0-9A-Za-z])"
_KOOP_RE = re.compile(
    r"(?<![0-9A-Za-z-])(kst|blg|h-tk|h-ek|ah-tk|ah-ek|stb|stcrt)-[0-9A-Za-z]+(?:-[0-9A-Za-z]+)*" + _STOP)
_ECLI_RE = re.compile(r"(?<![0-9A-Za-z])ECLI:[A-Z]{2}:[A-Z0-9]{1,7}:\d{4}:[A-Z0-9.]{1,25}", re.I)
_CELEX_RE = re.compile(r"(?<![0-9A-Za-z])CELEX:([0-9CE]\d{4}[A-Z]{1,2}\d{4}[0-9A-Z_]*(?:\(\d{2}\))?)", re.I)
_ELI_RE = re.compile(r"https?://data\.europa\.eu/eli/[a-z_]+/\d{4}/\d+(?:/[0-9A-Za-z_-]+)*")

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
        label = f"Kamerstukken {' '.join(delen[:-1]).upper()}, nr. {delen[-1]}"
    elif soort in {"stb", "stcrt"} and len(delen) == 2:
        label = f"{'Stb.' if soort == 'stb' else 'Stcrt.'} {delen[0]}, {delen[1]}"
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


def _ecli(ident: str) -> ExterneVindplaats:
    ident = ident.upper().rstrip(".")
    uri = f"https://deeplink.rechtspraak.nl/uitspraak?id={ident}" if ident.startswith("ECLI:NL:") else ""
    return ExterneVindplaats("uitspraak", ident, uri, ident)


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


def externe_vindplaats(ref: str) -> ExterneVindplaats | None:
    """De externe vindplaats van een verwijzing die precies één identifier is, of None."""
    ref = (ref or "").strip().rstrip(",;\\")
    for patroon, maak in ((_KOOP_RE, _koop), (_ECLI_RE, _ecli), (_ELI_RE, _eli)):
        if patroon.fullmatch(ref.rstrip(".")):
            return maak(ref.rstrip("."))
    if m := _CELEX_RE.fullmatch(ref.rstrip(".")):
        return _celex(m.group(1))
    return None


def externe_verwijzingen(tekst: str) -> list[ExterneVindplaats]:
    """Elke externe vindplaats in een tekst, ontdubbeld op `id`, in de volgorde van de tekst."""
    gevonden: list[tuple[int, ExterneVindplaats]] = []
    for patroon, maak in ((_KOOP_RE, _koop), (_ECLI_RE, _ecli), (_ELI_RE, _eli)):
        gevonden += [(m.start(), maak(m.group(0).rstrip("."))) for m in patroon.finditer(tekst or "")]
    gevonden += [(m.start(), _celex(m.group(1))) for m in _CELEX_RE.finditer(tekst or "")]
    uit: dict[str, ExterneVindplaats] = {}
    for _, vp in sorted(gevonden, key=lambda p: p[0]):
        uit.setdefault(vp.id, vp)
    return list(uit.values())
