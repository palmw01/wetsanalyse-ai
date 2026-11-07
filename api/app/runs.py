"""De statusmachine die de drie runsoorten delen: bronnenruns, begrippenruns en kaartruns.

Een run is `wacht` of `loopt` zolang graph-qa werkt, en eindigt `klaar` (met een uitkomst) of `mislukt`. Een run die
`VERLOPEN` lang niets van zich liet horen, telt als `mislukt` en mag opnieuw. Die regels stonden drie keer in de code
en liepen uiteen: de kaartrun nam een rijslot, de andere twee lazen eerst en schreven daarna, zodat een `loopt` of
`mislukt` een run kon overschrijven die net klaar was (AS-B2). Nu is het één conditionele UPDATE: een klare run
verandert niet meer.
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import Table, update

from . import db

VERLOPEN = timedelta(minutes=5)
LOPEND = ("wacht", "loopt")


def status(row) -> str:
    """De status zoals de client hem ziet: een lopende run zonder teken van leven heet `mislukt`."""
    if row.status in LOPEND and db.utcnow() - db.aware(row.gewijzigd) > VERLOPEN:
        return "mislukt"
    return row.status


async def _zet_als_niet_klaar(tabel: Table, run_id: str, **waarden) -> bool:
    async with db.get_engine().begin() as conn:
        uit = await conn.execute(update(tabel).where(tabel.c.id == run_id, tabel.c.status != "klaar")
                                 .values(gewijzigd=db.utcnow(), **waarden))
    return uit.rowcount > 0


async def zet_loopt(tabel: Table, run_id: str) -> bool:
    """graph-qa begint (of leeft nog): de stilteklok begint opnieuw. Een klare run blijft klaar; dan `False`."""
    return await _zet_als_niet_klaar(tabel, run_id, status="loopt")


async def zet_mislukt(tabel: Table, run_id: str, reden: str) -> None:
    """De run is mislukt, met de reden. Op een klare run 409."""
    if not await _zet_als_niet_klaar(tabel, run_id, status="mislukt", reden=reden[:2000]):
        raise HTTPException(409, "De run is al klaar.")
