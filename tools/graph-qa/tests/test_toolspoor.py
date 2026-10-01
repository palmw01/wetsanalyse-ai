"""Het toolspoor van een beurt: één regel per aanroep, en een aantal alleen waar er iets te tellen is."""
from __future__ import annotations

import json
from types import SimpleNamespace

from agent.beurt import BeurtSchrijver
from agent.tool_execution import execute_tool


def _event(call_id: str, phase: str, **extra):
    return {"type": "tool_execution", "run_id": "r1", "call_id": call_id, "tool": "get_bronnode",
            "actie": "bron_lezen", "phase": phase, **extra}


def test_start_en_einde_van_een_aanroep_worden_een_bewaarde_regel():
    """Start en einde van één aanroep tellen als één regel, niet als "10 aanroepen" voor vijf."""
    w = BeurtSchrijver()
    for i in range(5):
        w.verwerk(_event(f"c{i}", "start", status="running"))
        w.verwerk(_event(f"c{i}", "end", status="ok", duur_ms=10 * i))
    assert len(w.tool_executions) == 5
    assert all(e["phase"] == "end" and e["status"] == "ok" for e in w.tool_executions)
    assert w.tool_executions[3]["duur_ms"] == 30
    assert "type" not in w.tool_executions[0]


def test_een_laat_startevent_draait_een_afgeronde_aanroep_niet_terug():
    w = BeurtSchrijver()
    w.verwerk(_event("c1", "end", status="ok"))
    w.verwerk(_event("c1", "start", status="running"))
    assert [(e["phase"], e["status"]) for e in w.tool_executions] == [("end", "ok")]


def test_events_zonder_call_id_blijven_los():
    w = BeurtSchrijver()
    w.verwerk({"type": "tool_execution", "tool": "x", "phase": "start"})
    w.verwerk({"type": "tool_execution", "tool": "x", "phase": "end"})
    assert len(w.tool_executions) == 2


def _voer_uit(name: str, antwoord: dict) -> list[dict]:
    events: list[dict] = []
    execute_tool(SimpleNamespace(), {"run_id": "r1"}, events.append, {"name": name, "id": "c1", "input": {}},
                 operation=lambda: json.dumps(antwoord))
    return events


def test_dekking_heeft_geen_aantal():
    """De dekking is geen lijst; `len([])` gaf altijd "0 resultaten"."""
    eind = _voer_uit("get_annotatiedekking", {"status": "ok", "bereik": ["urn:x"], "voltooid": True})[-1]
    assert eind["phase"] == "end" and eind["aantal"] is None


def test_zoekresultaten_hebben_wel_een_aantal():
    eind = _voer_uit("search_annotaties", {"status": "ok", "resultaten": [{"id": 1}, {"id": 2}]})[-1]
    assert eind["aantal"] == 2
