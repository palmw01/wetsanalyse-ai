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


def _raakt(termen: list[str], tekst: str, ellips: bool = False, heel: bool = False) -> list[str]:
    """De termen die de tekst raakt: het begin van hun stam staat erin ("termijn" raakt "termijnen",
    "bezwaarschrift" raakt "bezwaarschriften", en met `ellips` ook "bezwaar- of beroepschrift"). Met `heel`
    (`Zoekprofiel.stam_heel`) raakt een lange term op zijn hele stam of zijn kern (`raakt_heel`)."""
    t = (tekst or "").casefold()
    t = ellipsen_uitgevouwen(t) if ellips else t
    return [w for w in termen if (raakt_heel(w, t) if heel else _stamdeel(w) in t)]


#: Een slotdeel van een samenstelling telt als haar kern vanaf zoveel letters ("termijn", niet "mijn").
MIN_KERN = 5


def raakt_heel(term: str, tekst: str) -> bool:
    """Raakt een term de (kleine-letter)tekst op zijn hele stam? Een stam van hoogstens acht letters raakt zoals altijd op
    zijn begin. Een langere stam raakt als hij er heel in staat, of als een slotdeel van minstens `MIN_KERN` letters er als
    begin van een woord in staat: "betalingstermijnen" raakt "termijnen", "belastingjaar" raakt "jaar" niet en
    "belasting" ook niet. Zonder deze regel was "betalingstermijnen" hetzelfde als "betaling"."""
    stam = queries._stam(term)
    if len(stam) <= 8:
        return stam[:8] in tekst
    if stam in tekst:
        return True
    return any(re.search(rf"\b{re.escape(stam[i:])}", tekst) for i in range(1, len(stam) - MIN_KERN + 1))


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
    r"([^.;:\n]{1,500}?)(?<!\s)\s++(?:valt|vallen|blijft|blijven)\s++(?:er)?buiten(?:\s++(?:de\s++afbakening|beschouwing))?[^\S\n]*+(?=[.,;\n]|$)",
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


#: Wat in een uitsluitingszin staat maar zelf niets uitsluit: het werkwoord van de zin ("… vallen erbuiten").
_ZINSWOORDEN = {"valt", "vallen", "blijft", "blijven", "buiten", "erbuiten", "beschouwing", "afbakening", "niet",
                "net", "als", "evenals", "alsook", "zowel", "ook", "ander", "andere", "overige", "dergelijke"}
#: Een onderdeel eindigt bij een voorzetsel of bijzin: "het verrekenen met andere toeslagen" gaat over verrekenen,
#: niet over toeslagen; "de vergunning die van rechtswege ontstaat" over de vergunning. "van" en "voor" verbinden:
#: "de kosten van vervolging" gaat over kosten én vervolging.
_TOT = re.compile(r"\b(?:met|bij|in|door|na|op|tegen|uit|aan|over|naar|onder|zonder|tot|tussen|binnen|"
                  r"die|dat|wanneer|waarin|waarbij|waarop|zoals)\b")
_VERBINDT = re.compile(r"\b(?:van|voor)\b")
#: Wat erbij hoort, niet erbuiten: "de dwanginvordering behalve beslag".
_BEHALVE = re.compile(r"\b(?:behalve|uitgezonderd|met\s+uitzondering\s+van|maar\s+niet)\b.*$")
_DELEN = re.compile(r"[,;:]|\b(?:en|of|net\s+als|evenals|alsook|dan\s+wel)\b")
_LIDWOORDEN = {"de", "het", "een", "zijn", "haar", "hun"}
#: Een bijvoeglijk naamwoord vóór het kernwoord: het hoort bij de uitsluiting ("fiscale eenheid", "hoger beroep").
_BIJVOEGLIJK = re.compile(r"(?:lijke|lijk|ische|isch|iele|ele|ale|ieve|bare|ende|ige|ere|ste)$")
_BIJVOEGLIJK_WOORD = {"hoger", "hogere", "lager", "lagere", "eerste", "tweede", "nieuwe", "oude", "algemene",
                      "bijzondere", "gemeentelijke", "wettelijke"}


def _bijvoeglijk(woord: str) -> bool:
    return woord in _BIJVOEGLIJK_WOORD or bool(_BIJVOEGLIJK.search(woord))


#: Hoeveel zelfstandige naamwoorden achter elkaar samen één uitsluiting zijn ("hersteloperatie toeslagen").
MAX_KERNWOORDEN = 2


def _kern(stuk: str) -> tuple[str, list[str]]:
    """(bijvoeglijk naamwoord of leeg, kernwoorden) van een stukje tekst: de inhoudswoorden van minstens `MIN_WOORD`
    letters die geen bijvoeglijk naamwoord zijn, direct achter elkaar en hoogstens `MAX_KERNWOORDEN`, met het
    bijvoeglijk naamwoord direct ervoor."""
    woorden = [w for w in re.findall(r"[0-9a-zà-ÿ]+", stuk)
               if w not in _LIDWOORDEN and w not in _ZINSWOORDEN and w not in _GEEN_TERM]
    for i, w in enumerate(woorden):
        if not _bijvoeglijk(w) and len(w) >= MIN_WOORD:
            bijv = woorden[i - 1] if i and _bijvoeglijk(woorden[i - 1]) else ""
            kern = [w]
            for v in woorden[i + 1:]:
                if _bijvoeglijk(v) or len(v) < MIN_WOORD or len(kern) >= MAX_KERNWOORDEN:
                    break
                kern.append(v)
            return bijv, kern
    return "", []


def uitsluitstammen_woorden(buiten: str) -> list[str]:
    """De lezing van vóór 18 nov 2026: het begin van elk inhoudswoord. Alleen nog voor de meting op oude opnames
    (`Zoekprofiel.afbakening_onderdelen` uit)."""
    stammen = [w.casefold()[:STAM] for w in queries.onderwerpwoorden(buiten or "") if len(w) >= MIN_WOORD]
    return list(dict.fromkeys(stammen))


def uitsluitstammen(buiten: str, onderwerp: str = "") -> list[str]:
    """Per onderdeel van wat buiten het werkgebied valt één stam: het begin van het kernwoord ("Overgangsrecht en de
    bestuurdersaansprakelijkheid" → ["overgang", "bestuurd"]), zodat "overgangsrecht" ook "Overgangs- en
    slotbepalingen" raakt. Een stam kan uit meer woorden bestaan; hij raakt een tekst pas als elk deel erin staat
    (`raakt_uitsluiting`).

    - Een onderdeel is een deel van de opsomming (komma, "en", "of", "net als").
    - Het kernwoord is het eerste inhoudswoord vóór een voorzetsel of bijzin; een bijvoeglijk naamwoord ervoor gaat
      mee ("fiscale eenheid", "hoger beroep").
    - "X van Y" en "X voor Y" zijn X en Y samen ("kosten vervolgi", "aansprak bronbela"), ook als X het onderwerp
      is: alleen Y zou te veel raken ("beslissing" in een werkgebied over beslistermijnen).
    - Niet mee: het werkwoord van de zin ("vallen erbuiten"), wat tussen haakjes staat (uitleg, voorbeelden), wat na
      "behalve" komt (dat hoort er juist bij), een voorzetselgroep ("met andere toeslagen"), korte woorden, en een kale
      stam die in het `onderwerp` staat (naam, analysevraag, deelvragen): "kwijtschelding voor ondernemers" sluit in
      een werkgebied over kwijtschelding de ondernemers uit, niet de kwijtschelding.

    Bronnenrun op acceptatie, 18 nov 2026: elk woord van de zin werd een stam, ook "toeslage", "andere", "aansprak" in
    een werkgebied over aansprakelijkheid, en "beslag" bij "behalve beslag"."""
    # Geen ellipsen uitvouwen: "schenk- en erfbelasting" geeft "schenk", en dat raakt "schenkbelasting" al.
    tekst = re.sub(r"\([^)]*\)", " ", buiten or "").casefold()
    in_onderwerp = (onderwerp or "").casefold()

    def deel_stam(bijv: str, kern: list[str]) -> str:
        return " ".join([*([bijv] if bijv else []), *(w[:STAM] for w in kern)])

    def onderwerp_zelf(bijv: str, kern: list[str]) -> bool:
        return not bijv and len(kern) == 1 and queries._stam(kern[0])[:STAM] in in_onderwerp

    stammen: list[str] = []
    for deel in _DELEN.split(tekst):
        deel = _BEHALVE.sub("", deel)
        m = _TOT.search(deel)
        deel = deel[:m.start()] if m else deel
        x, *rest = _VERBINDT.split(deel, maxsplit=1)
        y = rest[0] if rest else ""
        bx, kx = _kern(x)
        by, ky = _kern(y) if y else ("", [])
        if not kx:
            continue
        if ky:
            stammen.append(f"{deel_stam(bx, kx)} {deel_stam(by, ky)}")
        elif not onderwerp_zelf(bx, kx):
            stammen.append(deel_stam(bx, kx))
    return list(dict.fromkeys(stammen))


def uitsluiting_gewicht(stammen: list[str], tekst: str, woordbegin: bool = False) -> int:
    """Hoeveel een tekst raakt aan wat buiten het werkgebied valt: per stam die hem raakt het aantal delen ("kosten
    vervolgi" telt twee, zoals de twee woorden toen elk een eigen stam waren). Eén plek voor de woordenroute en de
    zoekvragen."""
    return sum(len(s.split()) for s in stammen if raakt_uitsluiting(s, tekst, woordbegin))


def raakt_uitsluiting(stam: str, tekst: str, woordbegin: bool = False) -> bool:
    """Raakt een uitsluitstam (`uitsluitstammen`) de tekst? Elk deel moet erin staan; met `woordbegin` aan het begin
    van een woord ("vallen" raakt "vallen buiten", niet "in andere gevallen")."""
    t = (tekst or "").casefold()
    if woordbegin:
        return all(re.search(rf"\b{re.escape(d)}", t) for d in stam.split())
    return all(d in t for d in stam.split())


def onderwerp_van(dossier: dict, deelvragen: list | None = None) -> str:
    """Waar het werkgebied over gaat, voor `uitsluitstammen`: naam, analysevraag en de deelvragen (tekst of
    `{vraag}`)."""
    vragen = [d if isinstance(d, str) else str((d or {}).get("vraag") or "") for d in (deelvragen or [])]
    return " ".join([str(dossier.get("naam") or ""), str(dossier.get("analysevraag") or ""), *vragen])


def buiten_stammen(dossier: dict, deelvragen: list | None = None, onderdelen: bool = True) -> list[str]:
    """De uitsluitstammen van een dossier: wat de afbakening buiten het werkgebied laat, gelezen tegen zijn
    onderwerp. Eén plek voor de bronselectie, de grondslag en de opschriften. `onderdelen` is
    `Zoekprofiel.afbakening_onderdelen`."""
    buiten = buiten_uit_afbakening(str(dossier.get("afbakening") or ""))
    if not onderdelen:
        return uitsluitstammen_woorden(buiten)
    return uitsluitstammen(buiten, onderwerp_van(dossier, deelvragen))


def valt_buiten(kop: str, stammen: list[str]) -> str:
    """De stam waarop een kop buiten het werkgebied valt, of leeg."""
    return next((s for s in stammen if raakt_uitsluiting(s, kop)), "")
