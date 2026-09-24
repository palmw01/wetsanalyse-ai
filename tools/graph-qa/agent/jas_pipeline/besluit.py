"""Beslissingen over kandidaten: welke kunnen zonder taalmodel, en de vorm van élke beslissing.

Opdracht §4: *kan het deterministisch, doe het zonder LLM.* Een kandidaat wordt hier zonder
modelaanroep voorgesteld als hij precies één mogelijke klasse heeft en al zijn bewijs uit een
hoog-deterministische regel komt (datum, termijn, definitieonderdeel, delegatieformule, rekenkundige
of vergelijkende operator, gebiedsnaam). Dat is een **voorstel**, geen vaststelling: de jurist
beoordeelt het zoals elk ander, en `deterministisch_accepteren=false` zet het uit.

Alles wat meer dan één klasse toelaat, of een signaal uit de parse of een lexicon draagt, gaat naar
de classifier. Een grammaticaal signaal is geen classificatie (ADR-001 §4).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .kandidaten import GEEN_ANNOTATIE, Candidate, CandidateStatus

# Bewijscodes die op zichzelf een klasse dragen (profielen: deterministic_detection_possible = hoog).
STERK_BEWIJS = frozenset({
    "TEMPORAL_DATE", "TEMPORAL_DURATION", "TEMPORAL_RELATIVE_PERIOD", "TEMPORAL_PERIOD_OF",
    "TEMPORAL_MOMENT", "DEFINITION_ITEM", "DEFINITION_SENTENCE", "DELEGATION_FORMULA",
    "COMPARISON", "ARITHMETIC", "LOCATION_NAME", "LOCATION_DESCRIPTION",
})
# Bewijs dat niets over de klasse zegt maar over wat er al mee gebeurde.
_ADMINISTRATIEF = frozenset({"PRIORITY_APPLIED"})


class Beslissing(BaseModel):
    """Eén beslissing over één kandidaat, met wie of wat hem nam en op grond waarvan."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kandidaat_id: str
    label: str
    status: CandidateStatus
    klasse: str = ""                      # leeg bij REJECTED/UNCERTAIN
    optie: str = ""                       # gekozen spanoptie-id, leeg = de kandidaatspan
    door: Literal["regel", "model", "specificiteit"]
    reden: str = ""                       # waarom deze uitkomst; bij UNCERTAIN een code


def deterministisch(k: Candidate) -> Beslissing | None:
    """Een beslissing zonder model, of None als de kandidaat naar de classifier moet."""
    if k.status is CandidateStatus.REJECTED:
        regel = next((e.regel for e in reversed(k.evidence) if e.code == "PRIORITY_APPLIED"), "")
        return Beslissing(kandidaat_id=k.id, label=k.label, status=CandidateStatus.REJECTED,
                          door="specificiteit", reden=regel)
    codes = {e.code for e in k.evidence} - _ADMINISTRATIEF
    if len(k.possible_classes) == 1 and codes and codes <= STERK_BEWIJS:
        return Beslissing(kandidaat_id=k.id, label=k.label, status=CandidateStatus.ACCEPTED,
                          klasse=k.possible_classes[0], door="regel", reden=",".join(sorted(codes)))
    return None


def uit_modelkeuze(k: Candidate, keuze: str, optie: str) -> Beslissing:
    if keuze == GEEN_ANNOTATIE:
        return Beslissing(kandidaat_id=k.id, label=k.label, status=CandidateStatus.REJECTED,
                          door="model", reden="geen annotatie")
    return Beslissing(kandidaat_id=k.id, label=k.label, status=CandidateStatus.ACCEPTED,
                      klasse=keuze, optie=optie, door="model")


def onzeker(k: Candidate, reden: str) -> Beslissing:
    return Beslissing(kandidaat_id=k.id, label=k.label, status=CandidateStatus.UNCERTAIN,
                      door="model", reden=reden)
