"""Zoektermen uit een vraag of dossiertekst, zonder model: welke woorden zoeken, hun stam, samenstellingen en
ellipsen, en of een tekst of kop een term raakt. Gedeeld door het zoeken per deelvraag (`deelvraag_zoeken`), de
methoden van de bronnenrun (`bronnen_vinden`) en de intake."""
from __future__ import annotations

import re
from functools import cache

from .graph import queries


# "Wanneer is een aanslag invorderbaar?" noemt geen onderwerp in de vorm van een overzichtsvraag; het
# vraagwoord vooraan eraf laat "een aanslag invorderbaar" over, en `onderwerpwoorden` haalt de stopwoorden
# weg. Alleen vooraan: een vraagwoord midden in de zin kan bij het onderwerp horen.
_VRAAGBEGIN = re.compile(
    r"^\s*(?:in welke gevallen|onder welke voorwaarden|in hoeverre|op welke wijze|wanneer|wie|wat|welke?|hoe|"
    r"waar|waarom|waardoor|waarover|is|zijn|kan|kunnen|mag|mogen|moet|moeten|geldt|gelden)\b\s*", re.I)


def onderwerp_van_deelvraag(vraag: str) -> str:
    """Het zoekonderwerp van een deelvraag: als overzichtsvraag ("welke artikelen gaan over X?") het
    onderwerp, anders de vraag zonder vraagwoord vooraan; leeg als er niets zoekbaars overblijft."""
    from .overzicht import onderwerp_uit

    o = onderwerp_uit(vraag)
    if o:
        return o
    rest = vraag.strip()
    while (kaler := _VRAAGBEGIN.sub("", rest, count=1)) != rest:
        rest = kaler
    rest = rest.rstrip("?.! ")
    return rest if queries.onderwerpwoorden(rest) else ""


#: Woorden die in een vraag staan maar niets zoeken: hulpwerkwoorden, vraag- en voegwoorden. Bovenop de
#: stopwoorden van `queries.onderwerpwoorden`, die voor een overzichtsonderwerp zijn gemaakt.
_GEEN_TERM = {"binnen", "wanneer", "welk", "wie", "wat", "hoe", "waar", "waarom", "die", "dat", "deze", "dit",
              "moet", "moeten", "wordt", "worden", "werd", "kan", "kunnen", "mag", "mogen", "zijn", "is", "heeft",
              "hebben", "tegen", "na", "nog", "niet", "geen", "ook", "als", "dan", "zich", "hij", "zij", "er",
              "daarbij", "daarvoor", "hierbij", "welke", "eisen", "voldoen", "begint", "blijft"}


def zoektermen(tekst: str) -> list[str]:
    """De inhoudswoorden van een vraag of dossiertekst, in volgorde en zonder dubbelen."""
    return [w for w in queries.onderwerpwoorden(tekst) if w not in _GEEN_TERM]


def _stamdeel(term: str) -> str:
    return queries._stam(term)[:8]


#: "bezwaar- of beroepschrift", "aan- en verkoop": het eerste woord deelt zijn staart met het tweede.
_ELLIPS = re.compile(r"\b([a-zà-ÿ]{3,})- (of|en|dan wel|c\.q\.) ([a-zà-ÿ]{5,})\b")


def ellipsen_uitgevouwen(tekst: str) -> str:
    """De tekst met elke nevenschikkingsellips ook voluit: "bezwaar- of beroepschrift" krijgt
    "bezwaarschrift" erbij. Welk deel van het tweede woord de gedeelde staart is, zegt de tekst niet, dus
    elk einde van minstens vier letters gaat mee; een woord dat niet bestaat raakt niets."""
    t = tekst or ""
    extra = []
    for m in _ELLIPS.finditer(t.casefold()):
        eerste, tweede = m.group(1), m.group(3)
        extra += [eerste + tweede[i:] for i in range(1, len(tweede) - 3)]
    return f"{t} {' '.join(extra)}" if extra else t


def _raakt(termen: list[str], tekst: str, ellips: bool = False) -> list[str]:
    """De termen die de tekst raakt: het begin van hun stam staat erin ("termijn" raakt "termijnen",
    "bezwaarschrift" raakt "bezwaarschriften", en met `ellips` ook "bezwaar- of beroepschrift")."""
    t = (tekst or "").casefold()
    t = ellipsen_uitgevouwen(t) if ellips else t
    return [w for w in termen if _stamdeel(w) in t]


def splitsingen(term: str) -> list[tuple[str, str]]:
    """De manieren om een samenstelling in twee delen van minstens vijf letters te knippen
    ("belastingaanslag" → … ("belasting", "aanslag") …). Welke knip de echte is, weet de code niet; een
    knip die geen woord oplevert, raakt in de index niets."""
    return [(term[:i], term[i:]) for i in range(5, len(term) - 4)]


def kop_raakt(term: str, kop: str) -> bool:
    """Raakt een deelvraagterm de kop van een deel? Op het begin van de stam, of als deel van een
    samenstelling: "bezwaarschrift" raakt "Algemene bepalingen over bezwaar en beroep", "belastingaanslag"
    raakt "De aanslag"."""
    k = (kop or "").casefold()
    if _stamdeel(term) in k:
        return True
    for w in re.findall(r"[0-9a-zà-ÿ]+", k):
        if len(w) >= 5 and (term.startswith(queries._stam(w)) or term.endswith(w)):
            return True
    return False


_WOORD = re.compile(r"[0-9a-zà-ÿ]+")


@cache
def _taal():
    from .jas_pipeline.taal import maak_provider
    return maak_provider("spacy")


def lemmas(tekst: str, termen: list[str]) -> dict[str, str]:
    """Per zoekterm het lemma uit de taalanalyse, alleen als dat een ander woord is ("ingediend" →
    "indienen"). Zonder taalmodel leeg: dan zoekt Lex zonder lemma, zoals voorheen."""
    try:
        analyse = _taal().analyseer(tekst)
    except Exception:  # noqa: BLE001 – geen taalmodel is geen kapotte intake
        return {}
    uit = {}
    for t in analyse.tokens:
        w, lemma = t.tekst.casefold(), (t.lemma or "").casefold()
        if w in termen and lemma != w and _WOORD.fullmatch(lemma) and len(lemma) >= 3:
            uit.setdefault(w, lemma)
    return uit


#: Een uitsluiting in vrije tekst, tot het eind van het zinsdeel: erachter ("buiten beschouwing blijft …",
#: "behalve …", een zinsdeel dat met "niet" begint: "…, niet de Leidraad") of ervoor ("… valt buiten de afbakening").
_UITSLUITING_VOOR = re.compile(
    r"(?:buiten\s+(?:de\s+afbakening|beschouwing)(?:\s+(?:valt|vallen|blijft|blijven))?|(?:valt|vallen)\s+buiten\s*:|"
    r"uitgezonderd|behalve|met\s+uitzondering\s+van|(?:^|(?<=[,;:]))\s*niet)\s*:?\s+([^.;\n]+)", re.I | re.M)
_UITSLUITING_NA = re.compile(
    r"([^.;:\n]+?)\s+(?:valt|vallen|blijft|blijven)\s+buiten(?:\s+(?:de\s+afbakening|beschouwing))?\s*(?=[.;\n]|$)",
    re.I | re.M)


def buiten_uit_afbakening(afbakening: str) -> str:
    """Wat buiten het werkgebied valt, uit de afbakeningstekst. Het samenstellen schrijft de regel "Buiten de
    afbakening: …" (`werkgebied_intake.afbakening`); die gaat voor. Bij *Vul het dossier aan* bewerkt de analist
    de hele tekst, en dan kan die regel ontbreken: dan de uitsluitingen die de tekst zelf noemt (`_UITSLUITING_*`).
    Nooit de hele tekst: een afbakening zegt ook wat er wél bij hoort, en dat mag niet achteraan."""
    for regel in (afbakening or "").splitlines():
        if regel.strip().lower().startswith("buiten de afbakening:"):
            return regel.split(":", 1)[1].strip()
    tekst = afbakening or ""
    delen = [m.group(1).strip() for m in (*_UITSLUITING_NA.finditer(tekst), *_UITSLUITING_VOOR.finditer(tekst))]
    return "; ".join(d for d in delen if d)


# --- Wat de analist buiten het werkgebied laat -------------------------------------------------------

MIN_WOORD = 5
STAM = 8


def uitsluitstammen(buiten: str) -> list[str]:
    """"Overgangsrecht en de bestuurdersaansprakelijkheid" → ["overgang", "bestuurd"]: het begin van
    elk inhoudswoord, zodat "overgangsrecht" ook "Overgangs- en slotbepalingen" raakt. Korte woorden
    doen niet mee; die raken te veel."""
    stammen = [w.casefold()[:STAM] for w in queries.onderwerpwoorden(buiten or "") if len(w) >= MIN_WOORD]
    return list(dict.fromkeys(stammen))


def valt_buiten(kop: str, stammen: list[str]) -> str:
    """De stam waarop een kop buiten het werkgebied valt, of leeg."""
    k = (kop or "").casefold()
    return next((s for s in stammen if s in k), "")
