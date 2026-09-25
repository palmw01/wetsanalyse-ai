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


