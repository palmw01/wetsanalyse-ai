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

#: Wat er per beurt met de sjablonen gebeurde (ADR-008), voor het `meting`-event en de logregel. Zonder dit stond een
#: weigering of een herhaalverzoek alleen in de logs, en was een meetronde zonder Grafana blind voor de grootste
#: tokenpost (iteratie wetgeving_live ronde 4: I24 en I28 drie schrijfrondes, de reden onzichtbaar).
#: - `gevraagd`: het herhaalverzoek na tekst met een lijst (`nodes/antwoord._lijst_zonder_sjabloon`);
#: - `omgezet`: een lijst in tekst die de code zelf omzette naar het sjabloon, zonder modelronde
#:   (`nodes/antwoord.lijst_omzetten`); `lijst_aangenomen`: een lijst zonder gevonden stuk, of een opbouw, als antwoord;
#: - `tekst_zonder_lijst`: tekst na een vondst van een connector, zonder lijst, als antwoord aangenomen;
#: - `gemist`: een tekstantwoord terwijl er een sjabloon was;
#: - `als_tekst`: een sjabloonaanroep die als tekst kwam en in code is omgezet;
#: - `uitgesteld`: een sjabloon naast een graaftool, gevuld na die tool (`nodes/antwoord.tools_node`);
#: - `tekst_ernaast`: tekens die het model naast een sjabloonaanroep schreef; dat zegt het sjabloon opnieuw, dus het
#:   zijn verspilde tokens (de tekst gaat niet naar het denkproces, `narratie.ronde_in_denk`);
#: - `gevuld` en `geweigerd`: per sjabloon, en per redencode (de functie die `Onvulbaar` gooide).
SJABLOON_TELLERS = ("gevraagd", "omgezet", "lijst_aangenomen", "tekst_zonder_lijst", "gemist", "als_tekst", "uitgesteld",
                    "tekst_ernaast")
SJABLOON_PER = ("gevuld", "geweigerd")


def tel_sjabloon(state: Mapping[str, Any], soort: str, sleutel: str = "", aantal: int = 1) -> dict[str, Any]:
    """De telling van deze beurt met één erbij, als update voor de state (`sjabloon_telling`). Alleen namen uit de
    code, geen inhoud."""
    telling = {k: (dict(v) if isinstance(v, dict) else v) for k, v in (state.get("sjabloon_telling") or {}).items()}
    if soort in SJABLOON_PER:
        per = telling.setdefault(soort, {})
        per[sleutel or "?"] = per.get(sleutel or "?", 0) + aantal
    elif soort in SJABLOON_TELLERS:
        telling[soort] = telling.get(soort, 0) + aantal
    else:
        raise ValueError(f"onbekende sjabloontelling: {soort}")
    return {"sjabloon_telling": telling}


def route_van(state: Mapping[str, Any]) -> str:
    """De beurtsoort uit de state: de agent en taak, of de specialist die de supervisor koos."""
    taak = state.get("agent_taak") or {}
    if taak.get("agent"):
        return f"{taak['agent']}:{taak.get('taak') or '?'}"
    if state.get("overzicht_route"):
        return "overzicht"
    if state.get("afwijzen"):
        # Een eigen statusregel (R3: doorvragen) of de afwijzing zelf; zonder dit stond de route op "onbekend".
        return "verduidelijken" if state.get("afwijs_stap") else "afgewezen"
    return str(state.get("specialist") or "")


async def gemeten(
    stroom: AsyncIterator[dict[str, Any]],
    *,
    meter: Verbruiksmeter | None,
    run: Any,
    gesprek_id: str,
    model: str,
    bronnen: str = "",
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
            "sjabloon": dict(meter.sjabloon) if meter is not None else {},
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
            # De bronconnectors die aanstonden (ADR-013); leeg als de aanroeper ze niet meegaf.
            **({"bronnen": bronnen} if bronnen else {}),
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
            elif soort == "bronstand":
                # De stand van de bronconnectors (ADR-013), met de reden per connector.
                bronnen = ",".join(f"{b['naam']}:{b['reden']}" for b in event.get("bronnen") or [])
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
