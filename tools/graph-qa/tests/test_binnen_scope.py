"""Een vraag die een regeling noemt, wijst Lex niet af, in beide vormen (ADR-016 ronde 4, K12).

"Wat is bekend over het milieu in de milieuwet?" wees de centrale agent af als niet over Nederlandse wet- en regelgeving;
de supervisor zocht en zei dat de graaf geen milieuregelgeving bevat. Dat laatste is het goede antwoord. De regel staat in
`agent/binnen_scope.py`, naast die voor een bron naast de wet."""
from __future__ import annotations

import asyncio

import pytest

from agent.agent import answer_stream
from agent.binnen_scope import genoemde_regelingen, niet_afwijzen
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block

K12 = "wat is bekend over het milieu in de milieuwet?"
AFWIJZEN = response([text_block("WORKERS: antwoord\nSPECIALIST: algemeen\nTAAK:\nPLAN: AFWIJZEN")], "end_turn")


def _run(gen):
    async def collect():
        return [ev async for ev in gen]

    return asyncio.run(collect())


def _tekst(events) -> str:
    return "".join(e.get("content", "") for e in events if e["type"] == "token")


@pytest.mark.parametrize("vraag,namen", [
    (K12, ["milieuwet"]),
    ("Wat zegt de Wet milieubeheer over geluid?", ["Wet milieubeheer"]),
    ("Hoe werkt de omgevingswet?", ["omgevingswet"]),
    ("Wat zegt de Invorderingswet 1990 over uitstel?", ["Invorderingswet 1990"]),
])
def test_een_regeling_in_de_vraag_wordt_herkend(vraag, namen):
    assert genoemde_regelingen(vraag) == namen
    assert "Wijs de vraag niet af" in niet_afwijzen(vraag)


@pytest.mark.parametrize("vraag", ["Wat voor weer wordt het morgen?", "Hoe schrijf ik een lus in Python?",
                                   "Wie won de wedstrijd gisteren?"])
def test_een_vraag_buiten_de_wetgeving_mag_worden_afgewezen(vraag):
    assert niet_afwijzen(vraag) == ""


def test_de_supervisor_draait_een_afwijzing_van_een_regelingvraag_terug():
    llm = FakeLLM([AFWIJZEN, response([text_block("De milieuwet staat niet in de kennisgraaf.")], "end_turn")])
    events = _run(answer_stream(K12, settings=make_settings(), llm=llm, graph=FakeGraph(result="")))
    assert len(llm.calls) == 2, "het model zei AFWIJZEN, de code liet de worker toch zoeken"
    assert "niet in de kennisgraaf" in _tekst(events)
    assert not any(e["type"] == "status" and e.get("route") == "afgewezen" for e in events)


def test_de_centrale_agent_krijgt_wijs_af_geweigerd_bij_een_regelingvraag():
    llm = FakeLLM([response([tool_block("t1", "wijs_af", {})], "tool_use"),
                   response([text_block("De milieuwet staat niet in de kennisgraaf.")], "end_turn")])
    events = _run(answer_stream(K12, settings=make_settings(centrale_agent="meten"), llm=llm,
                                graph=FakeGraph(result=""), agentvorm="centraal"))
    assert len(llm.calls) == 2
    [resultaat] = [b for m in llm.calls[1]["messages"] if isinstance(m["content"], list)
                   for b in m["content"] if b.get("type") == "tool_result"]
    assert resultaat["is_error"] is True and "milieuwet" in resultaat["content"]
    assert not any(e["type"] == "status" and e.get("route") == "afgewezen" for e in events)
