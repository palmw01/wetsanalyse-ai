"""Een async agent uitvoeren vanuit een synchrone LangGraph-node.

De nodes van de graaf zijn synchroon en draaien in de default-executor (`orchestrator.py`), zodat een
blokkerende LLM- of MCP-aanroep de event loop niet vasthoudt. De bestaande stromen op een werkgebied –
bronnen zoeken, begrippen voorstellen, de kaartacties, de verdieping – zijn async: ze praten met de api
via een `httpx.AsyncClient`, en die hoort bij de event loop waarop hij gemaakt is.

`draai` zet de coroutine daarom op de event loop van de beurt (`asyncio.run_coroutine_threadsafe`) en
laat de node-thread wachten. Events gaan via een thread-veilige wachtrij en de node schrijft ze in zijn
eigen thread naar de stream-writer van LangGraph, in volgorde. Zonder lopende loop (een synchrone
aanroep, zoals in een test met `invoke`) krijgt de coroutine een eigen loop.

Stoppen blijft een vlag: de agent leest `Context.gestopt` tussen zijn stappen, en de node zelf staat in
`stopbaar()`. Een lopende stap maakt zichzelf af, net als een node.
"""
from __future__ import annotations

import asyncio
import queue
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")

_WACHT_S = 0.05


def op_de_loop(loop: asyncio.AbstractEventLoop | None) -> bool:
    """Draait deze thread de event loop zelf? Dan mag hij er niet op wachten."""
    try:
        return asyncio.get_running_loop() is loop
    except RuntimeError:
        return False


def draai(maak: Callable[[Callable[[dict[str, Any]], None]], Awaitable[T]], *,
          loop: asyncio.AbstractEventLoop | None, schrijf: Callable[[dict[str, Any]], None]) -> T:
    """Voer `maak(stuur)` uit en geef zijn uitkomst. `stuur(event)` mag vanaf elke thread; elk event komt,
    in volgorde, bij `schrijf` in de thread van de aanroeper."""
    wachtrij: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()

    def leeg() -> None:
        while True:
            try:
                schrijf(wachtrij.get_nowait())
            except queue.Empty:
                return

    if loop is not None and loop.is_running():
        if op_de_loop(loop):
            raise RuntimeError("een agent wacht nooit op de event loop waarop hij zelf draait")
        toekomst = asyncio.run_coroutine_threadsafe(maak(wachtrij.put), loop)
        while not toekomst.done():
            try:
                schrijf(wachtrij.get(timeout=_WACHT_S))
            except queue.Empty:
                continue
        leeg()
        return toekomst.result()
    uitkomst = asyncio.run(maak(wachtrij.put))
    leeg()
    return uitkomst
