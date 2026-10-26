"""Een gesprek hoort bij een werkgebied of is los (spoor G1): koppelen, loskoppelen, archiveren, en wat
er gebeurt als een van beide verdwijnt. Het gesprek is een verslag; de objecten hebben hun eigen leven."""
from __future__ import annotations

from sqlalchemy import func, select

from app import db
from test_werkgebieden import _nieuw, client, database, graaf  # noqa: F401

G = "/v1/gesprekken"


async def _gesprek(client, **body) -> dict:
    r = await client.post(G, json={"titel": "Vraag", **body})
    assert r.status_code == 201, r.text
    return r.json()


async def _lijst(client, **params) -> list[dict]:
    r = await client.get(G, params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def test_een_gesprek_vanuit_een_werkgebied_hoort_erbij(client):
    wg = await _nieuw(client, "Invorderingsrente")
    g = await _gesprek(client, werkgebied_id=wg["id"])
    assert g["werkgebied_id"] == wg["id"] and g["gearchiveerd"] is None
    los = await _gesprek(client)
    assert los["werkgebied_id"] == ""

    rij = next(r for r in await _lijst(client) if r["id"] == g["id"])
    assert (rij["werkgebied_id"], rij["werkgebied_naam"]) == (wg["id"], "Invorderingsrente")
    assert [r["id"] for r in await _lijst(client, werkgebied_id=wg["id"])] == [g["id"]]
    assert [r["id"] for r in await _lijst(client, werkgebied_id="")] == [los["id"]]


async def test_koppelen_en_loskoppelen(client):
    wg = await _nieuw(client)
    g = await _gesprek(client)
    r = await client.patch(f"{G}/{g['id']}", json={"werkgebied_id": wg["id"]})
    assert r.status_code == 200 and r.json()["werkgebied_id"] == wg["id"]
    # De titel blijft staan als alleen het werkgebied verandert.
    assert r.json()["titel"] == "Vraag"
    r = await client.patch(f"{G}/{g['id']}", json={"werkgebied_id": ""})
    assert r.json()["werkgebied_id"] == ""


async def test_koppelen_aan_een_onbekend_werkgebied_kan_niet(client):
    g = await _gesprek(client)
    assert (await client.patch(f"{G}/{g['id']}", json={"werkgebied_id": "bestaat-niet"})).status_code == 404
    assert (await client.post(G, json={"werkgebied_id": "bestaat-niet"})).status_code == 404


async def test_archiveren_verbergt_en_herstellen_haalt_terug(client):
    g = await _gesprek(client)
    r = await client.patch(f"{G}/{g['id']}", json={"gearchiveerd": True})
    assert r.json()["gearchiveerd"]
    assert g["id"] not in [x["id"] for x in await _lijst(client, gearchiveerd="false")]
    assert [x["id"] for x in await _lijst(client, gearchiveerd="true")] == [g["id"]]
    r = await client.patch(f"{G}/{g['id']}", json={"gearchiveerd": False})
    assert r.json()["gearchiveerd"] is None


async def test_verplaatsen_zet_een_gesprek_niet_bovenaan(client):
    wg = await _nieuw(client)
    oud = await _gesprek(client, titel="Oud")
    nieuw = await _gesprek(client, titel="Nieuw")
    await client.patch(f"{G}/{oud['id']}", json={"werkgebied_id": wg["id"]})
    await client.patch(f"{G}/{oud['id']}", json={"gearchiveerd": True})
    await client.patch(f"{G}/{oud['id']}", json={"gearchiveerd": False})
    assert [x["id"] for x in await _lijst(client)] == [nieuw["id"], oud["id"]]


async def test_een_werkgebied_wissen_maakt_zijn_gesprekken_los(client):
    wg = await _nieuw(client)
    g = await _gesprek(client, werkgebied_id=wg["id"])
    r = await client.delete(f"/v1/werkgebieden/{wg['id']}", params={"verwachte_revisie": wg["revisie"]})
    assert r.status_code == 200
    doc = (await client.get(f"{G}/{g['id']}")).json()
    assert doc["werkgebied_id"] == ""


async def test_een_gesprek_wissen_laat_het_werkgebied_staan(client):
    wg = await _nieuw(client)
    g = await _gesprek(client, werkgebied_id=wg["id"])
    assert (await client.delete(f"{G}/{g['id']}")).status_code == 204
    assert (await client.get(f"/v1/werkgebieden/{wg['id']}")).status_code == 200
    async with db.get_engine().connect() as conn:
        assert (await conn.execute(select(func.count()).select_from(db.gesprekken))).scalar() == 0


async def test_andermans_gesprek_koppelen_kan_niet(client):
    wg = await _nieuw(client)
    g = await _gesprek(client)
    r = await client.patch(f"{G}/{g['id']}", json={"werkgebied_id": wg["id"]}, headers={"X-User-Id": "jurist-b"})
    assert r.status_code == 404
    # B ziet A's gesprekken ook niet onder het gedeelde werkgebied.
    await client.patch(f"{G}/{g['id']}", json={"werkgebied_id": wg["id"]})
    r = await client.get(G, params={"werkgebied_id": wg["id"]}, headers={"X-User-Id": "jurist-b"})
    assert r.json() == []
