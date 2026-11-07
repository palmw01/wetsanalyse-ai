"""Het budget en het verbruik buiten een gewone beurt (H5, bevinding M-03).

Een gewone beurt boekt zijn verbruik in de beurt-driver (`beurt._boek_verbruik`) en de api controleert het budget bij
`POST /v1/runs`. Wat daarbuiten een model aanroept – een reeks of werkgebied-run tussen twee onderdelen, de kaartacties en
de verdieping van de begrippen – had zijn eigen kopie, met een privénaam uit een andere module. Hier staan ze één keer.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger("graph_qa.verbruik")


def budget_poort(settings: Any, user_id: str) -> Callable[[], Awaitable[bool]]:
    """Dezelfde poort als vóór een run (`api/main._budget_check`), maar dan vóór elk volgend onderdeel. Fail-open, net als
    daar: een haperende boekhouding legt het werk niet stil."""
    from .wetsanalyse_api import WetsanalyseApi

    async def toegestaan() -> bool:
        api = WetsanalyseApi(settings, user_id)
        try:
            ok, _stand = await api.budget_toegestaan()
            return bool(ok)
        except Exception:  # noqa: BLE001
            logger.warning("budget niet te controleren", exc_info=True)
            return True
        finally:
            await api.aclose()
    return toegestaan


async def boek(api: Any, llm: Any, model: str, gesprek_id: str, run_id: str) -> int:
    """Boek wat de meter van `llm` telde (best-effort, idempotent op `run_id`); geeft het totaal. Zonder meter of zonder
    verbruik: niets boeken, 0."""
    meter = getattr(llm, "meter", None)
    if meter is None or meter.totaal <= 0:
        return 0
    try:
        await api.boek_verbruik(meter.als_dict(), model=model, gesprek_id=gesprek_id, run_id=run_id)
    except Exception:  # noqa: BLE001 – boekhouding mag het werk niet laten mislukken
        logger.warning("verbruik niet geboekt", extra={"run_id": run_id}, exc_info=True)
    return meter.totaal
