"""Gedeeld voor de hele api-suite (testplan api V7).

- de projectroot op `sys.path`, zodat `import app.*` werkt;
- elke test begint en eindigt zonder procestoestand (`_procestoestand_per_test`): de settings, de gesprekstore, de
  Fernet-sleutel, de rate limit en de actief-cache. Anders hangt een uitkomst af van de volgorde;
- `api_client`: de ASGI-client op een verse SQLite, met de omgeving en de testgebruikers die een suite vraagt;
- `postgres_schema`: een eigen Postgres-schema per test, voor elke suite die `ANNOTATIE_TEST_DSN` vraagt.

De bron en het werkgebied die veel suites delen, staan in `gedeelde_bron.py`: wat daar staat, geldt alleen waar het
geïmporteerd wordt, en hoort dus niet hier.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import sys
from collections.abc import AsyncIterator, Iterable
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def schoon() -> None:
    """Leeg wat de api per proces bewaart. Een nieuwe cache op moduleniveau hoort hier bij."""
    from app import ratelimit, secrets_crypto
    from app.config import get_settings
    from app.deps import get_gesprek_store
    from app.routers.auth import vergeet_actief

    get_settings.cache_clear()
    get_gesprek_store.cache_clear()
    secrets_crypto._fernet.cache_clear()
    ratelimit.reset()
    vergeet_actief()


@pytest.fixture(autouse=True)
def _procestoestand_per_test():
    schoon()
    yield
    schoon()


@contextlib.asynccontextmanager
async def api_client(monkeypatch, *, env: dict[str, str] | None = None, gebruikers: Iterable[str] = (),
                     reconcile: bool = False, met_2fa: Iterable[str] = (), beheerders: Iterable[str] = (),
                     headers: dict[str, str] | None = None) -> AsyncIterator:
    """De client die de meeste suites zelf opbouwden: omgeving, een verse in-memory SQLite, de testgebruikers (de eerste
    wordt de beheerder van `/setup`), en wie 2FA heeft of beheerder is. Wat een suite daarnaast klaarzet, doet ze binnen
    het blok."""
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import update

    from app import db

    for naam, waarde in (env or {}).items():
        monkeypatch.setenv(naam, waarde)
    schoon()
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    if reconcile:
        await db.reconcile_schema()
    gebruikers = tuple(gebruikers)
    if gebruikers:
        await maak_testgebruikers(*gebruikers)
    met_2fa, beheerders = tuple(met_2fa), tuple(beheerders)
    if met_2fa or beheerders:
        async with db.get_engine().begin() as conn:
            for uid in met_2fa:
                await conn.execute(update(db.users).where(db.users.c.userid == uid).values(totp_enabled=True))
            for uid in beheerders:
                await conn.execute(update(db.users).where(db.users.c.userid == uid).values(role="beheerder"))
    from app.main import app
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers or {}) as ac:
            yield ac
    finally:
        schoon()
        await db.dispose_engine()


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
