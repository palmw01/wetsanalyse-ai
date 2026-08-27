"""Waar gaat deze annotatiebeurt over, en welke tekst hoort erbij.

Het doel (bwbId + artikel + lid) kan uit drie hoeken komen: expliciet meegegeven door de werkplek,
afgeleid uit de tool-calls van de ophaal-agent, of uit de JSON die het model teruggaf. Het corpus
is de letterlijke tekst van die bepaling — gericht opgehaald, met de tool-trace als terugval.

Deze helpers staan apart omdat zowel de supervisie- als de annotatieketen ze nodig heeft.
"""
from __future__ import annotations

import logging
from typing import Any

from .artikel import artikel_corpus
from .graph.results import parse_select
from .ports import GraphPort
from .state import State

logger = logging.getLogger("graph_qa.orchestrator")


def _doel_uit_json(text: str) -> dict[str, str]:
    """Haal het doel ({bwbId,artikel,lid,nummer}) uit de JSON van de ophaal-agent – plat of onder een
    `doel`-sleutel."""
    import json

    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e > s:
        try:
            data = json.loads(text[s : e + 1])
            if isinstance(data, dict):
                d = data.get("doel") if isinstance(data.get("doel"), dict) else data
                return {k: str(d.get(k, "")).strip() for k in ("bwbId", "artikel", "lid", "nummer", "citeertitel")}
        except json.JSONDecodeError:
            pass
    return {"bwbId": "", "artikel": "", "lid": "", "nummer": "", "citeertitel": ""}


def _kandidaten_uit_json(text: str) -> list[dict[str, str]]:
    """Haal de kandidaat-bepalingen uit de JSON van de ophaal-agent.

    Vraagt een jurist om een ONDERWERP ("annoteer alles over aansprakelijkheid van de bestuurder"),
    dan is er geen enkele bepaling aan te wijzen. De ophaal-agent zoekt er dan in de graaf naar en
    levert `{"kandidaten": [...]}` in plaats van een `doel`. Welke daarvan de werkvoorraad in gaan is
    een inhoudelijke keuze van de jurist – dus hier niets raden.
    """
    import json

    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e <= s:
        return []
    try:
        data = json.loads(text[s : e + 1])
    except json.JSONDecodeError:
        return []
    rij = data.get("kandidaten") if isinstance(data, dict) else None
    if not isinstance(rij, list):
        return []

    uit: list[dict[str, str]] = []
    gezien: set[tuple[str, str, str]] = set()
    for k in rij:
        if not isinstance(k, dict):
            continue
        kandidaat = {
            veld: str(k.get(veld, "")).strip()
            for veld in ("bwbId", "artikel", "lid", "citeertitel", "fragment")
        }
        if not (kandidaat["bwbId"] and kandidaat["artikel"]):
            continue
        sleutel = (kandidaat["bwbId"], kandidaat["artikel"], kandidaat["lid"])
        if sleutel in gezien:
            continue
        gezien.add(sleutel)
        uit.append(kandidaat)
    return uit[:8]


# --- meldingen over het samenspel -----------------------------------------------------------------
#
# De annotatieketen doet er 60-90 seconden over en stuurde daarin geen enkel event: de jurist keek
# naar een leeg scherm en zag het heen-en-weer tussen annoteerder en Critic niet. Deze regels vullen
# dat gat. Ze zijn pure functies zodat de bewoording te testen is zonder een hele graaf te draaien.

def _ontbrekend_sleutel(item: dict[str, Any]) -> str:
    """Identiteit van een gemeld gemist element: klasse + het genoemde fragment."""
    return f"{str(item.get('klasse', '')).strip()}|{' '.join(str(item.get('tekst', '')).split()).lower()}"


def _doel_uit_toolcalls(messages: list[dict[str, Any]]) -> dict[str, str]:
    """Gezaghebbend doel = de LAATSTE fetch-tool-call (get_lid/get_artikel/get_bepaling) die de agent
    deed – wat hij écht ophaalde. get_bepaling levert een `nummer` (bv. '9.1' voor een divisie); dat
    zetten we óók als `artikel`, zodat de weergave het aankan. Leeg als er geen fetch-call was."""
    doel = {"bwbId": "", "artikel": "", "lid": "", "nummer": ""}
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for blok in content:
            if not (isinstance(blok, dict) and blok.get("type") == "tool_use"):
                continue
            naam = blok.get("name")
            inp = blok.get("input") or {}
            if naam in ("get_lid", "get_artikel"):
                doel = {
                    "bwbId": str(inp.get("bwb_id", "")).strip(),
                    "artikel": str(inp.get("artikel", "")).strip(),
                    "lid": str(inp.get("lid", "")).strip(),
                    "nummer": "",
                }
            elif naam == "get_bepaling":
                nummer = str(inp.get("nummer", "")).strip()
                doel = {"bwbId": str(inp.get("bwb_id", "")).strip(), "artikel": nummer, "lid": "", "nummer": nummer}
    return doel


def _bepaal_doel(state: State) -> dict[str, str]:
    """Combineer: neem de tool-call als bron (gezaghebbend) en vul lege velden aan uit de JSON.

    Gaf de aanroeper zélf een doel mee, dan wint dat van allebei: dan hoefde er niets gezocht te
    worden en is dit precies de bepaling die de jurist aanwees. De andere twee bronnen blijven als
    aanvulling staan – zo vult een meegegeven `{bwbId, artikel}` zich alsnog met een `citeertitel`
    als die uit de trace komt.
    """
    opgegeven = state.get("opgegeven_doel") or {}
    uit_tool = _doel_uit_toolcalls(state.get("messages", []))
    uit_json = _doel_uit_json(state.get("answer", ""))
    return {
        k: str(opgegeven.get(k, "") or "").strip() or uit_tool.get(k, "") or uit_json.get(k, "")
        for k in ("bwbId", "artikel", "lid", "nummer", "citeertitel")
    }


def _heeft_opgegeven_doel(state: State) -> bool:
    """Kunnen we meteen annoteren? Alleen met bwbId én een aanduiding is het doel compleet."""
    doel = state.get("opgegeven_doel") or {}
    return bool(str(doel.get("bwbId", "")).strip()
                and (str(doel.get("artikel", "")).strip() or str(doel.get("nummer", "")).strip()))


def _corpus_uit_trace(source_trace: list[tuple[str, str]]) -> str:
    """Reconstrueer de opgehaalde artikeltekst uit de get_lid/get_artikel-resultaten in de trace.

    **Terugval, geen eerste keus** – zie `_corpus_voor_doel`. Deze reconstructie plakt álle
    fetch-resultaten van de beurt aaneen, terwijl het doel de láátste fetch-call is: haalde de
    ophaal-agent eerst het hele artikel op en daarna het gevraagde lid, dan zit de tekst van de
    andere leden er ook in – en dan keurt de brongetrouwheidscheck een fragment uit lid 2 goed als
    markering "in lid 1". Bovendien is elk tool-resultaat afgekapt op 8000 tekens (`truncate`),
    dus bij een lange bepaling ontbreekt hier stilzwijgend het staartstuk.
    """
    delen: list[str] = []
    for naam, resultaat in source_trace:
        if naam not in ("get_lid", "get_artikel", "get_bepaling"):
            continue
        for r in parse_select(resultaat):
            tekst = (r.get("lidtekst") or r.get("tekst") or "").strip()
            if tekst:
                delen.append(tekst)
    return "\n\n".join(delen)


def _corpus_voor_doel(doel: dict[str, str], graph: GraphPort, source_trace: list[tuple[str, str]]) -> str:
    """De tekst waarop geannoteerd wordt: precies de bepaling uit `doel`, ongekapt.

    Eén gerichte ophaalactie via `artikel.artikel_corpus` – dezelfde functie waarmee `GET /v1/artikel`
    het documentpaneel vult. Daarmee is er weer één bron voor wat de jurist ziet en waartegen de
    brongetrouwheid wordt gecheckt, zoals `agent/artikel.py` altijd al beloofde.

    Kost één extra SPARQL-call per annotatiebeurt. Dat is de prijs voor een corpus dat niet afhangt
    van hoeveel omwegen de ophaal-agent nam; het resultaat gaat in de state, dus Critic en herziening
    betalen hem niet opnieuw.

    Levert de graaf niets (of kennen we het doel niet), dan valt dit terug op de trace-reconstructie:
    liever de tekst die de agent zag dan helemaal geen corpus – dan zou de hele beurt afbreken.
    """
    bwb = (doel.get("bwbId") or "").strip()
    aanduiding = (doel.get("artikel") or doel.get("nummer") or "").strip()
    if bwb and aanduiding:
        try:
            corpus = artikel_corpus(bwb, aanduiding, graph, (doel.get("lid") or "").strip() or None)
            if corpus.strip():
                return corpus
            logger.info(
                "corpus: graaf gaf niets voor het doel; terugval op de tool-trace",
                extra={"bwb_id": bwb, "aanduiding": aanduiding, "lid": doel.get("lid", "")},
            )
        except Exception:  # noqa: BLE001 – een mislukte ophaal mag de annotatie niet breken
            logger.warning("corpus: gericht ophalen mislukt; terugval op de tool-trace", exc_info=True)
    return _corpus_uit_trace(source_trace)
