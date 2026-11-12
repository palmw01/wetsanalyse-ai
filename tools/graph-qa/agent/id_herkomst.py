"""Waar een id in een toolaanroep van het model vandaan komt (iteratie bekendmakingen, ronde 5).

Een id in een aanroep van het model (een BWB-id, een id van een stuk bij een bronconnector, een kamerdossier) moet uit
het gesprek komen: de vraag van de jurist, een eerder toolresultaat, de context die de code meegaf (plan, werkgebied,
aangewezen object, focus). Een BWB-id van een regeling die in de kennisgraaf staat, mag ook: het resultaat noemt haar,
en de controle toetst het id tegen de trace (anders kostte elke graafvraag een zoekronde). Een id uit eigen kennis voert
`tool_execution` niet uit: het model krijgt een `is_error` met wat er ontbreekt, en zoekt eerst (wetgeving_live I20:
`zoek_regelingen {bwb_id: BWBR0002471}`, een id uit het geheugen, 18 rondes gissen in ronde 1).

**Declaratief per parameter, niet per tool.** `ARGUMENTEN` zegt welk soort id een parameter draagt; elke tool met die
parameter valt eronder. Het id-argument van een leestool komt uit de beschrijving van de connector
(`ConnectorBeschrijving.lees_argument`), zodat een nieuwe connector er zonder code onder valt. Code die zelf een tool
aanroept (een workflow, de voorlezing) leidt zijn ids zelf af en valt er niet onder: alleen `tools_node` vraagt de toets.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from bronmodel.connectors import CONNECTORS
from bronmodel.extern import externe_vindplaats

#: Een BWB-id, ook binnen een iri of jci ("urn:bwb:BWBR0004770:artikel:9", "c:BWBR0004770&artikel=9").
_BWB_RE = re.compile(r"BWB[RV]\d{7}", re.IGNORECASE)


@dataclass(frozen=True)
class Soort:
    """Een soort id: hoe het heet in een melding, en waarmee het model het vindt."""
    naam: str
    zoek: str


BWB = Soort("BWB-id", "zoek de regeling eerst op naam of woorden (search_wetgeving of list_regelingen in de kennisgraaf"
                      "{buiten}), en gebruik het id uit het resultaat")
STUK = Soort("id", "zoek het stuk eerst met {zoektools}, en gebruik het id uit het resultaat")
DOSSIER = Soort("dossiernummer", "zoek het dossier eerst met {zoektools} op woorden, en gebruik het nummer uit het "
                                 "resultaat")

#: Per parameter het soort id dat hij draagt, voor elke tool met die parameter.
ARGUMENTEN: dict[str, Soort] = {"bwb_id": BWB, "bron_iri": BWB, "dossier": DOSSIER}

#: Per leestool van een connector het argument met het id van het stuk (uit de beschrijving).
LEESARGUMENTEN: dict[str, str] = {c.leestool: c.lees_argument for c in CONNECTORS.values()}


def id_argumenten(tool: str, args: dict[str, Any]) -> list[tuple[str, Soort, str]]:
    """(parameter, soort, waarde) van elk id in deze aanroep."""
    uit = [(p, s, str(args[p]).strip()) for p, s in ARGUMENTEN.items() if str(args.get(p) or "").strip()]
    if (p := LEESARGUMENTEN.get(tool)) and str(args.get(p) or "").strip():
        uit.append((p, STUK, str(args[p]).strip()))
    return uit


def bekende_tekst(state: dict[str, Any]) -> str:
    """Alles waaruit een id mag komen: de woorden van de jurist, de toolresultaten (deze beurt, het register en de
    berichten), de context die de code meegaf, en eerdere antwoorden (die zijn gecontroleerd). Niet wat het model in
    deze beurt schreef: daar staat het id uit eigen kennis zelf in."""
    from .berichten import beurt_start
    delen: list[str] = [state.get("question", ""), state.get("zelfstandige_vraag", ""), state.get("plan", ""),
                        state.get("werkgebied_context", ""), state.get("onderwerp_context", "")]
    for sleutel in ("focus", "onderwerp", "context", "opgegeven_doel"):
        if state.get(sleutel):
            delen.append(json.dumps(state[sleutel], ensure_ascii=False))
    delen += [t for _, t in state.get("bronregister") or []]
    delen += [t for _, t in state.get("source_trace") or []]
    messages = state.get("messages") or []
    begin = beurt_start(messages, state.get("question", ""))
    for i, m in enumerate(messages):
        inhoud = m.get("content")
        if m.get("role") == "assistant":
            if i < begin:
                delen += [inhoud] if isinstance(inhoud, str) else [b.get("text", "") for b in inhoud or []
                                                                    if isinstance(b, dict) and b.get("type") == "text"]
            continue
        if isinstance(inhoud, str):
            delen.append(inhoud)
            continue
        for b in inhoud or []:
            if isinstance(b, dict) and b.get("type") == "text":
                delen.append(b.get("text", ""))
            elif isinstance(b, dict) and b.get("type") == "tool_result":
                c = b.get("content", "")
                delen.append(c if isinstance(c, str) else json.dumps(c, ensure_ascii=False))
    return "\n".join(d for d in delen if d)


def _staat_in(ident: str, tekst: str) -> bool:
    """Het id als geheel in de tekst, hoofdletterongevoelig: "stb-2010-17" staat niet in "stb-2010-176"; een
    versie erachter ("kst-32740-1-n1") of een iri eromheen wel."""
    return re.search(rf"(?<![0-9a-z]){re.escape(ident)}(?![0-9a-z])", tekst, re.IGNORECASE) is not None


def _bekend_stuk(waarde: str, tekst: str) -> bool:
    vp = externe_vindplaats(waarde)
    if vp is None:
        return True  # geen id-vorm: de tool zegt zelf wat er mis is (`ongeldig_id`)
    if _staat_in(vp.id, tekst) or _staat_in(waarde, tekst):
        return True
    if vp.brontype == "wettekst_live":
        return False  # de BWB-delen toetst `toets` apart
    return any(ident == vp.id for c in CONNECTORS.values() for _, ident in c.geciteerd(tekst))


def toets(tool: str, args: dict[str, Any], state: dict[str, Any], *, graph: Any = None) -> str | None:
    """None als elk id in de aanroep uit het gesprek komt; anders de zin voor het model: welk id, waarom, en hoe het
    wel te vinden is.

    De regel (besluit hoofdsessie, 12 nov 2026), bewust zo smal; maak hem niet breder zonder nieuw besluit:
    - een stuk-id (het id-argument van een leestool) en een dossiernummer moeten uit het gesprek komen, zonder uitzondering;
    - een BWB-id moet uit het gesprek komen, óf de graaf bevestigt de regeling: dan is het gecontroleerd, niet verzonnen;
    - geweigerd wordt dus een BWB-id dat de graaf weerlegt (een geldig leeg antwoord) en niet in het gesprek staat;
    - een graaf die niet of onleesbaar antwoordt, weerlegt niets: dan beslist de tool zelf.
    """
    ids = id_argumenten(tool, args)
    if not ids:
        return None
    tekst = bekende_tekst(state)
    onbekend: list[tuple[str, Soort, str]] = []
    for p, soort, waarde in ids:
        if soort is DOSSIER:
            if not _staat_in(waarde, tekst):
                onbekend.append((p, soort, waarde))
            continue
        if soort is STUK:
            if _bekend_stuk(waarde, tekst):
                continue
            if not _BWB_RE.search(waarde):
                onbekend.append((p, soort, waarde))
                continue
        # Een BWB-id, of een stuk van wetgeving buiten de kennisgraaf (`bwbt:<bwb>:<toestand>:…`): de toestand en de plek
        # zoekt de tool zelf op. Een BWB-id dat niet uit het gesprek komt, mag alleen als de regeling in de kennisgraaf
        # staat: dan noemt het resultaat haar titel en toetst de controle het id tegen de trace. Een id van een regeling
        # buiten de graaf (I20: BWBR0002471 uit het geheugen) weigert de code. Een graaf die niet antwoordt, bewijst niets.
        for bwb in _BWB_RE.findall(waarde):
            if not _staat_in(bwb, tekst) and _niet_in_graaf(graph, bwb.upper()):
                onbekend.append((p, BWB, bwb.upper()))
    if not onbekend:
        return None
    return melding(tool, onbekend, state)


def _niet_in_graaf(graph: Any, bwb_id: str) -> bool:
    """Toont de graaf aan dat deze regeling er niet in staat? Zonder graaf, of bij een onleesbaar antwoord: nee."""
    if graph is None:
        return False
    from .graph.results import parse_select
    from .tools import _q_regeling_bestaat
    try:
        ruw = graph.sparql(_q_regeling_bestaat(bwb_id))
    except Exception:  # noqa: BLE001 – een storing is geen bewijs
        return False
    return not parse_select(ruw) and "?r" in str(ruw or "")


def _zoektools(tool: str) -> str:
    c = next((k for k in CONNECTORS.values() if tool in k.tools), None)
    namen = sorted((c.tools - {c.leestool}) if c else set()) or ["de zoektool van de bron"]
    return " of ".join(namen)


def melding(tool: str, onbekend: Iterable[tuple[str, Soort, str]], state: dict[str, Any]) -> str:
    """"BWBR0002471 (bwb_id) staat niet in de vraag of in een eerder resultaat van dit gesprek. …"."""
    onbekend = list(onbekend)
    buiten = next((k for k in CONNECTORS.values() if k.brontype == "wettekst_live"), None)
    buiten_tekst = (f", of {' of '.join(sorted(buiten.tools - {buiten.leestool}))} buiten de kennisgraaf"
                    if buiten and (state.get("bronnen") is None or buiten.naam in (state.get("bronnen") or [])) else "")
    wat = "; ".join(f"{w} ({p})" for p, _, w in onbekend)
    hoe = {s.zoek.format(buiten=buiten_tekst, zoektools=_zoektools(tool)) for _, s, _ in onbekend}
    eerst = "Een id uit eigen kennis gebruik ik niet"
    return (f"{wat} {'staat' if len(onbekend) == 1 else 'staan'} niet in de vraag of in een eerder resultaat van dit "
            f"gesprek. {eerst}: {'; '.join(sorted(hoe))}.")

