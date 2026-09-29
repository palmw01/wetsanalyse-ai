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

from .besluit import GEEN_ANNOTATIE_REDEN, STERK_BEWIJS, Beslissing
from .bewijssterkte import klasse_van_bewijs
from .kandidaten import Candidate, CandidateStatus
from .validatie import Bevinding

# Welke klasse een sterk bewijsstuk aanwijst: afgeleid uit de regeldefinities (bewijssterkte.py).
KLASSE_VAN_BEWIJS = klasse_van_bewijs()
assert set(KLASSE_VAN_BEWIJS) == set(STERK_BEWIJS), "elk sterk bewijs wijst één klasse aan"

REVIEWBAAR = ("DETECTOR_CONFLICT", "CLASSIFIER_ABSTAIN", "ZELFDE_SPAN", "CENTRALE_NORM_AFGEWEZEN")


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
    return uit + centrale_afwijzingen(kandidaten, beslissingen)


def centrale_afwijzingen(kandidaten, beslissingen):
    """NormDetector levert één beschermd normsegment; inspecteer alleen die lokale eenheid.

    Een nominalisatie-RF is geen centrale norm. Validatie-afwijzingen worden hier niet
    opnieuw aangeboden. Geen detectorbewijs → geen claim dat een norm ontbreekt.
    """
    per_id = {b.kandidaat_id: b for b in beslissingen}
    normen = [k for k in kandidaten.values() if any(e.code == "NORMATIVE_PREDICATE" for e in k.evidence)]
    uit = []
    for norm in normen:
        b = per_id.get(norm.id)
        if not b or b.door != "model" or b.status is not CandidateStatus.REJECTED or b.reden != GEEN_ANNOTATIE_REDEN:
            continue
        binnen = [k for k in kandidaten.values() if k.span.bron_iri == norm.span.bron_iri
                  and norm.span.start <= k.span.start and k.span.eind <= norm.span.eind]
        if sum(k in normen for k in binnen) != 1:
            continue
        geaccepteerd = [k for k in binnen if k.id in per_id and per_id[k.id].status is CandidateStatus.ACCEPTED]
        centraal = any(per_id[k.id].klasse in {"Rechtsbetrekking", "Rechtsfeit", "Afleidingsregel"}
                       and any(e.code == "NORMATIVE_PREDICATE" or e.code.startswith("CALCULATION_")
                               for e in k.evidence) for k in geaccepteerd)
        rest = [k for k in geaccepteerd if per_id[k.id].klasse in {"Rechtsobject", "Tijdsaanduiding"}]
        if rest and not centraal:
            uit.append(Twijfel(label=norm.label, reden="CENTRALE_NORM_AFGEWEZEN", alternatieven=norm.possible_classes,
                              categorie="INHOUDELIJKE_HERBEOORDELING",
                              detail="Enige centrale norm afgewezen; resterend: " + "; ".join(
                                  f"{k.label} {per_id[k.id].klasse}: {k.span.tekst}" for k in rest)))
    return uit
