r"""Wie een contractresultaat leest, leest zijn WAARDEN, niet zijn JSON-tekst.

In JSON staat een newline als `\n` en een aanhalingsteken als `\"`. Werkten grounding en bronnen op de
ruwe tekst, dan viel een letterlijk citaat over een regelgrens af en werd een vindplaats verminkt.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from agent.grounding import check_grounding
from agent.provenance import collect_sources
from agent.resultaat import BUDGET, resultaat, waarden
from agent import tool_execution

IW = "BWBR0004770"
TEKST = 'De ontvanger kan "uitstel" verlenen.\nDaarna geldt een termijn van zes weken voor de belastingschuldige.'


def _contract() -> str:
    return resultaat([{"node": f"urn:bwb:{IW}:artikel:25:lid:1", "jci": f"jci1.3:c:{IW}&artikel=25&lid=1",
                       "tekst": TEKST}])


def test_waarden_geeft_de_gedecodeerde_tekst():
    assert TEKST in waarden(_contract())
    assert "\\n" not in waarden(_contract())
    assert waarden("geen contract") == "geen contract"


def test_een_citaat_over_een_regelgrens_is_letterlijk():
    antwoord = f'Volgens {IW}: "verlenen. Daarna geldt een termijn van zes weken voor de belastingschuldige".'
    rapport = check_grounding(antwoord, [("get_lid", _contract())])
    assert rapport.niet_letterlijk == [], rapport
    assert rapport.niveau == "gegrond"


def test_bronnen_komen_uit_de_waarden():
    bronnen = collect_sources([("get_lid", _contract())])
    assert [(b.uri, b.jci) for b in bronnen] == [(f"urn:bwb:{IW}:artikel:25:lid:1", f"jci1.3:c:{IW}&artikel=25&lid=1")]


def test_een_te_groot_contractresultaat_bereikt_het_model_niet(monkeypatch):
    groot = resultaat([{"tekst": "x" * (BUDGET + 10)}])
    monkeypatch.setattr(tool_execution, "dispatch", lambda *a, **k: groot)
    events: list[dict] = []
    b = SimpleNamespace(graph=None, settings=SimpleNamespace(annotatie_read_user_id=""), annotaties=object())
    uit = tool_execution.execute_tool(b, {}, events.append, {"name": "search_wetgeving", "input": {"query": "x"}})
    data = json.loads(uit)
    assert data["status"] == "error" and data["reden"] == "resultaatcontract_overschreden"
    assert "x" * 100 not in uit
    einde = events[-1]
    assert einde["status"] == "error" and einde["foutcode"] == "tool_resultaat_te_groot"
    assert einde["omvang"] > BUDGET and einde["budget"] == BUDGET


def test_has_more_is_een_afleiding_van_volledig(monkeypatch):
    onvolledig = resultaat([{"node": f"urn:bwb:{IW}:artikel:1"}], volledig=False,
                           vervolg={"tool": "search_wetgeving", "args": {"query": "x", "offset": 1}})
    monkeypatch.setattr(tool_execution, "dispatch", lambda *a, **k: onvolledig)
    events: list[dict] = []
    b = SimpleNamespace(graph=None, settings=SimpleNamespace(annotatie_read_user_id=""), annotaties=object())
    tool_execution.execute_tool(b, {}, events.append, {"name": "search_wetgeving", "input": {"query": "x"}})
    assert events[-1]["has_more"] is True and events[-1]["aantal"] == 1
