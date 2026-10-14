"""Het patroonregister voor begripsrelaties (ADR-004): kwalificatie, inclusie, uitsluiting, hiërarchie.

De patronen staan in `regels/*.yaml`, in de vorm van de JAS-regels (`jas_pipeline/detectoren/
regels/`): id, code, bron, versie, patroon en vier verplichte testsoorten. Het verschil: een
begripspatroon verbindt twee termen, via de benoemde groepen `van` en `naar`.

Een gevangen woord wordt een formulering zo:

1. een formulering in dezelfde bron die het woord omvat en het als kern heeft;
2. anders: de wettelijke term met die naam, als de bron binnen haar bereik valt (zo wordt
   "belastingaanslag" in "met een belastingaanslag gelijkgestelde beschikking" de definitie in
   art. 2, ook al is het woord hier geen eigen formulering).

Lukt dat voor een van beide kanten niet, dan vervalt de treffer: een relatie met maar één kant is
geen relatie.

Daarnaast het **kopsignaal**: is de kop van een samenstelling elders een eigen kern
("navorderingsaanslag" – "aanslag"), dan is dat zwak bewijs voor een hiërarchie. Zwak, omdat de
wet het anders kan regelen: in de Invorderingswet is "de aanslag" een zuster van de
navorderingsaanslag, niet de bovenliggende soort.

Een los "in afwijking van" is hier bewust **geen** tegenbewijs: het wijkt meestal af van een
norm (een andere termijn), niet van de betekenis van een term. De definitionele afwijking ("in
afwijking … geldt … als X") staat in `signalen.afwijkende_kwalificatie`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from .definities import WettelijkeTerm, wettelijke_termen
from .model import Bewijs, Hypothese, Manifest, Polariteit, Sterkte, Taalanalyse
from .signalen import Signaal

MAP = Path(__file__).parent / "regels"
VERSIE = "1"
VELDEN = {"id", "hypothese", "code", "polariteit", "sterkte", "bron", "versie", "patroon", "tests"}
TESTSOORTEN = ("positief", "negatief", "rand", "overlap")
_MACRO = {"LW": r"(?:de|het|een|die|deze|dat|dit)"}


@dataclass(frozen=True)
class Regel:
    id: str
    hypothese: Hypothese
    code: str
    polariteit: Polariteit
    sterkte: Sterkte
    bron: str
    versie: int
    patroon: re.Pattern
    tests: dict[str, list[dict[str, Any]]] = field(default_factory=dict, compare=False)


def _compileer(patroon: str) -> re.Pattern:
    def vervang(m: re.Match) -> str:
        if m.group(1) not in _MACRO:
            raise ValueError(f"onbekende macro {{{m.group(1)}}}")
        return _MACRO[m.group(1)]
    p = re.compile(re.sub(r"\{([A-Z]+)\}", vervang, patroon), re.IGNORECASE)
    if {"van", "naar"} - set(p.groupindex):
        raise ValueError("een begripspatroon heeft de groepen 'van' en 'naar'")
    return p


def _regel(d: dict[str, Any]) -> Regel:
    if set(d) != VELDEN:
        raise ValueError(f"{d.get('id', '?')}: velden {sorted(d)} ≠ {sorted(VELDEN)}")
    if not re.fullmatch(r"begrip\.[a-z_]+\.[a-z_]+", d["id"]):
        raise ValueError(f"{d['id']}: id heeft de vorm begrip.<familie>.<naam>")
    ontbreekt = [s for s in TESTSOORTEN if not d["tests"].get(s)]
    if ontbreekt:
        raise ValueError(f"{d['id']}: ontbrekende tests {ontbreekt}")
    return Regel(d["id"], Hypothese(d["hypothese"]), d["code"], Polariteit(d["polariteit"]),
                 Sterkte(d["sterkte"]), d["bron"], int(d["versie"]), _compileer(d["patroon"]),
                 d["tests"])


@cache
def alle_regels() -> tuple[Regel, ...]:
    regels = [_regel(d) for pad in sorted(MAP.glob("*.yaml"))
              for d in yaml.safe_load(pad.read_text(encoding="utf-8"))]
    ids = [r.id for r in regels]
    if len(set(ids)) != len(ids):
        raise ValueError("dubbel regel-id in het begrippenregister")
    return tuple(regels)


def _b(code: str, pol: Polariteit, sterkte: Sterkte, regel: str, versie: str, fragment: str,
       bron_iri: str) -> Bewijs:
    return Bewijs(code=code, polariteit=pol, sterkte=sterkte, regel=regel, versie=versie,
                  fragment=fragment, bron_iri=bron_iri)


def _formulering(manifest: Manifest, taal: dict[str, Taalanalyse], wts: list[WettelijkeTerm],
                 bron_iri: str, start: int, eind: int, woord: str) -> str:
    w = woord.lower()
    omvattend = sorted((f for f in manifest.formuleringen
                        if f.bron_iri == bron_iri and f.start <= start and f.eind >= eind
                        and w in (taal[f.element_id].kern, taal[f.element_id].kernvorm.lower())),
                       key=lambda f: f.eind - f.start)
    if omvattend:
        return omvattend[0].element_id
    for t in wts:
        if t.term == w and t.anker and t.bereik.omvat(bron_iri):
            return t.anker
    return ""


def toepassen(manifest: Manifest, taal: dict[str, Taalanalyse],
              wts: list[WettelijkeTerm] | None = None) -> list[Signaal]:
    wts = wettelijke_termen(manifest, taal) if wts is None else wts
    uit: list[Signaal] = []
    for bron in manifest.bronnen:
        for r in alle_regels():
            for m in r.patroon.finditer(bron.tekst):
                van = _formulering(manifest, taal, wts, bron.bron_iri, *m.span("van"), m.group("van"))
                naar = _formulering(manifest, taal, wts, bron.bron_iri, *m.span("naar"), m.group("naar"))
                if not van or not naar or van == naar:
                    continue
                uit.append(Signaal(r.hypothese, van, naar, _b(
                    r.code, r.polariteit, r.sterkte, r.id, str(r.versie), m.group(0), bron.bron_iri)))
                if r.hypothese is Hypothese.UITSLUITING:
                    a, b = sorted((van, naar))
                    uit.append(Signaal(Hypothese.ZELFDE_BETEKENIS, a, b, _b(
                        "NIET_VERSTAAN", Polariteit.TEGEN, Sterkte.STERK, r.id, str(r.versie),
                        m.group(0), bron.bron_iri)))
    return uit


def kopsignalen(manifest: Manifest, taal: dict[str, Taalanalyse]) -> list[Signaal]:
    """Kop van een samenstelling die elders een eigen kern is: zwak bewijs voor een hiërarchie."""
    kernen: dict[str, list[str]] = {}
    for f in manifest.formuleringen:
        t = taal[f.element_id]
        if not t.beperkt:
            kernen.setdefault(t.term, []).append(f.element_id)
    uit = []
    for f in manifest.formuleringen:
        t = taal[f.element_id]
        for boven in sorted(kernen.get(t.kop, [])) if t.kop else []:
            uit.append(Signaal(Hypothese.HIERARCHIE, boven, f.element_id, _b(
                "KOP_VAN_SAMENSTELLING", Polariteit.STEUN, Sterkte.ZWAK,
                "begrip.hierarchie.kop_samenstelling", VERSIE, f"{t.kern} → {t.kop}", f.bron_iri)))
    return uit
