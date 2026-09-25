"""Kandidaatbeslisstabiliteit (onderzoek-empirische-validatie §13, validatieplan V4).

`stabiliteit_analyse` vergelijkt *voorstellen* over runs. Dat mist alles wat geen voorstel werd:
een kandidaat die de ene keer werd afgewezen en de andere keer geaccepteerd, verschijnt daar als
"detectie instabiel", terwijl de detectie juist stabiel was en de beslissing niet. Dit rapport kijkt
per kandidaat, op het beslisregister (`jas_pipeline/beslisregister.py`).

Sleutel: `kandidaat_id` (hash van bron, start, eind), stabiel zolang de bron gelijk blijft.

Per kandidaat een rij:

| kandidaat | span | fingerprint | mogelijke klassen | uitkomst per run | aanwezig | accept-overeenstemming | klasse-overeenstemming bij acceptatie | contractfouten |

- *uitkomst* is `status:klasse` (bv. `ACCEPTED:Rechtsobject`, `REJECTED:`).
- Een **fingerprint die tussen runs verschilt** wijst op niet-determinisme in de detectie. Dat is
  een bug en staat apart in `fingerprint_drift`.
- **Kandidaatbeslisstabiliteit** van een casus: het aandeel kandidaten dat in alle R runs aanwezig is
  en R/R dezelfde uitkomst heeft.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

_GEACCEPTEERD = {"ACCEPTED", "HUMAN_REVIEW"}      # een voorstel, geel of niet


def _uitkomst(b: dict[str, Any]) -> str:
    return f"{b['status']}:{b.get('klasse', '') if b['status'] in _GEACCEPTEERD else ''}"


def _contract(b: dict[str, Any]) -> bool:
    return (b.get("classifier_reden") or "").startswith(("CLASSIFIER_ONGELDIGE_", "CLASSIFIER_GEEN_UITVOER",
                                                         "CLASSIFIER_OMITTED"))


def rapport(runs: list[list[dict[str, Any]]]) -> dict[str, Any]:
    """`runs`: per run het beslisregister van één casus (zelfde bron in elke run)."""
    r = len(runs)
    rijen: dict[str, dict[str, Any]] = {}
    for i, register in enumerate(runs):
        for b in register:
            rij = rijen.setdefault(b["kandidaat_id"], {
                "kandidaat_id": b["kandidaat_id"], "label": b.get("label", ""), "start": b["start"],
                "eind": b["eind"], "mogelijke_klassen": b.get("mogelijke_klassen", []),
                "fingerprints": set(), "uitkomsten": [None] * r, "contractfouten": 0})
            rij["fingerprints"].add(b.get("bewijs_fingerprint", ""))
            rij["uitkomsten"][i] = _uitkomst(b)
            rij["contractfouten"] += _contract(b)

    uit_rijen, stabiel, drift = [], 0, []
    for rij in sorted(rijen.values(), key=lambda x: (x["start"], x["eind"])):
        aanwezig = [u for u in rij["uitkomsten"] if u is not None]
        statussen = Counter(u.split(":", 1)[0] in _GEACCEPTEERD for u in aanwezig)
        klassen = Counter(u for u in aanwezig if u.split(":", 1)[0] in _GEACCEPTEERD)
        geaccepteerd = sum(klassen.values())
        zelfde = len(aanwezig) == r and len(set(aanwezig)) == 1
        stabiel += zelfde
        if len(rij["fingerprints"]) > 1:
            drift.append(rij["kandidaat_id"])
        uit_rijen.append({
            **{k: rij[k] for k in ("kandidaat_id", "label", "start", "eind", "mogelijke_klassen", "contractfouten")},
            "fingerprint": sorted(rij["fingerprints"])[0] if len(rij["fingerprints"]) == 1 else "≠",
            "uitkomsten": rij["uitkomsten"], "aanwezig": f"{len(aanwezig)}/{r}",
            "accept_overeenstemming": max(statussen.values()) / len(aanwezig) if aanwezig else None,
            "klasse_overeenstemming": max(klassen.values()) / geaccepteerd if geaccepteerd else None,
            "zelfde_uitkomst": zelfde,
        })
    n = len(uit_rijen)
    return {
        "runs": r, "kandidaten": n,
        "detectie_stabiel": sum(x["aanwezig"] == f"{r}/{r}" for x in uit_rijen) / n if n else None,
        "kandidaatbeslisstabiliteit": stabiel / n if n else None,
        "fingerprint_drift": drift,
        "contractfouten": sum(x["contractfouten"] for x in uit_rijen),
        "rijen": uit_rijen,
    }


def markdown(per_casus: dict[str, dict[str, Any]]) -> str:
    def pct(x):
        return "–" if x is None else f"{100 * x:.0f}%"
    regels = ["| casus | runs | kandidaten | detectie stabiel | beslisstabiliteit | fingerprint-drift | contractfouten |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for cid, a in per_casus.items():
        regels.append(f"| {cid} | {a['runs']} | {a['kandidaten']} | {pct(a['detectie_stabiel'])} | "
                      f"{pct(a['kandidaatbeslisstabiliteit'])} | {len(a['fingerprint_drift'])} | {a['contractfouten']} |")
    return "\n".join(regels) + "\n"
