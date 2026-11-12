"""Een wijziging van de methode voorstellen als concept-PR (ADR-014 C7).

Alleen een beheerder met 2FA, alleen met de vlag en het token, alleen methodetekst in een skill. De api toetst met
dezelfde validator als de generator (`bronmodel.methodesectie`) en opent op GitHub een concept-PR; GitHub is hier een
`httpx.MockTransport` die de verzoeken vastlegt.
"""
from __future__ import annotations

import base64
import json

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

_ADMIN = {"Authorization": "Bearer admin-token"}
_BEHEERDER = {**_ADMIN, "X-User-Id": "gebruiker-a"}
_ZONDER_2FA = {**_ADMIN, "X-User-Id": "gebruiker-b"}
BESTAND = ".claude/skills/wetsanalyse/references/agentrollen.md"
TEKST = "# Kop\n\n<!-- methode:duiding:begin -->\nOude tekst.\n<!-- methode:duiding:end -->\n\nStaart.\n"
VOORSTEL = {"onderdeel_id": "rol/duiding", "bestand": BESTAND, "sectie": "duiding", "tekst": "Nieuwe tekst.",
            "toelichting": "Scherper."}


class NepGithub:
    def __init__(self, tekst: str = TEKST, ref_bestaat: bool = False) -> None:
        self.tekst, self.ref_bestaat, self.verzoeken = tekst, ref_bestaat, []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.verzoeken.append(req)
        pad = req.url.path
        if req.method == "GET" and "/contents/" in pad:
            return httpx.Response(200, json={"sha": "blob1", "content": base64.b64encode(self.tekst.encode()).decode()})
        if req.method == "GET" and pad.endswith("/git/ref/heads/master"):
            return httpx.Response(200, json={"object": {"sha": "commit1"}})
        if req.method == "POST" and pad.endswith("/git/refs"):
            return httpx.Response(422 if self.ref_bestaat else 201, json={})
        if req.method == "PUT" and "/contents/" in pad:
            return httpx.Response(201, json={})
        if req.method == "POST" and pad.endswith("/pulls"):
            return httpx.Response(201, json={"number": 42, "html_url": "https://example.test/pull/42"})
        return httpx.Response(500)


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    monkeypatch.setenv("WETSANALYSE_ADMIN_TOKENS", "adm:admin-token")
    monkeypatch.setenv("CATALOGUS_VOORSTELLEN", "true")
    monkeypatch.setenv("GITHUB_PR_TOKEN", "tok")
    monkeypatch.setenv("GITHUB_REPO", "eigenaar/repo")
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
        yield ac
    get_settings.cache_clear()
    await db.dispose_engine()


@pytest.fixture
def github(monkeypatch):
    from app import catalogus_voorstel
    nep = NepGithub()
    monkeypatch.setattr(catalogus_voorstel, "_TRANSPORT", httpx.MockTransport(nep))
    return nep


async def test_een_voorstel_wordt_een_concept_pr_met_alleen_de_sectie_gewijzigd(client, github):
    r = await client.post("/v1/admin/catalogus/voorstellen", json=VOORSTEL, headers=_BEHEERDER)
    assert r.status_code == 201, r.text
    assert r.json()["pr_nummer"] == 42 and r.json()["branch"].startswith("claude/catalogus-voorstel-duiding-")
    put = next(v for v in github.verzoeken if v.method == "PUT")
    nieuw = base64.b64decode(json.loads(put.content)["content"]).decode()
    assert nieuw == TEKST.replace("Oude tekst.", "Nieuwe tekst.")
    pr = json.loads(next(v for v in github.verzoeken if v.url.path.endswith("/pulls")).content)
    assert pr["draft"] is True and pr["base"] == "master"
    assert "gebruiker-a" in pr["body"] and "Oude tekst." in pr["body"] and "Nieuwe tekst." in pr["body"]
    assert all(v.headers["Authorization"] == "Bearer tok" for v in github.verzoeken)


async def test_zonder_2fa_geen_voorstel(client, github):
    r = await client.post("/v1/admin/catalogus/voorstellen", json=VOORSTEL, headers=_ZONDER_2FA)
    assert r.status_code == 403 and not github.verzoeken


@pytest.mark.parametrize("veld,waarde,status", [
    ("bestand", "tools/graph-qa/agent/prompts.py", 422),
    ("bestand", ".claude/skills/wetsanalyse/SKILL.md", 422),
    ("sectie", "Onbekend!", 422),
    ("tekst", "<!-- methode:x:begin --> sluiproute", 422),
    ("tekst", "Oude tekst.", 409),
])
async def test_wat_niet_kan_wordt_geweigerd_zonder_branch(client, github, veld, waarde, status):
    r = await client.post("/v1/admin/catalogus/voorstellen", json={**VOORSTEL, veld: waarde}, headers=_BEHEERDER)
    assert r.status_code == status, r.text
    assert not any(v.method in ("POST", "PUT") for v in github.verzoeken)


async def test_een_sectie_die_niet_bestaat_is_422(client, github):
    r = await client.post("/v1/admin/catalogus/voorstellen", json={**VOORSTEL, "sectie": "retrieval"}, headers=_BEHEERDER)
    assert r.status_code == 422 and "retrieval" in r.json()["detail"]


async def test_hetzelfde_voorstel_nog_eens_is_409(client, github):
    github.ref_bestaat = True
    r = await client.post("/v1/admin/catalogus/voorstellen", json=VOORSTEL, headers=_BEHEERDER)
    assert r.status_code == 409


async def test_zonder_vlag_staat_het_uit(client, github, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("CATALOGUS_VOORSTELLEN", "false")
    get_settings.cache_clear()
    st = await client.get("/v1/admin/catalogus/voorstellen/stand", headers=_ADMIN)
    assert st.json() == {"aan": False, "reden": "Voorstellen vanuit de werkplek staan in deze omgeving uit."}
    r = await client.post("/v1/admin/catalogus/voorstellen", json=VOORSTEL, headers=_BEHEERDER)
    assert r.status_code == 404 and not github.verzoeken


async def test_de_stand_met_vlag_en_token(client):
    st = await client.get("/v1/admin/catalogus/voorstellen/stand", headers=_ADMIN)
    assert st.json() == {"aan": True, "reden": ""}
