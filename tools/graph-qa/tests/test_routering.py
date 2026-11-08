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


class _Supervisor:
    """Een model dat de supervisorregels teruggeeft, zoals op acceptatie: in een gesprek een herschreven vraag."""

    def __init__(self, tekst: str):
        self.tekst = tekst

    def create(self, **_):
        from fakes import response, text_block
        return response([text_block(self.tekst)], "end_turn")


def test_in_een_bestaand_werkgebied_start_een_vervolgvraag_geen_nieuw_werkgebied(monkeypatch):
    """Acceptatie 7 nov 2026: "Welke bronnen horen daarbij?" gaf "Hoe noemen we het werkgebied?"."""
    b = _bouw(_Supervisor("VRAAG: Welke bronnen horen bij de deelvraag die het minst is uitgewerkt?\nWORKERS: werkgebied\n"
                        "SPECIALIST: algemeen\nPLAN: bronnen per deelvraag"))
    state = {"question": "Welke bronnen horen daarbij?", "modus": "auto", "werkgebied_id": "w1", "focus": {},
             "messages": [{"role": "user", "content": "Welke deelvraag is het minst uitgewerkt?"},
                          {"role": "assistant", "content": "Deelvraag 3."},
                          {"role": "user", "content": "Welke bronnen horen daarbij?"}]}
    upd = supervisie.supervisor_node(b, state)
    assert supervisie._entry_node(b, {**state, **upd}) == "agent_taak"
    assert upd["agent_taak"]["agent"] == "deelvragen" and upd["agent_taak"]["taak"] == "dekking"


def test_buiten_een_werkgebied_stelt_de_werkgebied_worker_nog_steeds_samen():
    b = _bouw(_Supervisor("WORKERS: werkgebied\nSPECIALIST: algemeen\nPLAN: samenstellen"))
    state = {"question": "Ik wil de invordering van belastingen onderzoeken", "modus": "auto", "werkgebied_id": "",
             "focus": {}, "messages": [{"role": "user", "content": "Ik wil de invordering van belastingen onderzoeken"}]}
    upd = supervisie.supervisor_node(b, state)
    assert supervisie._entry_node(b, {**state, **upd}) == "werkgebied_intake"


def test_een_vervolgvraag_zonder_regeling_gaat_na_het_herschrijven_de_workflow_in():
    """"Wat staat er in artikel 9?" na Iw 9 lid 1: het model herschrijft met de regeling, de code kiest de workflow."""
    b = _bouw(_Supervisor("VRAAG: Wat staat er in artikel 9 van de Invorderingswet 1990?\nWORKERS: antwoord\n"
                          "SPECIALIST: duiding\nPLAN: de tekst"))
    state = {"question": "Wat staat er in artikel 9?", "modus": "auto", "werkgebied_id": "", "focus": {},
             "messages": [{"role": "user", "content": "Wat staat er in artikel 9 lid 1 van de Invorderingswet 1990?"},
                          {"role": "assistant", "content": "Een belastingaanslag is invorderbaar zes weken na …"},
                          {"role": "user", "content": "Wat staat er in artikel 9?"}]}
    upd = supervisie.supervisor_node(b, state)
    assert supervisie._entry_node(b, {**state, **upd}) == "bepaling_lezen"
    assert upd["bepalingsvraag"] == {"bwb_id": "BWBR0004770", "artikel": "9", "lid": ""}


def test_een_herschreven_uitlegvraag_blijft_bij_de_specialist():
    b = _bouw(_Supervisor("VRAAG: Wat betekent artikel 9 van de Invorderingswet 1990?\nWORKERS: antwoord\n"
                          "SPECIALIST: duiding\nPLAN: uitleg"))
    state = {"question": "En wat betekent dat?", "modus": "auto", "werkgebied_id": "", "focus": {},
             "messages": [{"role": "user", "content": "Wat staat er in artikel 9 van de Invorderingswet 1990?"},
                          {"role": "assistant", "content": "…"}, {"role": "user", "content": "En wat betekent dat?"}]}
    upd = supervisie.supervisor_node(b, state)
    assert supervisie._entry_node(b, {**state, **upd}) == "agent" and upd["specialist"] == "duiding"


def test_een_herschreven_vraag_naar_de_bronnen_van_een_deelvraag_gaat_naar_de_dekking():
    """Acceptatie 7 nov 2026: "Welke bronnen horen daarbij?" ging de open lus in (188 s, 7 rondes)."""
    b = _bouw(_Supervisor("VRAAG: Welke bronnen horen bij de deelvraag 'Wie kan om een rekeningafspraak verzoeken?'\n"
                          "WORKERS: antwoord\nSPECIALIST: duiding\nPLAN: bronnen"))
    state = {"question": "Welke bronnen horen daarbij?", "modus": "auto", "werkgebied_id": "w1", "focus": {},
             "messages": [{"role": "user", "content": "Welke deelvraag is het minst uitgewerkt?"},
                          {"role": "assistant", "content": "Deelvraag 5."},
                          {"role": "user", "content": "Welke bronnen horen daarbij?"}]}
    upd = supervisie.supervisor_node(b, state)
    taak = upd["agent_taak"]
    assert (taak["agent"], taak["taak"]) == ("deelvragen", "dekking")
    assert "Wie kan om een rekeningafspraak verzoeken" in taak["parameters"]["vraag"]


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
