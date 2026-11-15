"""ADR-016 §A7: de vlag en de supervisor zijn weg; de ingang kiest een route in code of de centrale agent.

1. Het denkproces van één beurt van de centrale agent begint met één korte regel ("Lex · bekijkt de vraag"), zonder de
   bronnen die aanstaan, en er staat geen tweede "zoekt in …"-regel vóór de eerste tool. Welke bronnen Lex gebruikt,
   zeggen de toolstappen. Dezelfde regel bij een subagent: geen bronnenlijst vooraf.
2. Wat eerst alleen via de supervisor liep, is via de centrale agent bereikbaar, door de hele graaf: afwijzen
   (`test_centrale_agent.py`), annoteren (`test_centrale_agent.py`, `test_aanwijzing.py`), het werkgebied
   (`test_werkgebied_intake.py`), de deelvragenagent (`test_centrale_agent.py`) en hier de begrippenagent.
"""
from __future__ import annotations

import asyncio

from agent.agent import answer_stream
from agent.nodes import supervisie
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block

ALLE = {f"connector_{n}": True for n in ("kamerstukken", "rechtspraak", "bekendmakingen", "kennisgroepen",
                                          "wetgeving_live")}


def _statussen(events: list[dict]) -> list[str]:
    return [e["message"] for e in events if e.get("type") == "status"]


def _voor_de_eerste_tool(events: list[dict]) -> list[str]:
    uit = []
    for e in events:
        if e.get("type") == "tool_execution":
            break
        if e.get("type") == "status":
            uit.append(e["message"])
    return uit


def test_een_beurt_van_de_centrale_agent_begint_met_een_regel_zonder_bronnenlijst():
    """De begripsvraag van de gebruiker (15 nov 2026): eerst "zoekt het antwoord in de wetgeving en Kamerstukken, …",
    dan "zoekt in de wetgeving en …", en pas daarna de definitie."""
    llm = FakeLLM([response([tool_block("t1", "zoek_definitie", {"term": "belastingschuldige"})], "tool_use"),
                   response([text_block("De belastingschuldige is degene die de belasting verschuldigd is.")], "end_turn")])

    async def beurt():
        return [e async for e in answer_stream("Wat betekent belastingschuldige?", settings=make_settings(**ALLE),
                                               llm=llm, graph=FakeGraph(result=""))]

    events = asyncio.run(beurt())
    vooraf = _voor_de_eerste_tool(events)
    # De eerste regel, en daarna alleen de stap van de tool zelf.
    assert vooraf == [f"Lex · {supervisie.NAAR_CENTRAAL}", "Lex · zoekt de definitie van „belastingschuldige”"], vooraf
    assert not any("zoekt in" in m or "zoekt het antwoord in" in m for m in _statussen(events))
    assert not any(label in vooraf[0] for label in ("Kamerstukken", "Rechtspraak", "Staatsblad")), "geen bronnenlijst"


def test_de_begrippenagent_is_via_de_centrale_agent_bereikbaar():
    from tests.test_agents import NepApi, _api_settings

    llm = FakeLLM([response([tool_block("t1", "taakagent", {"agent": "begrippen", "taak": "voorstellen"})], "tool_use"),
                   response([text_block("Klaar.")], "end_turn")])

    async def beurt():
        return [e async for e in answer_stream("Stel de begrippen voor van dit werkgebied.", None,
                                               settings=_api_settings(), llm=llm, graph=FakeGraph(), user_id="jurist",
                                               run_id="r1", werkgebied_id="wg1", agent_api=lambda s, u: NepApi())]

    events = asyncio.run(beurt())
    assert "rol agent" in llm.calls[0]["system"], "de centrale agent kiest de taak, geen supervisor"
    assert any(e.get("type") == "status" and e.get("route") == "begrippen" for e in events), _statussen(events)
