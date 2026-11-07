"""Eén logregel per beurt: wat de jurist wachtte, en wat het kostte.

Het dashboard toonde alleen een p95 per dienst. Die mengt een korte POST met een SSE van minuten,
dus de wachttijd stond nergens. `gemeten` wikkelt zich om de hele beurt (`voer_beurt_uit`) en schrijft
aan het eind `beurt_meting` weg, ook bij een fout, stop of afgebroken verbinding.

Twee keuzes:

- **`eerste_tekst_ms` is de eerste `reason` of `token`**: het moment dat de jurist tekst ziet. Alleen op
  `token` meten zou verschuiven zodra het antwoord pas na de controle wordt uitgegeven.
- **Geen inhoud.** Alleen namen uit de code, tellingen en tijden. Geen veldnaam met "token" erin: die
  zou de redactie in `observability` kunnen raken.

Dezelfde cijfers gaan als **`meting`-event** vlak vóór `done` naar wie meekijkt, plus het verbruik en de
duur per modelaanroep (`aanroepen`). Zonder dat event was een beurt alleen te meten met toegang tot App
Insights: de acceptatie-MCP zag het tokentotaal van de gebruiker, niet wat één beurt kostte of hoeveel er uit
de cache kwam (nulmeting 7 nov 2026). De werkplek negeert het event; de tekst van de beurt verandert niet.
Een stroom die zonder `done` eindigt (fout in de driver, afgebroken) krijgt geen event, wel de logregel.

Wat dit niet ziet: de batchruns van `begrippen_verdieping`. Die hebben een eigen meter en zijn geen
beurt; hun verbruik staat in het journaal van de api.
"""
from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator, Mapping
from typing import Any

from .models import Verbruiksmeter

logger = logging.getLogger("graph_qa.beurt")

_TEKST = frozenset({"reason", "token"})


def route_van(state: Mapping[str, Any]) -> str:
    """De beurtsoort uit de state: de agent en taak, of de specialist die de supervisor koos."""
    taak = state.get("agent_taak") or {}
    if taak.get("agent"):
        return f"{taak['agent']}:{taak.get('taak') or '?'}"
    if state.get("overzicht_route"):
        return "overzicht"
    return str(state.get("specialist") or "")


async def gemeten(
    stroom: AsyncIterator[dict[str, Any]],
    *,
    meter: Verbruiksmeter | None,
    run: Any,
    gesprek_id: str,
    model: str,
) -> AsyncIterator[dict[str, Any]]:
    """Geef de events ongewijzigd door en log aan het eind één `beurt_meting`."""
    begin = time.perf_counter()
    eerste_tekst: float | None = None
    toolaanroepen = 0
    fout = False
    klaar = False
    gelogd = False

    def meting() -> dict[str, Any]:
        verbruik = meter.als_dict() if meter is not None else {}
        if fout:
            uitkomst = "fout"
        elif getattr(run, "stop_gevraagd", False):
            uitkomst = "gestopt"
        else:
            uitkomst = "klaar" if klaar else "afgebroken"
        return {
            "route": (meter.route if meter is not None else "") or "onbekend",
            "uitkomst": uitkomst,
            "duur_ms": round((time.perf_counter() - begin) * 1000),
            "eerste_tekst_ms": None if eerste_tekst is None else round(eerste_tekst * 1000),
            "toolaanroepen": toolaanroepen,
            "modelrondes": verbruik.get("calls", 0),
            "invoer": verbruik.get("invoer", 0),
            "uitvoer": verbruik.get("uitvoer", 0),
            "cache_lees": verbruik.get("cache_lees", 0),
            "cache_schrijf": verbruik.get("cache_schrijf", 0),
            "model": model,
        }

    def log(waarden: dict[str, Any] | None = None) -> None:
        nonlocal gelogd
        if gelogd:
            return
        gelogd = True
        logger.info("beurt_meting", extra={
            "categorie": "functioneel",
            "run_id": getattr(run, "run_id", "") or "",
            "chat_session_id": gesprek_id,
            **(waarden or meting()),
        })

    try:
        async for event in stroom:
            soort = event.get("type")
            if soort in _TEKST:
                if eerste_tekst is None and event.get("content"):
                    eerste_tekst = time.perf_counter() - begin
            elif soort == "tool_execution":
                toolaanroepen += event.get("phase") == "start"
            elif soort == "error":
                fout = True
            elif soort == "done":
                # Vóór het doorgeven: na `done` stopt de lezer, en dan komt een `finally` pas bij het
                # opruimen van de generator. Het event gaat ervoor, want na `done` leest niemand meer.
                klaar = True
                waarden = meting()
                log(waarden)
                yield {"type": "meting", **waarden,
                       "aanroepen": list(meter.aanroepen) if meter is not None else []}
            yield event
    except Exception:
        fout = True
        raise
    finally:
        log()
