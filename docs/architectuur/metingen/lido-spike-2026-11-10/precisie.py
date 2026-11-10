"""Steekproef (artikel, ECLI) uit de spike; per paar de tekst bij Rechtspraak en de vermeldingen van het artikel.

Gebruik: python -I precisie.py uit/BWBR0004770.json <n> <seed> <uitbestand>
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import random
import re
import sys
import time
import urllib.request

UA = "wetsanalyse-lido-spike/0.1 (onderzoek, alleen lezen)"
WET = r"(?:Invorderingswet(?: 1990)?|IW(?: 1990)?|Iw(?: 1990)?)"


def tekst(ecli: str, cache: pathlib.Path) -> str:
    pad = cache / (hashlib.sha1(ecli.encode()).hexdigest() + ".rs.xml")
    if not pad.exists():
        req = urllib.request.Request(f"https://data.rechtspraak.nl/uitspraken/content?id={ecli}",
                                     headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            pad.write_bytes(r.read())
        time.sleep(0.15)
    ruw = pad.read_text(encoding="utf-8", errors="replace")
    t = re.sub(r"<[^>]+>", " ", ruw)
    return re.sub(r"\s+", " ", t)


def vermeldingen(t: str, nr: str) -> list[str]:
    n = re.escape(nr)
    pat = re.compile(
        rf"(?:artikel|art\.?)\s+{n}(?![0-9a-z])[^.;]{{0,120}}?{WET}"
        rf"|{WET}[^.;]{{0,25}}?(?:artikel|art\.?)\s*{n}(?![0-9a-z])"
        rf"|jci1\.3:c:BWBR0004770&(?:amp;)?(?:[a-z]+=[^&]+&(?:amp;)?)*artikel={n}(?![0-9a-z])",
        re.I)
    return [t[max(0, m.start() - 160): m.end() + 160] for m in pat.finditer(t)]


def main():
    data = json.load(open(sys.argv[1]))
    n, seed, uit = int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    cache = pathlib.Path(sys.argv[1]).parent / "cache"
    paren = sorted({(a["artikel"], l["doel"].split("/")[-1]) for a in data["artikelen"] for l in a["links"]
                    if l["groep"] == "Jurisprudentie" and l["richting"] == "inkomende"})
    random.seed(seed)
    steek = random.sample(paren, min(n, len(paren)))
    rijen = []
    for nr, ecli in steek:
        t = tekst(ecli, cache)
        v = vermeldingen(t, nr)
        rijen.append({"artikel": nr, "ecli": ecli, "vermeldingen": len(v), "lengte": len(t),
                      "fragmenten": v[:3]})
    json.dump({"populatie": len(paren), "steekproef": rijen}, open(uit, "w"), ensure_ascii=False, indent=1)
    print("populatie", len(paren), "steekproef", len(rijen), "met vermelding", sum(1 for r in rijen if r["vermeldingen"]))


if __name__ == "__main__":
    main()
