"""De statusregels die de werkplek live toont: één idioom `Actor · wat er gebeurde`.

Pure functies, bewust los van de nodes die ze aanroepen — zo zijn ze zonder graaf te testen, en
kunnen meerdere node-modules ze delen zonder elkaar te importeren.
"""
from __future__ import annotations

from typing import Any

from .agent_common import truncate

def _stap(writer: Any, actor: str, bericht: str) -> None:
    """Meld één stap in de keten: `Actor · wat er gebeurde`.

    Bestaat om het idioom af te dwingen. Zonder deze helper verzint elke node zijn eigen vorm – zo
    stonden er "Opgesplitst in 3 deelvragen." en "Annoteerder · 4 gegrond" naast elkaar, en waren er
    twee verschillende teksten voor dezelfde graafbevraging.
    """
    writer({"type": "status", "message": f"{actor} · {bericht}"})


def _toolregel(call: dict[str, Any]) -> str:
    """`get_lid(BWBR0004770, art. 9, lid 1)` – de tool mét waar hij naar kijkt.

    Alleen de tool-naam zei te weinig: bij drie opeenvolgende `get_lid`-aanroepen zag je niet dat het
    om verschillende bepalingen ging.
    """
    inp = call.get("input") or {}
    delen = [str(inp[k]).strip() for k in ("bwb_id", "artikel", "nummer", "lid", "query", "term")
             if str(inp.get(k, "")).strip()]
    return f"{call.get('name', '?')}({', '.join(truncate(d, 60) for d in delen)})" if delen else str(call.get("name", "?"))


def _annoteer_melding(voorstellen: list[Any], verworpen: list[Any]) -> str:
    """Wat de annoteerder opleverde, inclusief wat er sneuvelde en waarom."""
    regel = f"{len(voorstellen) + len(verworpen)} fragmenten, {len(voorstellen)} gegrond"
    if not verworpen:
        return regel
    per_reden: dict[str, int] = {}
    for v in verworpen:
        reden = getattr(v, "reden", "") or "onbekend"
        per_reden[reden] = per_reden.get(reden, 0) + 1
    uitleg = {"niet_letterlijk": "niet letterlijk", "ongeldige_klasse": "ongeldige klasse"}
    details = ", ".join(f"{n}× {uitleg.get(r, r)}" for r, n in per_reden.items())
    return f"{regel} – {len(verworpen)} verworpen ({details})"


def _critic_melding(
    oordelen: dict[str, Any],
    ontbrekend: list[Any],
    nieuw: int | None = None,
    gedempt: int = 0,
) -> str:
    """Tellingen per aandacht-niveau; de oordelen zelf staan al op de reviewkaarten."""
    telling: dict[str, int] = {}
    for o in oordelen.values():
        niveau = getattr(o, "aandacht", "") or "geen oordeel"
        telling[niveau] = telling.get(niveau, 0) + 1
    # Een gedempt oordeel staat als geel op de kaart. Het hier als rood tellen zou de tijdlijn iets
    # anders laten zeggen dan de jurist ziet – precies het soort verschil waarmee je deze keten
    # beoordeelt.
    if gedempt:
        telling["rood"] = max(0, telling.get("rood", 0) - gedempt)
        telling["geel"] = telling.get("geel", 0) + gedempt
        if not telling["rood"]:
            telling.pop("rood", None)
    volgorde = ["rood", "geel", "groen", "geen oordeel"]
    delen = [f"{telling[n]} {n}" for n in volgorde if telling.get(n)]
    regel = ", ".join(delen) if delen else "geen oordelen"
    if gedempt:
        woord = "oordeel" if gedempt == 1 else "oordelen"
        regel += f" · {gedempt} {woord} over een eigen correctie: als twijfel voorgelegd"
    if ontbrekend:
        regel += f" · {len(ontbrekend)} mogelijk gemist"
        # Onderscheid maken tussen "hij ziet iets nieuws" en "hij herhaalt zichzelf" is precies wat
        # je wilt kunnen zien in de tijdlijn.
        if nieuw is not None and nieuw < len(ontbrekend):
            regel += f" ({nieuw} nieuw)" if nieuw else " (niets nieuws)"
    return regel


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
    return f"brongetrouwheid: {' en '.join(goed)} gecontroleerd"


def _herzien_melding(voor: list[dict[str, Any]], na: list[dict[str, Any]]) -> str:
    """Wat de annoteerder met de kritiek deed. Dít is het samenspel: aangepast versus behouden."""
    oud = {v.get("id"): v for v in voor}
    aangepast = sum(
        1 for v in na
        if v.get("id") in oud
        and any(oud[v["id"]].get(k) != v.get(k) for k in ("klasse", "tekst", "lid"))
    )
    ongewijzigd = sum(1 for v in na if v.get("id") in oud) - aangepast
    toegevoegd = sum(1 for v in na if v.get("id") not in oud)
    verdwenen = sum(1 for v in voor if v.get("id") not in {x.get("id") for x in na})
    delen = [f"{aangepast} aangepast", f"{ongewijzigd} ongewijzigd"]
    if toegevoegd:
        delen.append(f"{toegevoegd} toegevoegd")
    if verdwenen:
        delen.append(f"{verdwenen} verwijderd")
    return ", ".join(delen)
