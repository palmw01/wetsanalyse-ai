"""Werkgebieden (spoor D, levering 1): revisies, bronselecties, gedeeld gebruik en de inventaris."""
from __future__ import annotations

import hashlib

import pytest
from fastapi import HTTPException

from app import annotatie_v2_store as store, db, werkgebieden
from app.annotatie_v2_contracts import Beslissing
from test_annotatie_v2 import ART, LAW, ONE, TWO, element, request, snapshot

LAW2 = "urn:bwb:BWBR0002320"
ART2 = LAW2 + ":artikel:2"


def snapshot2():
    nodes = [dict(bron_iri=LAW2, parent_iri="", type="Wet", label="AWR", tekst=""),
             dict(bron_iri=ART2, parent_iri=LAW2, type="Artikel", label="Artikel 2", tekst="Deze wet")]
    for i, n in enumerate(nodes):
        n.update(bron_hash=hashlib.sha256(n["tekst"].encode()).hexdigest(), volgorde=i, bwb_id="BWBR0002320")
    return dict(snapshot_id=store.digest(nodes), doel=nodes[1], nodes=nodes)


class Graaf:
    """Nep-resolver: welke bronstand er 'nu' is, en of een regeling onbereikbaar is."""

    def __init__(self):
        self.tweede_lid = "Beta"
        self.weg: set[str] = set()

    async def resolve(self, doel):
        iri = doel.get("bron_iri") or (ART if doel.get("artikel") == "9" else "")
        if not iri:
            from bronmodel import BronFout
            raise BronFout("Onbekende bepaling.")
        if iri.startswith(LAW2):
            if LAW2 in self.weg:
                raise ConnectionError("graaf weg")
            return snapshot2()
        return snapshot(iri, second=self.tweede_lid)


@pytest.fixture(autouse=True)
async def database():
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    yield
    await db.dispose_engine()


@pytest.fixture
def graaf(monkeypatch):
    g = Graaf()
    monkeypatch.setattr(werkgebieden, "_resolve_bron", g.resolve)
    return g


@pytest.fixture
async def client(monkeypatch, graaf):
    from httpx import ASGITransport, AsyncClient
    from app.config import get_settings
    from conftest import maak_testgebruikers
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    get_settings.cache_clear()
    await maak_testgebruikers("jurist-a", "jurist-b")
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                           headers={"X-User-Id": "jurist-a"}) as c:
        yield c
    get_settings.cache_clear()


async def _nieuw(client, naam="Invorderbaarheid") -> dict:
    r = await client.post("/v1/werkgebieden", json={"naam": naam, "analysevraag": "Wanneer?"})
    assert r.status_code == 201, r.text
    return r.json()


async def _bron(client, wg: dict, **velden) -> dict:
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/bronnen",
                          json={"verwachte_revisie": wg["revisie"], **velden})
    assert r.status_code in (200, 201), r.text
    return r.json()


# --- het werkgebied zelf ---------------------------------------------------------------------

async def test_aanmaken_lijst_en_wijzigen_met_revisie(client):
    wg = await _nieuw(client)
    assert (wg["revisie"], wg["status"], wg["aangemaakt_door"], wg["bronnen"]) == (1, "in_voorbereiding", "jurist-a", [])
    lijst = (await client.get("/v1/werkgebieden")).json()["werkgebieden"]
    assert [(w["naam"], w["aantal_bronnen"]) for w in lijst] == [("Invorderbaarheid", 0)]

    r = await client.patch(f"/v1/werkgebieden/{wg['id']}", json={"verwachte_revisie": 1, "status": "actief",
                                                                 "peildatum": "2026-01-01"})
    assert r.status_code == 200 and (r.json()["revisie"], r.json()["status"], r.json()["peildatum"]) == (2, "actief", "2026-01-01")
    oud = await client.patch(f"/v1/werkgebieden/{wg['id']}", json={"verwachte_revisie": 1, "naam": "X"})
    assert oud.status_code == 412 and oud.json()["detail"] == {"fout": "revisie_conflict", "revisie": 2}
    # peildatum leegmaken kan expliciet; een rare datum niet.
    leeg = await client.patch(f"/v1/werkgebieden/{wg['id']}", json={"verwachte_revisie": 2, "peildatum": None})
    assert leeg.json()["peildatum"] is None
    assert (await client.patch(f"/v1/werkgebieden/{wg['id']}",
                               json={"verwachte_revisie": 3, "peildatum": "1-1-2026"})).status_code == 422


async def test_gedeeld_tussen_analisten_en_de_audit_zegt_wie(client):
    wg = await _nieuw(client)
    r = await client.patch(f"/v1/werkgebieden/{wg['id']}", headers={"X-User-Id": "jurist-b"},
                           json={"verwachte_revisie": 1, "naam": "Invorderbaarheid aanslagen"})
    assert r.status_code == 200
    audit = (await client.get(f"/v1/werkgebieden/{wg['id']}/audit")).json()["audit"]
    assert [(a["actor"], a["actie"]) for a in audit] == [("jurist-b", "gewijzigd"), ("jurist-a", "aangemaakt")]


async def test_archiveren_haalt_uit_de_lijst(client):
    wg = await _nieuw(client)
    assert (await client.delete(f"/v1/werkgebieden/{wg['id']}", params={"verwachte_revisie": 1})).status_code == 200
    assert (await client.get("/v1/werkgebieden")).json()["werkgebieden"] == []
    assert len((await client.get("/v1/werkgebieden", params={"gearchiveerd": 1})).json()["werkgebieden"]) == 1
    assert (await client.get(f"/v1/werkgebieden/{wg['id']}")).status_code == 404


async def test_zonder_gebruiker_401(client):
    assert (await client.get("/v1/werkgebieden", headers={"X-User-Id": ""})).status_code == 401


# --- bronselecties ----------------------------------------------------------------------------

async def test_bron_toevoegen_via_iri_en_via_artikel(client):
    wg = await _nieuw(client)
    r = await _bron(client, wg, bwb_id="BWBR0004770", artikel="9")
    sel = r["selectie"]
    assert (sel["bron_iri"], sel["rol"], sel["bereik"], sel["bwb_id"]) == (ART, "analyseren", "onderliggend", "BWBR0004770")
    assert sel["snapshot_id"] and sel["bron_hash"]
    wg = r["werkgebied"]
    r2 = await _bron(client, wg, bron_iri=ONE, bereik="node", rol="context", reden="definitie")
    assert r2["werkgebied"]["revisie"] == 3 and len(r2["werkgebied"]["bronnen"]) == 2


async def test_dezelfde_bron_twee_keer_is_idempotent_of_een_conflict(client):
    wg = await _nieuw(client)
    eerste = await _bron(client, wg, bron_iri=ART)
    wg = eerste["werkgebied"]
    nog_eens = await client.post(f"/v1/werkgebieden/{wg['id']}/bronnen",
                                 json={"verwachte_revisie": wg["revisie"], "bron_iri": ART})
    assert nog_eens.status_code == 200 and nog_eens.json()["selectie"]["id"] == eerste["selectie"]["id"]
    assert nog_eens.json()["werkgebied"]["revisie"] == wg["revisie"]            # geen revisiesprong
    anders = await client.post(f"/v1/werkgebieden/{wg['id']}/bronnen",
                               json={"verwachte_revisie": wg["revisie"], "bron_iri": ART, "rol": "context"})
    assert anders.status_code == 409 and anders.json()["detail"]["fout"] == "al_opgenomen"


async def test_onbekende_bepaling_422_en_graaf_weg_503(client, graaf):
    wg = await _nieuw(client)
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/bronnen",
                          json={"verwachte_revisie": 1, "bwb_id": "BWBR0004770", "artikel": "999"})
    assert r.status_code == 422
    graaf.weg.add(LAW2)
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/bronnen", json={"verwachte_revisie": 1, "bron_iri": ART2})
    assert r.status_code == 503


async def test_acceptatie_zelfde_artikel_in_twee_werkgebieden_onafhankelijk(client):
    """PLAN D, levering 1: een wijziging in de ene selectie raakt de andere niet."""
    snap = snapshot()
    await store.batch(request(snap, [element(snap)]), snap, "lex")
    a, b = await _nieuw(client, "A"), await _nieuw(client, "B")
    sa = (await _bron(client, a, bron_iri=ART))
    sb = (await _bron(client, b, bron_iri=ART))
    a = sa["werkgebied"]
    r = await client.patch(f"/v1/werkgebieden/{a['id']}/bronnen/{sa['selectie']['id']}",
                           json={"verwachte_revisie": a["revisie"], "rol": "context"})
    a = r.json()
    r = await client.delete(f"/v1/werkgebieden/{a['id']}/bronnen/{sa['selectie']['id']}",
                            params={"verwachte_revisie": a["revisie"]})
    assert r.status_code == 200 and r.json()["bronnen"] == []
    b_nu = (await client.get(f"/v1/werkgebieden/{b['id']}")).json()
    assert [(s["id"], s["rol"]) for s in b_nu["bronnen"]] == [(sb["selectie"]["id"], "analyseren")]
    # De annotaties van de bron staan er nog.
    assert len((await store.weergave(snap))["elementen"]) == 1


# --- inventaris -------------------------------------------------------------------------------

async def _met_elementen():
    snap = snapshot()
    e1, e2 = element(snap), element(snap, TWO, 0, 4)
    multi = dict(klasse="Voorwaarde", tekst=e1["tekst"] + " " + e2["tekst"], ankers=[*e1["ankers"], *e2["ankers"]])
    await store.batch(request(snap, [e1, e2, multi]), snap, "lex")
    # Een afgewezen element in lid 1: telt, maar staat niet in de inventaris.
    snap_een = snapshot(ONE)
    weg = await store.batch(request(snap_een, [element(snap_een, ONE, 7, 11)], batch_id="weg",
                                    revisions={ONE: 1}), snap_een, "lex")
    eid = weg["elementen"][0]["id"]
    rev = (await store.weergave(snap_een))["lagen"][0]["revisie"]
    await store.beslis(eid, Beslissing(type="reject", snapshot_id=snap_een["snapshot_id"],
                                      verwachte_revisies={ONE: rev}), snap_een, "jurist-a")


async def test_inventaris_overlap_eenmaal_rol_en_afgewezen(client):
    await _met_elementen()
    wg = await _nieuw(client)
    wg = (await _bron(client, wg, bron_iri=ONE, bereik="node", rol="analyseren"))["werkgebied"]
    wg = (await _bron(client, wg, bron_iri=ART, rol="context"))["werkgebied"]
    inv = (await client.get(f"/v1/werkgebieden/{wg['id']}/elementen")).json()
    assert inv["volledig"] is True
    per_tekst = {(e["klasse"], e["tekst"]): e for e in inv["elementen"]}
    assert len(inv["elementen"]) == 3                                   # elk element één keer
    lid1 = next(e for e in inv["elementen"] if e["eigenaar_iri"] == ONE)
    lid2 = next(e for e in inv["elementen"] if e["eigenaar_iri"] == TWO)
    assert (lid1["rol"], lid2["rol"]) == ("analyseren", "context")      # analyse wint bij overlap
    assert all(not e["deels_buiten"] for e in per_tekst.values())
    per_sel = {s["bron_iri"]: s for s in inv["selecties"]}
    assert (per_sel[ONE]["aantal"], per_sel[ONE]["afgewezen"]) == (1, 1)
    assert per_sel[ART]["aantal"] == 3 and per_sel[ART]["afgewezen"] == 1
    assert all(e["lifecycle"] != "rejected" for e in inv["elementen"])


async def test_inventaris_deels_buiten_wordt_gemeld_niet_verbreed(client):
    await _met_elementen()
    wg = await _nieuw(client)
    wg = (await _bron(client, wg, bron_iri=ART, bereik="node"))["werkgebied"]
    inv = (await client.get(f"/v1/werkgebieden/{wg['id']}/elementen")).json()
    # Alleen het element van het artikel zelf (eigenaar ART, ankers in de leden) valt erin.
    assert [(e["eigenaar_iri"], e["deels_buiten"]) for e in inv["elementen"]] == [(ART, True)]


async def test_inventaris_bron_gewijzigd_en_onbereikbaar(client, graaf):
    await _met_elementen()
    wg = await _nieuw(client)
    wg = (await _bron(client, wg, bron_iri=TWO, bereik="node"))["werkgebied"]
    wg = (await _bron(client, wg, bron_iri=ART2))["werkgebied"]
    graaf.tweede_lid = "Gamma"                          # de tekst van lid 2 is intussen veranderd
    graaf.weg.add(LAW2)                                 # en de AWR is even niet bereikbaar
    inv = (await client.get(f"/v1/werkgebieden/{wg['id']}/elementen")).json()
    per_sel = {s["bron_iri"]: s for s in inv["selecties"]}
    assert per_sel[TWO]["bron_gewijzigd"] is True and per_sel[TWO]["onbereikbaar"] is None
    assert per_sel[ART2]["onbereikbaar"] and inv["volledig"] is False
    assert [e["eigenaar_iri"] for e in inv["elementen"]] == [TWO]       # de rest komt wel


async def test_wijzigen_van_een_selectie_in_een_ander_werkgebied_kan_niet(client):
    a, b = await _nieuw(client, "A"), await _nieuw(client, "B")
    sa = await _bron(client, a, bron_iri=ART)
    b = (await client.get(f"/v1/werkgebieden/{b['id']}")).json()
    r = await client.delete(f"/v1/werkgebieden/{b['id']}/bronnen/{sa['selectie']['id']}",
                            params={"verwachte_revisie": b["revisie"]})
    assert r.status_code == 404
