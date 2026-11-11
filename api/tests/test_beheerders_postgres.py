"""De laatste actieve beheerder onder echte PostgreSQL-races: het slot laat er altijd één over.

Zelfde opzet als `test_werkgebieden_postgres.py`: een eigen schema per test. SQLite serialiseert alle writes
en kan dus niet laten zien dat twee gelijktijdige transacties elkaar niet beide doorlaten.
"""
import asyncio
import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app import db, users

pytestmark = pytest.mark.skipif(not os.getenv("ANNOTATIE_TEST_DSN"), reason="PostgreSQL-test DSN ontbreekt")


@pytest.fixture(autouse=True)
async def postgres_schema():
    dsn = os.environ["ANNOTATIE_TEST_DSN"]
    schema = "beheerders_test_" + uuid.uuid4().hex
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


async def _beheerders(*userids: str) -> None:
    await users.bootstrap_admin(userids[0], f"{userids[0]}@example.test", "wachtwoord1")
    for uid in userids[1:]:
        await users.create_user(uid, f"{uid}@example.test", role="beheerder")


async def _actief() -> list[str]:
    return sorted(u.userid for u in await users.list_users() if u.role == "beheerder" and u.active)


async def test_twee_beheerders_degraderen_elkaar_tegelijk():
    await _beheerders("anna", "bram")
    uitkomst = await asyncio.gather(
        users.patch_user("anna", role="analist"), users.patch_user("bram", role="analist"),
        return_exceptions=True,
    )
    assert sum(isinstance(r, users.UserError) for r in uitkomst) == 1
    assert len(await _actief()) == 1


async def test_twee_beheerders_verwijderen_elkaar_tegelijk():
    await _beheerders("anna", "bram")
    uitkomst = await asyncio.gather(users.delete_user("anna"), users.delete_user("bram"), return_exceptions=True)
    assert sum(isinstance(r, users.UserError) for r in uitkomst) == 1
    assert len(await _actief()) == 1


async def test_verwijderen_en_deactiveren_tegelijk():
    await _beheerders("anna", "bram")
    uitkomst = await asyncio.gather(
        users.delete_user("anna"), users.patch_user("bram", active=False), return_exceptions=True,
    )
    assert sum(isinstance(r, users.UserError) for r in uitkomst) == 1
    assert len(await _actief()) == 1


async def test_alles_tegelijk_laat_precies_een_beheerder_over():
    namen = [f"beheerder{i}" for i in range(6)]
    await _beheerders(*namen)
    pogingen = []
    for i, uid in enumerate(namen):
        if i % 3 == 0:
            pogingen.append(users.delete_user(uid))
        elif i % 3 == 1:
            pogingen.append(users.patch_user(uid, active=False))
        else:
            pogingen.append(users.patch_user(uid, role="analist", active=False))
    uitkomst = await asyncio.gather(*pogingen, return_exceptions=True)
    assert not [r for r in uitkomst if isinstance(r, Exception) and not isinstance(r, users.UserError)]
    assert sum(isinstance(r, users.UserError) for r in uitkomst) == 1
    assert len(await _actief()) == 1


async def test_promotie_en_degradatie_tegelijk_raken_de_telling_niet_kwijt():
    """Een patch die een net gepromoveerde beheerder deactiveert, toetst op de rij van ná het slot."""
    await _beheerders("anna")
    await users.create_user("xander", "xander@example.test")
    for _ in range(5):
        await users.patch_user("xander", role="beheerder")
        uitkomst = await asyncio.gather(
            users.patch_user("anna", role="analist"), users.patch_user("xander", active=False),
            return_exceptions=True,
        )
        assert len(await _actief()) == 1, uitkomst
        # Terug naar de begintoestand: anna enige beheerder, xander actief analist.
        await users.patch_user("anna", role="beheerder", active=True)
        await users.patch_user("xander", role="analist", active=True)
