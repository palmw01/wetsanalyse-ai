"""Een genoemd stuk direct lezen (ADR-013): de vraag noemt een id van een connector die aanstaat (`kst-35496-F`).

Het model zocht dan eerst: `zoek_kamerstukken` met verkeerde argumenten, twee pagina's van het hele dossier en pas
daarna `get_kamerstuk` – zes rondes en ruim 100k cache-tokens voor een stuk waarvan de jurist het id al gaf
(acceptatie 8 nov 2026). Net als bij een genoemd artikel beslist de code: de leestool uit de beschrijving
(`leestool`, `lees_argument`) draait vóór de eerste modelronde, als echt `tool_use`/`tool_result`-paar in de historie
en in de `source_trace`, zodat bronnen, grounding en het subsjabloon `extern` het resultaat zien. Daarna formuleert de
agent, met de tools beschikbaar voor het vervolg (een volgende pagina, een tabel).

Dezelfde vorm als de leesroute voor annotaties (`annotatie_lezen.zoek_annotaties_node`).
"""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from bronmodel.antwoord import Antwoord, Leemte, antwoord_tekst
from bronmodel.connectors import van_id
from langgraph.config import get_stream_writer

from ..narratie import _stap, _toolregel
from ..sjablonen.extern import lijsten
from ..sjablonen.vullen import Onvulbaar
from ..state import State
from ..tool_execution import execute_tool

TOELICHTING = (
    "Deze stukken zijn al voor je opgehaald, omdat de vraag hun id noemt; haal ze niet opnieuw op en zoek ze niet. "
    "Beantwoord de vraag uit deze tekst. Is het resultaat niet volledig, haal dan alleen het vervolg op dat je nodig hebt."
)


def bron_lezen_node(b, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    gebruik, resultaten, trace = [], [], list(state.get("source_trace", []))
    for aanroep in state.get("bron_lezen") or []:
        tool = {"id": uuid4().hex, "name": aanroep["name"], "input": dict(aanroep.get("input") or {})}
        _stap(writer, "Lex", _toolregel(tool))
        raw = execute_tool(b, state, writer, tool)
        gebruik.append({"type": "tool_use", **tool})
        resultaten.append({"type": "tool_result", "tool_use_id": tool["id"], "content": raw})
        trace.append((tool["name"], raw))
    if not gebruik:
        return {"bron_lezen": []}
    paar = [{"role": "assistant", "content": gebruik}, {"role": "user", "content": resultaten}]
    if (zonder := _zonder_tekst(resultaten, trace)) is not None:
        uit = antwoord_tekst(zonder)
        return {"bron_lezen": [], "source_trace": trace, "answer": uit, "antwoord": zonder.model_dump(),
                "messages": [*paar, {"role": "assistant", "content": [{"type": "text", "text": uit}]}]}
    return {
        # Eén keer: een volgende worker in de keten leest niet opnieuw.
        "bron_lezen": [],
        "source_trace": trace,
        "messages": [{"role": "assistant", "content": gebruik},
                     {"role": "user", "content": [*resultaten, {"type": "text", "text": TOELICHTING}]}],
    }


def _zonder_tekst(resultaten: list[dict[str, Any]], trace: list[tuple[str, str]]) -> Antwoord | None:
    """Heeft elk gelezen stuk geen tekst bij de bron (een uitspraak met alleen metadata), dan zegt de code dat, met het
    stuk en zijn gegevens uit de bron als lijst en de link: geen model, dus geen eigen duiding ("dus een verkeersboete")
    en geen systeemtaal (nameting 10 nov 2026). None als er iets te lezen is, of bij een fout: dan formuleert de agent."""
    ids: list[str] = []
    for r in resultaten:
        try:
            data = json.loads(r.get("content") or "")
        except (TypeError, ValueError):
            return None
        stuk = data.get("stuk") if isinstance(data, dict) else None
        if (data.get("status") != "ok" or data.get("resultaten") or data.get("vervolg")
                or not isinstance(stuk, dict) or not isinstance(stuk.get("id"), str)):
            return None
        ids.append(stuk["id"])
    try:
        stukken = lijsten(ids, trace)
    except Onvulbaar:
        return None
    c = van_id(ids[0])
    melding = (f"De tekst van {'dit stuk' if len(ids) == 1 else 'deze stukken'} staat niet bij de bron: er is alleen "
               "de beschrijving hieronder. Lees de tekst via de link.")
    for s in stukken:
        s.kop = c.kop_in_antwoord if c is not None else s.kop
    return Antwoord(sjabloon="extern", blokken=[Leemte(tekst=melding), *stukken])


def route_na_bron_lezen(b, state: State) -> str:
    """Met een antwoord uit code (een stuk zonder tekst) naar de controle; anders formuleert de agent."""
    return "verify" if state.get("antwoord") else "agent"
