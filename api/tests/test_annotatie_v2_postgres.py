"""Echte PostgreSQL-races; nooit op publieke/default-tabellen schrijven.

CI levert ANNOTATIE_TEST_DSN; iedere test maakt een eigen willekeurig schema en
verwijdert uitsluitend dat schema. SQLite kan SELECT FOR UPDATE niet bewijzen.
"""
import asyncio
import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app import db
from app import annotatie_v2_store as store
from app.annotatie_v2_contracts import Beslissing
from test_annotatie_v2 import ONE, TWO, element, request, snapshot

pytestmark = pytest.mark.skipif(not os.getenv("ANNOTATIE_TEST_DSN"), reason="PostgreSQL-test DSN ontbreekt")


@pytest.fixture(autouse=True)
async def postgres_schema():
    dsn = os.environ["ANNOTATIE_TEST_DSN"]
    schema = "annotatie_test_" + uuid.uuid4().hex
    administration = create_async_engine(dsn)
    async with administration.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    db.init_engine(dsn, connect_args={"server_settings": {"search_path": schema}})
    try:
        await db.create_all()
        await db.reconcile_schema()
        yield
    finally:
        await db.dispose_engine()
        async with administration.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await administration.dispose()


async def test_concurrent_retry_commits_once():
    snap = snapshot(ONE)
    req = request(snap, [element(snap)])
    a, b = await asyncio.gather(store.batch(req, snap, "a"), store.batch(req, snap, "a"))
    assert a == b
    async with db.get_engine().connect() as conn:
        assert len((await conn.execute(select(db.annotatie_v2_elementen))).all()) == 1
        assert len((await conn.execute(select(db.annotatie_v2_batches))).all()) == 1
        assert len((await conn.execute(select(db.annotatie_v2_audit))).all()) == 2


async def test_concurrent_same_node_revision_conflict_without_lost_update():
    snap = snapshot(ONE)
    a = request(snap, [element(snap)], batch_id="a")
    b = request(snap, [element(snap, start=7, end=11)], batch_id="b")
    results = await asyncio.gather(store.batch(a, snap, "a"), store.batch(b, snap, "b"), return_exceptions=True)
    assert sum(isinstance(r, dict) for r in results) == 1
    errors = [r for r in results if isinstance(r, HTTPException)]
    assert len(errors) == 1 and errors[0].status_code == 412
    view = await store.weergave(snap)
    assert len(view["elementen"]) == 1
    assert view["lagen"][0]["revisie"] == 1


async def test_concurrent_move_and_review_cannot_split_owner_or_history():
    snap = snapshot()
    created = await store.batch(request(snap, [element(snap)]), snap, "a")
    element_id = created["elementen"][0]["id"]
    moved = element(snap, TWO, 0, 4)
    change = Beslissing(type="edit", snapshot_id=snap["snapshot_id"], verwachte_revisies={ONE: 1, TWO: 0},
                        wijziging={"tekst": moved["tekst"], "ankers": moved["ankers"]})
    approve = Beslissing(type="approve", snapshot_id=snap["snapshot_id"], verwachte_revisies={ONE: 1})
    results = await asyncio.gather(store.beslis(element_id, change, snap, "a"),
                                   store.beslis(element_id, approve, snap, "b"), return_exceptions=True)
    assert sum(isinstance(r, dict) for r in results) == 1
    errors = [r for r in results if isinstance(r, HTTPException)]
    assert len(errors) == 1 and errors[0].status_code == 412
    result = await store.detail(element_id)
    assert result["element"]["laag_id"] == result["laag"]["id"]
    assert result["element"]["eigenaar_iri"] == result["laag"]["bron_iri"]
    assert len(result["element"]["beslissingen"]) == 1
