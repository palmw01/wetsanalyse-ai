"""Baselineproef hybrid_v1: variantmatrix op de bevroren invorderingscasussen.

Scheidt de factoren die de vorige A/B/C-proef mengde: code, classifiergranulariteit en
graafcontext. Context komt uit hetzelfde mechanisme als productie (`BronContext.ouders`), niet
uit een samengesteld onderzoekspakket. Waar dat mechanisme niets oplevert is het modelverzoek
byte-identiek aan de variant zonder context; die poging wordt niet uitgevoerd maar als
`identiek_aan` in het manifest vastgelegd.

Casussen, bronnen en de lokale afbakening van de onderzoekssnapshot zijn die van de vorige proef
(`eval.invordering_proef`); die module en haar meetmap blijven ongewijzigd. Ruwe runbestanden
staan in `modelruns/` en gaan niet in git (zie README van de meetmap).

    python -m eval.baseline_proef plan  --baseline <checkout-b8117e2>
    python -m eval.baseline_proef run   --baseline <checkout-b8117e2> [--parallel 3]
    python -m eval.baseline_proef rapport
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from eval.invordering_proef import (MEETMAP as VORIGE_MEETMAP, ROOT, TARIEFBRON, TARIEVEN, TOKENS, codehash,
                                    controleer_cases, onderzoekssnapshot, schrijf, sha)

MEETMAP = ROOT / "docs/architectuur/metingen/hybrid-v1-baseline-2026-09-29"
RUNMAP = MEETMAP / "modelruns"
CASES = VORIGE_MEETMAP / "proef-bronnen.json"
MODEL = "claude-sonnet-4-6"
HERHALINGEN = 3
# naam → (code, granulariteit, context). A is de huidige productie (master b8117e2).
VARIANTEN: dict[str, tuple[str, str, str]] = {
    "A": ("baseline", "universeel", "geen"),
    "U0": ("variant", "universeel", "uit"),
    "K0": ("variant", "klasseverzameling", "uit"),
    "UC": ("variant", "universeel", "ouders"),
    "KC": ("variant", "klasseverzameling", "ouders"),
}
ZONDER_CONTEXT = {"UC": "U0", "KC": "K0"}


def lees(p: Path):
    return json.loads(p.read_text())


def casussen():
    p = lees(CASES)
    controleer_cases(p)
    return p


def context_van(c):
    from agent.jas_pipeline.broncontext import BronContext
    return BronContext.ouders(onderzoekssnapshot(c["snapshot"]))


def plan(baseline: Path) -> dict:
    """Welke pogingen er zijn, in welke volgorde, en welke identiek zijn aan een andere variant."""
    p = casussen()
    namen = list(VARIANTEN)
    identiek = {}
    for c in p["casussen"]:
        ctx = context_van(c)
        for v, zonder in ZONDER_CONTEXT.items():
            if not ctx.blok():
                identiek[f'{c["id"]}/{v}'] = zonder
    pogingen = []
    for ronde in range(1, HERHALINGEN + 1):
        volgorde = namen[ronde - 1:] + namen[:ronde - 1]
        for c in p["casussen"]:
            for v in volgorde:
                if f'{c["id"]}/{v}' not in identiek:
                    pogingen.append({"ronde": ronde, "casus": c["id"], "variant": v})
    return {"schema_versie": 1, "model": MODEL, "herhalingen": HERHALINGEN,
            "varianten": {k: dict(zip(("code", "granulariteit", "context"), v)) for k, v in VARIANTEN.items()},
            "code": {"baseline": codehash(baseline), "variant": codehash(ROOT)},
            "casussen_sha256": p["casussen_sha256"], "identiek_aan": identiek,
            "primaire_pogingen": len(pogingen), "pogingen": pogingen,
            "harnas_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def bestand(ronde: int, casus: str, variant: str) -> Path:
    return RUNMAP / f'{ronde}-{casus.replace(":", "_")}-{variant}.json'


def worker(args):
    # Import pas ná de keuze van checkout; de baseline gebruikt zijn eigen ketenmodules.
    sys.path.insert(0, str(args.code_root / "tools/graph-qa"))
    from dotenv import dotenv_values
    from bronmodel import CorpusMap, valideer_ankers
    from agent.config import Settings
    from agent.adapters.anthropic_llm import AnthropicLLM
    from agent.jas_pipeline.keten import analyseer
    from agent.jas_pipeline.beslisregister import compact
    code, granulariteit, contextsoort = VARIANTEN[args.variant]
    p = casussen()
    c = next(c for c in p["casussen"] if c["id"] == args.case)
    snap = onderzoekssnapshot(c["snapshot"])
    cm = CorpusMap(snap["segmenten"])
    s = Settings.from_env({**dotenv_values(ROOT / "tools/graph-qa/.env"), **os.environ}).model_copy(update={
        "llm_model": MODEL, "llm_timeout_seconds": 60, "llm_max_retries": 0,
        "classifier_temperature": None, "classifier_spankeuze": False,
        "classifier_granulariteit": granulariteit, "gerichte_review": True,
        "deterministisch_accepteren": True, "taal_provider": "spacy:nl_core_news_md"})
    extra = {}
    if contextsoort != "geen":
        from agent.jas_pipeline.broncontext import BronContext
        extra["context"] = BronContext.ouders(snap) if contextsoort == "ouders" else BronContext()
    live, calls = AnthropicLLM(s), []

    class Capture:
        def create(self, **kw):
            rec = {"verzoek": kw, "verzoek_sha256": sha(kw), "status": "gestart"}
            calls.append(rec)
            t = time.monotonic()
            try:
                resp = live.create(**kw)
                rec.update(status="ok", antwoord=resp.model_dump(mode="json"),
                           tokens={k: getattr(resp.usage, k, 0) or 0 for k in TOKENS})
                return resp
            except Exception as e:
                rec.update(status="fout", fout=type(e).__name__, http_status=getattr(e, "status_code", None))
                raise
            finally:
                rec["seconden"] = round(time.monotonic() - t, 3)

    r = {"casus": c["id"], "variant": args.variant, "ronde": args.ronde, "status": "gestart",
         "tijd": datetime.now(timezone.utc).isoformat(), "casussen_sha256": p["casussen_sha256"],
         "code_sha256": codehash(args.code_root), "model": s.llm_model, "provider": s.llm_provider,
         "snapshot_afbakening": snap.get("afbakening", {}),
         "instellingen": {k: getattr(s, k) for k in ("classifier_temperature", "classifier_spankeuze",
             "classifier_granulariteit", "gerichte_review", "deterministisch_accepteren", "taal_provider",
             "llm_timeout_seconds", "llm_max_retries")} | {"context": contextsoort}, "calls": calls}
    start = time.monotonic()
    try:
        uit = analyseer(snapshot=snap, corpus_segmenten=cm.als_dicts(), corpus=cm.corpus,
                        llm=Capture(), model=s.llm_model, settings=s, **extra)
        if uit.meting["gedegradeerd"]:
            raise RuntimeError("volledige parse vereist")
        for v in uit.voorstellen:
            valideer_ankers(snap, v["ankers"])
        r.update(status="ok", voorstellen=uit.voorstellen, meting=uit.meting,
                 fusie=uit.fusie.model_dump(mode="json"),
                 beslissingen=compact(uit.fusie.kandidaten, uit.beslissingen, uit.voorstellen, uit.fusie.bijdragen))
    except Exception as e:
        r.update(status="fout", fout=type(e).__name__, http_status=getattr(e, "status_code", None))
    r["seconden"] = round(time.monotonic() - start, 3)
    r["tokens"] = {k: sum(call.get("tokens", {}).get(k, 0) for call in calls) for k in TOKENS}
    r["kosten"] = {"factuurbedrag": None, "schatting_usd": round(sum(r["tokens"][k] * TARIEVEN[k] / 1e6 for k in TOKENS), 6),
                   "usd_per_miljoen": TARIEVEN, "tariefbron": TARIEFBRON, "tariefdatum": "2026-05-27",
                   "reden": "schatting volgens Microsoft Foundry-lijstprijs, geen Azure-factuur"}
    schrijf(args.output, r)
    print(c["id"], args.variant, args.ronde, r["status"], len(calls), "calls", flush=True)


def run(baseline: Path, parallel: int):
    RUNMAP.mkdir(parents=True, exist_ok=True)
    manifest = plan(baseline)
    mp = RUNMAP / "manifest.json"
    if mp.exists():
        if lees(mp) != manifest:
            raise RuntimeError("proefmanifest gewijzigd; hervatten met andere code/bronnen is niet toegestaan")
    else:
        schrijf(mp, manifest)
    gestopt = threading.Event()

    def poging(ronde, casus, variant):
        if gestopt.is_set():
            return
        code = VARIANTEN[variant][0]
        out = bestand(ronde, casus, variant)
        if out.exists():
            r = lees(out)
            if (r["casussen_sha256"], r["code_sha256"]) != (manifest["casussen_sha256"], manifest["code"][code]):
                gestopt.set()
                raise RuntimeError("bestaande poging hoort bij andere code/bronnen")
            return
        if codehash(baseline) != manifest["code"]["baseline"] or codehash(ROOT) != manifest["code"]["variant"]:
            gestopt.set()
            raise RuntimeError("code gewijzigd tijdens proef; geen gemengde meetversie")
        root = baseline if code == "baseline" else ROOT
        subprocess.run([sys.executable, "-m", "eval.baseline_proef", "worker", "--code-root", str(root),
                        "--case", casus, "--variant", variant, "--ronde", str(ronde), "--output", str(out)],
                       cwd=ROOT / "tools/graph-qa", check=True)
        if lees(out).get("http_status") in {401, 403, 404}:
            gestopt.set()
            raise RuntimeError("providerconfiguratie faalt; proef gestopt zonder extra aanvragen")

    # Per ronde: casussen parallel, varianten binnen een casus sequentieel; barrière tussen rondes.
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        for ronde in range(1, HERHALINGEN + 1):
            per_casus: dict[str, list] = {}
            for x in manifest["pogingen"]:
                if x["ronde"] == ronde:
                    per_casus.setdefault(x["casus"], []).append(x["variant"])
            futures = [pool.submit(lambda c=c, vs=vs: [poging(ronde, c, v) for v in vs])
                       for c, vs in per_casus.items()]
            for f in futures:
                f.result()


# --- rapport -------------------------------------------------------------------------------------

def laad_runs(manifest):
    runs = []
    for x in manifest["pogingen"]:
        p = bestand(x["ronde"], x["casus"], x["variant"])
        r = lees(p)
        runs.append({**r, "_bestand": p.name, "_sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    # Identieke verzoeken: dezelfde poging telt ook voor de contextvariant, expliciet gemarkeerd.
    for sleutel_, zonder in manifest["identiek_aan"].items():
        casus, variant = sleutel_.split("/")
        for r in [r for r in runs if r["casus"] == casus and r["variant"] == zonder]:
            runs.append({**r, "variant": variant, "_identiek_aan": zonder})
    return runs


def valideer(manifest, runs):
    p = casussen()
    if p["casussen_sha256"] != manifest["casussen_sha256"]:
        raise ValueError("bronpakket gewijzigd")
    cases = {c["id"]: c for c in p["casussen"]}
    fusies = {}
    for r in runs:
        code = VARIANTEN[r["variant"]][0]
        if r["code_sha256"] != manifest["code"][code] or r["model"] != MODEL:
            raise ValueError(f'{r["_bestand"]}: code/model gewisseld')
        if r["tokens"] != {k: sum(c.get("tokens", {}).get(k, 0) for c in r["calls"]) for k in TOKENS}:
            raise ValueError("tokentelling wijkt af")
        if r["status"] != "ok":
            continue
        nodes = {n["bron_iri"]: n for n in cases[r["casus"]]["snapshot"]["segmenten"]}
        for a in [k["span"] for k in r["fusie"]["kandidaten"]] + [a for v in r["voorstellen"] for a in v["ankers"]]:
            n = nodes[a["bron_iri"]]
            if n["tekst"][a["start"]:a["eind"]] != a["tekst"] or a["bron_hash"] != n["bron_hash"]:
                raise ValueError("fragment is niet brongetrouw")
        h = sha(r["fusie"])
        if fusies.setdefault((r["casus"], code), h) != h:
            raise ValueError("detectie niet reproduceerbaar binnen één codeversie")
        if code == "variant" and not r.get("_identiek_aan"):
            verwacht = context_van(cases[r["casus"]]) if VARIANTEN[r["variant"]][2] == "ouders" else None
            gekregen = [(x["bron_iri"], x["bron_hash"]) for x in r["meting"]["broncontext"]["passages"]]
            if gekregen != ([(x.bron_iri, x.bron_hash) for x in verwacht.passages] if verwacht else []):
                raise ValueError("aangeboden context wijkt af van het productiemechanisme")


def rapport():
    from eval.invordering_rapport import samenvatting, stabiliteit
    manifest = lees(RUNMAP / "manifest.json")
    runs = laad_runs(manifest)
    valideer(manifest, runs)
    p = casussen()
    uitgevoerd = [r for r in runs if not r.get("_identiek_aan")]
    totaal = {}
    for v in VARIANTEN:
        eigen = [r for r in uitgevoerd if r["variant"] == v]
        s = samenvatting(eigen) if eigen else {}
        ok = [r for r in eigen if r["status"] == "ok"]
        s["contractfouten"] = sum(t.get("categorie") == "CLASSIFIER_CONTRACT_ERROR"
                                  for r in ok for t in r["meting"]["twijfels"])
        s["regelbesluiten"] = sum(b["door"] == "regel" for r in ok for b in r["meting"]["oorspronkelijke_beslissingen"]) \
            if ok and "oorspronkelijke_beslissingen" in ok[0]["meting"] else None
        s["centrale_norm"] = dict(Counter(t["regel"] for r in ok for t in r["meting"]["resolutie"]
                                          if t["reden"] == "CENTRALE_NORM_AFGEWEZEN"))
        s["kosten_per_run_usd"] = round(s["kosten_schatting_usd"] / len(eigen), 6) if eigen else None
        totaal[v] = s
    per = {c["id"]: {v: stabiliteit([r for r in runs if r["casus"] == c["id"] and r["variant"] == v])
                     for v in VARIANTEN} for c in p["casussen"]}
    keuze = beslis(totaal, per)
    data = {"status": "diagnostisch_geen_gold", "manifest": manifest, "varianten": totaal, "casussen": per,
            "keuze": keuze, "runbestanden_sha256": {r["_bestand"]: r["_sha256"] for r in uitgevoerd}}
    schrijf(MEETMAP / "model-vergelijking.json", data)
    with (MEETMAP / "model-vergelijking.md").open("x") as f:
        f.write(markdown(manifest, totaal, per, keuze))


def beslis(totaal, per):
    """Het vooraf vastgelegde keuzecriterium (README): alleen toegepast, niet afgesteld."""
    uc, kc = totaal["UC"], totaal["KC"]
    stabiel = sum(per[c]["KC"].get("doorsnede_door_unie", 0) >= per[c]["UC"].get("doorsnede_door_unie", 0) for c in per)
    kosten = kc["kosten_per_run_usd"] / uc["kosten_per_run_usd"] if uc["kosten_per_run_usd"] else float("inf")
    a, b, c = kc["contractfouten"] < uc["contractfouten"], stabiel >= 6, kosten <= 3
    slechter_door_context = sum(per[x]["UC"].get("doorsnede_door_unie", 0) < per[x]["U0"].get("doorsnede_door_unie", 0)
                                for x in per)
    return {"granulariteit": "klasseverzameling" if a and b and c else "universeel",
            "criteria": {"minder_contractfouten": a, "stabiliteit_kc_ge_uc_casussen": stabiel,
                         "kostenfactor_kc_uc": round(kosten, 3)},
            "context_slechter_dan_zonder_casussen": slechter_door_context,
            "context_vraagt_bevestiging": slechter_door_context >= 5}


def markdown(manifest, totaal, per, keuze):
    md = [f'# Modelvergelijking baselineproef: {manifest["primaire_pogingen"]} primaire pogingen', "",
          "A = productie vóór deze ronde (master b8117e2, universeel, geen context). U0/K0 = baselinecode "
          "universeel/klasseverzameling zonder context; UC/KC = idem met context uit `BronContext.ouders`, "
          "het productiemechanisme. Waar dat mechanisme niets oplevert is het verzoek identiek aan U0/K0; "
          "die cellen tonen de U0/K0-runs en tellen niet mee in de varianttotalen.", "",
          "Stabiliteit vergelijkt bron-IRI + exacte offsets + klasse; zij bewijst geen juistheid. "
          "Kosten zijn ramingen uit tokens en lijstprijs, geen factuur.", "",
          "| Variant | Pogingen / geslaagd | Calls (review) | Contractfouten | Voorstellen (menselijk) | Mediaan s/run | USD totaal | USD/run |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for v, s in totaal.items():
        if not s.get("pogingen"):
            continue
        md.append(f'| {v} | {s["pogingen"]} / {s["geslaagd"]} | {s["calls"]} ({s["review_calls"]}) | {s["contractfouten"]} | '
                  f'{s["voorstellen"]} ({s["menselijk"]}) | {s["mediaan_seconden"]} | {s["kosten_schatting_usd"]:.4f} | {s["kosten_per_run_usd"]:.4f} |')
    md += ["", "## Herhaalbaarheid", "", "Per variant: aantallen per run; vast/unie.", "",
           "| Casus | " + " | ".join(VARIANTEN) + " |", "|---|" + "---|" * len(VARIANTEN)]
    for cid, ps in per.items():
        cellen = []
        for v, x in ps.items():
            merk = " (= " + ZONDER_CONTEXT[v] + ")" if f"{cid}/{v}" in manifest["identiek_aan"] else ""
            cellen.append(f'{x.get("aantallen", [])}; {x.get("doorsnede", 0)}/{x.get("unie", 0)}{merk}')
        md.append("| " + " | ".join([cid, *cellen]) + " |")
    md += ["", "## Keuzecriterium (vooraf vastgelegd)", "",
           f'- KC minder contractfouten dan UC: **{keuze["criteria"]["minder_contractfouten"]}**',
           f'- Casussen met KC-stabiliteit ≥ UC: **{keuze["criteria"]["stabiliteit_kc_ge_uc_casussen"]}/8** (drempel 6)',
           f'- Kostenfactor KC/UC per run: **{keuze["criteria"]["kostenfactor_kc_uc"]}** (drempel 3)',
           f'- Uitkomst granulariteit: **{keuze["granulariteit"]}**',
           f'- Casussen waar UC minder stabiel is dan U0: **{keuze["context_slechter_dan_zonder_casussen"]}** '
           f'(bij 5 of meer eerst bevestiging vragen: {keuze["context_vraagt_bevestiging"]})', ""]
    return "\n".join(md)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("actie", choices=("plan", "run", "worker", "rapport"))
    p.add_argument("--baseline", type=Path)
    p.add_argument("--parallel", type=int, default=3)
    p.add_argument("--code-root", type=Path, default=ROOT)
    p.add_argument("--case")
    p.add_argument("--variant", choices=list(VARIANTEN))
    p.add_argument("--ronde", type=int)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if args.actie == "plan":
        print(json.dumps({k: v for k, v in plan(args.baseline).items() if k != "pogingen"}, indent=2, ensure_ascii=False))
    elif args.actie == "run":
        run(args.baseline, args.parallel)
    elif args.actie == "worker":
        worker(args)
    else:
        rapport()


if __name__ == "__main__":
    main()
