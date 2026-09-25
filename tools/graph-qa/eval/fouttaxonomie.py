"""Fouttaxonomie v2 (onderzoek-empirische-validatie §8, validatieplan V3).

Elke fout krijgt precies één **primaire** code: die van de eerste laag waar het misging, niet de laag
waar het zichtbaar werd. Daarnaast nul of meer **secundaire** codes, en een **soort**:

- `juridisch`: de uitkomst is juridisch onjuist tegen gold;
- `technisch`: de pipeline brak een eigen contract, ongeacht de juridische uitkomst;
- `evaluatie`: de referentie, de matching of het harnas is fout.

`classificeer` leidt af wat uit de keten zelf af te leiden is: de kandidaat-, span-, contract- en
reviewlaag. Wat een mens moet vaststellen (bron, segmentatie, parser, connectief, context, relaties,
referentie- en matchingfouten) komt uit de relationele checklist (§14) en wordt via `correcties`
toegepast. Een correctie vervangt de automatische toewijzing, en het rapport zegt dat.

`debatable` in gold is géén fout: het telt apart en nooit als juist of onjuist.

Twee soorten invoer:

- **volledig**: alle kandidaten met hun beslissing (`uit_uitkomst`, het harnas). Dan zijn leakage en
  een model-afwijzing bij sterk bewijs te zien;
- **alleen voorstellen**: wat een run-export of het `element`-event draagt (`uit_elementen`). Afgewezen
  kandidaten ontbreken dan (§1, gat dat V4 dicht), en de batch-unie is onbekend: `LEAKAGE` wordt dan
  niet toegekend in plaats van geraden.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Any, Iterable

from agent.jas_pipeline.besluit import STERK_BEWIJS
from agent.jas_pipeline.kandidaten import GEEN_ANNOTATIE
from agent.jas_pipeline.onzekerheid import KLASSE_VAN_BEWIJS
from eval.metrieken import kern

JURIDISCH, TECHNISCH, EVALUATIE = "juridisch", "technisch", "evaluatie"

#: code → (laag, typische soort). De soort per fout volgt uit de primaire code.
CODES: dict[str, tuple[str, str]] = {
    "SOURCE_ERROR": ("bron", TECHNISCH),
    "SEGMENTATION_ERROR": ("segmentatie", TECHNISCH),
    "PARSER_ERROR": ("taal", TECHNISCH),
    "DETECTOR_ERROR": ("detector", TECHNISCH),
    "CONNECTIVE_DISAMBIGUATION_ERROR": ("detector", JURIDISCH),
    "CANDIDATE_MISSED": ("kandidaat", JURIDISCH),
    "CANDIDATE_FALSE_POSITIVE": ("kandidaat", TECHNISCH),
    "DETECTOR_SPAN_ERROR": ("kandidaat", JURIDISCH),
    "SPAN_TOO_WIDE": ("kandidaat/keuze", JURIDISCH),
    "SPAN_TOO_NARROW": ("kandidaat/keuze", JURIDISCH),
    "FUSION_ERROR": ("fusie", TECHNISCH),
    "HYPOTHESIS_ERROR": ("fusie/specificiteit", TECHNISCH),
    "POSSIBLE_CLASS_ERROR": ("kandidaat", JURIDISCH),
    "EVIDENCE_CLASS_MAPPING_ERROR": ("detector/profiel", TECHNISCH),
    "CLASSIFIER_ERROR": ("classifier", JURIDISCH),
    "CLASSIFIER_CONTRACT_ERROR": ("classifier", TECHNISCH),
    "CLASSIFIER_CROSS_CANDIDATE_LEAKAGE": ("classifier", TECHNISCH),
    "CLASSIFIER_ABSTAIN": ("classifier", TECHNISCH),
    "CONTEXT_ERROR": ("classifier-invoer", TECHNISCH),
    "RELATION_MISSING": ("", JURIDISCH),
    "FRAME_ERROR": ("", ""),
    "UNCERTAINTY_ERROR": ("onzekerheid", TECHNISCH),
    "REVIEW_ERROR": ("reviewer", JURIDISCH),
    "REVIEW_CONTRACT_ERROR": ("reviewer", TECHNISCH),
    "RESOLUTION_ERROR": ("resolver", TECHNISCH),
    "VALIDATION_ERROR": ("validatie", TECHNISCH),
    "PROJECTION_ERROR": ("api/RDF", TECHNISCH),
    "REFERENCE_ERROR": ("evaluatie", EVALUATIE),
    "MATCHING_ERROR": ("evaluatie", EVALUATIE),
}
# Codes die alleen secundair voorkomen: ze zeggen iets over een fout, niet wáár hij ontstond.
ALLEEN_SECUNDAIR = frozenset({"SPAN_TOO_WIDE", "SPAN_TOO_NARROW", "CLASSIFIER_CROSS_CANDIDATE_LEAKAGE"})
GEGENEREERD = frozenset({"FRAME_ERROR"})       # gereserveerd; nu nooit toegekend

_CONTRACT = ("CLASSIFIER_ONGELDIGE_KLASSE:", "CLASSIFIER_ONGELDIGE_OPTIE:")
_ABSTAIN = ("CLASSIFIER_GEEN_UITVOER", "CLASSIFIER_OMITTED")
_REVIEW_ONGELDIG = "R-ONGELDIG"


@dataclass(frozen=True)
class Kandidaat:
    """Wat de classificeerder van één kandidaat moet weten, los van de pydantic-modellen van de keten."""

    label: str
    bron: str
    start: int
    eind: int
    klassen: tuple[str, ...]                  # possible_classes na specificiteit
    codes: frozenset[str]                     # bewijscodes, zonder PRIORITY_APPLIED
    vervallen: tuple[str, ...] = ()           # door JAS-PRIORITY weggehaald
    opties: tuple[tuple[int, int], ...] = ()
    status: str = ""                          # beslissing: ACCEPTED/REJECTED/UNCERTAIN/HUMAN_REVIEW
    door: str = ""                            # regel/model/specificiteit
    reden: str = ""
    klasse: str = ""
    batch_unie: frozenset[str] | None = None  # None = onbekend (alleen-voorstellen-invoer)


@dataclass(frozen=True)
class Voorstel:
    label: str
    bron: str
    start: int
    eind: int
    klasse: str
    human_review: bool = False
    resolutie: tuple[str, ...] = ()           # regel-id's uit het spoor


@dataclass(frozen=True)
class Fout:
    primair: str
    soort: str
    secundair: tuple[str, ...] = ()
    gid: str = ""
    label: str = ""
    bron: str = ""
    start: int = 0
    eind: int = 0
    toelichting: str = ""
    handmatig: bool = False


@dataclass
class Uitslag:
    fouten: list[Fout] = field(default_factory=list)
    correct: int = 0
    debatable: int = 0


# --- invoer uit de keten ------------------------------------------------------------------------

def _vervallen(bewijs: Iterable[dict[str, Any]]) -> tuple[str, ...]:
    uit: list[str] = []
    for e in bewijs:
        if e.get("code") == "PRIORITY_APPLIED" and "vervalt:" in e.get("detail", ""):
            uit += [k.strip() for k in e["detail"].split("vervalt:", 1)[1].split(",") if k.strip()]
    return tuple(dict.fromkeys(uit))


def _kandidaat(k: dict[str, Any], b: dict[str, Any] | None, tekst: str | None, bron: str,
               batch_unie: frozenset[str] | None, twijfel: Iterable[dict[str, Any]] = ()) -> Kandidaat:
    span = k["span"]
    s, e = kern(tekst, span["start"], span["eind"]) if tekst is not None else (span["start"], span["eind"])
    opties = tuple(kern(tekst, o["start"], o["eind"]) if tekst is not None else (o["start"], o["eind"])
                   for o in k.get("spanopties", ()))
    b = b or {}
    # De resolver overschrijft de reden (bv. met R-ONGELDIG); de oorspronkelijke classifierreden
    # staat dan nog in de twijfel.
    reden = next((t.get("detail", "") for t in twijfel if t.get("reden") == "CLASSIFIER_ABSTAIN" and t.get("detail")),
                 b.get("reden", ""))
    return Kandidaat(label=k.get("label", ""), bron=bron, start=s, eind=e,
                     klassen=tuple(k.get("mogelijke_klassen", ())),
                     codes=frozenset(x["code"] for x in k.get("bewijs", ()) if x["code"] != "PRIORITY_APPLIED"),
                     vervallen=_vervallen(k.get("bewijs", ())), opties=opties, status=b.get("status", ""),
                     door=b.get("door", ""), reden=reden, klasse=b.get("klasse", ""),
                     batch_unie=batch_unie)


def uit_elementen(elementen: list[dict[str, Any]], tekst: str | None = None, bron: str = "",
                  granulariteit: str | None = None) -> tuple[list[Voorstel], list[Kandidaat]]:
    """Voorstellen en hun kandidaten uit `element`-events of een run-export (alleen voorgestelden).

    De batch-unie is hier onvolledig: afgewezen kandidaten ontbreken. Bij één universele batch is de
    unie over de zichtbare modelkandidaten wel een **ondergrens** van de echte, en een keuze die daarin
    staat, stond zeker in de batch-enum – leakage vaststellen op die ondergrens is dus veilig. Bij een
    andere of onbekende indeling blijft de unie onbekend.
    """
    voorstellen, kandidaten = [], {}
    for el in elementen:
        spoor = el.get("trace") or {}
        k = spoor.get("kandidaat") or {}
        a = (el.get("ankers") or [None])[0]
        if a is None:
            continue
        s, e = kern(tekst, a["start"], a["eind"]) if tekst is not None else (a["start"], a["eind"])
        voorstellen.append(Voorstel(label=k.get("label", ""), bron=bron, start=s, eind=e, klasse=el.get("klasse", ""),
                                    human_review=el.get("aandacht") == "geel",
                                    resolutie=tuple(t.get("regel", "") for t in spoor.get("resolutie") or ())))
        if k:                                   # legacy-elementen hebben geen kandidaatspoor
            kandidaten.setdefault(k.get("label", ""), _kandidaat(k, spoor.get("beslissing"), tekst, bron, None,
                                                                 spoor.get("twijfel") or ()))
    if granulariteit == "universeel":
        unie = frozenset(x for kk in kandidaten.values() if kk.door == "model" for x in (*kk.klassen, GEEN_ANNOTATIE))
        kandidaten = {lab: replace(kk, batch_unie=unie) if kk.door == "model" else kk for lab, kk in kandidaten.items()}
    return voorstellen, list(kandidaten.values())


def uit_uitkomst(uitkomst: Any, tekst: str | None = None, bron: str = "",
                 granulariteit: str = "universeel") -> tuple[list[Voorstel], list[Kandidaat]]:
    """Voorstellen én alle kandidaten uit `keten.Uitkomst` (harnas). De batch-unie wordt herleid uit
    de kandidaten die het model kreeg, met dezelfde batchindeling als de keten."""
    from agent.jas_pipeline.classificatie import batches

    per_label = {k.label: k for k in uitkomst.fusie.kandidaten}
    beslissingen = {b.label: b for b in uitkomst.beslissingen}
    naar_model = [per_label[b.label] for b in uitkomst.beslissingen if b.door == "model" and b.label in per_label]
    unie: dict[str, frozenset[str]] = {}
    for batch in batches(naar_model, granulariteit):
        u = frozenset(x for k in batch for x in k.toegestane_beslissingen())
        unie.update({k.label: u for k in batch})
    twijfels = {}
    for v in uitkomst.voorstellen:
        spoor = v.get("trace") or {}
        twijfels.setdefault(spoor.get("kandidaat", {}).get("label", ""), spoor.get("twijfel") or ())
    kandidaten = []
    for label, k in per_label.items():
        d = {"label": label, "span": k.span.model_dump(), "mogelijke_klassen": list(k.possible_classes),
             "bewijs": [e.model_dump() for e in k.evidence],
             "spanopties": [{"start": o.span.start, "eind": o.span.eind} for o in k.span_options]}
        b = beslissingen.get(label)
        kandidaten.append(_kandidaat(d, b.model_dump(mode="json") if b else None, tekst, bron, unie.get(label),
                                     twijfels.get(label, ())))
    voorstellen, _ = uit_elementen(uitkomst.voorstellen, tekst, bron)
    return voorstellen, kandidaten


# --- classificatie ------------------------------------------------------------------------------

def _fout(primair: str, secundair: Iterable[str] = (), **kw: Any) -> Fout:
    sec = tuple(dict.fromkeys(c for c in secundair if c != primair))
    return Fout(primair=primair, soort=CODES[primair][1], secundair=sec, **kw)


def _contract(k: Kandidaat | None) -> tuple[str, ...]:
    """De technische codes van een beslissing: contractfout (met leakage/hypothese) of abstain."""
    if k is None:
        return ()
    if k.reden.startswith(_CONTRACT[0]):
        gekozen = k.reden.split(":", 1)[1]
        uit = ["CLASSIFIER_CONTRACT_ERROR"]
        if k.batch_unie is not None and gekozen in k.batch_unie:
            uit.append("CLASSIFIER_CROSS_CANDIDATE_LEAKAGE")
        if gekozen in k.vervallen:
            uit.append("HYPOTHESIS_ERROR")
        return tuple(uit)
    if k.reden.startswith(_CONTRACT[1]):
        return ("CLASSIFIER_CONTRACT_ERROR",)
    if k.reden in _ABSTAIN:
        return ("CLASSIFIER_ABSTAIN",)
    return ()


def _sterk_voor(k: Kandidaat | None, klasse: str) -> bool:
    return k is not None and any(KLASSE_VAN_BEWIJS.get(c) == klasse for c in k.codes & STERK_BEWIJS)


def _richting(voor: tuple[int, int], gold: tuple[int, int]) -> str:
    if voor[0] <= gold[0] and gold[1] <= voor[1]:
        return "SPAN_TOO_WIDE"
    if gold[0] <= voor[0] and voor[1] <= gold[1]:
        return "SPAN_TOO_NARROW"
    return ""


def classificeer(gold: list[dict[str, Any]], voorstellen: list[Voorstel], kandidaten: list[Kandidaat],
                 bron: str = "", correcties: dict[str, dict[str, Any]] | None = None) -> Uitslag:
    """Per gold-element (en per overbodig voorstel) de fout, of niets als het klopt.

    `gold`: elementen met `gid`, `start`, `eind` (al op kern genormaliseerd), `klasse` en optioneel
    `annotation_status`. Positie = (bron, start, eind); `bron` is de casus of bronnode.
    `correcties`: gid of label → {"primair", "secundair", "toelichting"} uit de checklist (§14).
    """
    kand = {k.label: k for k in kandidaten}
    op_plek: dict[tuple[int, int], list[Kandidaat]] = {}
    for k in kandidaten:
        op_plek.setdefault((k.start, k.eind), []).append(k)
    uit = Uitslag()
    gebruikt: set[int] = set()                     # indexen van voorstellen die aan gold gekoppeld zijn
    debatable_plekken = set()

    for g in gold:
        plek = (g["start"], g["eind"])
        if g.get("annotation_status") == "debatable":
            uit.debatable += 1
            debatable_plekken.add(plek)
            continue
        klasse, gid = g["klasse"], g.get("gid", "")
        basis = dict(gid=gid, bron=bron, start=plek[0], eind=plek[1])
        exact = [i for i, v in enumerate(voorstellen) if (v.start, v.eind) == plek]
        raak = [i for i in exact if voorstellen[i].klasse == klasse]
        if raak:
            i = raak[0]
            gebruikt.add(i)
            v = voorstellen[i]
            techniek = _contract(kand.get(v.label))
            if techniek:
                uit.fouten.append(_fout(techniek[0], techniek[1:], label=v.label, **basis,
                                        toelichting="juiste klasse, maar via een contractfout als twijfel voorgelegd"))
            elif _REVIEW_ONGELDIG in v.resolutie:
                uit.fouten.append(_fout("REVIEW_CONTRACT_ERROR", label=v.label, **basis,
                                        toelichting="juiste klasse, maar de reviewer gaf ongeldige uitvoer"))
            else:
                uit.correct += 1
            continue

        ter_plekke = op_plek.get(plek, [])
        k = ter_plekke[0] if ter_plekke else None
        if exact:                                  # juiste span, verkeerde klasse
            i = exact[0]
            gebruikt.add(i)
            v = voorstellen[i]
            kv = kand.get(v.label) or k
            techniek = _contract(kv)
            if kv is not None and klasse not in kv.klassen:
                prim = "HYPOTHESIS_ERROR" if klasse in kv.vervallen else "POSSIBLE_CLASS_ERROR"
                uit.fouten.append(_fout(prim, techniek, label=v.label, **basis,
                                        toelichting=f"{klasse} niet aangeboden; voorgesteld: {v.klasse}"))
            elif techniek:
                uit.fouten.append(_fout(techniek[0], techniek[1:], label=v.label, **basis,
                                        toelichting=f"contractfout; voorgesteld: {v.klasse}"))
            elif kv is not None and kv.door == "model" and kv.klasse == klasse and v.klasse != klasse:
                uit.fouten.append(_fout("REVIEW_ERROR", label=v.label, **basis,
                                        toelichting=f"classifier koos {klasse}, na review {v.klasse}"))
            else:
                sec = ["UNCERTAINTY_ERROR"] if not v.human_review and _sterk_voor(kv, klasse) else []
                if kv is not None and kv.door == "model" and kv.klasse != klasse and any(
                        r.startswith("R-") and r != _REVIEW_ONGELDIG for r in v.resolutie):
                    sec.append("REVIEW_ERROR")
                prim = "CLASSIFIER_ERROR" if kv is None or kv.door == "model" else "EVIDENCE_CLASS_MAPPING_ERROR"
                uit.fouten.append(_fout(prim, sec, label=v.label, **basis,
                                        toelichting=f"{klasse} aangeboden, {v.klasse} gekozen"))
            continue

        if k is not None:                          # kandidaat op de juiste plek, maar geen voorstel
            techniek = _contract(k)
            if klasse not in k.klassen:
                prim = "HYPOTHESIS_ERROR" if klasse in k.vervallen else "POSSIBLE_CLASS_ERROR"
                uit.fouten.append(_fout(prim, techniek, label=k.label, **basis,
                                        toelichting=f"{klasse} niet aangeboden ({', '.join(k.klassen)})"))
            elif techniek:
                uit.fouten.append(_fout(techniek[0], techniek[1:], label=k.label, **basis))
            elif k.door == "specificiteit":
                uit.fouten.append(_fout("HYPOTHESIS_ERROR", label=k.label, **basis,
                                        toelichting="door voorrang afgewezen"))
            elif k.reden.startswith("VALIDATION_ERROR"):
                uit.fouten.append(_fout("VALIDATION_ERROR", label=k.label, **basis, toelichting=k.reden))
            else:
                sec = ["UNCERTAINTY_ERROR"] if _sterk_voor(k, klasse) else []
                uit.fouten.append(_fout("CLASSIFIER_ERROR", sec, label=k.label, **basis,
                                        toelichting=f"{klasse} aangeboden, model: geen annotatie"))
            continue

        optie = next((kk for kk in kandidaten if plek in kk.opties), None)
        overlap_v = [(i, v) for i, v in enumerate(voorstellen)
                     if v.start < plek[1] and plek[0] < v.eind and v.klasse == klasse]
        overlap_k = [kk for kk in kandidaten if kk.start < plek[1] and plek[0] < kk.eind and klasse in kk.klassen]
        if optie is not None:                      # de grens bestond als optie, maar werd niet gekozen
            richting = _richting((optie.start, optie.eind), plek)
            gebruikt.update(i for i, v in overlap_v if v.label == optie.label)
            uit.fouten.append(_fout("CLASSIFIER_ERROR", [richting] if richting else [], label=optie.label, **basis,
                                    toelichting="gold-grens stond als spanoptie klaar"))
        elif overlap_v or overlap_k:
            dichtst = overlap_v[0][1] if overlap_v else overlap_k[0]
            gebruikt.update(i for i, _ in overlap_v[:1])
            richting = _richting((dichtst.start, dichtst.eind), plek)
            uit.fouten.append(_fout("DETECTOR_SPAN_ERROR", [richting] if richting else [], label=dichtst.label, **basis,
                                    toelichting=f"dichtstbijzijnde span {dichtst.start}–{dichtst.eind}"))
        else:
            uit.fouten.append(_fout("CANDIDATE_MISSED", **basis))

    for i, v in enumerate(voorstellen):             # overbodig: geen gold op deze plek
        if i in gebruikt or (v.start, v.eind) in debatable_plekken:
            continue
        k = kand.get(v.label)
        techniek = _contract(k)
        basis = dict(label=v.label, bron=bron, start=v.start, eind=v.eind)
        if techniek:
            uit.fouten.append(_fout(techniek[0], techniek[1:], **basis, toelichting=f"overbodig: {v.klasse}"))
        elif k is not None and k.door == "regel":
            uit.fouten.append(_fout("DETECTOR_ERROR", **basis, toelichting=f"regel vuurde ten onrechte: {v.klasse}"))
        else:
            sec = ["REVIEW_CONTRACT_ERROR"] if _REVIEW_ONGELDIG in v.resolutie else []
            uit.fouten.append(_fout("CLASSIFIER_ERROR", sec, **basis, toelichting=f"overbodig: {v.klasse}"))

    if correcties:
        uit.fouten = [pas_toe(f, correcties.get(f.gid) or correcties.get(f.label)) for f in uit.fouten]
    return uit


def pas_toe(f: Fout, correctie: dict[str, Any] | None) -> Fout:
    """Een handmatige toewijzing uit de checklist (§14) vervangt de automatische."""
    if not correctie:
        return f
    prim = correctie["primair"]
    if prim not in CODES or prim in ALLEEN_SECUNDAIR | GEGENEREERD:
        raise ValueError(f"{prim!r} kan geen primaire code zijn")
    sec = tuple(correctie.get("secundair", ()))
    onbekend = [c for c in sec if c not in CODES]
    if onbekend:
        raise ValueError(f"onbekende code: {onbekend}")
    return replace(f, primair=prim, soort=correctie.get("soort", CODES[prim][1]), secundair=sec,
                   toelichting=correctie.get("toelichting", f.toelichting), handmatig=True)


def tel(uitslagen: Iterable[Uitslag]) -> dict[str, Any]:
    """Tellingen voor het rapport. `debatable` staat apart en zit in geen enkele noemer."""
    prim, sec, soort = Counter(), Counter(), Counter()
    correct = debatable = handmatig = 0
    for u in uitslagen:
        correct += u.correct
        debatable += u.debatable
        for f in u.fouten:
            prim[f.primair] += 1
            soort[f.soort] += 1
            sec.update(f.secundair)
            handmatig += f.handmatig
    return {"primair": dict(prim.most_common()), "secundair": dict(sec.most_common()),
            "per_soort": dict(soort.most_common()), "correct": correct, "debatable": debatable,
            "handmatig": handmatig}
