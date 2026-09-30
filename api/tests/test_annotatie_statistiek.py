"""De reviewstatistiek: wat juristen met de voorstellen van de agent deden.

Een beslissing draagt het type, de reden, de correctie en de oude waarden; elk agent-element draagt
het model dat het voorstel maakte. `annotatie_statistiek.rapport` telt dat op, via twee ingangen:
het admin-endpoint over de database en `scripts/statistiek.py` over een JSON-export.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.annotatie_statistiek import rapport


def _el(klasse: str = "Voorwaarde", herkomst: str = "agent", aandacht: str | None = None,
        beslissingen: list[dict] | None = None, **extra) -> dict:
    return {"id": extra.pop("id", "e1"), "klasse": klasse, "tekst": "indien hij verzoekt",
            "herkomst": herkomst, "aandacht": aandacht, "beslissingen": beslissingen or [],
            "geproduceerd_door": {"model": "claude-sonnet", "agent_versie": "1.2"}, **extra}


def _besluit(type_: str, **extra) -> dict:
    return {"type": type_, "actor": "jurist", **extra}


def test_de_zwaarste_beslissing_telt():
    st = rapport([_el(beslissingen=[_besluit("approve"), _besluit("comment")]),
                  _el(beslissingen=[_besluit("edit"), _besluit("reject")]),
                  _el()])
    assert (st.goedgekeurd, st.afgewezen, st.open) == (1, 1, 1)
    assert st.per_klasse["Voorwaarde"]["totaal"] == 3


def test_een_eigen_markering_is_geen_goedgekeurd_voorstel():
    st = rapport([_el(herkomst="mens", beslissingen=[_besluit("approve")]), _el()])
    assert (st.van_jurist, st.van_agent, st.goedgekeurd) == (1, 1, 0)


def test_klasse_verschuiving_leest_voor_en_na():
    edit = _besluit("edit", wijziging={"klasse": "Rechtsfeit"}, voor={"klasse": "Voorwaarde"},
                    review_reason="verkeerde_klasse")
    st = rapport([_el(klasse="Rechtsfeit", beslissingen=[edit])])
    assert st.klasse_verschuivingen == {"Voorwaarde → Rechtsfeit": 1}
    assert st.per_review_reason == {"verkeerde_klasse": 1}


def test_zonder_voor_geen_verschuiving():
    st = rapport([_el(beslissingen=[_besluit("edit", wijziging={"klasse": "Rechtsfeit"})])])
    assert st.klasse_verschuivingen == {}


def test_aandacht_telt_alleen_beoordeelde_elementen():
    st = rapport([_el(aandacht="geel", beslissingen=[_besluit("reject")]),
                  _el(aandacht="geel", beslissingen=[_besluit("approve")]),
                  _el(aandacht="groen")])
    assert st.per_aandacht == {"geel": {"beoordeeld": 2, "gecorrigeerd": 1}}


def test_per_model_en_verouderd():
    st = rapport([_el(beslissingen=[_besluit("approve")]), _el(verouderd=True)])
    assert st.elementen == 1
    assert st.per_model == {"claude-sonnet · 1.2": {
        "totaal": 1, "goedgekeurd": 1, "aangepast": 0, "afgewezen": 0, "open": 0}}


# --- de twee ingangen -------------------------------------------------------------------------------

@pytest.fixture
async def admin_client(monkeypatch):
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    monkeypatch.setenv("WETSANALYSE_ADMIN_TOKENS", "beheer:geheim")
    from app import db, ratelimit
    from app.config import get_settings

    get_settings.cache_clear()
    ratelimit.reset()
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()

    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_het_endpoint_telt_over_de_lagen(admin_client):
    from app import db

    async with db.get_engine().begin() as conn:
        for n in (1, 2):
            await conn.execute(db.annotatie_v2_lagen.insert().values(
                id=f"laag{n}", bron_iri=f"urn:bwb:BWBR1:artikel:{n}", revisie=1, status="in_review",
                snapshot_id="s", geprojecteerd_revisie=0, updated=db.utcnow()))
            await conn.execute(db.annotatie_v2_elementen.insert().values(
                id=f"e{n}", laag_id=f"laag{n}",
                inhoud=_el(id=f"e{n}", beslissingen=[_besluit("approve")])))

    r = await admin_client.get("/v1/admin/annotatie-statistiek",
                               headers={"Authorization": "Bearer geheim"})
    assert r.status_code == 200
    assert r.json()["lagen"] == 2 and r.json()["goedgekeurd"] == 2

    r = await admin_client.get("/v1/admin/annotatie-statistiek?limit=1",
                               headers={"Authorization": "Bearer geheim"})
    assert r.json()["lagen"] == 1 and r.json()["elementen"] == 1


async def test_zonder_admin_token_geen_statistiek(admin_client):
    r = await admin_client.get("/v1/admin/annotatie-statistiek")
    assert r.status_code == 401


def test_het_script_draait_over_een_export(tmp_path):
    """Dezelfde aggregatie langs de andere ingang – die moet werken zónder database."""
    export = {"elementen": [_el(beslissingen=[_besluit("edit", wijziging={"klasse": "Rechtsfeit"},
                                                       voor={"klasse": "Voorwaarde"})])]}
    pad = tmp_path / "export.json"
    pad.write_text(json.dumps(export), encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "statistiek.py"
    uit = subprocess.run([sys.executable, str(script), str(pad)], capture_output=True, text=True, check=True)
    assert "1 export(s), 1 elementen" in uit.stdout
    assert "Voorwaarde → Rechtsfeit" in uit.stdout
