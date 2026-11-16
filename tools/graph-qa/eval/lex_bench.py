"""Lex Bench, meetas bronselectie: de uitkomst op de (vroegere) blinde sets, naast wat de code nu geeft.

Plan: `docs/architectuur/plan-lex-bench.md` (§4.5, §20.4). Een blinde set wordt één keer gemeten; daarna is hij een
ontwikkelset. Zijn uitkomst hoort niet als pin in de unitsuite: wie de code afstemt, ziet de test dan rood worden, en
de set is niet meer blind voor het afstemmen. Daarom staat die uitkomst hier, in `docs/lex-bench/bronselectie/held-out.json`
(met de meting waar hij vandaan komt), en zegt dit script wat er nu anders is. **Het faalt niet op een verschil**: de score
is een hulpmiddel, geen poort (plan §1). De unitsuite houdt voor deze sets alleen het pad zonder model en de vorm
(`tests/evals/test_bronselectie_eval.py`).

Offline, tegen de opnames van de graaf: geen model, geen graaf, nul tokens.

    python -m eval.lex_bench               # het verschil per set en route, als tabel
    python -m eval.lex_bench --json uit.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from eval.bronselectie_eval import ROUTES, SETS, OpnameGraaf, laad_set, meet_intake

HELD_OUT = Path(__file__).resolve().parents[3] / "docs" / "lex-bench" / "bronselectie" / "held-out.json"
#: De maten die de uitkomst draagt; een route die een maat niet heeft, laat haar weg.
MATEN = ("recall", "recall_nodig", "recall_exact", "precisie", "recall_pool", "uitgesloten")


def laad() -> dict[str, Any]:
    return json.loads(HELD_OUT.read_text(encoding="utf-8"))


def meet_set(naam: str, routes: list[str]) -> tuple[dict[str, dict[str, Any]], int]:
    """De maten per route op één set, offline. Geeft ook het aantal query's dat de opname niet kende."""
    graaf = OpnameGraaf(json.loads((SETS / naam / "graafantwoorden.json").read_text(encoding="utf-8")))
    gekozen = {r: ROUTES[r] for r in routes if r in ROUTES}
    r = meet_intake(graaf, laad_set(naam), gekozen or None)
    uit = {}
    for route in routes:
        if route in r:
            uit[route] = {m: round(r[route][m], 3) if isinstance(r[route][m], float) else r[route][m]
                          for m in MATEN if m in r[route]}
    return uit, graaf.ontbrekend


def vergelijk(register: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Per set, route en maat: de uitkomst bij de blinde meting, nu, en of ze gelijk zijn."""
    register = register or laad()
    rijen = []
    for s in register["sets"]:
        nu, ontbrekend = meet_set(s["set"], list(s["uitkomst"]))
        for route, maten in s["uitkomst"].items():
            for maat, toen in maten.items():
                waarde = (nu.get(route) or {}).get(maat)
                rijen.append({"set": s["set"], "route": route, "maat": maat, "toen": toen, "nu": waarde,
                              "gelijk": waarde == toen, "opname_onvolledig": ontbrekend > 0, "meting": s["meting"]})
    return rijen


def _tabel(rijen: list[dict[str, Any]]) -> str:
    regels = ["| set | route | maat | bij de blinde meting | nu | |", "|---|---|---|---|---|---|"]
    for r in rijen:
        teken = "" if r["gelijk"] else "anders"
        regels.append(f"| {r['set']} | {r['route']} | {r['maat']} | {r['toen']} | {r['nu']} | {teken} |")
    anders = sum(not r["gelijk"] for r in rijen)
    regels.append(f"\n{len(rijen)} maten, {anders} anders dan bij de blinde meting. Een verschil is geen fout: het zegt wat "
                  "de code sindsdien veranderde op een set die nu ontwikkelset is.")
    return "\n".join(regels)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--json", type=Path, help="het verschil ook als JSON")
    args = p.parse_args(argv)
    rijen = vergelijk()
    print(_tabel(rijen))
    if args.json:
        args.json.write_text(json.dumps(rijen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
