"""Graph-qa meldt bij het starten aan de api wat zijn image bevat (ADR-016 §B1).

De api kan graph-qa niet bevragen: hij heeft er geen adres en geen token voor, en graph-qa staat vaak op nul replica's.
Andersom bestaat de weg al. Dus zegt graph-qa bij elke start welke skills en agentprofielen er in zijn image zitten
(het bronpakket, `agent/bronpakket.py`), en leidt de api daaruit af welke versie in de werkplaats actief is.

- **Idempotent.** Eerst gaat alleen de hash van het pakket. Kent de api hem, dan is de melding klaar en is er niets
  geschreven; anders volgt het hele pakket. Twee replica's die tegelijk starten, melden dus hetzelfde.
- **Een feit, geen oordeel.** Graph-qa zegt wat er in zijn image zit, niet of een versie actief is.
- **Nooit in de weg.** De melding loopt als achtergrondtaak: de dienst is gezond zonder haar, en een beurt wacht er
  niet op. Lukt het niet (de api slaapt of wordt net uitgerold), dan probeert hij het later opnieuw en geeft het daarna
  op met een waarschuwing. De api toont dan de stand van de vorige melding, met haar tijdstip.
- **Geen inhoud in de logs**: alleen de hash, de commit en het aantal onderdelen.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from . import bronpakket
from .config import Settings
from .wetsanalyse_api import WetsanalyseApi, WetsanalyseApiFout

logger = logging.getLogger("graph_qa.imagemelding")

#: Wachttijden tussen de pogingen, in seconden. De api staat op nul replica's en kan na een uitrol even weg zijn.
WACHT_S = (5.0, 30.0, 120.0, 600.0)


async def meld(settings: Settings) -> str:
    """Eén melding. Geeft terug wat er gebeurde: `uit` (graph-qa kent de api niet), `werkplaats_uit` (de api kent de
    werkplaats niet), `bekend` (de api had dit pakket al) of `geschreven`. Een andere fout komt als uitzondering."""
    if not settings.legt_zelf_vast:
        return "uit"
    pakket = bronpakket.pakket()
    kop = {"pakket_hash": pakket["sha256"], "revisie": settings.revisie}
    api = WetsanalyseApi(settings, "")
    try:
        antwoord = await api.meld_image(kop)
        if antwoord.get("bekend"):
            return "bekend"
        antwoord = await api.meld_image({**kop, "onderdelen": pakket["onderdelen"]})
        return "geschreven" if antwoord.get("geschreven") else "bekend"
    except WetsanalyseApiFout as fout:
        if fout.status == 404:
            return "werkplaats_uit"
        raise
    finally:
        await api.aclose()


async def meld_met_herhaling(settings: Settings, wacht: tuple[float, ...] = WACHT_S) -> str:
    """De achtergrondtaak van de dienst: meld, en probeer het bij een fout later opnieuw. Gooit nooit."""
    velden = {"categorie": "technisch", "pakket_hash": bronpakket.pakket()["sha256"], "revisie": settings.revisie}
    for poging, pauze in enumerate((*wacht, None), start=1):
        try:
            uitkomst = await meld(settings)
            logger.info("image gemeld", extra={**velden, "uitkomst": uitkomst, "poging": poging})
            return uitkomst
        except (WetsanalyseApiFout, httpx.HTTPError, ValueError) as fout:
            if pauze is None:
                logger.warning("image melden mislukt", extra={**velden, "poging": poging, "fout": type(fout).__name__})
                return "mislukt"
            await asyncio.sleep(pauze)
    return "mislukt"
