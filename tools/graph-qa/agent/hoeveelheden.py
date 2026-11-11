"""Termijnen, bedragen, percentages en datums in vrije tekst, om ze tegen de opgehaalde tekst te toetsen (R4a).

De controle toetste vindplaatsen en citaten, niet wat de uitleg beweert. Op acceptatie schreef Lex "inwerkingtredingsdatum:
1 oktober 2026" zonder bron, en in een toelichting een termijn die nergens stond. Een getal met een eenheid en een datum
zijn het deel van zo'n bewering dat de code zonder model kan nalopen: staat "zes weken" of "1 oktober 2026" ook in wat er
is opgehaald? Een kaal getal ("22 leden", "artikel 9") niet: dat is een telling of een vindplaats, met een eigen toets.

Geschreven en cijfermatige getallen zijn gelijk ("zes weken" = "6 weken"), en een eenheid telt in enkelvoud en meervoud.
"""
from __future__ import annotations

import json
import re

_TELWOORDEN = {
    "een": 1, "één": 1, "twee": 2, "drie": 3, "vier": 4, "vijf": 5, "zes": 6, "zeven": 7, "acht": 8, "negen": 9,
    "tien": 10, "elf": 11, "twaalf": 12, "dertien": 13, "veertien": 14, "vijftien": 15, "zestien": 16, "zeventien": 17,
    "achttien": 18, "negentien": 19, "twintig": 20, "dertig": 30, "veertig": 40, "vijftig": 50, "zestig": 60,
    "zeventig": 70, "tachtig": 80, "negentig": 90, "honderd": 100, "duizend": 1000,
}
_EENHEDEN = {
    "dag": "dag", "dagen": "dag", "werkdag": "werkdag", "werkdagen": "werkdag", "week": "week", "weken": "week",
    "maand": "maand", "maanden": "maand", "jaar": "jaar", "jaren": "jaar", "uur": "uur", "uren": "uur",
    "procent": "procent", "%": "procent", "euro": "euro",
}
_MAANDEN = ("januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
            "november", "december")

_GETAL = r"\d+(?:[.,]\d+)?|" + "|".join(sorted(_TELWOORDEN, key=len, reverse=True))
_EENHEID = "|".join(sorted((re.escape(e) for e in _EENHEDEN), key=len, reverse=True))
_HOEVEELHEID = re.compile(rf"(?<![\w€])(?:€\s*(?P<bedrag>\d+(?:[.,]\d+)*)|(?P<getal>{_GETAL})\s*(?P<eenheid>{_EENHEID}))(?![\w])",
                          re.IGNORECASE)
_DATUM = re.compile(rf"(?<!\d)(\d{{1,2}})\s+({'|'.join(_MAANDEN)})\s+(\d{{4}})(?!\d)", re.IGNORECASE)
#: Een datum zoals een bron hem levert ("2024-10-31", de metadata van een Kamerstuk): dezelfde datum als "31 oktober 2024".
#: Zonder dit telde een datum uit een zoekresultaat als onbevestigd (gesprek e906567a, 9 nov 2026).
_ISO_DATUM = re.compile(r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?![\d-])")


def _getal(woord: str) -> str:
    woord = woord.casefold()
    if woord in _TELWOORDEN:
        return str(_TELWOORDEN[woord])
    return woord.replace(".", "").replace(",", ".")


def hoeveelheden(tekst: str) -> set[str]:
    """De termijnen, bedragen, percentages en datums in de tekst, genormaliseerd ("6 week", "100 euro", "1 oktober 2026")."""
    uit: set[str] = set()
    for m in _HOEVEELHEID.finditer(tekst or ""):
        if m.group("bedrag"):
            uit.add(f"{_getal(m.group('bedrag'))} euro")
        else:
            uit.add(f"{_getal(m.group('getal'))} {_EENHEDEN[m.group('eenheid').casefold()]}")
    for dag, maand, jaar in _DATUM.findall(tekst or ""):
        uit.add(f"{int(dag)} {maand.casefold()} {jaar}")
    for jaar, maand, dag in _ISO_DATUM.findall(tekst or ""):
        if 1 <= int(maand) <= 12 and 1 <= int(dag) <= 31:
            uit.add(f"{int(dag)} {_MAANDEN[int(maand) - 1]} {jaar}")
    return uit


def buiten(tekst: str, bron: str) -> list[str]:
    """Wat de tekst aan termijnen, bedragen en datums noemt dat de bron niet noemt, in vaste volgorde."""
    return sorted(hoeveelheden(tekst) - hoeveelheden(bron))


_KAAL = re.compile(r"[-−–]?\s*(\d+(?:[.,]\d+)*)")


def _eenheid(tekst: str) -> str:
    """De eenheid die een titel of kolomkop noemt ("Opbrengst (€ mln)", "in procenten"); leeg bij geen of twee."""
    t = (tekst or "").casefold()
    gevonden = {e for e, ja in (("euro", "€" in t or re.search(r"\beuro\b", t)),
                                ("procent", "%" in t or re.search(r"\bprocent(en)?\b", t))) if ja}
    return next(iter(gevonden)) if len(gevonden) == 1 else ""


def uit_tabellen(trace: list[tuple[str, str]]) -> str:
    """De kale getallen uit tabellen in het opgehaalde, met de eenheid uit hun kolomkop of de titel van de tabel
    ("€ 106" voor de cel "106" onder "Tabel 1 Opbrengst (€ mln)"), als tekst om mee te toetsen.

    Een tabelcel draagt haar eenheid zelden zelf, en dan las de controle "€ 106 miljoen" in de uitleg als niet opgehaald
    (ronde 1 Kamerstukken, 11 nov 2026, K28: vijf keer vals alarm). Een tabel is de rij met `soort: "tabel"` (de titel als
    tekst, de kolommen als `cellen`, `tools/op_xml.py`); een `tabelrij` hoort bij de tabel met het hoogste `nr` dat er niet
    na komt, in hetzelfde stuk, ook op een volgende pagina."""

    tabellen: dict[str, list[tuple[int, str, list[str]]]] = {}
    uit: list[str] = []
    for _, raw in trace:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict) or not isinstance(data.get("resultaten"), list):
            continue
        stuk = str((data.get("stuk") or {}).get("id") or "") if isinstance(data.get("stuk"), dict) else ""
        for r in data["resultaten"]:
            if not isinstance(r, dict) or not isinstance(r.get("nr"), int):
                continue
            if r.get("soort") == "tabel":
                kolommen = [_eenheid(str(c)) for c in r.get("cellen") or []]
                tabellen.setdefault(stuk, []).append((r["nr"], _eenheid(str(r.get("tekst") or "")), kolommen))
            elif r.get("soort") == "tabelrij" and isinstance(r.get("cellen"), list):
                bij = max((t for t in tabellen.get(stuk, []) if t[0] <= r["nr"]), default=None, key=lambda t: t[0])
                if bij is None:
                    continue
                for i, cel in enumerate(r["cellen"]):
                    eenheid = (bij[2][i] if i < len(bij[2]) else "") or bij[1]
                    if eenheid and (m := _KAAL.fullmatch(str(cel).strip())):
                        uit.append(f"€ {m.group(1)}" if eenheid == "euro" else f"{m.group(1)} procent")
    return "\n".join(uit)
