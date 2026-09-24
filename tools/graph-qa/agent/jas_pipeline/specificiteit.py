"""Specificiteitsregels van JAS over kandidaten heen (ADR-001 PR 8, opdracht §12).

JAS kiest bij samenloop de meest specifieke klasse: een formulering die tijdsaanduiding én
variabele of parameter kan zijn, is een Tijdsaanduiding (H2:107); voor een plaats geldt hetzelfde
(H2:116). Die regels staan als `JAS-PRIORITY-001/002` in `jas_klassen.REGELS`.

In de legacy-keten werkten ze alleen binnen één element (klasse tegen alternatieven). Een los
Parameter-element op "zes weken" náást een Tijdsaanduiding op "zes weken na de dagtekening …"
bleef daardoor staan – de IW01-bevinding. Hier gelden ze ook voor **geneste spans met dezelfde
functie**:

- een kandidaat met zowel de winnende als een verliezende klasse verliest de verliezende;
- een kandidaat die binnen een winnende kandidaat ligt en zelf die functie heeft (bewijs met de
  functiecode, of zijn span is de kern van de winnaar) verliest de verliezende klassen ook.

Houdt een kandidaat dan geen klasse over, dan wordt hij `REJECTED` – met de regel als bewijs, zodat
de dekkingsboekhouding en de provenance zeggen waarom. Er verdwijnt niets stil.

"Dezelfde functie" is hier bewust smal: alleen wat de detectoren als tijd of plaats herkenden.
Een getal dat toevallig binnen een termijn staat maar een bedrag is, valt er niet onder.
"""
from __future__ import annotations

from ..jas_klassen import REGELS, RegelType
from .kandidaten import Candidate, CandidateStatus, Evidence

# Welke bewijscode "dezelfde functie" als de winnende klasse aanduidt. Nieuwe PRIORITY-regel →
# hier de functiecode bij, anders geldt hij alleen binnen één kandidaat (en faalt de test).
FUNCTIECODES = {"Tijdsaanduiding": "TEMPORAL_", "Plaatsaanduiding": "LOCATION_"}


def _prioriteitsregels():
    for r in REGELS:
        if r.type is RegelType.PRIORITEIT:
            rang = dict(r.priority)
            winnaar = max(rang, key=rang.get)
            yield r.id, winnaar, tuple(k for k in r.applies_to if k != winnaar)


def _heeft_functie(k: Candidate, winnaar: str) -> bool:
    return any(e.code.startswith(FUNCTIECODES[winnaar]) for e in k.evidence)


def _pas_regel_toe(k: Candidate, regel: str, verliezers: tuple[str, ...], waarom: str) -> Candidate:
    weg = tuple(c for c in k.possible_classes if c in verliezers)
    if not weg:
        return k
    over = tuple(c for c in k.possible_classes if c not in verliezers)
    bewijs = Evidence(detector="specificiteit", code="PRIORITY_APPLIED", regel=regel,
                      detail=f"{waarom}; vervalt: {', '.join(weg)}")
    if over:
        return k.model_copy(update={"possible_classes": over, "evidence": (*k.evidence, bewijs)})
    return k.model_copy(update={"status": CandidateStatus.REJECTED, "evidence": (*k.evidence, bewijs)})


def pas_toe(kandidaten: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    uit = list(kandidaten)
    for regel, winnaar, verliezers in _prioriteitsregels():
        if winnaar not in FUNCTIECODES:
            raise ValueError(f"{regel}: geen functiecode voor {winnaar} in FUNCTIECODES")
        winnaars = [k for k in uit if winnaar in k.possible_classes and _heeft_functie(k, winnaar)]
        for i, k in enumerate(uit):
            if winnaar in k.possible_classes:
                uit[i] = _pas_regel_toe(k, regel, verliezers, f"{winnaar} op dezelfde span")
                continue
            for w in winnaars:
                binnen = (w.span.bron_iri == k.span.bron_iri and w.span.start <= k.span.start
                          and k.span.eind <= w.span.eind and w.id != k.id)
                kern_van_w = any(o.soort == "kern" and o.span.sleutel() == k.span.sleutel() for o in w.span_options)
                if binnen and (_heeft_functie(k, winnaar) or kern_van_w):
                    uit[i] = _pas_regel_toe(k, regel, verliezers, f"binnen {winnaar} {w.span.tekst!r}")
                    break
    return tuple(uit)
