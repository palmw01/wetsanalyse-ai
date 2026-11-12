"""Feiten in de toelichting die niet terug te vinden zijn in wat er is opgehaald.

De controle toetste vindplaatsen en citaten, niet wat de uitleg eromheen beweert. In de iteratierondes van november 2026
stond in de toelichting een dossiernummer dat de bron niet kende ("dossier 20588", Kamerstukken K16), een intrekking bij
het verkeerde dossier (K17) en een instantie die nergens in de trace stond. Een bewering zonder bron is precies wat een
jurist niet ziet: het antwoord leest even zeker.

Eén mechanisme voor elke bron en elk sjabloon, en ook voor vrije tekst: de feiten komen uit de tekst, en de toets is of
ze in de opgehaalde tekst (deze beurt plus het register) of in de vraag zelf staan. Geen lijst per connector. Wat telt
als feit, zonder model na te lopen:

- een datum, termijn, bedrag of percentage (`hoeveelheden`);
- een getal van drie cijfers of meer: een dossier-, publicatie- of zaaknummer, een jaar, een groot aantal;
- een getal met een zelfstandig naamwoord erachter: een telling ("36 uitspraken", "184 van de 196 arresten");
- een instantie bij naam, uit de `organen` van de connectorbeschrijvingen ("Hoge Raad", "Eerste Kamer").

Niet hier: citaten (`niet_letterlijk`), vindplaatsen en ids van stukken (`unsupported`) en artikelnummers (`onbevestigd`
in `grounding`); die hebben een eigen toets, en hun getallen tellen hier niet mee.

Bekende grenzen: een klein getal (onder de 100) staat vaak ergens in de trace, dus een verkeerde kleine telling ontgaat de
toets; een telwoord ("drie uitspraken") toetst ze niet, want dat telt het model vaak zelf uit de lijst die het toont.
"""
from __future__ import annotations

import re
from functools import lru_cache

from .hoeveelheden import _DATUM, _HOEVEELHEID, _ISO_DATUM, buiten as hoeveelheden_buiten

#: Wat er vóór de getallen uit de tekst gaat: links, ids en vindplaatsen hebben een eigen toets.
_WEG = (
    re.compile(r"\]\([^)\s]*\)"),                                      # het doel van een markdown-link
    re.compile(r"https?://\S+"),
    re.compile(r"\bECLI:[A-Z]{2}:[A-Z0-9]+:\d{4}:[\w.]+", re.IGNORECASE),
    re.compile(r"\b(?:kst|stb|stcrt|trb|gmb|prb|wsb|bgr|h-tk|h-ek|ah-tk|ah-ek|blg)-[\w-]+", re.IGNORECASE),
    re.compile(r"\bBWB[RV]\d+\S*"),
    re.compile(r"\bjci[\d.]+:\S+"),
    re.compile(r"\bCELEX:\S+", re.IGNORECASE),
    re.compile(r"\burn:\S+"),
    # Een vindplaats in de wet: "artikel 36", "art. 4:94a", "lid 3", "artikelen 8, 9 en 10", "r.o. 3.4".
    re.compile(r"\b(?:artikel(?:en)?|art\.|leden|lid|onderdel(?:en)?|onderdeel|hoofdstuk(?:ken)?|afdeling(?:en)?|"
               r"paragraaf|titel|boek|bijlage|r\.o\.|rechtsoverweging|alinea|nr\.|nummer)\s+"
               r"[\w:.°]+(?:\s*(?:,|en|of|t/m|tot\s+en\s+met|-|–)\s*[\w:.°]+)*", re.IGNORECASE),
)
#: Het jaar in de naam van een regeling ("Invorderingswet 1990", "Leidraad Invordering 2008", "Wet IB 2001"): een naam,
#: geen bewering (ronde 2, R28b: de uitspraak noemde de wet anders).
_IN_NAAM = re.compile(r"\b(?:\w*(?:wet|besluit|regeling|leidraad|verdrag|code|richtlijn|verordening|reglement)|"
                      r"[A-Z]{2,5}|Invordering)\s+(?:\d{4})\b")
#: Een getal, ook met punten voor de duizendtallen ("6.772").
_GETAL = re.compile(r"(?<![\w.,/:-])(\d{1,3}(?:\.\d{3})+|\d+)(?![\w,]|[.:/-]\d)")
#: Een getal met een woord erachter, eventueel "van de N" ertussen: een telling.
_TELLING = re.compile(r"(?<![\w.,/:-])(\d{1,3}(?:\.\d{3})+|\d+)\s+(?:van\s+de\s+\d+\s+)?([a-zà-ÿ][a-zà-ÿ-]{2,})\b")
#: Woorden achter een getal die geen telling maken.
_GEEN_TELLING = frozenset({
    "en", "tot", "of", "t/m", "van", "tot", "per", "keer", "maal", "procent", "jaar", "jaren", "dag", "dagen", "weken",
    "week", "maand", "maanden", "uur", "uren", "euro", "januari", "februari", "maart", "april", "mei", "juni", "juli",
    "augustus", "september", "oktober", "november", "december", "minuten", "seconden", "werkdagen", "werkdag",
    # lidwoorden, voornaamwoorden en werkwoorden: "153 een eerdere redactie", "470 de huidige tekst"
    "een", "het", "die", "dat", "dit", "deze", "als", "bij", "aan", "met", "voor", "uit", "naar", "over", "zijn", "is",
    "was", "waren", "worden", "wordt", "werden", "hebben", "heeft", "noemen", "noemt", "gaan", "gaat", "staan", "staat",
    "komen", "komt", "daarvan", "ervan", "stuks",
})
#: Een blokcitaat: wettekst of een passage uit het blok `extern`, met een eigen toets.
_BLOKCITAAT = re.compile(r"^[ \t]*>.*$", re.MULTILINE)
#: Een citaat tussen aanhalingstekens: idem.
_CITAAT = re.compile(r"[\"“„][^\"“”„\n]{2,}[\"”“]")


def _zonder_citaten(tekst: str) -> str:
    tekst = _BLOKCITAAT.sub(" ", tekst or "")
    tekst = _CITAAT.sub(" ", tekst)
    for patroon in _WEG:
        tekst = patroon.sub(" ", tekst)
    return tekst


def _zonder_hoeveelheden(tekst: str) -> str:
    """De datums, termijnen en bedragen toetst `hoeveelheden`; hun getallen niet nog eens. Ook het jaar in een naam."""
    for patroon in (_DATUM, _ISO_DATUM, _HOEVEELHEID, _IN_NAAM):
        tekst = patroon.sub(" ", tekst)
    return tekst


def _vorm(getal: str) -> str:
    return getal.replace(".", "").lstrip("0") or "0"


def _getallen(bron: str) -> set[str]:
    """Elk getal in de bron, als losse cijferreeks én in de vorm met duizendtallen ("6.772" → "6772")."""
    uit = {_vorm(g) for g in re.findall(r"\d+", bron or "")}
    uit |= {_vorm(g) for g in re.findall(r"\d{1,3}(?:\.\d{3})+", bron or "")}
    return uit


@lru_cache(maxsize=1)
def _organen() -> tuple[str, ...]:
    """De instanties bij naam uit de beschrijvingen van de connectors, langste eerst: een eigennaam (met een hoofdletter),
    geen soort ("rechtbank") of meervoud ("gerechtshoven")."""
    from bronmodel.connectors import CONNECTORS, INSTANTIE_MEERVOUD, INSTANTIES

    namen = {o for c in CONNECTORS.values() for o in c.organen} | set(INSTANTIES)
    # Geen afkorting ("CRvB", "CBb"): de bron noemt het gerecht voluit, en dan was de afkorting vals alarm (ronde 2, R22).
    eigen = {n for n in namen if n[:1].isupper() and n not in INSTANTIE_MEERVOUD and len(n) > 4}
    return tuple(sorted(eigen, key=len, reverse=True))


def _instanties(tekst: str) -> list[str]:
    uit: list[str] = []
    rest = tekst
    for naam in _organen():
        patroon = re.compile(rf"(?<!\w){re.escape(naam)}(?!\w)")
        if patroon.search(rest):
            uit.append(naam)
            rest = patroon.sub(" ", rest)  # "Hoge Raad" in "Parket bij de Hoge Raad" telt niet apart
    return uit


def _is_jaar(getal: str) -> bool:
    """Een jaartal is geen telling ("In 1989 verscheen …"); het blijft een getal dat getoetst wordt."""
    return len(getal) == 4 and 1800 <= int(getal) <= 2100


def beweringen(tekst: str, bron: str, *, bekend: str = "") -> list[str]:
    """De feiten in `tekst` die niet in `bron` (de opgehaalde tekst) of `bekend` (de vraag) staan, in vaste volgorde.

    `bron` hoort ook de ruwe resultaten te dragen: een telling staat als getal in de JSON (`totaal`, `per_instantie`), en
    `resultaat.waarden` neemt alleen de tekstwaarden."""
    tegen = f"{bron}\n{bekend}"
    zonder = _zonder_citaten(tekst)
    uit = list(hoeveelheden_buiten(zonder, tegen))
    schoon = _zonder_hoeveelheden(zonder)
    kent = _getallen(tegen)
    gezien: set[str] = set()
    for m in _TELLING.finditer(schoon):
        getal, woord = m.group(1), m.group(2).casefold()
        if woord in _GEEN_TELLING or _vorm(getal) in kent or _is_jaar(getal):
            continue
        uit.append(f"{getal} {woord}")
        gezien.add(_vorm(getal))
    for m in _GETAL.finditer(schoon):
        getal = m.group(1)
        if len(_vorm(getal)) >= 3 and _vorm(getal) not in kent and _vorm(getal) not in gezien:
            uit.append(getal)
            gezien.add(_vorm(getal))
    tegen_klein = tegen.casefold()
    uit += [n for n in _instanties(schoon) if n.casefold() not in tegen_klein]
    return list(dict.fromkeys(uit))
