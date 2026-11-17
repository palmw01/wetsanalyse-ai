"""Het model van een subagent kiest de beheerder (`agent:<profiel>`, anders `stap:subagent`); zonder keuze draait hij op
het gewone model, net als de centrale agent. De lichte modelklasse uit de env is met ADR-016 §A7 vervallen."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent import agentvorm, modelkeuze, subagent as sub
from agent.agentvorm import Subagent, agent_voor
from fakes import make_settings


@pytest.fixture(autouse=True)
def _schoon():
    modelkeuze.vergeet()
    yield
    modelkeuze.vergeet()


def _stand(**keuzes: str) -> modelkeuze.Stand:
    return modelkeuze.Stand(basis="zwaar-m", standaard=None,
                            keuzes={k.replace("_", ":", 1): (f"p-{k}", m) for k, m in keuzes.items()})


def test_zonder_keuze_draait_een_subagent_op_het_gewone_model():
    s = make_settings(llm_model="zwaar-m")
    assert agent_voor("bepalingen_duiden", subagent=True).model(s) == "zwaar-m"
    assert agent_voor("centraal").model(s) == "zwaar-m"
    assert sub.kindmodel(s, "algemeen") == "zwaar-m"


def test_het_kind_meldt_de_keuze_van_de_beheerder():
    s = make_settings(llm_model="zwaar-m")
    modelkeuze.zet(_stand(stap_subagent="claude-licht", agent_bepalingen_duiden="claude-midden"))
    assert sub.kindmodel(s, "algemeen") == "claude-licht"
    assert sub.kindmodel(s, "bepalingen_duiden") == "claude-midden", "de keuze voor het profiel gaat voor"
    assert sub.kindmodel(None, "algemeen") == ""
    assert sub.kindmodel(SimpleNamespace(llm_model=""), "algemeen") == ""


def test_een_subagent_vraagt_de_keuze_voor_subagents(monkeypatch):
    gezien = []
    monkeypatch.setattr(agentvorm.Agent, "ronde", lambda self, llm, settings, **kw: gezien.append(kw["kader"]) or "ok")
    a = agent_voor("algemeen", subagent=True)
    assert isinstance(a, Subagent) and a.ronde(None, make_settings(), kader={"x": 1}) == "ok"
    assert gezien == [{"x": 1, "modelrol": "subagent"}]


def test_het_model_van_het_kind_staat_in_regie_taak():
    import asyncio

    from test_subagent import OPDRACHT, STATE, Api, _kinderen

    modelkeuze.zet(_stand(stap_subagent="claude-licht"))
    events = []
    kinderen, _, _ = _kinderen({"rapport": {"status": "klaar"}, "answer": "x", "source_trace": []})
    asyncio.run(sub.voer_uit(STATE, "bepalingen_duiden", OPDRACHT, events.append,
                             settings=make_settings(llm_model="zwaar-m"),
                             kinderen=kinderen, gestopt=lambda: False, api=Api()))
    [start] = [e for e in events if e["type"] == "regie_taak" and e["fase"] == "start"]
    assert start["gekozen_model"] == "claude-licht"


def test_het_eind_event_toont_het_model_dat_echt_draaide():
    import asyncio

    from test_subagent import OPDRACHT, STATE, Api, _kinderen

    events = []
    kinderen, _, _ = _kinderen({"rapport": {"status": "klaar"}, "answer": "x", "source_trace": [], "modellen": ["zwaar-m"]})
    asyncio.run(sub.voer_uit(STATE, "bepalingen_duiden", OPDRACHT, events.append,
                             settings=make_settings(llm_model="zwaar-m"),
                             kinderen=kinderen, gestopt=lambda: False, api=Api()))
    [eind] = [e for e in events if e["type"] == "regie_taak" and e["fase"] == "eind"]
    assert (eind["model"], eind["modellen"]) == ("zwaar-m", ["zwaar-m"])


def test_de_contextopbouw_toont_een_mislukte_aanroep():
    from agent.contextopbouw import _regel

    regel = _regel({"rol": "antwoord", "model": "licht-m", "mislukt": "modelprofiel_terugval", "http_status": 404,
                    "invoer": 0, "uitvoer": 0, "cache_lees": 0, "cache_schrijf": 0})
    assert (regel["mislukt"], regel["model"], regel["http_status"], regel["totaal"]) == (
        "modelprofiel_terugval", "licht-m", 404, 0)
    assert "mislukt" not in _regel({"rol": "antwoord", "model": "zwaar-m", "invoer": 3})
