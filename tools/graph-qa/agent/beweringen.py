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

Een **afgeleid getal** is geen bewering als de rekensom in de tekst staat: een som van twee of drie getallen die de
tekst noemt en die in het opgehaalde staan ("75 van de Hoge Raad en 91 van het Parket, samen 166"), het verschil van twee
("470 van de 623, de overige 153"), of een percentage van
zulke getallen ("232 en 222 van de 623, bijna 73%"). De operanden moeten allebei in de tekst én in de bron staan, zodat
de jurist de som kan nalopen; een getal dat toevallig de som is van twee getallen elders in de trace, telt niet (ronde 4:
de correctieronde vuurde op elke vraag naar een aandeel of een totaal, en bij X3 liet het model het gevraagde aandeel
weg).

Een **aantal** ("12 publicaties", "vijf wetten") hoort een aantal uit de trace te zijn: een geheel getal in de JSON (een
totaal, een telling per instantie) of de lengte van een lijst die een tool teruggaf (`tellingen`). Een klein getal staat
vaak toevallig ergens in de trace (in een datum, een nummer), dus dat volstaat niet (Staatsblad ronde 5, B03: "vijf wetten"
bij vier; B26: "vier aanpassingen" bij vijf). Een telwoord van twee tot twintig telt als getal; "een" en "één" niet, dat
zijn ook lidwoorden; een telwoord dat de gelezen tekst zelf gebruikt, telt niet (een samenvatting van een stuk). Wie
`beweringen` zonder `tellingen` aanroept, krijgt de oude toets: een telling in cijfers tegen
elk getal in de bron, en geen telwoorden.

Bekende grenzen: een aantal dat het model zelf telt uit een deel van een lijst ("drie daarvan gaan over …") is niet na te
lopen en telt dus als bewering.
"""
from __future__ import annotations

import re
from functools import lru_cache
from itertools import combinations

from .hoeveelheden import _DATUM, _HOEVEELHEID, _ISO_DATUM, buiten as hoeveelheden_buiten

#: Deze controle in de catalogus (ADR-014 §7, concept hook): deterministisch, op een vast moment, niet door het model
#: uit te zetten.
CONTROLE = {"naam": "beweringen", "label": "Feiten zonder bron", "doel": ("Zoekt in de toelichting datums, bedragen, nummers, tellingen en instanties die niet in het opgehaalde staan; eerst een correctieronde, daarna een signaal."),
            "moment": "na het antwoord, met de brongetrouwheid (verify_node)", "tests": ('tools/graph-qa/tests/test_beweringen.py',)}


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
# Een komma erna sluit alleen een decimaal uit ("4,5"), geen opsomming: "dossier 20588, 1988-1989" viel er anders helemaal
# buiten (Kamerstukken ronde 6, K16).
_GETAL = re.compile(r"(?<![\w.,/:-])(\d{1,3}(?:\.\d{3})+|\d+)(?!\w|,\d|[.:/-]\d)")
#: Een vergaderjaar: "1987/88", "1987-1988", "1987/1988", "1987–88". Het tweede jaar volgt op het eerste.
_VERGADERJAAR = re.compile(r"(?<![\w/-])((?:18|19|20)\d\d)\s*[/–-]\s*(\d{4}|\d{2})(?![\w/-])")
#: Een getal in de notatie van een Kamerdossier: "20 588" is 20588.
_DOSSIERNOTATIE = re.compile(r"(?<![\d.,])(\d{2,3}) (\d{3})(?!\d|[.,]\d)")
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
#: De telwoorden die een aantal maken; "een" en "één" niet (ook een lidwoord).
TELWOORDEN = {w: i for i, w in enumerate(
    "twee drie vier vijf zes zeven acht negen tien elf twaalf dertien veertien vijftien zestien zeventien achttien "
    "negentien twintig".split(), start=2)}
_TELWOORD = re.compile(rf"\b({'|'.join(TELWOORDEN)})\s+(?:van\s+de\s+\d+\s+)?([a-zà-ÿ][a-zà-ÿ-]{{2,}})\b", re.IGNORECASE)
_AANTAL = rf"(\d+|{'|'.join(TELWOORDEN)})"
_STUKKEN = r"(?:\w+\s+){0,2}?(uitspraken|arresten|vonnissen|stukken|kamerstukken|publicaties|bekendmakingen|documenten)"
_LEZEN = r"(?:gelezen|las|lazen|opgevraagd|opvroeg|doorgenomen|doornam|bestudeerd|bestudeerde)"
#: Een bewering over hoeveel stukken er gelezen zijn ("de subagent las 16 uitspraken", "16 uitspraken die hij las"). Zo'n
#: aantal toetst tegen de gelezen stukken (`gelezen.gelezen_en_gevonden`), niet tegen de aantallen in de trace: een
#: zoekresultaat met 16 treffers maakt geen 16 gelezen uitspraken (meting bundel 115, D01).
_GELEZEN_AANTAL = (
    re.compile(rf"\b{_AANTAL}\s+{_STUKKEN}\b[^.\n]{{0,40}}?\b{_LEZEN}\b", re.IGNORECASE),
    re.compile(rf"\b{_LEZEN}\b[^.\n]{{0,30}}?\b{_AANTAL}\s+{_STUKKEN}\b", re.IGNORECASE),
)


def gelezen_aantallen(tekst: str, gelezen: int) -> list[str]:
    """De aantallen gelezen stukken in `tekst` die groter zijn dan wat er gelezen is."""
    uit = []
    for patroon in _GELEZEN_AANTAL:
        for m in patroon.finditer(tekst):
            n = int(m.group(1)) if m.group(1).isdigit() else TELWOORDEN[m.group(1).casefold()]
            if n > gelezen:
                uit.append(f"{m.group(1)} {m.group(2).casefold()} gelezen (gelezen: {gelezen})")
    return uit


#: Een blokcitaat: wettekst of een passage uit het blok `extern`, met een eigen toets.
_BLOKCITAAT = re.compile(r"^[ \t]*>.*$", re.MULTILINE)
#: Een citaat tussen aanhalingstekens: idem.
_CITAAT = re.compile(r"[\"“„][^\"“”„\n]{2,}[\"”“]")


@lru_cache(maxsize=1)
def _citeervormen() -> tuple[re.Pattern[str], ...]:
    """De citeervormen van de connectors ("Stb. 2009, 610", "Kamerstukken II 1987/88, 20 588, nr. 3"): een id met een
    eigen toets (`unsupported`), dus zijn getallen tellen hier niet."""
    from bronmodel.connectors import CONNECTORS

    return tuple(re.compile(p, re.IGNORECASE) for c in CONNECTORS.values() for p, _ in c.citeervormen)


def _zonder_citaten(tekst: str) -> str:
    tekst = _BLOKCITAAT.sub(" ", tekst or "")
    tekst = _CITAAT.sub(" ", tekst)
    for patroon in (*_WEG, *_citeervormen()):
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
    """Elk getal in de bron, als losse cijferreeks, in de vorm met duizendtallen ("6.772" → "6772") en in de notatie van
    een Kamerdossier ("20 588" → "20588")."""
    uit = {_vorm(g) for g in re.findall(r"\d+", bron or "")}
    uit |= {_vorm(g) for g in re.findall(r"\d{1,3}(?:\.\d{3})+", bron or "")}
    uit |= {_vorm(a + b) for a, b in _DOSSIERNOTATIE.findall(bron or "")}
    return uit


def _vergaderjaren(tekst: str) -> set[str]:
    """De vergaderjaren in een tekst in één vorm ("1987/88" → "1987-1988"); een paar dat niet opeenvolgt, telt niet."""
    uit = set()
    for begin, eind in _VERGADERJAAR.findall(tekst or ""):
        volgend = int(eind) if len(eind) == 4 else int(begin[:2] + eind)
        if volgend == int(begin) + 1:
            uit.add(f"{begin}-{volgend}")
    return uit


def _zonder_vergaderjaren(tekst: str) -> str:
    return _VERGADERJAAR.sub(" ", tekst)


#: Een dossiernummer: een getal van vier tot zes cijfers dat geen jaar is.
def _dossiernummers(zin: str) -> set[str]:
    kandidaten = {_vorm(a + b) for a, b in _DOSSIERNOTATIE.findall(zin)}
    kandidaten |= {_vorm(g) for g in _GETAL.findall(_zonder_vergaderjaren(zin))}
    return {g for g in kandidaten if 4 <= len(g) <= 6 and not _is_jaar(g)}


def _paren_zonder_bron(tekst: str, bronnen: list[str]) -> list[str]:
    """Een dossier en een vergaderjaar in één zin horen samen in één bron te staan: "dossier 20588, 1988-1989" was een
    juist nummer met een fout jaar (de uitspraak zegt 1987/88), en elk apart stond wel ergens in de trace (K16)."""
    uit: list[str] = []
    per_bron = [(_getallen(b), _vergaderjaren(b)) for b in bronnen]
    for zin in re.split(r"(?<=[.;!?])\s+|\n+", tekst):
        jaren, dossiers = _vergaderjaren(zin), _dossiernummers(zin)
        for jaar in sorted(jaren):
            for d in sorted(dossiers):
                if not any(d in getallen and jaar in jaren_b for getallen, jaren_b in per_bron):
                    uit.append(f"dossier {d} in {jaar}")
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


#: Hoogstens zoveel getallen in een som; meer maakt toevallige treffers waarschijnlijk.
MAX_TERMEN = 3
#: Zoveel procentpunten mag een percentage afwijken van de rekensom ("bijna 73%" bij 72,9).
MARGE_PROCENT = 1.0


def _operanden(tekst: str, kent: set[str]) -> list[int]:
    """De getallen die de tekst noemt én die in de bron staan: de grondstof van een rekensom."""
    return sorted({int(_vorm(g)) for g in _GETAL.findall(tekst)
                   if _vorm(g) in kent and _vorm(g).isdigit() and not _is_jaar(_vorm(g))})


def _sommen(operanden: list[int]) -> set[int]:
    """De sommen van twee of drie operanden en de verschillen van twee."""
    sommen = {sum(c) for n in range(2, MAX_TERMEN + 1) for c in combinations(operanden, n)}
    return sommen | {b - a for a, b in combinations(operanden, 2) if b > a}  # "de overige 153" bij 470 van de 623


def _afgeleid(bewering: str, operanden: list[int], sommen: set[int]) -> bool:
    """Of een bewering een som of een percentage is van de operanden (zie de moduletekst)."""
    if m := re.fullmatch(r"(\d+(?:\.\d+)?) procent", bewering):
        p = float(m.group(1))
        tellers = set(operanden) | sommen
        return any(abs(100 * x / y - p) <= MARGE_PROCENT for y in operanden if y for x in tellers if x <= y)
    getal = _vorm(bewering.split()[0])
    return getal.isdigit() and int(getal) in sommen


def tellingen_uit(resultaten: list[str]) -> set[int]:
    """De aantallen in toolresultaten (JSON): elk geheel getal als waarde en de lengte van elke lijst. Geen JSON (een
    tekstresultaat) draagt niets bij."""
    import json

    uit: set[int] = set()

    def loop(x: object) -> None:
        if isinstance(x, bool):
            return
        if isinstance(x, int):
            uit.add(x)
        elif isinstance(x, list):
            uit.add(len(x))
            for y in x:
                loop(y)
        elif isinstance(x, dict):
            for y in x.values():
                loop(y)
    for r in resultaten:
        try:
            loop(json.loads(r))
        except (TypeError, ValueError):
            continue
    return uit


def regelingen_genoemd(tekst: str) -> list[str]:
    """De namen in `tekst` met de vorm van een regeling: een samenstelling op -wet ("Belastingwet"), een titel die met
    "Wet" begint, of een besluit of regeling met een jaartal of hoofdletters. Dezelfde vormen als
    `agent/buiten_graaf.py`; een afkorting telt niet, want die vorm is te los om er een bewering van te maken."""
    from . import buiten_graaf as bg
    uit: dict[str, None] = {}
    for patroon in (bg._SAMENSTELLING_RE, bg._WET_RE, *bg._TITEL_RES):
        for m in patroon.finditer(tekst):
            naam = re.sub(r"^(.*?\b(?:18|19|20)\d{2})\b.*$", r"\1", m.group("naam")).strip()
            if naam.casefold() not in bg._GEEN:
                uit.setdefault(naam)
    return list(uit)


def _regeling_bekend(naam: str, regelingen: set[str], tegen_klein: str) -> bool:
    """Kent de graaf deze regeling, of staat haar naam in het opgehaalde of in wat de jurist schreef? Ook zonder het
    jaartal: "de Invorderingswet" is de Invorderingswet 1990."""
    laag = naam.casefold()
    kaal = re.sub(r"\s+(?:18|19|20)\d{2}$", "", laag)
    return (laag in regelingen or kaal in regelingen or any(n.startswith(f"{kaal} ") for n in regelingen)
            or laag in tegen_klein or kaal in tegen_klein)


def beweringen(tekst: str, bron: str, *, bekend: str = "", tellingen: set[int] | None = None,
               bronnen: list[str] | None = None, regelingen: set[str] | None = None,
               gelezen: int | None = None) -> list[str]:
    """De feiten in `tekst` die niet in `bron` (de opgehaalde tekst) of `bekend` (de vraag) staan, in vaste volgorde.

    `bron` hoort ook de ruwe resultaten te dragen: een telling staat als getal in de JSON (`totaal`, `per_instantie`), en
    `resultaat.waarden` neemt alleen de tekstwaarden. `tellingen`: de aantallen uit de trace (`tellingen_uit`); daarmee
    toetst een aantal tegen een aantal, niet tegen elk getal. `bronnen`: de toolresultaten apart; daarmee moet een dossier
    met zijn vergaderjaar samen in één ervan staan. `regelingen`: de namen van de regelingen in de kennisgraaf (klein
    geschreven); daarmee is een regeling die de graaf niet kent en die nergens is opgehaald of gevraagd, een bewering
    (meting ADR-016 ronde 3, K12: "de Belastingwet" als voorbeeld, in een antwoord zonder bronnen). Zonder namen
    (geen graaf, een storing) geldt die toets niet."""
    tegen = f"{bron}\n{bekend}"
    zonder = _zonder_citaten(tekst)
    uit = list(hoeveelheden_buiten(zonder, tegen))
    # Een vergaderjaar is een eigen bewering, en zijn jaren tellen daarna niet nog eens als getal.
    jaren_bron = _vergaderjaren(tegen)
    uit += [f"vergaderjaar {j}" for j in sorted(_vergaderjaren(zonder)) if j not in jaren_bron]
    if bronnen is not None:
        uit += _paren_zonder_bron(zonder, [*bronnen, bekend])
    schoon = _DOSSIERNOTATIE.sub(r"\1\2", _zonder_vergaderjaren(_zonder_hoeveelheden(zonder)))
    kent = _getallen(tegen)
    gezien: set[str] = set()
    operanden = _operanden(_zonder_hoeveelheden(zonder), kent)
    sommen = _sommen(operanden)
    vraag = _getallen(bekend)
    tegen_klein = tegen.casefold()

    def telling_klopt(getal: str, woord: str) -> bool:
        if tellingen is None:
            return _vorm(getal) in kent
        n = int(_vorm(getal))
        # Een aantal uit de trace, uit de vraag, een rekensom van genoemde getallen, of letterlijk zo in de bron
        # ("12 leden" in de tekst van een stuk). Een getal van vier cijfers of meer dat in de bron staat, is een nummer
        # met een werkwoord erachter, geen eigen telling ("dossier 20588 valt", ronde 5, X5).
        return (n in tellingen or (n >= 1000 and _vorm(getal) in kent) or _vorm(getal) in vraag or n in sommen
                or re.search(rf"(?<![\d.]){n}\s+{re.escape(woord)}", tegen_klein) is not None)

    for m in _TELLING.finditer(schoon):
        getal, woord = m.group(1), m.group(2).casefold()
        if woord in _GEEN_TELLING or _is_jaar(getal) or telling_klopt(getal, woord):
            continue
        uit.append(f"{getal} {woord}")
        gezien.add(_vorm(getal))
    if tellingen is not None:
        for m in _TELWOORD.finditer(schoon):
            woord_n, woord = m.group(1).casefold(), m.group(2).casefold()
            # Een telwoord dat de gelezen tekst zelf gebruikt ("twee prejudiciële vragen" in een samenvatting van een
            # uitspraak) is geen eigen telling: de toets is voor een aantal bij een lijst.
            if woord in _GEEN_TELLING or telling_klopt(str(TELWOORDEN[woord_n]), woord) or \
                    re.search(rf"\b{woord_n}\b", tegen_klein):
                continue
            uit.append(f"{woord_n} {woord}")
    for m in _GETAL.finditer(schoon):
        getal = m.group(1)
        if len(_vorm(getal)) >= 3 and _vorm(getal) not in kent and _vorm(getal) not in gezien:
            uit.append(getal)
            gezien.add(_vorm(getal))
    uit += [n for n in _instanties(schoon) if n.casefold() not in tegen_klein]
    if regelingen:
        uit += [f"de regeling {n}" for n in regelingen_genoemd(zonder) if not _regeling_bekend(n, regelingen, tegen_klein)]
    uit = [b for b in dict.fromkeys(uit) if not _afgeleid(b, operanden, sommen)]
    # `gelezen`: hoeveel stukken er gelezen zijn. Een groter aantal "gelezen" is een bewering, ook als het aantal als
    # telling in de trace staat.
    return uit + gelezen_aantallen(zonder, gelezen) if gelezen is not None else uit
