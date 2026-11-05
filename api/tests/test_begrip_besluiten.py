"""Besluiten over passages en accorderen (fase 6 na de e2e-wetsanalyse): kleine antwoorden, bulk in één revisie, en een
verplichte reden in revisie en audit."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app import annotatie_v2_store as store, db
from app.annotatie_v2_contracts import Beslissing
from test_annotatie_v2 import snapshot
from test_begrip_onderhoud import _geaccordeerd, _herbeoordelingen
from test_begrippen import DEFINITIE, _annoteer, _begrip, _keur_alles_goed, _url, _werkgebied
from test_werkgebieden import client, database, graaf, snapshot2  # noqa: F401


async def _met_passages(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    return ids, wg, await _begrip(client, wg, list(ids.values()))


def _koppel_ids(b: dict) -> list[str]:
    return [k["id"] for k in b["koppelingen"]]


async def _audit(actie: str) -> list[dict]:
    t = db.werkgebied_audit
    async with db.get_engine().connect() as conn:
        return list((await conn.execute(select(t.c.detail).where(t.c.actie == actie))).scalars().all())


# --- B16: een klein antwoord -----------------------------------------------------------------

async def test_een_koppelingsbesluit_geeft_de_stand_niet_de_kaart(client):
    _, wg, b = await _met_passages(client)
    k = b["koppelingen"][0]
    r = await client.patch(_url(wg, b, "koppelingen", k["id"]), json={"verwachte_revisie": b["revisie"], "beoordeling": "akkoord"})
    uit = r.json()
    assert uit["revisie"] == b["revisie"] + 1
    assert "inhoud" not in uit and all("bewijs" not in x for x in uit["koppelingen"])
    assert next(x for x in uit["koppelingen"] if x["id"] == k["id"])["beoordeling"] == "akkoord"
    assert uit["accorderen"]["mag"] is False                  # de poort reist mee
    assert len(json.dumps(uit)) < 0.6 * len(json.dumps((await client.get(_url(wg, b))).json()))


async def test_losmaken_geeft_ook_de_stand(client):
    _, wg, b = await _met_passages(client)
    k = b["koppelingen"][0]
    r = await client.delete(_url(wg, b, "koppelingen", k["id"]), params={"verwachte_revisie": b["revisie"]})
    assert k["id"] not in _koppel_ids(r.json()) and len(r.json()["koppelingen"]) == 2


# --- bulk ------------------------------------------------------------------------------------

async def test_beoordelen_in_bulk_is_een_revisie_en_een_auditregel(client):
    _, wg, b = await _met_passages(client)
    ids = _koppel_ids(b)
    r = await client.post(_url(wg, b, "koppelingen", "beoordelen"),
                          json={"verwachte_revisie": b["revisie"], "koppeling_ids": ids, "beoordeling": "akkoord"})
    assert r.status_code == 200, r.text
    assert r.json()["revisie"] == b["revisie"] + 1
    assert {k["beoordeling"] for k in r.json()["koppelingen"]} == {"akkoord"}
    [regel] = await _audit("koppeling-gewijzigd")
    assert sorted(regel["koppelingen"]) == sorted(ids) and regel["beoordeling"] == "akkoord"


async def test_wat_al_zo_staat_is_geen_revisie(client):
    _, wg, b = await _met_passages(client)
    body = {"verwachte_revisie": b["revisie"], "koppeling_ids": _koppel_ids(b), "beoordeling": "open"}
    r = await client.post(_url(wg, b, "koppelingen", "beoordelen"), json=body)
    assert r.status_code == 200 and r.json()["revisie"] == b["revisie"]


async def test_bulk_met_een_onbekende_koppeling_doet_niets(client):
    _, wg, b = await _met_passages(client)
    r = await client.post(_url(wg, b, "koppelingen", "beoordelen"), json={
        "verwachte_revisie": b["revisie"], "koppeling_ids": [*_koppel_ids(b), "weg"], "beoordeling": "akkoord"})
    assert r.status_code == 404 and r.json()["detail"]["koppeling_ids"] == ["weg"]
    assert {k["beoordeling"] for k in (await client.get(_url(wg, b))).json()["koppelingen"]} == {"open"}


async def test_bulk_op_een_oude_revisie_is_een_412(client):
    _, wg, b = await _met_passages(client)
    r = await client.post(_url(wg, b, "koppelingen", "beoordelen"), json={
        "verwachte_revisie": b["revisie"] + 5, "koppeling_ids": _koppel_ids(b), "beoordeling": "akkoord"})
    assert r.status_code == 412


@pytest.mark.parametrize("ids", [[], ["a", "a"]])
async def test_het_contract_van_de_bulk(client, ids):
    _, wg, b = await _met_passages(client)
    r = await client.post(_url(wg, b, "koppelingen", "beoordelen"),
                          json={"verwachte_revisie": b["revisie"], "koppeling_ids": ids, "beoordeling": "akkoord"})
    assert r.status_code == 422


async def test_bevestigen_in_bulk_houdt_het_begrip_geaccordeerd(client):
    ids = await _annoteer()
    await _keur_alles_goed(ids)
    wg = await _werkgebied(client)
    b = await _geaccordeerd(client, wg, list(ids.values()))
    # Twee passages veranderen: ze krijgen elk een andere klasse.
    snap = snapshot()
    for eid in (ids["lid1"], ids["lid2"]):
        view = await store.weergave(snap)
        revs = {l["bron_iri"]: l["revisie"] for l in view["lagen"]}
        await store.beslis(eid, Beslissing(type="heropen", snapshot_id=snap["snapshot_id"], verwachte_revisies=revs), snap, "a")
        view = await store.weergave(snap)
        revs = {l["bron_iri"]: l["revisie"] for l in view["lagen"]}
        await store.beslis(eid, Beslissing(type="edit", wijziging={"klasse": "Voorwaarde"}, snapshot_id=snap["snapshot_id"],
                                           verwachte_revisies=revs), snap, "a")
    h = await _herbeoordelingen(client, wg, begrip_id=b["id"])
    [begrip] = h["begrippen"]
    te_bevestigen = [k["koppeling_id"] for k in begrip["koppelingen"]]
    assert len(te_bevestigen) == 2
    r = await client.post(_url(wg, b, "koppelingen", "bevestigen"), json={
        "verwachte_revisie": begrip["revisie"], "koppeling_ids": te_bevestigen, "motivatie": "Klasse aangescherpt."})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "geaccordeerd" and r.json()["revisie"] == begrip["revisie"] + 1
    assert {k["actualiteit"] for k in r.json()["koppelingen"]} == {"actueel"}
    assert sorted((await _audit("koppeling-bevestigd"))[0]["koppelingen"]) == sorted(te_bevestigen)
    assert not (await _herbeoordelingen(client, wg, begrip_id=b["id"]))["begrippen"]


# --- N1: accorderen met een reden ------------------------------------------------------------

async def _klaar(client):
    ids = await _annoteer()
    await _keur_alles_goed(ids)
    wg = await _werkgebied(client)
    b = await _begrip(client, wg, [ids["lid1"]])
    b = (await client.patch(_url(wg, b), json={"verwachte_revisie": b["revisie"], "inhoud": {"naam": "X", **DEFINITIE}})).json()
    b = (await client.post(_url(wg, b, "koppelingen", "beoordelen"), json={
        "verwachte_revisie": b["revisie"], "koppeling_ids": _koppel_ids(b), "beoordeling": "akkoord"})).json()
    return wg, b


@pytest.mark.parametrize("body", [{}, {"reden": ""}, {"reden": "   "}])
async def test_accorderen_zonder_reden_kan_niet(client, body):
    wg, b = await _klaar(client)
    r = await client.post(_url(wg, b, "accorderen"), json={"verwachte_revisie": b["revisie"], **body})
    assert r.status_code == 422
    assert (await client.get(_url(wg, b))).json()["status"] == "concept"


async def test_de_reden_staat_in_de_revisie_en_de_audit(client):
    wg, b = await _klaar(client)
    r = await client.post(_url(wg, b, "accorderen"), json={"verwachte_revisie": b["revisie"], "reden": "  Getoetst aan art. 9. "})
    assert r.status_code == 200, r.text
    assert r.json()["geaccordeerd_door"]
    [revisie, *_] = (await client.get(_url(wg, b, "revisies"))).json()["revisies"]
    assert (revisie["actie"], revisie["detail"]["reden"]) == ("begrip-geaccordeerd", "Getoetst aan art. 9.")
    [regel] = await _audit("begrip-geaccordeerd")
    assert regel["reden"] == "Getoetst aan art. 9."
