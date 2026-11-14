"""De routeringsset van de centrale agent (`eval/golden_routering_centraal.jsonl`): elke overdracht gaat door de code
naar de node die de set noemt, zonder model. Wat het model kiest, meet de agentset; hier staat dat de route er is
(analyse centrale agent, gat 4: "annoteer artikel 9 lid 1" had bij de centrale agent geen tool)."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent import overdracht
from agent.overdracht import CENTRAAL, INGANG, OVERDRACHT
from tests.fakes import FakeGraph, make_settings

EVAL = Path(__file__).resolve().parents[1] / "eval"
RIJEN = [json.loads(r) for r in (EVAL / "golden_routering_centraal.jsonl").read_text(encoding="utf-8").splitlines()
         if r.strip() and not r.startswith("#")]
MODEL = {json.loads(r)["id"] for r in (EVAL / "golden_routering.jsonl").read_text(encoding="utf-8").splitlines()
         if r.strip() and not r.startswith("#") and json.loads(r)["verwacht"].get("model")}


def test_de_set_dekt_elke_rij_waar_het_model_kiest():
    assert MODEL <= {r["id"] for r in RIJEN}
    assert len({r["id"] for r in RIJEN}) == len(RIJEN)


@pytest.mark.parametrize("rij", RIJEN, ids=[r["id"] for r in RIJEN])
def test_de_overdracht_komt_uit_bij_de_route(rij, monkeypatch):
    c = rij["centraal"]
    if c["tool"] is None:
        assert c["naar"] == "agent"
        return
    werkgebied = bool((rij.get("context") or {}).get("werkgebied_id"))
    assert c["tool"] in overdracht.voor(CENTRAAL, werkgebied=werkgebied), "de agent heeft de tool"
    monkeypatch.setattr(overdracht, "get_stream_writer", lambda: (lambda _e: None))
    import agent.nodes.supervisie as supervisie
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: (lambda _e: None), raising=False)
    state = {"question": rij["vraag"], "specialist": CENTRAAL, "messages": [], "run_id": "r",
             **(rij.get("context") or {})}
    b = SimpleNamespace(settings=make_settings(), graph=FakeGraph(result=""), kinderen=None, stop_check=None)
    tu = {"id": "t1", "name": c["tool"], "input": c["invoer"]}
    upd = overdracht.overdracht_node(b, {**state, "pending_tools": [tu]})
    assert not upd["messages"][0]["content"][0].get("is_error"), upd["messages"][0]["content"][0]["content"]
    naar = overdracht.route_na_overdracht(b, upd)
    assert naar == c["naar"]
    if "specialist" in c:
        assert upd["specialist"] == c["specialist"] and upd["zelfstandige_vraag"] == c["invoer"]["vraag"]
    if c["naar"] == "afwijzen":
        assert "artikel" in upd["afwijs_melding"].lower()
    if OVERDRACHT[c["tool"]].naar == INGANG:
        assert naar in (*OVERDRACHT[c["tool"]].ingangen, "agent")


def test_de_annotatie_agent_is_een_taakagent():
    assert "annotatie" in overdracht.TAAKAGENTS
    taken = OVERDRACHT["taakagent"].invoer["taak"]["enum"]
    assert {"werkgebied", "deelvragen"} <= set(taken)
