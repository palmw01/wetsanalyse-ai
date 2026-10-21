"""Verwijderen is echt wissen, net als een annotatie: een werkgebied en een begrip gaan met alles wat eraan
hangt uit de database; de audit blijft als bewijs, de annotaties blijven staan, en wie het object later
opvraagt hoort wanneer en door wie het verwijderd is."""
from __future__ import annotations

from sqlalchemy import func, select

from app import begrip_store, db, werkgebied_store
from test_annotatie_v2 import ART
from test_begrippen import _annoteer, _begrip, _url, _werkgebied
from test_werkgebieden import _nieuw, client, database, graaf  # noqa: F401


async def _aantal(tabel: str, kolom: str, waarde: str) -> int:
    t = db.metadata.tables[tabel]
    async with db.get_engine().connect() as conn:
        return (await conn.execute(select(func.count()).select_from(t).where(t.c[kolom] == waarde))).scalar()


async def _gevuld(client) -> tuple[dict, dict, dict, dict]:
    """Een werkgebied met twee begrippen, een relatie, een deelvraag met bron- en begripkoppeling."""
    ids = await _annoteer()
    wg = await _werkgebied(client)
    a = await _begrip(client, wg, [ids["lid1"]], naam="A")
    b = await _begrip(client, wg, [ids["awr"]], naam="B")
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/relaties",
                          json={"van_begrip": a["id"], "naar_begrip": b["id"], "type": "verwant", "toelichting": "x"})
    assert r.status_code == 201, r.text
    wg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/deelvragen",
                          json={"verwachte_revisie": wg["revisie"], "vraag": "Wie is belastingschuldige?"})
    assert r.status_code == 201, r.text
    wg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    d = wg["deelvragen"][0]
    r = await client.put(f"/v1/werkgebieden/{wg['id']}/deelvragen/{d['id']}/koppelingen",
                         json={"verwachte_revisie": wg["revisie"], "bronnen": [wg["bronnen"][0]["id"]],
                               "begrippen": [a["id"], b["id"]]})
    assert r.status_code == 200, r.text
    return (await client.get(f"/v1/werkgebieden/{wg['id']}")).json(), a, b, d


# --- het werkgebied ---------------------------------------------------------------------------------

async def test_een_werkgebied_verwijderen_wist_alles_behalve_de_audit_en_de_annotaties(client):
    wg, a, _, d = await _gevuld(client)
    ander = await _nieuw(client, "Ander")
    r = await client.delete(f"/v1/werkgebieden/{wg['id']}", params={"verwachte_revisie": wg["revisie"]})
    assert r.status_code == 200 and r.json() == {"verwijderd": wg["id"]}
    for tabel in werkgebied_store.WERKGEBIED_TABELLEN:
        assert await _aantal(tabel, "werkgebied_id", wg["id"]) == 0, tabel
    assert await _aantal("werkgebieden", "id", wg["id"]) == 0
    assert await _aantal("begrip_revisies", "begrip_id", a["id"]) == 0
    assert await _aantal("werkgebied_deelvraag_koppelingen", "deelvraag_id", d["id"]) == 0
    # De audit blijft, met een laatste regel; de annotaties en het andere werkgebied ook.
    assert await _aantal("werkgebied_audit", "werkgebied_id", wg["id"]) > 1
    async with db.get_engine().connect() as conn:
        assert (await conn.execute(select(func.count()).select_from(db.metadata.tables["annotatie_v2_elementen"]))).scalar() == 3
    assert [w["id"] for w in (await client.get("/v1/werkgebieden")).json()["werkgebieden"]] == [ander["id"]]


async def test_een_verwijderd_werkgebied_zegt_wanneer_en_door_wie(client):
    wg = await _nieuw(client)
    await client.delete(f"/v1/werkgebieden/{wg['id']}", params={"verwachte_revisie": 1})
    r = await client.get(f"/v1/werkgebieden/{wg['id']}")
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert (detail["fout"], detail["soort"], detail["door"]) == ("verwijderd", "werkgebied", "jurist-a") and detail["op"]
    # Een id dat nooit bestond: een gewone 404.
    assert (await client.get("/v1/werkgebieden/bestaat-niet")).json()["detail"] == "Werkgebied bestaat niet."
    # Nog eens verwijderen: 404 met dezelfde melding.
    assert (await client.delete(f"/v1/werkgebieden/{wg['id']}", params={"verwachte_revisie": 1})).status_code == 404


async def test_verwijderen_met_een_oude_revisie_is_412_en_wist_niets(client):
    wg = await _nieuw(client)
    await client.patch(f"/v1/werkgebieden/{wg['id']}", json={"verwachte_revisie": 1, "naam": "Nieuw"})
    r = await client.delete(f"/v1/werkgebieden/{wg['id']}", params={"verwachte_revisie": 1})
    assert r.status_code == 412 and r.json()["detail"]["fout"] == "revisie_conflict"
    assert (await client.get(f"/v1/werkgebieden/{wg['id']}")).status_code == 200


async def test_na_verwijderen_maakt_dezelfde_intake_een_nieuw_werkgebied(client):
    invoer = {"naam": "Box 3", "analysevraag": "Wie?", "intake_id": "ik-9"}
    eerst = (await client.post("/v1/werkgebieden", json=invoer)).json()
    await client.delete(f"/v1/werkgebieden/{eerst['id']}", params={"verwachte_revisie": 1})
    r = await client.post("/v1/werkgebieden", json=invoer)
    assert r.status_code == 201 and r.json()["id"] != eerst["id"]


# --- het begrip -----------------------------------------------------------------------------------

async def test_een_begrip_verwijderen_wist_het_met_relaties_en_deelvraagplek(client):
    wg, a, b, d = await _gevuld(client)
    r = await client.delete(_url(wg, a), params={"verwachte_revisie": a["revisie"]})
    assert r.status_code == 200 and r.json()["verwijderd"] == a["id"]
    for tabel in ("begrip_revisies", "begrip_koppelingen", "begrip_voorstellen", "begrip_kaartruns"):
        assert await _aantal(tabel, "begrip_id", a["id"]) == 0, tabel
    assert await _aantal("begrippen", "id", a["id"]) == 0
    assert await _aantal("begrip_relaties", "van_begrip", a["id"]) == 0
    # De deelvraag houdt haar bron en het andere begrip.
    wg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    [dv] = wg["deelvragen"]
    assert dv["begrippen"] == [b["id"]] and len(dv["bronnen"]) == 1
    # Het andere begrip staat er nog; het verwijderde zegt wanneer en door wie.
    assert (await client.get(_url(wg, b))).status_code == 200
    weg = (await client.get(_url(wg, a))).json()["detail"]
    assert (weg["fout"], weg["soort"], weg["door"]) == ("verwijderd", "begrip", "jurist-a")


async def test_de_opvolger_verwijderen_zet_de_voorganger_terug(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    oud = await _begrip(client, wg, [ids["lid1"]])
    r = await client.post(_url(wg, oud, "nieuwe-betekenis"), json={"verwachte_revisie": oud["revisie"], "reden": "x"})
    nieuw = r.json()
    r = await client.delete(_url(wg, nieuw), params={"verwachte_revisie": nieuw["revisie"]})
    assert r.status_code == 200 and r.json()["hersteld"] == [oud["id"]]
    oud = (await client.get(_url(wg, oud))).json()
    assert oud["status"] == "concept"
    # Een vervangen begrip zelf gaat niet weg.
    r = await client.post(_url(wg, oud, "nieuwe-betekenis"), json={"verwachte_revisie": oud["revisie"], "reden": "y"})
    assert r.status_code == 201, r.text
    oud = (await client.get(_url(wg, oud))).json()
    assert (await client.delete(_url(wg, oud), params={"verwachte_revisie": oud["revisie"]})).status_code == 409


# --- de wislijsten zijn volledig ------------------------------------------------------------------

def test_elke_tabel_met_een_werkgebied_of_begrip_staat_in_de_wislijst():
    """Een nieuwe tabel met `werkgebied_id` of `begrip_id` laat anders stil een wees achter."""
    werkgebied = {t.name for t in db.metadata.sorted_tables if "werkgebied_id" in t.c} - {"werkgebied_audit"}
    assert werkgebied == set(werkgebied_store.WERKGEBIED_TABELLEN)
    begrip = {t.name for t in db.metadata.sorted_tables if "begrip_id" in t.c}
    assert begrip == set(begrip_store.BEGRIP_TABELLEN)
