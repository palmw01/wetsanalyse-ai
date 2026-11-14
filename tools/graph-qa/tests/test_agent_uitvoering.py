"""Spike (F3c, eerste stap): een async agent in een synchrone LangGraph-node.

De bestaande stromen op een werkgebied zijn async en houden een api-client vast die bij de event loop van
de beurt hoort; de nodes van de graaf zijn synchroon en draaien in een executor-thread. Deze tests
bewijzen dat `agents.uitvoering.draai` de coroutine op díe loop zet, de events in volgorde in de stream
krijgt, een fout doorgeeft en de stopvlag laat werken.
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any, TypedDict

import pytest
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from agent.agents.uitvoering import draai


class _S(TypedDict, total=False):
    uit: str


def _graaf(maak, loop_van):
    def node(state: _S) -> dict[str, Any]:
        writer = get_stream_writer()
        return {"uit": draai(maak, loop=loop_van(), schrijf=writer)}

    g = StateGraph(_S)
    g.add_node("agent_taak", node)
    g.add_edge(START, "agent_taak")
    g.add_edge("agent_taak", END)
    return g.compile()


async def _stroom(app) -> tuple[list[dict], dict]:
    events, laatste = [], {}
    async for modus, stuk in app.astream({}, stream_mode=["custom", "values"]):
        if modus == "custom":
            events.append(stuk)
        else:
            laatste = stuk
    return events, laatste


def test_de_agent_draait_op_de_loop_van_de_beurt_en_de_events_komen_in_volgorde():
    gezien: dict[str, Any] = {}

    async def hoofd():
        beurt_loop = asyncio.get_running_loop()
        # Een object dat aan déze loop vastzit, zoals de `httpx.AsyncClient` van de api.
        klaar = asyncio.Event()

        def maak(stuur):
            async def agent() -> str:
                gezien["loop"] = asyncio.get_running_loop()
                gezien["thread"] = threading.get_ident()
                for i in range(3):
                    stuur({"type": "status", "message": f"Lex · stap {i}"})
                    await asyncio.sleep(0)
                klaar.set()
                await klaar.wait()
                return "klaar"
            return agent()

        events, laatste = await _stroom(_graaf(maak, lambda: beurt_loop))
        return beurt_loop, threading.get_ident(), events, laatste

    beurt_loop, hoofdthread, events, laatste = asyncio.run(hoofd())
    assert gezien["loop"] is beurt_loop and gezien["thread"] == hoofdthread
    assert [e["message"] for e in events] == ["Lex · stap 0", "Lex · stap 1", "Lex · stap 2"]
    assert laatste["uit"] == "klaar"


def test_een_fout_in_de_agent_komt_bij_de_beurt_aan():
    async def hoofd():
        loop = asyncio.get_running_loop()

        def maak(stuur):
            async def agent():
                stuur({"type": "status", "message": "Lex · begint"})
                raise ValueError("api weg")
            return agent()

        return await _stroom(_graaf(maak, lambda: loop))

    with pytest.raises(ValueError, match="api weg"):
        asyncio.run(hoofd())


def test_de_stopvlag_houdt_de_agent_tussen_zijn_stappen_tegen():
    stop = threading.Event()

    async def hoofd():
        loop = asyncio.get_running_loop()

        def maak(stuur):
            async def agent() -> str:
                for i in range(100):
                    if stop.is_set():
                        return f"gestopt na {i}"
                    stuur({"type": "status", "message": f"stap {i}"})
                    if i == 2:
                        stop.set()      # de jurist drukt op stop terwijl de agent loopt
                    await asyncio.sleep(0)
                return "af"
            return agent()

        return await _stroom(_graaf(maak, lambda: loop))

    events, laatste = asyncio.run(hoofd())
    assert laatste["uit"] == "gestopt na 3" and len(events) == 3


def test_zonder_lopende_loop_krijgt_de_agent_een_eigen_loop():
    def maak(stuur):
        async def agent() -> str:
            stuur({"type": "status", "message": "eigen loop"})
            return "ok"
        return agent()

    geschreven: list[dict] = []
    assert draai(maak, loop=None, schrijf=geschreven.append) == "ok"
    assert geschreven == [{"type": "status", "message": "eigen loop"}]


def test_op_de_loop_zelf_wachten_wordt_geweigerd():
    async def hoofd():
        loop = asyncio.get_running_loop()

        def maak(stuur):
            async def agent():
                return "nooit"
            return agent()

        coro_maak = maak
        with pytest.raises(RuntimeError, match="event loop"):
            draai(coro_maak, loop=loop, schrijf=lambda e: None)

    asyncio.run(hoofd())


def test_een_agent_die_niet_klaar_wordt_houdt_de_node_niet_eeuwig_vast():
    """Bugonderzoek ADR-016 (twijfelgeval): de node wacht met een grens, annuleert de taak en geeft een nette fout."""
    from agent.agents.uitvoering import AgentWachtTeLang

    loop = asyncio.new_event_loop()
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()
    geannuleerd = threading.Event()

    async def hangt(_stuur):
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            geannuleerd.set()
            raise

    try:
        with pytest.raises(AgentWachtTeLang, match="niet klaar binnen"):
            draai(hangt, loop=loop, schrijf=lambda _e: None, max_wacht_s=0.2)
        assert geannuleerd.wait(2), "de taak is geannuleerd"
    finally:
        loop.call_soon_threadsafe(loop.stop)
        t.join(2)


def test_een_loop_die_stopt_zonder_te_annuleren_laat_de_node_niet_hangen():
    from agent.agents.uitvoering import AgentWachtTeLang

    loop = asyncio.new_event_loop()
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()

    async def hangt(_stuur):
        await asyncio.sleep(60)

    threading.Timer(0.2, lambda: loop.call_soon_threadsafe(loop.stop)).start()
    with pytest.raises(AgentWachtTeLang, match="event loop"):
        draai(hangt, loop=loop, schrijf=lambda _e: None, max_wacht_s=30)
    t.join(2)
    loop.close()
