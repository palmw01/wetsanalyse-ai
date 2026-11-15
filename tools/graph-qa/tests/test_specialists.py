"""De supervisor routeert naar een specialist met eigen tool-subset."""
from __future__ import annotations

import asyncio

from agent import tools
from agent.agent import answer_stream
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block


def _run(gen):
    async def collect():
        return [ev async for ev in gen]

    return asyncio.run(collect())


def _route_to(specialist: str) -> FakeLLM:
    return FakeLLM([
        response([text_block("Direct antwoord.")], "end_turn"),                              # agent (geen tools)
    ])


def _agent_tools(llm: FakeLLM) -> set[str]:
    # llm.calls[0] = router (create), [1] = agent (stream) → de tool-set die de agent zag.
    return {t["name"] for t in llm.calls[1]["tools"]}


def test_definitie_prompt_volgt_bronvindplaats_en_onderdelen():
    from agent.specialists import get

    prompt = get("definitie").system
    assert "bepaal de vindplaats uit bronresultaten" in prompt
    assert "Haal de gevonden definitiebepaling op" in prompt
    assert "&o=k" in prompt


def test_planning_uit_is_algemeen_alle_tools():
    llm = FakeLLM([response([text_block("Antwoord.")], "end_turn")])
    _run(answer_stream("vraag", settings=make_settings(enable_planning=False),
                       llm=llm, graph=FakeGraph(result="")))
    # geen router → llm.calls[0] is de agent-stream-call
    assert {t["name"] for t in llm.calls[0]["tools"]} == ({t["name"] for t in tools.TOOLS} - tools.CONNECTOR_TOOLS) | {"antwoord_bepaling"}
