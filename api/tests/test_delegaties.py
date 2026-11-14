"""Delegaties (ADR-016 §A5, ADR-012): het object met zijn sloten – een regie in een werkgebied en een subagent, ook in
een los gesprek – en deelgesprekken onder het gesprek dat de delegatie startte."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import update

from app import db, delegatie_store
from test_werkgebieden import _nieuw, client, database, graaf  # noqa: F401

G = "/v1/gesprekken"
B = {"X-User-Id": "jurist-b"}


async def _gesprek(client, headers=None, **body) -> dict:
    r = await client.post(G, json={"titel": "Regie", **body}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


D = "/v1/delegaties"


async def _start(client, wg, gesprek, headers=None, **extra):
    return await client.post(D, headers=headers, json={
        "werkgebied_id": wg["id"], "gesprek_id": gesprek["id"], "opdracht": "bronnen", "plan_id": "abcdef0123456789",
        "plan": {"taken": [{"deelvraag_id": "d1"}]}, **extra})


async def _subagent(client, gesprek, headers=None, werkgebied_id=""):
    return await client.post(D, headers=headers, json={
        "soort": "subagent", "werkgebied_id": werkgebied_id, "gesprek_id": gesprek["id"], "opdracht": "subagent",
        "plan_id": "abcdef0123456789", "plan": {"taken": [{"profiel": "algemeen", "opdracht": {"doel": "Zoek"}}]}})


async def test_een_regie_start_loopt_en_sluit_af(client):
    wg = await _nieuw(client)
    g = await _gesprek(client, werkgebied_id=wg["id"])
    r = await _start(client, wg, g, budget_aandeel=1000)
    assert r.status_code == 201, r.text
    regie = r.json()
    assert (regie["status"], regie["opdracht"], regie["budget_aandeel"]) == ("loopt", "bronnen", 1000)
    assert regie["user_id"] == "jurist-a" and regie["plan"]["taken"][0]["deelvraag_id"] == "d1"

    r = await client.patch(f"{D}/{regie['id']}", json={"status": "loopt"})
    assert r.status_code == 200 and r.json()["status"] == "loopt"
    r = await client.patch(f"{D}/{regie['id']}", json={"status": "klaar", "uitkomst": {"opgeleverd": 2}})
    assert r.json()["status"] == "klaar" and r.json()["uitkomst"] == {"opgeleverd": 2} and r.json()["afgerond"]
    # Dezelfde eindstand nog eens is een herhaald verzoek, een andere niet.
    assert (await client.patch(f"{D}/{regie['id']}", json={"status": "klaar"})).status_code == 200
    r = await client.patch(f"{D}/{regie['id']}", json={"status": "gestopt"})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "delegatie_afgerond"
    assert [x["id"] for x in (await client.get(D, params={"werkgebied_id": wg["id"]})).json()] == [regie["id"]]


async def test_een_regie_per_werkgebied_en_per_gebruiker(client):
    wg, wg2 = await _nieuw(client, "Een"), await _nieuw(client, "Twee")
    g = await _gesprek(client, werkgebied_id=wg["id"])
    eerste = (await _start(client, wg, g)).json()
    # Een collega in hetzelfde werkgebied: het werkgebied heeft al een regie.
    gb = await _gesprek(client, headers=B, werkgebied_id=wg["id"])
    r = await _start(client, wg, gb, headers=B)
    assert r.status_code == 409 and r.json()["detail"]["delegatie_id"] == eerste["id"]
    # Dezelfde jurist in een ander werkgebied: hij heeft al een regie.
    g2 = await _gesprek(client, werkgebied_id=wg2["id"])
    r = await _start(client, wg2, g2)
    assert r.status_code == 409 and r.json()["detail"]["werkgebied_id"] == wg["id"]
    # Na afloop is het slot vrij.
    await client.patch(f"{D}/{eerste['id']}", json={"status": "gestopt"})
    assert (await _start(client, wg2, g2)).status_code == 201


async def test_een_verweesde_regie_houdt_het_slot_niet_vast(client):
    wg = await _nieuw(client)
    g = await _gesprek(client, werkgebied_id=wg["id"])
    oud = (await _start(client, wg, g)).json()
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.delegaties).values(hartslag=db.utcnow() - delegatie_store.VERWEESD_NA - timedelta(seconds=5)))
    assert (await client.get(f"{D}/{oud['id']}")).json()["status"] == "mislukt"
    nieuw = await _start(client, wg, g)
    assert nieuw.status_code == 201, nieuw.text
    oud_nu = (await client.get(f"{D}/{oud['id']}")).json()
    assert oud_nu["status"] == "mislukt" and oud_nu["uitkomst"] == {"reden": "verweesd"}


async def test_alleen_de_eigenaar_en_het_eigen_gesprek(client):
    wg, ander = await _nieuw(client, "Een"), await _nieuw(client, "Ander")
    g = await _gesprek(client, werkgebied_id=wg["id"])
    regie = (await _start(client, wg, g)).json()
    assert (await client.patch(f"{D}/{regie['id']}", headers=B, json={"status": "gestopt"})).status_code == 404
    # Het regiegesprek van een ander, of uit een ander werkgebied, kan niet.
    gb = await _gesprek(client, headers=B, werkgebied_id=ander["id"])
    assert (await _start(client, ander, gb)).status_code == 404
    g_ander = await _gesprek(client, werkgebied_id=ander["id"])
    await client.patch(f"{D}/{regie['id']}", json={"status": "klaar"})
    r = await _start(client, wg, g_ander)
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "ander_werkgebied"
    assert (await client.post(D, json={"werkgebied_id": "bestaat-niet", "gesprek_id": g["id"], "opdracht": "bronnen",
                                       "plan_id": "abcdef0123456789"})).status_code == 404


async def test_deelgesprekken_onder_een_regiegesprek(client):
    wg = await _nieuw(client)
    ouder = await _gesprek(client, werkgebied_id=wg["id"])
    regie = (await _start(client, wg, ouder)).json()
    kind = await _gesprek(client, titel="Bronnen · deelvraag 1", werkgebied_id=wg["id"],
                          ouder_id=ouder["id"], delegatie_id=regie["id"])
    assert (kind["ouder_id"], kind["delegatie_id"], kind["profiel"]) == (ouder["id"], regie["id"], "")
    los = await _gesprek(client, werkgebied_id=wg["id"])

    lijst = (await client.get(G, params={"ouder_id": ouder["id"]})).json()
    assert [x["id"] for x in lijst] == [kind["id"]] and lijst[0]["delegatie_id"] == regie["id"]
    boven = {x["id"] for x in (await client.get(G, params={"ouder_id": ""})).json()}
    assert boven == {ouder["id"], los["id"]}

    # De ouder weg: het deelgesprek blijft, los.
    assert (await client.delete(f"{G}/{ouder['id']}")).status_code == 204
    nu = (await client.get(f"{G}/{kind['id']}")).json()
    assert (nu["ouder_id"], nu["delegatie_id"], nu["werkgebied_id"]) == ("", "", wg["id"])


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
    assert (await client.post(G, json={"werkgebied_id": wg["id"], "delegatie_id": "x"})).status_code == 422
    # Verhuizen maakt het deelgesprek los.
    r = await client.patch(f"{G}/{kind['id']}", json={"werkgebied_id": ander["id"]})
    assert (r.json()["ouder_id"], r.json()["werkgebied_id"]) == ("", ander["id"])


async def test_een_werkgebied_wissen_neemt_de_delegaties_mee(client):
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


async def test_een_subagent_ook_in_een_los_gesprek(client):
    """ADR-016 §A3: een subagent kan buiten een werkgebied; zijn deelgesprek draagt het profiel."""
    ouder = await _gesprek(client)
    r = await _subagent(client, ouder)
    assert r.status_code == 201, r.text
    d = r.json()
    assert (d["soort"], d["opdracht"], d["werkgebied_id"], d["status"]) == ("subagent", "subagent", "", "loopt")
    kind = await _gesprek(client, titel="Rechtspraak", ouder_id=ouder["id"], delegatie_id=d["id"], profiel="algemeen")
    assert (kind["ouder_id"], kind["delegatie_id"], kind["profiel"], kind["werkgebied_id"]) == (
        ouder["id"], d["id"], "algemeen", "")
    assert [x["id"] for x in (await client.get(D, params={"gesprek_id": ouder["id"]})).json()] == [d["id"]]
    # Een tweede delegatie van dezelfde gebruiker wacht op de eerste, ook een regie elders.
    wg = await _nieuw(client)
    g = await _gesprek(client, werkgebied_id=wg["id"])
    r = await _start(client, wg, g)
    assert r.status_code == 409 and r.json()["detail"]["delegatie_id"] == d["id"]
    await client.patch(f"{D}/{d['id']}", json={"status": "klaar", "uitkomst": {"status": "klaar"}})
    assert (await _start(client, wg, g)).status_code == 201


async def test_een_subagent_in_een_werkgebied_houdt_het_werkgebied_niet_bezet(client):
    """Alleen een regie heeft het slot per werkgebied: een subagent van een collega blokkeert geen regie."""
    wg = await _nieuw(client)
    gb = await _gesprek(client, headers=B, werkgebied_id=wg["id"])
    assert (await _subagent(client, gb, headers=B, werkgebied_id=wg["id"])).status_code == 201
    g = await _gesprek(client, werkgebied_id=wg["id"])
    assert (await _start(client, wg, g)).status_code == 201


async def test_soort_opdracht_en_werkgebied_passen_bij_elkaar(client):
    wg = await _nieuw(client)
    los = await _gesprek(client)
    g = await _gesprek(client, werkgebied_id=wg["id"])
    for body in ({"soort": "regie", "opdracht": "bronnen", "gesprek_id": los["id"]},          # regie zonder werkgebied
                 {"soort": "regie", "opdracht": "subagent", "werkgebied_id": wg["id"], "gesprek_id": g["id"]},
                 {"soort": "subagent", "opdracht": "bronnen", "gesprek_id": los["id"]}):
        r = await client.post(D, json={"plan_id": "abcdef0123456789", **body})
        assert r.status_code == 422, (body, r.text)
    # Het werkgebied is dat van het gesprek: een los gesprek met een werkgebied, of andersom, kan niet.
    r = await client.post(D, json={"soort": "subagent", "opdracht": "subagent", "werkgebied_id": wg["id"],
                                   "gesprek_id": los["id"], "plan_id": "abcdef0123456789"})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "ander_werkgebied"
    assert (await _subagent(client, g)).status_code == 409
    # De lijst vraagt één werkgebied of één gesprek.
    assert (await client.get(D)).status_code == 422


async def test_een_deelgesprek_van_een_los_gesprek_blijft_los(client):
    wg = await _nieuw(client)
    ouder = await _gesprek(client)
    r = await client.post(G, json={"werkgebied_id": wg["id"], "ouder_id": ouder["id"]})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "ander_werkgebied"
    assert (await client.post(G, json={"profiel": "algemeen"})).status_code == 422
    assert (await client.post(G, json={"ouder_id": ouder["id"], "profiel": "Niet Goed"})).status_code == 422
