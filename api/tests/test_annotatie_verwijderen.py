"""Een annotatie verwijderen: uit Postgres én uit de graaf, voor iedereen, met audit en revisietoets."""
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app import db
from app import annotatie_v2_store as store
from app import graaf_projectie_v2 as projectie
from app.config import get_settings
from app.graaf_projectie_v2 import REGISTER, graph_iri, laag_iri
from graafdb_fake import installeer
from test_annotatie_v2 import ART, ONE, TWO, element, request, snapshot


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
        return [r.detail for r in (await conn.execute(select(db.annotatie_v2_audit)
                                                      .where(db.annotatie_v2_audit.c.actie == actie))).all()]


async def dekkingrijen() -> list[dict]:
    async with db.get_engine().connect() as conn:
        return [dict(r) for r in (await conn.execute(select(db.annotatie_v2_dekking))).mappings().all()]


def over_beide_leden(snap: dict) -> dict:
    """Een markering met ankers in lid 1 én lid 2: haar eigenaar is het artikel."""
    first, second = element(snap), element(snap, TWO, 0, 4)
    return dict(klasse="Voorwaarde", tekst=first["tekst"] + " " + second["tekst"],
                ankers=[*first["ankers"], *second["ankers"]])


def in_register(nep, laag_id: str) -> bool:
    return any(True for _ in nep.ds.graph(REGISTER).triples((laag_iri(laag_id), None, None)))


async def test_verwijdert_de_lagen_in_beeld_met_elementen_dekking_audit_en_graaf(monkeypatch):
    nep = installeer(monkeypatch)
    art, lid = snapshot(), snapshot(ONE)
    a = await store.batch(request(art, [over_beide_leden(art), element(art, TWO, 0, 4)],
                                  dekking={"voltooid": True, "bereik": [ONE, TWO], "parent_context": True}), art, "a")
    await store.batch(request(lid, [element(lid)], batch_id="lid", revisions={ONE: 1}), lid, "b")
    ids = [l["id"] for l in (await store.weergave(art))["lagen"]]
    assert len(ids) == 3
    for laag_id in ids:
        assert await projectie.projecteer(laag_id)
        assert len(nep.ds.graph(graph_iri(laag_id)))

    view = await store.weergave(art)
    uit = await store.verwijder_weergave(art, revisies(view), "c")

    assert uit == {"verwijderd": {"lagen": 3, "elementen": 3}, "graaf": "verwijderd"}
    na = await store.weergave(art)
    assert not na["lagen"] and not na["elementen"] and na["verwijderd"]["op"]
    assert not await dekkingrijen()
    assert not (await store.dekking(art))["voltooid"]
    for laag_id in ids:
        assert not len(nep.ds.graph(graph_iri(laag_id))) and not in_register(nep, laag_id)
    detail = sorted(await audit("laag-verwijderd"), key=lambda d: d["bron_iri"])
    assert [d["bron_iri"] for d in detail] == [ART, ONE, TWO]
    assert all(d["weergave"] == ART and len(d["elementen"]) == 1 for d in detail)
    # De audit is append-only: de regels van vóór het verwijderen blijven staan.
    async with db.get_engine().connect() as conn:
        acties = [r.actie for r in (await conn.execute(select(db.annotatie_v2_audit))).all()]
    assert len(acties) > len(detail)


async def test_een_lid_verwijderen_laat_de_laag_van_het_artikel_staan_en_snoeit_diens_dekking():
    art, lid = snapshot(), snapshot(ONE)
    await store.batch(request(art, [over_beide_leden(art), element(art, TWO, 0, 4)],
                              dekking={"voltooid": True, "bereik": [ONE, TWO], "parent_context": True}), art, "a")
    await store.batch(request(lid, [element(lid, start=7, end=11)], batch_id="lid", revisions={ONE: 1}), lid, "b")

    uit = await store.verwijder_weergave(lid, revisies(await store.weergave(lid)), "c")

    assert uit["verwijderd"] == {"lagen": 1, "elementen": 1}
    assert uit["graaf"] == "uit"
    na = await store.weergave(art)
    assert sorted(l["bron_iri"] for l in na["lagen"]) == [ART, TWO]
    assert len(na["elementen"]) == 2
    # De markering van het artikel die in lid 1 valt, blijft een verwijzing in de lidweergave.
    lid_na = await store.weergave(lid)
    assert not lid_na["elementen"] and len(lid_na["verwijzingen"]) == 1
    [rij] = await dekkingrijen()
    assert rij["bron_iri"] == ART
    assert rij["inhoud"]["bereik"] == [TWO] and not rij["inhoud"]["voltooid"]
    assert not (await store.dekking(lid))["voltooid"]


async def test_een_tussentijdse_wijziging_geeft_412_en_verwijdert_niets():
    lid = snapshot(ONE)
    await store.batch(request(lid, [element(lid)]), lid, "a")
    with pytest.raises(HTTPException) as exc:
        await store.verwijder_weergave(lid, {ONE: 0}, "b")
    assert exc.value.status_code == 412
    assert len((await store.weergave(lid))["elementen"]) == 1
    assert not await audit("laag-verwijderd")


async def test_niets_om_te_verwijderen_is_404():
    with pytest.raises(HTTPException) as exc:
        await store.verwijder_weergave(snapshot(ONE), {}, "a")
    assert exc.value.status_code == 404


async def test_een_afgeronde_laag_van_een_ander_is_ook_te_verwijderen():
    lid = snapshot(ONE)
    uit = await store.batch(request(lid, [element(lid)]), lid, "a")
    laag = uit["lagen"][0]
    from app.annotatie_v2_contracts import Beslissing
    await store.beslis(uit["elementen"][0]["id"], Beslissing(type="approve", snapshot_id=lid["snapshot_id"],
                                                             verwachte_revisies={ONE: 1}), lid, "a")
    await store.zet_status(laag["id"], "geaccordeerd", 2, "a")
    await store.verwijder_weergave(lid, revisies(await store.weergave(lid)), "b")
    assert not (await store.weergave(lid))["lagen"]


async def test_opnieuw_annoteren_na_verwijderen_begint_schoon():
    lid = snapshot(ONE)
    await store.batch(request(lid, [element(lid)], dekking={"voltooid": True, "bereik": [ONE]}), lid, "a")
    await store.verwijder_weergave(lid, revisies(await store.weergave(lid)), "b")
    assert not (await store.dekking(lid))["voltooid"]

    nieuw = await store.batch(request(lid, [element(lid, start=7, end=11)], batch_id="nieuw"), lid, "a")
    assert nieuw["lagen"][0]["revisie"] == 1
    view = await store.weergave(lid)
    assert len(view["elementen"]) == 1 and view["verwijderd"] is None


async def test_haperende_graaf_meldt_volgt_en_de_lus_ruimt_de_wees_op(monkeypatch):
    nep = installeer(monkeypatch)
    lid = snapshot(ONE)
    uit = await store.batch(request(lid, [element(lid)]), lid, "a")
    laag_id = uit["lagen"][0]["id"]
    assert await projectie.projecteer(laag_id)

    nep.storing(True)
    weg = await store.verwijder_weergave(lid, revisies(await store.weergave(lid)), "b")
    assert weg["graaf"] == "volgt"
    assert not (await store.weergave(lid))["lagen"]  # Postgres is de waarheid, en die is al bijgewerkt

    nep.storing(False)
    assert in_register(nep, laag_id)
    assert await projectie.verwijder_verweesde_projecties() == 1
    assert not len(nep.ds.graph(graph_iri(laag_id))) and not in_register(nep, laag_id)


async def test_endpoint_verwijdert_op_de_bewaarde_bronstand_zonder_de_brongraaf(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from app import annotatie_v2
    from conftest import maak_testgebruikers
    monkeypatch.setenv("ANNOTATIE_CONTRACT_VERSIE", "2")
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    get_settings.cache_clear()
    await maak_testgebruikers("v2-reviewer")
    from app.main import app

    art = snapshot()
    await store.batch(request(art, [over_beide_leden(art)]), art, "a")
    lid = snapshot(ONE)

    async def onbereikbaar(goal):
        raise HTTPException(503, "Brongraaf niet bereikbaar.")
    monkeypatch.setattr(annotatie_v2, "_resolve_bron", onbereikbaar)
    headers = {"X-User-Id": "v2-reviewer"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        body = {"bron_iri": ONE, "snapshot_id": lid["snapshot_id"], "verwachte_revisies": {}}
        # Lid 1 heeft zelf geen laag; de markering is van het artikel.
        assert (await client.post("/v1/annotatie/weergave/verwijder", json=body, headers=headers)).status_code == 404
        body = {"bron_iri": ART, "snapshot_id": art["snapshot_id"], "verwachte_revisies": {ART: 1}}
        assert (await client.post("/v1/annotatie/weergave/verwijder", json=body)).status_code == 401
        r = await client.post("/v1/annotatie/weergave/verwijder", json=body, headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["verwijderd"] == {"lagen": 1, "elementen": 1}
        # Een onbekende bronstand kan alleen via de brongraaf; die is hier weg.
        body["snapshot_id"] = "onbekend"
        assert (await client.post("/v1/annotatie/weergave/verwijder", json=body, headers=headers)).status_code == 503
    [detail] = await audit("laag-verwijderd")
    assert detail["bron_iri"] == ART


async def test_endpoint_weigert_een_verouderde_bronstand(monkeypatch):
    from httpx import ASGITransport, AsyncClient
    from app import annotatie_v2
    from conftest import maak_testgebruikers
    monkeypatch.setenv("ANNOTATIE_CONTRACT_VERSIE", "2")
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    get_settings.cache_clear()
    await maak_testgebruikers("v2-reviewer")
    from app.main import app

    async def resolve(goal):
        return snapshot(goal.get("bron_iri", ART), second="Nieuw")
    monkeypatch.setattr(annotatie_v2, "_resolve_bron", resolve)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/v1/annotatie/weergave/verwijder", headers={"X-User-Id": "v2-reviewer"},
                              json={"bron_iri": ART, "snapshot_id": "nooit-bewaard", "verwachte_revisies": {}})
    assert r.status_code == 409
