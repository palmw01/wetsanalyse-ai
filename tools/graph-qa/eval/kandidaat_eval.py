"""Kandidaatdekking van de deterministische detectoren op de ontwikkelsplit (ADR-001 PR 6+).

Meet wat de detectoren aanreiken tegen de conceptmarkeringen van de referentieset (status
`provisional`): per klasse de candidate recall, met en zonder spanopties, en wat elke detector als
enige vond. Geen modelaanroepen, geen graaf – draait in seconden, dus bij elke detectorwijziging.

Dit is **ankerdekking**, geen annotation recall: de referentie is niet vastgesteld (§13).

    python -m eval.kandidaat_eval [--md uit.md] [--json uit.json] [--taal spacy|null]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles, kandidaten_van
from eval.metrieken import Ref, controleer_status, kandidaat_metrieken, kern, laagste_status
from eval.taal_benchmark import ontwikkelcasussen


def meet(taal: str = "null") -> dict:
    casussen = ontwikkelcasussen()
    status = laagste_status(controleer_status(c) for c in casussen)
    provider = None
    if taal != "null":
        from agent.jas_pipeline.taal import maak_provider
        provider = maak_provider(taal)
    kandidaten, referentie = [], []
    for c in casussen:
        tekst = c["tekst"]
        analyse = provider.analyseer(tekst) if provider else None
        for k in kandidaten_van(detecteer_alles(BronTekst.van_tekst(c["id"], tekst, analyse=analyse))):
            kandidaten.append({
                "bron": c["id"], "start": k.span.start, "eind": k.span.eind,
                "possible_classes": list(k.possible_classes),
                "detectors": sorted({e.detector for e in k.evidence}),
                "opties": [kern(tekst, o.span.start, o.span.eind) for o in k.span_options],
            })
        for a in c["annotaties"]:
            referentie.append(Ref(c["id"], *kern(tekst, a["start"], a["end"]), a["klasse"]))
    # Kandidaatgrenzen op dezelfde kern-normalisatie als de referentie (rand-interpunctie weg).
    for k in kandidaten:
        k["start"], k["eind"] = kern_van(casussen, k)
    return kandidaat_metrieken(kandidaten, referentie, status)


def kern_van(casussen: list[dict], k: dict) -> tuple[int, int]:
    tekst = next(c["tekst"] for c in casussen if c["id"] == k["bron"])
    return kern(tekst, k["start"], k["eind"])


def markdown(m: dict) -> str:
    pct = lambda x: "–" if x is None else f"{100 * x:.0f}%"  # noqa: E731
    regels = [f"Referentie: {m['referenties']} spans, status **{m['referentie_status']}** (ankerdekking, geen recall).",
              f"Kandidaten: {m['kandidaten']} · candidate precision {pct(m['candidate_precision'])} · "
              f"kandidaten per referentie {m['kandidaten_per_referentie']:.2f}", "",
              "| klasse | n | candidate recall | met klasse |", "|---|---:|---:|---:|"]
    for k, v in m["per_klasse"].items():
        regels.append(f"| {k} | {v['n']} | {pct(v['candidate_recall'])} | {pct(v['met_klasse'])} |")
    regels += [f"| **totaal** | {m['referenties']} | {pct(m['candidate_recall'])} "
               f"(incl. opties {pct(m['candidate_recall_incl_opties'])}) | {pct(m['candidate_recall_met_klasse'])} |",
               "", "Unieke bijdrage per detector: " + ", ".join(f"{d} {n}" for d, n in m["unieke_bijdrage_per_detector"].items())]
    return "\n".join(regels) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--md")
    p.add_argument("--json")
    p.add_argument("--taal", default="null")
    args = p.parse_args()
    m = meet(args.taal)
    print(markdown(m))
    if args.md:
        Path(args.md).write_text(markdown(m), encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
