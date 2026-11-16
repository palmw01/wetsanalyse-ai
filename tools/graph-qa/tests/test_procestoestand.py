"""De procesbrede toestand lekt niet tussen tests (Lex Bench §14.1, testplan graph-qa §4.2).

Een module die op moduleniveau een cache of stand bewaart en die in een functie wijzigt, meldt zich bij
`agent.procestoestand` met een functie die hem leegmaakt; `conftest.py` roept die voor en na elke test aan. Deze test
zoekt zulke toestand in `agent/` en eist de melding, zodat een nieuwe cache niet stil van test naar test lekt.
"""
from __future__ import annotations

import pytest

import ast
import importlib
from pathlib import Path

from agent import procestoestand

pytestmark = pytest.mark.risico("R21", laag=2)

AGENT = Path(__file__).resolve().parents[1] / "agent"
MUTEREND = {"append", "add", "update", "clear", "setdefault", "pop", "extend", "popitem", "discard", "remove",
            "insert", "move_to_end"}
CONTAINERS = {"set", "dict", "list", "OrderedDict", "defaultdict", "deque"}
#: Toestand die tussen tests hoort te blijven, met de reden.
UITGEZONDERD = {"agent.procestoestand": "het register zelf: de meldingen gebeuren bij het importeren"}


def _module(pad: Path) -> str:
    delen = pad.relative_to(AGENT.parent).with_suffix("").parts
    return ".".join(delen[:-1] if delen[-1] == "__init__" else delen)


def _gewijzigde_toestand(boom: ast.Module) -> set[str]:
    """Namen op moduleniveau met een veranderlijke waarde (of `None`) die een functie wijzigt."""
    kandidaten: set[str] = set()
    for knoop in boom.body:
        if isinstance(knoop, (ast.Assign, ast.AnnAssign)) and knoop.value is not None:
            v = knoop.value
            veranderlijk = (isinstance(v, (ast.Dict, ast.List, ast.Set))
                            or (isinstance(v, ast.Call) and getattr(v.func, "id", None) in CONTAINERS)
                            or (isinstance(v, ast.Constant) and v.value is None))
            doelen = knoop.targets if isinstance(knoop, ast.Assign) else [knoop.target]
            kandidaten |= {d.id for d in doelen if isinstance(d, ast.Name) and veranderlijk}
    gewijzigd: set[str] = set()
    for f in ast.walk(boom):
        if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for x in ast.walk(f):
            if isinstance(x, ast.Global):
                gewijzigd |= set(x.names) & kandidaten
            elif (isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and isinstance(x.func.value, ast.Name)
                  and x.func.value.id in kandidaten and x.func.attr in MUTEREND):
                gewijzigd.add(x.func.value.id)
            elif isinstance(x, (ast.Assign, ast.AugAssign)):
                for d in x.targets if isinstance(x, ast.Assign) else [x.target]:
                    if isinstance(d, ast.Subscript) and isinstance(d.value, ast.Name) and d.value.id in kandidaten:
                        gewijzigd.add(d.value.id)
    return gewijzigd


def _met_toestand() -> dict[str, set[str]]:
    uit = {}
    for pad in sorted(AGENT.rglob("*.py")):
        if namen := _gewijzigde_toestand(ast.parse(pad.read_text(encoding="utf-8"))):
            uit[_module(pad)] = namen
    return uit


def test_elke_module_met_procesbrede_toestand_meldt_zich():
    gevonden = _met_toestand()
    assert gevonden, "de zoektocht vindt niets meer: dan toetst deze test niets"
    for module in gevonden:
        importlib.import_module(module)
    zonder = {m: sorted(n) for m, n in gevonden.items() if m not in procestoestand.gemeld() and m not in UITGEZONDERD}
    assert not zonder, ("procesbrede toestand zonder melding bij agent.procestoestand; voeg een functie toe die hem "
                        f"leegmaakt en registreer die: {zonder}")


def test_de_zoektocht_herkent_de_vormen():
    """Een positieve controle: de vormen die lekken, ziet de zoektocht; een constante en een cache in een functie niet."""
    bron = ("A: dict = {}\nB = []\nC = None\nD = set()\nE = 5\nF = {}\n"
            "def f():\n    global C\n    C = 1\n    A['x'] = 1\n    B.append(1)\n    D.add(1)\n    g = {}\n    g['y'] = 2\n")
    assert _gewijzigde_toestand(ast.parse(bron)) == {"A", "B", "C", "D"}


def test_reset_maakt_de_regelingen_leeg():
    from agent import overzicht
    overzicht._REGELINGEN_CACHE.append({"bwb_id": "BWBR0004770"})
    procestoestand.reset()
    assert overzicht._REGELINGEN_CACHE == []
