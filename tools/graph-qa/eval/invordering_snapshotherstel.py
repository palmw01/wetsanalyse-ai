"""Herstel uitsluitend de lokale boomafbakening met bewaarde modelreacties.

De primaire poging en oorspronkelijke uitvoer blijven bestaan. De replay moet exact
dezelfde aanvragen en kandidaten opleveren. Alleen nieuw bereikbare review mag een
aanvullende call gebruiken; classificatie wordt nooit opnieuw betaald.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from eval.invordering_proef import MEETMAP, ROOT, controleer_cases, schrijf, codehash


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", type=Path, required=True)
    args = p.parse_args()
    out = MEETMAP / "modelruns"
    manifest = json.loads((out / "manifest.json").read_text())
    cases = MEETMAP / "proef-bronnen.json"
    controleer_cases(json.loads(cases.read_text()))
    if {"baseline": codehash(args.baseline), "variant": codehash(ROOT)} != manifest["code"]:
        raise ValueError("applicatiecode gewijzigd")
    worker = Path(__file__).with_name("invordering_proef.py")
    correctie = {"schema_versie": 1, "type": "uitsluitend_afbakening_onderzoekssnapshot",
        "bronpakket_ongewijzigd": True, "applicatiecode_ongewijzigd": True,
        "harnas_sha256_voor": manifest["harnas_sha256"],
        "harnas_sha256_na": hashlib.sha256(worker.read_bytes()).hexdigest(),
        "casussen_sha256": manifest["casussen_sha256"],
        "reden": "De hoogste geselecteerde graafouder is de lokale wortel; de verbinding buiten de selectie wordt apart bewaard. Bronteksten, offsets, directe ouders, detectoren en modelverzoeken blijven gelijk.",
        "oorspronkelijke_pogingen": sorted(p.name for p in out.glob("[123]-*.json"))}
    cp = out / "correctie-snapshot.json"
    if not cp.exists():
        schrijf(cp, correctie)
    elif json.loads(cp.read_text())["harnas_sha256_na"] != correctie["harnas_sha256_na"]:
        raise ValueError("correctie na vastlegging gewijzigd")
    herstel = out / "snapshot-herstel"
    herstel.mkdir(exist_ok=True)
    for bron in sorted(out.glob("[123]-*.json")):
        r = json.loads(bron.read_text())
        if not any(v["code"] == "V_ANKER" for v in r.get("meting", {}).get("validatie", [])):
            continue
        doel = herstel / bron.name
        if doel.exists():
            if json.loads(doel.read_text())["herstel"]["origineel_sha256"] != hashlib.sha256(bron.read_bytes()).hexdigest():
                raise ValueError("oorspronkelijke poging veranderd")
            continue
        root = args.baseline if r["variant"] == "A_huidig" else ROOT
        subprocess.run([sys.executable, str(worker), "--worker", "--code-root", str(root),
            "--cases", str(cases), "--case", r["casus"], "--variant", r["variant"],
            "--ronde", str(r["ronde"]), "--output", str(doel), "--replay-source", str(bron)],
            cwd=root / "tools/graph-qa", check=True)


if __name__ == "__main__":
    main()
