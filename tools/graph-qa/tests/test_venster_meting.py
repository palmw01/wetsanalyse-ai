"""E6-C1: de logregel `venster` meet hoeveel gesprek er uit het venster naar het model valt."""
from __future__ import annotations

import asyncio
import json
import logging

from agent.agent import answer_stream
from agent.berichten import _KRIMP_NOOT, CORRECTIE, _trim_messages, venster_telling
from agent.observability import JsonFormatter
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block


def _u(text: str) -> dict:
    return {"role": "user", "content": text}


def _a(text: str) -> dict:
    return {"role": "assistant", "content": text}


def _a_tool(tid: str) -> dict:
    return {"role": "assistant", "content": [{"type": "tool_use", "id": tid, "name": "get_lid", "input": {}}]}


def _r(tid: str, tekst: str) -> dict:
    return {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "content": tekst}]}


def test_alles_past_niets_valt_weg():
    msgs = [_u("vraag 1"), _a("antwoord"), _u("vraag 2")]
    t = venster_telling(msgs, _trim_messages(msgs, 40_000, "vraag 2"))
    assert t == {"historie_tekens": 22, "venster_tekens": 22, "beurten_historie": 2,
                 "beurten_venster": 2, "ingekort": 0}


def test_hele_beurten_vallen_weg_en_resultaten_krimpen():
    msgs = []
    for i in range(6):
        msgs += [_u(f"vraag {i}"), _a_tool(f"t{i}"), _r(f"t{i}", "x" * 3000), _a(f"antwoord {i}")]
    msgs.append(_u("nu"))
    venster = _trim_messages(msgs, 5000, "nu")
    t = venster_telling(msgs, venster)
    assert t["beurten_historie"] == 7
    assert 1 <= t["beurten_venster"] < 7
    assert t["venster_tekens"] < t["historie_tekens"]
    # Het krimpen staat in het venster, en niet in het origineel.
    assert t["ingekort"] >= 1
    assert venster_telling(msgs, msgs)["ingekort"] == 0


def test_correctie_en_tool_result_tellen_niet_als_beurt():
    msgs = [_u("vraag"), _a_tool("t1"), _r("t1", "tekst" + _KRIMP_NOOT), _a("antwoord"),
            _u(CORRECTIE + "het citaat klopt niet")]
    t = venster_telling(msgs, msgs)
    assert t["beurten_historie"] == t["beurten_venster"] == 1
    assert t["ingekort"] == 1


def test_de_telling_wijzigt_het_venster_niet():
    msgs = [_u("vraag"), _a_tool("t1"), _r("t1", "x" * 9000), _u("nog een")]
    kopie = json.loads(json.dumps(msgs))
    venster = _trim_messages(msgs, 1000, "nog een")
    venster_telling(msgs, venster)
    assert msgs == kopie


def _regels(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "graph_qa.beurt" and r.getMessage() == "venster"]


def test_een_regel_per_beurt_ook_bij_meer_toolrondes(caplog):
    caplog.set_level(logging.INFO, logger="graph_qa.beurt")
    settings = make_settings(enable_planning=False, grounding_correct=False)
    graph = FakeGraph(result='?regeling\t?citeertitel\n<urn:bwb:BWBR0004770>\t"Invorderingswet 1990"\n')
    llm = FakeLLM([
        response([tool_block("t1", "list_regelingen", {})], "tool_use"),
        response([tool_block("t2", "list_regelingen", {"zoek": "a"})], "tool_use"),
        response([tool_block("t3", "list_regelingen", {"zoek": "b"})], "tool_use"),
        response([text_block("Klaar.")], "end_turn"),
    ])

    async def lus():
        return [e async for e in answer_stream("vraag", settings=settings, llm=llm, graph=graph,
                                                conversation_id="g1", run_id="r1")]

    events = asyncio.run(lus())
    assert "done" in [e["type"] for e in events]
    assert sum(e["type"] == "tool_execution" and e.get("phase") == "start" for e in events) >= 3

    [regel] = _regels(caplog)
    assert regel.categorie == "functioneel"
    assert regel.run_id == "r1"
    assert regel.chat_session_id == "g1"
    assert regel.beurten_historie == regel.beurten_venster == 1
    assert regel.ingekort == 0
    assert regel.register_items == 0
    # Geen inhoud en geen veldnaam met "token": zo komt hij ongeschonden door de redactie.
    uit = json.loads(JsonFormatter().format(regel))
    velden = {"run_id", "chat_session_id", "historie_tekens", "venster_tekens", "beurten_historie",
              "beurten_venster", "ingekort", "register_items"}
    assert velden <= uit.keys()
    assert not any("token" in k for k in velden)
    assert "vraag" not in json.dumps({k: uit[k] for k in velden})
