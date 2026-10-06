"""Vooraf vastgelegde meetcriteria toetsen tegen een voor- en na-meting.

Een criteriabestand (YAML) legt **vóór** de wijziging vast wat die moet bereiken en wat hij niet mag
breken (onderzoek §18: geen criterium achteraf). Dit script toetst het tegen de deterministische
audit (`eval.detector_audit`, verplicht) en optioneel tegen modelrapporten
(`eval.compare_pipelines`).

    python -m eval.criteria criteria.yaml --audit-voor voor.json --audit-na na.json \\
        [--model-voor voor-model.json --model-na na-model.json] [--json uit.json]

Uitslag per regel: `geslaagd`, `gezakt` of `niet_gemeten` (er is geen modelrapport). Een regel met
`poort: false` is een waarneming: hij wordt gerapporteerd maar beslist niet. Exitcode 0 alleen als
elke poortregel geslaagd is – niet gemeten is niet geslaagd.

Regelsoorten (veld `soort`):

- `recall_niet_lager` – per klasse candidate recall (en met klasse) op v1 niet lager dan voor;
- `geen_verloren_ankers` – geen v1-anker verliest zijn kandidaat (S0);
- `anker_klasse_behouden` – v1-ankers van `klasse` (optioneel alleen `ankers: [casus/gid]`) houden
  een kandidaat mét die klasse als ze die voor hadden;
- `element_kandidaat` – conceptelement `casus/gid` heeft een kandidaat op precies zijn kernpositie
  (`core`, standaard ja) met `klasse` erin; `zonder_klasse` mag er dan níét in staan;
- `geen_klasse_op_tekst` – geen kandidaat in `casus` met kerntekst `tekst` (optioneel alleen die op
  `start`) draagt `klasse`; er moet er wel minstens één zijn;
- `alleen_toegestane_wijzigingen` – in v1 verandert alleen wat in `toegestaan: {casus: [tekst…]}`
  staat (nieuw, verdwenen of andere klassen op een positie);
- `model_min_niet_lager` – in het modelrapport is het minimum over de rondes van `metric` (of van
  `per_klasse_ankerdekking`/`per_klasse_f1` voor `klasse`) niet lager dan voor.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from eval import casusbron
from eval.detector_audit import klassenverschil
from eval.metrieken import kern

SOORTEN = ("recall_niet_lager", "geen_verloren_ankers", "anker_klasse_behouden", "element_kandidaat",
           "geen_klasse_op_tekst", "alleen_toegestane_wijzigingen", "model_min_niet_lager")


def _s0(audit: dict, casus: str) -> tuple[str, list[dict]]:
    c = audit["per_casus"].get(casus)
    if c is None:
        raise KeyError(f"casus {casus} staat niet in de audit")
    return c["tekst"], c["scenario"]["S0"]


def _op_plek(audit: dict, casus: str, start: int, eind: int) -> set[str] | None:
    tekst, rijen = _s0(audit, casus)
    hier = [r for r in rijen if kern(tekst, r["start"], r["eind"]) == (start, eind)]
    return {k for r in hier for k in r["possible_classes"]} if hier else None


def _v1_ankers(audit: dict) -> list[dict]:
    return audit["referentieankers"]


def _concept(casus: str) -> dict:
    return next(c for c in casusbron.laad(f"concept:{casus}"))


def toets(regel: dict, voor: dict, na: dict, model_voor: dict | None, model_na: dict | None) -> tuple[str, str]:
    s = regel["soort"]
    if s == "recall_niet_lager":
        kv, kn = voor["kandidaat_eval"]["per_klasse"], na["kandidaat_eval"]["per_klasse"]
        lager = [f"{k} {m}: {kv[k][m]} → {kn.get(k, {}).get(m)}" for k in kv for m in ("candidate_recall", "met_klasse")
                 if (kn.get(k, {}).get(m) or 0) < (kv[k][m] or 0)]
        return ("gezakt", "; ".join(lager)) if lager else ("geslaagd", "")
    if s == "geen_verloren_ankers":
        weg = sorted(set(voor["scenario"]["S0"]["gedekte_ankers"]) - set(na["scenario"]["S0"]["gedekte_ankers"]))
        return ("gezakt", ", ".join(weg)) if weg else ("geslaagd", "")
    if s == "anker_klasse_behouden":
        kies = set(regel.get("ankers") or [])
        kwijt = []
        for a in _v1_ankers(na):
            if a["klasse"] != regel["klasse"] or (kies and a["id"] not in kies):
                continue
            had = a["klasse"] in (_op_plek(voor, a["bron"], a["start"], a["eind"]) or set())
            heeft = a["klasse"] in (_op_plek(na, a["bron"], a["start"], a["eind"]) or set())
            if had and not heeft:
                kwijt.append(a["id"])
        if kies - {a["id"] for a in _v1_ankers(na)}:
            return "gezakt", f"onbekende ankers: {sorted(kies - {a['id'] for a in _v1_ankers(na)})}"
        return ("gezakt", ", ".join(kwijt)) if kwijt else ("geslaagd", "")
    if s == "element_kandidaat":
        casus, gid = regel["element"].split("/")
        c = _concept(casus)
        g = next(g for g in c["gold"] if g["gid"] == gid)
        start, eind = kern(c["tekst"], g["start"], g["eind"])
        klassen = _op_plek(na, casus, start, eind)
        if klassen is None:
            return "gezakt", f"geen kandidaat op {start}–{eind} ({c['tekst'][start:eind]!r})"
        if regel.get("klasse") and regel["klasse"] not in klassen:
            return "gezakt", f"klassen op de plek: {sorted(klassen)}"
        verboden = set(regel.get("zonder_klasse") or []) & klassen
        if verboden:
            return "gezakt", f"draagt nog {sorted(verboden)}"
        return "geslaagd", f"{sorted(klassen)}"
    if s == "geen_klasse_op_tekst":
        tekst, rijen = _s0(na, regel["casus"])
        raak = [r for r in rijen if tekst[slice(*kern(tekst, r["start"], r["eind"]))] == regel["tekst"]
                and regel.get("start") in (None, kern(tekst, r["start"], r["eind"])[0])]
        fout = [f"{r['start']}–{r['eind']}" for r in raak if regel["klasse"] in r["possible_classes"]]
        if not raak and regel.get("moet_bestaan", True):
            return "gezakt", "geen kandidaat met die tekst (verdwenen is niet hetzelfde als goed geklasseerd)"
        return ("gezakt", ", ".join(fout)) if fout else ("geslaagd", f"{len(raak)} kandidaten")
    if s == "alleen_toegestane_wijzigingen":
        toegestaan = {c: set(t) for c, t in (regel.get("toegestaan") or {}).items()}
        fout = []
        for cid, x in na["per_casus"].items():
            if x.get("diagnostisch") or cid in na["diagnostiek"]:
                continue
            for w in klassenverschil(voor["per_casus"][cid]["scenario"]["S0"], x["scenario"]["S0"], x["tekst"]):
                if w["tekst"] not in toegestaan.get(cid, set()):
                    fout.append(f"{cid} {w['soort']} {w['tekst']!r} +{w['klassen_bij']} -{w['klassen_af']}")
        return ("gezakt", "; ".join(fout)) if fout else ("geslaagd", "")
    if s == "model_min_niet_lager":
        if model_voor is None or model_na is None:
            return "niet_gemeten", "geen modelrapporten opgegeven"
        from eval.vergelijk_rapporten import _analyse, ROUTE
        av, an = (_analyse(m)["routes"][ROUTE]["spreiding"] for m in (model_voor, model_na))
        if regel.get("klasse"):
            bv, bn = (a[regel["metric"]].get(regel["klasse"]) for a in (av, an))
        else:
            bv, bn = av.get(regel["metric"]), an.get(regel["metric"])
        if not bv or not bn:
            return "niet_gemeten", "metric ontbreekt in een van de rapporten"
        return ("geslaagd" if bn["min"] >= bv["min"] else "gezakt"), f"min {bv['min']} → {bn['min']}"
    raise ValueError(f"onbekende regelsoort {s!r} (bekend: {', '.join(SOORTEN)})")


def evalueer(criteria: dict, voor: dict, na: dict, model_voor: dict | None = None,
             model_na: dict | None = None) -> dict[str, Any]:
    uit = []
    for regel in criteria["regels"]:
        try:
            uitslag, detail = toets(regel, voor, na, model_voor, model_na)
        except KeyError as exc:
            uitslag, detail = "gezakt", f"ontbreekt: {exc}"
        uit.append({"id": regel["id"], "soort": regel["soort"], "poort": regel.get("poort", True),
                    "uitslag": uitslag, "detail": detail})
    poort = [r for r in uit if r["poort"]]
    return {"naam": criteria.get("naam", ""), "regels": uit,
            "geslaagd": all(r["uitslag"] == "geslaagd" for r in poort)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("criteria", type=Path)
    ap.add_argument("--audit-voor", type=Path, required=True)
    ap.add_argument("--audit-na", type=Path, required=True)
    ap.add_argument("--model-voor", type=Path)
    ap.add_argument("--model-na", type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    lees = lambda p: json.loads(p.read_text()) if p else None  # noqa: E731
    u = evalueer(yaml.safe_load(args.criteria.read_text(encoding="utf-8")), lees(args.audit_voor),
                 lees(args.audit_na), lees(args.model_voor), lees(args.model_na))
    for r in u["regels"]:
        print(f"{r['uitslag']:>12}  {r['id']}{'' if r['poort'] else ' (waarneming)'}  {r['detail']}")
    print(f"\n{u['naam']}: {'GESLAAGD' if u['geslaagd'] else 'NIET GESLAAGD'}")
    if args.json:
        args.json.write_text(json.dumps(u, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if u["geslaagd"] else 1


if __name__ == "__main__":
    sys.exit(main())
