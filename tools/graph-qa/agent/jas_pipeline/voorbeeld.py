"""Rekenvoorbeelden in de bron (plan-lessen-termijnen-bibliotheek V8/M2; skill `references/markeringslijst.md`).

Een beleidsregel rekent een regel soms voor: "valt de dagtekening op 31 oktober, dan vervalt de termijn op 30
november". Zo'n zin is geen norm, maar wel bron. De skill zegt wat dat voor de markering betekent:

- de concrete data en bedragen in het voorbeeld markeer je niet los;
- de woorden die een kenmerk aanduiden dat een regel nodig heeft (het jaartal, de laatste dag van de maand), markeer
  je wel: vaak is het voorbeeld de enige plek waar de tekst ze noemt;
- het voorbeeld stelt geen nieuwe regel.

Deze stap herkent de voorbeeldzin zonder model en past dat toe op de kandidaten van de fusie, vóór de deterministische
besluiten. De kennis staat hier en in de tests, niet in een prompt (ADR-001). Wat de stap doet, staat als bewijs op
de kandidaat; er verdwijnt niets stil:

- `VOORBEELD_WAARDE`: een concrete waarde in het voorbeeld (een kalenderdatum of een bedrag) wordt `REJECTED`. Een
  duur ("zes weken") valt er bewust niet onder: in een voorbeeld noemt die de parameter zelf ("de betalingstermijn van
  zes weken"), niet een uitkomst;
- `VOORBEELD_GEEN_NORM`: de klassen die een norm dragen (afleidingsregel, voorwaarde, rechtsbetrekking, rechtsfeit)
  vallen weg; blijft er niets over, dan `REJECTED`;
- `IN_VOORBEELD`: wat overblijft, krijgt dit kenmerk. Het zegt niets over de klasse (`besluit` telt het niet als
  bewijs), maar de classifier en de reviewer zien het als signaal en de jurist in de toelichting.

**Wanneer is een zin een voorbeeld?** Twee generieke signalen, elk met een concrete waarde (een kalenderdatum of een
bedrag) als uitkomst; een duur alleen telt niet, want die staat ook in elke termijnnorm:

1. *een inleiding*: "bijvoorbeeld", "ter illustratie", "stel dat", "dus", of een conclusie als "dan houdt dat in
   dat" en "dat betekent dat", met een concrete waarde als gegeven ná de inleiding (een grens telt niet, zie hieronder). Bij een
   conclusie begint het voorbeeld bij de inleiding: wat ervoor staat, is vaak de regel die het voorbeeld uitwerkt;
2. *een uitkomst uit een concreet geval*: een voorwaardelijke zin ("als …, dan …", of met de persoonsvorm voorop: "is
   de dagtekening …, vervalt …") waarvan de voorwaarde een kalenderdatum als gegeven noemt en de hoofdzin een
   kalenderdatum als uitkomst. Met een bedrag is zo'n zin even vaak een norm met een drempel; die telt alleen met een
   inleiding. Een datum als grens in de voorwaarde ("vóór 1 april", "met ingang van") is geen
   gegeven: zo schrijft een overgangsregeling een norm.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from .detectoren.regels import woordenlijsten
from .kandidaten import Candidate, CandidateStatus, Evidence

VERSIE = "1"

#: De klassen die een norm dragen. Een voorbeeld stelt geen regel (skill, markeringslijst).
NORMKLASSEN = ("Afleidingsregel", "Voorwaarde", "Rechtsbetrekking", "Rechtsfeit")

CODE_IN = "IN_VOORBEELD"
CODE_WAARDE = "VOORBEELD_WAARDE"
CODE_GEEN_NORM = "VOORBEELD_GEEN_NORM"
REGEL_WAARDE = "jas.voorbeeld.waarde"
REGEL_GEEN_NORM = "jas.voorbeeld.geen_norm"
REGEL_KENMERK = "jas.voorbeeld.kenmerk"
#: De codes waarmee deze stap een kandidaat afwijst; `besluit.deterministisch` leest er de regel uit.
AFWIJZINGSCODES = frozenset({CODE_WAARDE, CODE_GEEN_NORM})

_W = woordenlijsten()
_DATUM = rf"\b\d{{1,2}}\s+(?:{_W['MAAND']})(?:\s+\d{{4}}(?!\d))?\b"
_BEDRAG = r"(?:€\s?\d[\d.]*(?:,(?:\d{1,2}|-))?|\b\d[\d.]*(?:,\d{1,2})?\s+euro\b)"
_CONCREET = re.compile(rf"{_DATUM}|{_BEDRAG}", re.IGNORECASE)
_KALENDERDATUM = re.compile(_DATUM, re.IGNORECASE)
# Een datum die een grens is, geen gegeven: vóór 1 april, met ingang van 1 januari.
_GRENS = re.compile(r"(?:\b(?:vóór|voor|na|vanaf|sinds|tot(?:\s+en\s+met)?|met\s+ingang\s+van|uiterlijk(?:\s+op)?"
                    r"|tussen|per)\s+)$", re.IGNORECASE)

# Een inleiding die het hele zinsdeel tot voorbeeld maakt, en een conclusie waar het voorbeeld begint.
_INLEIDING = re.compile(r"\b(?:bijvoorbeeld|ter\s+illustratie|bij\s+wijze\s+van\s+voorbeeld|stel\s+dat|dus)\b"
                        r"|^\s*(?:voorbeeld\s*\d*\s*[:.]|stel\b)", re.IGNORECASE)
_CONCLUSIE = re.compile(r"\b(?:(?:dan|dit|dat)\s+)?(?:houdt\s+(?:dat|dit|het)\s+in|betekent(?:\s+(?:dat|dit|het))?)\s+dat\b"
                        r"|\bdat\s+wil\s+zeggen\b", re.IGNORECASE)
_VOORWAARDE_BEGIN = re.compile(r"^\s*(?:als|indien|wanneer|ingeval|in\s+geval|in\s+het\s+geval\s+dat|zodra)\b",
                               re.IGNORECASE)
# De persoonsvorm voorop (inversie), zonder parser: de werkwoorden waarmee een geval wordt gesteld.
_INVERSIE = re.compile(r"^\s*(?:is|zijn|valt|vallen|bedraagt|bedragen|ligt|wordt|heeft|hebben|eindigt|begint)\b",
                       re.IGNORECASE)

# Een concrete waarde als hele kandidaat, eventueel met een voorzetsel of lidwoord ervoor.
_VOOR = r"(?:(?:op|per|van|tot|vóór|voor|na|met|in|de|het|een|tot\s+en\s+met|te|ten\s+bedrage\s+van)\s+)*"
_WAARDE = re.compile(rf"^\s*{_VOOR}(?:{_DATUM}|{_BEDRAG})\s*[.,;]?\s*$",
                     re.IGNORECASE)


@dataclass(frozen=True)
class Voorbeeld:
    """Een stuk van één bronnode dat een voorbeeld is: [start, eind) en het signaal dat het herkende."""

    bron_iri: str
    start: int
    eind: int
    signaal: str          # "inleiding", "conclusie" of "uitkomst"


def _zinnen(tekst: str, analyse=None) -> list[tuple[int, int]]:
    if analyse is not None and getattr(analyse, "zinnen", None) and not getattr(analyse, "gedegradeerd", False):
        return [(z.start, z.eind) for z in analyse.zinnen]
    uit, start = [], 0
    for m in re.finditer(r"(?<=[.;!?])\s+(?=[A-ZÀ-Ý])", tekst):
        uit.append((start, m.start()))
        start = m.end()
    if start < len(tekst):
        uit.append((start, len(tekst)))
    return uit


def _gegevens(tekst: str, patroon: re.Pattern = _CONCREET) -> list[re.Match]:
    """De concrete waarden die als gegeven staan, niet als grens."""
    return [m for m in patroon.finditer(tekst) if not _GRENS.search(tekst[:m.start()])]


def _uitkomst(zin: str) -> bool:
    """Een voorwaardelijke zin met een kalenderdatum als gegeven én een als uitkomst. Een bedrag telt hier niet: "is de
    schuld lager dan € 20, dan …" is een drempel in een norm (Awir art. 7 lid 3), en een bedrag als uitkomst ook."""
    if not (_VOORWAARDE_BEGIN.match(zin) or _INVERSIE.match(zin)):
        return False
    komma = zin.find(",")
    if komma < 0:
        return False
    voorwaarde, hoofdzin = zin[:komma], zin[komma + 1:]
    return bool(_gegevens(voorwaarde, _KALENDERDATUM)) and bool(_KALENDERDATUM.search(hoofdzin))


def herken(bron_iri: str, tekst: str, analyse=None) -> list[Voorbeeld]:
    """De voorbeelden in de tekst van één bronnode, in tekstvolgorde."""
    uit = []
    for s, e in _zinnen(tekst, analyse):
        zin = tekst[s:e]
        if not _CONCREET.search(zin):
            continue
        conclusie = _CONCLUSIE.search(zin)
        if conclusie and _gegevens(zin[conclusie.start():]):
            uit.append(Voorbeeld(bron_iri, s + conclusie.start(), e, "conclusie"))
        elif (inleiding := _INLEIDING.search(zin)) and _gegevens(zin[inleiding.start():]):
            uit.append(Voorbeeld(bron_iri, s, e, "inleiding"))
        elif _uitkomst(zin):
            uit.append(Voorbeeld(bron_iri, s, e, "uitkomst"))
    return uit


def is_waarde(tekst: str) -> bool:
    """Is dit fragment alleen een concrete waarde: een kalenderdatum of een bedrag, eventueel met een voorzetsel?"""
    return bool(_WAARDE.match(tekst))


def _plek(v: Voorbeeld, detail: str = "") -> str:
    return f"{v.signaal} [{v.start}:{v.eind}]" + (f"; {detail}" if detail else "")


def pas_toe(kandidaten: Iterable[Candidate], voorbeelden: Iterable[Voorbeeld]) -> tuple[Candidate, ...]:
    """Pas de regel van het rekenvoorbeeld toe op elke kandidaat die helemaal binnen een voorbeeld ligt."""
    per_bron: dict[str, list[Voorbeeld]] = {}
    for v in voorbeelden:
        per_bron.setdefault(v.bron_iri, []).append(v)
    uit = []
    for k in kandidaten:
        v = next((v for v in per_bron.get(k.span.bron_iri, ())
                  if v.start <= k.span.start and k.span.eind <= v.eind), None)
        if v is None or k.status is CandidateStatus.REJECTED:
            uit.append(k)
            continue
        if is_waarde(k.span.tekst):
            bewijs = Evidence(detector="voorbeeld", code="VOORBEELD_WAARDE", regel=REGEL_WAARDE, detail=_plek(v))
            uit.append(k.model_copy(update={"status": CandidateStatus.REJECTED, "evidence": (*k.evidence, bewijs)}))
            continue
        weg = tuple(c for c in k.possible_classes if c in NORMKLASSEN)
        over = tuple(c for c in k.possible_classes if c not in NORMKLASSEN)
        geen_norm = (Evidence(detector="voorbeeld", code="VOORBEELD_GEEN_NORM", regel=REGEL_GEEN_NORM,
                              detail=_plek(v, f"vervalt: {', '.join(weg)}")),) if weg else ()
        if weg and not over:
            uit.append(k.model_copy(update={"status": CandidateStatus.REJECTED, "evidence": (*k.evidence, *geen_norm)}))
            continue
        kenmerk = Evidence(detector="voorbeeld", code="IN_VOORBEELD", regel=REGEL_KENMERK, detail=_plek(v))
        uit.append(k.model_copy(update={"possible_classes": over, "evidence": (*k.evidence, kenmerk, *geen_norm)}))
    return tuple(uit)


def op_fusie(fusie, teksten) -> tuple:
    """De stap in de keten: (de fusie met de regel toegepast, de meting), of (dezelfde fusie, None) zonder voorbeeld."""
    voorbeelden = [v for t in teksten for v in herken(t.bron_iri, t.tekst, t.analyse)]
    if not voorbeelden:
        return fusie, None
    kandidaten = pas_toe(fusie.kandidaten, voorbeelden)
    afgewezen = sum(k.status is CandidateStatus.REJECTED and any(e.code in AFWIJZINGSCODES for e in k.evidence)
                    for k in kandidaten)
    return (fusie.model_copy(update={"kandidaten": kandidaten}),
            {"versie": VERSIE, "aantal": len(voorbeelden), "afgewezen": afgewezen})
