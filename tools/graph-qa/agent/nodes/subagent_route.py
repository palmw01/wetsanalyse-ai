"""De route `subagent_route`: een vraag die per uitspraak of per stuk iets samengevat wil, gaat in code naar een subagent
(ADR-016 §A5, meting 14 nov 2026).

S01 en D01 ("vat per uitspraak samen wat de rechter zegt") deed de centrale agent zelf, ook met een scherpere regel in
zijn profiel: 18 keer `get_uitspraak` in 13 rondes, 659k tokens. De vorm ligt vast, dus de code herkent haar (`past`) en
start de subagent zonder modelronde, met de vraag van de jurist als doel: die is de volledige opdracht. Daarna gaat de
beurt naar de centrale agent, met het rapport als gegeven in de context van de beurt (`State.rapporten`, zoals na een
klik op een vraagkaart), en die vat het samen. Heeft de subagent een vraag, dan sluit `finalize_node` af met de kaart.

Alleen voor de centrale agent, en alleen als er een bron naast de wet aanstaat: de stukken komen uit een connector. Kan
de subagent niet starten (er loopt al werk van de gebruiker), dan beantwoordt de centrale agent de vraag zelf.
"""
from __future__ import annotations

import re
from typing import Any

from langgraph.config import get_stream_writer

from .. import subagent as sub
from ..agents.uitvoering import draai
from ..agentvorm import CENTRAAL
from ..models import SubagentOpdracht
from ..narratie import _stap
from ..state import State
from .context import Bouw

#: Het profiel voor stukken uit een bron naast de wet (zoals de instructie van de centrale agent het noemt).
PROFIEL = "algemeen"

_PER_STUK = re.compile(r"\b(?:per|elke|iedere)\s+(?:uitspraak|arrest|vonnis|kamerstuk|stuk|publicatie|bekendmaking)\b",
                       re.I)
_SAMENVATTEN = re.compile(r"\b(?:vat\w*|samen\s*te\s*vatten|samenvat\w*|samenvatting\w*|de\s+kern|op\s+een\s+rij)\b", re.I)


_ARTIKEL = re.compile(r"\bart(?:ikel|\.)\s*\d", re.I)


def past(vraag: str, bronstand: dict[str, Any] | None) -> bool:
    """Vraagt dit om per uitspraak of stuk iets samen te vatten, met een bron naast de wet aan? Een vraag die een artikel
    noemt zonder regeling niet (V01: "artikel 30"): die vraagt eerst welke regeling, en dat doet de centrale agent
    (`id_herkomst`). Een regeling alleen bij afkorting telt hier niet als genoemd: liever de centrale agent dan een gok."""
    from ..binnen_scope import genoemde_regelingen

    if not (vraag and _PER_STUK.search(vraag) and _SAMENVATTEN.search(vraag)):
        return False
    if _ARTIKEL.search(vraag) and not genoemde_regelingen(vraag):
        return False
    return any((s or {}).get("aan") for s in (bronstand or {}).values())


def subagent_route_node(b: Bouw, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    vraag = " ".join((state.get("question") or "").split())
    if b.kinderen is None or not state.get("gesprek_id") or not getattr(b.settings, "legt_zelf_vast", False):
        return {"specialist": CENTRAAL}
    _stap(writer, "Lex", f"zet een subagent ({PROFIEL}) aan het werk op je vraag", route="subagent")
    opdracht = SubagentOpdracht(doel=vraag, oplevering="Per stuk de kern, met de passages die haar dragen.")
    afloop, kind, weigering = draai(
        lambda stuur: sub.voer_uit(state, PROFIEL, opdracht, stuur, settings=b.settings, kinderen=b.kinderen,
                                   gestopt=lambda: bool(b.stop_check and b.stop_check())),
        loop=b.loop, schrijf=writer)
    if weigering:
        return {"specialist": CENTRAAL}
    trace = list(state.get("source_trace") or []) + [tuple(x) for x in kind.get("source_trace") or []]
    rapport = sub.als_toolresultaat(PROFIEL, afloop.uitkomst, sub.rapport_tekst(afloop, kind))
    return {"specialist": CENTRAAL, "source_trace": trace, "subagenten": [afloop.als_dict()],
            "rapporten": ("RAPPORT VAN EEN SUBAGENT (de code gaf hem de vraag van de gebruiker; vat het rapport samen voor "
                          "de gebruiker):\n" + rapport + "\n\n")}
