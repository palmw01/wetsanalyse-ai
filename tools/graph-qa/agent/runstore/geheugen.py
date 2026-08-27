"""De runs in het geheugen van dit proces — het oorspronkelijke gedrag.

De default zonder database: lokaal draaien en de testsuite. Op één replica is dit precies goed en
een stuk sneller dan een store die per event naar Postgres schrijft. Draaien er meer replica's, dan
is `PostgresStore` de juiste keuze — deze store ziet de runs van een ander proces niet.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from . import BEWAAR_NA_AFLOOP_S, MAX_EVENTS, VLUCHTIGE_TYPES, Run, RunBestaatAl

logger = logging.getLogger("graph_qa.runs")


class GeheugenStore:
    """Houdt de lopende en recent afgeronde runs bij, één per gesprek. In dit proces."""

    def __init__(self, *, max_events: int = MAX_EVENTS, bewaar_s: float = BEWAAR_NA_AFLOOP_S) -> None:
        self._runs: dict[str, Run] = {}
        self._max_events = max_events
        self._bewaar_s = bewaar_s

    # -- opvragen ------------------------------------------------------------------------------

    async def get(self, run_id: str, *, user_id: str | None = None) -> Run | None:
        """De run, of niets als hij niet van deze gebruiker is.

        `user_id=None` slaat de controle over – alleen voor intern gebruik, nooit vanaf een
        request. Een run van iemand anders levert `None` en dus een 404: precies zoals de api
        andermans document behandelt, zodat het bestaan niet lekt.
        """
        self._ruim_op()
        run = self._runs.get(run_id)
        if run is None:
            return None
        if user_id is not None and run.user_id != user_id:
            return None
        return run

    async def actief_voor(self, conversation_id: str, *, user_id: str | None = None) -> Run | None:
        """De lopende run van dit gesprek, of de laatst afgeronde die nog binnen de bewaartermijn
        valt – beide zijn een geldige reden om aan te haken."""
        self._ruim_op()
        kandidaten = [
            r for r in self._runs.values()
            if r.conversation_id == conversation_id and (user_id is None or r.user_id == user_id)
        ]
        if not kandidaten:
            return None
        # Een lopende run wint altijd van een afgeronde; anders de meest recente.
        lopend = [r for r in kandidaten if r.loopt]
        return sorted(lopend or kandidaten, key=lambda r: r.gestart)[-1]

    # -- starten -------------------------------------------------------------------------------

    async def start(
        self,
        *,
        conversation_id: str,
        vraag: str,
        maak_stroom: Callable[[Run], AsyncIterator[dict[str, Any]]],
        user_id: str = "",
    ) -> Run:
        """Registreer een run en zet hem als achtergrondtaak weg.

        `maak_stroom` krijgt de Run mee zodat de driver een stopverzoek kan zien; hij levert de
        eventstroom (in de praktijk `answer_stream`). De taak hangt bewust **niet** aan de
        request-scope: dat is de hele omkering.
        """
        self._ruim_op()
        if conversation_id:
            # Bewust ZONDER user-filter: twee beurten op één thread_id schrijven door elkaar in de
            # checkpointer, ongeacht wie ze start. De bescherming geldt de data, niet de gebruiker.
            bestaand = await self.actief_voor(conversation_id)
            if bestaand is not None and bestaand.loopt:
                raise RunBestaatAl(bestaand.run_id)

        run = Run(run_id=uuid.uuid4().hex, conversation_id=conversation_id,
                  user_id=user_id, vraag=vraag)
        self._runs[run.run_id] = run
        run.taak = asyncio.create_task(self._draai(run, maak_stroom))
        return run

    async def _draai(self, run: Run, maak_stroom: Callable[[Run], AsyncIterator[dict[str, Any]]]) -> None:
        try:
            async for event in maak_stroom(run):
                await self._voeg_toe(run, event)
            nieuwe_status = "gestopt" if run.stop_gevraagd else "klaar"
        except asyncio.CancelledError:
            await self._rond_af(run, "gestopt")
            raise
        except Exception:
            # De stroom zelf saniteert zijn fouten al naar een `error`-event; komt er tóch een
            # exception doorheen, dan is dat een defect in de driver en hoort het in het log.
            logger.exception("run mislukt", extra={"categorie": "technisch", "run_id": run.run_id})
            await self._voeg_toe(run, {
                "type": "error",
                "message": "Er ging iets mis bij het beantwoorden. Probeer het opnieuw.",
            })
            nieuwe_status = "mislukt"
        await self._rond_af(run, nieuwe_status)

    async def _rond_af(self, run: Run, status: str) -> None:
        run.status = status
        run.eind_op = time.monotonic()
        async with run._wakker:
            run._wakker.notify_all()

    async def _voeg_toe(self, run: Run, event: dict[str, Any]) -> None:
        run.events.append({**event, "seq": run.geproduceerd})
        run.geproduceerd += 1
        self._cap(run)
        async with run._wakker:
            run._wakker.notify_all()

    def _cap(self, run: Run) -> None:
        """Snoei de log als hij te lang wordt – maar gooi alleen narratie weg.

        Een generieke ringbuffer zou bij een lange beurt precies het begin van het antwoord
        opeten, en dan ziet een late aanhaker een tekst die klopt noch compleet is.
        """
        if len(run.events) <= self._max_events:
            return
        teveel = len(run.events) - self._max_events
        behouden: list[dict[str, Any]] = []
        gedropt = 0
        for event in run.events:
            if gedropt < teveel and event.get("type") in VLUCHTIGE_TYPES:
                gedropt += 1
                continue
            behouden.append(event)
        run.events = behouden
        run.weggevallen += gedropt

    # -- stoppen -------------------------------------------------------------------------------

    async def vraag_stop(self, run: Run) -> None:
        """Vraag om te stoppen. Bewust een vlag en géén `task.cancel()`.

        De nodes zijn synchroon en de MCP-verbinding wordt in een `finally` gesloten; die onder een
        nog draaiende executor-thread wegtrekken is vragen om kapotte verbindingen. De run stopt dus
        op de eerstvolgende grens waar de driver de vlag leest – dat kan tientallen seconden duren,
        en de UI hoort dat niet weg te moffelen.
        """
        run.stop_gevraagd = True

    async def stop_gevraagd(self, run: Run) -> bool:
        """In dit proces is het verzoek de vlag zelf; er valt niets op te halen."""
        return run.stop_gevraagd

    # -- meekijken -----------------------------------------------------------------------------

    async def volg(self, run: Run, vanaf: int = 0) -> AsyncIterator[dict[str, Any]]:
        """Lever de events vanaf `vanaf` en volg daarna live mee.

        Elke abonnee houdt zijn eigen cursor en wacht op een `Condition` – geen `asyncio.Queue`,
        want die kun je maar één keer leegdrinken en er kunnen meerdere tabbladen meekijken.
        Losraken van deze generator laat de run ongemoeid.

        Twee dingen die eerder misgingen en waar de vorm nu op is gebouwd:

        - **Een gat blijkt uit de seq-sprong**, niet uit een teller. Het snoeien (`_cap`) haalt
          narratie weg waar die ook staat, dus "de eerste N zijn weg" was een verkeerde aanname:
          daarmee schoven de nummers op en kreeg een aanhaker betekenisvolle events dubbel.
        - **De toestandscontrole hoort onder de lock.** Stond ze erbuiten, dan kon de run afronden
          tussen `if not run.loopt` en het wachten – de `notify_all` was dan al geweest en de kijker
          bleef hangen op een run die klaar was, met een SSE-stream die nooit sloot.
        """
        cursor = vanaf
        while True:
            for event in [e for e in run.events if e.get("seq", 0) >= cursor]:
                seq = int(event.get("seq", cursor))
                if seq > cursor:
                    # Wees expliciet over het gat in plaats van stilzwijgend een verminkte tekst te
                    # leveren; dit dekt zowel te laat aanhaken als tussentijds snoeien.
                    yield {"type": "gat", "weggevallen": seq - cursor}
                yield event
                cursor = seq + 1
            async with run._wakker:
                if cursor >= run.geproduceerd and not run.loopt:
                    return
                if cursor >= run.geproduceerd:
                    await run._wakker.wait_for(
                        lambda: cursor < run.geproduceerd or not run.loopt
                    )

    # -- opruimen ------------------------------------------------------------------------------

    def _ruim_op(self) -> None:
        nu = time.monotonic()
        verlopen = [
            run_id for run_id, run in self._runs.items()
            if run.eind_op is not None and nu - run.eind_op > self._bewaar_s
        ]
        for run_id in verlopen:
            del self._runs[run_id]
