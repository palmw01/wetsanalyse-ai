"""De supervisor in een lopend gesprek: eerst lezen waar een vervolgvraag over gaat, dan kiezen.

Zonder dit zag de supervisor alleen de kale vraag. "Waarom?" na een annotatie werd een afwijzing of
een plan zonder onderwerp, en "welke zijn er nog meer?" na een vraag over rechtssubjecten was geen
leesvraag – het woord "annotatie" stond er niet in.
"""
from __future__ import annotations

import asyncio

from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block, vraag_van
from test_bronnode_keten import ReadApi, snapshot

from agent.agent import answer_stream
from agent.berichten import eerdere_beurten


def _run(gen):
    async def collect():
        return [ev async for ev in gen]
    return asyncio.run(collect())


def test_eerdere_beurten_zonder_toolruis():
    messages = [
        {"role": "user", "content": "Wat regelt artikel 9?"},
        {"role": "assistant", "content": [{"type": "text", "text": "Ik zoek."},
                                          {"type": "tool_use", "id": "t", "name": "get_artikel", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t", "content": "x" * 5000}]},
        {"role": "assistant", "content": [{"type": "text", "text": "Artikel 9 regelt de invorderbaarheid."}]},
        {"role": "user", "content": "Let op: onderbouw dit."},
        {"role": "user", "content": "En lid 2?"},
    ]
    assert eerdere_beurten(messages, "En lid 2?") == [("Wat regelt artikel 9?", "Artikel 9 regelt de invorderbaarheid.")]
    assert eerdere_beurten(messages[:1], "Wat regelt artikel 9?") == []


def _eerste_beurt(settings, gid):
    llm = FakeLLM([
        response([tool_block("t1", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": "9"})], "tool_use"),
        response([text_block("Artikel 9 regelt wanneer een aanslag invorderbaar is.")], "end_turn"),
    ])
    _run(answer_stream("Wat regelt artikel 9 van de Invorderingswet 1990?", gid, settings=settings, llm=llm,
                       graph=FakeGraph(result='?nummer\t?tekst\n"9"\t"tekst"')))
    supervisor = str(llm.prompts[0])
    assert "VERVOLGVRAAG" not in supervisor, "de eerste vraag van een gesprek heeft niets te herschrijven"

