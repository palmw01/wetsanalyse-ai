"""Werkgebieden onder echte PostgreSQL-races: het rij-slot laat precies één wijziging door.

Zelfde opzet als `test_annotatie_v2_postgres.py`: een eigen schema per test, alleen dat schema wordt
verwijderd. SQLite kan `SELECT … FOR UPDATE` niet bewijzen.
"""
import asyncio
import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app import db, werkgebied_store as store
from app.werkgebied_contracts import BronselectieInvoer, WerkgebiedInvoer, WerkgebiedWijziging
from test_annotatie_v2 import ART

pytestmark = pytest.mark.skipif(not os.getenv("ANNOTATIE_TEST_DSN"), reason="PostgreSQL-test DSN ontbreekt")


@pytest.fixture(autouse=True)
async def postgres_schema():
    dsn = os.environ["ANNOTATIE_TEST_DSN"]
    schema = "werkgebied_test_" + uuid.uuid4().hex
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


async def test_twee_gelijktijdige_wijzigingen_precies_een_412():
    wg = await store.maak(WerkgebiedInvoer(naam="A"), "a")
    results = await asyncio.gather(
        store.wijzig(wg["id"], WerkgebiedWijziging(verwachte_revisie=1, naam="B"), "a"),
        store.wijzig(wg["id"], WerkgebiedWijziging(verwachte_revisie=1, naam="C"), "b"),
        return_exceptions=True)
    fouten = [r for r in results if isinstance(r, HTTPException)]
    assert len(fouten) == 1 and fouten[0].status_code == 412
    assert (await store.haal(wg["id"]))["revisie"] == 2


async def test_dezelfde_bron_gelijktijdig_toevoegen_levert_een_selectie():
    wg = await store.maak(WerkgebiedInvoer(naam="A"), "a")
    bron = {"bron_iri": ART, "label": "art. 9", "bwb_id": "BWBR0004770", "snapshot_id": "s", "bron_hash": "h"}
    invoer = BronselectieInvoer(verwachte_revisie=1, bron_iri=ART)
    results = await asyncio.gather(store.voeg_bron_toe(wg["id"], invoer, bron, "a"),
                                   store.voeg_bron_toe(wg["id"], invoer, bron, "b"),
                                   return_exceptions=True)
    assert sum(not isinstance(r, Exception) for r in results) >= 1
    assert all(r.status_code in (409, 412) for r in results if isinstance(r, HTTPException))
    assert len((await store.haal(wg["id"]))["bronnen"]) == 1


async def test_twee_kandidaten_gelijktijdig_opnemen_op_dezelfde_revisie_precies_een_412():
    """Fase A: opnemen loopt door het slot van het werkgebied; kandidaat en selectie landen samen."""
    from app import bronnen_run_store as runs
    from app.bronnen_run_contracts import BronnenUitkomst, Opnemen
    from test_werkgebieden import ART2

    wg = await store.maak(WerkgebiedInvoer(naam="A", analysevraag="Wanneer?"), "a")
    run, _ = await runs.start(await store.haal(wg["id"]), "a")
    k = lambda iri: {"bron_iri": iri, "rol": "kern", "bewijs": [{"methode": "overzicht"}]}  # noqa: E731
    await runs.zet_uitkomst(wg["id"], run["id"], BronnenUitkomst(invoer_id=run["invoer_id"],
                                                                 kandidaten=[k(ART), k(ART2)]), "lex")
    bron = lambda iri: {"bron_iri": iri, "label": iri, "bwb_id": "", "snapshot_id": "s", "bron_hash": "h"}  # noqa: E731
    results = await asyncio.gather(
        runs.opnemen(wg["id"], runs.kandidaat_id(ART), Opnemen(verwachte_revisie=1), bron(ART), "a"),
        runs.opnemen(wg["id"], runs.kandidaat_id(ART2), Opnemen(verwachte_revisie=1), bron(ART2), "b"),
        return_exceptions=True)
    fouten = [r for r in results if isinstance(r, HTTPException)]
    assert len(fouten) == 1 and fouten[0].status_code == 412
    statussen = {x["bron_iri"]: x["status"] for x in (await runs.kandidaten(wg["id"]))["kandidaten"]}
    # De kandidaat van de geweigerde opname staat nog open: geen half besluit.
    assert sorted(statussen.values()) == ["opgenomen", "voorgesteld"]
    assert len((await store.haal(wg["id"]))["bronnen"]) == 1
