"""De traceerbaarheidsmatrix van Lex Bench: van risico, naar testgeval, naar laag (plan-lex-bench.md §21).

De bron is de code zelf. Een test noemt het risico dat hij dekt:

- in pytest met `@pytest.mark.risico("R07")` op de test of als `pytestmark` in de module; een andere laag dan die van de
  plek geef je mee: `pytest.mark.risico("R20", laag=3)`;
- in vitest met `[R07]` in de naam van een `describe`, `it` of `test`;
- in een browserscript, een workflow of een E2E-scenario met een regel `risico: R07, R08` (in commentaar).

De laag volgt uit de plek (`LAGEN`): een test in een component is laag 1, `tests/poort/` laag 2, een workflow laag 3,
`docs/acceptatie/` laag 4, `docs/lex-bench/` laag 5. Het register staat in `docs/lex-bench/risicos.json`.

Voorlopig alleen zichtbaar, nog niet bindend (besluit 15): het script en `tests/poort/test_risicomatrix.py` falen op een
onbekend risico of een kapotte marker, niet op een risico zonder test. Die staan in de uitvoer als *niet gedekt*.

    python scripts/risicomatrix.py               # de matrix als tabel
    python scripts/risicomatrix.py --json uit.json

Alleen de standaardbibliotheek, zoals de poorttests.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

WORTEL = Path(__file__).resolve().parents[1]
REGISTER = WORTEL / "docs" / "lex-bench" / "risicos.json"

#: Waar tests staan, met de laag die daar standaard geldt.
PYTEST = [("tools/graph-qa/tests", 1), ("api/tests", 1), ("tools/bwb-import/tests", 1), ("tests/poort", 2)]
VITEST = [("frontend", 1)]
REGELS = [("frontend/scripts", 1, "test-*.mjs"), (".github/workflows", 3, "*.yml"), ("docs/acceptatie", 4, "*.md"),
          ("docs/lex-bench", 5, "*.json")]

ID = re.compile(r"\bR\d{2}\b")
VITEST_NAAM = re.compile(r"""\b(?:describe|it|test)(?:\.\w+)?\(\s*(["'`])((?:(?!\1).)*\[R\d{2}\](?:(?!\1).)*)\1""")
REGEL = re.compile(r"(?mi)^\W*risico:\s*([R\d ,]+)$")


def register() -> dict:
    return json.loads(REGISTER.read_text(encoding="utf-8"))


def _risico_markers(knoop: ast.AST) -> list[tuple[str, int | None]]:
    """De `pytest.mark.risico(...)`-aanroepen in een decorator of `pytestmark`, als (id, laag)."""
    uit = []
    for x in ast.walk(knoop):
        if (isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr == "risico"
                and isinstance(x.func.value, ast.Attribute) and x.func.value.attr == "mark"):
            laag = next((k.value.value for k in x.keywords if k.arg == "laag" and isinstance(k.value, ast.Constant)), None)
            uit += [(a.value, laag) for a in x.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
    return uit


def _pytest(map_: Path, standaard: int) -> list[dict]:
    uit = []
    for pad in sorted(map_.rglob("test_*.py")):
        boom = ast.parse(pad.read_text(encoding="utf-8"))
        module = [m for k in boom.body if isinstance(k, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in k.targets) for m in _risico_markers(k)]
        for k in ast.walk(boom):
            if isinstance(k, (ast.FunctionDef, ast.AsyncFunctionDef)) and k.name.startswith("test_"):
                eigen = [m for d in k.decorator_list for m in _risico_markers(d)]
                for rid, laag in module + eigen:
                    uit.append({"risico": rid, "laag": laag or standaard, "test": f"{pad.relative_to(WORTEL)}::{k.name}"})
    return uit


def _vitest(map_: Path, standaard: int) -> list[dict]:
    uit = []
    for pad in sorted(map_.rglob("*.test.ts*")):
        if "node_modules" in pad.parts:
            continue
        for _, naam in VITEST_NAAM.findall(pad.read_text(encoding="utf-8")):
            for rid in ID.findall(naam):
                uit.append({"risico": rid, "laag": standaard, "test": f"{pad.relative_to(WORTEL)} › {naam}"})
    return uit


def _regels(map_: Path, standaard: int, patroon: str) -> list[dict]:
    uit = []
    for pad in sorted(map_.glob(patroon)):
        if pad.name == REGISTER.name:
            continue
        for groep in REGEL.findall(pad.read_text(encoding="utf-8")):
            uit += [{"risico": rid, "laag": standaard, "test": str(pad.relative_to(WORTEL))} for rid in ID.findall(groep)]
    return uit


def verzamel() -> list[dict]:
    uit = []
    for map_, laag in PYTEST:
        uit += _pytest(WORTEL / map_, laag)
    for map_, laag in VITEST:
        uit += _vitest(WORTEL / map_, laag)
    for map_, laag, patroon in REGELS:
        uit += _regels(WORTEL / map_, laag, patroon)
    return uit


def matrix(markers: list[dict] | None = None, reg: dict | None = None) -> dict:
    """Per risico: de tests per laag, en of de primaire laag een test heeft."""
    reg = reg or register()
    markers = verzamel() if markers is None else markers
    rijen = {}
    for r in reg["risicos"]:
        per_laag: dict[str, list[str]] = {}
        for m in markers:
            if m["risico"] == r["id"]:
                per_laag.setdefault(str(m["laag"]), []).append(m["test"])
        rijen[r["id"]] = {"risico": r["risico"], "impact": r["impact"], "primair": r["primair"], "tweede": r["tweede"],
                          "per_laag": {k: sorted(set(v)) for k, v in sorted(per_laag.items())},
                          "primair_gedekt": str(r["primair"]) in per_laag}
    onbekend = sorted({m["risico"] for m in markers} - set(rijen))
    return {"risicos": rijen, "onbekend": onbekend,
            "niet_gedekt_hoog": [k for k, v in rijen.items() if v["impact"] == "hoog" and not v["primair_gedekt"]]}


def _tabel(m: dict) -> str:
    regels = ["| risico | impact | primair | 1 | 2 | 3 | 4 | 5 |", "|---|---|---|---|---|---|---|---|"]
    for rid, r in m["risicos"].items():
        cellen = [str(len(r["per_laag"].get(str(l), []))) or "" for l in range(1, 6)]
        cellen = ["·" if c == "0" else c for c in cellen]
        regels.append(f"| {rid} {r['risico'][:50]} | {r['impact']} | {r['primair']}{'' if r['primair_gedekt'] else ' (niet gedekt)'} | "
                      + " | ".join(cellen) + " |")
    gedekt = sum(r["primair_gedekt"] for r in m["risicos"].values())
    regels.append(f"\n{gedekt} van {len(m['risicos'])} risico's hebben een test op hun primaire laag. Niet gedekt met impact "
                  f"hoog: {', '.join(m['niet_gedekt_hoog']) or 'geen'}. Alleen zichtbaar, nog niet bindend (besluit 15).")
    if m["onbekend"]:
        regels.append(f"Onbekende risico's in een marker: {', '.join(m['onbekend'])}")
    return "\n".join(regels)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--json", type=Path)
    args = p.parse_args(argv)
    m = matrix()
    print(_tabel(m))
    if args.json:
        args.json.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if m["onbekend"] else 0


if __name__ == "__main__":
    sys.exit(main())
