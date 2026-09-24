"""Deterministische validatie vóór een voorstel de keten verlaat (ADR-001 PR 11, opdracht §20).

Een taalmodel mag deze controles niet vervangen, en ze hangen ook niet van een model af: ze
toetsen of wat er uitgaat structureel klopt met de bron, de kandidaat en de beslissing.

Fouten (het voorstel gaat er niet uit; de beslissing wordt REJECTED met foutcode):

- `V_KANDIDAAT`   – het voorstel hangt niet aan een bekende kandidaat en beslissing
- `V_STATUS`      – de beslissing is niet ACCEPTED of HUMAN_REVIEW
- `V_ANKER`       – offsets, letterlijke tekst, bron-hash of snapshot kloppen niet (bronmodel)
- `V_KLASSE`      – de klasse bestaat niet of was voor deze kandidaat niet toegestaan
- `V_GRENS`       – de grens is niet de kandidaatspan en geen van zijn spanopties
- `V_PROVENANCE`  – geen bewijs, of een modelbeslissing zonder model/promptversie

Waarschuwingen (het voorstel gaat wél door, de resolver weegt ze):

- `W_ZELFDE_SPAN` – dezelfde grens met meer dan één klasse. JAS staat overlap toe voor
  verschillende functies (projectregel markeren-fragmentgrenzen); of het hier om één functie gaat,
  is geen structurele vraag.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from bronmodel import BronFout, valideer_ankers
from pydantic import BaseModel, ConfigDict

from ..jas_klassen import GELDIGE_JAS_KLASSEN
from .besluit import Beslissing
from .kandidaten import Candidate, CandidateStatus


class Bevinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    label: str
    detail: str = ""
    ernst: str = "fout"          # "fout" of "waarschuwing"


def valideer(voorstellen: list[tuple[dict[str, Any], Beslissing]], kandidaten: dict[str, Candidate],
             snapshot: dict[str, Any], provenance: dict[str, Any]) -> tuple[list[dict[str, Any]], list[Bevinding]]:
    """Geeft de voorstellen die door de controles komen, en alle bevindingen."""
    goed, bevindingen = [], []
    for v, b in voorstellen:
        fout = _fout(v, b, kandidaten.get(b.kandidaat_id), snapshot, provenance)
        if fout:
            bevindingen.append(Bevinding(code=fout[0], label=b.label, detail=fout[1]))
        else:
            goed.append((v, b))
    per_span: dict[tuple, list[tuple[str, str]]] = defaultdict(list)
    for v, b in goed:
        per_span[tuple((a["bron_iri"], a["start"], a["eind"]) for a in v["ankers"])].append((v["klasse"], b.label))
    for klassen in per_span.values():
        if len({k for k, _ in klassen}) > 1:
            bevindingen.append(Bevinding(code="W_ZELFDE_SPAN", label=klassen[0][1], ernst="waarschuwing",
                                         detail=", ".join(sorted({k for k, _ in klassen}))))
    return [v for v, _ in goed], bevindingen


def _fout(v: dict[str, Any], b: Beslissing, k: Candidate | None, snapshot: dict[str, Any],
          provenance: dict[str, Any]) -> tuple[str, str] | None:
    if k is None or k.label != b.label:
        return "V_KANDIDAAT", b.kandidaat_id
    if b.status not in (CandidateStatus.ACCEPTED, CandidateStatus.HUMAN_REVIEW):
        return "V_STATUS", b.status.value
    ankers = v.get("ankers") or []
    try:
        valideer_ankers(snapshot, ankers)
    except (BronFout, KeyError, TypeError) as exc:
        return "V_ANKER", str(exc)
    if v.get("tekst") != " ".join(a["tekst"] for a in ankers):
        return "V_ANKER", "tekst wijkt af van de ankers"
    if v.get("klasse") not in GELDIGE_JAS_KLASSEN or v.get("klasse") != b.klasse:
        return "V_KLASSE", str(v.get("klasse"))
    if b.klasse not in k.possible_classes:
        return "V_KLASSE", f"{b.klasse} was voor {k.label} niet toegestaan"
    grens = (ankers[0]["bron_iri"], ankers[0]["start"], ankers[-1]["eind"])
    toegestaan = {k.span.sleutel(), *(o.span.sleutel() for o in k.span_options)}
    if len(ankers) != 1 or grens not in toegestaan:
        return "V_GRENS", f"{grens[1]}-{grens[2]}"
    if not k.evidence:
        return "V_PROVENANCE", "geen bewijs"
    if b.door == "model" and not (provenance.get("model") and provenance.get("classifier_prompt")):
        return "V_PROVENANCE", "modelbeslissing zonder model of promptversie"
    return None
