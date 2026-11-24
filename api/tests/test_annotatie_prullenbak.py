"""De prullenbak van de annotaties: verwijderen bewaart, terugzetten herstelt, een nieuwe laag blokkeert, en wat naar
een verwijderd element verwijst zegt "bron verwijderd"."""
import pytest
from fastapi import HTTPException
from sqlalchemy import insert, select, update

from app import annotatie_prullenbak as bak
from app import annotatie_v2_store as store
from app import db
from app import graaf_projectie_v2 as projectie
from app.annotatie_v2_contracts import Beslissing
from app.config import get_settings
from app.graaf_projectie_v2 import graph_iri
from graafdb_fake import installeer
from gedeelde_bron import ONE, element, request, snapshot


@pytest.fixture(autouse=True)
async def database():
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    yield
    get_settings.cache_clear()
    await db.dispose_engine()


def revisies(view: dict) -> dict[str, int]:
    return {l["bron_iri"]: l["revisie"] for l in view["lagen"]}


async def audit(actie: str) -> list[dict]:
    async with db.get_engine().connect() as conn:
        return [dict(r) for r in (await conn.execute(select(db.annotatie_v2_audit).where(
            db.annotatie_v2_audit.c.actie == actie))).mappings().all()]


async def beoordeeld_lid() -> tuple[dict, dict]:
    """Lid 1 met twee markeringen van Lex, waarvan één beoordeeld, en een artefactversie van de annotatie."""
    lid = snapshot(ONE)
    uit = await store.batch(request(lid, [element(lid), element(lid, start=7, end=11)],
                                    dekking={"voltooid": True, "bereik": [ONE]}), lid, "lex")
    await store.beslis(uit["elementen"][0]["id"], Beslissing(type="approve", snapshot_id=lid["snapshot_id"],
                                                             verwachte_revisies={ONE: 1}), lid, "jurist")
    async with db.get_engine().begin() as conn:
        await conn.execute(insert(db.artefact_versies).values(
            id="v1", soort="annotatie", sleutel=f"annotatie:{ONE}", run_id="run-1", inhoud={"x": 1}, gemaakt=db.utcnow()))
    return lid, uit


async def test_verwijderen_bewaart_alles_in_de_prullenbak_en_terugzetten_herstelt_het(monkeypatch):
    nep = installeer(monkeypatch)
    lid, uit = await beoordeeld_lid()
    laag_id = uit["lagen"][0]["id"]
    assert await projectie.projecteer(laag_id)
    voor = await store.weergave(lid)

    weg = await store.verwijder_weergave(lid, revisies(voor), "jurist-b")

    assert weg["prullenbak"]["bewaartermijn_dagen"] == 30
    pid = weg["prullenbak"]["id"]
    na = await store.weergave(lid)
    assert not na["lagen"] and not na["elementen"] and na["verwijderd"]["door"] == "jurist-b"
    assert na["prullenbak"]["id"] == pid and na["prullenbak"]["terugzetbaar"] and not na["prullenbak"]["bezet"]
    assert (na["prullenbak"]["markeringen"], na["prullenbak"]["beoordeeld"]) == (2, 1)
    assert not len(nep.ds.graph(graph_iri(laag_id)))         # de projectie gaat er wel uit
    assert (await audit("laag-verwijderd"))[0]["detail"]["prullenbak_id"] == pid

    terug = await bak.zet_terug(pid, "jurist-c")

    assert terug["teruggezet"] == {"lagen": 1, "elementen": 2, "relaties": 0, "impliciet": 0}
    hersteld = await store.weergave(lid)
    assert [e["id"] for e in hersteld["elementen"]] == [e["id"] for e in voor["elementen"]]
    assert [e["lifecycle"] for e in hersteld["elementen"]] == [e["lifecycle"] for e in voor["elementen"]]
    assert hersteld["lagen"][0]["id"] == laag_id and hersteld["lagen"][0]["revisie"] == voor["lagen"][0]["revisie"] + 1
    assert hersteld["dekking"]["voltooid"] and hersteld["prullenbak"] is None and hersteld["verwijderd"] is None
    # De laag staat vuil (`geprojecteerd_revisie` 0): na de commit, of anders in de lus, gaat hij weer de graaf in.
    assert hersteld["lagen"][0]["geprojecteerd_revisie"] == 0
    assert await projectie.projecteer(laag_id) and len(nep.ds.graph(graph_iri(laag_id)))
    async with db.get_engine().connect() as conn:
        assert (await conn.execute(select(db.artefact_versies.c.id))).scalars().all() == ["v1"]
        assert not (await conn.execute(select(db.annotatie_v2_prullenbak))).all()
    [regel] = await audit("laag-teruggezet")
    assert regel["actor"] == "jurist-c" and regel["detail"]["prullenbak_id"] == pid
    with pytest.raises(HTTPException) as exc:
        await bak.zet_terug(pid, "jurist-c")
    assert exc.value.status_code == 404


async def test_een_nieuwe_laag_blokkeert_terugzetten_en_de_vergelijking_toont_beide():
    lid, _ = await beoordeeld_lid()
    pid = (await store.verwijder_weergave(lid, revisies(await store.weergave(lid)), "b"))["prullenbak"]["id"]
    await store.batch(request(lid, [element(lid, start=2, end=6)], batch_id="nieuw"), lid, "lex")

    view = await store.weergave(lid)
    assert len(view["elementen"]) == 1 and view["verwijderd"] is None
    assert view["prullenbak"]["id"] == pid and not view["prullenbak"]["terugzetbaar"]
    assert view["prullenbak"]["bezet"] == [ONE]
    with pytest.raises(HTTPException) as exc:
        await bak.zet_terug(pid, "c")
    assert exc.value.status_code == 409
    assert exc.value.detail["fout"] == "nieuwe_laag" and exc.value.detail["bezet"] == [ONE]
    assert exc.value.detail["nu"][ONE]["markeringen"] == 1
    toen = await bak.lees(pid)
    assert len(toen["elementen"]) == 2 and sum(e["lifecycle"] == "human_approved" for e in toen["elementen"]) == 1
    assert "trace" not in toen["elementen"][0]
    assert len((await store.weergave(lid))["elementen"]) == 1   # er veranderde niets


async def test_een_artikel_toont_de_prullenbak_van_zijn_lid_en_zet_terug():
    lid, _ = await beoordeeld_lid()
    await store.verwijder_weergave(lid, revisies(await store.weergave(lid)), "b")
    art = snapshot()
    view = await store.weergave(art)
    assert view["prullenbak"]["weergave_iri"] == ONE and view["prullenbak"]["terugzetbaar"]
    await bak.zet_terug(view["prullenbak"]["id"], "c")
    assert len((await store.weergave(art))["elementen"]) == 2


async def test_de_impact_noemt_markeringen_beoordeeld_en_wie_ernaar_verwijst():
    lid, uit = await beoordeeld_lid()
    eid = uit["elementen"][0]["id"]
    nu = db.utcnow()
    async with db.get_engine().begin() as conn:
        for bid, naam in (("b1", "belastingschuldige"), ("b2", "aanslag"), ("rb", "verschuldigd")):
            await conn.execute(insert(db.begrippen).values(id=bid, werkgebied_id="w", inhoud={"naam": naam},
                                                           aangemaakt_door="a", aangemaakt=nu, gewijzigd=nu))
        for kid, bid in (("k1", "b1"), ("k2", "b2")):
            await conn.execute(insert(db.begrip_koppelingen).values(
                id=kid, begrip_id=bid, werkgebied_id="w", element_id=eid, rol="duiding", bewijs={},
                toegevoegd_door="a", toegevoegd=nu))
        await conn.execute(insert(db.regels).values(id="r1", werkgebied_id="w", inhoud={"regelbegrip_id": "rb"},
                                                    aangemaakt_door="a", aangemaakt=nu, gewijzigd=nu))
        await conn.execute(insert(db.regel_dragers).values(id="d1", regel_id="r1", werkgebied_id="w", element_id=eid,
                                                           rol="grondslag", bewijs={}, toegevoegd_door="a", toegevoegd=nu))

    impact = await store.verwijder_impact(lid)

    assert (impact["lagen"], impact["markeringen"], impact["beoordeeld"], impact["relaties"]) == (1, 2, 1, 0)
    assert [b["naam"] for b in impact["begrippen"]] == ["belastingschuldige", "aanslag"]
    assert impact["regels"] == [{"id": "r1", "werkgebied_id": "w", "naam": "verschuldigd"}]
    assert impact["bewaartermijn_dagen"] == 30
    assert len((await store.weergave(lid))["elementen"]) == 2   # alleen lezen

    # Na verwijderen zeggen de koppeling en de drager "bron verwijderd", met de prullenbak; na legen zonder.
    pid = (await store.verwijder_weergave(lid, revisies(await store.weergave(lid)), "jurist-b"))["prullenbak"]["id"]
    from app import begrip_store, regel_store
    async with db.get_engine().connect() as conn:
        koppelingen = await begrip_store._koppelingen_van(conn, "w")
        dragers = await regel_store._dragers_van(conn, "w", ["r1"])
    assert {k["actualiteit"] for k in koppelingen} == {"verdwenen"}
    assert all(k["bron_verwijderd"]["prullenbak_id"] == pid and k["bron_verwijderd"]["door"] == "jurist-b"
               and k["bron_verwijderd"]["weergave"] == ONE for k in koppelingen)
    assert dragers["r1"][0]["bron_verwijderd"]["prullenbak_id"] == pid
    await bak.legen("beheerder", pid)
    async with db.get_engine().connect() as conn:
        [d] = (await regel_store._dragers_van(conn, "w", ["r1"]))["r1"]
    assert d["bron_verwijderd"]["prullenbak_id"] is None and d["bron_verwijderd"]["op"]


async def test_legen_is_een_beheeractie_die_de_bewaartermijn_respecteert(monkeypatch):
    lid, _ = await beoordeeld_lid()
    pid = (await store.verwijder_weergave(lid, revisies(await store.weergave(lid)), "b"))["prullenbak"]["id"]
    assert (await bak.legen("beheerder"))["geleegd"] == 0          # binnen de termijn: niets
    [item] = await bak.lijst()
    assert item["id"] == pid and not item["over_termijn"]
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.annotatie_v2_prullenbak).values(
            verwijderd_op=db.utcnow() - bak.bewaartermijn() - bak.timedelta(minutes=1)))
    assert (await bak.lijst())[0]["over_termijn"]
    assert (await bak.legen("beheerder"))["geleegd"] == 1
    assert not await bak.lijst()
    [regel] = await audit("prullenbak-geleegd")
    assert regel["actor"] == "beheerder" and regel["detail"]["prullenbak_id"] == pid
    view = await store.weergave(lid)
    assert view["prullenbak"] is None and view["verwijderd"]["op"]  # definitief weg, maar wel te lezen
    with pytest.raises(HTTPException) as exc:
        await bak.zet_terug(pid, "c")
    assert exc.value.status_code == 404


async def test_endpoints_impact_terugzetten_en_legen(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from conftest import maak_testgebruikers
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    monkeypatch.setenv("WETSANALYSE_ADMIN_TOKENS", "adm:admin-token")
    get_settings.cache_clear()
    await maak_testgebruikers("v2-reviewer")
    from app.main import app

    lid, _ = await beoordeeld_lid()
    h = {"X-User-Id": "v2-reviewer"}
    body = {"bron_iri": ONE, "snapshot_id": lid["snapshot_id"], "verwachte_revisies": revisies(await store.weergave(lid))}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/v1/annotatie/weergave/verwijder-impact", json=body, headers=h)
        assert r.status_code == 200, r.text
        assert (r.json()["markeringen"], r.json()["beoordeeld"]) == (2, 1)
        r = await client.post("/v1/annotatie/weergave/verwijder", json=body, headers=h)
        pid = r.json()["prullenbak"]["id"]
        assert (await client.get(f"/v1/annotatie/prullenbak/{pid}", headers=h)).json()["markeringen"] == 2
        # Een nieuwe annotatie ertussen: 409 met wat er nu ligt.
        await store.batch(request(lid, [element(lid)], batch_id="nieuw"), lid, "lex")
        r = await client.post(f"/v1/annotatie/prullenbak/{pid}/terugzetten", headers=h)
        assert r.status_code == 409 and r.json()["detail"]["fout"] == "nieuwe_laag"
        nieuw = await store.weergave(lid)
        await store.verwijder_weergave(lid, revisies(nieuw), "b")
        # De oudste ligt er nog; de nieuwe ook. Terugzetten van de eerste kan nu.
        r = await client.post(f"/v1/annotatie/prullenbak/{pid}/terugzetten", headers=h)
        assert r.status_code == 200, r.text
        assert len((await store.weergave(lid))["elementen"]) == 2
        # Legen alleen met het beheertoken.
        assert (await client.post("/v1/admin/annotatie/prullenbak/legen", json={})).status_code == 401
        adm = {"Authorization": "Bearer admin-token"}
        lijst = (await client.get("/v1/admin/annotatie/prullenbak", headers=adm)).json()
        assert lijst["bewaartermijn_dagen"] == 30 and len(lijst["items"]) == 1
        r = await client.post("/v1/admin/annotatie/prullenbak/legen", json={"alles": True}, headers=adm)
        assert r.status_code == 200 and r.json()["geleegd"] == 1
