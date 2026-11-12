"""De statusregels die de werkplek live toont: één idioom `Actor · wat er gebeurde`.

Pure functies, bewust los van de nodes die ze aanroepen — zo zijn ze zonder graaf te testen, en
kunnen meerdere node-modules ze delen zonder elkaar te importeren.
"""
from __future__ import annotations

from typing import Any


def _duur(ms: int) -> str:
    """`0,4 s` / `12 s` – Nederlandse notatie, zoals de werkplek hem toont."""
    return f"{ms / 1000:.1f} s".replace(".", ",") if ms < 10_000 else f"{round(ms / 1000)} s"


def _stap(writer: Any, actor: str, bericht: str, duur_ms: int | None = None, route: str = "", bron: str = "") -> None:
    """Meld één stap in de keten: `Actor · wat er gebeurde`.

    Bestaat om het idioom af te dwingen. Zonder deze helper verzint elke node zijn eigen vorm – zo
    stonden er "Opgesplitst in 3 deelvragen." en "Annoteerder · 4 gegrond" naast elkaar, en waren er
    twee verschillende teksten voor dezelfde graafbevraging.

    Met `duur_ms` staat de duur achter de regel (`… (0,4 s)`) én als eigen veld op het event: de
    tekst reist als `denk` mee naar het chatbericht, dus zo blijft de duur na herladen bewaard.

    `route` zegt welke weg de beurt neemt, als eigen veld: de tekst is voor de jurist en mag veranderen, de eval leest
    de route (G2b). Eerst las de eval hem uit de tekst, dus "Supervisor · kiest de duiding-worker" kon niet weg.

    `bron` zegt bij een regel over een opgehaald resultaat welke spoorbron het was (`agent/spoorbronnen.py`), om dezelfde
    reden: de tekst is voor de jurist, het veld voor wie hem leest zonder tekst te ontleden.
    """
    event: dict[str, Any] = {"type": "status", "message": f"{actor} · {bericht}"}
    if route:
        event["route"] = route
    if bron:
        event["bron"] = bron
    if duur_ms is not None:
        event["message"] += f" ({_duur(duur_ms)})"
        event["duur_ms"] = duur_ms
    writer(event)


def met_regelgrens(denk: str, inhoud: str) -> str:
    """`inhoud` van een `reason`-event, met een regelgrens als het denkproces op een statusregel eindigt. De eerste ronde
    draagt geen alinea-scheiding (`ronde_in_denk`), dus plakte "· Lex · zoekt in de kennisgraaf" aan "Ik zoek …"
    (acceptatie 7 nov 2026). `frontend/lib/beurtStroom.ts` doet hetzelfde voor wie meekijkt."""
    laatste = denk.rsplit("\n", 1)[-1]
    return "\n" + inhoud if inhoud and laatste.startswith("· ") and not inhoud.startswith("\n") else inhoud


def ronde_in_denk(writer: Any, tool_uses: list[Any], tekst: list[str], ronde: int,
                  afronden: frozenset[str] | set[str] = frozenset()) -> None:
    """Zet de tekst van een afgelopen modelronde in het denkproces (`reason`), als het narratie is.

    Een ronde zonder tool-aanroepen is een eindantwoord, en dat hoort daar niet: `verify` kan het nog
    afkeuren, en het denkproces staat tijdens de beurt open (besluit 2, 6 nov 2026). Vandaar ná de
    ronde en niet per delta: tijdens het streamen is nog niet bekend welke van de twee het is.

    Een ronde met een tool uit `afronden` (de sjablonen) is óók het antwoord: wat het model ernaast schreef, staat daarna
    in het sjabloon, dus in het denkproces stond het antwoord twee keer (acceptatie 12 nov 2026, K17).

    Op een rondegrens een alinea-scheiding, anders plakt "…tegelijkertijd." aan "De thesaurus…".
    Een ronde zonder tekst geeft niets, dus ook geen loshangende witregel.
    """
    inhoud = "".join(tekst)
    if not tool_uses or not inhoud.strip() or any(_naam(t) in afronden for t in tool_uses):
        return
    writer({"type": "reason", "content": ("\n\n" if ronde > 0 else "") + inhoud})


def _naam(tool_use: Any) -> str:
    return str(tool_use.get("name", "") if isinstance(tool_use, dict) else getattr(tool_use, "name", ""))


#: Wat er in het denkproces staat vóór een statusregel: `· Actor · bericht`.
STATUSTEKEN = "· "


def denk_bij(denk: str, event: dict[str, Any]) -> str:
    """Het denkproces na één event: de enige plek in graph-qa die het opbouwt, voor het bewaarde bericht
    (`beurt.BeurtSchrijver`). Een `status` wordt een eigen regel, een `reason` loopt door (met `met_regelgrens`); elk ander
    event, ook `token`, laat het staan. `frontend/lib/denkproces.ts` (`denkBij`) doet hetzelfde voor wie meekijkt, en
    `tests/poort/denkproces-vectoren.json` houdt de twee gelijk."""
    soort = event.get("type")
    if soort == "status":
        return denk + ("\n" if denk else "") + STATUSTEKEN + str(event.get("message", ""))
    if soort == "reason":
        return denk + met_regelgrens(denk, str(event.get("content", "")))
    return denk


def _toolregel(call: dict[str, Any]) -> str:
    """"leest artikel 9, lid 1 (Invorderingswet 1990)": het werkwoord komt uit het register van spoorbronnen
    (`agent/spoorbronnen.py`), voor de graaf en elke connector langs dezelfde weg."""
    from .spoorbronnen import toolregel
    return toolregel(call)


def _grounding_melding(report: Any) -> str:
    """Wat de brongetrouwheidstoets opleverde – inclusief het geval dat er niets te toetsen viel.

    De controle kijkt naar twee dingen die los van elkaar staan: **vindplaatsen** (BWB-id's en IRI's
    in het antwoord) en **citaten** (tekst tussen aanhalingstekens). De melding hoort te zeggen wat
    er daadwerkelijk is nagelopen.

    Dat ging mis bij een antwoord dat artikelen in gewone taal noemt – "artikel 2 lid 1 onderdeel m"
    zonder BWB-id. Nul vindplaatsen dus, maar wél twee citaten, en die klopten allebei. De tijdlijn
    meldde toen "0 verwijzingen onderbouwd": precies de misleidende regel die de "niets te
    controleren"-tak hierboven had moeten voorkomen, maar die vangt alleen het geval waarin er
    helemaal niets was.
    """
    onbevestigd = getattr(report, "onbevestigd", None)
    if report.niveau == "onbepaald" and onbevestigd:
        return f"brongetrouwheid: {len(onbevestigd)} vermelding(en) niet teruggevonden in wat is opgehaald"
    if report.niveau == "onbepaald":
        return "brongetrouwheid: geen vindplaats of citaat genoemd – niets te controleren"

    delen: list[str] = []
    if report.unsupported:
        delen.append(f"{len(report.unsupported)} verwijzing(en) niet uit de graaf")
    if report.niet_letterlijk:
        delen.append(f"{len(report.niet_letterlijk)} citaat(en) niet letterlijk teruggevonden")
    if delen:
        return "brongetrouwheid: " + ", ".join(delen)

    # Alles klopte. Zeg dan wát er klopte, en tel alleen mee wat er ook echt was.
    aantal_citaten = int(getattr(report, "citaten", 0) or 0)
    goed: list[str] = []
    if report.cited:
        goed.append(f"{len(report.cited)} " + ("verwijzingen" if len(report.cited) > 1 else "verwijzing"))
    if aantal_citaten:
        goed.append(f"{aantal_citaten} " + ("citaten" if aantal_citaten > 1 else "citaat"))
    if not goed:  # een vaste tekst van de code (de bepalingsroute): niets aangehaald, dus ook niets geteld
        return "brongetrouwheid: gecontroleerd, niets aangehaald"
    return f"brongetrouwheid: {' en '.join(goed)} gecontroleerd"


