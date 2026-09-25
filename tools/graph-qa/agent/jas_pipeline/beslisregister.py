"""Het beslisregister: per kandidaat één compacte regel, óók als hij niets opleverde (validatieplan V4).

Een export draagt alleen wat is voorgesteld. Wat het model afwees of wat de voorrang wegnam, bleef
tot nu toe in de agent-state achter en was na de beurt weg. Daardoor waren twee vragen op
productiedata niet te beantwoorden: wijst het model sterk bewijs af (H6), en krijgt dezelfde
kandidaat bij een herhaling dezelfde uitkomst (§13)?

Dit register reist met de batch mee naar de api, die het bij de batch bewaart. Het is een meting en
verandert niets aan wat de keten besluit.

Twee velden verdienen uitleg:

- `bewijs_fingerprint`: sha256 over de gesorteerde (detector, code, regel). Detectie hoort
  deterministisch te zijn, dus een fingerprint die tussen twee runs op dezelfde bron verschilt,
  is een bug.
- `classifier_reden`: de reden die de classifier gaf, vóór de resolver hem overschreef. Bij een
  ongeldige keuze staat `CLASSIFIER_ONGELDIGE_KLASSE:<klasse>` hier, ook als de uiteindelijke
  `reden` `R-ONGELDIG` is. Die code staat alleen in de twijfel van het voorstel, dus zonder dit veld
  was hij na de resolver kwijt.
"""
from __future__ import annotations

import hashlib
from typing import Any

from .kandidaten import Candidate


def fingerprint(k: Candidate) -> str:
    sleutels = sorted({(e.detector, e.code, e.regel) for e in k.evidence})
    return hashlib.sha256(repr(sleutels).encode("utf-8")).hexdigest()[:16]


def vervallen(k: Candidate) -> list[str]:
    """De klassen die JAS-PRIORITY bij deze kandidaat weghaalde (uit het bewijs `PRIORITY_APPLIED`)."""
    uit: list[str] = []
    for e in k.evidence:
        if e.code == "PRIORITY_APPLIED" and "vervalt:" in e.detail:
            uit += [c.strip() for c in e.detail.split("vervalt:", 1)[1].split(",") if c.strip()]
    return list(dict.fromkeys(uit))


def compact(kandidaten: list[Candidate] | tuple[Candidate, ...], beslissingen: list[Any],
            voorstellen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Eén regel per kandidaat die een beslissing kreeg, in labelvolgorde."""
    per_label = {k.label: k for k in kandidaten}
    twijfel = {}
    for v in voorstellen:
        spoor = v.get("trace") or {}
        label = (spoor.get("kandidaat") or {}).get("label", "")
        for t in spoor.get("twijfel") or ():
            if t.get("reden") == "CLASSIFIER_ABSTAIN" and t.get("detail"):
                twijfel.setdefault(label, t["detail"])
    uit = []
    for b in sorted(beslissingen, key=lambda b: b.label):
        k = per_label.get(b.label)
        if k is None:
            continue
        uit.append({
            "kandidaat_id": k.id, "label": k.label, "bron_iri": k.span.bron_iri,
            "start": k.span.start, "eind": k.span.eind, "mogelijke_klassen": list(k.possible_classes),
            "vervallen": vervallen(k),
            "bewijs": sorted({e.code for e in k.evidence if e.code != "PRIORITY_APPLIED"}),
            "detectoren": sorted({e.detector for e in k.evidence if e.code != "PRIORITY_APPLIED"}),
            "opties": [[o.span.start, o.span.eind] for o in k.span_options],
            "bewijs_fingerprint": fingerprint(k),
            "status": b.status.value, "door": b.door, "klasse": b.klasse, "reden": b.reden,
            "classifier_reden": twijfel.get(b.label, b.reden if b.reden.startswith("CLASSIFIER_") else ""),
        })
    return uit
