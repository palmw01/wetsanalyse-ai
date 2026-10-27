"""De bronselectie-worker (spoor J): één stap van de bronselectie per deelvraag.

De logica staat in `agent/bronselectie.py` en draait op de event loop van de beurt (de api-client is async),
zoals de agents. De stand komt bij elke beurt vers van de api; deze node bewaart niets in de state. Zoeken is
de bronnenrun van de deelvragen-agent (`bronnen_run.bronnen_kern`, zonder model).

Uit gaan een `token` (de zin van Lex), een `vraagkaart` (het kaartje, ook na herladen te beantwoorden) en een
`artefact` `{soort: "bronselectie", ref: {werkgebied_id, deelvraag_id?}}`: het paneel naast het gesprek.
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.config import get_stream_writer

from .. import bronselectie as bs
from ..agents import Context
from ..agents.uitvoering import draai
from ..narratie import _stap
from ..state import State
from .agent_taak import STORING, ZONDER_API, _maak_api

logger = logging.getLogger("graph_qa.bronselectie")

ZONDER_WERKGEBIED = ("De bronselectie hoort bij een werkgebied. Open het gesprek vanuit het werkgebied, of stel er "
                     "eerst een samen.")
CONFLICT = "Iemand anders werkte intussen aan deze deelvraag; hieronder de stand van nu."


def bronselectie_node(b, state: State) -> dict[str, Any]:
    from ..wetsanalyse_api import WetsanalyseApiFout

    writer = get_stream_writer()
    actie = dict(state.get("intake_actie") or {})
    wid = bs.werkgebied_van(actie["intake_id"]) if actie.get("intake_id") else state.get("werkgebied_id", "")
    if not wid:
        return _zeg(writer, ZONDER_WERKGEBIED)
    if not b.settings.legt_zelf_vast:
        return _zeg(writer, ZONDER_API)
    onderwerp = state.get("onderwerp") or {}
    aangewezen = onderwerp.get("id", "") if onderwerp.get("soort") == "deelvraag" else ""

    async def stap(stuur) -> dict[str, Any]:
        api = _maak_api(b, state.get("user_id", ""))
        ctx = Context(api=api, settings=b.settings, user_id=state.get("user_id", ""), run_id=state.get("run_id", ""),
                      gesprek_id=state.get("gesprek_id", ""), graph=b.graph, llm=b.llm,
                      melding=lambda bericht: _stap(stuur, "Lex", bericht),
                      gestopt=lambda: bool(b.stop_check and b.stop_check()))

        async def zoek(deelvraag_id: str) -> str:
            from ..bronnen_run import bronnen_kern
            _stap(stuur, "Lex", "zoekt bepalingen bij het werkgebied en zijn deelvragen")
            uit = await bronnen_kern(ctx, wid, "" if deelvraag_id == bs.ANALYSEVRAAG else deelvraag_id)
            return "" if uit.status == "ok" else (uit.reden or "het zoeken lukte niet")

        try:
            if actie:
                return await bs.verwerk(api, actie, zoek)
            return await bs.start(api, wid, zoek, vraag=state.get("question", ""), deelvraag_id=aangewezen)
        except WetsanalyseApiFout as fout:
            if fout.status == 412:
                uit = await bs.start(api, wid, None)
                return {**uit, "zinnen": [CONFLICT]}
            if fout.status == 404:
                return {"zinnen": ["Dit werkgebied bestaat niet (meer)."]}
            raise
        finally:
            if (aclose := getattr(api, "aclose", None)) is not None:
                await aclose()

    try:
        uit = draai(stap, loop=b.loop, schrijf=writer)
    except Exception:  # noqa: BLE001 – een storing is een zin in het gesprek, de oorzaak staat in het log
        logger.exception("bronselectie mislukt", extra={"categorie": "technisch"})
        return _zeg(writer, STORING)
    tekst = " ".join(z for z in uit.get("zinnen") or [] if z).strip()
    kaart = uit.get("kaart")
    writer({"type": "token", "content": tekst})
    if kaart:
        writer({"type": "vraagkaart", "vraagkaart": kaart})
    did = uit.get("deelvraag") or (kaart or {}).get("deelvraag_id") or ""
    writer({"type": "artefact", "artefact": {"soort": "bronselectie", "titel": "Bronselectie",
                                             "ref": {"werkgebied_id": wid, **({"deelvraag_id": did} if did else {})}}})
    inhoud = tekst + (f"\n\n[Vraag: {kaart['vraag']}]" if kaart else "")
    return {"answer": tekst, "messages": [{"role": "assistant", "content": inhoud.strip()}]}


def _zeg(writer, tekst: str) -> dict[str, Any]:
    writer({"type": "token", "content": tekst})
    return {"answer": tekst, "messages": [{"role": "assistant", "content": tekst}]}
