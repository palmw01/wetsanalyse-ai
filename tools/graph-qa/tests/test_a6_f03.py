"""F03 na de korte meting na A6 (15 nov 2026, bundel 129): op "Wat is er in de deelgesprekken veranderd sinds je bundel?"
zei Lex "geen ervan gewijzigd", terwijl in deelvraag 1 was doorgevraagd. De markering kwam nooit aan: een deelgesprek
onthield zijn delegatie alleen met een opdracht (een subagent), en de kinderen van een regie starten met een actie. Nu
krijgt ook een regiekind zijn delegatie mee, en markeert doorvragen in zijn deelgesprek haar, met het deelgesprek erbij.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from agent.models import ChatRequest
from agent.nodes import supervisie
from test_regisseur import Kinderen, NepApi, _draai, _plan_id, _verzoek
from test_subagent import STATE

ECHT = "0f32954237464fc7"   # de vorm die de api uitdeelt (uuid4().hex[:16])


def test_een_regiekind_kent_zijn_delegatie():
    class Api(NepApi):
        async def start_delegatie(self, invoer):
            await super().start_delegatie(invoer)
            return {"id": ECHT}

    api, kinderen = Api(), Kinderen()
    events = _draai(_verzoek(plan_id=_plan_id(api)), api, kinderen)
    assert not [e for e in events if e["type"] == "error"] and len(kinderen.verzoeken) == 3
    assert {v.delegatie_id for v in kinderen.verzoeken} == {ECHT}


def test_het_verzoek_neemt_een_delegatie_aan_bij_een_opdracht_of_een_actie():
    ChatRequest(question="Bepaal de bronnen bij deelvraag 1", conversation_id="k1", actie="bronselectie",
                werkgebied_id="w1", delegatie_id=ECHT)
    with pytest.raises(ValueError):
        ChatRequest(question="Waarom?", conversation_id="k1", delegatie_id=ECHT)


def _markeringen(monkeypatch) -> list[dict]:
    gezet: list[dict] = []

    class Api:
        async def wijzig_delegatie(self, _id, waarden):
            gezet.append(waarden)

    import agent.nodes.context as context

    @asynccontextmanager
    async def met_api(_b, _u):
        yield Api()

    monkeypatch.setattr(context, "met_api", met_api)
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: (lambda _e: None))
    return gezet


def _bouw():
    return SimpleNamespace(settings=SimpleNamespace(centrale_agent="aan", legt_zelf_vast=True), graph=None,
                           kinderen=None, loop=None, llm=None)


def test_doorvragen_in_het_deelgesprek_van_een_regiekind_markeert_de_delegatie(monkeypatch):
    """De vraag uit de opzet van F03, in het deelgesprek van deelvraag 1."""
    gezet = _markeringen(monkeypatch)
    state = {**STATE, "gesprek_id": "k1", "question": "Waarom stel je de eerste bepaling voor bij deze deelvraag?",
             "modus": "auto", "agentvorm": "centraal", "deelgesprek": {"delegatie_id": ECHT, "profiel": ""}}
    supervisie._kies(_bouw(), state)
    assert gezet == [{"later_gewijzigd": True, "deelgesprek": "k1"}]


def test_de_eigen_beurt_van_het_kind_markeert_niets(monkeypatch):
    gezet = _markeringen(monkeypatch)
    state = {**STATE, "gesprek_id": "k1", "question": "Bepaal de bronnen bij deelvraag 1", "modus": "auto",
             "actie": "bronselectie", "werkgebied_id": "w1", "deelgesprek": {"delegatie_id": ECHT, "profiel": ""}}
    supervisie._kies(_bouw(), state)
    assert gezet == []
