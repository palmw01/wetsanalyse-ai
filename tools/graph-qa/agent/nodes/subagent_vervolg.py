"""De node `subagent_vervolg`: een klik op de vraagkaart van een subagent (ADR-016 §A4, §A5), zonder model.

De bevestiging vóór meer subagents (`sa_start`) start ze (`subagent.voer_plan_uit`); daarna zoals hieronder.

De kaart (`subagent.vraagkaart`, `intake_id` `sa-<delegatie>`) stelt de vragen van een subagent één voor één. Een klik:

1. leest de delegatie bij de api. Staat ze niet meer op `wacht`, dan zegt een vaste zin dat de vraag niet meer openstaat;
2. *Laat maar* (`afbreken`) sluit de delegatie af (`gestopt`), en de subagent gaat niet verder;
3. een antwoord komt bij de delegatie (`uitkomst.antwoorden`). Staat er nog een vraag open, dan komt de volgende kaart;
4. na de laatste vraag hervat de code de subagent in zijn deelgesprek (`subagent.hervat`), met de antwoorden van de jurist.
   Heeft hij daarna weer een vraag, dan komt die als kaart. Anders gaat de beurt naar de centrale agent, met het rapport
   als gegeven in de context van de beurt (`State.rapporten`), en schrijft die de bundel. Zijn toolresultaten gaan in de
   trace, zodat `verify` de samenvatting ertegen toetst.

De volgorde en de antwoorden staan bij de api, niet in het gesprek: herladen of een tussenvraag breekt niets.
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.config import get_stream_writer

from .. import subagent as sub
from ..agents.uitvoering import draai
from ..agentvorm import CENTRAAL
from ..narratie import _stap
from ..state import State
from ..wetsanalyse_api import WetsanalyseApiFout
from .context import Bouw, met_api

logger = logging.getLogger("graph_qa.subagent")

PREFIX = "sa-"
GESTOPT = "Dan laat ik deze vraag rusten; de subagent gaat niet verder. Wat hij al vond, staat in zijn deelgesprek."
VOLGENDE = "Dank je. De subagent heeft nog een vraag."
NIET_GESTART = "Dan begin ik er niet aan; er is niets gestart."
STORING = "Dat lukte nu niet: de wetsanalyse-api haperde. Probeer het zo opnieuw; je antwoord is niet verloren gegaan."


def delegatie_van(state: State) -> str:
    return str((state.get("intake_actie") or {}).get("intake_id", "")).removeprefix(PREFIX)


def _antwoord(actie: dict[str, Any]) -> str:
    """Het antwoord van de jurist: de gekozen optie en wat hij typte."""
    delen = [*(actie.get("keuzes") or []), actie.get("tekst") or "", *(actie.get("teksten") or [])]
    return "; ".join(d for x in delen if (d := " ".join(str(x).split())))


async def _verwerk(b: Bouw, state: State, stuur) -> dict[str, Any]:
    actie = state.get("intake_actie") or {}
    delegatie_id = delegatie_van(state)
    async with met_api(b, state.get("user_id", "")) as api:
        try:
            delegatie = await api.haal_delegatie(delegatie_id)
        except WetsanalyseApiFout:
            return {"tekst": sub.AL_BEANTWOORD}
        kinderen = list((delegatie.get("uitkomst") or {}).get("kinderen") or [])
        if delegatie.get("soort") == "subagent" and delegatie.get("status") == "wacht" and not kinderen:
            # De bevestiging vóór meer subagents (ADR-016 §A5): nog niets gestart.
            if actie.get("actie") == "afbreken":
                await api.wijzig_delegatie(delegatie_id, {"status": "gestopt", "uitkomst": {"door": "gebruiker"}})
                return {"tekst": NIET_GESTART}
            paren, weigering = await sub.voer_plan_uit(
                state, delegatie_id, stuur, settings=b.settings, kinderen=b.kinderen, api=api,
                gestopt=lambda: bool(b.stop_check and b.stop_check()))
            if weigering:
                return {"tekst": weigering}
            j = sub.eerste_vraag([a.als_dict() for a, _ in paren])
            if j is not None:
                return {"paren": paren, "kaart": sub.vraagkaart(delegatie_id, paren[j][0].vragen, 1)}
            return {"paren": paren}
        i = sub.eerste_vraag(kinderen)
        if delegatie.get("soort") != "subagent" or delegatie.get("status") != "wacht" or i is None:
            return {"tekst": sub.AL_BEANTWOORD}
        if actie.get("actie") == "afbreken":
            await api.wijzig_delegatie(delegatie_id, {"status": "gestopt", "uitkomst": {"kinderen": kinderen,
                                                                                         "door": "gebruiker"}})
            return {"tekst": GESTOPT}
        vragen = list(kinderen[i].get("vragen") or [])
        antwoorden = [*(kinderen[i].get("antwoorden") or []),
                      _antwoord(actie) if actie.get("actie") != "overslaan" else "(geen antwoord)"]
        if len(antwoorden) < len(vragen):
            kinderen[i] = {**kinderen[i], "antwoorden": antwoorden}
            await api.wijzig_delegatie(delegatie_id, {"status": "wacht", "uitkomst": {"kinderen": kinderen}})
            return {"tekst": VOLGENDE, "kaart": sub.vraagkaart(delegatie_id, vragen, len(antwoorden) + 1)}
        afloop, kind, weigering = await sub.hervat(
            state, delegatie_id, antwoorden, stuur, settings=b.settings, kinderen=b.kinderen, api=api,
            van="van de gebruiker", gestopt=lambda: bool(b.stop_check and b.stop_check()))
        if weigering:
            return {"tekst": weigering}
        # Wacht er nog een kind (dit kind met een nieuwe vraag, of een ander), dan de kaart voor de eerste.
        na = list(((await api.haal_delegatie(delegatie_id)).get("uitkomst") or {}).get("kinderen") or [])
        j = sub.eerste_vraag(na)
        kaart = sub.vraagkaart(delegatie_id, na[j]["vragen"], 1) if j is not None else None
        return {"paren": [(afloop, kind)], "kaart": kaart}


def subagent_vervolg_node(b: Bouw, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    _stap(writer, "Lex", "geeft je antwoord aan de subagent", route="subagent")
    if b.kinderen is None or not b.settings.legt_zelf_vast:
        uit: dict[str, Any] = {"tekst": "Een subagent kan hier niet verder. Stel je vraag opnieuw."}
    else:
        try:
            uit = draai(lambda stuur: _verwerk(b, state, stuur), loop=b.loop, schrijf=writer)
        except WetsanalyseApiFout:
            logger.warning("subagent_vervolg: api-fout", extra={"categorie": "technisch"})
            uit = {"tekst": STORING}
    paren = uit.get("paren")
    if paren:
        if uit.get("kaart"):
            uit = {"tekst": VOLGENDE, "kaart": uit["kaart"]}
        else:
            # Klaar of niet gelukt: de centrale agent schrijft de bundel met de rapporten als gegeven. Hun toolresultaten
            # gaan in de trace, zodat `verify` de samenvatting ertegen toetst.
            trace = list(state.get("source_trace") or [])
            for _a, kind in paren:
                trace += [tuple(x) for x in kind.get("source_trace") or []]
            return {"specialist": CENTRAAL, "source_trace": trace, "subagenten": [a.als_dict() for a, _ in paren],
                    "rapporten": ("RAPPORTEN VAN DE SUBAGENTS (de gebruiker bevestigde het plan of beantwoordde hun "
                                  "vragen; vat ze samen voor de gebruiker):\n" + sub.bundel_rapporten(paren) + "\n\n")}
    tekst = uit.get("tekst") or sub.AL_BEANTWOORD
    writer({"type": "token", "content": tekst})
    if uit.get("kaart"):
        writer({"type": "vraagkaart", "vraagkaart": uit["kaart"]})
    return {"answer": tekst, "messages": [{"role": "assistant", "content": tekst}]}


def route_na_vervolg(_b: Bouw, state: State) -> str:
    """Met een rapport schrijft de centrale agent de bundel; anders is de beurt klaar (een kaart of een vaste zin)."""
    return "agent" if state.get("rapporten") else "einde"
