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
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from bronmodel.connectors import CONNECTORS, ConnectorBeschrijving

from .aanwijzing import _ARTIKEL, lees_aanwijzing

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
_JAAR = r"(?:19|20)\d{2}"
#: Een periode: "uit 2023 en 2024", "2023-2024", "tussen 2020 en 2022", "van 2020 tot en met 2022". Vóór de losse jaren,
#: anders werd "uit 2023 en 2024" alleen 2023 (analyse meting bekendmakingen, 10 nov 2026).
_PERIODE_RE = re.compile(rf"\b(?:(?:tussen|in|uit|van)\s+)?(?P<a>{_JAAR})\s*(?:-|–|/|\ben\b|\bt/m\b|\btot\s+en\s+met\b)\s*"
                         rf"(?P<b>{_JAAR})\b", re.IGNORECASE)
#: Eén jaar met een voorzetsel. "van 2018" is "in 2018": "de verbeterbladen in het Staatsblad van 2018" verloor het jaar
#: (meting bekendmakingen B11, 10 nov 2026).
_JAAR_RE = re.compile(rf"\b(?:(?P<sinds>sinds|vanaf|na)\s+(?P<j1>{_JAAR})|(?P<in>in|uit|van)\s+(?P<j2>{_JAAR})"
                      rf"|(?P<tot>tot|voor)\s+(?P<j3>{_JAAR}))\b", re.IGNORECASE)
_VERGADERJAAR_RE = re.compile(r"\bvergaderjaar\s+(?P<a>\d{4})\s*[-/]\s*(?P<b>\d{2,4})\b", re.IGNORECASE)
_OVER_RE = re.compile(r"\bover\s+(?:de\s+|het\s+)?(?P<o>[^?.!,;]+)", re.IGNORECASE)
#: Woorden die in een lijstvraag staan zonder iets te zoeken.
_VULWOORDEN = frozenset("""geef mij me toon noem laat zien lijst wat welke wie is zijn de het een van uit bij in op
    met en of er nu ook alle stuk stukken publicaties staan zit zitten gaan gaat graag alsjeblieft aub kun kan je u
    noemen noemt genoemd over horen hoort hoeveel""".split()) | frozenset(
    w for c in CONNECTORS.values() for w in (*c.verzamelnamen, *c.vulwoorden))
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


def lees(vraag: str, aan: frozenset[str],
         regelingen: Callable[[str], list[tuple[str, set[str]]]] | None = None) -> Lijstvraag | None:
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
        elif (een := _EEN_RE.search(zonder_organen)) and not _meervoud(c, een.group(0).split()[-1]):
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
            # De soort die het brontype zelf is ("uitspraken" bij Rechtspraak) is de algemene naam van een stuk, geen
            # filter: anders sloot "de nieuwste uitspraken van de Hoge Raad" de conclusies stil uit (meting 10 nov 2026).
            if label != c.brontype:
                args[arg] = label
            rest = rest.replace(s.group(0), " ")
            break
    if (wv := _wetsverwijzing(c, rest, regelingen)) is not None:
        if not wv:
            return None
        args.update(wv[0])
        rest = wv[1]
    for orgaan in c.organen:
        # Het eerste dat past: een gerecht bij naam ("Rechtbank Gelderland") staat vóór de soort gerecht erin.
        if re.search(rf"\b{re.escape(orgaan)}\b", rest, re.IGNORECASE) and (arg := _arg(c, "orgaan")):
            args[arg] = orgaan
            rest = re.sub(rf"\b{re.escape(orgaan)}\b", " ", rest, flags=re.IGNORECASE)
            break
    for veld in c.metadata:
        # Een veld met vaste waarden ("in het belastingrecht"): het filter krijgt de waarde.
        for waarde, patroon in veld.waarden:
            if veld.filters and (w := re.search(patroon, rest, re.IGNORECASE)):
                args[veld.filters[0]] = waarde
                rest = rest.replace(w.group(0), " ")
                break
    if (v := _VERGADERJAAR_RE.search(rest)) and (arg := _arg(c, "jaar")):
        args[arg] = f"{v.group('a')}-{v.group('b')}"
        rest = rest.replace(v.group(0), " ")
    if (p := _PERIODE_RE.search(rest)) and int(p.group("a")) <= int(p.group("b")):
        vanaf, tot = _arg(c, "datum", 0), _arg(c, "datum", 1)
        if not (vanaf and tot):
            return None
        args[vanaf], args[tot] = p.group("a"), p.group("b")
        rest = rest.replace(p.group(0), " ")
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
        if woorden and (len(woorden) > MAX_ONDERWERP or "tekst" not in _zoekargumenten(c)):
            return None
        if woorden:
            args["tekst"] = f'"{" ".join(woorden)}"' if len(woorden) > 1 else woorden[0]
        # Zonder woorden ging het "over" iets dat de code al plaatste ("gaan over artikel 36 Iw").
        rest = rest.replace(o.group(0), " ")
    rest = _VOLGORDE_RE.sub(" ", rest)
    # Een woord dat de bron aanwijst ("jurisprudentie", "rechtspraak") zoekt niets.
    rest = " ".join(w for w in rest.split() if not _bronwoord(c, w))
    if not args:
        return None
    # Wat er overblijft, moet leeg zijn: een woord dat de code niet plaatst, is een vraag die het model beter leest.
    # Ook een getal: een jaartal of nummer dat de code niet plaatste, is een filter dat anders stil wegvalt ("uit 2023 en
    # 2024" werd alleen 2023, meting bekendmakingen 10 nov 2026). Aantal, dossier en vergaderjaar zijn al uit `rest`.
    over = [w for w in re.findall(r"[0-9A-Za-zÀ-ÿ]+", rest) if w.lower() not in _VULWOORDEN]
    if over:
        return None
    return Lijstvraag(c.naam, zoektool[0], args)


def _wetsverwijzing(c: ConnectorBeschrijving, tekst: str,
                    regelingen: Callable[[str], list[tuple[str, set[str]]]] | None):
    """Een genoemde bepaling als filter, voor een connector met het metadataveld `wetsverwijzing` (Rechtspraak: de
    uitspraken die een artikel noemen): (argumenten, de rest van de tekst). None als de tekst geen artikel noemt; een lege
    tuple als hij er een noemt dat de code niet eenduidig kan plaatsen (meer artikelen, geen of meer regelingen, of geen
    graaf): dan leest de agent de vraag."""
    veld = c.veld("wetsverwijzing")
    aw = lees_aanwijzing(tekst)
    if veld is None or len(veld.filters) < 2 or not aw.artikelen:
        return None
    if len(aw.artikelen) != 1 or aw.leden or regelingen is None:
        return ()
    genoemd = regelingen(tekst)
    if len(genoemd) != 1:
        return ()
    bwb_id, namen = genoemd[0]
    rest = _ARTIKEL.sub(" ", tekst)
    for naam in sorted(namen, key=len, reverse=True):
        rest = re.sub(rf"(?<![\w.]){re.escape(naam)}(?![\w])", " ", rest, flags=re.IGNORECASE)
    return {veld.filters[0]: bwb_id, veld.filters[1]: aw.artikelen[0]}, rest


def _bronwoord(c: ConnectorBeschrijving, woord: str) -> bool:
    """Een los woord dat de bron zelf aanwijst ("jurisprudentie", "rechtspraak", "kamerstukken"): een verzamelnaam."""
    w = re.sub(r"[^\w-]", "", woord)
    return bool(w) and any(re.search(p, w, re.IGNORECASE) for p in c.signalen)


def _meervoud(c: ConnectorBeschrijving, woord: str) -> bool:
    """Is het woord na "de laatste" een meervoud ("de laatste moties", "de nieuwste uitspraken")? Dan geen aantal 1. Een
    woord op -en of -s dat een soort van de connector is, maar niet de soort zelf; en "stukken"."""
    w = woord.lower()
    if w == "stukken" or w in c.verzamelnamen:  # meervoud of verzamelnaam
        return True
    return w.endswith(("en", "s")) and any(re.search(p, w, re.IGNORECASE) for _, p in c.soorten) and all(
        w != label.lower() for label, _ in c.soorten)


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
