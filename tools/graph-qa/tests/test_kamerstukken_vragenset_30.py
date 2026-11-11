"""De vragenset van de Kamerstukken-iteratie (`tests/data/kamerstukken_vragenset_30.json`, ronde 1 op 11 nov 2026).

De set is de maat van elke ronde: dezelfde 30 vragen. Deze test houdt hem bruikbaar: elk id één keer, een bestaande tool,
en argumenten die die tool kent."""
from __future__ import annotations

import json
from pathlib import Path

from agent import tools

SET = json.loads((Path(__file__).parent / "data" / "kamerstukken_vragenset_30.json").read_text(encoding="utf-8"))


def test_dertig_vragen_met_een_eigen_id():
    ids = [v["id"] for v in SET["vragen"]]
    assert len(ids) == 30 and len(set(ids)) == 30 and ids == [f"K{i:02d}" for i in range(1, 31)]


def test_elke_vraag_noemt_een_tool_met_argumenten_die_hij_kent():
    schemas = {t["name"]: t["input_schema"] for t in tools.TOOLS}
    for v in SET["vragen"]:
        assert v["vraag"].strip() and v["goed"].strip(), v["id"]
        if not v.get("tool"):
            continue
        assert v["tool"] in schemas, v["id"]
        assert set(v.get("args") or {}) <= set(schemas[v["tool"]]["properties"]), v["id"]
