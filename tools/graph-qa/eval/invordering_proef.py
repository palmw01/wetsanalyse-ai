"""Begrensde A/B/C-proef met bevroren graafbronnen en afzonderlijke code-checkouts.

Geen opslag-API, graph writes of bronretrieval tijdens modelruns. Per run exclusieve
uitvoer; hervatten slaat bestaande pogingen over, ook mislukte. Geen extra herhalingen.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
MEETMAP = ROOT / "docs/architectuur/metingen/hybrid-v1-invordering-vervolg-2026-09-29"
ONDERZOEK = ROOT / "docs/wetsanalyse/onderzoek-invordering-2026-09-29"
VARIANTEN = ("A_huidig", "B_verbeterd", "C_context")
TOKENS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
TARIEVEN = dict(zip(TOKENS, (3.0, 15.0, 0.30, 3.75)))
TARIEFBRON = "https://www-cdn.anthropic.com/files/4zrzovbb/website/3684c2faafb97418665782cea0001f439f74b1d2.pdf"


def sha(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def schrijf(pad, value):
    with pad.open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def prepare():
    from eval.onderzoek_invordering import snapshot, controleer_bronnen
    p = json.loads((ONDERZOEK / "bronnen.json").read_text())
    controleer_bronnen(p)
    cs = []
    for c in p["casussen"]:
        ps = [d for d in [*p["casussen"], *p["contextpassages"]] if d["bron_iri"] != c["bron_iri"]]
        context = [{k: d[k] for k in ("bron_iri", "tekst", "bron_hash", "herkomst", "toestand", "juridische_status")}
                   for d in ps]
        cs.append({"id": c["id"], "snapshot": snapshot(c), "herkomst": "graaf", "context": context,
                   "doel_metadata": {"bron_iri": c["bron_iri"], "toestand": c["toestand"],
                                     "juridische_status": c["juridische_status"]}})
    controle = json.loads((MEETMAP / "controlebronnen-graaf.json").read_text())
    for c in controle["controles"]:
        cs.append({"id": c["id"], "snapshot": c["snapshot"], "herkomst": "graaf", "context": c["context"],
                   "doel_metadata": {"bron_iri": c["snapshot"]["doel"]["bron_iri"],
                                     "toestand": c["toestand"], "juridische_status": c["juridische_status"]}})
    return {"schema_versie": 1, "casussen": cs, "bronpakket_sha256": sha(p),
            "controlepakket_sha256": sha(controle), "vervanging": controle.get("vervanging", {}),
            "casussen_sha256": sha(cs), "herhalingen": 3, "varianten": list(VARIANTEN)}


def controleer_cases(p):
    from bronmodel import tekst_hash
    if p["casussen_sha256"] != sha(p["casussen"]):
        raise ValueError("bronpakket veranderd")
    if len({c["id"] for c in p["casussen"]}) != len(p["casussen"]):
        raise ValueError("dubbele casus")
    for c in p["casussen"]:
        if c["herkomst"] != "graaf" or len(c["context"]) > 20:
            raise ValueError("onjuist bronbeleid")
        for n in [*c["snapshot"]["segmenten"], *c["context"]]:
            if tekst_hash(n["tekst"]) != n["bron_hash"]:
                raise ValueError("gewijzigde brontekst")
        if any(n["herkomst"] != "graaf" for n in c["context"]):
            raise ValueError("context komt niet uit de graaf")


def codehash(root):
    files = [root / "tools/graph-qa/agent/config.py"]
    files += sorted(p for p in (root / "tools/graph-qa/agent/jas_pipeline").rglob("*") if p.suffix in {".py", ".yaml"})
    return sha({str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files})


def worker(args):
    # Import pas ná de keuze van checkout; de baseline gebruikt zijn eigen ketenmodules.
    sys.path.insert(0, str(args.code_root / "tools/graph-qa"))
    from dotenv import dotenv_values
    from bronmodel import CorpusMap, valideer_ankers
    from agent.config import Settings
    from agent.adapters.anthropic_llm import AnthropicLLM
    from agent.jas_pipeline.keten import analyseer
    from agent.jas_pipeline.beslisregister import compact
    p = json.loads(args.cases.read_text())
    controleer_cases(p)
    c = next(c for c in p["casussen"] if c["id"] == args.case)
    cm = CorpusMap(c["snapshot"]["segmenten"])
    s = Settings.from_env({**dotenv_values(ROOT / "tools/graph-qa/.env"), **os.environ}).model_copy(update={
        "llm_model": "claude-sonnet-4-6", "llm_timeout_seconds": 60, "llm_max_retries": 0,
        "classifier_temperature": None, "classifier_spankeuze": False,
        "classifier_granulariteit": "universeel" if args.variant == "A_huidig" else "klasseverzameling",
        "gerichte_review": True, "deterministisch_accepteren": True,
        "taal_provider": "spacy:nl_core_news_md"})
    calls = []
    live = AnthropicLLM(s)

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

    extra = {}
    if args.variant != "A_huidig":
        from agent.jas_pipeline.broncontext import BronContext
        extra["context"] = BronContext.model_validate({"passages": c["context"], "doel_metadata": c["doel_metadata"]}) \
            if args.variant == "C_context" else BronContext()
    r = {"casus": c["id"], "variant": args.variant, "ronde": args.ronde, "status": "gestart",
         "tijd": datetime.now(timezone.utc).isoformat(), "casussen_sha256": p["casussen_sha256"],
         "code_sha256": codehash(args.code_root), "model": s.llm_model, "provider": s.llm_provider,
         "instellingen": {k: getattr(s, k) for k in ("classifier_temperature", "classifier_spankeuze",
             "classifier_granulariteit", "gerichte_review", "deterministisch_accepteren", "taal_provider",
             "llm_timeout_seconds", "llm_max_retries")}, "calls": calls}
    start = time.monotonic()
    try:
        uit = analyseer(snapshot=c["snapshot"], corpus_segmenten=cm.als_dicts(), corpus=cm.corpus,
                        llm=Capture(), model=s.llm_model, settings=s, **extra)
        if uit.meting["gedegradeerd"]:
            raise RuntimeError("volledige parse vereist")
        for v in uit.voorstellen:
            valideer_ankers(c["snapshot"], v["ankers"])
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepare", action="store_true")
    p.add_argument("--worker", action="store_true")
    p.add_argument("--cases", type=Path, default=MEETMAP / "proef-bronnen.json")
    p.add_argument("--baseline", type=Path)
    p.add_argument("--code-root", type=Path, default=ROOT)
    p.add_argument("--case")
    p.add_argument("--variant", choices=VARIANTEN)
    p.add_argument("--ronde", type=int)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if args.prepare:
        result = prepare()
        controleer_cases(result)
        schrijf(args.cases, result)
    elif args.worker:
        worker(args)
    else:
        if not args.baseline or not args.output:
            p.error("--baseline en --output (map) vereist")
        cases = json.loads(args.cases.read_text())
        controleer_cases(cases)
        args.output.mkdir(parents=True, exist_ok=True)
        hashes = {"baseline": codehash(args.baseline), "variant": codehash(args.code_root)}
        manifest = {"code": hashes, "casussen_sha256": cases["casussen_sha256"], "herhalingen": 3,
                    "varianten": list(VARIANTEN), "primaire_pogingen": len(cases["casussen"]) * 9,
                    "harnas_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        mp = args.output / "manifest.json"
        if mp.exists():
            if json.loads(mp.read_text()) != manifest:
                raise RuntimeError("proefmanifest gewijzigd; hervatten met andere code/bronnen is niet toegestaan")
        else:
            schrijf(mp, manifest)
        for ronde in range(1, 4):
            for c in cases["casussen"]:
                volgorde = VARIANTEN[ronde - 1:] + VARIANTEN[:ronde - 1]
                for variant in volgorde:
                    out = args.output / f'{ronde}-{c["id"].replace(":", "_")}-{variant}.json'
                    if out.exists():
                        vorig = json.loads(out.read_text())
                        if (vorig["casussen_sha256"] != cases["casussen_sha256"]
                                or vorig["code_sha256"] != hashes["baseline" if variant == "A_huidig" else "variant"]):
                            raise RuntimeError("bestaande poging hoort bij andere code/bronnen")
                        continue
                    if codehash(args.baseline) != hashes["baseline"] or codehash(args.code_root) != hashes["variant"]:
                        raise RuntimeError("code gewijzigd tijdens proef; geen gemengde meetversie")
                    root = args.baseline if variant == "A_huidig" else args.code_root
                    subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", "--code-root", str(root),
                        "--cases", str(args.cases.resolve()), "--case", c["id"], "--variant", variant,
                        "--ronde", str(ronde), "--output", str(out.resolve())], cwd=root / "tools/graph-qa", check=True)
                    r = json.loads(out.read_text())
                    if r.get("http_status") in {401, 403, 404}:
                        raise RuntimeError("providerconfiguratie faalt; proef gestopt zonder extra aanvragen")


if __name__ == "__main__":
    main()
