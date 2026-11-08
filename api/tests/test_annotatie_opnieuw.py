"""Opnieuw annoteren ruimt de oude voorstellen van Lex op die de nieuwe ronde niet meer maakte (`vervangen`).

Niets wordt gewist: de rij, de herkomst en de audit blijven. Een besluit, een opmerking, een eigen markering en een
ronde die niet af is, raken het nooit."""
import hashlib

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app import db
from app import annotatie_v2_store as store
from app import graaf_projectie_v2
from app.annotatie_v2_contracts import Batch, Beslissing
from app.begrip_store import actualiteit, element_hash

LAW = "urn:bwb:BWBR0004770"
ART = LAW + ":artikel:9"
ONE = ART + ":lid:1"
TWO = ART + ":lid:2"
OPNIEUW = {"modus": "opnieuw", "model": "m", "ronde": "2"}
VOLTOOID = {"voltooid": True, "bereik": [ONE]}


def snapshot(target=ONE):
    nodes = [dict(bron_iri=LAW, parent_iri="", type="Wet", label="Wet", tekst=""),
             dict(bron_iri=ART, parent_iri=LAW, type="Artikel", label="Artikel 9", tekst=""),
             dict(bron_iri=ONE, parent_iri=ART, type="Lid", label="Lid 1", tekst="De ontvanger stelt de aanslag vast"),
             dict(bron_iri=TWO, parent_iri=ART, type="Lid", label="Lid 2", tekst="Beta")]
    for i, n in enumerate(nodes):
        n.update(bron_hash=hashlib.sha256(n["tekst"].encode()).hexdigest(), volgorde=i, bwb_id="BWBR0004770")
    return dict(snapshot_id=store.digest(nodes), doel=next(n for n in nodes if n["bron_iri"] == target), nodes=nodes)


def element(snap, start, end, id_, klasse="Rechtssubject"):
    n = store.nodes_van(snap)[ONE]
    return dict(id=id_, klasse=klasse, tekst=n["tekst"][start:end],
                ankers=[dict(bron_iri=ONE, start=start, eind=end, tekst=n["tekst"][start:end], bron_hash=n["bron_hash"])])


def request(snap, elements, batch_id, revisie, run=None, dekking=None):
    return Batch.model_validate(dict(batch_id=batch_id, doel={"bron_iri": snap["doel"]["bron_iri"]},
        snapshot_id=snap["snapshot_id"], elementen=elements, verwachte_revisies={ONE: revisie} if revisie else {},
        run=run or {"modus": "nieuw"}, dekking=dekking or VOLTOOID))


@pytest.fixture(autouse=True)
async def database():
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    yield
    await db.dispose_engine()


async def _eerste_ronde(snap):
    """Ronde 1: drie voorstellen van Lex op lid 1."""
    await store.batch(request(snap, [element(snap, 3, 12, "ontvanger"), element(snap, 13, 18, "stelt", "Operator"),
                                     element(snap, 19, 21, "de")], "ronde-1", 0), snap, "agent")


async def _rij(element_id):
    async with db.get_engine().connect() as conn:
        return (await conn.execute(select(db.annotatie_v2_elementen.c.inhoud).where(
            db.annotatie_v2_elementen.c.id == element_id))).scalar_one()


async def _audit(actie):
    async with db.get_engine().connect() as conn:
        return [dict(r) for r in (await conn.execute(select(db.annotatie_v2_audit).where(
            db.annotatie_v2_audit.c.actie == actie))).mappings().all()]


async def test_opnieuw_vervangt_wat_de_nieuwe_ronde_niet_meer_maakte():
    snap = snapshot()
    await _eerste_ronde(snap)
    res = await store.batch(request(snap, [element(snap, 3, 12, "ontvanger")], "ronde-2", 1, OPNIEUW), snap, "agent")
    assert sorted(res["vervangen"]) == ["de", "stelt"]
    view = await store.weergave(snap)
    # Niet actueel: weg uit de elementen, wel terug te vinden.
    assert [e["id"] for e in view["elementen"]] == ["ontvanger"]
    assert sorted(v["id"] for v in view["vervangen"]) == ["de", "stelt"]
    assert view["vervangen"][0]["vervangen_in"]["batch_id"] == "ronde-2"
    # Niet gewist: de rij en de herkomst blijven, met een auditregel per element.
    rij = await _rij("stelt")
    assert rij["lifecycle"] == "vervangen" and rij["herkomst"] == "agent" and rij["geproduceerd_door"] == {"modus": "nieuw"}
    regels = await _audit("element-vervangen")
    assert sorted(r["element_id"] for r in regels) == ["de", "stelt"]
    assert all(r["detail"]["batch_id"] == "ronde-2" and r["laag_id"] for r in regels)
    assert (await _audit("element-gemaakt"))  # de geschiedenis van ronde 1 staat er nog
    # Eén revisie voor de hele ronde, ook al raakte alleen het opruimen de laag.
    assert view["lagen"][0]["revisie"] == 2


async def test_een_besluit_een_opmerking_en_een_eigen_markering_blijven_staan():
    snap = snapshot()
    await _eerste_ronde(snap)
    await store.beslis("stelt", Beslissing(type="approve", snapshot_id=snap["snapshot_id"],
                                           verwachte_revisies={ONE: 1}), snap, "jurist")
    await store.beslis("de", Beslissing(type="comment", comment="twijfel", snapshot_id=snap["snapshot_id"],
                                        verwachte_revisies={ONE: 2}), snap, "jurist")
    eigen = element(snap, 22, 29, "")
    eigen["klasse"] = "Rechtsobject"
    mijn = (await store.batch(request(snap, [eigen], "markering", 3), snap, "jurist", mens=True))["elementen"][0]
    res = await store.batch(request(snap, [element(snap, 3, 12, "ontvanger")], "ronde-2", 4, OPNIEUW), snap, "agent")
    assert res["vervangen"] == []
    view = await store.weergave(snap)
    assert {e["id"] for e in view["elementen"]} == {"ontvanger", "stelt", "de", mijn["id"]}
    assert not view["vervangen"]
    # Niets vervangen en niets nieuws: de laag houdt haar revisie.
    assert view["lagen"][0]["revisie"] == 4


async def test_wat_de_ronde_opnieuw_maakt_blijft_hetzelfde_element():
    snap = snapshot()
    await _eerste_ronde(snap)
    voor = await _rij("ontvanger")
    await store.batch(request(snap, [element(snap, 3, 12, "ontvanger"), element(snap, 19, 21, "de")], "ronde-2", 1,
                              OPNIEUW), snap, "agent")
    assert await _rij("ontvanger") == voor
    assert (await _rij("de"))["lifecycle"] == "voorgesteld"
    assert (await _rij("stelt"))["lifecycle"] == "vervangen"


@pytest.mark.parametrize("run, dekking", [
    (OPNIEUW, {"voltooid": False, "bereik": [ONE]}),   # gestopt of mislukt: geen nieuwe uitkomst
    ({"modus": "nieuw"}, VOLTOOID),                    # geen ronde opnieuw: puur aanvullend, zoals altijd
])
async def test_zonder_voltooide_ronde_opnieuw_ruimt_niets_op(run, dekking):
    snap = snapshot()
    await _eerste_ronde(snap)
    res = await store.batch(request(snap, [element(snap, 3, 12, "ontvanger")], "ronde-2", 1, run, dekking), snap, "agent")
    assert res["vervangen"] == []
    assert len((await store.weergave(snap))["elementen"]) == 3
    assert not await _audit("element-vervangen")


async def test_een_vervangen_voorstel_leeft_op_als_een_latere_ronde_het_weer_maakt():
    snap = snapshot()
    await _eerste_ronde(snap)
    await store.batch(request(snap, [element(snap, 3, 12, "ontvanger")], "ronde-2", 1, OPNIEUW), snap, "agent")
    res = await store.batch(request(snap, [element(snap, 3, 12, "ontvanger"), element(snap, 13, 18, "stelt", "Operator")],
                                    "ronde-3", 2, {**OPNIEUW, "ronde": "3"}), snap, "agent")
    assert res["vervangen"] == []                                   # "de" was al vervangen en blijft dat
    assert (await _rij("de"))["lifecycle"] == "vervangen"
    terug = await _rij("stelt")
    assert terug["lifecycle"] == "voorgesteld" and "vervangen_in" not in terug
    assert terug["geproduceerd_door"]["ronde"] == "3"
    assert [r["element_id"] for r in await _audit("element-hersteld")] == ["stelt"]
    assert {e["id"] for e in (await store.weergave(snap))["elementen"]} == {"ontvanger", "stelt"}


async def test_vervangen_is_alleen_lezen_en_houdt_afronden_niet_tegen():
    snap = snapshot()
    await _eerste_ronde(snap)
    await store.batch(request(snap, [element(snap, 3, 12, "ontvanger")], "ronde-2", 1, OPNIEUW), snap, "agent")
    with pytest.raises(HTTPException) as exc:
        await store.beslis("stelt", Beslissing(type="approve", snapshot_id=snap["snapshot_id"],
                                               verwachte_revisies={ONE: 2}), snap, "jurist")
    assert exc.value.status_code == 409
    assert store.slot_van(await _rij("stelt"), "in_review") == "alleen-lezen"
    await store.beslis("ontvanger", Beslissing(type="approve", snapshot_id=snap["snapshot_id"],
                                               verwachte_revisies={ONE: 2}), snap, "jurist")
    laag = (await store.weergave(snap))["lagen"][0]
    # Het enige actuele voorstel is beoordeeld; de vervangen voorstellen zijn geen open werk.
    await store.zet_status(laag["id"], "geaccordeerd", laag["revisie"], "jurist", snap)
    rij = next(r for r in await store.overzicht(None, "", 10, 0) if r["id"] == laag["id"])
    assert rij["aantal_elementen"] == 1 and rij["te_beoordelen"] == 0 and rij["vervangen"] == 2


async def test_lezers_zien_vervangen_niet_als_actueel():
    snap = snapshot()
    await _eerste_ronde(snap)
    stelt_toen = await _rij("stelt")
    await store.batch(request(snap, [element(snap, 3, 12, "ontvanger")], "ronde-2", 1, OPNIEUW), snap, "agent")
    nodes = store.nodes_van(snap)
    assert {e["id"] for e in await store.actuele_elementen(nodes)} == {"ontvanger"}
    assert {e["id"] for e in await store.actuele_elementen(nodes, inclusief_vervangen=True)} == {"ontvanger", "stelt", "de"}
    # De projectie: alleen het actuele element gaat de graaf in.
    laag = (await store.weergave(snap))["lagen"][0]
    async with db.get_engine().connect() as conn:
        elementen, _, _ = await graaf_projectie_v2.laag_invoer(conn, laag)
    assert [e["id"] for e in elementen] == ["ontvanger"]
    # Een begrip dat op het vervangen element rustte, ziet dat als een gewijzigde passage – nooit stil actueel.
    koppeling = {"bewijs": {"element_hash": element_hash(stelt_toen)}, "bevestigingen": []}
    assert actualiteit(koppeling, stelt_toen)["actualiteit"] == "actueel"
    assert actualiteit(koppeling, await _rij("stelt"))["actualiteit"] == "gewijzigd"


async def test_opnieuw_ververst_een_voorstel_waar_niemand_over_besliste():
    """Hetzelfde id, een betere duiding: de keten kreeg een subtype en een andere toelichting. Zonder verversen bereikt
    een verbetering aan de keten een bestaand element nooit (meting WA TRM, iteratie 2)."""
    snap = snapshot()
    await _eerste_ronde(snap)
    beter = {**element(snap, 3, 12, "ontvanger"), "jas_subtype": "variabele", "toelichting": "nieuwe duiding",
             "trace": {"ronde": 2}}
    res = await store.batch(request(snap, [beter, element(snap, 13, 18, "stelt", "Operator"),
                                           element(snap, 19, 21, "de")], "ronde-2", 1, OPNIEUW), snap, "agent")
    rij = await _rij("ontvanger")
    assert (rij["jas_subtype"], rij["toelichting"], rij["trace"]) == ("variabele", "nieuwe duiding", {"ronde": 2})
    assert rij["geproduceerd_door"] == OPNIEUW and rij["lifecycle"] == "voorgesteld" and rij["id"] == "ontvanger"
    assert next(e for e in res["elementen"] if e["id"] == "ontvanger")["jas_subtype"] == "variabele"
    [regel] = await _audit("element-bijgewerkt")
    assert regel["element_id"] == "ontvanger" and regel["detail"]["velden"] == ["jas_subtype", "toelichting"]
    assert (await store.weergave(snap))["lagen"][0]["revisie"] == 2


@pytest.mark.parametrize("geval", ["oordeel", "nieuw", "mens"])
async def test_verversen_raakt_geen_oordeel_geen_gewone_ronde_en_geen_eigen_markering(geval):
    snap = snapshot()
    await _eerste_ronde(snap)
    revisie = 1
    if geval == "oordeel":
        await store.beslis("ontvanger", Beslissing(type="comment", comment="klopt dit?", snapshot_id=snap["snapshot_id"],
                                                   verwachte_revisies={ONE: 1}), snap, "jurist")
        revisie = 2
    voor = await _rij("ontvanger")
    beter = {**element(snap, 3, 12, "ontvanger"), "jas_subtype": "variabele"}
    run = {"modus": "nieuw"} if geval == "nieuw" else OPNIEUW
    await store.batch(request(snap, [beter], "ronde-2", revisie, run), snap, "jurist" if geval == "mens" else "agent",
                      mens=geval == "mens")
    assert (await _rij("ontvanger"))["jas_subtype"] == voor["jas_subtype"] == ""
    assert not await _audit("element-bijgewerkt")
