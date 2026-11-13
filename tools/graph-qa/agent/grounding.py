"""
Grounding-/verificatie: controleert of het ANTWOORD herleidbaar is tot de tool-executietrace.

Deterministisch, geen extra LLM-call in het live pad. Twee controles naast elkaar:

1. **Vindplaatsen** – elke verwijzing (IRI/jci/BWB-id) in het antwoord moet in de trace voorkomen.
   Bewust op BWB-id-granulariteit: zo vangen we het echte falen (een verzonnen regeling die de graaf
   nooit teruggaf) zónder vals alarm op afwijkende jci-formattering of geparafraseerde IRI's.
2. **Citaten** – tekst die het antwoord tússen aanhalingstekens zet, moet letterlijk in de
   opgehaalde tekst staan. De agent belooft letterlijk te citeren en de annotatieketen dwingt dat af
   (`annotatie.komt_letterlijk_voor`); in het antwoordpad ontbrak diezelfde controle, terwijl een
   citaat met één woord verschil precies is waar een jurist op afgaat.

En een derde uitkomst naast gegrond/ongegrond: **onbepaald**. Een antwoord dat géén vindplaats en
géén citaat noemt, is niet "gegrond" – er valt niets te controleren. Dat als groen tellen is
schijnzekerheid, en juist die wil dit platform bestrijden.
"""
from __future__ import annotations

import logging
import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import unquote

from .annotatie import _normaliseer, komt_letterlijk_voor
from .beweringen import beweringen as feiten_buiten, tellingen_uit
from .hoeveelheden import uit_tabellen
from .models import Source
from bronmodel.connectors import leestools, van_id
from bronmodel.extern import externe_verwijzingen, externe_vindplaats

from .provenance import _BWB_RE, citations_in, first_bwb
from .resultaat import is_contract, waarden
from .tools.begrip_tools import AFGELEIDE_TOOL_NAMEN

#: Deze controle in de catalogus (ADR-014 §7, concept hook): deterministisch, op een vast moment, niet door het model
#: uit te zetten.
CONTROLE = {"naam": "brongetrouwheid", "label": "Controle op brongetrouwheid", "doel": ("Toetst na het antwoord of elke vindplaats uit de graaf kwam en elk citaat letterlijk in de opgehaalde tekst staat; bij een afwijking één correctieronde, daarna gaat het oordeel mee."),
            "moment": "na het antwoord, vóór uitgifte (verify_node; Stop-hook)", "tests": ('tools/graph-qa/tests/test_grounding.py',)}


logger = logging.getLogger(__name__)

# Citaten in de vormen die een model gebruikt: rechte, typografische en Nederlandse dubbele aanhalingstekens, ook
# gemengd. De ene tabel voor de herkenning én het herstel: een vorm die er maar op één plek bijkomt, wordt wel
# afgekeurd maar nooit meer hersteld. Enkele quotes blijven erbuiten – die staan in Nederlandse lopende tekst te vaak
# om iets anders (een aanhaling binnen een aanhaling, een apostrof) en zouden vals alarm geven.
_PAREN = (('"', '"'), ("“", "”"), ("„", "”"), ("„", '"'), ("„", "“"))


def _citaat_patroon() -> re.Pattern[str]:
    """Per openingsteken tot het eerste sluitteken, binnen één alinea en zonder lengtegrens: een lang citaat is juist
    het citaat waar een jurist op afgaat, en een lege regel betekent dat een los aanhalingsteken geen paar heeft."""
    delen = []
    for open_ in dict.fromkeys(o for o, _ in _PAREN):
        sluit = "".join(re.escape(d) for o, d in _PAREN if o == open_)
        delen.append(rf"{re.escape(open_)}((?:(?!\n[ \t]*\n)[^{sluit}]){{2,}})[{sluit}]")
    return re.compile("|".join(delen))


_CITAAT_RE = _citaat_patroon()

# Onder deze lengte controleren we niet. Een korte quote is meestal een begrip of een label
# ("belastingschuldige", "de ontvanger") en geen citaat van een passage; daar is de kans op een
# terechte afwijking (verbuiging, hoofdletter) groter dan de opbrengst van de controle.
_MIN_WOORDEN = 5


@dataclass
class GroundingReport:
    grounded: bool
    cited: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    # Tekst die het antwoord als citaat presenteert maar die niet letterlijk in de trace staat.
    niet_letterlijk: list[str] = field(default_factory=list)
    # Hoeveel passages er als citaat zijn nagelopen – geslaagd én mislukt. Zonder dit getal is niet te
    # melden wát er is gecontroleerd: een antwoord dat artikelen in gewone taal noemt ("artikel 2 lid
    # 1 onderdeel m") heeft nul vindplaatsen, en dan las de tijdlijn "0 verwijzingen onderbouwd" —
    # terwijl er twee citaten wél waren getoetst en klopten.
    citaten: int = 0
    # Wat niet is teruggevonden maar ook niet is afgekeurd (`_onbevestigd`). Telt niet in `grounded`: geen correctieronde.
    onbevestigd: list[str] = field(default_factory=list)
    # Feiten in de tekst (een datum, een nummer, een telling, een instantie) die het opgehaalde en de vraag niet noemen
    # (`beweringen`). Hier een signaal zoals `onbevestigd`; `verify_node` vraagt er eerst een correctieronde voor.
    beweringen: list[str] = field(default_factory=list)
    # "gegrond" | "onbepaald" | "ongegrond" – fijner dan de bool, die voor het bestaande
    # event-contract blijft bestaan.
    niveau: str = "gegrond"


def _citaten(text: str) -> list[str]:
    """De passages die het antwoord als letterlijk citaat presenteert."""
    uit: list[str] = []
    for m in _CITAAT_RE.finditer(text or ""):
        passage = next((g for g in m.groups() if g), "").strip()
        if len(passage.split()) >= _MIN_WOORDEN:
            uit.append(passage)
    return uit


_BLOCKQUOTE_RE = re.compile(r"(?:^[ \t]*>.*(?:\n|$))+", re.MULTILINE)
_AANHALINGSTEKENS = frozenset(t for paar in _PAREN for t in paar)
_ARTIKEL_VINDPLAATS = re.compile(r""":(?:artikel|bepaling):([^\s:"'<>,\\`*]+)|[&?]artikel=([^\s&"'<>,\\`*]+)""", re.IGNORECASE)
# Een artikel in een boek (BW): de jci noemt het boek apart (`boek=6&…&artikel=162`), en de tekst noemt het "artikel
# 6:162" (meting wetgeving_live ronde 2, I24/I28: "6:162" en "2:9" bleven onbevestigd). Ook in een IRI met `:boek:`.
_BOEK_ARTIKEL = re.compile(r"""[&?]boek=([^\s&"'<>,\\`*]+)(?:&(?!artikel=)[^\s&"'<>,\\`*]*)*&artikel=([^\s&"'<>,\\`*]+)"""
                           r"""|:boek:([^\s:"'<>,\\`*]+)(?::[^\s"'<>,\\`*]*?)?:artikel:([^\s:"'<>,\\`*]+)""", re.IGNORECASE)
# Een opbouwtreffer noemt zijn bepalingen als kale lijst (`bepalingen: "4, 5"`), zonder IRI per bepaling.
_ARTIKEL_VELD = re.compile(r'''"(?:artikel|nummer|bepalingen)"\s*:\s*"([^"]+)"''')


def _blockquotes(text: str) -> list[str]:
    """Blokcitaten van voldoende lengte. Staan er aanhalingstekens in, dan toetst `_citaten` ze al."""
    uit: list[str] = []
    for blok in _BLOCKQUOTE_RE.findall(text or ""):
        passage = " ".join(re.sub(r"^[ \t]*>[ \t]?", "", regel) for regel in blok.splitlines()).strip()
        if len(passage.split()) >= _MIN_WOORDEN and not _AANHALINGSTEKENS & set(passage):
            uit.append(passage)
    return uit


def _bekende_artikelen(source_trace: list[tuple[str, str]]) -> set[str]:
    """Elk artikel dat in de opgehaalde resultaten voorkomt: als vindplaats (IRI of jci), of omdat de tekst het noemt
    ("bedoeld in artikel 8"). Dat laatste is een terechte vermelding die in geen enkele IRI staat. Ook de afgeleide
    tools tellen mee: een annotatie is geen bron voor een citaat, maar wijst wel naar een bestaande bepaling."""
    from .overzicht import vermeldingen

    bekend: set[str] = set()
    for _naam, tekst in source_trace:
        for m in _ARTIKEL_VINDPLAATS.finditer(tekst or ""):
            bekend.add(unquote(m.group(1) or m.group(2)).casefold())
        for m in _BOEK_ARTIKEL.finditer(tekst or ""):
            boek, artikel = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            bekend.add(unquote(f"{boek}:{artikel}").casefold())
        for m in _ARTIKEL_VELD.finditer(tekst or ""):
            bekend |= {nummer.strip().casefold() for nummer in m.group(1).split(",")}
        bekend |= {v.removeprefix("artikel ").casefold() for v in vermeldingen(waarden(tekst or ""))
                   if v.startswith("artikel ")}
    return bekend


def _onbevestigd(answer_text: str, source_trace: list[tuple[str, str]], trace_text: str) -> list[str]:
    """Wat het antwoord noemt maar niet in het opgehaalde terug te vinden is: artikelen in gewone taal, en blokcitaten
    die niet letterlijk kloppen. Een signaal en geen afkeuring: een blokcitaat over twee leden en een artikel uit een
    samenvatting zijn vaak terecht, dus eerst meten hoe vaak dit vals alarm is."""
    from .overzicht import vermeldingen

    bekend = _bekende_artikelen(source_trace)
    uit = [v for v in vermeldingen(answer_text)
           if v.startswith("artikel ") and v.removeprefix("artikel ").casefold() not in bekend]
    for passage in _blockquotes(answer_text):
        if "\\" not in passage and not komt_letterlijk_voor(trace_text, passage):
            uit.append(passage if len(passage) <= 80 else passage[:80].rstrip() + "…")
    # Een termijn, bedrag of datum die het antwoord noemt en het opgehaalde niet (R4a) is een bewering: `beweringen`.
    return uit


_EIND_LEESTEKENS = " .,;:"


def herstel_citaten(answer_text: str, source_trace: list[tuple[str, str]]) -> tuple[str, list[tuple[str, str]]]:
    """Maak een bijna-letterlijk citaat letterlijk, met de tekst zoals die in de bron staat.

    Het model citeert soms net niet letterlijk: een hoofdletter aan het begin ("Zes weken" waar de
    bron "zes weken" heeft) of een punt binnen de aanhalingstekens waar de bron doorloopt. De
    controle keurde dat terecht af, maar dan volgde een volledige correctieronde – en de jurist had
    het afgekeurde antwoord al gezien. Zo'n afwijking is mechanisch te herstellen: zoek de passage
    hoofdletter- en witruimte-ongevoelig, zonder leestekens aan het eind, en zet de BRONTEKST terug.
    Een leesteken dat in het citaat stond maar niet in de bron, komt achter het aanhalingsteken.

    Alleen bij één eenduidige vindplaats. Al het andere – weglatingen, eigen woorden, een andere
    verbuiging – blijft een afwijking voor `check_grounding`. Het citaat wordt hier dus alleen
    letterlijker, nooit losser. Geeft het herstelde antwoord en de paren (oud, nieuw)."""
    trace_text = _normaliseer(
        "\n".join(waarden(t) for name, t in source_trace if t and name not in AFGELEIDE_TOOL_NAMEN))
    hersteld: list[tuple[str, str]] = []
    for citaat in _citaten(answer_text):
        if "\\" in citaat or komt_letterlijk_voor(trace_text, citaat):
            continue
        kern = citaat.rstrip(_EIND_LEESTEKENS)
        woorden = kern.split()
        if len(woorden) < _MIN_WOORDEN:
            continue
        patroon = r"(?<!\w)" + r"\s+".join(re.escape(w) for w in woorden) + r"(?!\w)"
        vindplaatsen = {m.group(0) for m in re.finditer(patroon, trace_text, re.IGNORECASE)}
        if len(vindplaatsen) != 1:
            continue
        bron = vindplaatsen.pop()
        staart = citaat[len(kern):].strip()
        for open_, dicht in _PAREN:
            answer_text = answer_text.replace(f"{open_}{citaat}{dicht}", f"{open_}{bron}{dicht}{staart}")
        hersteld.append((citaat, bron))
    return answer_text, hersteld


def _feitenbron(source_trace: list[tuple[str, str]], trace_text: str) -> str:
    """Waartegen een bewering getoetst wordt: de waarden, de ruwe resultaten (een telling is een getal in de JSON) en de
    getallen uit tabellen met hun eenheid. Zonder de afgeleide tools: een annotatie is geen bron."""
    ruw = "\n".join(t for name, t in source_trace if t and name not in AFGELEIDE_TOOL_NAMEN)
    return f"{trace_text}\n{ruw}\n{uit_tabellen(source_trace)}"


def check_grounding(answer_text: str, source_trace: list[tuple[str, str]],
                    overzicht: dict | None = None, *, bekend: str = "",
                    regelingen: set[str] | None = None) -> GroundingReport:
    """Markeer wat in het antwoord niet uit de trace te herleiden is: verwijzingen én citaten.

    Met een `overzicht` (de overzichtsroute) telt ook elk genoemd artikel dat niet in het overzicht
    staat als onderbouwd-noch-opgehaald (`overzicht.vermeldingen_buiten`)."""
    # De waarden van een contractresultaat, niet zijn JSON-tekst: anders staat een newline in de
    # brontekst er als `\n` en valt een letterlijk citaat over die grens af (`resultaat.waarden`).
    trace_text = "\n".join(waarden(t) for name, t in source_trace if t and name not in AFGELEIDE_TOOL_NAMEN)
    # Exacte BWB-id's uit de trace (woordgrens via _BWB_RE), zodat een gehallucineerde prefix-id
    # (bv. BWBR0001 t.o.v. het opgehaalde BWBR00012345) niet vals als gegrond geldt.
    trace_bwbs = set(_BWB_RE.findall(trace_text))
    # Een externe bron (ADR-013) op zijn canonieke id: `celex:` en `CELEX:`, een ELI over http of https.
    trace_extern = {e.id for e in externe_verwijzingen(trace_text)}
    cited = citations_in(answer_text)
    unsupported: list[str] = []
    for c in cited:
        bwb = first_bwb(c)
        if (ext := externe_vindplaats(c)) is not None:
            if ext.id not in trace_extern:
                unsupported.append(c)
        elif bwb is not None:
            if bwb not in trace_bwbs:
                unsupported.append(c)
        elif c not in trace_text:
            unsupported.append(c)

    # Dezelfde eis en dezelfde normalisatie als bij een JAS-markering: witruimte-ongevoelig, verder
    # letterlijk. Een citaat dat een aanhalingsteken bevat slaan we over – de trace draagt de
    # tool-resultaten rauw (JSON-string-wrapped TSV), dus daar zijn quotes ge-escaped en zou een
    # terecht citaat als afwijking uit de bus komen.
    citaten = _citaten(answer_text)
    niet_letterlijk = [
        c for c in citaten
        if "\\" not in c and not komt_letterlijk_voor(trace_text, c)
    ]

    if overzicht:
        # Elke genoemde bepaling is getoetst tegen het overzicht: wat erin staat is gecontroleerd en
        # goed, wat er niet in staat is ongegrond.
        from .overzicht import vermeldingen, vermeldingen_buiten
        buiten = vermeldingen_buiten(answer_text, overzicht)
        unsupported += [v for v in buiten if v not in unsupported]
        cited = [*cited, *(v for v in vermeldingen(answer_text) if v not in cited)]

    # De overzichtsroute heeft hierboven elke genoemde bepaling al hard getoetst.
    onbevestigd = [] if overzicht else _onbevestigd(answer_text, source_trace, trace_text)
    # `bekend`: wat de jurist zelf schreef (de vraag, het dossier). Een feit dat hij noemt, is geen bewering van Lex.
    # De aantallen uit wat een bron teruggaf. Rust de beurt alleen op afgeleide tools (de annotaties), dan is er geen bron
    # om een aantal tegen te toetsen, en geldt de toets zonder aantallen (een overzicht van annotaties telt per groep).
    uit_bron = [t for name, t in source_trace if t and name not in AFGELEIDE_TOOL_NAMEN]
    tellingen = tellingen_uit(uit_bron) if uit_bron else None
    feiten = [] if overzicht else [f for f in feiten_buiten(answer_text, _feitenbron(source_trace, trace_text),
                                                              bekend=bekend, tellingen=tellingen,
                                                              bronnen=[f"{waarden(t)}\n{t}" for t in uit_bron],
                                                              regelingen=regelingen)
                                   if f not in unsupported]
    # Een stuk van een bronconnector (ADR-013) dat het antwoord noemt en dat alleen in een zoekresultaat stond, is
    # gevonden, niet gelezen. Dat is geen signaal: het id bestaat en het zoekresultaat draagt zijn label, soort, datum
    # en titel uit de bron. Tot 10 nov 2026 telde zo'n stuk als onbevestigd; op acceptatie gaf een lijst opvolgende
    # stukken zo 13 waarschuwingen die er niet hoorden. Een citaat uit zo'n stuk blijft getoetst (`niet_letterlijk`),
    # en in de bronnenlijst komt het pas als het gelezen is (`alleen_gelezen_extern`). Gelogd, zodat het te meten is.
    lees = leestools()
    gelezen = {e.id for name, t in source_trace if t and name in lees for e in externe_verwijzingen(waarden(t))}
    gevonden = {ext.id for c in cited if (ext := externe_vindplaats(c)) is not None and van_id(ext.id) is not None
                and ext.id in trace_extern and ext.id not in gelezen}
    if gevonden:
        logger.info("alleen gevonden genoemd", extra={"categorie": "functioneel", "aantal": len(gevonden)})

    if unsupported:
        niveau = "ongegrond"
    elif not cited and not citaten:
        # Niets te controleren. Dat is geen bewijs van juistheid – zeg dat dan ook.
        niveau = "onbepaald"
    elif niet_letterlijk:
        niveau = "ongegrond"
    elif onbevestigd or feiten:
        # Niet afgekeurd, maar ook niet goedgekeurd.
        niveau = "onbepaald"
    else:
        niveau = "gegrond"

    return GroundingReport(
        citaten=len(citaten),
        # `grounded` blijft de vraag "is er iets aangetroffen dat níét klopt": het bestaande
        # event-contract en de eval hangen eraan. `onbevestigd` telt hier bewust niet mee. Het onderscheid tussen "gecontroleerd en goed" en
        # "er viel niets te controleren" zit in `niveau`.
        grounded=not unsupported and not niet_letterlijk,
        cited=cited,
        unsupported=unsupported,
        niet_letterlijk=niet_letterlijk,
        onbevestigd=onbevestigd,
        beweringen=feiten,
        niveau=niveau,
    )


# Sleutels die een plek in de structuur aanduiden maar niet de bepaling zelf: een jci draagt vaak
# `hoofdstuk=I` terwijl de graaf-IRI van hetzelfde lid dat niet doet. Datumsleutels (`g`, `z`)
# zeggen iets over de versie, niet over de plek.
_OMHULSEL = frozenset({"hoofdstuk", "afdeling", "paragraaf", "subparagraaf", "titeldeel", "titel",
                       "boek", "deel", "g", "z"})
_JCI_DELEN = re.compile(r"jci[\d.]+:c:(BWB[RV]\d+)(.*)$", re.I)


def _locatie(uri: str) -> tuple[str, tuple[tuple[str, str], ...]] | None:
    """(BWB-id, pad) van een vindplaats: het pad is de reeks sleutel/waarde-paren zonder omhulsel
    (`artikel`, `lid`, `o` …). Graaf-IRI en jci leveren voor dezelfde bepaling hetzelfde pad."""
    u = uri.strip()
    if u.startswith("urn:bwb:"):
        bwb, *rest = u[len("urn:bwb:"):].split(":")
        if len(rest) % 2:
            return None
        paren = list(zip(rest[::2], rest[1::2]))
    elif m := _JCI_DELEN.search(u):
        bwb = m.group(1).upper()
        paren = [tuple(d.split("=", 1)) for d in m.group(2).split("&") if "=" in d]
    else:
        return None
    return bwb, tuple((k.lower(), v) for k, v in paren if k.lower() not in _OMHULSEL)


def _op_pad(a: tuple[tuple[str, str], ...], b: tuple[tuple[str, str], ...]) -> bool:
    """Ligt de ene vindplaats boven of onder de andere (of zijn ze gelijk)?"""
    kort, lang = (a, b) if len(a) <= len(b) else (b, a)
    return lang[: len(kort)] == kort


def genoemd_extern(tekst: str) -> set[str]:
    """De ids van de stukken naast de wet die een tekst noemt: bij id ("stb-2013-568", een ECLI) én in een citeervorm van
    een connector ("Stb. 2013, 568", "Staatscourant 2026, nr. 37344", "Kamerstuk 32140, nr. 342", "ecli nl hr 2022 50").
    Zonder de citeervorm viel een gelezen stuk dat het antwoord zo noemt uit de bronnenlijst (meting Kamerstukken ronde 2,
    K18)."""
    from bronmodel.connectors import genoemde_stukken

    return {e.id for e in externe_verwijzingen(tekst or "")} | {i for _, i in genoemde_stukken(tekst or "")}


def curate_sources(sources: list[Source], answer_text: str) -> list[Source]:
    """Beperk de bronnenlijst tot wat het antwoord aanhaalt.

    Eerst op regeling: opgehaalde-maar-onbesproken regelingen (BWB-id's die het antwoord niet
    noemt) vallen weg. Dan, binnen een regeling waarvan het antwoord een precieze vindplaats
    citeert (een jci of graaf-IRI met artikel/lid/onderdeel), op pad: alleen bronnen die boven of
    onder een geciteerde vindplaats liggen blijven staan. Een definitievraag haalt art. 2 lid 1 op
    met al zijn onderdelen a–z; zonder padfilter toont de lijst dan 28 bronnen voor een antwoord over
    onderdeel k.

    Noemt het antwoord een regeling alleen met haar BWB-id, dan blijven al haar bronnen staan. Valt
    terug op de volledige lijst als het antwoord geen BWB-id noemt (dan niets
    weggooien), en op de regelingsfilter als de padfilter niets overlaat.
    """
    bwbs = set(_BWB_RE.findall(answer_text))
    if not bwbs:
        return sources
    # Een externe bron (ADR-013) blijft staan als het antwoord haar id noemt; zonder id volgt ze de regel
    # van de regelingen: onbesproken, dus weg zodra het antwoord wél regelingen noemt.
    genoemd = genoemd_extern(answer_text)
    extern = [s for s in sources if s.brontype not in (None, "wettekst") and s.uri in genoemd]
    # Exacte BWB-id-match (woordgrens) i.p.v. substring, zodat een genoemde prefix-id geen bron van
    # een langere regeling meesleept.
    kept = [s for s in sources if (m := _BWB_RE.search(s.uri)) and m.group(0) in bwbs]
    if not kept:
        return sources
    geciteerd: dict[str, list[tuple[tuple[str, str], ...]]] = {}
    for c in citations_in(answer_text):
        loc = _locatie(c)
        if loc and loc[1]:
            geciteerd.setdefault(loc[0], []).append(loc[1])
    if not geciteerd:
        return [*kept, *extern]

    def blijft(s: Source) -> bool:
        loc = _locatie(s.uri)
        if loc is None or loc[0] not in geciteerd:
            return True
        return any(_op_pad(loc[1], pad) for pad in geciteerd[loc[0]])

    fijn = [s for s in kept if blijft(s)]
    return [*(fijn or kept), *extern]


def alleen_gelezen_extern(sources: list[Source], trace: list[tuple[str, str]], answer_text: str,
                          vraag: str = "", geciteerd: frozenset[str] = frozenset()) -> list[Source]:
    """Een bron naast de wet (ADR-013) staat alleen in de bronnenlijst als ze gelezen is (in een resultaat van de
    leestool van haar connector) én het antwoord haar noemt. Wat alleen gevonden is, is geen bron: dat staat al als
    "alleen gevonden, niet gelezen" in `onbevestigd` (acceptatie 8 nov 2026: "Klaar · 32 bronnen" voor één gelezen
    Kamerstuk, omdat `curate_sources` zonder BWB-id in het antwoord niets snoeit). Een extern id zonder connector (een
    EHRM-uitspraak waar een gelezen uitspraak naar verwijst, `ECLI:CE:…`) staat er alleen als het antwoord het noemt
    (nameting 10 nov 2026). Wettekst blijft ongemoeid.

    Het gelezen stuk zelf (het `stuk` van de leestool) staat er ook als de vraag het noemt: een antwoord óver
    ECLI:NL:HR:2022:50 noemt die ECLI vaak niet meer, en dan miste de bronnenlijst precies het stuk dat gelezen is
    (derde meting 10 nov 2026). Net zo een gelezen stuk waaruit het sjabloon citeert (`geciteerd`: de blokken `extern`):
    de tekst noemt het dan in een citeervorm ("Stb. 2010, 176"), en die herkent `externe_verwijzingen` niet (meting
    bekendmakingen B04). Een gelezen wettekst van overheid.nl (`wettekst_live`) blijft altijd staan: dat is wettekst."""
    lees = leestools()
    in_tekst: set[str] = set()
    stukken: set[str] = set()
    for name, t in trace:
        if not t or name not in lees:
            continue
        in_tekst |= {e.id for e in externe_verwijzingen(waarden(t))}
        # Het gelezen stuk, uit elk resultaat van de leestool: ook een fout met een stuk (`alleen_pdf`).
        try:
            data = json.loads(t)
        except (TypeError, ValueError):
            data = {}
        data = data if isinstance(data, dict) else {}
        if isinstance(data.get("stuk"), dict) and (vp := externe_vindplaats(str(data["stuk"].get("id") or ""))):
            stukken.add(vp.id)
    genoemd = genoemd_extern(answer_text)
    gevraagd = genoemd_extern(vraag)
    return [s for s in sources
            if s.brontype in (None, "wettekst")
            # Een stuk van een connector telt alleen als het gelezen is; dat een gelezen stuk het noemt (een voetnoot,
            # `verwijst_naar`), maakt het geen bron (meting Staatsblad ronde 4, B12: Stcrt. 2021, 12238 en Stb. 2023, 381
            # en 408). Een id zonder connector (EHRM) staat er als het gelezen stuk het noemt en het antwoord ook.
            or (s.uri in genoemd and (s.uri in stukken or (van_id(s.uri) is None and s.uri in in_tekst)))
            or (s.uri in gevraagd | geciteerd and s.uri in stukken)
            # Wettekst van overheid.nl (`wettekst_live`) is wettekst, geen stuk naast de wet: gelezen is genoeg. Haar id
            # (`bwbt:…`) staat nooit in lopende tekst, dus de jurist zag "Klaar · 0 bronnen" (meting 11 nov 2026, W07/W12/W15).
            or (s.brontype == "wettekst_live" and s.uri in stukken)]


def live_niet_letterlijk(antwoord: dict[str, Any] | None, trace: list[tuple[str, str]]) -> tuple[bool, list[str]]:
    """De letterlijkheid van wettekst van overheid.nl in een sjabloon (het blok `extern` met brontype `wettekst_live`).

    Geeft (heeft zulke blokken, passages die niet letterlijk in een gelezen rij van dat stuk staan). Wettekst uit een
    sjabloon staat zonder aanhalingstekens, dus `check_grounding` ziet er "niets te controleren" in; deze toets legt elke
    passage naast de rijen die `get_wettekst` voor dat id teruggaf (meting 11 nov 2026: grounding `onbepaald` bij W07)."""
    blokken = [b for b in (antwoord or {}).get("blokken") or []
               if b.get("soort") == "extern" and b.get("brontype") == "wettekst_live"]
    if not blokken:
        return False, []
    gelezen: dict[str, set[str]] = {}
    for naam, tekst in trace:
        if naam != "get_wettekst" or not (data := is_contract(tekst)) or not isinstance(data.get("stuk"), dict):
            continue
        ident = str(data["stuk"].get("id") or "")
        gelezen.setdefault(ident, set()).update(
            str(r.get("tekst")) for r in data.get("resultaten") or [] if isinstance(r, dict) and r.get("tekst"))
    fout = [str(p.get("tekst") or "")[:200] for b in blokken for p in b.get("passages") or []
            if str(p.get("tekst") or "") not in gelezen.get(str(b.get("id") or ""), set())]
    return True, fout
