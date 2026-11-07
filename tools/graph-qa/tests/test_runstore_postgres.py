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


@met_store
async def test_sluiten_bewaart_eindstatus_voordat_databasepool_sluit(store):
    started = asyncio.Event()
    async def stream(run):
        yield {"type": "tool_execution", "run_id": run.run_id, "call_id": "call1",
               "tool": "get_annotatie", "phase": "start"}
        started.set()
        await asyncio.Event().wait()
    run = await store.start(conversation_id="shutdown", vraag="v", maak_stroom=stream, user_id="u1")
    await asyncio.wait_for(started.wait(), timeout=5)
    await store.sluit()
    assert run.taak.done()
    replica = PostgresStore(DSN)
    await replica.setup()
    try:
        saved = await replica.get(run.run_id, user_id="u1")
        assert saved.status == "gestopt"
        events = [e async for e in replica.volg(saved)]
        assert events[0]["tool"] == "get_annotatie"
    finally:
        await replica.sluit()


@met_store
async def test_sluiten_direct_na_start_laat_geen_lopende_run_achter(store):
    run = await store.start(conversation_id="instant", vraag="v", maak_stroom=blijf_draaien())
    await store.sluit()
    replica = PostgresStore(DSN)
    await replica.setup()
    try:
        saved = await replica.get(run.run_id)
        assert saved.status == "gestopt"
    finally:
        await replica.sluit()


# ── het einde van een run ───────────────────────────────────────────────────────────────────────

@met_store
async def test_elke_run_eindigt_met_een_done_ook_op_de_andere_replica(store):
    run = await store.start(conversation_id="einde", vraag="v", maak_stroom=stroom([{"type": "token", "content": "x"}]))
    await asyncio.wait_for(run.taak, timeout=5)
    uit = [e async for e in store.volg(run)]
    assert [e["type"] for e in uit] == ["token", "done"] and uit[-1]["uitkomst"] == "klaar"
    # Aanhaken ná de `done`: geen vals alarm, en de client krijgt zijn einde.
    laat = [e async for e in store.volg(run, vanaf=run.geproduceerd)]
    assert [e["type"] for e in laat] == ["done"] and laat[0]["uitkomst"] == "klaar"


async def _wees(store: PostgresStore, gemeld: list[str]):
    """Een run die 'loopt' zonder hartslag en zonder eigen taak: zijn replica is weg."""
    run = await store.start(conversation_id="wees", vraag="v", user_id="u1", maak_stroom=blijf_draaien())
    await asyncio.sleep(0.05)  # de taak moet draaien, anders ruimt hij zichzelf niet op
    run.taak.cancel()
    await asyncio.gather(run.taak, return_exceptions=True)
    gemeld.clear()
    async with store.pool.connection() as conn:
        await conn.execute("UPDATE agent_runs SET status = 'loopt', hartslag = now() - interval '1 hour' "
                           "WHERE run_id = %s", (run.run_id,))
    return run


@met_store
async def test_een_wees_krijgt_precies_een_bericht_ook_met_twee_lezers(store):
    gemeld: list[str] = []

    async def haak(run, melding):
        gemeld.append(f"{run.run_id}:{melding}")

    store._bij_afbraak = haak
    run = await _wees(store, gemeld)
    await asyncio.gather(store.get(run.run_id), store.get(run.run_id))
    assert (await store.get(run.run_id)).status == "mislukt"
    assert len(gemeld) == 1 and gemeld[0].startswith(run.run_id)


@met_store
async def test_een_wees_eindigt_voor_de_kijker_met_een_fout_en_done(store):
    run = await _wees(store, [])
    uit = [e async for e in store.volg(run)]
    assert [e["type"] for e in uit][-2:] == ["error", "done"]
    assert uit[-2]["foutcode"] == "beurt_afgebroken" and uit[-1]["uitkomst"] == "mislukt"


@met_store
async def test_afsluiten_legt_de_lopende_runs_vast(store):
    gemeld: list[str] = []

    async def haak(run, _melding):
        gemeld.append(run.run_id)

    store._bij_afbraak = haak
    run = await store.start(conversation_id="uitrol", vraag="v", maak_stroom=blijf_draaien())
    klaar = await store.start(conversation_id="klaar", vraag="v", maak_stroom=stroom([{"type": "done"}]))
    await asyncio.wait_for(klaar.taak, timeout=5)
    await store.sluit()
    assert gemeld == [run.run_id]


@met_store
async def test_een_dode_run_blokkeert_de_volgende_vraag_niet(store):
    """Een run zonder hartslag hield het gesprek bezet: de volgende vraag kreeg een 409 zonder run (AG-13)."""
    async with store.pool.connection() as conn:
        await conn.execute("INSERT INTO agent_runs (run_id, conversation_id, vraag, hartslag) "
                           "VALUES ('dood', 'g1', 'v', now() - interval '5 minutes')")
    run = await store.start(conversation_id="g1", vraag="w", maak_stroom=stroom([{"type": "done"}]))
    await run.taak
    assert (await store.get("dood")).status == "mislukt" and run.run_id != "dood"


@met_store
async def test_de_hartslag_loopt_door_na_een_stopverzoek(store):
    """Na een stop rondt de run nog af; zonder hartslag verklaart een andere replica hem verweesd (AG-12)."""
    from agent.runstore import postgres

    monkeypatch_s = (postgres.POLS_S, postgres.HARTSLAG_S)
    postgres.POLS_S, postgres.HARTSLAG_S = 0.05, 0.1
    try:
        def rondt_traag_af(run):
            async def gen():
                yield {"type": "status", "content": "bezig"}
                while not run.stop_gevraagd:
                    await asyncio.sleep(0.02)
                await asyncio.sleep(0.8)  # een node die na de stop nog een modelaanroep afmaakt
                yield {"type": "done"}
            return gen()
        run = await store.start(conversation_id="g1", vraag="v", maak_stroom=rondt_traag_af)
        await store.vraag_stop(run)
        await asyncio.sleep(0.3)
        async with store.pool.connection() as conn:
            voor = (await (await conn.execute("SELECT hartslag FROM agent_runs WHERE run_id = %s", (run.run_id,))).fetchone())["hartslag"]
        await asyncio.sleep(0.3)
        async with store.pool.connection() as conn:
            na = (await (await conn.execute("SELECT hartslag FROM agent_runs WHERE run_id = %s", (run.run_id,))).fetchone())["hartslag"]
        await run.taak
    finally:
        postgres.POLS_S, postgres.HARTSLAG_S = monkeypatch_s
    assert na > voor
