"""Voor/na-vergelijking van twee rapporten van `eval.compare_pipelines`.

Twee metingen zijn alleen vergelijkbaar als ze dezelfde referentie, casusset, model, provider en
ketenvlaggen hebben (`manifest.VERGELIJKBAAR`); anders weigert dit script. Wat mag verschillen is de
code – dat is wat er gemeten wordt.

Per metric de delta van het gemiddelde, plus de vlag `binnen_spreiding`: overlappen de banden
(min–max over de rondes) van voor en na, dan is het verschil niet van de run-variatie te
onderscheiden. Per element (op positie, niet op kandidaat-id) wat er veranderde.

    python -m eval.vergelijk_rapporten voor.json na.json [--md uit.md] [--json uit.json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from eval import manifest
from eval.compare_pipelines import analyseer

ROUTE = "hybrid_v1"
METRICS = ("micro_f1", "micro_precision", "micro_ankerdekking", "macro_f1", "onbetwist_precision",
           "onbetwist_ankerdekking", "exact_span", "geel_aandeel")


class Onvergelijkbaar(ValueError):
    pass


def _analyse(rapport: dict[str, Any]) -> dict[str, Any]:
    return analyseer(rapport)


def _overlap(a: dict | None, b: dict | None) -> bool | None:
    if not a or not b:
        return None
    return a["min"] <= b["max"] and b["min"] <= a["max"]


def _delta(a, b):
    return None if a is None or b is None else round(b - a, 3)


def vergelijk(voor: dict[str, Any], na: dict[str, Any]) -> dict[str, Any]:
    if not voor.get("manifest") or not na.get("manifest"):
        raise Onvergelijkbaar("rapport zonder manifest: van vóór het meetharnas, niet vergelijkbaar")
    verschil = manifest.verschillen(voor["manifest"], na["manifest"])
    for veld in ("casus_ids", "herhalingen", "offline"):
        if voor["manifest"].get(veld) != na["manifest"].get(veld):
            verschil.append(veld)
    if verschil:
        raise Onvergelijkbaar(f"manifesten verschillen op: {', '.join(verschil)}")
    av, an = _analyse(voor)["routes"][ROUTE], _analyse(na)["routes"][ROUTE]
    metrics = {m: {"voor": av.get(m), "na": an.get(m), "delta": _delta(av.get(m), an.get(m)),
                   "binnen_spreiding": _overlap(av["spreiding"].get(m), an["spreiding"].get(m))} for m in METRICS}
    klassen = sorted(av["spreiding"]["per_klasse_f1"].keys() | an["spreiding"]["per_klasse_f1"].keys())
    per_klasse = {}
    for k in klassen:
        bv, bn = av["spreiding"]["per_klasse_f1"].get(k), an["spreiding"]["per_klasse_f1"].get(k)
        bv2, bn2 = av["spreiding"]["per_klasse_ankerdekking"].get(k), an["spreiding"]["per_klasse_ankerdekking"].get(k)
        per_klasse[k] = {"f1_voor": bv, "f1_na": bn, "f1_binnen_spreiding": _overlap(bv, bn),
                         "ankerdekking_voor": bv2, "ankerdekking_na": bn2,
                         "ankerdekking_binnen_spreiding": _overlap(bv2, bn2)}
    ev, en = av["elementen"], an["elementen"]
    elementen = {}
    for plek in sorted(ev.keys() | en.keys()):
        a, b = ev.get(plek), en.get(plek)
        if a and b and a["klassen"] == b["klassen"] and a["geel"] == b["geel"]:
            continue
        elementen[plek] = {"tekst": (a or b)["tekst"], "voor": a and {"klassen": a["klassen"], "geel": a["geel"]},
                           "na": b and {"klassen": b["klassen"], "geel": b["geel"]}}
    return {"route": ROUTE, "voor_git": voor["manifest"]["git_sha"], "na_git": na["manifest"]["git_sha"],
            "casussen": na["manifest"]["casussen"], "metrics": metrics, "per_klasse": per_klasse,
            "elementen": elementen}


def markdown(v: dict[str, Any]) -> str:
    def p(x):
        return "–" if x is None else f"{100 * x:.0f}%"

    def band(b):
        return "–" if not b else f"{100 * b['min']:.0f}–{100 * b['max']:.0f}%"

    def vlag(x):
        return "–" if x is None else ("binnen spreiding" if x else "**buiten spreiding**")
    regels = [f"Voor `{v['voor_git'][:7]}` → na `{v['na_git'][:7]}`, casussen `{v['casussen']}`.", "",
              "| maat | voor | na | delta | |", "|---|---:|---:|---:|---|"]
    regels += [f"| {m} | {p(x['voor'])} | {p(x['na'])} | {p(x['delta'])} | {vlag(x['binnen_spreiding'])} |"
               for m, x in v["metrics"].items()]
    regels += ["", "| klasse | F1 voor | F1 na | | ankerdekking voor | na | |", "|---|---|---|---|---|---|---|"]
    regels += [f"| {k} | {band(x['f1_voor'])} | {band(x['f1_na'])} | {vlag(x['f1_binnen_spreiding'])} | "
               f"{band(x['ankerdekking_voor'])} | {band(x['ankerdekking_na'])} | {vlag(x['ankerdekking_binnen_spreiding'])} |"
               for k, x in v["per_klasse"].items()]
    if v["elementen"]:
        regels += ["", "| plek | tekst | voor | na |", "|---|---|---|---|"]
        regels += [f"| {plek} | {x['tekst'][:60]} | {x['voor'] or '–'} | {x['na'] or '–'} |"
                   for plek, x in v["elementen"].items()]
    return "\n".join(regels) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("voor", type=Path)
    ap.add_argument("na", type=Path)
    ap.add_argument("--md", type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    try:
        v = vergelijk(json.loads(args.voor.read_text()), json.loads(args.na.read_text()))
    except Onvergelijkbaar as exc:
        print(f"niet vergelijkbaar: {exc}")
        return 2
    tekst = markdown(v)
    print(tekst)
    if args.md:
        args.md.write_text(tekst, encoding="utf-8")
    if args.json:
        args.json.write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
