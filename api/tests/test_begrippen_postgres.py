"""Begrippen onder echte PostgreSQL-races: het werkgebiedslot houdt de primaire duiding uniek, het
begripslot laat precies één wijziging door.

Zelfde opzet als `test_werkgebieden_postgres.py`: een eigen schema per test. SQLite kan
`SELECT … FOR UPDATE` niet bewijzen.
"""
import asyncio
import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app import annotatie_v2_store as annotaties, begrip_store as store, db, werkgebied_store
from app.begrip_contracts import BegripInhoud, BegripInvoer, BegripWijziging, KoppelInvoer
from app.werkgebied_contracts import BronselectieInvoer, WerkgebiedInvoer
from test_annotatie_v2 import ART, ONE, element, request, snapshot

pytestmark = pytest.mark.skipif(not os.getenv("ANNOTATIE_TEST_DSN"), reason="PostgreSQL-test DSN ontbreekt")


@pytest.fixture(autouse=True)
async def postgres_schema():
    dsn = os.environ["ANNOTATIE_TEST_DSN"]
    schema = "begrip_test_" + uuid.uuid4().hex
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


async def resolve(doel):
    return snapshot(doel.get("bron_iri") or ART)


async def _opzet() -> tuple[dict, str]:
    snap = snapshot()
    uit = await annotaties.batch(request(snap, [element(snap, ONE)]), snap, "lex")
    wg = await werkgebied_store.maak(WerkgebiedInvoer(naam="A"), "a")
    bron = {"bron_iri": ART, "label": "Artikel 9", "bwb_id": "BWBR0004770", "snapshot_id": snap["snapshot_id"],
            "bron_hash": ""}
    await werkgebied_store.voeg_bron_toe(wg["id"], BronselectieInvoer(verwachte_revisie=1, bron_iri=ART), bron, "a")
    return await werkgebied_store.haal(wg["id"]), uit["elementen"][0]["id"]


async def test_gelijktijdig_dezelfde_duiding_aan_twee_begrippen_levert_er_een():
    wg, eid = await _opzet()
    a = await store.maak(wg, BegripInvoer(inhoud=BegripInhoud(naam="A")), "a", resolve)
    b = await store.maak(wg, BegripInvoer(inhoud=BegripInhoud(naam="B")), "b", resolve)
    results = await asyncio.gather(
        store.koppel(wg, a["id"], KoppelInvoer(verwachte_revisie=1, element_ids=[eid]), "a", resolve),
        store.koppel(wg, b["id"], KoppelInvoer(verwachte_revisie=1, element_ids=[eid]), "b", resolve),
        return_exceptions=True)
    fouten = [r for r in results if isinstance(r, HTTPException)]
    assert len(fouten) == 1 and fouten[0].status_code == 409 and fouten[0].detail["fout"] == "al_primair"
    k = db.begrip_koppelingen
    async with db.get_engine().connect() as conn:
        aantal = len((await conn.execute(select(k.c.id).where(k.c.element_id == eid, k.c.rol == "duiding"))).all())
    assert aantal == 1


async def test_twee_gelijktijdige_wijzigingen_van_een_begrip_precies_een_412():
    wg, _ = await _opzet()
    b = await store.maak(wg, BegripInvoer(inhoud=BegripInhoud(naam="A")), "a", resolve)
    results = await asyncio.gather(
        store.wijzig(wg["id"], b["id"], BegripWijziging(verwachte_revisie=1, inhoud=BegripInhoud(naam="B")), "a"),
        store.wijzig(wg["id"], b["id"], BegripWijziging(verwachte_revisie=1, inhoud=BegripInhoud(naam="C")), "b"),
        return_exceptions=True)
    fouten = [r for r in results if isinstance(r, HTTPException)]
    assert len(fouten) == 1 and fouten[0].status_code == 412
    assert (await store.haal(wg["id"], b["id"]))["revisie"] == 2
