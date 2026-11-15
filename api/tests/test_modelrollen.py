"""Het modelprofiel per rol van Lex: de beheerder kiest per rol een profiel, graph-qa leest de modelnaam.

Zonder keuze volgt elke rol het standaardprofiel; een keuze draagt een naam (2FA) en een auditregel; een profiel dat Lex
niet kan gebruiken is niet te kiezen; een gekozen profiel verwijderen weigert.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

_ADMIN = {"Authorization": "Bearer admin-token"}
_BEHEERDER = {**_ADMIN, "X-User-Id": "gebruiker-a"}
_ZONDER_2FA = {**_ADMIN, "X-User-Id": "gebruiker-b"}


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    monkeypatch.setenv("WETSANALYSE_ADMIN_TOKENS", "adm:admin-token")
    monkeypatch.setenv("LLM_API_BASE", "https://straat.example/")
    from sqlalchemy import update

    from app import db, ratelimit
    from app.config import get_settings
    from app.routers.auth import vergeet_actief
    from conftest import maak_testgebruikers

    get_settings.cache_clear()
    ratelimit.reset()
    vergeet_actief()
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    await db.reconcile_schema()
    await maak_testgebruikers("gebruiker-a", "gebruiker-b")
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.users).where(db.users.c.userid == "gebruiker-a").values(totp_enabled=True))
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for naam, model, base, default in (("sonnet", "claude-sonnet-4-6", "", True),
                                           ("licht", "claude-haiku-4-5", "https://straat.example", False),
                                           ("elders", "claude-haiku-4-5", "https://ander.example", False),
                                           ("gpt", "gpt-5", "", False)):
            r = await ac.put(f"/v1/admin/profiles/{naam}", headers=_ADMIN,
                             json={"model": model, "api_base": base, "is_default": default})
            assert r.status_code == 200, r.text
        yield ac
    get_settings.cache_clear()
    await db.dispose_engine()


async def test_zonder_keuze_volgt_elke_rol_de_standaard(client):
    from bronmodel.modelrollen import NAMEN

    o = (await client.get("/v1/admin/modelrollen", headers=_ADMIN)).json()
    assert o["standaard"] == "sonnet" and o["standaard_model"] == "claude-sonnet-4-6"
    assert [r["naam"] for r in o["rollen"]] == list(NAMEN)
    assert all(r["profiel"] is None and r["model"] == "claude-sonnet-4-6" for r in o["rollen"])
    # Per profiel of Lex het kan gebruiken: een ander endpoint en een niet-Claude-model niet.
    assert o["profielen"]["licht"] == "" and o["profielen"]["sonnet"] == ""
    assert "endpoint" in o["profielen"]["elders"] and "Claude" in o["profielen"]["gpt"]
    agent = (await client.get("/v1/modelrollen")).json()
    assert agent == {"standaard": {"profiel": "sonnet", "model": "claude-sonnet-4-6"}, "rollen": {}}


async def test_een_keuze_bereikt_de_agent_en_staat_in_de_audit(client):
    r = await client.put("/v1/admin/modelrollen/subagent", json={"profiel": "licht"}, headers=_BEHEERDER)
    assert r.status_code == 200 and r.json()["model"] == "claude-haiku-4-5" and r.json()["door"] == "gebruiker-a"
    assert (await client.get("/v1/modelrollen")).json()["rollen"] == {
        "subagent": {"profiel": "licht", "model": "claude-haiku-4-5"}}
    # Dezelfde keuze nog eens is geen auditregel; terug naar de standaard wel.
    await client.put("/v1/admin/modelrollen/subagent", json={"profiel": "licht"}, headers=_BEHEERDER)
    r = await client.put("/v1/admin/modelrollen/subagent", json={"profiel": None}, headers=_BEHEERDER)
    assert r.json()["profiel"] is None and r.json()["model"] == "claude-sonnet-4-6"
    regels = (await client.get("/v1/admin/modelrollen/subagent/audit", headers=_ADMIN)).json()
    assert [(a["actie"], a["details"]) for a in regels] == [
        ("standaard", {"was": "licht", "wordt": None}), ("gekozen", {"was": None, "wordt": "licht"})]
    assert (await client.get("/v1/modelrollen")).json()["rollen"] == {}


async def test_de_standaard_wisselen_neemt_de_rollen_zonder_keuze_mee(client):
    await client.post("/v1/admin/profiles/licht/default", headers=_ADMIN)
    agent = (await client.get("/v1/modelrollen")).json()
    assert agent["standaard"] == {"profiel": "licht", "model": "claude-haiku-4-5"}


async def test_een_onbruikbaar_profiel_is_niet_te_kiezen(client):
    for profiel in ("elders", "gpt"):
        r = await client.put("/v1/admin/modelrollen/supervisor", json={"profiel": profiel}, headers=_BEHEERDER)
        assert r.status_code == 422 and r.json()["detail"]["fout"] == "niet_bruikbaar"
    assert (await client.put("/v1/admin/modelrollen/supervisor", json={"profiel": "bestaat-niet"},
                             headers=_BEHEERDER)).status_code == 404
    assert (await client.put("/v1/admin/modelrollen/onbekend", json={"profiel": "licht"},
                             headers=_BEHEERDER)).status_code == 404


async def test_een_profiel_dat_later_onbruikbaar_wordt_valt_terug_op_de_standaard(client):
    await client.put("/v1/admin/modelrollen/ophaal", json={"profiel": "licht"}, headers=_BEHEERDER)
    await client.put("/v1/admin/profiles/licht", headers=_ADMIN,
                     json={"model": "claude-haiku-4-5", "api_base": "https://ander.example"})
    rol = next(r for r in (await client.get("/v1/admin/modelrollen", headers=_ADMIN)).json()["rollen"]
               if r["naam"] == "ophaal")
    assert rol["profiel"] == "licht" and rol["niet_bruikbaar"] and rol["model"] == "claude-sonnet-4-6"
    assert (await client.get("/v1/modelrollen")).json()["rollen"] == {}


async def test_een_gekozen_profiel_verwijderen_weigert(client):
    await client.put("/v1/admin/modelrollen/jas_reviewer", json={"profiel": "licht"}, headers=_BEHEERDER)
    r = await client.delete("/v1/admin/profiles/licht", headers=_ADMIN)
    assert r.status_code == 409 and "JAS-reviewer" in r.json()["detail"]
    await client.put("/v1/admin/modelrollen/jas_reviewer", json={"profiel": None}, headers=_BEHEERDER)
    assert (await client.delete("/v1/admin/profiles/licht", headers=_ADMIN)).status_code == 204


async def test_zonder_2fa_of_zonder_admin_geen_keuze(client):
    r = await client.put("/v1/admin/modelrollen/subagent", json={"profiel": "licht"}, headers=_ZONDER_2FA)
    assert r.status_code == 403
    r = await client.put("/v1/admin/modelrollen/subagent", json={"profiel": "licht"},
                         headers={"X-User-Id": "gebruiker-a"})
    assert r.status_code == 401
    assert (await client.get("/v1/modelrollen")).json()["rollen"] == {}
