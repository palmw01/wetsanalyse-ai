"""De opbouw van een modelverzoek: tellingen en vingerafdrukken, nooit inhoud (`agent/verzoekopbouw.py`)."""
from __future__ import annotations

import json
import logging
from types import SimpleNamespace

from agent.berichten import CORRECTIE
from agent.llm_stap import Rol, aanroep
from agent.models import Verbruiksmeter
from agent.verzoekopbouw import opbouw

TOOLS = [{"name": "get_artikel", "description": "Haalt een artikel op.", "input_schema": {"type": "object"}}]
GEHEIM = "vertrouwelijke vraag over artikel 9"


def _berichten() -> list[dict]:
    return [
        {"role": "user", "content": "eerste vraag"},
        {"role": "assistant", "content": "eerste antwoord"},
        {"role": "user", "content": GEHEIM},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "get_artikel", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "tekst van het artikel"}]},
        {"role": "user", "content": f"{CORRECTIE}het citaat klopt niet"},
    ]


def test_de_opbouw_splitst_historie_en_lopende_beurt():
    berichten = _berichten()
    o = opbouw(system=["stabiel deel", "variabel"], tools=TOOLS, messages=berichten)
    # De correctie hoort bij de lopende beurt: die begint bij de laatste echte vraag.
    assert o["historie_tekens"] == len("eerste vraag") + len("eerste antwoord")
    assert o["beurt_tekens"] > len(GEHEIM)
    assert o["berichten"] == len(berichten)
    assert o["system_stabiel_tekens"] == len("stabiel deel") and o["system_variabel_tekens"] == len("variabel")
    assert o["tools_aantal"] == 1 and o["tools_tekens"] == len(json.dumps(TOOLS, ensure_ascii=False))


def test_de_vingerafdruk_wijst_een_ander_voorvoegsel_aan():
    a = opbouw(system=["stabiel", "x"], tools=TOOLS, messages=[])
    b = opbouw(system=["stabiel", "y"], tools=TOOLS, messages=[])
    c = opbouw(system=["stabiel", "x"], tools=TOOLS + [{"name": "zoek", "input_schema": {}}], messages=[])
    # Het variabele deel telt niet in de vingerafdruk van het stabiele deel; een andere toolset wel.
    assert a["system_hash"] == b["system_hash"] and a["tools_hash"] == b["tools_hash"]
    assert a["tools_hash"] != c["tools_hash"]
    assert len(a["tools_hash"]) == 12


def test_een_systeemtekst_zonder_delen_is_helemaal_stabiel():
    o = opbouw(system="alles", tools=[], messages=[])
    assert o["system_stabiel_tekens"] == 5 and o["system_variabel_tekens"] == 0 and o["tools_hash"] == ""


def test_de_opbouw_draagt_geen_inhoud():
    o = opbouw(system=[GEHEIM, GEHEIM], tools=TOOLS, messages=_berichten())
    tekst = json.dumps(o)
    assert GEHEIM not in tekst and "get_artikel" not in tekst
    assert not any("token" in k for k in o)  # de redactie in `observability` kijkt naar die veldnaam


def test_de_meter_en_de_logregel_dragen_de_opbouw(caplog):
    meter = Verbruiksmeter()
    usage = SimpleNamespace(input_tokens=10, output_tokens=2, cache_read_input_tokens=0, cache_creation_input_tokens=5)
    resp = SimpleNamespace(usage=usage, stop_reason="end_turn", content=[])

    class Nep:
        def create(self, **verzoek):
            meter.tel_response(resp, ms=1, opbouw=opbouw(**verzoek))
            return resp

    verzoek = {"model": "m", "max_tokens": 10, "system": ["stabiel", "variabel"], "tools": TOOLS,
               "messages": _berichten()}
    with caplog.at_level(logging.INFO, logger="graph_qa.llm"):
        aanroep(Nep(), Rol.INTAKE, **verzoek)
    regel = next(r for r in caplog.records if r.getMessage() == "model_aanroep")
    assert regel.tools_hash == meter.aanroepen[0]["tools_hash"]
    assert regel.beurt_tekens == meter.aanroepen[0]["beurt_tekens"] > 0
    assert meter.aanroepen[0]["cache_schrijf"] == 5 and meter.totaal == 17


def test_systeemblokken_tellen_als_tekst_en_een_vreemde_vorm_breekt_niets():
    o = opbouw(system=[{"type": "text", "text": "stabiel"}, {"type": "text", "text": "var"}], tools=[], messages=[])
    assert o["system_stabiel_tekens"] == 7 and o["system_variabel_tekens"] == 3
    assert opbouw(system=None, tools=[{"onserialiseerbaar": object()}], messages=[]) == {}
