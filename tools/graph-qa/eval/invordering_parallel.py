"""Voer de bevroren proef per ronde met maximaal drie onafhankelijke casussen uit.

De originele worker, code, bronnen, pogingen en variantrotatie blijven ongewijzigd.
Deze planner kan een gestopte sequentiële planner hervatten; nooit tegelijk gebruiken.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading

from eval.invordering_proef import ROOT, MEETMAP, VARIANTEN, codehash, controleer_cases, schrijf


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", type=Path, required=True)
    args = p.parse_args()
    out = MEETMAP / "modelruns"
    cases_path = MEETMAP / "proef-bronnen.json"
    cases = json.loads(cases_path.read_text())
    controleer_cases(cases)
    manifest = json.loads((out / "manifest.json").read_text())
    worker = Path(__file__).with_name("invordering_proef.py")
    correctiepad = out / "correctie-snapshot.json"
    correctie = json.loads(correctiepad.read_text()) if correctiepad.exists() else {}
    harnashash = correctie.get("harnas_sha256_na", manifest["harnas_sha256"])
    if hashlib.sha256(worker.read_bytes()).hexdigest() != harnashash:
        raise ValueError("originele worker gewijzigd")
    if cases["casussen_sha256"] != manifest["casussen_sha256"]:
        raise ValueError("bronpakket gewijzigd")
    info = {"max_casussen_tegelijk": 3, "volgorde_per_casus_per_ronde": [
        list(VARIANTEN[n:] + VARIANTEN[:n]) for n in range(3)],
        "reeds_afgerond_bij_overnemen": sorted(p.name for p in out.glob("[123]-*.json")),
        "planner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reden": "Onafhankelijke casussen parallel; alle 72 oorspronkelijke pogingen blijven behouden. Latentie is mede afhankelijk van parallelisme."}
    ip = out / ("planner-na-snapshotherstel.json" if correctie else "planner.json")
    if not ip.exists():
        schrijf(ip, info)
    elif json.loads(ip.read_text())["planner_sha256"] != info["planner_sha256"]:
        raise ValueError("planner gewijzigd")
    gestopt = threading.Event()

    def casus(c, ronde):
        for variant in VARIANTEN[ronde - 1:] + VARIANTEN[:ronde - 1]:
            if gestopt.is_set():
                return
            versie = "baseline" if variant == "A_huidig" else "variant"
            pad = out / f'{ronde}-{c["id"].replace(":", "_")}-{variant}.json'
            if pad.exists():
                r = json.loads(pad.read_text())
                if (r["casus"], r["variant"], r["ronde"], r["code_sha256"], r["casussen_sha256"]) != (
                        c["id"], variant, ronde, manifest["code"][versie], cases["casussen_sha256"]):
                    gestopt.set()
                    raise ValueError("bestaande poging hoort niet bij manifest")
                continue
            if codehash(args.baseline) != manifest["code"]["baseline"] or codehash(ROOT) != manifest["code"]["variant"]:
                gestopt.set()
                raise ValueError("code gewijzigd tijdens proef")
            root = args.baseline if versie == "baseline" else ROOT
            try:
                subprocess.run([sys.executable, str(worker), "--worker", "--code-root", str(root),
                    "--cases", str(cases_path), "--case", c["id"], "--variant", variant,
                    "--ronde", str(ronde), "--output", str(pad)], cwd=root / "tools/graph-qa", check=True)
                r = json.loads(pad.read_text())
                if r.get("http_status") in {401, 403, 404}:
                    raise RuntimeError("providerconfiguratie faalt")
            except Exception:
                gestopt.set()
                raise

    # Volgende ronde pas nadat alle casussen in deze ronde klaar zijn.
    with ThreadPoolExecutor(max_workers=3) as pool:
        for ronde in range(1, 4):
            futures = [pool.submit(casus, c, ronde) for c in cases["casussen"]]
            for f in futures:
                f.result()


if __name__ == "__main__":
    main()
