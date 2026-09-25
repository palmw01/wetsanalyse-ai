"""Onzekerheid uit waarneembare signalen (ADR-001 PR 12, opdracht §19).

Geen zelfgerapporteerde modelconfidence: een twijfelgeval is een kandidaat waar iets aanwijsbaars
botst. Vier redenen, elk met een vaste behandeling in de resolver:

- `DETECTOR_CONFLICT`  – het model koos klasse K terwijl er sterk, hoog-deterministisch bewijs voor
  een andere klasse K' ligt (een termijnpatroon, een definitie-aanhef …). → gerichte review.
- `CLASSIFIER_ABSTAIN` – de classifier gaf voor deze kandidaat geen geldige beslissing. → review.
- `ZELFDE_SPAN`        – twee geaccepteerde klassen op exact dezelfde grens (validatiewaarschuwing).
  JAS staat overlap toe voor verschillende functies; of dat hier zo is, is een oordeel. → review.
- `DEGRADED_PARSE`     – de kandidaat komt uit een bron zonder zinsontleding en het model besliste.
  Minder signalen, dus meer onzekerheid, maar een tweede model voegt hier niets toe. → jurist.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .besluit import STERK_BEWIJS, Beslissing
from .kandidaten import Candidate, CandidateStatus
from .validatie import Bevinding

# Welke klasse een sterk bewijsstuk aanwijst (profielen: de hoog-deterministische regels).
KLASSE_VAN_BEWIJS = {
    "TEMPORAL_DATE": "Tijdsaanduiding", "TEMPORAL_DURATION": "Tijdsaanduiding",
    "TEMPORAL_RELATIVE_PERIOD": "Tijdsaanduiding", "TEMPORAL_PERIOD_OF": "Tijdsaanduiding",
    "TEMPORAL_MOMENT": "Tijdsaanduiding", "DEFINITION_ITEM": "Brondefinitie",
    "DEFINITION_SENTENCE": "Brondefinitie", "DELEGATION_FORMULA": "Delegatiebevoegdheid en delegatie-invulling",
    "COMPARISON": "Operator", "ARITHMETIC": "Operator", "LOCATION_NAME": "Plaatsaanduiding",
    "LOCATION_DESCRIPTION": "Plaatsaanduiding",
}
assert set(KLASSE_VAN_BEWIJS) == set(STERK_BEWIJS), "elk sterk bewijs wijst één klasse aan"

REVIEWBAAR = ("DETECTOR_CONFLICT", "CLASSIFIER_ABSTAIN", "ZELFDE_SPAN")


class Twijfel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    reden: str                            # een van de vier codes hierboven
    huidig: str = ""                      # de klasse die nu voorligt (leeg bij abstain)
    alternatieven: tuple[str, ...] = ()   # wat er ook toegestaan is
    detail: str = ""
    # Alleen rapportage (validatieplan V5): bij CLASSIFIER_ABSTAIN of het een contractfout was (een
    # keuze buiten de toegestane beslissingen) of echt geen uitvoer. De reviewer ziet dit veld niet
    # en de resolver kijkt er niet naar; de afhandeling blijft die van CLASSIFIER_ABSTAIN.
    categorie: str = ""


def signaleer(kandidaten: dict[str, Candidate], beslissingen: list[Beslissing], bevindingen: list[Bevinding],
              gedegradeerd: set[str]) -> list[Twijfel]:
    per_label = {k.label: k for k in kandidaten.values()}
    uit: list[Twijfel] = []
    for b in beslissingen:
        k = kandidaten[b.kandidaat_id]
        overige = tuple(c for c in k.possible_classes if c != b.klasse)
        if b.status is CandidateStatus.UNCERTAIN and b.door == "model":
            contract = b.reden.startswith(("CLASSIFIER_ONGELDIGE_KLASSE", "CLASSIFIER_ONGELDIGE_OPTIE"))
            uit.append(Twijfel(label=b.label, reden="CLASSIFIER_ABSTAIN", alternatieven=k.possible_classes,
                               detail=b.reden,
                               categorie="CLASSIFIER_CONTRACT_ERROR" if contract else "CLASSIFIER_ABSTAIN"))
            continue
        if b.status is not CandidateStatus.ACCEPTED or b.door != "model":
            continue
        sterk = {KLASSE_VAN_BEWIJS[e.code] for e in k.evidence if e.code in KLASSE_VAN_BEWIJS}
        if sterk and b.klasse not in sterk:
            uit.append(Twijfel(label=b.label, reden="DETECTOR_CONFLICT", huidig=b.klasse,
                               alternatieven=tuple(c for c in overige if c in sterk) or overige,
                               detail="sterk bewijs voor " + ", ".join(sorted(sterk))))
        elif k.span.bron_iri in gedegradeerd:
            uit.append(Twijfel(label=b.label, reden="DEGRADED_PARSE", huidig=b.klasse, alternatieven=overige))
    for w in bevindingen:
        if w.code == "W_ZELFDE_SPAN" and w.label in per_label:
            klassen = tuple(w.detail.split(", "))
            uit.append(Twijfel(label=w.label, reden="ZELFDE_SPAN", huidig=klassen[0], alternatieven=klassen[1:]))
    return uit
