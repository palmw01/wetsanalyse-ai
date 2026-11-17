"""De meting van de proef `Zoekprofiel.model_kiest` (na de pilot LB3 van Lex Bench): per set de zoekvragenroute van nu
naast de route waarin een model per deelvraag kiest, live tegen de graaf en het model van de straat.

Kost modeltokens: alleen met akkoord, via `azure-infra` → `eval` met `eval_set: bronselectie_model`. Het image draagt
`docs/` niet, dus de sets komen van GitHub, van precies de commit van het image (`LEX_REVISIE`): wat gemeten wordt,
hoort bij de code die meet. Lokaal kan `--lokaal` (de sets uit de checkout), maar dan nog met een echt model en een
echte graaf.

Met `--rondes` kiest het model meer keren per set (de spreiding tussen runs), met `--varianten` meten varianten die de
pool verbreden elk één ronde, en per nodige bepaling zegt de meting waar ze afviel (`afval`). De meting stopt vóór een
set als het verbruik van het model boven `MAX_TOKENS` komt. Ze schrijft geen opname weg en
wijzigt geen set: het rapport staat in de log."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from eval.bronselectie_eval import ROUTES, kandidaten_route, meet_intake, model_kiest_route
from eval.wortel import WORTEL as WORTEL_REPO

REPO = "palmw01/wetsanalyse-ai"
WORTEL = WORTEL_REPO
REFERENTIE = "docs/wetsanalyse/referentieset-bronselectie"
PILOT = "docs/lex-bench/bronselectie/pilot"
PILOTMETING = "docs/architectuur/metingen/lex-bench-2026-11-17-pilot"
#: De sets met deelvragen; `invorderbaarheid-concept` heeft er geen.
SETS = ("bestuurdersaansprakelijkheid-concept", "bezwaar-ontvankelijkheid-concept",
        "invorderbaarheid-deelvragen-concept", "kwijtschelding-concept", "rekeningafspraken-deelvragen-concept",
        "termijnen-deelvragen-concept", "verrekening-concept")
CASUSSEN = {"LB-07": "lb-07-beslistermijn", "LB-08": "lb-08-terugvordering-toeslag",
            "LB-09": "lb-09-achteraf-belasting"}
STANDAARD = "zoekvragen standaard (stap 8)"
MODEL = "model kiest (proef)"
#: Het plafond op het verbruik van het model over de hele meting (invoer, cache en uitvoer samen).
MAX_TOKENS = 1_500_000


def lezer(lokaal: bool):
    """Een functie pad → JSON: uit de checkout, of van GitHub op de commit van het image."""
    if lokaal:
        return lambda pad: json.loads((WORTEL / pad).read_text(encoding="utf-8"))
    revisie = os.environ.get("LEX_REVISIE", "").strip()
    if not revisie:
        raise SystemExit("LEX_REVISIE ontbreekt: zonder commit weet de meting niet welke sets bij deze code horen.")
    import httpx

    client = httpx.Client(timeout=30, follow_redirects=True)

    def lees(pad: str) -> Any:
        r = client.get(f"https://raw.githubusercontent.com/{REPO}/{revisie}/{pad}")
        r.raise_for_status()
        return r.json()
    return lees


def sets(lees) -> list[tuple[str, dict[str, Any]]]:
    """De sets van de meting: de referentiesets met deelvragen, en de drie pilotcasussen met de bevroren
    teamverwachting als verwachting (zoals `lex_bench_review._set_met_team`)."""
    from eval.lex_bench_review import _set_met_team

    uit = [(naam, lees(f"{REFERENTIE}/{naam}/set.json")) for naam in SETS]
    for casus, map_ in CASUSSEN.items():
        dossier = lees(f"{PILOT}/{map_}/set.json")
        tv = lees(f"{PILOTMETING}/{casus}/teamverwachting.json")
        uit.append((casus, _set_met_team({**dossier, "status": "concept"}, tv)))
    return uit


def _maat(r: dict[str, Any], sleutel: str) -> str:
    w = r.get(sleutel)
    return "–" if w is None else f"{w:.2f}"


#: De varianten die de pool verbreden (analyse bronselectie, 17 nov 2026): elk één ronde naast het model.
VARIANTEN = {"definitie_brug": {"definitie_brug": True}, "verwijzingen": {"verwijzingen": True}}
#: Waar een nodige bepaling afviel, van vroeg naar laat.
FASEN = ("niet gevonden", "gevonden, niet bij de 40", "bij de 40, niet gekozen", "gekozen")


def afval(graaf: Any, s: dict[str, Any], spoor: list[dict[str, Any]]) -> dict[str, Any]:
    """Per nodige bepaling (kern of afhankelijkheid) van de set: waar ze afviel. *Gevonden* is wat de index bij de
    deelvraag vindt (`_pool`, de woordenroute vóór de rangschikking) samen met de pool rond de gebeurtenis; *bij de 40*
    is wat het model te zien kreeg; *gekozen* wat het koos. Uit het spoor van de eerste modelronde."""
    from agent import deelvraag_zoeken, zoekvragen, zoektermen
    from eval.bronselectie_eval import _pool, _raakt

    per_vraag = {e["vraag"]: e for e in spoor if e["set"] == s["naam"]}
    gebeurtenis: list[str] = []
    if s.get("gebeurtenis"):
        buiten = zoektermen.uitsluitstammen(zoektermen.buiten_uit_afbakening("Buiten de afbakening: " + s.get("buiten", "")))
        gebeurtenis = [k["bron_iri"] for k in zoekvragen.pool(graaf, gebeurtenis=s["gebeurtenis"], regelingen=s["regelingen"],
                                                               buiten=buiten)["kandidaten"]]
    tel = {f: 0 for f in FASEN}
    voorbeelden: dict[str, list[str]] = {f: [] for f in FASEN}
    for i, vraag in enumerate(s["deelvragen"]):
        e = per_vraag.get(vraag)
        if e is None:
            continue
        gevonden = set(_pool(graaf, s, vraag, deelvraag_zoeken.STANDAARD_PROFIEL)) | set(gebeurtenis)
        for v in s["verwacht"]:
            if v["deelvraag"] != i or v["rol"] not in ("kern", "afhankelijkheid"):
                continue
            iri = v["bron_iri"]
            raakt = lambda lijst: any(_raakt(c, iri) for c in lijst)  # noqa: E731
            fase = (FASEN[3] if raakt(e["gekozen"]) else FASEN[2] if raakt(e["kandidaten"])
                    else FASEN[1] if raakt(gevonden) else FASEN[0])
            tel[fase] += 1
            if len(voorbeelden[fase]) < 4:
                voorbeelden[fase].append(f"DV{i + 1} {iri.split(':', 1)[-1]}")
    return {"telling": tel, "voorbeelden": voorbeelden}


def meet_kandidaten(a: argparse.Namespace) -> int:
    """De recall van de kandidatenlijst per grens (en eventueel een variant, `80+definitie_brug`), zonder model: 0
    tokens. Het model kiest bijna alles wat nodig is en bij de kandidaten staat, dus dit is zijn plafond."""
    from agent.adapters.graphdb_graph import make_graph
    from agent.config import Settings

    graaf = make_graph(Settings.from_env())
    routes: dict[str, Any] = {}
    for c in [x for x in a.kandidaten.split(",") if x]:
        grens, _, variant = c.partition("+")
        routes[c] = kandidaten_route(int(grens), VARIANTEN.get(variant) if variant else None)
    print(f"Kandidatenlijst (zonder model): {', '.join(routes)}; commit {os.environ.get('LEX_REVISIE', '') or 'lokaal'}",
          flush=True)
    som = {c: [0, 0] for c in routes}
    rapport: dict[str, Any] = {}
    try:
        for naam, s in sets(lezer(a.lokaal)):
            r = meet_intake(graaf, s, routes)
            for c, v in r.items():
                som[c][0] += sum(d["gevonden_nodig"] for d in v["per_deelvraag"])
                som[c][1] += sum(d["nodig"] for d in v["per_deelvraag"])
            rapport[naam] = {c: v["recall_nodig"] for c, v in r.items()}
            print(f"{naam:40} " + " | ".join(f"{c} {_maat(v, 'recall_nodig')}" for c, v in r.items()), flush=True)
    finally:
        graaf.close()
    print("TOTAAL nodig bij de kandidaten: " + " | ".join(f"{c} {g}/{n}" for c, (g, n) in som.items()), flush=True)
    if a.json:
        a.json.write_text(json.dumps({"som": som, "sets": rapport}, ensure_ascii=False, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--lokaal", action="store_true", help="de sets uit de checkout in plaats van van GitHub")
    p.add_argument("--json", type=Path, help="het rapport ook als JSON wegschrijven")
    p.add_argument("--rondes", type=int, default=1, help="hoe vaak het model per set kiest (de spreiding tussen runs)")
    p.add_argument("--varianten", default="", help="komma-gescheiden varianten uit VARIANTEN, elk één ronde")
    p.add_argument("--kandidaten", default="",
                   help="zonder model: de recall van de kandidatenlijst per grens, bv. 40,80,120 of 80+definitie_brug")
    a = p.parse_args(argv)
    if a.kandidaten:
        return meet_kandidaten(a)

    from agent.adapters.anthropic_llm import AnthropicLLM
    from agent.adapters.graphdb_graph import make_graph
    from agent.config import Settings

    settings = Settings.from_env()
    llm = AnthropicLLM(settings)
    graaf = make_graph(settings)
    modelmeting: dict[str, Any] = {}
    spoor: list[dict[str, Any]] = []
    routes: dict[str, Any] = {STANDAARD: ROUTES[STANDAARD]}
    for r in range(1, a.rondes + 1):
        routes[f"{MODEL} {r}"] = model_kiest_route(llm, settings.llm_model, modelmeting, spoor=spoor if r == 1 else None)
    for v in [x for x in a.varianten.split(",") if x]:
        routes[f"variant {v}"] = model_kiest_route(llm, settings.llm_model, modelmeting, vlaggen=VARIANTEN[v])
    print(f"Bronselectie: {', '.join(routes)}; model {settings.llm_model}, "
          f"commit {os.environ.get('LEX_REVISIE', '') or 'lokaal'}", flush=True)
    rapport: dict[str, Any] = {}
    totaal_afval = {f: 0 for f in FASEN}
    try:
        for naam, s in sets(lezer(a.lokaal)):
            if llm.meter.totaal > MAX_TOKENS:
                print(f"STOP: het verbruik ({llm.meter.totaal}) is boven {MAX_TOKENS}; {naam} en verder niet gemeten.",
                      flush=True)
                break
            r = meet_intake(graaf, s, routes)
            modellen = [r[k]["recall_nodig"] or 0.0 for k in r if k.startswith(MODEL)]
            prec = [r[k]["precisie"] or 0.0 for k in r if k.startswith(MODEL)]
            val = afval(graaf, s, spoor)
            for f, n in val["telling"].items():
                totaal_afval[f] += n
            rapport[naam] = {"routes": {k: {m: v[m] for m in ("recall_nodig", "recall", "precisie", "aantal")}
                                        | {"per_deelvraag": [{"opties": d["opties"]} for d in v["per_deelvraag"]]}
                                        for k, v in r.items()},
                             "afval": val}
            varianten = " | ".join(f"{k.removeprefix('variant ')} {_maat(v, 'recall_nodig')}"
                                   for k, v in r.items() if k.startswith("variant "))
            print(f"{naam:40} nodig {_maat(r[STANDAARD], 'recall_nodig')} → model gem. {sum(modellen) / len(modellen):.2f}"
                  f" ({min(modellen):.2f}–{max(modellen):.2f})"
                  f" | precisie {_maat(r[STANDAARD], 'precisie')} → {sum(prec) / len(prec):.2f}"
                  + (f" | {varianten}" if varianten else "")
                  + f" | verbruik tot nu {llm.meter.totaal}", flush=True)
            print(f"{'':40} afval: " + ", ".join(f"{f} {n}" for f, n in val["telling"].items())
                  + " | niet gevonden bv. " + "; ".join(val["voorbeelden"][FASEN[0]]), flush=True)
    finally:
        graaf.close()
    print("AFVAL TOTAAL: " + ", ".join(f"{f} {n}" for f, n in totaal_afval.items()), flush=True)
    print(f"MODEL: {modelmeting.get('llm_calls', 0)} aanroepen, verbruik {json.dumps(llm.meter.als_dict())}", flush=True)
    if a.json:
        a.json.write_text(json.dumps({"verbruik": llm.meter.als_dict(), "afval": totaal_afval, "sets": rapport},
                                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
