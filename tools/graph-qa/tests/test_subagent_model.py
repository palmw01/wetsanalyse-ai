"""Een subagent draait op de lichte modelklasse (ADR-016 §A2; besluit gebruiker 14 nov 2026), de centrale agent niet."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent import agentvorm, subagent as sub
from agent.agentvorm import Subagent, agent_voor, subagent_model
from fakes import make_settings


@pytest.fixture(autouse=True)
def _schoon():
    agentvorm._LICHT_KAPOT.clear()
    yield
    agentvorm._LICHT_KAPOT.clear()


def test_de_lichte_klasse_en_haar_terugval():
    assert subagent_model(make_settings(llm_model="zwaar-m", llm_model_licht="licht-m")) == ("licht-m", "")
    assert subagent_model(make_settings(llm_model="zwaar-m", llm_model_router="router-m")) == ("router-m", "")
    assert subagent_model(make_settings(llm_model="zwaar-m")) == ("zwaar-m", "geen_lichte_klasse")


def test_alleen_een_subagent_draait_licht():
    s = make_settings(llm_model="zwaar-m", llm_model_licht="licht-m")
    assert agent_voor("duiding", subagent=True).model(s) == "licht-m"
    assert agent_voor("duiding").model(s) == "zwaar-m", "als specialist van de supervisor houdt een profiel zijn model"
    assert agent_voor("centraal").model(s) == "zwaar-m", "de centrale agent blijft op zijn eigen model"


class Fout(Exception):
    def __init__(self, status):
        self.status_code = status


def test_faalt_het_lichte_model_dan_het_gewone_en_daarna_blijft_dat(monkeypatch):
    s = make_settings(llm_model="zwaar-m", llm_model_licht="licht-m")
    gebruikt = []

    def ronde(self, llm, settings, **kw):
        gebruikt.append(self.model(settings))
        if self.model(settings) == "licht-m":
            raise Fout(404)
        return "antwoord"

    monkeypatch.setattr(agentvorm.Agent, "ronde", ronde)
    a = agent_voor("algemeen", subagent=True)
    assert isinstance(a, Subagent) and a.ronde(None, s) == "antwoord"
    assert gebruikt == ["licht-m", "zwaar-m"]
    assert a.model(s) == "zwaar-m" and subagent_model(s) == ("zwaar-m", "lichte_klasse_faalde"), \
        "het voorvoegsel blijft per model vast: geen wisselen per ronde"


def test_een_andere_fout_valt_niet_terug(monkeypatch):
    s = make_settings(llm_model="zwaar-m", llm_model_licht="licht-m")
    monkeypatch.setattr(agentvorm.Agent, "ronde", lambda self, llm, settings, **kw: (_ for _ in ()).throw(Fout(500)))
    with pytest.raises(Fout):
        agent_voor("algemeen", subagent=True).ronde(None, s)
    assert not agentvorm._LICHT_KAPOT


def test_het_kind_meldt_zijn_model_in_het_event():
    assert sub.kindmodel(make_settings(llm_model="zwaar-m", llm_model_licht="licht-m"), "algemeen") == "licht-m"
    assert sub.kindmodel(None, "algemeen") == ""
    assert sub.kindmodel(SimpleNamespace(llm_model=""), "algemeen") == ""


def test_het_model_van_het_kind_staat_in_regie_taak_en_in_de_meetsamenvatting():
    import asyncio

    from eval.centrale_agent_vat import vat  # noqa: F401 – de samenvatting leest `model` uit `regie_taak`
    from test_subagent import OPDRACHT, STATE, Api, _kinderen

    events = []
    kinderen, _, _ = _kinderen({"rapport": {"status": "klaar"}, "answer": "x", "source_trace": []})
    asyncio.run(sub.voer_uit(STATE, "duiding", OPDRACHT, events.append,
                             settings=make_settings(llm_model="zwaar-m", llm_model_licht="licht-m"),
                             kinderen=kinderen, gestopt=lambda: False, api=Api()))
    [start] = [e for e in events if e["type"] == "regie_taak" and e["fase"] == "start"]
    assert start["gekozen_model"] == "licht-m"


def test_de_mislukte_aanroep_staat_in_aanroepen_en_het_gedraaide_model_telt(monkeypatch):
    from agent.models import Verbruiksmeter

    s = make_settings(llm_model="zwaar-m", llm_model_licht="licht-m")
    meter = Verbruiksmeter()
    llm = SimpleNamespace(meter=meter)

    def ronde(self, llm, settings, **kw):
        if self.model(settings) == "licht-m":
            raise Fout(404)
        meter.tel_response(SimpleNamespace(usage=SimpleNamespace(input_tokens=1, output_tokens=1)), rol="antwoord",
                           model="zwaar-m")
        return "antwoord"

    monkeypatch.setattr(agentvorm.Agent, "ronde", ronde)
    agent_voor("algemeen", subagent=True).ronde(llm, s)
    mislukt, gelukt = meter.aanroepen
    assert (mislukt["model"], mislukt["mislukt"], mislukt["http_status"], mislukt["invoer"]) == (
        "licht-m", "subagent_model_terugval", 404, 0)
    assert gelukt["model"] == "zwaar-m" and meter.gedraaid() == ["zwaar-m"]
    assert meter.calls == 1, "de mislukte aanroep telt niet in de sommen"


def test_het_eind_event_toont_het_model_dat_echt_draaide():
    import asyncio

    from test_subagent import OPDRACHT, STATE, Api, _kinderen

    events = []
    kinderen, _, _ = _kinderen({"rapport": {"status": "klaar"}, "answer": "x", "source_trace": [], "modellen": ["zwaar-m"]})
    asyncio.run(sub.voer_uit(STATE, "duiding", OPDRACHT, events.append,
                             settings=make_settings(llm_model="zwaar-m", llm_model_licht="licht-m"),
                             kinderen=kinderen, gestopt=lambda: False, api=Api()))
    [eind] = [e for e in events if e["type"] == "regie_taak" and e["fase"] == "eind"]
    assert (eind["model"], eind["modellen"]) == ("zwaar-m", ["zwaar-m"])


def test_de_contextopbouw_toont_de_mislukte_aanroep():
    from agent.contextopbouw import _regel

    regel = _regel({"rol": "antwoord", "model": "licht-m", "mislukt": "subagent_model_terugval", "http_status": 404,
                    "invoer": 0, "uitvoer": 0, "cache_lees": 0, "cache_schrijf": 0})
    assert (regel["mislukt"], regel["model"], regel["http_status"], regel["totaal"]) == (
        "licht-m" and "subagent_model_terugval", "licht-m", 404, 0)
    assert "mislukt" not in _regel({"rol": "antwoord", "model": "zwaar-m", "invoer": 3})
