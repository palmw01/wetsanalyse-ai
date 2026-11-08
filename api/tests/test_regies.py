"""Regie binnen een werkgebied (ADR-012): het regie-object met zijn sloten, en deelgesprekken onder een regiegesprek."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import update

from app import db, regie_store
from test_werkgebieden import _nieuw, client, database, graaf  # noqa: F401

G = "/v1/gesprekken"
B = {"X-User-Id": "jurist-b"}


async def _gesprek(client, headers=None, **body) -> dict:
    r = await client.post(G, json={"titel": "Regie", **body}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _regies(wg: dict) -> str:
    return f"/v1/werkgebieden/{wg['id']}/regies"


async def _start(client, wg, gesprek, headers=None, **extra):
    return await client.post(_regies(wg), headers=headers, json={
        "gesprek_id": gesprek["id"], "opdracht": "bronnen", "plan_id": "abcdef0123456789",
        "plan": {"taken": [{"deelvraag_id": "d1"}]}, **extra})


async def test_een_regie_start_loopt_en_sluit_af(client):
    wg = await _nieuw(client)
    g = await _gesprek(client, werkgebied_id=wg["id"])
    r = await _start(client, wg, g, budget_aandeel=1000)
    assert r.status_code == 201, r.text
    regie = r.json()
    assert (regie["status"], regie["opdracht"], regie["budget_aandeel"]) == ("loopt", "bronnen", 1000)
    assert regie["user_id"] == "jurist-a" and regie["plan"]["taken"][0]["deelvraag_id"] == "d1"

    r = await client.patch(f"{_regies(wg)}/{regie['id']}", json={"status": "loopt"})
    assert r.status_code == 200 and r.json()["status"] == "loopt"
    r = await client.patch(f"{_regies(wg)}/{regie['id']}", json={"status": "klaar", "uitkomst": {"opgeleverd": 2}})
    assert r.json()["status"] == "klaar" and r.json()["uitkomst"] == {"opgeleverd": 2} and r.json()["afgerond"]
    # Dezelfde eindstand nog eens is een herhaald verzoek, een andere niet.
    assert (await client.patch(f"{_regies(wg)}/{regie['id']}", json={"status": "klaar"})).status_code == 200
    r = await client.patch(f"{_regies(wg)}/{regie['id']}", json={"status": "gestopt"})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "regie_afgerond"
    assert [x["id"] for x in (await client.get(_regies(wg))).json()] == [regie["id"]]


async def test_een_regie_per_werkgebied_en_per_gebruiker(client):
    wg, wg2 = await _nieuw(client, "Een"), await _nieuw(client, "Twee")
    g = await _gesprek(client, werkgebied_id=wg["id"])
    eerste = (await _start(client, wg, g)).json()
    # Een collega in hetzelfde werkgebied: het werkgebied heeft al een regie.
    gb = await _gesprek(client, headers=B, werkgebied_id=wg["id"])
    r = await _start(client, wg, gb, headers=B)
    assert r.status_code == 409 and r.json()["detail"]["regie_id"] == eerste["id"]
    # Dezelfde jurist in een ander werkgebied: hij heeft al een regie.
    g2 = await _gesprek(client, werkgebied_id=wg2["id"])
    r = await _start(client, wg2, g2)
    assert r.status_code == 409 and r.json()["detail"]["werkgebied_id"] == wg["id"]
    # Na afloop is het slot vrij.
    await client.patch(f"{_regies(wg)}/{eerste['id']}", json={"status": "gestopt"})
    assert (await _start(client, wg2, g2)).status_code == 201


async def test_een_verweesde_regie_houdt_het_slot_niet_vast(client):
    wg = await _nieuw(client)
    g = await _gesprek(client, werkgebied_id=wg["id"])
    oud = (await _start(client, wg, g)).json()
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.regies).values(hartslag=db.utcnow() - regie_store.VERWEESD_NA - timedelta(seconds=5)))
    assert (await client.get(f"{_regies(wg)}/{oud['id']}")).json()["status"] == "mislukt"
    nieuw = await _start(client, wg, g)
    assert nieuw.status_code == 201, nieuw.text
    oud_nu = (await client.get(f"{_regies(wg)}/{oud['id']}")).json()
    assert oud_nu["status"] == "mislukt" and oud_nu["uitkomst"] == {"reden": "verweesd"}


async def test_alleen_de_eigenaar_en_het_eigen_gesprek(client):
    wg, ander = await _nieuw(client, "Een"), await _nieuw(client, "Ander")
    g = await _gesprek(client, werkgebied_id=wg["id"])
    regie = (await _start(client, wg, g)).json()
    assert (await client.patch(f"{_regies(wg)}/{regie['id']}", headers=B, json={"status": "gestopt"})).status_code == 404
    # Het regiegesprek van een ander, of uit een ander werkgebied, kan niet.
    gb = await _gesprek(client, headers=B, werkgebied_id=ander["id"])
    assert (await _start(client, ander, gb)).status_code == 404
    g_ander = await _gesprek(client, werkgebied_id=ander["id"])
    await client.patch(f"{_regies(wg)}/{regie['id']}", json={"status": "klaar"})
    r = await _start(client, wg, g_ander)
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "ander_werkgebied"
    assert (await client.post("/v1/werkgebieden/bestaat-niet/regies", json={
        "gesprek_id": g["id"], "opdracht": "bronnen", "plan_id": "abcdef0123456789"})).status_code == 404


async def test_deelgesprekken_onder_een_regiegesprek(client):
    wg = await _nieuw(client)
    ouder = await _gesprek(client, werkgebied_id=wg["id"])
    regie = (await _start(client, wg, ouder)).json()
    kind = await _gesprek(client, titel="Bronnen · deelvraag 1", werkgebied_id=wg["id"],
                          ouder_id=ouder["id"], regie_id=regie["id"])
    assert (kind["ouder_id"], kind["regie_id"]) == (ouder["id"], regie["id"])
    los = await _gesprek(client, werkgebied_id=wg["id"])

    lijst = (await client.get(G, params={"ouder_id": ouder["id"]})).json()
    assert [x["id"] for x in lijst] == [kind["id"]] and lijst[0]["regie_id"] == regie["id"]
    boven = {x["id"] for x in (await client.get(G, params={"ouder_id": ""})).json()}
    assert boven == {ouder["id"], los["id"]}

    # De ouder weg: het deelgesprek blijft, los.
    assert (await client.delete(f"{G}/{ouder['id']}")).status_code == 204
    nu = (await client.get(f"{G}/{kind['id']}")).json()
    assert (nu["ouder_id"], nu["regie_id"], nu["werkgebied_id"]) == ("", "", wg["id"])


async def test_een_deelgesprek_hoort_bij_zijn_ouder(client):
    wg, ander = await _nieuw(client, "Een"), await _nieuw(client, "Ander")
    ouder = await _gesprek(client, werkgebied_id=wg["id"])
    r = await client.post(G, json={"werkgebied_id": ander["id"], "ouder_id": ouder["id"]})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "ander_werkgebied"
    vreemd = await _gesprek(client, headers=B, werkgebied_id=wg["id"])
    assert (await client.post(G, json={"werkgebied_id": wg["id"], "ouder_id": vreemd["id"]})).status_code == 404
    kind = await _gesprek(client, werkgebied_id=wg["id"], ouder_id=ouder["id"])
    r = await client.post(G, json={"werkgebied_id": wg["id"], "ouder_id": kind["id"]})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "te_diep"
    assert (await client.post(G, json={"werkgebied_id": wg["id"], "regie_id": "x"})).status_code == 422
    # Verhuizen maakt het deelgesprek los.
    r = await client.patch(f"{G}/{kind['id']}", json={"werkgebied_id": ander["id"]})
    assert (r.json()["ouder_id"], r.json()["werkgebied_id"]) == ("", ander["id"])


async def test_een_werkgebied_wissen_neemt_de_regies_mee(client):
    wg = await _nieuw(client)
    ouder = await _gesprek(client, werkgebied_id=wg["id"])
    await _start(client, wg, ouder)
    kind = await _gesprek(client, werkgebied_id=wg["id"], ouder_id=ouder["id"])
    r = await client.delete(f"/v1/werkgebieden/{wg['id']}", params={"verwachte_revisie": wg["revisie"]})
    assert r.status_code == 200, r.text
    nu = (await client.get(f"{G}/{kind['id']}")).json()
    assert (nu["werkgebied_id"], nu["ouder_id"]) == ("", "")


async def test_een_bericht_draagt_het_regieartefact_en_de_bevestiging(client):
    wg = await _nieuw(client)
    g = await _gesprek(client, werkgebied_id=wg["id"])
    regie = (await _start(client, wg, g)).json()
    r = await client.post(f"{G}/{g['id']}/berichten", json={
        "rol": "assistant", "tekst": "Plan", "run_id": "r1",
        "bevestiging": {"soort": "regie", "werkgebied_id": wg["id"], "aantal": 2, "plan_id": "0123456789abcdef",
                        "opdracht": "bronnen"},
        "artefact": {"soort": "regie", "ref": {"werkgebied_id": wg["id"], "regie_id": regie["id"]}}})
    assert r.status_code == 201, r.text
    bericht = (await client.get(f"{G}/{g['id']}")).json()["berichten"][-1]
    assert bericht["bevestiging"]["plan_id"] == "0123456789abcdef" and bericht["bevestiging"]["opdracht"] == "bronnen"
    assert bericht["artefact"]["ref"]["regie_id"] == regie["id"]
    # Een regieartefact zonder regie, en een plan_id dat geen plan_id is, kunnen niet.
    for fout in ({"artefact": {"soort": "regie", "ref": {"werkgebied_id": wg["id"]}}},
                 {"bevestiging": {"soort": "regie", "werkgebied_id": wg["id"], "aantal": 1, "plan_id": "x"}}):
        assert (await client.post(f"{G}/{g['id']}/berichten", json={"rol": "assistant", **fout})).status_code == 422
    # Een bevestiging zonder plan blijft zoals ze was.
    await client.post(f"{G}/{g['id']}/berichten", json={"rol": "assistant", "run_id": "r2", "bevestiging": {
        "soort": "werkgebied_annoteren", "werkgebied_id": wg["id"], "aantal": 1}})
    oud = (await client.get(f"{G}/{g['id']}")).json()["berichten"][-1]["bevestiging"]
    assert "plan_id" not in oud and "opdracht" not in oud
