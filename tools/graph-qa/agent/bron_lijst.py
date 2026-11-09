"""Lijstvragen over een bron naast de wet (ADR-013, ADR-010 laag 2): "geef de 10 meest recente Kamerstukken", "wat is
het laatste stuk van dossier 32140", "de laatste vijf moties van de Eerste Kamer".

Op acceptatie (gesprek e906567a, 9 nov 2026) bladerde het model voor "wat is het laatste stuk" door een dossier van 405
stukken: elf rondes, 264k cache-tokens en twee foute antwoorden, want op nummer staan de letters na de cijfers. Wat er
gevraagd wordt, is een zoekvraag met een volgorde, en die leest de code uit de vraag: de volgorde, het aantal, het
dossier, het soort, een periode, de Kamer en een onderwerp. Lukt dat niet volledig (een woord dat de code niet plaatst
in de vraag naar de inhoud van een stuk), dan geen route: de agent heeft dezelfde tool met dezelfde argumenten.

De argumentnamen komen uit de beschrijving (`ConnectorBeschrijving.filters`, `soorten`, `organen`); er staat hier geen
connector met naam.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from bronmodel.connectors import CONNECTORS, ConnectorBeschrijving

_TELWOORDEN = {"een": 1, "één": 1, "twee": 2, "drie": 3, "vier": 4, "vijf": 5, "zes": 6, "zeven": 7, "acht": 8,
               "negen": 9, "tien": 10, "twaalf": 12, "vijftien": 15, "twintig": 20, "vijfentwintig": 25}
_GETAL = r"\d{1,2}|" + "|".join(sorted(_TELWOORDEN, key=len, reverse=True))
_NIEUWSTE = r"meest\s+recente?|recentste|nieuwste|laatste|jongste"
_OUDSTE = r"oudste|eerste"
_VOLGORDE_RE = re.compile(rf"\b(?:(?P<nieuw>{_NIEUWSTE})|(?P<oud>{_OUDSTE}))\b", re.IGNORECASE)
_AANTAL_RE = re.compile(rf"\b(?:(?P<voor>{_GETAL})\s+(?:{_NIEUWSTE}|{_OUDSTE})|(?:{_NIEUWSTE}|{_OUDSTE})\s+(?P<na>{_GETAL}))\b",
                        re.IGNORECASE)
#: Eén stuk: "het laatste stuk", "wat is de nieuwste motie", "de meest recente brief".
_EEN_RE = re.compile(rf"\b(?:het|de)\s+(?:{_NIEUWSTE}|{_OUDSTE})\s+(?!\d)(?!(?:{_GETAL})\b)\w+", re.IGNORECASE)
#: Een vraag naar wat er in een stuk staat, is geen lijstvraag.
_INHOUD_RE = re.compile(r"\b(?:staat\s+er|zegt|zeggen|samenvat\w*|inhoud|uitleg|leg\s+uit|waarom|bedoel\w*|"
                        r"lees|citeer|wat\s+vind)\b", re.IGNORECASE)
_DOSSIER_RE = re.compile(r"\b(?:dossier(?:nummer)?|kamerstukdossier)\s+(?P<d>\d{4,6}(?:[- ](?:[IVXLC]{1,6}|[A-Z]))?)\b",
                         re.IGNORECASE)
_JAAR_RE = re.compile(r"\b(?:(?P<sinds>sinds|vanaf|na)\s+(?P<j1>(?:19|20)\d{2})|(?P<in>in|uit)\s+(?P<j2>(?:19|20)\d{2})"
                      r"|(?P<tot>tot|voor)\s+(?P<j3>(?:19|20)\d{2}))\b", re.IGNORECASE)
_VERGADERJAAR_RE = re.compile(r"\bvergaderjaar\s+(?P<a>\d{4})\s*[-/]\s*(?P<b>\d{2,4})\b", re.IGNORECASE)
_OVER_RE = re.compile(r"\bover\s+(?:de\s+|het\s+)?(?P<o>[^?.!,;]+)", re.IGNORECASE)
#: Woorden die in een lijstvraag staan zonder iets te zoeken.
_VULWOORDEN = frozenset("""geef mij me toon noem laat zien lijst wat welke wie is zijn de het een van uit bij in op
    met en of er nu ook alle stuk stukken kamerstuk kamerstukken parlementaire publicaties dossier dossiernummer
    kamerstukdossier staan zit zitten gaan gaat graag alsjeblieft aub kun kan je u""".split())
MAX_ONDERWERP = 4


@dataclass(frozen=True)
class Lijstvraag:
    """De zoekvraag die de code uit een lijstvraag las: de connector en de argumenten van zijn zoektool."""
    connector: str
    tool: str
    args: dict[str, Any] = field(default_factory=dict)


def _getal(woord: str) -> int:
    return int(woord) if woord.isdigit() else _TELWOORDEN[woord.lower()]


def _arg(c: ConnectorBeschrijving, sleutel: str, index: int = 0) -> str:
    """Het argument van de zoektool dat op dit metadataveld filtert (`MetadataVeld.filters`), of ''."""
    veld = c.veld(sleutel)
    return veld.filters[index] if veld is not None and len(veld.filters) > index else ""


def lees(vraag: str, aan: frozenset[str]) -> Lijstvraag | None:
    """De lijstvraag in de vraag, voor een connector die aanstaat en de vraag herkent; None als het geen lijstvraag is
    of de code haar niet helemaal kan lezen."""
    tekst = " ".join((vraag or "").split())
    if _INHOUD_RE.search(tekst):
        return None
    c = next((c for c in CONNECTORS.values() if c.naam in aan and c.volgordes and _herkent(c, tekst)), None)
    if c is None or c.geciteerd(tekst) or not (zoektool := sorted(c.tools - {c.leestool})):
        return None
    # Een orgaan is geen volgorde: "Eerste Kamer" las als "eerste", dus oudste eerst (acceptatie 9 nov 2026).
    zonder_organen = _zonder_organen(c, tekst)
    args: dict[str, Any] = {}
    rest = tekst
    if (m := _VOLGORDE_RE.search(zonder_organen)) is not None:
        volgorde = "nieuwste" if m.group("nieuw") else "oudste"
        if volgorde not in c.volgordes:
            return None
        args["volgorde"] = volgorde
        if (a := _AANTAL_RE.search(zonder_organen)) is not None:
            args["aantal"] = min(max(_getal(a.group("voor") or a.group("na")), 1), 25)
            rest = rest.replace(a.group(0), " ")
        elif _EEN_RE.search(zonder_organen) and not re.search(r"\bstukken\b|\bkamerstukken\b", tekst, re.IGNORECASE):
            args["aantal"] = 1
        args.setdefault("aantal", 10)
    # Zonder volgorde ("Kamerstukken uit vergaderjaar 2025-2026 over invorderingsrente") kiest de zoektool de volgorde en
    # de pagina: relevantie bij woorden of tekst, een dossier op nummer, anders de nieuwste. Dan moet er wel een filter
    # zijn.
    if (d := _DOSSIER_RE.search(tekst)) and (arg := _arg(c, "reeks")):
        args[arg] = re.sub(r"\s+", "-", d.group("d")).upper()
        rest = rest.replace(d.group(0), " ")
    for label, patroon in c.soorten:
        if (s := re.search(patroon, rest, re.IGNORECASE)) and (arg := _arg(c, "soort")):
            args[arg] = label
            rest = rest.replace(s.group(0), " ")
            break
    for orgaan in c.organen:
        if re.search(rf"\b{re.escape(orgaan)}\b", rest, re.IGNORECASE) and (arg := _arg(c, "orgaan")):
            args[arg] = orgaan
            rest = re.sub(rf"\b{re.escape(orgaan)}\b", " ", rest, flags=re.IGNORECASE)
    if (v := _VERGADERJAAR_RE.search(rest)) and (arg := _arg(c, "jaar")):
        args[arg] = f"{v.group('a')}-{v.group('b')}"
        rest = rest.replace(v.group(0), " ")
    for j in _JAAR_RE.finditer(rest):
        vanaf, tot = _arg(c, "datum", 0), _arg(c, "datum", 1)
        if j.group("sinds") and vanaf:
            args[vanaf] = j.group("j1")
        elif j.group("in") and vanaf and tot:
            args[vanaf] = args[tot] = j.group("j2")
        elif j.group("tot") and tot:
            args[tot] = str(int(j.group("j3")) - 1)
        rest = rest.replace(j.group(0), " ")
    if (o := _OVER_RE.search(rest)) is not None:
        woorden = [w for w in re.findall(r"[0-9A-Za-zÀ-ÿ'-]+", o.group("o")) if w.lower() not in _VULWOORDEN]
        if not woorden or len(woorden) > MAX_ONDERWERP or "tekst" not in _zoekargumenten(c):
            return None
        args["tekst"] = f'"{" ".join(woorden)}"' if len(woorden) > 1 else woorden[0]
        rest = rest.replace(o.group(0), " ")
    rest = _VOLGORDE_RE.sub(" ", rest)
    if not args:
        return None
    # Wat er overblijft, moet leeg zijn: een woord dat de code niet plaatst, is een vraag die het model beter leest.
    over = [w for w in re.findall(r"[0-9A-Za-zÀ-ÿ]+", rest) if w.lower() not in _VULWOORDEN and not w.isdigit()]
    if over:
        return None
    return Lijstvraag(c.naam, zoektool[0], args)


def _zonder_organen(c: ConnectorBeschrijving, tekst: str) -> str:
    for orgaan in c.organen:
        tekst = re.sub(rf"\b{re.escape(orgaan)}\b", " ", tekst, flags=re.IGNORECASE)
    return tekst


def _herkent(c: ConnectorBeschrijving, tekst: str) -> bool:
    """De connector, een soort stuk van de connector ("de laatste vijf moties") of een dossiernummer ("het laatste stuk
    van dossier 32140"): in een lijstvraag wijst elk daarvan de bron aan."""
    return (c.herkent(tekst) or any(re.search(p, tekst, re.IGNORECASE) for _, p in c.soorten)
            or (bool(_DOSSIER_RE.search(tekst)) and bool(_arg(c, "reeks"))))


def _zoekargumenten(c: ConnectorBeschrijving) -> set[str]:
    from .tools import TOOLS

    return {a for t in TOOLS if t["name"] in c.tools - {c.leestool} for a in t["input_schema"]["properties"]}
