"""De routeringsset (ADR-010, Q2): wat de code zonder model routeert, en wat naar de centrale agent gaat.

Gratis: de ingang draait met een model dat faalt zodra het wordt aangeroepen; sinds ADR-016 §A7 vraagt de ingang nooit
een model. Een rij met `model: false` komt zonder aanroep op zijn route uit; een rij met `model: true` gaat naar de
centrale agent (de route `agent`, profiel `centraal`), die het model daarna vraagt: de code beslist het niet stil.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import overzicht
from agent.nodes import supervisie
from agent.nodes.context import Bouw
from fakes import FakeGraph, make_settings

pytestmark = pytest.mark.risico("R16", laag=2)

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


def _bouw(llm=None) -> Bouw:
    graaf = FakeGraph(results=lambda q: NAMEN if "bwb:Regeling" in q else "")
    return Bouw(settings=make_settings(), llm=llm or _GeenModel(), graph=graaf, stop_check=None, model="m", model_router="m",
                model_ophaal="m", memory_context=lambda _s: "", advies_context=lambda _s: "")


def _route(rij: dict) -> tuple[str, str]:
    ctx = rij.get("context") or {}
    state = {"question": rij["vraag"], "messages": [{"role": "user", "content": rij["vraag"]}], "modus": ctx.get("modus", "auto"),
             "werkgebied_id": ctx.get("werkgebied_id", ""), "actie": ctx.get("actie", ""), "context": ctx.get("context") or {},
             "opgegeven_doel": ctx.get("doel") or {}, "focus": {}, "bronstand": ctx.get("bronstand") or {}}
    b = _bouw()
    upd = supervisie.ingang_node(b, state)
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
        assert _route(rij) == ("agent", "centraal")
        return
    route, specialist = _route(rij)
    assert route == verwacht["route"]
    if "specialist" in verwacht:
        assert specialist == verwacht["specialist"]


_INTERN = ("Supervisor", "Specialist", "worker", "-agent", "taak ")


def test_de_statusregels_van_de_routering_zijn_in_gebruikerstaal_en_dragen_hun_route(monkeypatch):
    """G2b: de jurist ziet wat Lex doet, niet welke worker of agent het doet; de eval leest de route uit het veld."""
    events: list[dict] = []
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: events.append)
    for rij in RIJEN:
        if rij["verwacht"]["model"] or rij.get("bekend"):
            continue
        voor = len(events)
        _route(rij)
        nieuw = [e for e in events[voor:] if e.get("type") == "status"]
        assert any(e.get("route") for e in nieuw), f"{rij['id']}: geen statusregel met een route"
        for e in nieuw:
            assert not any(w in e["message"] for w in _INTERN), f"{rij['id']}: {e['message']}"


_AAN = {"kamerstukken": {"naam": "kamerstukken", "label": "Kamerstukken", "aan": True, "reden": "aan"}}


def test_een_genoemd_id_wordt_zonder_model_gelezen():
    state = {"question": "Wat staat er in kst-35496-F?", "modus": "auto", "focus": {}, "bronstand": _AAN,
             "messages": [{"role": "user", "content": "Wat staat er in kst-35496-F?"}]}
    b = _bouw()  # _GeenModel faalt als de ingang het model vraagt
    upd = supervisie.ingang_node(b, state)
    assert supervisie._entry_node(b, {**state, **upd}) == "bron_lezen"
    assert upd["bron_lezen"] == [{"name": "get_kamerstuk", "input": {"id": "kst-35496-F"}}]


def test_een_genoemd_id_van_een_uitgezette_bron_wordt_niet_gelezen():
    uit = {"kamerstukken": {**_AAN["kamerstukken"], "aan": False, "reden": "gesprek"}}
    state = {"question": "Wat staat er in kst-35496-F?", "modus": "auto", "focus": {}, "bronstand": uit,
             "messages": [{"role": "user", "content": "Wat staat er in kst-35496-F?"}]}
    b = _bouw()
    upd = supervisie.ingang_node(b, state)
    assert supervisie._entry_node(b, {**state, **upd}) == "afwijzen" and not upd.get("bron_lezen")


_LIVE = {"wetgeving_live": {"naam": "wetgeving_live", "label": "Wetgeving buiten de kennisgraaf", "aan": True,
                            "reden": "aan"}}


@pytest.fixture
def _wetgeving_live(monkeypatch):
    """De connector Wetgeving buiten de kennisgraaf tegen de opnames van overheid.nl (`test_wetgeving_tools.py`), met een
    graaf waarin alleen de Iw 1990 staat."""
    from agent import buiten_graaf
    from agent.tools import wetgeving_tools as w
    from agent.tools.connectortools import MODULES
    from test_wetgeving_tools import VANDAAG, _bron, _graaf

    monkeypatch.setattr(MODULES["wetgeving_live"], "_bron", _bron())
    monkeypatch.setattr(buiten_graaf, "_graafnamen", lambda graph: {"invorderingswet 1990"})
    import dataclasses
    import datetime as dt

    class _Datum(dt.date):
        @classmethod
        def today(cls):
            return dt.date.fromisoformat(VANDAAG)
    monkeypatch.setattr(dt, "date", _Datum)
    w._graaf_stand.clear()
    yield dataclasses.replace(_bouw(), graph=_graaf())
    w._graaf_stand.clear()


def test_een_genoemd_artikel_buiten_de_graaf_wordt_zonder_model_gelezen(_wetgeving_live):
    # Een tekstvraag gaat de bepalingsworkflow in (`test_wetgeving_live_routes.py`); een andere vraag over het artikel leest
    # de code vooraf, waarna de duiding formuleert.
    vraag = "Wat regelt artikel 31 van de Participatiewet?"
    state = {"question": vraag, "modus": "auto", "focus": {}, "bronstand": _LIVE,
             "messages": [{"role": "user", "content": vraag}]}
    upd = supervisie.ingang_node(_wetgeving_live, state)
    assert supervisie._entry_node(_wetgeving_live, {**state, **upd}) == "bron_lezen"
    assert upd["bron_lezen"] == [{"name": "get_wettekst", "input": {"bwb_id": "BWBR0015703", "artikel": "31"}}]
    assert "REGELINGEN BUITEN DE KENNISGRAAF" in upd["plan"]


def test_een_dubbelzinnige_afkorting_wordt_een_vraag_terug_zonder_model(_wetgeving_live):
    vraag = "Wat staat er in artikel 1 Pw?"
    state = {"question": vraag, "modus": "auto", "focus": {}, "bronstand": _LIVE,
             "messages": [{"role": "user", "content": vraag}]}
    upd = supervisie.ingang_node(_wetgeving_live, state)
    assert upd["afwijzen"] and "Welke bedoel je?" in upd["afwijs_melding"] and "Participatiewet" in upd["afwijs_melding"]


def test_zonder_de_connector_geen_verzoek_naar_overheid(_wetgeving_live, monkeypatch):
    from agent.tools.connectortools import MODULES

    monkeypatch.setattr(MODULES["wetgeving_live"], "_bron", None)
    vraag = "Wat staat er in artikel 31 van de Participatiewet?"
    uit = {"wetgeving_live": {**_LIVE["wetgeving_live"], "aan": False, "reden": "straat"}}
    assert supervisie._buiten_graaf(_wetgeving_live, {"bronstand": uit}, vraag) == []
