"""Meting van *Schrijf de uitleg in B1* (spoor I2): hoe vaak raakt een uitleg van Lex een B1-toets?

Live: de graaf (`GRAPHDB_MCP_URL`/`GRAPHDB_TOKEN`) en het model (`LLM_MODEL`) – dit kost geld. Per begrip
uit de ontwikkelset van *Zoek de brondefinitie* (`kaartacties_brondefinitie.json`, Invorderingswet en
AWR) haalt de meting zonder model de sterkste brondefinitie op, neemt die als definitie en laat Lex de
uitleg schrijven, `--runs` keer (standaard 3: dezelfde vraag geeft per run een andere tekst, zie het
meetlogboek). Gemeten per run en over alle runs:

- **voorstel** – het deel van de pogingen dat een uitleg opleverde;
- **per code** – hoe vaak elke B1-toets (`begrip_b1.CODES`) afging;
- **schoon** – het deel van de uitleggen zonder enig B1-aandachtspunt;
- **woorden per zin** en **zinnen** – gemiddeld.

Een ontwikkelset, geen blinde meting. Gebruik: `uv run python -m eval.uitleg_eval [--runs 3] [--json pad]`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from agent import begrip_kaart as bk
from agent.begrippen_pipeline import begrip_b1, fragmenten as fragmenten_mod, kaartacties as ka
from agent.begrippen_pipeline.model import Bron

SET = Path(__file__).with_name("kaartacties_brondefinitie.json")


def _instellingen():
    from agent.config import Settings
    return Settings.from_env()


def _graaf(settings):
    from agent.adapters.graphdb_graph import make_graph
    return make_graph(settings)


def _llm(settings):
    from agent.adapters.anthropic_llm import AnthropicLLM
    return AnthropicLLM(settings)


def _brontekst(graph, iri: str) -> str:
    from agent.graph.results import parse_select
    rijen = parse_select(graph.sparql(bk.PREFIXES + f"SELECT ?t WHERE {{ <{iri}> bwb:tekst ?t }} LIMIT 1"))
    return rijen[0]["t"] if rijen else ""


def _woorden_per_zin(tekst: str) -> tuple[int, float]:
    a = begrip_b1.standaard_provider().analyseer(tekst)
    zinnen = [tekst[z.start:z.eind] for z in a.zinnen] or [tekst]
    return len(zinnen), sum(len(begrip_b1._woorden(z)) for z in zinnen) / len(zinnen)


def een_uitleg(llm, model: str, graph, case: dict) -> dict:
    """Eén poging voor één begrip: de brondefinitie (zonder model), dan de uitleg (met model)."""
    invoer = {"begrip": {"inhoud": {"naam": case["naam"], "alternatieve_termen": case.get("alternatieve_termen", [])}},
              "selecties": [{"bron_iri": s} for s in case["selecties"]]}
    r = bk.zoek_brondefinities(graph, invoer)
    if not r.voorstellen:
        return {"case": case["id"], "uitleg": "", "melding": r.melding or "geen brondefinitie", "codes": []}
    d = r.voorstellen[0]["definitie"]
    tekst = _brontekst(graph, d["definitie_bron_iri"])
    bron = Bron(bron_iri=d["definitie_bron_iri"], tekst=tekst, label=d.get("definitie_vindplaats", ""),
                bron_hash=hashlib.sha256(tekst.encode()).hexdigest())
    frs = list(fragmenten_mod.knip(bron))[:ka.MAX_FRAGMENTEN]
    k = ka.Kant(id=case["id"], inhoud={"naam": case["naam"], "definitie": d["definitie"]}, leden=())
    prompt = "\n".join(["Schrijf de uitleg in B1 bij dit begrip.", "", f'BEGRIP "{k.naam}"',
                        f'  huidige definitie: "{d["definitie"]}"', "", *ka.fragmentblok(frs)])
    item = ka._vraag(llm, model, ka.SYSTEEM_UITLEG, prompt, ka.schema_uitleg(frs), {})
    uit = ka.valideer_uitleg(k, frs, item)
    if not uit.voorstellen:
        return {"case": case["id"], "uitleg": "", "melding": uit.melding, "codes": []}
    v = uit.voorstellen[0]
    zinnen, wpz = _woorden_per_zin(v["tekst"])
    return {"case": case["id"], "uitleg": v["tekst"], "melding": "", "zinnen": zinnen, "woorden_per_zin": wpz,
            "codes": [c for c in v["aandachtspunten"] if c in begrip_b1.CODES]}


def vat_samen(pogingen: list[dict]) -> dict:
    met = [p for p in pogingen if p["uitleg"]]
    codes = Counter(c for p in met for c in p["codes"])
    n = max(1, len(met))
    return {"pogingen": len(pogingen), "voorstel": len(met) / max(1, len(pogingen)),
            "schoon": sum(not p["codes"] for p in met) / n,
            "per_code": {c: codes[c] / n for c in begrip_b1.CODES},
            "zinnen": sum(p["zinnen"] for p in met) / n, "woorden_per_zin": sum(p["woorden_per_zin"] for p in met) / n}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--json", type=Path, help="schrijf het rapport ook als JSON")
    a = p.parse_args(argv)
    cases = json.loads(SET.read_text())["cases"]
    settings = _instellingen()
    graph, llm = _graaf(settings), _llm(settings)
    try:
        runs = [[een_uitleg(llm, settings.llm_model, graph, c) for c in cases] for _ in range(a.runs)]
    finally:
        graph.close()
    rapport = {"runs": [vat_samen(r) for r in runs], "totaal": vat_samen([x for r in runs for x in r]),
               "pogingen": runs}
    for i, r in enumerate(rapport["runs"], 1):
        print(f"run {i}: voorstel {r['voorstel']:.2f} · schoon {r['schoon']:.2f} · zinnen {r['zinnen']:.1f} · "
              f"woorden/zin {r['woorden_per_zin']:.1f}")
    t = rapport["totaal"]
    print("\ntotaal: " + " · ".join(f"{c} {v:.2f}" for c, v in t["per_code"].items()))
    print(f"voorstel {t['voorstel']:.2f} · schoon {t['schoon']:.2f}")
    if a.json:
        a.json.write_text(json.dumps(rapport, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
