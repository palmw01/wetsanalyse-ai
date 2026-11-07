"""De routeringsset (ADR-010, Q2): wat de code zonder model routeert, en waar het model kiest.

Gratis: de supervisor draait met een model dat faalt zodra het wordt aangeroepen. Een rij met `model: false` moet zonder
aanroep op zijn route uitkomen; een rij met `model: true` moet het model wél vragen (dan beslist de code het niet stil).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import overzicht
from agent.nodes import supervisie
from agent.nodes.context import Bouw
from fakes import FakeGraph, make_settings

SET = Path(__file__).resolve().parents[1] / "eval" / "golden_routering.jsonl"
RIJEN = [json.loads(r) for r in SET.read_text(encoding="utf-8").splitlines() if r.strip() and not r.startswith("#")]
NAMEN = ("?regeling\t?citeertitel\t?soort\t?afkortingen\n"
         "<urn:bwb:BWBR0004770>\t\"Invorderingswet 1990\"\t\"wet\"\t\"IW | Iw 1990\"\n")


class ModelGevraagd(Exception):
    pass


class _GeenModel:
    def create(self, **_):
        raise ModelGevraagd

    def stream(self, **_):
        raise ModelGevraagd


def _bouw() -> Bouw:
    graaf = FakeGraph(results=lambda q: NAMEN if "bwb:Regeling" in q else "")
    return Bouw(settings=make_settings(), llm=_GeenModel(), graph=graaf, stop_check=None, model="m", model_router="m",
                model_ophaal="m", memory_context=lambda _s: "", advies_context=lambda _s: "")


def _route(rij: dict) -> tuple[str, str]:
    ctx = rij.get("context") or {}
    state = {"question": rij["vraag"], "messages": [{"role": "user", "content": rij["vraag"]}], "modus": ctx.get("modus", "auto"),
             "werkgebied_id": ctx.get("werkgebied_id", ""), "actie": ctx.get("actie", ""), "context": ctx.get("context") or {},
             "opgegeven_doel": ctx.get("doel") or {}, "focus": {}}
    b = _bouw()
    upd = supervisie.supervisor_node(b, state)
    return supervisie._entry_node(b, {**state, **upd}), upd.get("specialist", "")


@pytest.fixture(autouse=True)
def _stil(monkeypatch):
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: (lambda _e: None))
    overzicht._REGELINGEN_CACHE.clear()
    yield
    overzicht._REGELINGEN_CACHE.clear()


def test_elke_rij_heeft_een_id_en_een_verwachting():
    assert len({r["id"] for r in RIJEN}) == len(RIJEN)
    assert all("model" in r["verwacht"] and ("route" in r["verwacht"] or r["verwacht"]["model"]) for r in RIJEN)


@pytest.mark.parametrize("rij", RIJEN, ids=[r["id"] for r in RIJEN])
def test_routering(rij, request):
    if rij.get("bekend"):
        request.applymarker(pytest.mark.xfail(strict=True, reason=rij["bekend"]))
    verwacht = rij["verwacht"]
    if verwacht["model"]:
        with pytest.raises(ModelGevraagd):
            _route(rij)
        return
    route, specialist = _route(rij)
    assert route == verwacht["route"]
    if "specialist" in verwacht:
        assert specialist == verwacht["specialist"]
