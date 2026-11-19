"""Begrippen onder echte PostgreSQL-races: het werkgebiedslot houdt de primaire duiding uniek, het
begripslot laat precies één wijziging door.

Zelfde opzet als `test_werkgebieden_postgres.py`: een eigen schema per test. SQLite kan
`SELECT … FOR UPDATE` niet bewijzen.
"""
import asyncio
import os

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app import annotatie_v2_store as annotaties, begrip_store as store, db, werkgebied_store
from app.begrip_contracts import BegripInhoud, BegripInvoer, BegripWijziging, KoppelInvoer
from app.werkgebied_contracts import BronselectieInvoer, WerkgebiedInvoer
from gedeelde_bron import ART, ONE, element, request, snapshot

from conftest import postgres_schema as eigen_schema

pytestmark = pytest.mark.skipif(not os.getenv("ANNOTATIE_TEST_DSN"), reason="PostgreSQL-test DSN ontbreekt")


@pytest.fixture(autouse=True)
async def postgres_schema():
    """Elke test een eigen schema (`conftest.postgres_schema`, testplan api V7)."""
    async for _ in eigen_schema("begrip_test"):
        yield


async def resolve(doel):
    return snapshot(doel.get("bron_iri") or ART)


async def _opzet() -> tuple[dict, str]:
    snap = snapshot()
    uit = await annotaties.batch(request(snap, [element(snap, ONE)]), snap, "lex")
    wg = await werkgebied_store.maak(WerkgebiedInvoer(naam="A"), "a")
    bron = {"bron_iri": ART, "label": "Artikel 9", "bwb_id": "BWBR0004770", "snapshot_id": snap["snapshot_id"],
            "bron_hash": ""}
    await werkgebied_store.voeg_bron_toe(wg["id"], BronselectieInvoer(verwachte_revisie=1, bron_iri=ART), bron, "a")
    return await werkgebied_store.haal(wg["id"]), uit["elementen"][0]["id"]


def _invoer(naam: str, eid: str) -> BegripInvoer:
    """Een begrip rust altijd op een annotatie (422 `geen_passage`): hier het element als context, dat de primaire
    duiding vrij laat."""
    return BegripInvoer(inhoud=BegripInhoud(naam=naam), element_ids=[eid], rol="context")


async def test_gelijktijdig_dezelfde_duiding_aan_twee_begrippen_levert_er_een():
    wg, eid = await _opzet()
    a = await store.maak(wg, _invoer("A", eid), "a", resolve)
    b = await store.maak(wg, _invoer("B", eid), "b", resolve)
    results = await asyncio.gather(
        store.koppel(wg, a["id"], KoppelInvoer(verwachte_revisie=1, element_ids=[eid]), "a", resolve),
        store.koppel(wg, b["id"], KoppelInvoer(verwachte_revisie=1, element_ids=[eid]), "b", resolve),
        return_exceptions=True)
    fouten = [r for r in results if isinstance(r, HTTPException)]
    assert len(fouten) == 1 and fouten[0].status_code == 409 and fouten[0].detail["fout"] == "al_primair"
    k = db.begrip_koppelingen
    async with db.get_engine().connect() as conn:
        aantal = len((await conn.execute(select(k.c.id).where(k.c.element_id == eid, k.c.rol == "duiding"))).all())
    assert aantal == 1


async def test_twee_gelijktijdige_wijzigingen_van_een_begrip_precies_een_412():
    wg, eid = await _opzet()
    b = await store.maak(wg, _invoer("A", eid), "a", resolve)
    results = await asyncio.gather(
        store.wijzig(wg["id"], b["id"], BegripWijziging(verwachte_revisie=1, inhoud=BegripInhoud(naam="B")), "a"),
        store.wijzig(wg["id"], b["id"], BegripWijziging(verwachte_revisie=1, inhoud=BegripInhoud(naam="C")), "b"),
        return_exceptions=True)
    fouten = [r for r in results if isinstance(r, HTTPException)]
    assert len(fouten) == 1 and fouten[0].status_code == 412
    assert (await store.haal(wg["id"], b["id"]))["revisie"] == 2


async def test_twee_gelijktijdige_starts_op_hetzelfde_manifest_geven_een_run():
    from app import begrippen_run_store as runs
    from gedeelde_bron import TWO

    snap = snapshot()
    await annotaties.batch(request(snap, [element(snap, TWO, 0, 4)], batch_id="tweede", revisions={}), snap, "lex")
    wg, _ = await _opzet()
    uit = await asyncio.gather(runs.start(wg, "a", resolve), runs.start(wg, "b", resolve))
    assert uit[0][0]["id"] == uit[1][0]["id"]
    assert sorted(n for _, n in uit) == [False, True]


async def test_twee_gelijktijdige_akkoorden_op_een_groep_maken_een_begrip():
    """Fase D: akkoord is één transactie onder het werkgebiedslot. Twee jurists tegelijk op dezelfde
    groep: één begrip, de ander krijgt 409 met dat begrip – geen tweede begrip, geen halve stand."""
    from app import begrippen_run_store as runs
    from app.begrippen_run_contracts import Akkoord, UitkomstInvoer
    from gedeelde_bron import TWO

    snap = snapshot()
    tweede = await annotaties.batch(request(snap, [element(snap, TWO, 0, 4)], batch_id="tweede", revisions={}),
                                    snap, "lex")
    wg, eid = await _opzet()
    run, _ = await runs.start(wg, "a", resolve)
    leden = [eid, tweede["elementen"][0]["id"]]
    await runs.zet_uitkomst(wg["id"], run["id"], UitkomstInvoer(manifest_id=run["manifest_id"], groepen=[
        {"id": "Gaaa111", "leden": leden, "aandacht": "groen", "voorstel": {"naam": "alfa"}}]), "graph-qa")
    akkoord = Akkoord(groep_ids=["Gaaa111"], naam="Alfa")
    uit = await asyncio.gather(runs.akkoord(wg, akkoord, "a", resolve), runs.akkoord(wg, akkoord, "b", resolve),
                               return_exceptions=True)
    fouten = [u for u in uit if isinstance(u, HTTPException)]
    goed = [u for u in uit if isinstance(u, dict)]
    assert len(goed) == 1 and len(fouten) == 1 and fouten[0].status_code == 409
    assert fouten[0].detail["begrippen"] == {"Gaaa111": goed[0]["begrip"]["id"]}
    assert [b["id"] for b in await store.lijst(wg["id"])] == [goed[0]["begrip"]["id"]]



async def test_projectie_wacht_op_een_lopende_schrijftransactie(monkeypatch):
    """Het `commit`-event valt vóór de COMMIT, dus de projectie kan starten terwijl de schrijver nog bezig
    is (fase F3). Ze wacht met een leesslot op het werkgebied en projecteert dan de nieuwe stand."""
    from rdflib import Literal

    from app import begrip_projectie as bp
    from graafdb_fake import installeer

    nep = installeer(monkeypatch)
    wg, eid = await _opzet()
    b = await store.maak(wg, _invoer("Oud", eid), "a", resolve)
    async with store._gewijzigd(wg["id"], b["id"], b["revisie"], "a", "begrip-gewijzigd", {}) as (_c, _r, stand):
        stand["inhoud"] = {**stand["inhoud"], "naam": "Nieuw"}
        taak = asyncio.create_task(bp.projecteer(wg["id"]))
        await asyncio.sleep(0.5)
        assert not taak.done()                          # wacht op het slot van de schrijver
    await taak
    g = nep.ds.graph(bp.graph_iri(wg["id"]))
    assert (bp.begrip_iri(b["id"]), bp.SKOS.prefLabel, Literal("Nieuw", lang="nl")) in g
    assert (bp.begrip_iri(b["id"]), bp.SKOS.prefLabel, Literal("Oud", lang="nl")) not in g


async def test_projectie_direct_na_de_commit(monkeypatch):
    from rdflib import Literal

    from app import begrip_projectie as bp
    from graafdb_fake import installeer

    nep = installeer(monkeypatch)
    wg, eid = await _opzet()
    b = await store.maak(wg, _invoer("Oud", eid), "a", resolve)
    bp._geschreven.clear()
    bp.activeer(True)
    try:
        await store.wijzig(wg["id"], b["id"], BegripWijziging(verwachte_revisie=b["revisie"],
                                                              inhoud=BegripInhoud(naam="Nieuw")), "a")
        await asyncio.gather(*list(bp._taken))
    finally:
        await bp.stop()
    assert (bp.begrip_iri(b["id"]), bp.SKOS.prefLabel, Literal("Nieuw", lang="nl")) in nep.ds.graph(bp.graph_iri(wg["id"]))
