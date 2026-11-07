"""De schema-opstart op PostgreSQL: gelijktijdig, en een bijgewerkte database is gelijk aan een verse (G7)."""
import asyncio
import os
import uuid

import pytest
from sqlalchemy import event, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app import db

pytestmark = pytest.mark.skipif(not os.getenv("ANNOTATIE_TEST_DSN"), reason="PostgreSQL-test DSN ontbreekt")


@pytest.fixture
async def leeg_schema():
    dsn = os.environ["ANNOTATIE_TEST_DSN"]
    schema = "schema_start_" + uuid.uuid4().hex
    beheer = create_async_engine(dsn)
    async with beheer.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    db.init_engine(dsn, connect_args={"server_settings": {"search_path": schema}})
    try:
        yield schema
    finally:
        await db.dispose_engine()
        async with beheer.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await beheer.dispose()


async def _stand(schema: str) -> dict:
    def lees(sync_conn):
        insp = inspect(sync_conn)
        uit = {}
        for tabel in insp.get_table_names(schema=schema):
            uit[tabel] = {
                "kolommen": {c["name"]: (str(c["type"]), c["nullable"]) for c in insp.get_columns(tabel, schema=schema)},
                "indexen": {i["name"]: (tuple(i["column_names"]), i["unique"]) for i in insp.get_indexes(tabel, schema=schema)},
            }
        return uit
    async with db.get_engine().connect() as conn:
        return await conn.run_sync(lees)


async def test_gelijktijdige_starts_botsen_niet(leeg_schema):
    await asyncio.gather(*(db.bouw_schema() for _ in range(4)))
    assert set(await _stand(leeg_schema)) == set(db.metadata.tables)


async def test_bijgewerkt_is_gelijk_aan_vers(leeg_schema):
    await db.bouw_schema()
    vers = await _stand(leeg_schema)
    # Een oude database: alles wat later is bijgekomen ontbreekt, en een oude NOT NULL staat er nog.
    async with db.get_engine().begin() as conn:
        for tabel in db.metadata.tables.values():
            for kolom in tabel.columns:
                if kolom.nullable and not kolom.primary_key and kolom.name != "werkgebied_id":
                    await conn.execute(text(f'ALTER TABLE "{tabel.name}" DROP COLUMN "{kolom.name}" CASCADE'))
        await conn.execute(text("ALTER TABLE begrippen ALTER COLUMN werkgebied_id SET NOT NULL"))
    await db.bouw_schema()
    assert await _stand(leeg_schema) == vers


async def test_een_herstart_neemt_geen_tabelslot(leeg_schema):
    await db.bouw_schema()
    ddl = []

    def noteer(_conn, _cursor, statement, *_rest):
        if statement.lstrip().upper().startswith(("ALTER", "CREATE", "DROP")):
            ddl.append(statement)

    event.listen(db.get_engine().sync_engine, "before_cursor_execute", noteer)
    await db.bouw_schema()
    assert ddl == []
