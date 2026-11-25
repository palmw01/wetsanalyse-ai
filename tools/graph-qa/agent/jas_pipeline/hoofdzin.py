"""De hoofdzin van een ALS→DAN-regel draagt geen eigen norm (plan-lessen-termijnen-bibliotheek, M2-vervolg).

"Als de dagtekening … valt op een andere dag …, vervalt de termijn …" is één afleidingsregel: de hele zin, met de
voorwaarde. Zo zegt de skill het: een afleidingsregel markeer je met werkwoord en voorwaarden (markeren-fragmentgrenzen),
en bij één normzin is de hele zin het dragende fragment (markeringslijst). De hoofdzin alleen ("vervalt de termijn …") is
het gevolg in die regel, geen tweede afleidingsregel en ook geen eigen rechtsbetrekking of rechtsfeit. Besluit eigenaar
25 nov 2026 ("alleen de hele zin"); de jurist wees de hoofdzin in Leidraad 9.5 af, en het model maakte er na het weghalen
van de Afleidingsregel een Rechtsfeit van (meting keten-rekenvoorbeelden-vervolg).

Herkend zonder model, na de fusie: een kandidaat-Afleidingsregel die eerder begint en de span van een andere kandidaat als
spanoptie `clause` aanbiedt (de GevolgDetector doet dat bij een voorwaarde vóór het gevolg). Die andere kandidaat verliest
de normklassen; blijft er niets over, dan wordt hij `REJECTED`. Het bewijs `HOOFDZIN_VAN_REGEL` staat op de kandidaat.
Wat de hoofdzin bevat (de termijn, de tijdsaanduiding, het rechtsobject) blijft een eigen kandidaat: alleen de span van
de hoofdzin zelf valt onder de regel.
"""
from __future__ import annotations

from .kandidaten import CandidateStatus, Evidence

VERSIE = "1"
CODE = "HOOFDZIN_VAN_REGEL"
REGEL = "jas.afleiding.hoofdzin_van_regel"
#: De klassen van een norm. De afleidingsregel is de hele zin; de hoofdzin draagt geen eigen norm.
NORMKLASSEN = ("Afleidingsregel", "Rechtsbetrekking", "Rechtsfeit")
_AR = "Afleidingsregel"


def pas_toe(kandidaten: tuple) -> tuple:
    """Haal de normklassen weg van elke kandidaat die de hoofdzin is van een ALS→DAN-regel."""
    regels: dict[tuple, object] = {}
    for r in kandidaten:
        if _AR not in r.possible_classes or r.status is CandidateStatus.REJECTED:
            continue
        for o in r.span_options:
            if o.soort == "clause" and r.span.start < o.span.start:
                regels.setdefault(o.span.sleutel(), r)
    if not regels:
        return kandidaten
    uit = []
    for k in kandidaten:
        r = regels.get(k.span.sleutel())
        weg = tuple(c for c in k.possible_classes if c in NORMKLASSEN)
        if r is None or r.id == k.id or not weg or k.status is CandidateStatus.REJECTED:
            uit.append(k)
            continue
        over = tuple(c for c in k.possible_classes if c not in NORMKLASSEN)
        bewijs = Evidence(detector="hoofdzin", code="HOOFDZIN_VAN_REGEL", regel=REGEL,
                          detail=f"hoofdzin van {r.span.tekst[:80]!r}; vervalt: {', '.join(weg)}")
        if over:
            uit.append(k.model_copy(update={"possible_classes": over, "evidence": (*k.evidence, bewijs)}))
        else:
            uit.append(k.model_copy(update={"status": CandidateStatus.REJECTED, "evidence": (*k.evidence, bewijs)}))
    return tuple(uit)


def op_fusie(fusie):
    """De stap in de keten: de fusie met de regel toegepast (dezelfde fusie als er niets te doen is)."""
    kandidaten = pas_toe(fusie.kandidaten)
    return fusie if kandidaten is fusie.kandidaten else fusie.model_copy(update={"kandidaten": kandidaten})
