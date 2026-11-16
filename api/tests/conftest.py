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
