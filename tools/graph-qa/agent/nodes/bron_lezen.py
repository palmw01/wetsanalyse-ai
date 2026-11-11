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
import re
from typing import Any
from uuid import uuid4

from bronmodel.antwoord import Antwoord, Leemte, antwoord_tekst
from bronmodel.connectors import CONNECTORS, van_id
from langgraph.config import get_stream_writer

from ..narratie import _stap, _toolregel
from ..sjablonen.extern import lijsten
from ..spoorbronnen import bron_van, voorleesregel
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
        eerste = tool
        lezer = _Voorlezer(writer)
        raw = execute_tool(b, state, lezer, tool)
        if "artikel" in tool["input"] and _leeg(raw):
            # Het genoemde artikel staat in geen wijzigingsonderdeel ("wat staat er in Stb. 2010, 176 over artikel 36"
            # noemt het in de toelichting): dan het hele stuk, zodat de agent geen extra ronde nodig heeft.
            tool = {**tool, "id": uuid4().hex, "input": {k: v for k, v in tool["input"].items() if k != "artikel"}}
            raw = execute_tool(b, state, lezer, tool)
        gebruik.append({"type": "tool_use", **tool})
        resultaten.append({"type": "tool_result", "tool_use_id": tool["id"], "content": raw})
        trace.append((tool["name"], raw))
        if tool["name"] in HEEL_LEZEN or _kort(tool, raw):
            # Een artikel is één geheel, en een kort stuk ook: alle pagina's in code, anders bladerde het model zelf, één
            # ronde per pagina (meting 11 nov 2026, W15: drie aanroepen en 131k tokens voor artikel 31 van de
            # Participatiewet; iteratie bekendmakingen ronde 2, B21: zes rondes voor een stuk van 100 alinea's).
            for _ in range(MAX_PAGINAS - 1):
                if not (vervolg := _vervolg(raw, tool["name"])):
                    break
                tool = {"id": uuid4().hex, "name": vervolg["tool"], "input": dict(vervolg.get("args") or {})}
                raw = execute_tool(b, state, lezer, tool)
                gebruik.append({"type": "tool_use", **tool})
                resultaten.append({"type": "tool_result", "tool_use_id": tool["id"], "content": raw})
                trace.append((tool["name"], raw))
                lezer.paginas += 1
        lezer.klaar(eerste, volledig=_vervolg(raw, tool["name"]) is None)
    if not gebruik:
        return {"bron_lezen": []}
    paar = [{"role": "assistant", "content": gebruik}, {"role": "user", "content": resultaten}]
    if (zonder := _zonder_tekst(resultaten, trace, gebruik)) is not None:
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


class _Voorlezer:
    """De writer tijdens het lezen van één genoemd stuk. Hij houdt de regels over wat de bron opleverde vast (de status
    met een `bron`), en laat al het andere door, ook de `tool_execution`-events. Las de code zelf meer pagina's, dan
    wordt het één regel (`spoorbronnen.voorleesregel`) in plaats van "deels gelezen" per pagina; anders, of als een
    pagina een fout gaf, komen de vastgehouden regels zoals ze waren."""

    def __init__(self, writer: Any) -> None:
        self.writer, self.regels, self.paginas, self.fout = writer, [], 1, False

    def __call__(self, event: dict[str, Any]) -> None:
        if event.get("type") == "status" and event.get("bron"):
            self.regels.append(event)
            return
        if event.get("type") == "tool_execution" and event.get("phase") == "end" and event.get("status") not in ("ok", "partial"):
            self.fout = True
        self.writer(event)

    def klaar(self, tool: dict[str, Any], *, volledig: bool) -> None:
        if self.paginas == 1 or self.fout:
            for event in self.regels:
                self.writer(event)
            return
        bron = bron_van(tool["name"])
        _stap(self.writer, bron.label if bron else "Kennisgraaf",
              voorleesregel(tool["name"], tool["input"], self.paginas, volledig), bron=bron.naam if bron else "")


#: De leestools waarvan de code altijd alle pagina's leest: een wettekst van overheid.nl is per artikel begrensd.
HEEL_LEZEN = frozenset({"get_wettekst"})
#: Zoveel pagina's hoogstens (gelijk aan de bepalingsworkflow), ook voor een kort stuk.
MAX_PAGINAS = 8
#: Een stuk van hoogstens zoveel rijen (het `totaal` van de eerste pagina) leest de code helemaal voor, bij elke leestool
#: van een connector. Een langer stuk (een verzamelwet, een memorie van toelichting) blijft bij de eerste pagina met de
#: `inhoud`: daar springt het model gericht, en alles voorlezen zou elke volgende ronde duurder maken.
MAX_RIJEN_KORT = 150
#: De argumenten die een lezing filteren of verplaatsen: dan leest de code niet verder, het resultaat is al gericht.
_GERICHT = frozenset({"artikel", "regeling", "tabel", "inhoud", "offset"})


def _kort(tool: dict[str, Any], raw: str) -> bool:
    """Of de code een genoemd stuk helemaal voorleest: een leestool van een connector, ongefilterd, met een vervolg, en
    met hoogstens `MAX_RIJEN_KORT` rijen in het hele stuk."""
    if tool["name"] not in {c.leestool for c in CONNECTORS.values()} or _GERICHT & set(tool.get("input") or {}):
        return False
    try:
        data = json.loads(raw)
    except ValueError:
        return False
    totaal = data.get("totaal") if isinstance(data, dict) else None
    return (isinstance(data, dict) and data.get("status") == "ok" and isinstance(data.get("vervolg"), dict)
            and isinstance(totaal, int) and totaal <= MAX_RIJEN_KORT)


def _vervolg(raw: str, tool: str) -> dict[str, Any] | None:
    """De aanroep voor de volgende pagina van een geslaagde lezing met dezelfde tool, of None."""
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    vervolg = data.get("vervolg") if isinstance(data, dict) and data.get("status") in ("ok", "partial") else None
    return vervolg if isinstance(vervolg, dict) and vervolg.get("tool") == tool else None


def _leeg(raw: str) -> bool:
    """Een geslaagde lezing zonder rijen."""
    try:
        data = json.loads(raw)
    except ValueError:
        return False
    return isinstance(data, dict) and data.get("status") == "ok" and not data.get("resultaten")


def _zonder_tekst(resultaten: list[dict[str, Any]], trace: list[tuple[str, str]],
                 gebruik: list[dict[str, Any]] | None = None) -> Antwoord | None:
    """Is geen enkel genoemd stuk te lezen, dan zegt de code dat, zonder model: geen eigen duiding ("dus een
    verkeersboete") en geen systeemtaal (nameting 10 nov 2026). Voor elke connector dezelfde drie gevallen:

    - geen tekst bij de bron (een uitspraak met alleen metadata, `leesbaar: false`);
    - alleen een PDF (`alleen_pdf`, met het `stuk` en zijn metadata: het bestaat);
    - niet gevonden (`niet_gevonden`): het id staat in de melding, en er komt geen stuk in de lijst.

    Een stuk dat wel te lezen is staat als lijst met zijn gegevens uit de bron en de link (ronde 1 Kamerstukken, 11 nov
    2026: K12 en K27 gingen langs het model). None als er iets te lezen is, of bij een andere fout: dan formuleert de
    agent."""
    zonder: list[str] = []
    pdf: list[str] = []
    weg: list[str] = []
    for i, r in enumerate(resultaten):
        try:
            data = json.loads(r.get("content") or "")
        except (TypeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        stuk = data.get("stuk") if isinstance(data.get("stuk"), dict) else None
        ident = stuk.get("id") if stuk is not None and isinstance(stuk.get("id"), str) else None
        if data.get("status") == "ok" and not data.get("resultaten") and not data.get("vervolg") and ident:
            zonder.append(ident)
        elif data.get("status") == "error" and data.get("reden") == "alleen_pdf" and ident:
            pdf.append(ident)
        elif data.get("status") == "error" and data.get("reden") == "niet_gevonden" and (genoemd := _genoemd(gebruik, i)):
            weg.append(genoemd)
        else:
            return None
    ids = [*zonder, *pdf]
    try:
        stukken = lijsten(ids, trace)
    except Onvulbaar:
        return None
    for s in stukken:
        c = van_id(next((st.id for st in s.items), "")) if s.items else None
        s.kop = c.kop_in_antwoord if c is not None else s.kop
    blokken: list[Any] = []
    if zonder:
        blokken.append(Leemte(tekst=f"De tekst van {'dit stuk' if len(zonder) == 1 else 'deze stukken'} staat niet bij "
                                    "de bron: er is alleen de beschrijving hieronder. Lees de tekst via de link."))
    if pdf:
        c = van_id(pdf[0])
        hoe = f" ({extra})" if c is not None and (extra := _wat_nieuw(c.zonder_tekst, "alleen als PDF")) else ""
        blokken.append(Leemte(tekst=f"{'Dit stuk staat' if len(pdf) == 1 else 'Deze stukken staan'} bij de bron alleen "
                                    f"als PDF{hoe}: de tekst kan ik niet lezen of citeren. De beschrijving staat hieronder; "
                                    "lees het stuk via de link."))
    for ident in weg:
        c = van_id(ident)
        bij = f" bij {c.label}" if c is not None else ""
        blokken.append(Leemte(tekst=f"{ident} is{bij} niet gevonden. Controleer het id, of vraag mij naar de stukken "
                                    "waar het bij hoort; zonder tekst zeg ik er niets over."))
    return Antwoord(sjabloon="extern", blokken=[*blokken, *stukken])


def _wat_nieuw(toevoeging: str, zin: str) -> str:
    """Wat `toevoeging` zegt naast `zin`: de delen (tussen komma's) met een woord dat er nog niet in staat. "alleen als
    PDF" achter "alleen als PDF" gaf "alleen als PDF (alleen als PDF)" (Staatsblad ronde 3, B07); bij Kamerstukken
    blijft van "onopgemaakt, alleen PDF" alleen "onopgemaakt" over."""
    al = {w.lower() for w in re.findall(r"\w+", zin)}
    delen = [d.strip() for d in toevoeging.split(",") if d.strip()]
    return ", ".join(d for d in delen if {w.lower() for w in re.findall(r"\w+", d)} - al)


def _genoemd(gebruik: list[dict[str, Any]] | None, i: int) -> str:
    """Het id dat de i-de leesaanroep vroeg (het `lees_argument` van zijn connector), of leeg."""
    if not gebruik or i >= len(gebruik):
        return ""
    invoer = gebruik[i].get("input") or {}
    for c in CONNECTORS.values():
        if c.leestool == gebruik[i].get("name"):
            return str(invoer.get(c.lees_argument) or "").strip()
    return ""


def route_na_bron_lezen(b, state: State) -> str:
    """Met een antwoord uit code (een stuk zonder tekst) naar de controle; anders formuleert de agent."""
    return "verify" if state.get("antwoord") else "agent"
