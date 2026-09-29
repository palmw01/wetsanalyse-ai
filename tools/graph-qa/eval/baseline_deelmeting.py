"""Compacte deelmeting per werkpakket van de baseline: vergelijking zonder volledige kandidaatdumps.

    python -m eval.detector_audit --json <na-dev.json> --vergelijk <voor-dev.json>
    python -m eval.onderzoek_invordering --output <na-onderzoek.json>
    python -m eval.baseline_deelmeting <WP> <na-dev.json> <voor-onderzoek.json> <na-onderzoek.json> <uitmap>/<naam>

Schrijft <naam>.json (kengetallen en gewijzigde kandidaten), <naam>-ontwikkelset.txt en
<naam>-hoofdgevallen.txt: per gewijzigde kandidaat de klassen, bewijsbijdragen en route.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def _s0(x):
    return {k: v for k, v in x["S0"].items() if not isinstance(v, list)}


def ontwikkelset(dev: dict) -> list[str]:
    v = dev["vergelijking"]
    regels = ["S0 voor/na: " + str({k: (v["voor"]["S0"][k], v["na"]["S0"][k])
                                    for k in ("kandidaten", "ankers_core", "ankers_met_klasse", "deterministisch")}),
              f'verloren: {v["verloren_devankers"]}']

    def sam(x):
        return (x["possible_classes"], sorted({(b["detector"], b["code"]) for b in x["bewijs"]})) if x else None
    for c, x in v["per_casus"].items():
        for k in x["kandidaten"]:
            voor, na = k.get("voor"), k.get("na")
            a, b = sam(voor), sam(na)
            if a == b:
                continue
            ref = voor or na
            regels.append(f'{c} [{ref["start"]},{ref["eind"]}) {ref["tekst"][:60]!r}')
            if a and b:
                if a[0] != b[0]:
                    regels.append(f"   klassen: {a[0]} -> {b[0]}")
                if a[1] != b[1]:
                    regels.append(f"   bewijs -: {sorted(set(a[1]) - set(b[1]))} +: {sorted(set(b[1]) - set(a[1]))}")
            else:
                regels.append(f'    {"NIEUW" if b else "WEG"} {(b or a)[0]} {(b or a)[1]}')
        for key in ("classifier_input_gelijk", "parse_gelijk"):
            if x.get(key) is False:
                regels.append(f"{c} {key} False")
    return regels


def hoofdgevallen(voor: dict, na: dict) -> list[str]:
    def idx(c):
        return {(k["start"], k["eind"]): (tuple(k["possible_classes"]),
                tuple(sorted({(e["detector"], e["code"]) for e in k["bewijs"]})), k.get("route"), k["tekst"])
                for k in c["kandidaten"]}
    regels = []
    for cid, a in voor["casussen"].items():
        b = na["casussen"][cid]
        x, y = idx(a), idx(b)
        regels.append(f'== {cid}: tellingen {a["tellingen"].get("fusie")} -> {b["tellingen"].get("fusie")} | '
                      f'routes {a["tellingen"].get("routes")} -> {b["tellingen"].get("routes")}')
        for s in sorted(set(x) | set(y)):
            p, q = x.get(s), y.get(s)
            if p == q:
                continue
            t = (p or q)[3][:70]
            if not p:
                regels.append(f"  + [{s[0]},{s[1]}) {t!r} {q[0]} {[c for _, c in q[1]]} {q[2]}")
            elif not q:
                regels.append(f"  - [{s[0]},{s[1]}) {t!r} {p[0]} {[c for _, c in p[1]]} {p[2]}")
            else:
                regels.append(f"  ~ [{s[0]},{s[1]}) {t!r}")
                if p[0] != q[0]:
                    regels.append(f"      klassen {p[0]} -> {q[0]}")
                if p[1] != q[1]:
                    regels.append(f"      bewijs - {sorted(set(p[1]) - set(q[1]))} + {sorted(set(q[1]) - set(p[1]))}")
                if p[2] != q[2]:
                    regels.append(f"      route {p[2]} -> {q[2]}")
    return regels


def main():
    wp, dev_pad, voor_pad, na_pad, uit = sys.argv[1:6]
    dev = json.loads(Path(dev_pad).read_text())
    voor, na = json.loads(Path(voor_pad).read_text()), json.loads(Path(na_pad).read_text())
    v = dev["vergelijking"]
    data = {"werkpakket": wp, "git_sha": dev["git_sha"],
            "hashes_sha256": hashlib.sha256(json.dumps(dev["hashes"], sort_keys=True).encode()).hexdigest(),
            "ontwikkelset": {"voor": _s0(v["voor"]), "na": _s0(v["na"]), "verloren_devankers": v["verloren_devankers"],
                             "classifier_input_gewijzigd": sorted(c for c, x in v["per_casus"].items()
                                                                  if x.get("classifier_input_gelijk") is False),
                             "parse_gewijzigd": sorted(c for c, x in v["per_casus"].items() if x.get("parse_gelijk") is False),
                             "gewijzigde_kandidaten": {c: x["kandidaten"] for c, x in v["per_casus"].items() if x["kandidaten"]}},
            "onderzoek": {c: {"tellingen": x["tellingen"]} for c, x in na["casussen"].items()}}
    Path(uit + ".json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    Path(uit + "-ontwikkelset.txt").write_text("\n".join(ontwikkelset(dev)) + "\n")
    Path(uit + "-hoofdgevallen.txt").write_text("\n".join(hoofdgevallen(voor, na)) + "\n")


if __name__ == "__main__":
    main()
