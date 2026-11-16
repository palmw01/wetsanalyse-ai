"""Test-bootstrap: zet de projectroot op sys.path zodat `import app.*` werkt.

De brede engine-/durability-fixtures (FakeLLM/FakeWettenbank/store/engine) zijn met de
analyse-pijplijn verwijderd; de resterende suites (annotatie, auth, admin, wet-info,
validation, observability) brengen hun eigen fixtures mee."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


async def maak_testgebruikers(*userids: str) -> None:
    """Zet de gegeven userids als actieve accounts in de (test-)DB.

    Nodig sinds de gescopete endpoints via `actieve_userid` controleren of het account bestaat en
    actief is: een verzonnen X-User-Id levert nu 401 in plaats van stilzwijgend door te lopen.
    """
    from app import users

    for i, uid in enumerate(userids):
        if i == 0 and await users.needs_setup():
            await users.bootstrap_admin(uid, f"{uid}@example.test", "testwachtwoord123")
        else:
            await users.create_user(uid, f"{uid}@example.test")


@pytest.fixture
def pdftotext() -> str:
    """Het pad van `pdftotext`, de onafhankelijke tekstextractie voor de PDF-tests (testplan api V2).

    Lokaal zonder poppler slaat een test over; in CI (`CI` is daar gezet) is een ontbrekende `pdftotext` een fout,
    want anders slaan de PDF-tests daar altijd stil over. Elke job die de api-tests draait, installeert
    `poppler-utils`."""
    pad = shutil.which("pdftotext")
    if pad is None:
        if os.environ.get("CI"):
            pytest.fail("pdftotext ontbreekt in CI: installeer poppler-utils in deze job")
        pytest.skip("pdftotext ontbreekt voor onafhankelijke PDF-tekstextractie")
    return pad


#: Postgres voor de races (testplan api V4): `ANNOTATIE_TEST_DSN` in de poort, lokaal een eigen container.
POSTGRES_DSN = os.environ.get("ANNOTATIE_TEST_DSN", "")


def vereis_postgres():
    """Een `pytestmark` voor een test die een echte Postgres vraagt: SQLite serialiseert alles en bewijst geen slot."""
    return pytest.mark.skipif(not POSTGRES_DSN, reason="PostgreSQL-test DSN ontbreekt")


async def postgres_schema(naam: str):
    """Een eigen schema per test, als engine van `app.db`; alleen dat schema wordt na afloop verwijderd. Dezelfde opzet als
    `test_werkgebieden_postgres.py`, gedeeld zodat elke race-test er één regel voor nodig heeft."""
    import uuid

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app import db
    schema = f"{naam}_{uuid.uuid4().hex}"
    beheer = create_async_engine(POSTGRES_DSN)
    async with beheer.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    db.init_engine(POSTGRES_DSN, connect_args={"server_settings": {"search_path": schema}})
    try:
        await db.create_all()
        await db.reconcile_schema()
        yield
    finally:
        await db.dispose_engine()
        async with beheer.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await beheer.dispose()


async def op_postgres(naam: str, monkeypatch):
    """Zet een eigen Postgres-schema klaar en laat de `init_engine`/`dispose_engine` van een bestaande client-fixture er
    niets aan veranderen: zo draait een fixture die zelf SQLite opzet, ongewijzigd op Postgres. Gebruik als autouse-fixture
    (die gaat vóór de client-fixture)."""
    from app import db
    async for _ in postgres_schema(naam):
        monkeypatch.setattr(db, "init_engine", lambda *a, **k: None)
        monkeypatch.setattr(db, "dispose_engine", _geen)
        yield
        monkeypatch.undo()


async def _geen() -> None:
    return None


def pytest_configure(config):
    config.addinivalue_line("markers", "risico(id, laag=None): het risico van Lex Bench dat deze test dekt "
                                       "(docs/lex-bench/risicos.json, scripts/risicomatrix.py)")
