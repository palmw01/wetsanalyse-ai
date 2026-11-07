"""bcrypt houdt de event loop niet vast, en een golf pogingen krijgt snel een nee (B2)."""
import asyncio
import threading
import time

import pytest
from fastapi import HTTPException

from app import users


async def test_de_lus_draait_door_tijdens_een_hash(monkeypatch):
    klaar = threading.Event()
    monkeypatch.setattr(users, "hash_password", lambda _p: (klaar.wait(5), "hash")[1])
    taak = asyncio.create_task(users.hash_wachtwoord("x"))
    await asyncio.sleep(0.01)                      # zou hier vastzitten als bcrypt op de lus draaide
    assert not taak.done()
    klaar.set()
    assert await taak == "hash"


async def test_een_volle_wachtrij_weigert_meteen(monkeypatch):
    klaar = threading.Event()
    monkeypatch.setattr(users, "verify_password", lambda *_a: klaar.wait(5))
    monkeypatch.setattr(users, "_BCRYPT_MAX_WACHTEND", 3)
    taken = [asyncio.create_task(users.controleer_wachtwoord("x", "h")) for _ in range(3)]
    await asyncio.sleep(0)
    begin = time.perf_counter()
    with pytest.raises(HTTPException) as fout:
        await users.controleer_wachtwoord("x", "h")
    assert fout.value.status_code == 503 and time.perf_counter() - begin < 0.1
    klaar.set()
    assert await asyncio.gather(*taken) == [True, True, True]
    assert users._bcrypt_wachtend == 0
