"""Bewijssterkte, afgeleid uit de regeldefinities (audit D06).

Welke bewijscode op zichzelf één klasse draagt, stond eerder als losse lijst in `besluit` en
`onzekerheid`, zonder sluitende relatie met de regels die de code uitgeven. Nu verklaart elke
regel zijn sterkte waar hij gedefinieerd is: in de regel-YAML (`bewijs:`) of als `BEWIJS` op een
codedetector. Een code is alleen sterk als **al** zijn regels sterk zijn en dezelfde ene klasse
aanwijzen; zo kan een zwakke regel met dezelfde code een sterke niet stil verdunnen.

Klassenniveau (`deterministic_detection_possible` in een profiel) is iets anders dan regelbewijs
(audit H8); de enige harde koppeling is dat een klasse met `laag` geen sterke code heeft.
"""
from __future__ import annotations

from functools import cache


@cache
def _per_code() -> dict[str, set[tuple[str, str]]]:
    from .detectoren import standaard_detectoren
    from .detectoren.regels import alle_regels
    per: dict[str, set[tuple[str, str]]] = {}
    for r in alle_regels():
        per.setdefault(r.code, set()).add((r.bewijs, r.klassen[0] if r.bewijs == "sterk" else ""))
    for d in standaard_detectoren():
        for code, (sterkte, klasse) in getattr(d, "BEWIJS", {}).items():
            per.setdefault(code, set()).add((sterkte, klasse))
    return per


@cache
def klasse_van_bewijs() -> dict[str, str]:
    uit = {}
    for code, sterktes in _per_code().items():
        if {s for s, _ in sterktes} == {"sterk"} and len({k for _, k in sterktes}) == 1:
            uit[code] = next(iter(sterktes))[1]
    return uit


@cache
def generiek_bewijs() -> frozenset[str]:
    return frozenset(c for c, sterktes in _per_code().items() if {s for s, _ in sterktes} == {"generiek"})
