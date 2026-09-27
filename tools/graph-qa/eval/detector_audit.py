"""Lokale pre-baselineaudit. Geen modelaanroepen, geen referentiemutaties.

S1 is een diagnostisch meetmodel: lege klassen zijn géén productie-Candidates.
S2 verwijdert generieke bijdragen uit de juridische kandidaatruimte, zonder een
nieuwe contextgenerator te simuleren. De syntactische spans blijven in S1 beschikbaar.
Gebruik: python -m eval.detector_audit --json <bestand> [--vergelijk <voor.json>]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from agent.jas_pipeline.besluit import STERK_BEWIJS, deterministisch
from agent.jas_pipeline.classificatie import batches, systeemprompt, toolschema, userprompt
from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
from agent.jas_pipeline.fusie import _samen, fuseer
from agent.jas_pipeline.kandidaten import CandidateStatus, label_kandidaten
from agent.jas_pipeline.specificiteit import pas_toe
from agent.jas_pipeline.taal import SpacyProvider
from eval.kandidaat_eval import meet as kandidaatmeting
from eval.metrieken import controleer_status, kern, laagste_status
from eval.taal_benchmark import ontwikkelcasussen

GENERIEK = frozenset({"SUBJECT_NP", "OBJECT_NP", "ENUMERATED_NP"})
ROOT = Path(__file__).resolve().parents[3]
DIAGNOSTIEK = Path(__file__).resolve().parents[1] / "tests/fixtures/detector_audit_diagnostiek.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def generiek(k):
    codes = {e.code for e in k.evidence} - {"PRIORITY_APPLIED"}
    return bool(codes) and codes <= GENERIEK


def rij(k):
    b = deterministisch(k)
    return {"id": k.id, "bron": k.span.bron_iri, "start": k.span.start, "eind": k.span.eind,
            "tekst": k.span.tekst, "possible_classes": list(k.possible_classes),
            "bewijs": [e.model_dump() for e in k.evidence],
            "opties": [{"start": o.span.start, "eind": o.span.eind, "soort": o.soort} for o in k.span_options],
            "status": k.status.value, "route": b.door if b else "model"}


def samen_voordat_specificiteit(resultaten):
    samen = {}
    for r in resultaten:
        for k in r.kandidaten:
            samen[k.id] = _samen(samen[k.id], k) if k.id in samen else _samen(k, k)
    return samen


def scenario(resultaten, naam):
    if naam == "S0":
        return [rij(k) for k in fuseer(resultaten).kandidaten]
    if naam == "S2":
        rs = [r.model_copy(update={"kandidaten": tuple(k for k in r.kandidaten if not generiek(k))})
              for r in resultaten]
        return [rij(k) for k in fuseer(rs).kandidaten]
    if naam != "S1":
        raise ValueError(naam)
    onafhankelijk = defaultdict(list)
    for r in resultaten:
        for k in r.kandidaten:
            if not generiek(k):
                onafhankelijk[k.id].extend(k.possible_classes)
    met_klasse, leeg = [], []
    for kid, k in samen_voordat_specificiteit(resultaten).items():
        klassen = tuple(dict.fromkeys(onafhankelijk[kid]))
        if klassen:
            met_klasse.append(k.model_copy(update={"possible_classes": klassen}))
        else:
            leeg.append({**rij(k), "possible_classes": [], "route": "zonder_hypothese"})
    # Geen lege Candidate, ook niet via model_copy. Alleen echte hypotheses gaan door specificiteit.
    return sorted([rij(k) for k in label_kandidaten(pas_toe(tuple(met_klasse)))] + leeg,
                  key=lambda r: (r["bron"], r["start"], -r["eind"]))


def plekken(r, teksten, opties=False):
    grenzen = [(r["start"], r["eind"])]
    if opties:
        grenzen += [(o["start"], o["eind"]) for o in r["opties"]]
    return {(r["bron"], *kern(teksten[r["bron"]], s, e)) for s, e in grenzen}


def samenvatting(rijen, refs, teksten):
    core, opties = set(), set()
    met_klasse = set()
    for r in rijen:
        ps = plekken(r, teksten)
        core |= ps
        opties |= plekken(r, teksten, True)
        if r.get("status") != "REJECTED":
            met_klasse.update((*p, c) for p in ps for c in r["possible_classes"])
    gedekt = [r["id"] for r in refs if (r["bron"], r["start"], r["eind"]) in core]
    route = Counter(r["route"] for r in rijen)
    return {"kandidaten": len(rijen), "referenties": len(refs), "ankers_core": len(gedekt),
            "ankers_opties": sum((r["bron"], r["start"], r["eind"]) in opties for r in refs),
            "ankers_met_klasse": sum((r["bron"], r["start"], r["eind"], r["klasse"]) in met_klasse for r in refs),
            "gedekte_ankers": gedekt, "gemiddeld_klassen": sum(len(r["possible_classes"]) for r in rijen) / len(rijen)
                if rijen else None,
            "deterministisch": route["regel"], "specificiteit_afgewezen": route["specificiteit"],
            "classifier_kandidaten": route["model"], "zonder_hypothese": route["zonder_hypothese"],
            "classifier_batches_universeel": len({r["bron"] for r in rijen if r["route"] == "model"})}


def meet():
    provider = SpacyProvider("nl_core_news_md")
    cases = ontwikkelcasussen()
    status = laagste_status(controleer_status(c) for c in cases)
    diagnostiek = json.loads(DIAGNOSTIEK.read_text())
    teksten = {c["id"]: c["tekst"] for c in [*cases, *diagnostiek]}
    refs = [{"id": c["id"] + "/" + g["gid"], "bron": c["id"], "klasse": g["klasse"],
             "start": kern(c["tekst"], g["start"], g["eind"])[0],
             "eind": kern(c["tekst"], g["start"], g["eind"])[1]}
            for c in cases for g in c["gold"]]
    per_case = {}
    for c in [*cases, *diagnostiek]:
        a = provider.analyseer(c["tekst"])
        if a.gedegradeerd:
            raise RuntimeError(f"Audit vereist echte parse: {c['id']}: {a.fout}")
        rs = detecteer_alles(BronTekst.van_tekst(c["id"], c["tekst"], analyse=a))
        raw = [{**rij(k), "detector": r.detector, "versie": r.versie} for r in rs for k in r.kandidaten]
        f = fuseer(rs)
        model = [k for k in f.kandidaten if deterministisch(k) is None]
        payload = [{"system": systeemprompt(b), "user": userprompt(b, c["tekst"]), "tool": toolschema(b)}
                   for b in batches(model, "universeel")]
        before = samen_voordat_specificiteit(rs)
        per_case[c["id"]] = {
            "familie": c.get("familie"), "tekstsoort": c.get("tekstsoort"),
            "bron_sha256": sha(c["tekst"].encode()), "raw": raw,
            "voor_specificiteit": [rij(k) for k in before.values()],
            "scenario": {s: scenario(rs, s) for s in ("S0", "S1", "S2")},
            "classifier_input_sha256": sha(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()),
            "parse_sha256": sha(repr(a).encode()),
            "detectoren": [{"naam": r.detector, "versie": r.versie, "n": len(r.kandidaten),
                            "overgeslagen": r.overgeslagen} for r in rs]}
    ids = [c["id"] for c in cases]
    raw = [r for cid in ids for r in per_case[cid]["raw"]]
    s0 = [r for cid in ids for r in per_case[cid]["scenario"]["S0"]]
    generic = [r for r in raw if {e["code"] for e in r["bewijs"]} <= GENERIEK]
    other = [r for r in raw if r not in generic]
    details = []
    for r in s0:
        gs = [x for x in generic if x["id"] == r["id"]]
        if not gs:
            continue
        os = [x for x in other if x["id"] == r["id"]]
        gc = {c for x in gs for c in x["possible_classes"]}
        oc = {c for x in os for c in x["possible_classes"]}
        ocodes = {e["code"] for x in os for e in x["bewijs"]}
        s2 = next((x for x in per_case[r["bron"]]["scenario"]["S2"] if x["id"] == r["id"]), None)
        details.append({"id": r["id"], "bron": r["bron"], "tekst": r["tekst"],
                        "ook_andere_detector": bool(os), "ook_sterk_bewijs": bool(ocodes & STERK_BEWIJS),
                        "toegevoegde_klassen_voor_specificiteit": sorted(gc - oc),
                        "toegevoegde_klassen_na_specificiteit": sorted(set(r["possible_classes"]) -
                            set(s2["possible_classes"] if s2 else [])),
                        "blokkeert_deterministisch": r["route"] == "model" and bool(s2) and s2["route"] == "regel"})
    uniek = {}
    for opts in (False, True):
        gp = set().union(*(plekken(r, teksten, opts) for r in generic))
        op = set().union(*(plekken(r, teksten, opts) for r in other))
        uniek["incl_opties" if opts else "core"] = [r["id"] for r in refs
                    if (r["bron"], r["start"], r["eind"]) in gp - op]
    bestanden = list((ROOT / "tools/graph-qa/agent/jas_pipeline").rglob("*.py"))
    bestanden += list((ROOT / "tools/graph-qa/agent/jas_pipeline").rglob("*.yaml"))
    bestanden += [ROOT / "tools/graph-qa/uv.lock", ROOT / "docs/wetsanalyse/referentieset/v1/cases.json", DIAGNOSTIEK]
    return {
        "schema_versie": 1, "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "python": platform.python_version(), "spacy": importlib.metadata.version("spacy"), "taalmodel": provider.model,
        "referentie_status": status, "ontwikkeling": ids, "diagnostiek": [c["id"] for c in diagnostiek],
        "config": {"deterministisch_accepteren": True, "classifier_granulariteit": "universeel",
                   "classifier_spankeuze": False, "modelaanroepen": 0},
        "hashes": {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in sorted(bestanden)},
        "kandidaat_eval": kandidaatmeting(),
        "scenario": {s: samenvatting([r for cid in ids for r in per_case[cid]["scenario"][s]], refs, teksten)
                     for s in ("S0", "S1", "S2")},
        "generic_np": {"raw_kandidaten": len(raw), "raw_generiek": len(generic),
                       "codes": dict(Counter(e["code"] for r in generic for e in r["bewijs"])),
                       "unieke_ankers": uniek, "kandidaten": details},
        "per_casus": per_case,
    }


def vergelijk(voor, na):
    wijzigingen = {}
    for cid in voor["per_casus"]:
        v, n = voor["per_casus"][cid], na["per_casus"][cid]
        vr, nr = ({r["id"]: r for r in x["scenario"]["S0"]} for x in (v, n))
        verschillen = [{"id": kid, "voor": vr.get(kid), "na": nr.get(kid)} for kid in sorted(vr.keys() | nr.keys())
                       if vr.get(kid) != nr.get(kid)]
        wijzigingen[cid] = {"kandidaten": verschillen,
                           "classifier_input_gelijk": v["classifier_input_sha256"] == n["classifier_input_sha256"],
                           "parse_gelijk": v["parse_sha256"] == n["parse_sha256"]}
    return {"voor": voor["scenario"], "na": na["scenario"], "per_casus": wijzigingen,
            "verloren_devankers": sorted(set(voor["scenario"]["S0"]["gedekte_ankers"]) -
                                         set(na["scenario"]["S0"]["gedekte_ankers"]))}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", required=True)
    ap.add_argument("--vergelijk")
    args = ap.parse_args()
    m = meet()
    if args.vergelijk:
        m["vergelijking"] = vergelijk(json.loads(Path(args.vergelijk).read_text()), m)
    Path(args.json).write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"scenario": m["scenario"], "generic_codes": m["generic_np"]["codes"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
