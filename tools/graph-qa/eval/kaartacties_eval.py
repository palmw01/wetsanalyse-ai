"""Meting van *Zoek de brondefinitie* (spoor D, fase E): vindt Lex de wettelijke definitie, en op de goede plaats?

Live tegen de graaf (`GRAPHDB_MCP_URL`/`GRAPHDB_TOKEN`), zonder model en dus zonder kosten. Per case
een werkgebied (selecties) en een begrip; verwacht zijn de bepalingen die de term definiëren, met de
plaats die Lex ze moet geven (`werkgebied`, `regeling`, `definitieverwijzing`, `elders`). Gemeten:

- **recall** – welk deel van de verwachte definities als voorstel terugkomt;
- **plaats** – of elk gevonden verwacht voorstel de verwachte plaats krijgt;
- **volgorde** – of de voorstellen van sterk naar zwak staan;
- **letterlijk** – of elke voorgestelde definitie letterlijk in de tekst van haar bron staat (garantie: 1.0).

De set (`eval/kaartacties_brondefinitie.json`) is een **ontwikkelset**: opgesteld bij de bouw, niet
door een jurist vastgesteld. Gebruik: `uv run python -m eval.kaartacties_eval [--json pad]`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent import begrip_kaart as bk
from agent.begrippen_pipeline import kaartacties as ka
from agent.graph.results import parse_select

SET = Path(__file__).with_name("kaartacties_brondefinitie.json")


def _graaf():
    from agent.adapters.graphdb_graph import make_graph
    from agent.config import Settings
    return make_graph(Settings.from_env())


def _brontekst(graph, iri: str) -> str:
    rijen = parse_select(graph.sparql(bk.PREFIXES + f"SELECT ?t WHERE {{ <{iri}> bwb:tekst ?t }} LIMIT 1"))
    return rijen[0]["t"] if rijen else ""


def meet(graph, cases: list[dict]) -> dict:
    uit = []
    for c in cases:
        invoer = {"begrip": {"inhoud": {"naam": c["naam"], "alternatieve_termen": c.get("alternatieve_termen", [])}},
                  "selecties": [{"bron_iri": s} for s in c["selecties"]]}
        r = bk.zoek_brondefinities(graph, invoer)
        gevonden = {v["definitie"]["definitie_bron_iri"]: v for v in r.voorstellen}
        verwacht = c["verwacht"]
        geraakt = [iri for iri in verwacht if iri in gevonden]
        plaatsen = [gevonden[i]["definitie"]["vindplaats_soort"] == verwacht[i] for i in geraakt]
        rang = [ka.PLAATSEN.index(v["definitie"]["vindplaats_soort"]) for v in r.voorstellen]
        letterlijk = [v["definitie"]["definitie"] in _brontekst(graph, i) for i, v in gevonden.items()]
        uit.append({"case": c["id"], "naam": c["naam"], "recall": len(geraakt) / len(verwacht) if verwacht else 1.0,
                    "plaats_goed": sum(plaatsen), "plaats_van": len(plaatsen), "volgorde": rang == sorted(rang),
                    "letterlijk": all(letterlijk), "voorstellen": len(r.voorstellen), "melding": r.melding,
                    "gevonden": {i: v["definitie"]["vindplaats_soort"] for i, v in gevonden.items()}})
    n = len(uit)
    return {"cases": uit, "totaal": {
        "recall": sum(x["recall"] for x in uit) / n,
        "plaats": sum(x["plaats_goed"] for x in uit) / max(1, sum(x["plaats_van"] for x in uit)),
        "volgorde": sum(x["volgorde"] for x in uit) / n, "letterlijk": sum(x["letterlijk"] for x in uit) / n}}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--json", type=Path, help="schrijf het rapport ook als JSON")
    a = p.parse_args(argv)
    cases = json.loads(SET.read_text())["cases"]
    graph = _graaf()
    try:
        rapport = meet(graph, cases)
    finally:
        graph.close()
    for x in rapport["cases"]:
        print(f"{x['case']:<28} recall {x['recall']:.2f}  plaats {x['plaats_goed']}/{x['plaats_van']}  "
              f"volgorde {'ja' if x['volgorde'] else 'NEE'}  letterlijk {'ja' if x['letterlijk'] else 'NEE'}  "
              f"({x['voorstellen']} voorstellen) {x['melding']}")
    t = rapport["totaal"]
    print(f"\nrecall {t['recall']:.2f} · plaats {t['plaats']:.2f} · volgorde {t['volgorde']:.2f} · letterlijk {t['letterlijk']:.2f}")
    if a.json:
        a.json.write_text(json.dumps(rapport, ensure_ascii=False, indent=2) + "\n")
    return 0 if t["letterlijk"] == 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
