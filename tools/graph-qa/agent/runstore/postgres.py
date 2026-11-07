"""De runs gedeeld in PostgreSQL — zodat twee replica's elkaars beurten zien.

graph-qa staat op Azure op `maxReplicas: 2`. Met de runs in procesgeheugen betekende dat vier stille
storingen: aanhaken op de andere replica gaf 404, de 409-bescherming zag een lopende run niet,
`GET /conversations/{id}/run` miste hem, en een stopverzoek landde op het verkeerde proces en deed
niets. Deze store lost alle vier op, zonder nieuwe infrastructuur: graph-qa heeft al een
`CHECKPOINT_DB_URL` naar dezelfde database als de api.

Wat er wél en niet gedeeld is:

- **Gedeeld:** de eventlog, de metadata en het stopverzoek. Elke replica kan meelezen, de 409
  vaststellen en om een stop vragen.
- **Niet gedeeld:** de draaiende taak zelf. Die is een asyncio-taak in één proces, en de
  LangGraph-nodes zijn synchroon — er is geen resume-pad. Een replica die omvalt neemt zijn lopende
  runs mee.

Dat laatste is zichtbaar in plaats van stil: elke lopende run schrijft een hartslag, en een run
die `loopt` zegt maar al een minuut geen teken van leven gaf, wordt bij het uitlezen als `mislukt`
gemarkeerd. Zonder dat blijft zo'n run eeuwig "lopend" en wacht de werkplek op een antwoord dat
nooit komt.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from psycopg import errors as pg_errors
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from . import (
    AFGEBROKEN,
    MAX_EVENTS,
    VLUCHTIGE_TYPES,
    BijAfbraak,
    Run,
    RunBestaatAl,
    afgebroken_events,
    meld_afbraak,
    sluit_af,
)

logger = logging.getLogger("graph_qa.runs")

# Hoe vaak de polstaak draait: hij leest het stopverzoek én houdt de hartslag bij. Kort genoeg dat
# een stopverzoek van een andere replica snel aankomt (de gebruiker wacht erop), en de graaf leest de
# vlag verder gratis — `stop_check` blijft een simpele attribuutlezing.
POLS_S = 2.0
# Hoe vaak de hartslag naar de database gaat. Een veelvoud van POLS_S: een write per twee seconden
# per lopende run is zonde voor iets dat pas na een minuut betekenis krijgt.
HARTSLAG_S = 10.0
# Hoe lang een run zonder hartslag nog als levend telt. Ruim boven HARTSLAG_S, want een node die een
# trage LLM-call doet mag geen vals alarm geven — de hartslag loopt als aparte taak door.
VERWEESD_NA_S = 60.0
# Hoe vaak een meekijker naar nieuwe events polst. Kort genoeg dat tokens vloeiend binnenkomen,
# lang genoeg dat een handvol tabbladen de database niet plat legt.
POLL_S = 0.25
# Hoe lang een stopverzoek gecachet wordt. De graaf vraagt het per node; zonder cache is dat een
# query per node en dat is zonde voor een vlag die zelden aan staat.
STOP_CACHE_S = 2.0
# Hoe lang het afsluiten wacht op lopende beurten voor het ze afbreekt. Een uitrol of inschalen stopt de replica; een
# beurt van een paar minuten hoort dan af te ronden in plaats van te sneuvelen (ROB-05). Samen met uvicorns
# `--timeout-graceful-shutdown` (Dockerfile) binnen `terminationGracePeriodSeconds` van de app (main.bicep).
DRAIN_S = 150.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_runs (
    run_id           TEXT PRIMARY KEY,
    conversation_id  TEXT NOT NULL DEFAULT '',
    user_id          TEXT NOT NULL DEFAULT '',
    vraag            TEXT NOT NULL DEFAULT '',
    status           TEXT NOT NULL DEFAULT 'loopt',
    stop_verzocht    BOOLEAN NOT NULL DEFAULT FALSE,
    geproduceerd     INTEGER NOT NULL DEFAULT 0,
    weggevallen      INTEGER NOT NULL DEFAULT 0,
    hartslag         TIMESTAMPTZ NOT NULL DEFAULT now(),
    gestart          TIMESTAMPTZ NOT NULL DEFAULT now(),
    afgerond         TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS agent_run_events (
    run_id   TEXT NOT NULL REFERENCES agent_runs(run_id) ON DELETE CASCADE,
    seq      INTEGER NOT NULL,
    type     TEXT NOT NULL DEFAULT '',
    payload  JSONB NOT NULL,
    PRIMARY KEY (run_id, seq)
);

-- Twee beurten op één gesprek schrijven door elkaar heen in dezelfde checkpointer-thread
-- (thread_id == conversation_id). Een check-then-insert dekt dat niet als er twee replica's zijn;
-- deze index maakt er een botsing van die de database afdwingt.
CREATE UNIQUE INDEX IF NOT EXISTS agent_runs_een_lopende_per_gesprek
    ON agent_runs (conversation_id)
    WHERE status = 'loopt' AND conversation_id <> '';
"""


def _naar_run(rij: dict[str, Any]) -> Run:
    """Een databaserij → het Run-object dat de rest van de code kent."""
    return Run(
        run_id=rij["run_id"],
        conversation_id=rij["conversation_id"],
        user_id=rij["user_id"],
        vraag=rij["vraag"],
        status=rij["status"],
        weggevallen=rij["weggevallen"],
        geproduceerd=rij["geproduceerd"],
        stop_gevraagd=rij["stop_verzocht"],
    )


class PostgresStore:
    """Runs in PostgreSQL, zodat elke replica ze ziet."""

    def __init__(self, conninfo: str, *, max_events: int = MAX_EVENTS,
                 bij_afbraak: BijAfbraak | None = None) -> None:
        self._conninfo = conninfo
        self._bij_afbraak = bij_afbraak
        # De runs die dit proces draait: bij het afsluiten krijgt wat dan nog loopt een bericht.
        self._lopend: dict[str, Run] = {}
        self._max_events = max_events
        self._pool: AsyncConnectionPool | None = None
        # Alleen de runs die in dít proces draaien. De store is gedeeld, de taak is dat niet.
        self._taken: dict[str, asyncio.Task[None]] = {}
        self._stop_cache: dict[str, tuple[float, bool]] = {}

    async def setup(self) -> None:
        """Open de pool en maak de tabellen als ze ontbreken. Idempotent, zoals de checkpointer."""
        if self._pool is None:
            self._pool = AsyncConnectionPool(
                self._conninfo, open=False, min_size=1, max_size=4,
                # Pool-breed, niet per connectie: een row_factory die je op een geleende
                # connectie zet, blijft erop staan als hij terugkeert in de pool.
                kwargs={"row_factory": dict_row},
            )
            await self._pool.open()
        async with self._pool.connection() as conn:
            await conn.execute(_SCHEMA)

    async def sluit(self, *, wacht_s: float = DRAIN_S) -> None:
        # Eerst laten afronden wat loopt; pas wat daarna nog loopt, wordt afgebroken en als gestopt vastgelegd.
        if self._taken and wacht_s > 0:
            await asyncio.wait(list(self._taken.values()), timeout=wacht_s)
        run_ids = list(self._taken)
        taken = list(self._taken.values())
        afgebroken = list(self._lopend.values())
        for taak in taken:
            taak.cancel()
        # Annulering schrijft nog de eindstatus en stopt de heartbeat. Houd de pool
        # open totdat dit klaar is, zodat andere replicas geen spookrun zien.
        if taken:
            await asyncio.gather(*taken, return_exceptions=True)
            # Een taak kan al geannuleerd zijn vóór haar coroutine start. Ook dan
            # moet de bij start() vastgelegde run als beëindigd leesbaar zijn.
            async with self.pool.connection() as conn:
                await conn.execute(
                    "UPDATE agent_runs SET status = 'gestopt', afgerond = now() "
                    "WHERE run_id = ANY(%s) AND status = 'loopt'", (run_ids,))
            self._taken.clear()
            # Niemand anders kan dit nog: de status staat al op `gestopt`, dus geen replica verklaart ze verweesd.
            await asyncio.gather(*(meld_afbraak(self._bij_afbraak, run, AFGEBROKEN) for run in afgebroken))
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> AsyncConnectionPool:
        if self._pool is None:
            raise RuntimeError("PostgresStore.setup() is niet aangeroepen")
        return self._pool

    # -- opvragen ------------------------------------------------------------------------------

    async def _lees(self, sql: str, params: tuple[Any, ...]) -> Run | None:
        async with self.pool.connection() as conn:
            cur = await conn.execute(sql, params)
            rij = await cur.fetchone()
        if rij is None:
            return None
        return await self._verweesd_afhandelen(_naar_run(rij))

    async def _verweesd_afhandelen(self, run: Run) -> Run:
        """Een run die 'loopt' zegt maar geen hartslag meer geeft, draait nergens meer.

        Dat gebeurt als de replica die hem draaide is herstart of weggeschaald. De werkplek zou
        anders blijven wachten op events die niet meer komen; nu leest ze `mislukt` en kan ze dat
        tonen. Bewust bij het uitlezen en niet in een opruimtaak: dan is er geen achtergrondproces
        nodig dat zelf weer kan omvallen.
        """
        if run.status != "loopt" or run.run_id in self._taken:
            return run
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                "UPDATE agent_runs SET status = 'mislukt', afgerond = now() "
                "WHERE run_id = %s AND status = 'loopt' AND hartslag < now() - make_interval(secs => %s) "
                "RETURNING run_id",
                (run.run_id, VERWEESD_NA_S),
            )
            verweesd = await cur.fetchone()
        if verweesd is None:
            return run
        logger.warning(
            "run verweesd verklaard: geen hartslag meer",
            extra={"categorie": "technisch", "run_id": run.run_id, "grens_s": VERWEESD_NA_S},
        )
        run.status = "mislukt"
        # De `RETURNING` hierboven kiest precies één winnaar, dus er is één schrijver, ook met meer lezers.
        await meld_afbraak(self._bij_afbraak, run, AFGEBROKEN)
        return run

    async def get(self, run_id: str, *, user_id: str | None = None) -> Run | None:
        run = await self._lees("SELECT * FROM agent_runs WHERE run_id = %s", (run_id,))
        if run is None:
            return None
        if user_id is not None and run.user_id and run.user_id != user_id:
            return None
        return run

    async def actief_voor(self, conversation_id: str, *, user_id: str | None = None) -> Run | None:
        if not conversation_id:
            return None
        run = await self._lees(
            "SELECT * FROM agent_runs WHERE conversation_id = %s AND status = 'loopt' "
            "ORDER BY gestart DESC LIMIT 1",
            (conversation_id,),
        )
        if run is None or not run.loopt:
            return None
        if user_id is not None and run.user_id and run.user_id != user_id:
            return None
        return run

    # -- starten -------------------------------------------------------------------------------

    async def start(
        self,
        *,
        conversation_id: str,
        vraag: str,
        maak_stroom: Callable[[Run], AsyncIterator[dict[str, Any]]],
        user_id: str = "",
    ) -> Run:
        run = Run(run_id=uuid.uuid4().hex, conversation_id=conversation_id,
                  user_id=user_id, vraag=vraag)
        try:
            async with self.pool.connection() as conn:
                await conn.execute(
                    "INSERT INTO agent_runs (run_id, conversation_id, user_id, vraag) "
                    "VALUES (%s, %s, %s, %s)",
                    (run.run_id, conversation_id, user_id, vraag),
                )
        except pg_errors.UniqueViolation as botsing:
            # De partiële index sloeg toe: er loopt al een run op dit gesprek. Bewust zonder
            # user-filter opgehaald — twee lussen op één thread_id is een dataprobleem, ongeacht wie
            # ze start.
            bestaand = await self.actief_voor(conversation_id)
            raise RunBestaatAl(bestaand.run_id if bestaand else "") from botsing

        self._lopend[run.run_id] = run
        run.taak = asyncio.create_task(self._draai(run, maak_stroom))
        self._taken[run.run_id] = run.taak
        return run

    async def _draai(self, run: Run, maak_stroom: Callable[[Run], AsyncIterator[dict[str, Any]]]) -> None:
        hart = asyncio.create_task(self._pols(run))
        try:
            async for event in sluit_af(maak_stroom(run), run, self._bij_afbraak):
                await self._voeg_toe(run, event)
            status = run.uitkomst
            self._lopend.pop(run.run_id, None)
        except asyncio.CancelledError:
            await self._rond_af(run, "gestopt")
            raise
        except Exception:
            logger.exception("run mislukt", extra={"categorie": "technisch", "run_id": run.run_id})
            melding = "Er ging iets mis bij het beantwoorden. Probeer het opnieuw."
            await self._voeg_toe(run, {"type": "error", "message": melding})
            await self._voeg_toe(run, {"type": "done", "uitkomst": "mislukt"})
            await meld_afbraak(self._bij_afbraak, run, melding)
            self._lopend.pop(run.run_id, None)
            status = "mislukt"
        finally:
            hart.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hart
            self._taken.pop(run.run_id, None)
        await self._rond_af(run, status)

    async def _pols(self, run: Run) -> None:
        """Twee dingen die allebei van buiten dit proces komen of moeten gaan.

        **Het stopverzoek lezen.** De graaf vraagt per node `stop_check()`, en dat is een synchrone
        aanroep vanuit een threadpool — daar kan geen query doorheen. Deze taak leest de vlag dus
        vóór hem uit en zet hem op de Run; `stop_check` blijft een attribuutlezing. Zo bereikt een
        cancel die op de ándere replica binnenkwam alsnog de draaiende beurt.

        **De hartslag schrijven.** Minder vaak dan de pols: hij krijgt pas na een minuut betekenis.
        """
        sinds_hartslag = 0.0
        faalt = False  # Eén regel per storing: de pols loopt elke paar seconden.
        while True:
            await asyncio.sleep(POLS_S)
            sinds_hartslag += POLS_S
            try:
                async with self.pool.connection() as conn:
                    if sinds_hartslag >= HARTSLAG_S:
                        cur = await conn.execute(
                            "UPDATE agent_runs SET hartslag = now() WHERE run_id = %s "
                            "RETURNING stop_verzocht", (run.run_id,))
                        sinds_hartslag = 0.0
                    else:
                        cur = await conn.execute(
                            "SELECT stop_verzocht FROM agent_runs WHERE run_id = %s", (run.run_id,))
                    rij = await cur.fetchone()
                faalt = False
                if rij and rij["stop_verzocht"]:
                    run.stop_gevraagd = True
                    return  # de graaf ziet de vlag; verder polsen heeft geen zin
            except Exception:  # noqa: BLE001 – de pols mag de beurt niet laten vallen
                if not faalt:
                    logger.warning("run-pols mislukt", exc_info=True,
                                   extra={"categorie": "technisch", "run_id": run.run_id})
                faalt = True

    async def _rond_af(self, run: Run, status: str) -> None:
        run.status = status
        run.eind_op = time.monotonic()
        async with self.pool.connection() as conn:
            await conn.execute(
                "UPDATE agent_runs SET status = %s, afgerond = now() WHERE run_id = %s",
                (status, run.run_id),
            )

    async def _voeg_toe(self, run: Run, event: dict[str, Any]) -> None:
        seq = run.geproduceerd
        async with self.pool.connection() as conn:
            await conn.execute(
                "INSERT INTO agent_run_events (run_id, seq, type, payload) VALUES (%s, %s, %s, %s)",
                (run.run_id, seq, str(event.get("type", "")), Jsonb({**event, "seq": seq})),
            )
            await conn.execute(
                "UPDATE agent_runs SET geproduceerd = %s, hartslag = now() WHERE run_id = %s",
                (seq + 1, run.run_id),
            )
        run.geproduceerd = seq + 1
        await self._cap(run)

    async def _cap(self, run: Run) -> None:
        """Snoei de log, maar gooi alleen narratie weg — net als de geheugenvariant.

        Een generieke ringbuffer zou het begin van het antwoord opeten en een late aanhaker een
        tekst leveren die klopt noch compleet is.
        """
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                "SELECT count(*) FROM agent_run_events WHERE run_id = %s", (run.run_id,)
            )
            rij = await cur.fetchone()
            aantal = int(rij["count"]) if rij else 0
            if aantal <= self._max_events:
                return
            teveel = aantal - self._max_events
            cur = await conn.execute(
                "DELETE FROM agent_run_events WHERE ctid IN ("
                "  SELECT ctid FROM agent_run_events"
                "  WHERE run_id = %s AND type = ANY(%s) ORDER BY seq LIMIT %s"
                ") RETURNING seq",
                (run.run_id, list(VLUCHTIGE_TYPES), teveel),
            )
            gedropt = len(await cur.fetchall())
            if gedropt:
                await conn.execute(
                    "UPDATE agent_runs SET weggevallen = weggevallen + %s WHERE run_id = %s",
                    (gedropt, run.run_id),
                )
        run.weggevallen += gedropt

    # -- stoppen -------------------------------------------------------------------------------

    async def vraag_stop(self, run: Run) -> None:
        """Zet de vlag in de database, zodat hij ook de replica bereikt waar de run draait."""
        run.stop_gevraagd = True
        self._stop_cache.pop(run.run_id, None)
        async with self.pool.connection() as conn:
            await conn.execute(
                "UPDATE agent_runs SET stop_verzocht = TRUE WHERE run_id = %s", (run.run_id,)
            )

    async def stop_gevraagd(self, run: Run) -> bool:
        """Is er om een stop gevraagd? Kort gecachet: de graaf vraagt dit per node."""
        if run.stop_gevraagd:
            return True
        nu = time.monotonic()
        gecachet = self._stop_cache.get(run.run_id)
        if gecachet is not None and nu - gecachet[0] < STOP_CACHE_S:
            return gecachet[1]
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                "SELECT stop_verzocht FROM agent_runs WHERE run_id = %s", (run.run_id,)
            )
            rij = await cur.fetchone()
        gevraagd = bool(rij["stop_verzocht"]) if rij else False
        self._stop_cache[run.run_id] = (nu, gevraagd)
        if gevraagd:
            run.stop_gevraagd = True
        return gevraagd

    # -- meekijken -----------------------------------------------------------------------------

    async def volg(self, run: Run, vanaf: int = 0) -> AsyncIterator[dict[str, Any]]:
        """Lever de events vanaf `vanaf` en volg daarna live mee, ook als de run elders draait.

        Waar de geheugenvariant op een `Condition` wacht, polst deze de tabel: een wachtende
        connectie per kijker houden schaalt slechter dan een korte query per kwart seconde, en
        LISTEN/NOTIFY vraagt een eigen verbinding buiten de pool om.

        De gat-melding komt uit de seq-sprong, niet uit een teller — het snoeien haalt narratie weg
        waar die ook staat, dus "de eerste N zijn weg" is een verkeerde aanname.
        """
        cursor = vanaf
        gezien = False
        while True:
            async with self.pool.connection() as conn:
                cur = await conn.execute(
                    "SELECT seq, payload FROM agent_run_events "
                    "WHERE run_id = %s AND seq >= %s ORDER BY seq",
                    (run.run_id, cursor),
                )
                rijen = await cur.fetchall()
            for rij in rijen:
                seq = int(rij["seq"])
                if seq > cursor:
                    yield {"type": "gat", "weggevallen": seq - cursor}
                yield rij["payload"]
                gezien = gezien or rij["payload"].get("type") == "done"
                cursor = seq + 1

            vers = await self.get(run.run_id)
            if vers is None:
                return
            run.status, run.geproduceerd = vers.status, vers.geproduceerd
            if cursor >= vers.geproduceerd and not vers.loopt:
                break
            if cursor >= vers.geproduceerd:
                await asyncio.sleep(POLL_S)
        if not gezien:
            # Ook wie aanhaakt ná de `done` (`vanaf`) krijgt hem: alleen `done` sluit een beurt voor de client.
            einde = await self._einde(run)
            for event in [einde] if einde else afgebroken_events():
                yield event

    async def _einde(self, run: Run) -> dict[str, Any] | None:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                "SELECT payload FROM agent_run_events WHERE run_id = %s AND type = 'done' LIMIT 1", (run.run_id,))
            rij = await cur.fetchone()
        return rij["payload"] if rij else None
