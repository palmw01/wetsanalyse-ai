"""De vaste route voor een lijstvraag over een bron naast de wet (ADR-013, ADR-010 laag 2), zonder model.

De supervisor zet `bron_lijst` als de code de vraag helemaal kon lezen (`agent/bron_lijst.py`): de zoektool van de
connector met een volgorde, een aantal en de filters uit de vraag. Deze node roept hem één keer aan en vult het blok
`stukken` uit de rijen (`sjablonen/extern.lijsten`); een lege uitkomst is een leemte met de zoekvraag erbij. Daarna
`verify` en `finalize` zoals bij elk sjabloon. Mislukt de aanroep, dan gaat de beurt naar de agent, met het resultaat
in de historie: die zegt wat er misging.

Op acceptatie (gesprek e906567a) kostte "wat is het laatste stuk van dossier 32140" elf modelrondes en gaf twee foute
antwoorden. Hier is het één toolaanroep en nul modelrondes.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from bronmodel.antwoord import Antwoord, Leemte, TelPost, Telling, antwoord_tekst
from bronmodel.connectors import CONNECTORS
from langgraph.config import get_stream_writer

from ..narratie import _stap, _toolregel
from ..sjablonen.extern import MAX_LIJST, leemte_tekst, lijsten
from ..sjablonen.vullen import Onvulbaar
from ..state import State
from ..tool_execution import execute_tool

logger = logging.getLogger(__name__)


def met_peildatum(tool: str, args: dict[str, Any], peildatum: str) -> dict[str, Any]:
    """De peildatum van het werkgebied als argument, als de zoektool er een kent en de vraag een artikel noemt.

    Meting 11 nov 2026 (`rechtspraak-versies-2026-11-11`, vraag 5): in een werkgebied met peildatum 2015 toonde de lijst
    de nieuwste uitspraken bij de tekst van nu, zonder te zeggen dat ze niet bij de peildatum horen. Het model las de
    peildatum uit het contextblok; deze route heeft geen model. Het is een argument, geen filter: de lijst blijft
    dezelfde, elke rij zegt `op_peildatum` en de zoekvraag noemt de peildatum. Zonder artikel geen peildatum: die gaat
    over de tekst van een artikel, en de zoektool weigert hem dan."""
    if not peildatum or "peildatum" in args or not args.get("artikel"):
        return args
    from ..tools import TOOLS
    schema = next((t for t in TOOLS if t["name"] == tool), {})
    if "peildatum" not in ((schema.get("input_schema") or {}).get("properties") or {}):
        return args
    return {**args, "peildatum": peildatum}


def bron_lijst_node(b, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    v = state.get("bron_lijst") or {}
    c = CONNECTORS[v["connector"]]
    tool = {"id": uuid4().hex, "name": v["tool"], "input": met_peildatum(v["tool"], dict(v.get("args") or {}),
                                                                   state.get("werkgebied_peildatum") or "")}
    _stap(writer, "Lex", _toolregel(tool))
    raw = execute_tool(b, state, writer, tool)
    paar = [{"role": "assistant", "content": [{"type": "tool_use", **tool}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool["id"], "content": raw}]}]
    trace = [(tool["name"], raw)]
    try:
        data = json.loads(raw)
    except ValueError:
        data = {}
    if data.get("status") not in ("ok", "partial"):
        # Een fout: de agent krijgt het resultaat en zegt wat er misging, met de tools voor een tweede poging.
        return {"bron_lijst": {}, "messages": paar, "source_trace": [*state.get("source_trace", []), *trace]}
    # Hoogstens wat het blok draagt (`MAX_LIJST`); een langere pagina (een dossier op nummer) toont dan het begin, en
    # "N van de M stukken" zegt dat er meer is. Anders weigerde het blok de lijst en stond er "geen gevonden".
    ids = [r["id"] for r in data.get("resultaten") or []
           if isinstance(r, dict) and isinstance(r.get("id"), str)][:MAX_LIJST]
    try:
        blokken: list[Any] = lijsten(ids, trace) if ids else []
    except Onvulbaar:
        # Er is iets gevonden dat het blok niet draagt: dat is geen "niets gevonden". De agent krijgt het resultaat.
        logger.warning("bron_lijst_onvulbaar", extra={"connector": c.naam, "aantal": len(ids)})
        return {"bron_lijst": {}, "messages": paar, "source_trace": [*state.get("source_trace", []), *trace]}
    if not blokken:
        # De verzamelnaam uit de beschrijving ("bekendmakingen"): "Geen Staatsblad en Staatscourant gevonden" las
        # krom (meting bekendmakingen B14). Zonder volgorde, met de kanttekening van de tool (`leemte_tekst`).
        blokken = [Leemte(tekst=leemte_tekst(c, data))]
    if (gevraagd := int(v.get("gevraagd") or 0)) and blokken and getattr(blokken[0], "soort", "") == "stukken":
        # Begrensd mag, stil niet: "de 100 nieuwste" gaf 25 zonder dat te zeggen (externe review, 10 nov 2026). De
        # slotzin noemt het totaal ("25 van de 874 stukken"); de volgende pagina haalt de agent (`vervolg`).
        getoond = len(blokken[0].items)
        blokken[0] = blokken[0].model_copy(update={"zoekvraag": " ".join(filter(None, [
            blokken[0].zoekvraag, f"Je vroeg om {gevraagd}; per keer toon ik er hoogstens {getoond}. Vraag om de "
            "volgende als je meer wilt zien."]))})
    if v.get("kanttekening") and blokken and getattr(blokken[0], "soort", "") == "stukken":
        blokken[0] = blokken[0].model_copy(update={"zoekvraag": " ".join(filter(None, [blokken[0].zoekvraag,
                                                                                       v["kanttekening"]]))})
    if v.get("tellen") and blokken and getattr(blokken[0], "soort", "") == "stukken":
        blokken[0] = blokken[0].model_copy(update={"telling": telling(c.label, data, v.get("verdeling") or "")})
    antwoord = Antwoord(sjabloon="extern", blokken=blokken)
    uit = antwoord_tekst(antwoord)
    return {
        "answer": uit,
        "antwoord": antwoord.model_dump(),
        "source_trace": [*state.get("source_trace", []), *trace],
        # Het paar plus het antwoord: een vervolgvraag ("lees de eerste") kent de ids en de zoekvraag.
        "messages": [*paar, {"role": "assistant", "content": [{"type": "text", "text": uit}]}],
    }


def _stam(woord: str) -> str:
    """Het woord zonder meervoud, om het naast een telling van de bron te leggen ("instanties" → "instantie")."""
    w = woord.lower()
    for eind in ("ies", "en", "s"):
        if w.endswith(eind) and len(w) - len(eind) >= 4:
            return w[: -len(eind)] + ("ie" if eind == "ies" else "")
    return w


def telling(bron: str, data: dict[str, Any], verdeling: str = "") -> Telling:
    """Het antwoord op een telvraag uit het resultaat van de zoektool, voor elke connector: het `totaal` van de bron (anders
    het aantal rijen van een volledig resultaat, anders ten minste dat), met de `dekking` die de tool zegt. Een verdeling
    komt uit een telling van de bron (`per_<woord>`: `per_instantie`), nooit uit de rijen van één pagina; geeft de bron er
    geen, dan zegt de telling dat."""
    rijen = data.get("resultaten") or []
    totaal = data.get("totaal")
    if isinstance(totaal, int):
        aantal, dekking = totaal, "ten minste" if data.get("dekking") == "ten minste" else "precies"
    else:
        aantal, dekking = len(rijen), "precies" if data.get("volledig") else "ten minste"
    uit = Telling(aantal=aantal, dekking=dekking, bron=bron)
    if not verdeling:
        return uit
    stam = _stam(verdeling)
    sleutel = next((k for k, w in data.items() if k.startswith("per_") and isinstance(w, dict)
                    and _stam(k[4:].replace("_", " ")).startswith(stam[:6])), "")
    if not sleutel:
        return uit.model_copy(update={"zonder_verdeling": f"Een verdeling naar {verdeling} geeft {bron or 'de bron'} "
                                                          "niet, en die tel ik niet zelf uit één pagina."})
    per = [TelPost(waarde=str(w), aantal=n) for w, n in data[sleutel].items() if isinstance(n, int)]
    return uit.model_copy(update={"per_wat": sleutel[4:].replace("_", " "), "per": per})


def route_na_bron_lijst(b, state: State) -> str:
    """Met een antwoord naar de controle; na een fout naar de agent."""
    return "verify" if state.get("antwoord") else "agent"
