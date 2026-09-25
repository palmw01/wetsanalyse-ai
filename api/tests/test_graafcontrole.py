"""De graafcontrole: meldt hij elke manier waarop de annotatiegraaf uit de pas kan lopen?

De graaf wordt hier gevuld door de échte projectie (`graaf_projectie_v2.projecteer`) uit een échte
store-batch; daarna muteren de tests de graaf of Postgres en eisen ze dat de controle het ziet.
Een controle die alleen "in orde" kan zeggen, bewijst niets.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from rdflib import Literal, URIRef
from sqlalchemy import update

from app import annotatie_v2_store as store
from app import db
from app import graaf_projectie_v2 as projectie
from app.annotatie_v2_contracts import Beslissing
from app.config import get_settings
from app.graafcontrole import controleer
from app.graaf_projectie_v2 import JAS, REGISTER, element_iri, graph_iri, laag_iri
from graafdb_fake import installeer
from test_annotatie_v2 import ONE, element, request, snapshot


@pytest.fixture
async def omgeving(monkeypatch):
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    nep = installeer(monkeypatch)
    snap = snapshot(ONE)
    uit = await store.batch(request(snap, [element(snap)]), snap, "a")
    laag_id, eid = uit["lagen"][0]["id"], uit["elementen"][0]["id"]
    yield nep, snap, laag_id, eid
    get_settings.cache_clear()
    await db.dispose_engine()


async def _geprojecteerd(omgeving):
    import httpx
    nep, snap, laag_id, eid = omgeving
    assert await projectie.projecteer(laag_id)
    async with httpx.AsyncClient() as client:
        await projectie.zorg_voor_vocabulaire(client)
    return nep, snap, laag_id, eid


async def test_een_geprojecteerde_laag_is_in_orde(omgeving):
    await _geprojecteerd(omgeving)
    r = await controleer()
    assert r["graaf_beschikbaar"] and r["in_orde"] is True, r
    assert r["lagen"] == 1 and not r["afwijkingen"] and not r["verweesd"] and not r["achterstand"]
    assert r["invarianten"] == {"geen_bwb_subject": True, "geen_bwb_predicaat": True, "geen_schema_axioma": True}
    assert r["vocabulaire"]["aanwezig"] is True
    assert r["shacl"]["beschikbaar"] is True
    assert r["shacl"]["conform"] is True and not r["shacl"]["bevindingen"]


async def test_een_beslissing_die_nog_niet_geprojecteerd_is_heet_achterstand_geen_afwijking(omgeving):
    nep, snap, laag_id, eid = await _geprojecteerd(omgeving)
    await store.beslis(eid, Beslissing(type="approve", snapshot_id=snap["snapshot_id"],
                                       verwachte_revisies={ONE: 1}), snap, "b")
    r = await controleer()
    assert [a["laag_id"] for a in r["achterstand"]] == [laag_id]
    assert r["in_orde"] is True and not r["afwijkingen"]
    await projectie.projecteer(laag_id)
    assert (await controleer())["achterstand"] == []


async def test_gewijzigde_inhoud_in_de_graaf_wordt_gezien(omgeving):
    nep, _snap, laag_id, eid = await _geprojecteerd(omgeving)
    g = nep.ds.graph(graph_iri(laag_id))
    g.set((element_iri(eid), JAS.tekst, Literal("iets anders")))
    r = await controleer(shacl=False)
    assert {a["soort"] for a in r["afwijkingen"]} == {"inhoud_wijkt_af"} and r["in_orde"] is False


async def test_ontbrekend_element_in_de_graaf_wordt_gezien(omgeving):
    nep, _snap, laag_id, eid = await _geprojecteerd(omgeving)
    g = nep.ds.graph(graph_iri(laag_id))
    for t in list(g.triples((element_iri(eid), None, None))):
        g.remove(t)
    r = await controleer(shacl=False)
    assert "inhoud_wijkt_af" in {a["soort"] for a in r["afwijkingen"]}


async def test_registerrevisie_en_graphrevisie_worden_apart_gemeld(omgeving):
    nep, _snap, laag_id, _eid = await _geprojecteerd(omgeving)
    nep.ds.graph(REGISTER).set((laag_iri(laag_id), JAS.revisie, Literal(9)))
    nep.ds.graph(graph_iri(laag_id)).set((laag_iri(laag_id), JAS.revisie, Literal(7)))
    soorten = {a["soort"] for a in (await controleer(shacl=False))["afwijkingen"]}
    assert {"registerrevisie", "graphrevisie"} <= soorten


async def test_ontbrekende_graph_en_ontbrekende_registratie(omgeving):
    nep, _snap, laag_id, _eid = await _geprojecteerd(omgeving)
    nep.ds.remove_graph(nep.ds.graph(graph_iri(laag_id)))
    assert "graph_ontbreekt" in {a["soort"] for a in (await controleer(shacl=False))["afwijkingen"]}
    await projectie.projecteer(laag_id)
    for t in list(nep.ds.graph(REGISTER).triples((laag_iri(laag_id), None, None))):
        nep.ds.graph(REGISTER).remove(t)
    assert "niet_in_register" in {a["soort"] for a in (await controleer(shacl=False))["afwijkingen"]}


async def test_verweesde_registratie_en_graph_worden_gemeld(omgeving):
    nep, *_ = await _geprojecteerd(omgeving)
    wees = "weeslaag"
    nep.ds.graph(REGISTER).add((laag_iri(wees), JAS.laagId, Literal(wees)))
    nep.ds.graph(REGISTER).add((laag_iri(wees), JAS.inGraaf, graph_iri(wees)))
    nep.ds.graph(REGISTER).add((laag_iri(wees), JAS.revisie, Literal(1)))
    nep.ds.graph(graph_iri(wees)).add((laag_iri(wees), JAS.laagId, Literal(wees)))
    r = await controleer(shacl=False)
    assert {v["soort"] for v in r["verweesd"]} == {"registratie", "graph"} and r["in_orde"] is False


async def test_een_wettekst_subject_in_een_laag_breekt_de_invariant(omgeving):
    nep, _snap, laag_id, _eid = await _geprojecteerd(omgeving)
    nep.ds.graph(graph_iri(laag_id)).add((URIRef(ONE), URIRef("urn:bwb-ns:tekst"), Literal("vals")))
    r = await controleer(shacl=False)
    assert r["invarianten"]["geen_bwb_subject"] is False
    assert r["invarianten"]["geen_bwb_predicaat"] is False
    assert r["in_orde"] is False


async def test_shacl_ziet_een_klasse_buiten_de_dertien(omgeving):
    pytest.importorskip("pyshacl")
    nep, _snap, laag_id, eid = await _geprojecteerd(omgeving)
    nep.ds.graph(graph_iri(laag_id)).set((element_iri(eid), JAS.klasseNaam, Literal("Termijn")))
    r = await controleer()
    assert r["shacl"]["conform"] is False
    assert {b["niveau"] for b in r["shacl"]["bevindingen"]} == {"jas_model"}


async def test_een_onbereikbare_graaf_is_nooit_in_orde(omgeving):
    nep, *_ = await _geprojecteerd(omgeving)
    nep.storing()
    r = await controleer()
    assert r["graaf_beschikbaar"] is False and r["in_orde"] is None and r["reden"] == "graaf_onbeschikbaar"


async def test_zonder_graaf_geconfigureerd_zegt_hij_dat(omgeving, monkeypatch):
    monkeypatch.setenv("GRAPHDB_URL", "")
    get_settings.cache_clear()
    r = await controleer()
    assert r["graaf_beschikbaar"] is False and r["in_orde"] is None and r["reden"] == "graafprojectie_uit"


async def test_het_endpoint_is_alleen_voor_beheerders(omgeving, monkeypatch):
    await _geprojecteerd(omgeving)
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    monkeypatch.setenv("WETSANALYSE_ADMIN_TOKENS", "beheer:geheim")
    get_settings.cache_clear()
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        assert (await ac.get("/v1/admin/annotatie/graafcontrole")).status_code in (401, 403)
        r = await ac.get("/v1/admin/annotatie/graafcontrole", params={"shacl": "false"},
                         headers={"Authorization": "Bearer geheim"})
    assert r.status_code == 200 and r.json()["in_orde"] is True


async def test_de_lichte_controle_logt_de_afwijking(omgeving, caplog):
    import logging

    from app.graafcontrole import log_stand
    nep, _snap, laag_id, eid = await _geprojecteerd(omgeving)
    nep.ds.graph(graph_iri(laag_id)).set((element_iri(eid), JAS.tekst, Literal("x")))
    with caplog.at_level(logging.INFO, logger="app.graafcontrole"):
        await log_stand()
    rec = next(r for r in caplog.records if r.getMessage() == "annotatie_graafcontrole")
    assert rec.annotatie_graaf_afwijking == 1 and rec.levelname == "WARNING"


async def test_achterstand_ook_na_een_postgres_wijziging_zonder_projectie(omgeving):
    """Staat `geprojecteerd_revisie` achter, dan vergelijkt hij niet – de lus haalt dat in."""
    nep, _snap, laag_id, _eid = await _geprojecteerd(omgeving)
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.annotatie_v2_lagen).where(db.annotatie_v2_lagen.c.id == laag_id)
                           .values(revisie=5))
    r = await controleer(shacl=False)
    assert r["achterstand"] and not r["afwijkingen"]


async def test_shacl_beschikbaarheid_ook_zonder_lagen(monkeypatch):
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    installeer(monkeypatch)
    try:
        assert (await controleer())["shacl"]["beschikbaar"] is True
    finally:
        get_settings.cache_clear()
        await db.dispose_engine()


async def test_een_ontbrekende_vocabulaire_is_een_afwijking(omgeving):
    nep, *_ = await _geprojecteerd(omgeving)
    nep.ds.remove_graph(nep.ds.graph(projectie.VOCABULAIRE))
    r = await controleer(shacl=False)
    assert r["vocabulaire"]["aanwezig"] is False and r["in_orde"] is False


async def test_dekking_uit_de_batch_komt_in_de_graaf_en_de_controle_bouwt_hem_mee(monkeypatch):
    """De projectie en de controle lezen de dekking via dezelfde `laag_invoer`; anders zou elke laag
    met dekking als 'inhoud wijkt af' gemeld worden."""
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    nep = installeer(monkeypatch)
    try:
        snap = snapshot(ONE)
        meting = {"dimensies": {"tijd": "uitgevoerd"}, "ongedekt": [{"tekst": "Alfa", "start": 7, "eind": 11}]}
        uit = await store.batch(request(snap, [element(snap)], dekking={"voltooid": True, "bereik": [ONE],
                                                                     "structureel": {ONE: meting}}), snap, "a")
        laag_id = uit["lagen"][0]["id"]
        await _geprojecteerd((nep, snap, laag_id, uit["elementen"][0]["id"]))
        assert list(nep.ds.graph(graph_iri(laag_id)).objects(laag_iri(laag_id), JAS.dekking))
        r = await controleer()
        assert r["in_orde"] is True, r
    finally:
        get_settings.cache_clear()
        await db.dispose_engine()
