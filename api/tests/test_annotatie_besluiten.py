"""Wat een besluit vastlegt en teruggeeft: één definitie van beoordeeld, een audit zonder gat, een toelichting die
bij de klasse past, en compacte antwoorden met bulk per laag (fase 6 na de e2e-wetsanalyse)."""
import json

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app import annotatie_export, annotatie_statistiek, db
from app import annotatie_v2_store as store
from app.annotatie_v2_contracts import AFGEHANDELD, BEOORDEELD, Batch, Beslissing, Laagbesluiten
from app.graaf_projectie_v2 import bouw_graaf
from tests.test_annotatie_v2 import ONE, TWO, element, request, snapshot

RUN = {"ronde": 1, "model": "m", "agent_versie": "v", "tijd": "2026-11-05T10:00:00+00:00",
       "instellingen": {"classifier": "x", "meting": {"taal_model": "nl", "fasen": [{"fase": "f" * 2000}] * 20}}}


@pytest.fixture(autouse=True)
async def database():
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    yield
    await db.dispose_engine()


def besluit(snap, laag, type_, **extra):
    return Beslissing.model_validate({"type": type_, "snapshot_id": snap["snapshot_id"],
                                      "verwachte_revisies": {laag["bron_iri"]: laag["revisie"]}, **extra})


async def voorstel(snap, *els, batch_id="b", run=None):
    uit = await store.batch(request(snap, list(els), batch_id=batch_id, run=run or RUN), snap, "agent")
    return uit["lagen"][0], uit["elementen"]


async def eigen(snap):
    uit = await store.batch(request(snap, [element(snap, toelichting="Mijn duiding")], batch_id="eigen"), snap, "jurist", mens=True)
    return uit["lagen"][0], uit["elementen"][0]


# --- B19, B24: één definitie van beoordeeld ------------------------------------------------------

async def test_een_laag_met_een_aangepast_element_rondt_af():
    snap = snapshot(ONE)
    laag, [el] = await voorstel(snap, element(snap, toelichting="t"))
    uit = await store.beslis(el["id"], besluit(snap, laag, "edit", wijziging={"klasse": "Voorwaarde"}), snap, "jurist")
    assert uit["element"]["lifecycle"] == "edited"
    klaar = await store.zet_status(laag["id"], "geaccordeerd", uit["lagen"][0]["revisie"], "jurist", snap)
    assert klaar["status"] == "geaccordeerd"


async def test_het_overzicht_telt_een_aangepast_element_niet_als_open():
    snap = snapshot(ONE)
    laag, [el] = await voorstel(snap, element(snap))
    await store.beslis(el["id"], besluit(snap, laag, "edit", wijziging={"klasse": "Voorwaarde"}), snap, "jurist")
    [rij] = await store.overzicht(None, "", 10, 0)
    assert rij["te_beoordelen"] == 0
    assert "edited" in BEOORDEELD and "rejected" in AFGEHANDELD - BEOORDEELD


async def test_een_voorstel_houdt_afronden_nog_steeds_tegen():
    snap = snapshot(ONE)
    laag, _ = await voorstel(snap, element(snap))
    with pytest.raises(HTTPException) as exc:
        await store.zet_status(laag["id"], "geaccordeerd", laag["revisie"], "jurist", snap)
    assert exc.value.status_code == 409


# --- B18: een eigen markering heeft een beslissingsregel --------------------------------------

async def test_een_eigen_markering_draagt_haar_beslissingsregel():
    snap = snapshot(ONE)
    _, el = await eigen(snap)
    [regel] = el["beslissingen"]
    assert (regel["type"], regel["actor"], regel["wijziging"]) == ("markering", "jurist", {"klasse": "Rechtssubject"})
    assert regel["tijd"]


async def test_de_regel_is_geen_oordeel_de_maker_kan_nog_wijzigen_en_wissen():
    snap = snapshot(ONE)
    laag, el = await eigen(snap)
    assert not store.heeft_oordeel(el)
    gewijzigd = await store.beslis(el["id"], besluit(snap, laag, "edit", wijziging={"toelichting": "Scherper"}), snap, "jurist")
    assert gewijzigd["element"]["toelichting"] == "Scherper"

    snap2 = snapshot(TWO)
    laag2 = (await store.batch(request(snap2, [element(snap2, TWO, 0, 4)], batch_id="eigen2"), snap2, "jurist", mens=True))
    wis = laag2["elementen"][0]
    assert (await store.verwijder(wis["id"], laag2["lagen"][0]["revisie"], "jurist"))["verwijderd"] == wis["id"]


async def test_de_regel_telt_niet_als_uitkomst_en_past_in_de_projectie():
    snap = snapshot(ONE)
    laag, el = await eigen(snap)
    assert annotatie_statistiek._uitkomst(el) == "open"
    assert "markering" in bouw_graaf(await store.laag_detail(laag["id"]), [el]).serialize(format="turtle")


# --- B17: de toelichting volgt de klasse ------------------------------------------------------

async def test_een_klassewissel_herziet_de_verouderde_toelichting():
    snap = snapshot(ONE)
    laag, [el] = await voorstel(snap, element(snap, toelichting="Een rechtssubject is iemand."))
    uit = (await store.beslis(el["id"], besluit(snap, laag, "edit", wijziging={"klasse": "Rechtsfeit"}), snap, "jurist"))["element"]
    assert uit["toelichting"].startswith("Klasse gewijzigd van Rechtssubject naar Rechtsfeit")
    assert "rechtssubject is iemand" not in uit["toelichting"]
    # De oude tekst is niet weg: de beslissing bewaart hem.
    assert uit["beslissingen"][-1]["voor"]["toelichting"] == "Een rechtssubject is iemand."


@pytest.mark.parametrize("wijziging, verwacht", [
    ({"klasse": "Rechtsfeit", "toelichting": "Eigen tekst"}, "Eigen tekst"),      # de jurist schrijft haar zelf
    ({"toelichting": "Scherper"}, "Scherper"),                                     # geen klassewissel
])
async def test_een_eigen_toelichting_wint(wijziging, verwacht):
    snap = snapshot(ONE)
    laag, [el] = await voorstel(snap, element(snap, toelichting="Oud"))
    uit = await store.beslis(el["id"], besluit(snap, laag, "edit", wijziging=wijziging), snap, "jurist")
    assert uit["element"]["toelichting"] == verwacht


async def test_dezelfde_toelichting_meesturen_telt_niet_als_eigen_tekst():
    snap = snapshot(ONE)
    laag, [el] = await voorstel(snap, element(snap, toelichting="Oud"))
    w = {"klasse": "Rechtsfeit", "toelichting": "Oud"}
    assert (await store.beslis(el["id"], besluit(snap, laag, "edit", wijziging=w), snap, "jurist"))["element"]["toelichting"] != "Oud"


async def test_zonder_oude_toelichting_komt_er_geen_zin_bij():
    snap = snapshot(ONE)
    laag, [el] = await voorstel(snap, element(snap))
    uit = await store.beslis(el["id"], besluit(snap, laag, "edit", wijziging={"klasse": "Rechtsfeit"}), snap, "jurist")
    assert uit["element"]["toelichting"] == ""


# --- B14, B20: compacte antwoorden -----------------------------------------------------------

async def test_een_besluit_herhaalt_de_run_meting_en_het_spoor_niet():
    snap = snapshot(ONE)
    laag, [el] = await voorstel(snap, element(snap, trace={"kandidaat": {"bewijs": ["x" * 5000]}}))
    uit = await store.beslis(el["id"], besluit(snap, laag, "approve"), snap, "jurist")
    assert not {"trace", "geproduceerd_door"} & set(uit["element"])
    assert uit["element"]["lifecycle"] == "human_approved" and uit["lagen"][0]["revisie"] == laag["revisie"] + 1
    assert len(json.dumps(uit)) < 2000
    # De opslag raakt niets kwijt.
    assert (await store.detail(el["id"]))["element"]["geproduceerd_door"]["instellingen"]["meting"]


async def test_de_weergave_draagt_elke_meting_een_keer():
    snap = snapshot(ONE)
    await voorstel(snap, element(snap), element(snap, start=7, end=11))
    volledig = await store.weergave(snap)
    compact = store.compacte_weergave(volledig)
    assert len(compact["runs"]) == 1
    [run] = compact["runs"].values()
    assert run["instellingen"]["meting"]["taal_model"] == "nl"
    for e in compact["elementen"]:
        assert e["geproduceerd_door"]["model"] == "m" and e["geproduceerd_door"]["instellingen"] == {"classifier": "x"}
        assert store.run_sleutel(e["geproduceerd_door"]) in compact["runs"]
    assert len(json.dumps(compact, default=str)) < 0.7 * len(json.dumps(volledig, default=str))


async def test_de_export_houdt_de_meting():
    snap = snapshot(ONE)
    await voorstel(snap, element(snap), element(snap, start=7, end=11))
    [run] = annotatie_export.runs(await store.weergave(snap))
    assert run["instellingen"]["meting"]["taal_model"] == "nl"


# --- bulk per laag -----------------------------------------------------------------------------

def bulk(snap, laag, besluiten):
    return Laagbesluiten.model_validate({"verwachte_revisie": laag["revisie"], "snapshot_id": snap["snapshot_id"],
                                         "besluiten": besluiten})


async def test_bulk_is_een_transactie_een_revisie_en_klein():
    snap = snapshot(ONE)
    laag, [a, b] = await voorstel(snap, element(snap), element(snap, start=7, end=11, toelichting="Oud"))
    uit = await store.beslis_laag(laag["id"], bulk(snap, laag, [
        {"element_id": a["id"], "type": "approve"},
        {"element_id": b["id"], "type": "edit", "wijziging": {"klasse": "Rechtsfeit"}}]), snap, "jurist")
    assert uit["laag"]["revisie"] == laag["revisie"] + 1
    assert uit["open"] == 0
    assert {e["id"]: e["lifecycle"] for e in uit["elementen"]} == {a["id"]: "human_approved", b["id"]: "edited"}
    assert len(json.dumps(uit, default=str)) < 1000

    [revisie, *_] = await store.revisies(laag["id"])
    assert sorted(x["actie"] for x in revisie["acties"]) == ["approve", "edit"]
    async with db.get_engine().connect() as conn:
        rijen = (await conn.execute(select(db.annotatie_v2_audit.c.actie).where(
            db.annotatie_v2_audit.c.actie.in_(["approve", "edit"])))).scalars().all()
    assert len(rijen) == 2
    # Dezelfde regels als een los besluit: de toelichting is herzien.
    assert (await store.detail(b["id"]))["element"]["toelichting"].startswith("Klasse gewijzigd")
    assert (await store.zet_status(laag["id"], "geaccordeerd", uit["laag"]["revisie"], "jurist", snap))["status"] == "geaccordeerd"


async def test_bulk_is_alles_of_niets():
    snap = snapshot(ONE)
    laag, [a, b] = await voorstel(snap, element(snap), element(snap, start=7, end=11))
    laag = (await store.beslis(b["id"], besluit(snap, laag, "approve"), snap, "jurist"))["lagen"][0]
    with pytest.raises(HTTPException) as exc:
        await store.beslis_laag(laag["id"], bulk(snap, laag, [{"element_id": a["id"], "type": "approve"},
                                                              {"element_id": b["id"], "type": "reject"}]), snap, "jurist")
    assert exc.value.status_code == 409
    assert exc.value.detail["element_id"] == b["id"] and "niets vastgelegd" in exc.value.detail["melding"]
    assert (await store.detail(a["id"]))["element"]["lifecycle"] == "voorgesteld"
    assert (await store.laag_detail(laag["id"]))["revisie"] == laag["revisie"]


async def test_bulk_weigert_een_element_van_een_andere_laag_en_een_oude_revisie():
    snap = snapshot()
    uit = await store.batch(request(snap, [element(snap), element(snap, TWO, 0, 4)], run=RUN), snap, "agent")
    een, twee = uit["lagen"]
    ander = next(e for e in uit["elementen"] if e["laag_id"] == twee["id"])
    with pytest.raises(HTTPException) as exc:
        await store.beslis_laag(een["id"], bulk(snap, een, [{"element_id": ander["id"], "type": "approve"}]), snap, "jurist")
    assert (exc.value.status_code, exc.value.detail["fout"]) == (422, "element_buiten_laag")

    eigen_el = next(e for e in uit["elementen"] if e["laag_id"] == een["id"])
    with pytest.raises(HTTPException) as exc:
        await store.beslis_laag(een["id"], bulk(snap, {**een, "revisie": 0}, [{"element_id": eigen_el["id"], "type": "approve"}]), snap, "jurist")
    assert exc.value.status_code == 412


async def test_bulk_op_een_andere_bronstand_is_een_409():
    snap = snapshot(ONE)
    laag, [a] = await voorstel(snap, element(snap))
    with pytest.raises(HTTPException) as exc:
        await store.beslis_laag(laag["id"], bulk({**snap, "snapshot_id": "ander"}, laag, [{"element_id": a["id"], "type": "approve"}]), snap, "jurist")
    assert exc.value.status_code == 409


@pytest.mark.parametrize("onjuist", [
    {"besluiten": []},
    {"besluiten": [{"element_id": "a", "type": "edit", "wijziging": {"ankers": []}}]},
    {"besluiten": [{"element_id": "a", "type": "approve"}, {"element_id": "a", "type": "reject"}]},
    {"besluiten": [{"element_id": "a", "type": "grens"}]},
])
def test_het_contract_van_de_bulk(onjuist):
    with pytest.raises(ValueError):
        Laagbesluiten.model_validate({"verwachte_revisie": 1, "snapshot_id": "s", **onjuist})
