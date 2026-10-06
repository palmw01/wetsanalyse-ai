"""Kandidaatdekking van de deterministische detectoren op de ontwikkelsplit (ADR-001).

Meet wat de detectoren aanreiken tegen de conceptmarkeringen van de referentieset (status
`provisional`): per klasse de candidate recall, met en zonder spanopties, en wat elke detector als
enige vond. Geen modelaanroepen, geen graaf – draait in seconden, dus bij elke detectorwijziging.

Dit is **ankerdekking**, geen annotation recall: de referentie is niet vastgesteld (§13).

    python -m eval.kandidaat_eval [--casussen v1|concept[:ID]|pad:<bestand>] [--md uit.md] [--json uit.json]
                                  [--taal spacy:nl_core_news_md|null]

Met diagnostische casussen (`--casussen concept:IW05`) komt er per referentie-element een regel bij
(`elementen`): ligt er een kandidaat op die plek, of een spanoptie, en met welke klassen. Een
diagnostische meting telt nooit mee in een v1-totaal (`eval.casusbron`).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent.jas_pipeline.detectoren import BronTekst, detecteer_alles
from agent.jas_pipeline.fusie import fuseer
from agent.jas_pipeline.kandidaten import CandidateStatus
from eval import casusbron, manifest
from eval.metrieken import Ref, controleer_status, kandidaat_metrieken, kern, laagste_status


def gemengd(bijdragen) -> list[str]:
    """Kandidaten waarin detectoren met **disjuncte** klassensets op dezelfde span samenkomen.

    De fusie neemt de vlakke unie van de klassen; bij zo'n kandidaat is niet meer te zien welk bewijs
    welke klasse draagt. De telling is het bewijs voor of tegen klassegebonden bijdragen
    (EvidenceHypothesis, kandidaat na V7) – geen fout op zich.
    """
    per: dict[str, dict[str, set[str]]] = {}
    for b in bijdragen:
        per.setdefault(b.kandidaat_id, {}).setdefault(b.detector, set()).update(b.mogelijke_klassen)
    uit = []
    for kid, detectoren in per.items():
        sets = [s for s in detectoren.values() if s]
        if any(not (a & b) for i, a in enumerate(sets) for b in sets[i + 1:]):
            uit.append(kid)
    return sorted(uit)


def meet(taal: str = "spacy:nl_core_news_md", casussen: str = casusbron.STANDAARD) -> dict:
    spec, casussen = casussen, casusbron.laad(casussen)
    status = laagste_status(controleer_status(c) for c in casussen)
    provider = None
    if taal != "null":
        from agent.jas_pipeline.taal import maak_provider
        provider = maak_provider(taal)
    kandidaten, referentie, afgewezen, gemengde_unies = [], [], 0, {}
    for c in casussen:
        tekst = c["tekst"]
        analyse = provider.analyseer(tekst) if provider else None
        f = fuseer(detecteer_alles(BronTekst.van_tekst(c["id"], tekst, analyse=analyse)))
        gemengde_unies[c["id"]] = len(gemengd(f.bijdragen))
        for k in f.kandidaten:
            # Een kandidaat die de specificiteitsregels afwezen, reikte de span wél aan, maar
            # geen klasse meer.
            afgewezen += k.status is CandidateStatus.REJECTED
            kandidaten.append({
                "bron": c["id"], "start": k.span.start, "eind": k.span.eind,
                "possible_classes": [] if k.status is CandidateStatus.REJECTED else list(k.possible_classes),
                "detectors": sorted({e.detector for e in k.evidence}),
                "opties": [kern(tekst, o.span.start, o.span.eind) for o in k.span_options],
                "tekst": k.span.tekst,
            })
        for a in c["gold"]:
            referentie.append(Ref(c["id"], *kern(tekst, a["start"], a["eind"]), a["klasse"]))
    # Kandidaatgrenzen op dezelfde kern-normalisatie als de referentie (rand-interpunctie weg).
    for k in kandidaten:
        k["start"], k["eind"] = kern_van(casussen, k)
    uit = {**kandidaat_metrieken(kandidaten, referentie, status), "afgewezen_door_specificiteit": afgewezen,
           "gemengde_unies": sum(gemengde_unies.values()), "gemengde_unies_per_casus": gemengde_unies,
           "manifest": manifest.maak(spec)}
    if spec != casusbron.STANDAARD:
        uit["elementen"] = elementdekking(casussen, kandidaten)
        uit["kandidatenlijst"] = kandidaten
    return uit


def elementdekking(casussen: list[dict], kandidaten: list[dict]) -> dict[str, dict]:
    """Per referentie-element (`<casus>/<gid>`): kandidaat op die plek, spanoptie, klassen daar."""
    uit = {}
    for c in casussen:
        hier = [k for k in kandidaten if k["bron"] == c["id"]]
        for g in c["gold"]:
            s, e = kern(c["tekst"], g["start"], g["eind"])
            op = [k for k in hier if (k["start"], k["eind"]) == (s, e)]
            klassen = sorted({x for k in op for x in k["possible_classes"]})
            uit[f"{c['id']}/{g['gid']}"] = {
                "klasse": g["klasse"], "start": s, "eind": e, "core": bool(op),
                "optie": any((s, e) in map(tuple, k["opties"]) for k in hier),
                "met_klasse": g["klasse"] in klassen, "klassen": klassen}
    return uit


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
               "", f"Afgewezen door JAS-specificiteitsregels: {m['afgewezen_door_specificiteit']}.",
               "", "Unieke bijdrage per detector: " + ", ".join(f"{d} {n}" for d, n in m["unieke_bijdrage_per_detector"].items()),
               "", f"Gemengde unies (detectoren met disjuncte klassen op één span): {m['gemengde_unies']}."]
    if m.get("elementen"):
        ja = lambda b: "ja" if b else "–"  # noqa: E731
        regels += ["", "| element | klasse | kandidaat | optie | met klasse | klassen op de plek |",
                   "|---|---|:-:|:-:|:-:|---|"]
        regels += [f"| {gid} | {e['klasse']} | {ja(e['core'])} | {ja(e['optie'])} | {ja(e['met_klasse'])} | "
                   f"{', '.join(e['klassen'])} |" for gid, e in m["elementen"].items()]
    return "\n".join(regels) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--md")
    p.add_argument("--json")
    p.add_argument("--taal", default="spacy:nl_core_news_md")
    p.add_argument("--casussen", default=casusbron.STANDAARD, help="v1 | concept[:ID,…] | pad:<bestand>")
    args = p.parse_args()
    m = meet(args.taal, args.casussen)
    print(markdown(m))
    if args.md:
        Path(args.md).write_text(markdown(m), encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
