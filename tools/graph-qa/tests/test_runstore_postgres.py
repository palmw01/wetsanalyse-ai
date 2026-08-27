"""De gedeelde run-store, getoetst zoals hij in productie gebruikt wordt: door twee replica's.

Deze tests draaien tegen een echte PostgreSQL en zijn daarom gemarkeerd als `integration`
(standaard geskipt). Zonder database is "de runs zijn gedeeld" een bewering; dit is de plek waar
die bewering wordt nagerekend.

Draaien:
    docker run -d --name pg -p 55433:5432 \
      -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test postgres:16
    RUNSTORE_TEST_DSN=postgresql://test:test@localhost:55433/test \
      uv run --extra dev pytest tests/test_runstore_postgres.py -m integration
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import inspect
import os
from typing import Any

import pytest

from agent.runstore import RunBestaatAl, RunStore
from agent.runstore.postgres import PostgresStore

DSN = os.environ.get("RUNSTORE_TEST_DSN", "")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DSN, reason="RUNSTORE_TEST_DSN niet gezet"),
]


def stroom(events: list[dict[str, Any]], vertraag: float = 0.0):
    """Een `maak_stroom` die de gegeven events levert."""
    def maak(run):
        async def gen():
            for e in events:
                if vertraag:
                    await asyncio.sleep(vertraag)
                yield e
        return gen()
    return maak


def blijf_draaien(stop_na: float = 5.0):
    """Een stroom die pas eindigt als er om een stop gevraagd is."""
    def maak(run):
        async def gen():
            yield {"type": "status", "content": "bezig"}
            for _ in range(int(stop_na / 0.05)):
                if run.stop_gevraagd:
                    return
                await asyncio.sleep(0.05)
        return gen()
    return maak


def met_store(fn):
    """graph-qa heeft geen pytest-asyncio (zie tests/test_runs.py): de test draait zijn eigen
    event-loop. Deze decorator levert er meteen een lege store bij, en ruimt hem daarna op."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        async def draai():
            store = PostgresStore(DSN)
            await store.setup()
            async with store.pool.connection() as conn:
                await conn.execute("TRUNCATE agent_run_events, agent_runs")
            try:
                return await fn(store, *args, **kwargs)
            finally:
                await store.sluit()
        return asyncio.run(draai())

    # Zonder dit ziet pytest via functools.wraps de originele signatuur en zoekt hij een fixture
    # `store` die niet bestaat.
    wrapper.__signature__ = inspect.Signature()
    return wrapper


@met_store
async def test_de_store_voldoet_aan_het_protocol(store):
    assert isinstance(store, RunStore)


@met_store
async def test_setup_is_idempotent(store):
    await store.setup()  # tweede keer mag niets kapotmaken
    await store.setup()


@met_store
async def test_een_run_is_zichtbaar_vanaf_een_tweede_replica(store):
    """De kern: replica A start, replica B leest mee. Dit is wat er nu stukgaat bij maxReplicas 2."""
    replica_b = PostgresStore(DSN)
    await replica_b.setup()
    try:
        run = await store.start(conversation_id="g1", vraag="Wat regelt artikel 36?",
                                 maak_stroom=stroom([{"type": "token", "content": "a"},
                                                     {"type": "done"}]), user_id="u1")
        await asyncio.wait_for(run.taak, timeout=5)

        # B kent de run zonder hem ooit gestart te hebben.
        vanaf_b = await replica_b.get(run.run_id, user_id="u1")
        assert vanaf_b is not None
        assert vanaf_b.vraag == "Wat regelt artikel 36?"
        assert vanaf_b.status == "klaar"

        # En kan de events teruglezen.
        events = [e async for e in replica_b.volg(vanaf_b)]
        assert [e["type"] for e in events] == ["token", "done"]
    finally:
        await replica_b.sluit()


@met_store
async def test_de_eigenaarscontrole_geldt_ook_cross_replica(store):
    replica_b = PostgresStore(DSN)
    await replica_b.setup()
    try:
        run = await store.start(conversation_id="g1", vraag="v",
                                 maak_stroom=stroom([{"type": "done"}]), user_id="u1")
        await asyncio.wait_for(run.taak, timeout=5)
        assert await replica_b.get(run.run_id, user_id="iemand-anders") is None
    finally:
        await replica_b.sluit()


@met_store
async def test_een_tweede_run_op_hetzelfde_gesprek_botst_op_de_database(store):
    """Niet check-then-insert maar een unieke index: dit is de enige vorm die tussen twee
    replica's standhoudt."""
    replica_b = PostgresStore(DSN)
    await replica_b.setup()
    try:
        eerste = await store.start(conversation_id="g1", vraag="v", maak_stroom=blijf_draaien())
        with pytest.raises(RunBestaatAl) as botsing:
            await replica_b.start(conversation_id="g1", vraag="v2", maak_stroom=blijf_draaien())
        assert botsing.value.run_id == eerste.run_id

        await store.vraag_stop(eerste)
        await asyncio.wait_for(eerste.taak, timeout=5)

        # Na afloop mag het weer — de index geldt alleen lopende runs.
        tweede = await replica_b.start(conversation_id="g1", vraag="v2",
                                       maak_stroom=stroom([{"type": "done"}]))
        await asyncio.wait_for(tweede.taak, timeout=5)
    finally:
        await replica_b.sluit()


@met_store
async def test_stoppen_vanaf_de_andere_replica_bereikt_de_draaiende_run(store):
    """Het scherpste geval: het cancel-verzoek komt binnen op de replica waar de run níét draait."""
    replica_b = PostgresStore(DSN)
    await replica_b.setup()
    try:
        run = await store.start(conversation_id="g1", vraag="v", maak_stroom=blijf_draaien())
        await asyncio.sleep(0.1)

        vanaf_b = await replica_b.get(run.run_id)
        assert vanaf_b is not None
        await replica_b.vraag_stop(vanaf_b)          # B vraagt, A draait

        # A leest het verzoek op zijn eerstvolgende controle en stopt.
        await asyncio.wait_for(run.taak, timeout=5)
        eind = await store.get(run.run_id)
        assert eind is not None and eind.status == "gestopt"
    finally:
        await replica_b.sluit()


@met_store
async def test_een_run_zonder_hartslag_wordt_niet_eeuwig_lopend_genoemd(store):
    """Een replica die omvalt laat zijn runs achter. Die horen als mislukt te lezen, niet als
    lopend — anders wacht de werkplek op events die nooit meer komen."""
    run = await store.start(conversation_id="g1", vraag="v", maak_stroom=blijf_draaien())
    await asyncio.sleep(0.1)

    # Simuleer een weggevallen replica: de taak is weg en de hartslag veroudert.
    run.taak.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await run.taak
    store._taken.pop(run.run_id, None)
    async with store.pool.connection() as conn:
        await conn.execute(
            "UPDATE agent_runs SET status = 'loopt', hartslag = now() - interval '5 minutes' "
            "WHERE run_id = %s", (run.run_id,))

    gelezen = await store.get(run.run_id)
    assert gelezen is not None and gelezen.status == "mislukt"


@met_store
async def test_aanhaken_vanaf_een_seq_slaat_het_begin_over(store):
    run = await store.start(conversation_id="g1", vraag="v", maak_stroom=stroom(
        [{"type": "token", "content": c} for c in "abcd"] + [{"type": "done"}]))
    await asyncio.wait_for(run.taak, timeout=5)
    vanaf_twee = [e async for e in store.volg(run, vanaf=2)]
    assert [e.get("content") for e in vanaf_twee if e["type"] == "token"] == ["c", "d"]


@met_store
async def test_meekijken_op_een_lopende_run_levert_events_terwijl_ze_ontstaan(store):
    run = await store.start(conversation_id="g1", vraag="v", maak_stroom=stroom(
        [{"type": "token", "content": "a"}, {"type": "token", "content": "b"}, {"type": "done"}],
        vertraag=0.05))
    events = [e async for e in store.volg(run)]
    assert [e["type"] for e in events] == ["token", "token", "done"]
    assert run.status == "klaar"
