"""Samenhangsgraaf: structuur, annotaties en letterlijke verwijzingen, zonder afgeleide relaties."""
import pytest

from app import annotatie_v2_store as store
from app import db, samenhang
from test_annotatie_v2 import ART, LAW, ONE, TWO, element, request, snapshot

ANDER = "urn:bwb:BWBR0004770:artikel:10"
STUB = "urn:bwb:BWBR0002320:artikel:3"


@pytest.fixture(autouse=True)
async def database():
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    yield
    await db.dispose_engine()


def rijen(uit=None, inn=None):
    async def haal(iris):
        return uit or [], inn or []
    return haal


async def test_lid_toont_hele_artikel_met_structuur_annotaties_en_verwijzingen(monkeypatch):
    snap = snapshot()
    await store.batch(request(snap, [element(snap), element(snap, TWO, 0, 4)]), snap, "a")
    monkeypatch.setattr(samenhang, "_verwijzingen", rijen(
        uit=[{"van": TWO, "naar": ONE, "anker": "het eerste lid"},
             {"van": ONE, "naar": ANDER, "anker": "artikel 10", "label": "Artikel 10"},
             {"van": ONE, "naar": STUB, "stub": "Awb, artikel 3"}],
        inn=[{"van": "urn:bwb:BWBR0004770:artikel:20:lid:1", "naar": ART, "label": "Artikel 20, lid 1"}]))
    g = await samenhang.samenhang(snapshot(ONE))
    ids = {k["id"]: k for k in g["knopen"]}
    assert g["artikel_iri"] == ART and g["verwijzingen_beschikbaar"]
    assert {LAW, ART, ONE, TWO} <= ids.keys()
    assert ("bevat", LAW, ART) in {(r["soort"], r["bron"], r["doel"]) for r in g["relaties"]}
    # binnen het artikel: gewone kant, geen randknoop
    assert any(r["bron"] == TWO and r["doel"] == ONE and r["groep"] == "verwijzingen" for r in g["relaties"])
    assert not ids[ONE]["rand"]
    assert ids[ANDER]["rand"] and ids[ANDER]["soort"] == "artikel" and ids[ANDER]["artikel"] == "10"
    assert ids[STUB]["soort"] == "extern" and ids[STUB]["label"] == "Awb, artikel 3"
    assert ids["urn:bwb:BWBR0004770:artikel:20:lid:1"]["lid"] == "1"
    markeringen = [k for k in g["knopen"] if k["soort"] == "markering"]
    assert len(markeringen) == 2 and "klasse:Rechtssubject" in ids
    assert all(k["element_id"] for k in markeringen)


async def test_afgewezen_en_verouderde_markeringen_blijven_weg(monkeypatch):
    snap = snapshot()
    await store.batch(request(snap, [element(snap), element(snap, TWO, 0, 4)]), snap, "a")
    monkeypatch.setattr(samenhang, "_verwijzingen", rijen())
    # Andere tekst in lid 2 maakt het element daar verouderd.
    g = await samenhang.samenhang(snapshot(second="Gamma"))
    assert [k["tekst"] for k in g["knopen"] if k["soort"] == "markering"] == ["Alfa"]


async def test_verwijzingen_onbeschikbaar_geeft_toch_structuur(monkeypatch):
    async def faalt(iris):
        return None
    monkeypatch.setattr(samenhang, "_verwijzingen", faalt)
    g = await samenhang.samenhang(snapshot())
    assert not g["verwijzingen_beschikbaar"]
    assert not any(r["groep"] == "verwijzingen" for r in g["relaties"])
    assert {k["id"] for k in g["knopen"]} >= {LAW, ART, ONE, TWO}


async def test_afkapping_en_ontdubbeling(monkeypatch):
    veel = [{"van": ONE, "naar": f"urn:bwb:BWBR0004770:artikel:{i}"} for i in range(100, 100 + samenhang.MAX_VERWIJZINGEN + 1)]
    monkeypatch.setattr(samenhang, "_verwijzingen", rijen(uit=veel + veel[:3]))
    g = await samenhang.samenhang(snapshot())
    assert g["afgekapt"]
    assert sum(r["groep"] == "verwijzingen" for r in g["relaties"]) == samenhang.MAX_VERWIJZINGEN


async def test_zonder_graaf_geen_fout_bij_verwijzingen(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("GRAPHDB_URL", "")
    get_settings.cache_clear()
    assert await samenhang._verwijzingen([ONE]) is None
    get_settings.cache_clear()


def test_queries_beperken_zich_tot_de_scope():
    q = samenhang._uitgaand([ONE, TWO])
    assert f"<{ONE}>" in q and f"<{TWO}>" in q and "VALUES ?van" in q
    assert f"LIMIT {samenhang.MAX_VERWIJZINGEN + 1}" in samenhang._inkomend([ONE])


async def test_endpoint_vereist_gebruiker_en_meldt_capability(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from app import annotatie_v2
    from app.config import get_settings
    from conftest import maak_testgebruikers
    monkeypatch.setenv("ANNOTATIE_CONTRACT_VERSIE", "2")
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    get_settings.cache_clear()
    await maak_testgebruikers("v2-samenhang")
    from app.main import app

    async def resolve(goal):
        return snapshot(goal.get("bron_iri", ART))
    monkeypatch.setattr(annotatie_v2, "_resolve_bron", resolve)
    monkeypatch.setattr(samenhang, "_verwijzingen", rijen())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/v1/annotatie/samenhang", params={"bron_iri": ONE})).status_code == 401
        headers = {"X-User-Id": "v2-samenhang"}
        r = await client.get("/v1/annotatie/samenhang", params={"bron_iri": ONE}, headers=headers)
        assert r.status_code == 200 and r.json()["artikel_iri"] == ART
        assert (await client.get("/v1/annotatie/capabilities", headers=headers)).json()["samenhang"]
    get_settings.cache_clear()
