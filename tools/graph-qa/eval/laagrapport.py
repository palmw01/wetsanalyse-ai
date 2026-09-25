"""Rapport per laag (onderzoek-empirische-validatie §2.2, §9, §14; validatieplan V6).

Eén rapport per run-set (een `compare_pipelines`-uitvoer). Per laag de metrics van §9, uitgesplitst
per familie en per tekstsoort, met de fouten gescheiden naar juridisch, technisch en evaluatie.
**Er is geen totaalscore**: een gemiddelde over lagen verstopt precies waar het misgaat.

Drie regels uit §9:

- elke metric draagt de referentiestatus, het aantal casussen en runs en de referentiehash;
- tegen iets anders dan `adjudicated` heet recall `ankerdekking`;
- onder n = 20 staat naast het percentage de teller en noemer.

De **relationele checklist** (§14) komt als bijlage mee: per fout tegen gold een rij met de twaalf
vragen. Wat uit de keten af te leiden is, is vooraf ingevuld; de rest is leeg. Een ingevulde checklist
gaat terug via `--checklist`. De correcties daarin vervangen dan de automatische foutcode, en de
antwoorden op vraag 7–9 tellen als bewijs vóór of tegen de frames van §15.

    python -m eval.laagrapport ab.json --md laag.md [--json laag.json] [--bijlage checklist.json]
    python -m eval.laagrapport ab.json --md laag.md --checklist checklist-ingevuld.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from agent.jas_pipeline.besluit import STERK_BEWIJS
from eval.beslisstabiliteit import rapport as beslisrapport
from eval.compare_pipelines import _v1
from eval.fouttaxonomie import CODES, Uitslag, classificeer, tel, uit_elementen, uit_register
from eval.metrieken import (
    Ref, classificatie_metrieken, contract_metrieken, controleer_status, kandidaat_metrieken, kern,
    laagste_status, recall_naam,
)
from eval.referentieset import sethash

GENERIEK = frozenset({"SUBJECT_NP", "OBJECT_NP", "ENUMERATED_NP"})
CHECKLIST = (
    ("span_aanwezig", "Juiste span aanwezig: als kandidaat, als optie, of niet?"),
    ("clause_aanwezig", "Juiste clause aanwezig? Staat de bijzin of het segment als kandidaat?"),
    ("dependency_juist", "Juiste dependency: klopt de parse op het kopwoord en op de relatie met het predicaat?"),
    ("detector_juist", "Juiste detector: welke regel had moeten vuren, en vuurde hij?"),
    ("hypothese_juist", "Juiste hypothese: stond de gold-klasse in possible_classes?"),
    ("bewijs_voor_gold", "Bewijs voor de gold-klasse: welk bewijs steunde hem, en was het sterk of generiek?"),
    ("predicaatrelatie_nodig", "Relatie met het predicaat nodig om de klasse te bepalen? (NormFrame)"),
    ("afleiding_nodig", "Afleiding nodig? output = f(input) (DerivationFrame)"),
    ("vergelijking_nodig", "Vergelijking nodig? links, operator, rechts (ComparisonFrame)"),
    ("classifier_interface", "Classifier-interface: contractfout, leakage, ontbrekende uitvoer?"),
    ("juridische_classifierfout", "Juridische classifierfout: geldige keuze, gold aangeboden, toch fout?"),
    ("onzekerheid_had_moeten_triggeren", "Had de onzekerheid moeten triggeren? Zo ja: welk signaal?"),
)
FRAMEVRAGEN = {"predicaatrelatie_nodig": "NormFrame", "afleiding_nodig": "DerivationFrame",
               "vergelijking_nodig": "ComparisonFrame"}


# --- per run ------------------------------------------------------------------------------------

def _gold(c: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"gid": g["gid"], "start": s, "eind": e, "klasse": g["klasse"],
             "annotation_status": g.get("annotation_status")}
            for g in c["gold"] for s, e in [kern(c["tekst"], g["start"], g["eind"])]]


def _kandidaten(run: dict[str, Any], c: dict[str, Any]) -> list[dict[str, Any]]:
    """Het register in de vorm van `kandidaat_metrieken`, op kern-posities."""
    uit = []
    for b in run.get("beslissingen") or []:
        s, e = kern(c["tekst"], b["start"], b["eind"])
        uit.append({"bron": c["id"], "start": s, "eind": e,
                    "possible_classes": [] if b["door"] == "specificiteit" else b["mogelijke_klassen"],
                    "detectors": b.get("detectoren", []), "bewijs": b.get("bewijs", []),
                    "opties": [kern(c["tekst"], o[0], o[1]) for o in b.get("opties", [])],
                    "door": b["door"]})
    return uit


def _iou(voorspeld: list[Ref], referentie: list[Ref]) -> list[float]:
    """IoU over gekoppelde paren: per referentie de best overlappende voorspelling van dezelfde klasse."""
    uit = []
    for r in referentie:
        beste = 0.0
        for v in voorspeld:
            if v.bron == r.bron and v.klasse == r.klasse and v.start < r.eind and r.start < v.eind:
                doorsnede = min(v.eind, r.eind) - max(v.start, r.start)
                beste = max(beste, doorsnede / (max(v.eind, r.eind) - min(v.start, r.start)))
        if beste:
            uit.append(beste)
    return uit


def _uitslag(run: dict[str, Any], c: dict[str, Any], correcties: dict[str, Any]) -> Uitslag:
    if run.get("beslissingen"):
        voorstellen, kandidaten = uit_register(run["beslissingen"], run["na_keten"], c["tekst"], c["id"],
                                               run.get("granulariteit") or "universeel")
    else:                                   # oud rapport zonder register: alleen voorstellen
        voorstellen, kandidaten = uit_elementen(run["na_keten"], c["tekst"], c["id"])
    return classificeer(_gold(c), voorstellen, kandidaten, bron=c["id"],
                        correcties={k.split("/", 1)[1]: v for k, v in correcties.items()
                                    if k.startswith(c["id"] + "/")})


# --- per groep ----------------------------------------------------------------------------------

def _gem(xs: list[float | None]) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def _groep(runs: list[dict[str, Any]], casussen: dict[str, dict[str, Any]], status: str,
           correcties: dict[str, Any]) -> dict[str, Any]:
    ids = sorted({r["casus"] for r in runs})
    kand_m, klas_m, ious, uitslagen, contract, reviewload = [], [], [], [], [], Counter()
    generiek = geblokkeerd = kandidaten_n = model_n = det_n = 0
    fp_per_code: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for ronde in sorted({r["ronde"] for r in runs}):
        deze = [r for r in runs if r["ronde"] == ronde]
        betwist = {(r["casus"], g["start"], g["eind"]) for r in deze for g in _gold(casussen[r["casus"]])
                   if g["annotation_status"] == "debatable"}
        ref = [Ref(r["casus"], g["start"], g["eind"], g["klasse"]) for r in deze
               for g in _gold(casussen[r["casus"]]) if g["annotation_status"] != "debatable"]
        vs = []
        for r in deze:
            c = casussen[r["casus"]]
            for e in r["na_keten"]:
                a = (e.get("ankers") or [None])[0]
                if a is not None:
                    p = Ref(c["id"], *kern(c["tekst"], a["start"], a["eind"]), e.get("klasse", ""))
                    if (p.bron, p.start, p.eind) not in betwist:
                        vs.append(p)
        klas_m.append(classificatie_metrieken(vs, ref, status))
        ious += _iou(vs, ref)
        kand = [k for r in deze for k in _kandidaten(r, casussen[r["casus"]])]
        if kand:
            kand_m.append(kandidaat_metrieken(kand, ref, status))
        ref_plekken = {(x.bron, x.start, x.eind) for x in ref}
        for k in kand:
            kandidaten_n += 1
            generiek += bool(k["bewijs"]) and set(k["bewijs"]) <= GENERIEK
            model_n += k["door"] == "model"
            det_n += k["door"] == "regel"
            geblokkeerd += k["door"] == "model" and bool(set(k["bewijs"]) & STERK_BEWIJS)
            for code in k["bewijs"]:
                fp_per_code[code][1] += 1
                fp_per_code[code][0] += (k["bron"], k["start"], k["eind"]) not in ref_plekken
        for r in deze:
            uitslagen.append(_uitslag(r, casussen[r["casus"]], correcties))
            if r.get("beslissingen"):
                contract.append(contract_metrieken(r["beslissingen"], r.get("granulariteit") or "universeel",
                                                   r["meting"].get("resolutie")))
            reviewload.update(r["meting"].get("reviewload") or {})

    fouten = tel(uitslagen)
    per_laag: dict[str, Counter] = defaultdict(Counter)
    for u in uitslagen:
        for f in u.fouten:
            per_laag[CODES[f.primair][0] or "(geen laag)"][f.soort] += 1
    beslis = {}
    for cid in ids:
        registers = [r["beslissingen"] for r in sorted(runs, key=lambda r: r["ronde"])
                     if r["casus"] == cid and r.get("beslissingen")]
        if len(registers) >= 2:
            beslis[cid] = beslisrapport(registers)
    som_contract = {k: sum(m[k] or 0 for m in contract) for k in (contract[0] if contract else {})
                    if not k.endswith("_rate")}

    def deel(a: int, b: int) -> dict[str, Any]:
        return {"waarde": round(a / b, 3) if b else None, "teller": a, "noemer": b}

    return {
        "casussen": ids, "n_casussen": len(ids), "runs": len(runs), "referentie_status": status,
        "kandidaatlaag": {
            "candidate_recall": _gem([m["candidate_recall"] for m in kand_m]),
            "candidate_recall_incl_opties": _gem([m["candidate_recall_incl_opties"] for m in kand_m]),
            "possible_class_recall": _gem([m["candidate_recall_met_klasse"] for m in kand_m]),
            "candidate_precision (diagnostisch)": _gem([m["candidate_precision"] for m in kand_m]),
            "kandidaten_per_gold": _gem([m["kandidaten_per_referentie"] for m in kand_m]),
            "generiek_aandeel": deel(generiek, kandidaten_n),
            "unieke_bijdrage_per_detector": dict(sum((Counter(m["unieke_bijdrage_per_detector"]) for m in kand_m),
                                                     Counter())),
            "fp_rate_per_bewijscode": {c: deel(fp, n) for c, (fp, n) in sorted(fp_per_code.items())},
        },
        "spanlaag": {
            "exact_span": _gem([m["exact_span"] for m in klas_m]),
            "partial_overlap_zelfde_klasse": _gem([m["partial_overlap_zelfde_klasse"] for m in klas_m]),
            "mean_iou": _gem(ious),
            "detector_span_error": fouten["primair"].get("DETECTOR_SPAN_ERROR", 0),
            "span_too_wide": fouten["secundair"].get("SPAN_TOO_WIDE", 0),
            "span_too_narrow": fouten["secundair"].get("SPAN_TOO_NARROW", 0),
        },
        "classificatie": {
            "micro_precision": _gem([m["micro"]["precision"] for m in klas_m]),
            recall_naam(status): _gem([m["micro"]["recall"] for m in klas_m]),
            "micro_f1": _gem([m["micro"]["f1"] for m in klas_m]),
            "macro_f1": _gem([m["macro_f1"] for m in klas_m]),
            "per_klasse_f1": {k: _gem([m["per_klasse"].get(k, {}).get("f1") for m in klas_m])
                              for k in sorted({k for m in klas_m for k in m["per_klasse"]})},
            "debatable_uitgesloten": fouten["debatable"],
        },
        "proces": {
            "deterministisch": deel(det_n, kandidaten_n), "classifier": deel(model_n, kandidaten_n),
            "geblokkeerd_deterministisch": geblokkeerd,
            "reviewload": dict(reviewload),
        },
        "classifier_contract": {**som_contract,
            "contract_error_rate": deel(som_contract.get("invalid_class_selections", 0)
                                        + som_contract.get("invalid_option_selections", 0)
                                        + som_contract.get("invalid_tool_outputs", 0),
                                        som_contract.get("modelbeslissingen", 0)),
            "reviewer_contract_error_rate": deel(som_contract.get("reviewer_contract_errors", 0),
                                                 som_contract.get("reviewer_gevallen", 0))},
        "stabiliteit": {
            "kandidaatbeslisstabiliteit": _gem([b["kandidaatbeslisstabiliteit"] for b in beslis.values()]),
            "detectie_stabiel": _gem([b["detectie_stabiel"] for b in beslis.values()]),
            "fingerprint_drift": sum(len(b["fingerprint_drift"]) for b in beslis.values()),
        },
        "fouten": {**fouten, "per_laag": {k: dict(v) for k, v in sorted(per_laag.items())}},
    }


# --- checklist ----------------------------------------------------------------------------------

def checklist(rapport: dict[str, Any], route: str = "hybrid_v1") -> list[dict[str, Any]]:
    """De bijlage: één rij per fout tegen gold (eerste ronde), met wat af te leiden is al ingevuld."""
    casussen = {c["id"]: _v1(c) for c in rapport["casussen"]}
    runs = [r for r in rapport["runs"] if r["route"] == route and not r["fout"]]
    eerste = min((r["ronde"] for r in runs), default=1)
    rijen = []
    for r in (r for r in runs if r["ronde"] == eerste):
        c = casussen[r["casus"]]
        _, kandidaten = (uit_register(r["beslissingen"], r["na_keten"], c["tekst"], c["id"],
                                      r.get("granulariteit") or "universeel")
                         if r.get("beslissingen") else uit_elementen(r["na_keten"], c["tekst"], c["id"]))
        klasse_van = {g["gid"]: g["klasse"] for g in _gold(c)}
        for f in _uitslag(r, c, {}).fouten:
            if not f.gid:
                continue
            k = next((x for x in kandidaten if (x.start, x.eind) == (f.start, f.eind)), None)
            optie = any((f.start, f.eind) in x.opties for x in kandidaten)
            gk = klasse_van[f.gid]
            rij = {"sleutel": f"{c['id']}/{f.gid}", "fragment": c["tekst"][f.start:f.eind], "klasse": gk,
                   "automatisch": {"primair": f.primair, "secundair": list(f.secundair), "soort": f.soort},
                   "antwoorden": {n: None for n, _ in CHECKLIST}, "correctie": None}
            a = rij["antwoorden"]
            a["span_aanwezig"] = "kandidaat" if k else ("optie" if optie else "niet")
            if k:
                a["hypothese_juist"] = gk in k.klassen
                a["bewijs_voor_gold"] = ("sterk" if k.codes & STERK_BEWIJS else "generiek" if k.codes <= GENERIEK
                                         else "overig") if gk in k.klassen else "geen"
            a["classifier_interface"] = next((s for s in (f.primair, *f.secundair) if s in (
                "CLASSIFIER_CONTRACT_ERROR", "CLASSIFIER_ABSTAIN", "CLASSIFIER_CROSS_CANDIDATE_LEAKAGE")), "nee")
            a["juridische_classifierfout"] = f.primair == "CLASSIFIER_ERROR"
            rijen.append(rij)
    return rijen


def lees_checklist(rijen: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Correcties per `casus/gid`, en de telling van de framevragen 7–9 (§14 → §15)."""
    correcties = {r["sleutel"]: r["correctie"] for r in rijen if r.get("correctie")}
    frames = {naam: Counter(str(r["antwoorden"].get(v)) for r in rijen) for v, naam in FRAMEVRAGEN.items()}
    return correcties, {naam: {"ja": c.get("True", 0) + c.get("ja", 0), "nee": c.get("False", 0) + c.get("nee", 0),
                               "open": c.get("None", 0)} for naam, c in frames.items()}


# --- rapport ------------------------------------------------------------------------------------

def bouw(rapport: dict[str, Any], route: str = "hybrid_v1",
         ingevuld: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    casussen = {c["id"]: _v1(c) for c in rapport["casussen"]}
    status = laagste_status(controleer_status(c) for c in rapport["casussen"])
    runs = [r for r in rapport["runs"] if r["route"] == route and not r["fout"]]
    correcties, frames = lees_checklist(ingevuld) if ingevuld else ({}, None)
    groepen: dict[str, list[dict[str, Any]]] = {"alle": runs}
    for r in runs:
        c = casussen[r["casus"]]
        groepen.setdefault(f"familie {c['familie']}", []).append(r)
        groepen.setdefault(f"tekstsoort {c.get('tekstsoort', 'onbekend')}", []).append(r)
    return {
        "route": route, "referentie_status": status, "recall_heet": recall_naam(status),
        "referentie_sha256": sethash([casussen[i] for i in sorted(casussen)]),
        "runs": len(runs), "herhalingen": len({r["ronde"] for r in runs}),
        "handmatige_correcties": len(correcties), "frames": frames,
        "groepen": {naam: _groep(rs, casussen, status, correcties) for naam, rs in groepen.items()},
    }


GETAL = frozenset({"kandidaten_per_gold", "geblokkeerd_deterministisch", "detector_span_error", "span_too_wide",
                   "span_too_narrow", "debatable_uitgesloten", "fingerprint_drift"})


def _fmt(x: Any, metric: str = "") -> str:
    if metric in GETAL and isinstance(x, (int, float)):
        return f"{x:.2f}" if isinstance(x, float) else str(x)
    if x is None:
        return "–"
    if isinstance(x, dict) and "teller" in x:
        if x["waarde"] is None:
            return "–"
        pct = f"{100 * x['waarde']:.0f}%"
        return f"{pct} ({x['teller']}/{x['noemer']})" if x["noemer"] < 20 else pct
    if isinstance(x, float):
        return f"{100 * x:.0f}%" if x <= 1 else f"{x:.2f}"
    if isinstance(x, dict):
        return ", ".join(f"{k}: {_fmt(v)}" for k, v in x.items()) or "–"
    return str(x)


LAGEN = ("kandidaatlaag", "spanlaag", "classificatie", "proces", "classifier_contract", "stabiliteit")


def markdown(r: dict[str, Any]) -> str:
    regels = [f"# Rapport per laag – {r['route']}", "",
              f"Referentie **{r['referentie_status']}** (sha256 `{r['referentie_sha256'][:12]}`), "
              f"{r['runs']} runs over {r['herhalingen']} herhaling(en). Recall heet hier *{r['recall_heet']}*. "
              "Geen totaalscore.", ""]
    if r["handmatige_correcties"]:
        regels += [f"{r['handmatige_correcties']} foutcode(s) uit de ingevulde checklist (§14).", ""]
    if r["frames"]:
        regels += ["Framevragen §14 (7–9): " + "; ".join(f"{n}: {v['ja']} ja, {v['nee']} nee, {v['open']} open"
                                                          for n, v in r["frames"].items()), ""]
    namen = list(r["groepen"])
    kop = ["| | " + " | ".join(namen) + " |", "|---|" + "---:|" * len(namen)]

    def tabel(waarden) -> bool:
        return isinstance(waarden, dict) and "teller" not in waarden

    for laag in LAGEN:
        metrics = r["groepen"]["alle"][laag]
        regels += [f"## {laag}", "", *kop]
        for metric, w in metrics.items():
            if not tabel(w):
                regels.append(f"| {metric} | " + " | ".join(_fmt(r["groepen"][g][laag].get(metric), metric)
                                                            for g in namen) + " |")
        for metric, w in metrics.items():
            if tabel(w):                     # per klasse, per bewijscode, …: een eigen tabel
                sleutels = sorted({k for g in namen for k in (r["groepen"][g][laag].get(metric) or {})})
                regels += ["", f"**{metric}**", "", *kop]
                regels += [f"| {k} | " + " | ".join(_fmt((r["groepen"][g][laag].get(metric) or {}).get(k), metric)
                                                    for g in namen) + " |" for k in sleutels]
        regels.append("")
    regels += ["## Fouten (primair, per soort)", "",
               "| groep | casussen | runs | juridisch | technisch | evaluatie | correct | debatable |",
               "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for g in namen:
        f = r["groepen"][g]["fouten"]
        regels.append(f"| {g} | {r['groepen'][g]['n_casussen']} | {r['groepen'][g]['runs']} | "
                      f"{f['per_soort'].get('juridisch', 0)} | {f['per_soort'].get('technisch', 0)} | "
                      f"{f['per_soort'].get('evaluatie', 0)} | {f['correct']} | {f['debatable']} |")
    alle = r["groepen"]["alle"]["fouten"]
    regels += ["", "**Per laag (alle):** " + _fmt({k: _fmt(v) for k, v in alle["per_laag"].items()}),
               "", "**Primair (alle):** " + _fmt(alle["primair"]),
               "", "**Secundair (alle):** " + _fmt(alle["secundair"]), "",
               "## Bijlage: relationele checklist (§14)", "",
               "Per fout tegen gold één rij (`--bijlage checklist.json`); wat af te leiden is, staat al ingevuld. "
               "Terug met `--checklist`: `correctie` vervangt de automatische code, vraag 7–9 tellen voor §15.", ""]
    regels += [f"{i}. {vraag}" for i, (_, vraag) in enumerate(CHECKLIST, 1)]
    return "\n".join(regels) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rapport")
    ap.add_argument("--route", default="hybrid_v1")
    ap.add_argument("--md")
    ap.add_argument("--json")
    ap.add_argument("--bijlage", help="schrijf de lege relationele checklist (§14) als JSON")
    ap.add_argument("--checklist", help="een ingevulde checklist: correcties en framevragen tellen mee")
    args = ap.parse_args()
    rapport = json.loads(Path(args.rapport).read_text(encoding="utf-8"))
    ingevuld = json.loads(Path(args.checklist).read_text(encoding="utf-8")) if args.checklist else None
    r = bouw(rapport, args.route, ingevuld)
    if args.json:
        Path(args.json).write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.bijlage:
        Path(args.bijlage).write_text(json.dumps(checklist(rapport, args.route), ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")
    md = markdown(r)
    if args.md:
        Path(args.md).write_text(md, encoding="utf-8")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
