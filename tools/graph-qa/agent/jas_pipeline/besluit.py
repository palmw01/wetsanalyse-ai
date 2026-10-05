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

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .bewijssterkte import generiek_bewijs, klasse_van_bewijs
from .kandidaten import GEEN_ANNOTATIE, Candidate, CandidateStatus

# De reden van een modelafwijzing; ook de herbeoordeling van centrale normen herkent haar hieraan.
GEEN_ANNOTATIE_REDEN = "geen annotatie"

# Bewijscodes die op zichzelf één klasse dragen: afgeleid uit de regeldefinities (bewijssterkte.py).
STERK_BEWIJS = frozenset(klasse_van_bewijs())
KLASSE_VAN_STERK = klasse_van_bewijs()
STERK_BOVEN_GENERIEK = "STERK_BOVEN_GENERIEK"
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
    # `terugval`: het model koos niets bruikbaars en de review besliste niet; de resolver zette de
    # eerste mogelijke klasse voorlopig neer. Geen keuze van het model, dus ook niet zo genoemd.
    door: Literal["regel", "model", "specificiteit", "terugval"]
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
    # Audit D05: een generiek grammaticaal signaal (onderwerp, object, opsomming) mag sterk
    # patroonbewijs niet blokkeren. Alle sterke codes wijzen één klasse aan en er is geen ander
    # zwak bewijs; de overige klassen blijven als alternatief in het voorstel zichtbaar.
    sterk = codes & STERK_BEWIJS
    klassen = {KLASSE_VAN_STERK[c] for c in sterk}
    if (sterk and len(klassen) == 1 and (klasse := klassen.pop()) in k.possible_classes
            and codes - sterk and codes - sterk <= generiek_bewijs()):
        return Beslissing(kandidaat_id=k.id, label=k.label, status=CandidateStatus.ACCEPTED, klasse=klasse,
                          door="regel", reden=f"{STERK_BOVEN_GENERIEK}:{','.join(sorted(sterk))}"
                          f"|{','.join(sorted(codes - sterk))}")
    return None


def uit_modelkeuze(k: Candidate, keuze: str, optie: str) -> Beslissing:
    if keuze == GEEN_ANNOTATIE:
        return Beslissing(kandidaat_id=k.id, label=k.label, status=CandidateStatus.REJECTED,
                          door="model", reden=GEEN_ANNOTATIE_REDEN)
    return Beslissing(kandidaat_id=k.id, label=k.label, status=CandidateStatus.ACCEPTED,
                      klasse=keuze, optie=optie, door="model")


def onzeker(k: Candidate, reden: str) -> Beslissing:
    return Beslissing(kandidaat_id=k.id, label=k.label, status=CandidateStatus.UNCERTAIN,
                      door="model", reden=reden)


def kernouder(e) -> str:
    """De langere kandidaat waarvan dit TEMPORAL_KERNEL-bewijs de kern registreert."""
    return json.loads(e.detail)["ouder"]


def ontdubbel_tijd(voorstellen, beslissingen, kandidaten):
    """Alleen expliciete kernalternatieven van dezelfde geaccepteerde T-functie ontdubbelen."""
    bs = {b.kandidaat_id: b for b in beslissingen}
    vs = {}
    for v in voorstellen:
        kid = v["trace"]["kandidaat"]["id"]
        if kid in vs:
            raise ValueError(f"meer dan één voorstel voor kandidaat {kid}; ontdubbelen zou er een verliezen")
        vs[kid] = v

    def t_geaccepteerd(kid):
        b = bs.get(kid)
        return bool(b and b.status is CandidateStatus.ACCEPTED and b.klasse == "Tijdsaanduiding" and not b.optie)

    vervangen = {}
    for kort in kandidaten.values():
        if not t_geaccepteerd(kort.id):
            continue
        ouders = [kandidaten[o] for o in (kernouder(e) for e in kort.evidence if e.code == "TEMPORAL_KERNEL")
                  if o in kandidaten and o in vs and t_geaccepteerd(o)]
        if ouders:
            lang = max(ouders, key=lambda k: (k.span.eind - k.span.start, k.id))
            vervangen[kort.id] = lang.id
    for kid in vervangen:
        gezien = {kid}
        while vervangen[kid] in vervangen:
            if vervangen[kid] in gezien:
                raise ValueError(f"cyclische tijdkern bij {kid}")
            gezien.add(vervangen[kid])
            vervangen[kid] = vervangen[vervangen[kid]]
    uit = [b.model_copy(update={"status": CandidateStatus.REJECTED, "klasse": "",
                                "reden": "DUBBELE_TIJD_FUNCTIE:" + vervangen[b.kandidaat_id]})
           if b.kandidaat_id in vervangen else b for b in beslissingen]
    return [v for kid, v in vs.items() if kid not in vervangen], uit, vervangen
