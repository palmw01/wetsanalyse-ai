"""`beurt_meting`: elke afloop levert één regel, zonder inhoud."""
from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace

import pytest

from agent.beurtmeting import gemeten, route_van
from agent.models import Verbruiksmeter
from agent.observability import JsonFormatter


def _meter() -> Verbruiksmeter:
    meter = Verbruiksmeter()
    meter.route = "definitie"
    meter.tel_response(SimpleNamespace(usage=SimpleNamespace(
        input_tokens=10, output_tokens=5, cache_read_input_tokens=7, cache_creation_input_tokens=3)))
    return meter


async def _stroom(*events, fout=None):
    for event in events:
        yield event
    if fout:
        raise fout


def _draai(stroom, *, run=None, meter=None, lees=None):
    run = run or SimpleNamespace(run_id="r1", stop_gevraagd=False)

    async def lus():
        gezien = []
        beurt = gemeten(stroom, meter=meter or _meter(), run=run, gesprek_id="g1", model="m")
        async for event in beurt:
            gezien.append(event)
            if lees is not None and len(gezien) == lees:
                await beurt.aclose()
                break
        return gezien

    return asyncio.run(lus())


def _regels(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.getMessage() == "beurt_meting"]


@pytest.fixture(autouse=True)
def _log(caplog):
    caplog.set_level(logging.INFO, logger="graph_qa.beurt")


def test_een_geslaagde_beurt_geeft_een_regel_met_alle_velden(caplog):
    events = [
        {"type": "status", "message": "bezig"},
        {"type": "tool_execution", "phase": "start", "call_id": "1"},
        {"type": "tool_execution", "phase": "einde", "call_id": "1"},
        {"type": "reason", "content": "Ik zoek"},
        {"type": "token", "content": "Antwoord"},
        {"type": "done"},
    ]
    uit = _draai(_stroom(*events))
    assert [e for e in uit if e["type"] != "meting"] == events
    assert [e["type"] for e in uit][-2:] == ["meting", "done"]

    [regel] = _regels(caplog)
    assert regel.uitkomst == "klaar" and regel.route == "definitie"
    assert regel.toolaanroepen == 1 and regel.modelrondes == 1
    assert (regel.invoer, regel.uitvoer, regel.cache_lees, regel.cache_schrijf) == (10, 5, 7, 3)
    assert regel.eerste_tekst_ms is not None and regel.duur_ms >= regel.eerste_tekst_ms
    assert regel.chat_session_id == "g1" and regel.run_id == "r1" and regel.model == "m"


def test_een_beurt_zonder_tekst_heeft_geen_eerste_tekst(caplog):
    _draai(_stroom({"type": "token", "content": ""}, {"type": "done"}))
    assert _regels(caplog)[0].eerste_tekst_ms is None


@pytest.mark.parametrize("events,uitkomst", [
    ([{"type": "error", "message": "x"}, {"type": "done"}], "fout"),
    ([{"type": "token", "content": "a"}], "afgebroken"),
])
def test_de_uitkomst_volgt_de_afloop(caplog, events, uitkomst):
    _draai(_stroom(*events))
    assert [r.uitkomst for r in _regels(caplog)] == [uitkomst]


def test_stoppen_is_geen_fout(caplog):
    _draai(_stroom({"type": "done"}), run=SimpleNamespace(run_id="r", stop_gevraagd=True))
    assert _regels(caplog)[0].uitkomst == "gestopt"


def test_een_exceptie_logt_en_gaat_door(caplog):
    with pytest.raises(RuntimeError):
        _draai(_stroom({"type": "token", "content": "a"}, fout=RuntimeError("kapot")))
    assert [r.uitkomst for r in _regels(caplog)] == ["fout"]


def test_een_lezer_die_weggaat_laat_ook_een_regel_achter(caplog):
    _draai(_stroom({"type": "token", "content": "a"}, {"type": "token", "content": "b"}), lees=1)
    assert [r.uitkomst for r in _regels(caplog)] == ["afgebroken"]


def test_de_regel_draagt_geen_inhoud(caplog):
    geheim = "de vraag van de jurist"
    _draai(_stroom({"type": "token", "content": geheim}, {"type": "done"}))
    assert geheim not in JsonFormatter().format(_regels(caplog)[0])


def test_de_tellers_overleven_de_redactie(caplog):
    _draai(_stroom({"type": "done"}))
    regel = json.loads(JsonFormatter().format(_regels(caplog)[0]))
    assert regel["bericht"] == "beurt_meting" and regel["invoer"] == 10 and regel["cache_lees"] == 7


def test_de_meting_gaat_als_event_mee_met_dezelfde_cijfers_als_de_regel(caplog):
    """Zonder App Insights is een beurt alleen zo te meten: wat hij kostte, per aanroep, en hoeveel uit de cache."""
    meter = _meter()
    meter.tel_response(SimpleNamespace(usage=SimpleNamespace(
        input_tokens=1, output_tokens=2, cache_read_input_tokens=3, cache_creation_input_tokens=0)), ms=1200)
    uit = _draai(_stroom({"type": "tool_execution", "phase": "start"}, {"type": "done"}), meter=meter)
    [meting] = [e for e in uit if e["type"] == "meting"]
    [regel] = _regels(caplog)
    for veld in ("route", "uitkomst", "duur_ms", "toolaanroepen", "modelrondes", "invoer", "uitvoer", "cache_lees",
                 "cache_schrijf", "model"):
        assert meting[veld] == getattr(regel, veld), veld
    assert meting["modelrondes"] == 2 and meting["toolaanroepen"] == 1
    assert meting["aanroepen"] == [{"invoer": 10, "uitvoer": 5, "cache_lees": 7, "cache_schrijf": 3},
                                   {"invoer": 1, "uitvoer": 2, "cache_lees": 3, "cache_schrijf": 0, "ms": 1200}]


def test_zonder_done_geen_meting_maar_wel_een_regel(caplog):
    uit = _draai(_stroom({"type": "token", "content": "a"}))
    assert not [e for e in uit if e["type"] == "meting"] and len(_regels(caplog)) == 1


def test_de_meting_draagt_geen_inhoud():
    geheim = "de vraag van de jurist"
    [meting] = [e for e in _draai(_stroom({"type": "token", "content": geheim}, {"type": "done"})) if e["type"] == "meting"]
    assert geheim not in json.dumps(meting)


def test_de_aanroepen_zijn_begrensd_de_tellers_niet():
    from agent.models import MAX_AANROEPEN
    meter = Verbruiksmeter()
    for _ in range(MAX_AANROEPEN + 5):
        meter.tel_response(SimpleNamespace(usage=SimpleNamespace(input_tokens=1, output_tokens=0)))
    assert len(meter.aanroepen) == MAX_AANROEPEN and meter.calls == MAX_AANROEPEN + 5 and meter.invoer == MAX_AANROEPEN + 5


@pytest.mark.parametrize("state,route", [
    ({"agent_taak": {"agent": "deelvragen", "taak": "opstellen"}, "specialist": "agent_taak"}, "deelvragen:opstellen"),
    ({"specialist": "algemeen", "overzicht_route": True}, "overzicht"),
    ({"specialist": "annotatie"}, "annotatie"),
    ({}, ""),
])
def test_route_van(state, route):
    assert route_van(state) == route


def test_doorvragen_en_afwijzen_hebben_een_route():
    assert route_van({"afwijzen": True, "afwijs_stap": "vraagt eerst welk artikel je bedoelt"}) == "verduidelijken"
    assert route_van({"afwijzen": True}) == "afgewezen"
