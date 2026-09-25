"""Meting van de annotatieketen op de ontwikkelcasussen (ADR-001 PR 16).

Oorspronkelijk een A/B van de legacy-keten tegen `hybrid_v1`; sinds PR 18 bestaat alleen de
laatste nog, en meet dit harnas die – oude rapporten met legacy-runs blijven analyseerbaar. Per
casus dezelfde bronpassage (`keten_fixture`), en per route en casus:

- **kwaliteit tegen de referentie**: P/R/F1 per klasse, micro/macro, confusion, exacte span en
  partiële overlap (`eval/metrieken.py`), op positie. De referentie is `provisional`, dus recall
  heet hier **ankerdekking** – dit rapport kan geen annotation recall claimen;
- **reproduceerbaarheid** over de herhalingen (`stabiliteit_analyse.analyseer_casus`);
- **efficiëntie**: modelcalls, tokens per soort, seconden, en voor hybrid het aandeel beslissingen
  zonder model, review- en human-review-aandeel;
- **fouten per categorie** volgens fouttaxonomie v2 (`eval/fouttaxonomie.py`, onderzoek §8): primair,
  secundair en soort (juridisch/technisch/evaluatie). `debatable` in de referentie telt nergens mee.

Een meting mag de gemeten toestand niet veranderen: geen api, geen checkpointer, lege
annotatiepoort. Met `--offline` draait het tegen een nep-LLM (geen kosten, alleen de mechaniek).

    python -m eval.compare_pipelines --output /pad/ab.json [--cases IW01 …] [--herhalingen 3] [--offline]
    python -m eval.compare_pipelines --analyseer /pad/ab.json --md /pad/ab.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from eval.keten_fixture import (
    TOKENVELDEN, Capture, FixtureGraph, LegeAnnotaties, fixture_doel, ketensettings, laad_cases, ontwikkelcases,
)
from eval.beslisstabiliteit import rapport as beslisrapport
from eval.fouttaxonomie import Uitslag, classificeer, tel, uit_elementen
from eval.metrieken import Ref, classificatie_metrieken, controleer_status, kern, laagste_status, recall_naam
from eval.stabiliteit_analyse import analyseer_casus

# `legacy` bestaat alleen nog in rapporten van vóór ADR-001 PR 18; de analyse kan die nog lezen,
# meten kan alleen de huidige keten.
ROUTES = ("legacy", "hybrid_v1")
MEETBAAR = ("hybrid_v1",)


def _posities(elementen: list[dict[str, Any]], tekst: str, casus: str) -> list[Ref]:
    """Elementen als (casus, start, eind, klasse). In de fixture is de bronnode de casustekst, dus
    de lokale ankeroffsets zijn posities in die tekst."""
    uit = []
    for e in elementen:
        a = (e.get("ankers") or [None])[0]
        if a is None:
            continue
        uit.append(Ref(casus, *kern(tekst, a["start"], a["eind"]), e.get("klasse", "")))
    return uit


def _gold(c: dict[str, Any]) -> list[dict[str, Any]]:
    """De referentie van één casus op kern-posities, met status (voor `debatable`)."""
    return [{"gid": g["gid"], "start": s, "eind": e, "klasse": g["klasse"],
             "annotation_status": g.get("annotation_status")}
            for g in c["gold"] for s, e in [kern(c["tekst"], g["start"], g["eind"])]]


def _debatable(c: dict[str, Any]) -> set[tuple[int, int]]:
    return {(g["start"], g["eind"]) for g in _gold(c) if g["annotation_status"] == "debatable"}


def _fouten(run: dict[str, Any], c: dict[str, Any]) -> Uitslag:
    """Fouttaxonomie v2 op één run. Alleen voorstellen: afgewezen kandidaten en de batch-unie
    ontbreken in de events (V4), dus leakage en model-afwijzingen blijven hier ongeteld."""
    voorstellen, kandidaten = uit_elementen(run["na_keten"], c["tekst"], c["id"])
    return classificeer(_gold(c), voorstellen, kandidaten, bron=c["id"])


def meet(cases: list[dict[str, Any]], herhalingen: int, settings: Any, maak_llm, rapport: dict[str, Any],
         bewaar=lambda: None, routes: tuple[str, ...] = MEETBAAR) -> None:
    from agent.agent import answer_stream      # pas hier: agentmodules laden de configuratie

    async def run():
        for ronde in range(1, herhalingen + 1):
            for c in cases:
                for route in routes:          # afwisselend per casus, zodat een storing beide raakt
                    s = settings
                    llm = Capture(maak_llm(s))
                    start = time.monotonic()
                    events = [e async for e in answer_stream(
                        "Annoteer de aangewezen bronpassage.", doel=fixture_doel(c), settings=s, llm=llm,
                        graph=FixtureGraph(c["tekst"]), annotaties=LegeAnnotaties(c["tekst"]))]
                    run_ev = next((e["run"] for e in events if e.get("type") == "run"), {})
                    rapport["runs"].append({
                        "route": route, "casus": c["id"], "ronde": ronde,
                        "seconden": round(time.monotonic() - start, 2), "modelcalls": len(llm.calls),
                        "tokens": {v: sum(k.get(v, 0) for k in llm.calls) for v in TOKENVELDEN},
                        "fout": any(e.get("type") == "error" for e in events),
                        "meting": (run_ev.get("instellingen") or {}).get("meting", {}),
                        "na_keten": [e["element"] for e in events if e.get("type") == "element"],
                        # Het beslisregister (V4): ook wat geen voorstel werd.
                        "beslissingen": next((e["dekking"].get("beslissingen", []) for e in events
                                              if e.get("type") == "dekking"), []),
                    })
                    bewaar()
    asyncio.run(run())


def _v1(c: dict[str, Any]) -> dict[str, Any]:
    """Rapporten van vóór referentieset v1 dragen hun casussen in het oude formaat (`annotaties`,
    `end`); zonder deze vertaling zijn ze niet meer te analyseren."""
    if "gold" in c:
        return c
    oud = {k: v for k, v in c.items() if k not in ("annotaties", "artikel")}
    return {**oud, "gold": [{"gid": a["id"], "start": a["start"], "eind": a["end"], "tekst": a["tekst"],
                             "klasse": a["klasse"], "annotation_status": None} for a in c["annotaties"]]}


def analyseer(rapport: dict[str, Any]) -> dict[str, Any]:
    casussen = {c["id"]: _v1(c) for c in rapport["casussen"]}
    status = laagste_status(controleer_status(c) for c in rapport["casussen"])   # vóór de vertaling
    uit: dict[str, Any] = {"referentie_status": status, "recall_heet": recall_naam(status), "routes": {}}
    for route in ROUTES:
        runs = [r for r in rapport["runs"] if r["route"] == route and not r["fout"]]
        if not runs:
            continue
        # `debatable` blijft buiten teller én noemer: niet in de referentie, en een voorstel op
        # die plek telt ook niet als overbodig.
        betwist = {(cid, *p) for cid, c in casussen.items() for p in _debatable(c)}
        ref = [Ref(cid, g["start"], g["eind"], g["klasse"]) for cid, c in casussen.items() for g in _gold(c)
               if g["annotation_status"] != "debatable"]

        def telt(p: Ref) -> bool:
            return (p.bron, p.start, p.eind) not in betwist

        per_ronde, onbetwist, uitslagen = [], [], []
        for ronde in sorted({r["ronde"] for r in runs}):
            deze = [r for r in runs if r["ronde"] == ronde]
            vs = [p for r in deze for p in _posities(r["na_keten"], casussen[r["casus"]]["tekst"], r["casus"])
                  if telt(p)]
            # Een geel voorstel is een vraag aan de jurist, geen uitspraak: apart meten wat de keten
            # zonder voorbehoud voorstelt.
            zeker = [p for r in deze for p in _posities([e for e in r["na_keten"] if e.get("aandacht") != "geel"],
                                                         casussen[r["casus"]]["tekst"], r["casus"]) if telt(p)]
            per_ronde.append(classificatie_metrieken(vs, ref, status))
            onbetwist.append(classificatie_metrieken(zeker, ref, status))
            uitslagen += [_fouten(r, casussen[r["casus"]]) for r in deze]
        stabiliteit, beslis = {}, {}
        for cid, c in casussen.items():
            reeks = [r["na_keten"] for r in sorted(runs, key=lambda r: r["ronde"]) if r["casus"] == cid]
            if len(reeks) >= 2:
                stabiliteit[cid] = analyseer_casus(c["tekst"], reeks)
            registers = [r["beslissingen"] for r in sorted(runs, key=lambda r: r["ronde"])
                         if r["casus"] == cid and r.get("beslissingen")]     # oude rapporten: geen register
            if len(registers) >= 2:
                beslis[cid] = beslisrapport(registers)
        n = len(runs)
        beslissingen = Counter()
        for r in runs:
            beslissingen.update((r["meting"].get("per_status") or {}))
        uit["routes"][route] = {
            "runs": n,
            "micro_f1": _gem([m["micro"]["f1"] for m in per_ronde]),
            "micro_precision": _gem([m["micro"]["precision"] for m in per_ronde]),
            "micro_ankerdekking": _gem([m["micro"]["recall"] for m in per_ronde]),
            "macro_f1": _gem([m["macro_f1"] for m in per_ronde]),
            "onbetwist_precision": _gem([m["micro"]["precision"] for m in onbetwist]),
            "onbetwist_ankerdekking": _gem([m["micro"]["recall"] for m in onbetwist]),
            "exact_span": _gem([m["exact_span"] for m in per_ronde]),
            "partieel_zelfde_klasse": _gem([m["partial_overlap_zelfde_klasse"] for m in per_ronde]),
            "per_klasse_f1": _per_klasse(per_ronde),
            "foutcategorieen": tel(uitslagen),
            "debatable_uitgesloten": len(betwist),
            "beslisstabiliteit": {
                "kandidaatbeslisstabiliteit": _gem([b["kandidaatbeslisstabiliteit"] for b in beslis.values()]),
                "fingerprint_drift": sum(len(b["fingerprint_drift"]) for b in beslis.values()),
                "per_casus": beslis,
            },
            "stabiliteit": {
                "detectie_stabiel": _gem([s["detectie_stabiel"] for s in stabiliteit.values()]),
                "span_exact": _gem([s["span_exact"] for s in stabiliteit.values()]),
                "klasse_unaniem": _gem([s["klasse_unaniem"] for s in stabiliteit.values()]),
            },
            "efficientie": {
                "modelcalls_per_run": round(sum(r["modelcalls"] for r in runs) / n, 2),
                "tokens_per_run": {v: round(sum(r["tokens"][v] for r in runs) / n) for v in TOKENVELDEN},
                "seconden_per_run": round(sum(r["seconden"] for r in runs) / n, 2),
                "elementen_per_run": round(sum(len(r["na_keten"]) for r in runs) / n, 2),
                "zonder_model": _deel(sum(r["meting"].get("deterministisch", 0) for r in runs),
                                      sum(r["meting"].get("kandidaten", 0) for r in runs)),
                "human_review": _deel(beslissingen.get("HUMAN_REVIEW", 0), sum(beslissingen.values())),
                "review_calls_per_run": round(sum(r["meting"].get("review_calls", 0) for r in runs) / n, 2),
            },
        }
    return uit


def _gem(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def _deel(a, b):
    return round(a / b, 3) if b else None


def _per_klasse(per_ronde):
    klassen = sorted({k for m in per_ronde for k in m["per_klasse"]})
    return {k: _gem([m["per_klasse"].get(k, {}).get("f1") for m in per_ronde]) for k in klassen}


def markdown(a: dict[str, Any]) -> str:
    routes = list(a["routes"])

    def rij(naam: str, pad: str, pct: bool = True) -> str:
        def f(x):
            return "–" if x is None else (f"{100 * x:.0f}%" if pct else str(x))
        return f"| {naam} | " + " | ".join(f(_pak(a["routes"][r], pad)) for r in routes) + " |"
    regels = [f"Referentie: **{a['referentie_status']}** – recall heet hier *{a['recall_heet']}*, geen annotation recall.",
              "", "| maat | " + " | ".join(routes) + " |", "|---|" + "---:|" * len(routes),
              rij("micro-F1", "micro_f1"), rij("micro-precisie", "micro_precision"),
              rij(a["recall_heet"], "micro_ankerdekking"), rij("macro-F1", "macro_f1"),
              rij("precisie, alleen onbetwist", "onbetwist_precision"),
              rij(a["recall_heet"] + ", alleen onbetwist", "onbetwist_ankerdekking"),
              rij("exacte span", "exact_span"), rij("partieel, zelfde klasse", "partieel_zelfde_klasse"),
              rij("detectie stabiel", "stabiliteit.detectie_stabiel"), rij("span exact over runs", "stabiliteit.span_exact"),
              rij("klasse unaniem over runs", "stabiliteit.klasse_unaniem"),
              rij("kandidaatbeslisstabiliteit", "beslisstabiliteit.kandidaatbeslisstabiliteit"),
              rij("fingerprint-drift (bug)", "beslisstabiliteit.fingerprint_drift", pct=False),
              rij("modelcalls per run", "efficientie.modelcalls_per_run", pct=False),
              rij("seconden per run", "efficientie.seconden_per_run", pct=False),
              rij("elementen per run", "efficientie.elementen_per_run", pct=False),
              rij("beslissingen zonder model", "efficientie.zonder_model"),
              rij("human review", "efficientie.human_review"), "",
              "Foutcategorieën (fouttaxonomie v2, primair): " + "; ".join(
                  f"{r}: {a['routes'][r]['foutcategorieen']['primair']}" for r in routes),
              "Per soort: " + "; ".join(f"{r}: {a['routes'][r]['foutcategorieen']['per_soort']}" for r in routes)]
    return "\n".join(regels) + "\n"


def _pak(d, pad):
    for deel in pad.split("."):
        d = (d or {}).get(deel)
    return d


class _NepLLM:
    """Offline: legacy krijgt een lege annotatie, hybrid een classifier die niets kiest. Alleen om
    het harnas te toetsen; de uitkomst zegt niets over kwaliteit."""

    def __init__(self, _settings):
        pass

    def create(self, **kw):
        from types import SimpleNamespace as N
        return N(content=[N(type="text", text='{"elementen": [], "oordelen": [], "ontbrekend": []}')],
                 stop_reason="end_turn", usage=None)

    def stream(self, **kw):
        raise AssertionError("de ketens met een expliciet doel streamen niet")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", nargs="+", default=None)
    ap.add_argument("--herhalingen", type=int, default=3)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--analyseer", type=Path, help="alleen een bestaand rapport analyseren")
    ap.add_argument("--md", type=Path)
    ap.add_argument("--routes", nargs="+", choices=MEETBAAR, default=list(MEETBAAR),
                    help="welke route(s) meten; legacy bestaat sinds PR 18 niet meer")
    args = ap.parse_args()
    if args.analyseer:
        a = analyseer(json.loads(args.analyseer.read_text()))
    else:
        if not args.output or args.output.exists():
            ap.error("--output moet een nieuw pad zijn")
        cases = laad_cases(args.cases or ontwikkelcases())
        from agent.config import Settings
        from eval.run_eval import _laad_env
        _laad_env()
        settings = ketensettings(Settings.from_env())
        if args.offline:
            maak = _NepLLM
        else:
            from agent.adapters.anthropic_llm import AnthropicLLM
            maak = AnthropicLLM
        rapport = {"status": "bezig", "model": settings.llm_model, "offline": args.offline, "routes": args.routes,
                   "herhalingen": args.herhalingen, "casussen": cases, "runs": []}
        bewaar = lambda: args.output.write_text(json.dumps(rapport, ensure_ascii=False, indent=2))  # noqa: E731
        try:
            meet(cases, args.herhalingen, settings, maak, rapport, bewaar, tuple(args.routes))
            rapport["status"] = "gemeten_nog_niet_juridisch_beoordeeld"
        except Exception as exc:
            rapport.update(status="niet_volledig_gemeten", fout=f"{type(exc).__name__}: {str(exc)[:300]}")
        bewaar()
        a = analyseer(rapport)
    tekst = markdown(a)
    print(tekst)
    if args.md:
        args.md.write_text(tekst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
