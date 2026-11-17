"""De meting van de proef `Zoekprofiel.model_kiest` (na de pilot LB3 van Lex Bench): per set de zoekvragenroute van nu
naast de route waarin een model per deelvraag kiest, live tegen de graaf en het model van de straat.

Kost modeltokens: alleen met akkoord, via `azure-infra` → `eval` met `eval_set: bronselectie_model`. Het image draagt
`docs/` niet, dus de sets komen van GitHub, van precies de commit van het image (`LEX_REVISIE`): wat gemeten wordt,
hoort bij de code die meet. Lokaal kan `--lokaal` (de sets uit de checkout), maar dan nog met een echt model en een
echte graaf.

De meting stopt vóór een set als het verbruik van het model boven `MAX_TOKENS` komt. Ze schrijft geen opname weg en
wijzigt geen set: het rapport staat in de log."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from eval.bronselectie_eval import ROUTES, meet_intake, model_kiest_route
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
MAX_TOKENS = 600_000


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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--lokaal", action="store_true", help="de sets uit de checkout in plaats van van GitHub")
    p.add_argument("--json", type=Path, help="het rapport ook als JSON wegschrijven")
    a = p.parse_args(argv)

    from agent.adapters.anthropic_llm import AnthropicLLM
    from agent.adapters.graphdb_graph import make_graph
    from agent.config import Settings

    settings = Settings.from_env()
    llm = AnthropicLLM(settings)
    graaf = make_graph(settings)
    modelmeting: dict[str, Any] = {}
    routes = {STANDAARD: ROUTES[STANDAARD], MODEL: model_kiest_route(llm, settings.llm_model, modelmeting)}
    print(f"Bronselectie: {STANDAARD} tegen {MODEL}, model {settings.llm_model}, "
          f"commit {os.environ.get('LEX_REVISIE', '') or 'lokaal'}", flush=True)
    rapport: dict[str, Any] = {}
    try:
        for naam, s in sets(lezer(a.lokaal)):
            if llm.meter.totaal > MAX_TOKENS:
                print(f"STOP: het verbruik ({llm.meter.totaal}) is boven {MAX_TOKENS}; {naam} en verder niet gemeten.",
                      flush=True)
                break
            r = meet_intake(graaf, s, routes)
            rapport[naam] = {k: {m: v[m] for m in ("recall_nodig", "recall", "precisie", "aantal")}
                             | {"per_deelvraag": [{"opties": d["opties"]} for d in v["per_deelvraag"]]}
                             for k, v in r.items()}
            print(f"{naam:40} nodig {_maat(r[STANDAARD], 'recall_nodig')} → {_maat(r[MODEL], 'recall_nodig')}"
                  f" | recall {_maat(r[STANDAARD], 'recall')} → {_maat(r[MODEL], 'recall')}"
                  f" | precisie {_maat(r[STANDAARD], 'precisie')} → {_maat(r[MODEL], 'precisie')}"
                  f" | verbruik tot nu {llm.meter.totaal}", flush=True)
    finally:
        graaf.close()
    print(f"MODEL: {modelmeting.get('llm_calls', 0)} aanroepen, verbruik {json.dumps(llm.meter.als_dict())}", flush=True)
    if a.json:
        a.json.write_text(json.dumps({"verbruik": llm.meter.als_dict(), "sets": rapport}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
