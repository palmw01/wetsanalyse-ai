"""Deterministische grenzen in oorspronkelijke codepoints, los van parserdependencies.

Een segment eindigt ook op `;` of `:`, een zin niet. Een gewone regelovergang
kan tekstomloop zijn; alleen een lege regel is hier een grens. Herkende notaties
beschermen hun interne leestekens, niet de interpunctie die erna staat.
"""
from dataclasses import dataclass
import re

from .verwijzingen import verwijzingen

VERSIE = "1"


@dataclass(frozen=True, slots=True)
class Bereik:
    start: int
    eind: int
    reden: str


@dataclass(frozen=True, slots=True)
class Grens:
    positie: int
    reden: str


@dataclass(frozen=True, slots=True)
class TekstGrenzen:
    beschermd: tuple[Bereik, ...]
    zinsgrenzen: tuple[Grens, ...]
    segmentgrenzen: tuple[Grens, ...]

    def zinnen(self, tekst: str) -> tuple[Bereik, ...]:
        return _bereiken(tekst, self.zinsgrenzen)

    def segmenten(self, tekst: str) -> tuple[Bereik, ...]:
        return _bereiken(tekst, self.segmentgrenzen)


def _bereiken(tekst: str, grenzen: tuple[Grens, ...]) -> tuple[Bereik, ...]:
    uit, begin = [], 0
    for grens in grenzen:
        s, e = begin, grens.positie
        while s < e and tekst[s].isspace():
            s += 1
        while e > s and tekst[e - 1].isspace():
            e -= 1
        if s < e:
            uit.append(Bereik(s, e, grens.reden))
        begin = grens.positie
    return tuple(uit)


_NUMERIEK = re.compile(r"(?<!\w)\d+(?:[.,:]\d+)+(?!\w)")
_AFKORTING = re.compile(r"\b(?:artt?|nr|jo|bijv|resp|enz|etc|d\.w\.z|o\.a|m\.a\.w|t\.a\.v|mr|dr|prof)\.", re.I)
_LABEL = re.compile(r"(?<!\S)(?:[a-z]{1,3}|\d+[a-z]?|[IVXLCDM]+)°?\.(?=\s+\S)")


def onderdeel_labels(tekst: str) -> tuple[Bereik, ...]:
    """Nummering bij bronstart, regelstart of na opsommingsinterpunctie.

    `artikel 4.` midden in een zin is hierdoor nooit een onderdeelnummer.
    """
    uit = []
    for m in _LABEL.finditer(tekst):
        prefix = tekst[:m.start()]
        if not prefix.strip() or re.search(r"[;:\n][ \t\r]*$", prefix):
            uit.append(Bereik(m.start(), m.end(), "onderdeelnummer"))
    return tuple(uit)


def analyseer_grenzen(tekst: str) -> TekstGrenzen:
    beschermd = [Bereik(s, e, f"verwijzing:{naam}") for s, e, naam in verwijzingen(tekst)]
    beschermd += [Bereik(m.start(), m.end(), "numeriek") for m in _NUMERIEK.finditer(tekst)]
    beschermd += list(onderdeel_labels(tekst))
    for m in _AFKORTING.finditer(tekst):
        rest = tekst[m.end():].lstrip()
        # Een afkorting kan tevens een zin afsluiten ("enz. Daarna ...").
        # Titels vóór een eigennaam blijven wel beschermd.
        doorlopend = bool(rest) and (not rest[0].isupper() or m.group().lower() in {"mr.", "dr.", "prof."})
        eind = m.end() if doorlopend else m.end() - 1
        if eind > m.start():
            beschermd.append(Bereik(m.start(), eind, "afkorting"))
    beschermd = tuple(sorted(set(beschermd), key=lambda b: (b.start, b.eind, b.reden)))
    zinnen, segmenten = {}, {}
    for m in re.finditer(r"[.;:!?]", tekst):
        if any(b.start <= m.start() < b.eind for b in beschermd):
            continue
        segmenten[m.end()] = Grens(m.end(), f"leesteken:{m.group()}")
        if m.group() in ".!?":
            zinnen[m.end()] = segmenten[m.end()]
    for m in re.finditer(r"\r?\n[ \t\r]*\n", tekst):
        zinnen[m.end()] = segmenten[m.end()] = Grens(m.end(), "alinea")
    zinnen.setdefault(len(tekst), Grens(len(tekst), "broneinde"))
    segmenten.setdefault(len(tekst), Grens(len(tekst), "broneinde"))
    return TekstGrenzen(beschermd, tuple(zinnen[k] for k in sorted(zinnen)),
                       tuple(segmenten[k] for k in sorted(segmenten)))
