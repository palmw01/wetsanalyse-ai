"""Offset-gebaseerde metrieken voor de hybride JAS-pijplijn (ADR-001 PR 5b, §13).

De scorers in `scoring.py` vergelijken op genormaliseerde tekst; die blijven voor de legacy-eval.
Hier gaat het om **posities**: een kandidaat en een referentie-annotatie zijn dezelfde als ze
dezelfde bron en dezelfde offsets hebben (modulo witruimte en interpunctie aan de rand). Twee
keer "de verzekerde" in één lid zijn dus twee verschillende spans – op tekst vergelijken kan dat
onderscheid niet maken.

Drie regels die de getallen eerlijk houden:

1. **Elke uitkomst draagt de referentiestatus.** Tegen `silver`/`provisional` heet recall
   `ankerdekking`; alleen tegen `adjudicated`/`gold` heet hij `annotation_recall` (§13).
2. **Candidate coverage is geen recall.** `candidate_recall` meet of de generator een span
   aanreikt, niet of de annotatie juist is.
3. **Partiële overlap is diagnose**, geen correcte annotatie.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

# Oplopend in zeggingskracht. De laagste status in een set bepaalt hoe het rapport mag heten.
STATUSSEN = ("fixture", "synthetic", "silver", "provisional", "review_pending", "adjudicated", "gold")
GEVALIDEERD = {"adjudicated", "gold"}
GEEN = "∅"          # rij/kolom in de confusion matrix voor "niet gevonden" of "niet in de referentie"
_RAND = " \t\n.,;:"


@dataclass(frozen=True)
class Ref:
    """Een referentie-annotatie of een voorspelling, op positie."""

    bron: str           # bron-IRI, of het casus-id bij de referentieset
    start: int
    eind: int
    klasse: str


def kern(tekst: str, start: int, eind: int) -> tuple[int, int]:
    """De span zonder witruimte en interpunctie aan de rand – zelfde regel als `taal.spanopties`."""
    fragment = tekst[start:eind]
    return start + len(fragment) - len(fragment.lstrip(_RAND)), eind - (len(fragment) - len(fragment.rstrip(_RAND)))


def controleer_status(referentie: dict[str, Any]) -> str:
    """De status van één referentie; `adjudicated`/`gold` zonder adjudicatierecord is een fout.

    Een casus uit de geversioneerde referentieset (herkenbaar aan `gold`) toetst het volledige schema
    van `eval.referentieset`; de ankerset (`golden_annotatie.jsonl`) houdt het lichtere record.
    """
    if "gold" in referentie:
        from eval.referentieset import valideer_casus   # lui: referentieset importeert deze module
        return valideer_casus(referentie)
    status = referentie.get("referentie_status", "")
    if status not in STATUSSEN:
        raise ValueError(f"onbekende of ontbrekende referentie_status: {status!r}")
    if status in GEVALIDEERD:
        adj = referentie.get("adjudicatie") or {}
        if not (adj.get("beoordelaars") and adj.get("datum") and adj.get("procedure")):
            raise ValueError(f"{status} zonder adjudicatie (beoordelaars, datum, procedure)")
    return status


def laagste_status(statussen: Iterable[str]) -> str:
    return min(statussen, key=STATUSSEN.index)


def recall_naam(status: str) -> str:
    return "annotation_recall" if status in GEVALIDEERD else "ankerdekking"


# --- kandidaatlaag ---------------------------------------------------------------------------

def kandidaat_metrieken(kandidaten: list[dict[str, Any]], referentie: list[Ref], status: str) -> dict[str, Any]:
    """Hoe goed reikt de kandidaatgenerator de referentiespans aan?

    `kandidaten`: dicts met `bron`, `start`, `eind`, `possible_classes`, `detectors` (de namen
    van de detectoren die hem vonden) en optioneel `opties` (spanopties als (start, eind)). Een
    referentie heet *gedekt* als er een kandidaat op exact die positie ligt, en *gedekt met
    klasse* als die klasse ook in `possible_classes` staat. `candidate_recall_incl_opties` telt ook
    een spanoptie mee: dat is de grens waar een latere keuze uit kan putten.
    """
    op_plek: dict[tuple[str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for k in kandidaten:
        op_plek[(k["bron"], k["start"], k["eind"])].append(k)
    ref_plekken = {(r.bron, r.start, r.eind) for r in referentie}

    per_klasse: dict[str, list[tuple[bool, bool]]] = defaultdict(list)
    bijdrage: Counter[str] = Counter()          # referenties die alleen déze detector aanreikte
    for r in referentie:
        hier = op_plek.get((r.bron, r.start, r.eind), [])
        per_klasse[r.klasse].append((bool(hier), any(r.klasse in k["possible_classes"] for k in hier)))
        detectoren = {d for k in hier for d in k.get("detectors", ())}
        if len(detectoren) == 1:
            bijdrage[next(iter(detectoren))] += 1

    alle = [x for v in per_klasse.values() for x in v]
    raak_kandidaten = sum(1 for plek in op_plek if plek in ref_plekken)
    optieplekken = {(k["bron"], s, e) for k in kandidaten for s, e in k.get("opties", ())} | set(op_plek)
    incl_opties = sum(1 for r in referentie if (r.bron, r.start, r.eind) in optieplekken)
    return {
        "referentie_status": status,
        "referenties": len(referentie),
        "kandidaten": len(op_plek),
        "candidate_recall": _deel(sum(g for g, _ in alle), len(alle)),
        "candidate_recall_met_klasse": _deel(sum(k for _, k in alle), len(alle)),
        "candidate_recall_incl_opties": _deel(incl_opties, len(referentie)),
        "candidate_precision": _deel(raak_kandidaten, len(op_plek)),
        "kandidaten_per_referentie": _deel(len(op_plek), len(referentie)),
        "per_klasse": {k: {"n": len(v), "candidate_recall": _deel(sum(g for g, _ in v), len(v)),
                           "met_klasse": _deel(sum(x for _, x in v), len(v))}
                       for k, v in sorted(per_klasse.items())},
        "unieke_bijdrage_per_detector": dict(sorted(bijdrage.items())),
    }


# --- classificatielaag -----------------------------------------------------------------------

def classificatie_metrieken(voorspeld: list[Ref], referentie: list[Ref], status: str) -> dict[str, Any]:
    """P/R/F1 per klasse op exacte positie + klasse, macro en micro, en een confusion matrix.

    De matrix vergelijkt op exacte positie: rij = referentieklasse (of ∅ als de voorspelling
    nergens in de referentie staat), kolom = voorspelde klasse (of ∅ als de referentie niet is
    voorspeld). Meerdere klassen op één positie (overlap is in JAS toegestaan) worden als
    multiset gekoppeld: gelijke klassen eerst.
    """
    ref_op: dict[tuple, list[str]] = defaultdict(list)
    vs_op: dict[tuple, list[str]] = defaultdict(list)
    for r in referentie:
        ref_op[(r.bron, r.start, r.eind)].append(r.klasse)
    for v in voorspeld:
        vs_op[(v.bron, v.start, v.eind)].append(v.klasse)

    matrix: Counter[tuple[str, str]] = Counter()
    for plek in set(ref_op) | set(vs_op):
        rest_r, rest_v = Counter(ref_op.get(plek, [])), Counter(vs_op.get(plek, []))
        gelijk = rest_r & rest_v
        for klasse, n in gelijk.items():
            matrix[(klasse, klasse)] += n
        rest_r, rest_v = list((rest_r - gelijk).elements()), list((rest_v - gelijk).elements())
        for r, v in zip(rest_r, rest_v):
            matrix[(r, v)] += 1
        for r in rest_r[len(rest_v):]:
            matrix[(r, GEEN)] += 1
        for v in rest_v[len(rest_r):]:
            matrix[(GEEN, v)] += 1

    klassen = sorted({k for paar in matrix for k in paar if k != GEEN})
    per_klasse = {}
    for k in klassen:
        tp = matrix[(k, k)]
        fp = sum(n for (r, v), n in matrix.items() if v == k and r != k)
        fn = sum(n for (r, v), n in matrix.items() if r == k and v != k)
        p, rc = _deel(tp, tp + fp), _deel(tp, tp + fn)
        per_klasse[k] = {"precision": p, "recall": rc, "f1": _f1(p, rc), "tp": tp, "fp": fp, "fn": fn}
    tp = sum(v["tp"] for v in per_klasse.values())
    fp = sum(v["fp"] for v in per_klasse.values())
    fn = sum(v["fn"] for v in per_klasse.values())
    micro_p, micro_r = _deel(tp, tp + fp), _deel(tp, tp + fn)
    gemeten = [v["f1"] for v in per_klasse.values() if v["f1"] is not None]
    return {
        "referentie_status": status,
        "recall_naam": recall_naam(status),
        "per_klasse": per_klasse,
        "micro": {"precision": micro_p, "recall": micro_r, "f1": _f1(micro_p, micro_r)},
        "macro_f1": sum(gemeten) / len(gemeten) if gemeten else None,
        "exact_span": _deel(len(set(ref_op) & set(vs_op)), len(ref_op)),
        "partial_overlap_zelfde_klasse": _partieel(voorspeld, referentie),
        "confusion": {f"{r} → {v}": n for (r, v), n in sorted(matrix.items())},
    }


def _partieel(voorspeld: list[Ref], referentie: list[Ref]) -> float | None:
    """Aandeel referenties zónder exacte match waar een voorspelling van dezelfde klasse overlapt."""
    exact = {(v.bron, v.start, v.eind, v.klasse) for v in voorspeld}
    rest = [r for r in referentie if (r.bron, r.start, r.eind, r.klasse) not in exact]
    raak = sum(1 for r in rest if any(v.bron == r.bron and v.klasse == r.klasse and v.start < r.eind
                                      and r.start < v.eind for v in voorspeld))
    return _deel(raak, len(rest))


def _deel(teller: int, noemer: int) -> float | None:
    """Geen noemer is 'niet gemeten', geen gratis 1.0 (kwaliteit.md: 'niet beoordeelbaar')."""
    return teller / noemer if noemer else None


def _f1(p: float | None, r: float | None) -> float | None:
    if p is None or r is None:
        return None
    return 2 * p * r / (p + r) if p + r else 0.0


# --- classifier-contract (onderzoek §9, V5) ---------------------------------------------------

_ONGELDIGE_UITVOER = ("CLASSIFIER_GEEN_UITVOER", "CLASSIFIER_OMITTED")


def contract_metrieken(register: list[dict[str, Any]], granulariteit: str = "universeel",
                       resolutie: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Hoe vaak de classifier (en de reviewer) buiten zijn contract trad, op het beslisregister (V4).

    - `leakage_count`: de ongeldige keuze stond wél in de batch-enum (de unie over de batch);
    - `leakage_uit_specificiteit`: de ongeldige keuze was bij déze kandidaat door JAS-PRIORITY
      weggehaald – een conflict tussen regel en model, geen gewone vergissing.

    De batch-unie wordt herleid met dezelfde indeling als de keten (`classificatie.batches`): één
    batch bij `universeel`, anders per familie van de eerste mogelijke klasse.
    """
    from agent.jas_pipeline.classificatie import FAMILIES
    from agent.jas_pipeline.kandidaten import GEEN_ANNOTATIE

    model = [b for b in register if b.get("door") == "model"]
    sleutel = (lambda b: "alle") if granulariteit == "universeel" else (lambda b: FAMILIES[b["mogelijke_klassen"][0]])
    unie: dict[str, set[str]] = defaultdict(set)
    for b in model:
        unie[sleutel(b)].update(b["mogelijke_klassen"], {GEEN_ANNOTATIE})
    ongeldig_klasse = [b for b in model if b.get("classifier_reden", "").startswith("CLASSIFIER_ONGELDIGE_KLASSE:")]
    gekozen = {id(b): b["classifier_reden"].split(":", 1)[1] for b in ongeldig_klasse}
    ongeldig_optie = sum(b.get("classifier_reden", "").startswith("CLASSIFIER_ONGELDIGE_OPTIE:") for b in model)
    ongeldige_uitvoer = sum(b.get("classifier_reden", "") in _ONGELDIGE_UITVOER for b in model)
    fouten = len(ongeldig_klasse) + ongeldig_optie + ongeldige_uitvoer
    review = [t for t in (resolutie or []) if t.get("reden") != "DEGRADED_PARSE"]
    return {
        "modelbeslissingen": len(model),
        "invalid_class_selections": len(ongeldig_klasse),
        "invalid_option_selections": ongeldig_optie,
        "leakage_count": sum(gekozen[id(b)] in unie[sleutel(b)] for b in ongeldig_klasse),
        "leakage_uit_specificiteit": sum(gekozen[id(b)] in b.get("vervallen", ()) for b in ongeldig_klasse),
        "invalid_tool_outputs": ongeldige_uitvoer,
        "contract_error_rate": fouten / len(model) if model else None,
        "reviewer_gevallen": len(review),
        "reviewer_contract_errors": sum(t.get("regel") == "R-ONGELDIG" for t in review),
        "reviewer_contract_error_rate": (sum(t.get("regel") == "R-ONGELDIG" for t in review) / len(review)
                                         if review else None),
    }
