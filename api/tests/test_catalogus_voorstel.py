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
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from httpx import ASGITransport, AsyncClient

SLEUTEL = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PEM = SLEUTEL.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

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
        self.weiger_token, self.token_verzoek = False, None

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.verzoeken.append(req)
        pad = req.url.path
        if req.method == "POST" and pad == "/app/installations/77/access_tokens":
            if self.weiger_token:
                return httpx.Response(401, json={"message": "Bad credentials"})
            # De JWT moet met de sleutel van de App getekend zijn, kort geldig en voor deze App.
            kop, inhoud, handtekening = req.headers["Authorization"].removeprefix("Bearer ").split(".")
            SLEUTEL.public_key().verify(_b64d(handtekening), f"{kop}.{inhoud}".encode(), padding.PKCS1v15(), hashes.SHA256())
            claims = json.loads(_b64d(inhoud))
            assert claims["iss"] == "123" and claims["exp"] - claims["iat"] <= 600
            self.token_verzoek = json.loads(req.content)
            return httpx.Response(201, json={"token": "inst-tok", "expires_at": "2026-11-12T16:00:00Z"})
        if req.headers.get("Authorization") != "Bearer inst-tok":
            return httpx.Response(401)
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
    monkeypatch.setenv("GITHUB_APP_ID", "123")
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "77")
    monkeypatch.setenv("GITHUB_APP_KEY", PEM)
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
    # Eerst het installatietoken, beperkt tot deze repo en twee rechten; daarna alles met dat token.
    assert github.verzoeken[0].url.path == "/app/installations/77/access_tokens"
    assert github.token_verzoek == {"repositories": ["repo"], "permissions": {"contents": "write", "pull_requests": "write"}}
    assert all(v.headers["Authorization"] == "Bearer inst-tok" for v in github.verzoeken[1:])
    # Nooit een merge.
    assert not any("/merge" in v.url.path for v in github.verzoeken)


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
    assert not any(v.method in ("POST", "PUT") and "/app/installations/" not in v.url.path for v in github.verzoeken)


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


async def test_de_stand_met_vlag_en_app(client):
    st = await client.get("/v1/admin/catalogus/voorstellen/stand", headers=_ADMIN)
    assert st.json() == {"aan": True, "reden": ""}


async def test_zonder_app_staat_het_uit(client, github, monkeypatch):
    from app.config import get_settings
    monkeypatch.delenv("GITHUB_APP_KEY")
    get_settings.cache_clear()
    st = await client.get("/v1/admin/catalogus/voorstellen/stand", headers=_ADMIN)
    assert st.json()["aan"] is False and "GitHub App" in st.json()["reden"]
    r = await client.post("/v1/admin/catalogus/voorstellen", json=VOORSTEL, headers=_BEHEERDER)
    assert r.status_code == 404 and not github.verzoeken


async def test_een_onleesbare_sleutel_is_een_nette_fout(client, github, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("GITHUB_APP_KEY", "geen pem")
    get_settings.cache_clear()
    r = await client.post("/v1/admin/catalogus/voorstellen", json=VOORSTEL, headers=_BEHEERDER)
    assert r.status_code == 500 and "sleutel" in r.json()["detail"] and not github.verzoeken


async def test_een_geweigerd_installatietoken_is_502(client, github):
    github.weiger_token = True
    r = await client.post("/v1/admin/catalogus/voorstellen", json=VOORSTEL, headers=_BEHEERDER)
    assert r.status_code == 502
