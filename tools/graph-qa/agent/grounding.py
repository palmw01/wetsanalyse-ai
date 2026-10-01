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

import re
from dataclasses import dataclass, field

from .annotatie import komt_letterlijk_voor
from .models import Source
from .provenance import _BWB_RE, citations_in, first_bwb
from .tools.annotatie_tools import ANNOTATIE_TOOL_NAMEN

# Citaten in de vormen die een model gebruikt: rechte en typografische dubbele aanhalingstekens.
# Enkele quotes blijven erbuiten – die staan in Nederlandse lopende tekst te vaak om iets anders
# (een aanhaling binnen een aanhaling, een apostrof) en zouden vals alarm geven.
_CITAAT_RE = re.compile(r'"([^"\n]{2,400})"' r"|“([^”\n]{2,400})”")

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
    # "gegrond" | "onbepaald" | "ongegrond" – fijner dan de bool, die voor het bestaande
    # event-contract blijft bestaan.
    niveau: str = "gegrond"


def _citaten(text: str) -> list[str]:
    """De passages die het antwoord als letterlijk citaat presenteert."""
    uit: list[str] = []
    for m in _CITAAT_RE.finditer(text or ""):
        passage = (m.group(1) or m.group(2) or "").strip()
        if len(passage.split()) >= _MIN_WOORDEN:
            uit.append(passage)
    return uit


def check_grounding(answer_text: str, source_trace: list[tuple[str, str]]) -> GroundingReport:
    """Markeer wat in het antwoord niet uit de trace te herleiden is: verwijzingen én citaten."""
    trace_text = "\n".join(t for name, t in source_trace if t and name not in ANNOTATIE_TOOL_NAMEN)
    # Exacte BWB-id's uit de trace (woordgrens via _BWB_RE), zodat een gehallucineerde prefix-id
    # (bv. BWBR0001 t.o.v. het opgehaalde BWBR00012345) niet vals als gegrond geldt.
    trace_bwbs = set(_BWB_RE.findall(trace_text))
    cited = citations_in(answer_text)
    unsupported: list[str] = []
    for c in cited:
        bwb = first_bwb(c)
        if bwb is not None:
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

    if unsupported:
        niveau = "ongegrond"
    elif not cited and not citaten:
        # Niets te controleren. Dat is geen bewijs van juistheid – zeg dat dan ook.
        niveau = "onbepaald"
    elif niet_letterlijk:
        niveau = "ongegrond"
    else:
        niveau = "gegrond"

    return GroundingReport(
        citaten=len(citaten),
        # `grounded` blijft de vraag "is er iets aangetroffen dat níét klopt": het bestaande
        # event-contract en de eval hangen eraan. Het onderscheid tussen "gecontroleerd en goed" en
        # "er viel niets te controleren" zit in `niveau`.
        grounded=not unsupported and not niet_letterlijk,
        cited=cited,
        unsupported=unsupported,
        niet_letterlijk=niet_letterlijk,
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
        return kept

    def blijft(s: Source) -> bool:
        loc = _locatie(s.uri)
        if loc is None or loc[0] not in geciteerd:
            return True
        return any(_op_pad(loc[1], pad) for pad in geciteerd[loc[0]])

    fijn = [s for s in kept if blijft(s)]
    return fijn or kept
