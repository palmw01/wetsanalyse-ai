"""Declaratieve regeldetectoren: één YAML per detectorfamilie, één regel per patroon.

Schema van een regel (zie `regels/*.yaml`):

    id:         jas.<familie>.<naam>, uniek; verwijst naar `candidate_rules` in het detectieprofiel
    klassen:    mogelijke JAS-klassen (volgorde = voorkeur, geen beslissing)
    code:       bewijscode, bv. TEMPORAL_DURATION
    bron:       waar het patroon vandaan komt: "H2:109", of "adr-001:…" voor een projectregel
    versie:     int; ophogen bij elke gedragswijziging
    patroon:    regex voor de kern; {NAAM} verwijst naar een woordenlijst uit _woordenlijsten.yaml
    links:      optioneel; regex die direct vóór de kern moet eindigen ('$' wordt toegevoegd)
    rechts:     optioneel; regex die direct na de kern moet beginnen
    niet_binnen: maskers waarbinnen de regel niet vuurt (default: [verwijzing])
    tests:      positief / negatief / rand / overlap – verplicht, zie tests/test_detectoren.py

Een uitbreiding naar links of rechts maakt de kandidaatspan niet vanzelf langer: de kern en elke
uitbreiding worden spanopties, en de kandidaat krijgt de langste. Welke grens juridisch juist is
('zes weken' of 'zes weken na de dagtekening …') is een latere keuze uit die opties – nooit tekst
die een model zelf typt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from ...jas_klassen import GELDIGE_JAS_KLASSEN
from ..kandidaten import BronSpan, Candidate, DetectorResult, Evidence, SpanOption
from . import BronTekst

MAP = Path(__file__).parent / "regels"
_MACRO = re.compile(r"\{([A-Z_]+)\}")
_RAND = " \t\n,:"      # een zinseinde (. en ;) hoort bij de span als het patroon het meeneemt


@cache
def woordenlijsten() -> dict[str, str]:
    lijsten = yaml.safe_load((MAP / "_woordenlijsten.yaml").read_text(encoding="utf-8"))
    return {naam: "|".join(sorted((re.escape(w) if not w.startswith("re:") else w[3:] for w in woorden),
                                  key=len, reverse=True))
            for naam, woorden in lijsten.items()}


def _vul_in(patroon: str) -> str:
    lijsten = woordenlijsten()

    def vervang(m: re.Match) -> str:
        if m.group(1) not in lijsten:
            raise ValueError(f"onbekende woordenlijst {{{m.group(1)}}}")
        return f"(?:{lijsten[m.group(1)]})"
    return _MACRO.sub(vervang, patroon)


@dataclass(frozen=True)
class Regel:
    id: str
    detector: str
    klassen: tuple[str, ...]
    code: str
    bron: str
    versie: int
    kern: re.Pattern
    links: re.Pattern | None = None
    rechts: re.Pattern | None = None
    niet_binnen: tuple[str, ...] = ("verwijzing",)
    tests: dict[str, list[dict[str, Any]]] = field(default_factory=dict, compare=False)

    @classmethod
    def van(cls, detector: str, d: dict[str, Any]) -> Regel:
        onbekend = [k for k in d.get("klassen", []) if k not in GELDIGE_JAS_KLASSEN]
        if onbekend or not d.get("klassen"):
            raise ValueError(f"{d.get('id')}: ongeldige klassen {onbekend or '(leeg)'}")
        if not str(d.get("id", "")).startswith("jas."):
            raise ValueError(f"{d.get('id')}: id moet met 'jas.' beginnen")
        vlag = re.IGNORECASE if d.get("hoofdletterongevoelig", True) else 0

        def comp(p: str | None, suffix: str = "") -> re.Pattern | None:
            return re.compile(_vul_in(p) + suffix, vlag) if p else None
        return cls(d["id"], detector, tuple(d["klassen"]), d["code"], d["bron"], int(d["versie"]),
                   comp(d["patroon"]), comp(d.get("links"), "$"), comp(d.get("rechts")),
                   tuple(d.get("niet_binnen", ["verwijzing"])), d.get("tests", {}))

    def vind(self, tekst: str) -> list[list[tuple[int, int]]]:
        """Per treffer de mogelijke grenzen: kern, links+kern, kern+rechts, links+kern+rechts."""
        uit = []
        for m in self.kern.finditer(tekst):
            s, e = _trim(tekst, *m.span())
            if s >= e:
                continue
            ls = s
            if self.links and (lm := self.links.search(tekst, 0, s)):
                ls = lm.start()
            re_ = e
            if self.rechts and (rm := self.rechts.match(tekst, e)):
                re_ = _trim(tekst, e, rm.end())[1]
            uit.append(sorted({(s, e), (ls, e), (s, re_), (ls, re_)}, key=lambda g: g[1] - g[0]))
        return uit


def _trim(tekst: str, s: int, e: int) -> tuple[int, int]:
    while s < e and tekst[s] in _RAND:
        s += 1
    while e > s and tekst[e - 1] in _RAND:
        e -= 1
    return s, e


@dataclass(frozen=True)
class Masker:
    """Een negatief patroon: bereiken waarbinnen een regel niet mag vuren. Geen JAS-kandidaat."""

    id: str
    masker: str               # naam waarnaar `niet_binnen` verwijst, bv. "verwijzing"
    bron: str
    patroon: re.Pattern
    tests: dict[str, list[dict[str, Any]]] = field(default_factory=dict, compare=False)


@cache
def maskerregels() -> tuple[Masker, ...]:
    d = yaml.safe_load((MAP / "_maskers.yaml").read_text(encoding="utf-8"))
    return tuple(Masker(m["id"], m["masker"], m["bron"], re.compile(_vul_in(m["patroon"]), re.IGNORECASE),
                        m.get("tests", {})) for m in d)


def maskers(tekst: str) -> dict[str, list[tuple[int, int]]]:
    """Per maskernaam de bereiken in de tekst (bv. 'verwijzing' → [(12, 30), …])."""
    uit: dict[str, list[tuple[int, int]]] = {}
    for m in maskerregels():
        for treffer in m.patroon.finditer(tekst):
            uit.setdefault(m.masker, []).append(_trim(tekst, *treffer.span()))
    return uit


def _binnen(grens: tuple[int, int], bereiken: list[tuple[int, int]]) -> bool:
    s, e = grens
    return any(ms <= s and e <= me for ms, me in bereiken)


class RegelDetector:
    """Alle regels van één familie (één YAML-bestand)."""

    def __init__(self, naam: str, regels: tuple[Regel, ...]):
        self.naam = naam
        self.regels = regels
        self.versie = ".".join(str(r.versie) for r in regels)

    def detecteer(self, bron: BronTekst) -> DetectorResult:
        masker = maskers(bron.tekst)
        kandidaten: dict[str, Candidate] = {}
        for regel in self.regels:
            weg = [b for naam in regel.niet_binnen for b in masker.get(naam, [])]
            for grenzen in regel.vind(bron.tekst):
                if _binnen(grenzen[0], weg):
                    continue
                langste = grenzen[-1]
                opties = [SpanOption(soort="regel" if g != grenzen[0] else "kern",
                                     span=BronSpan.van(bron.span(*g))) for g in grenzen if g != langste]
                bewijs = Evidence(detector=self.naam, code=regel.code, regel=regel.id,
                                  detail=bron.tekst[grenzen[0][0]:grenzen[0][1]])
                k = Candidate.maak(bron.span(*langste), regel.klassen, [bewijs], opties)
                if k.id in kandidaten:           # zelfde span via twee regels: bewijs samenvoegen
                    oud = kandidaten[k.id]
                    k = oud.model_copy(update={
                        "possible_classes": tuple(dict.fromkeys((*oud.possible_classes, *k.possible_classes))),
                        "evidence": (*oud.evidence, bewijs),
                        "span_options": tuple(dict.fromkeys((*oud.span_options, *opties)))})
                kandidaten[k.id] = k
        return DetectorResult(detector=self.naam, versie=self.versie, bron_iri=bron.bron_iri,
                              kandidaten=tuple(kandidaten.values()))


@cache
def alle_regels() -> tuple[Regel, ...]:
    regels = []
    for pad in sorted(MAP.glob("[!_]*.yaml")):
        for d in yaml.safe_load(pad.read_text(encoding="utf-8")):
            regels.append(Regel.van(pad.stem, d))
    ids = [r.id for r in regels]
    if len(ids) != len(set(ids)):
        raise ValueError("dubbele regel-id's")
    return tuple(regels)


def regeldetectoren() -> list[RegelDetector]:
    per: dict[str, list[Regel]] = {}
    for r in alle_regels():
        per.setdefault(r.detector, []).append(r)
    return [RegelDetector(naam, tuple(rs)) for naam, rs in per.items()]
