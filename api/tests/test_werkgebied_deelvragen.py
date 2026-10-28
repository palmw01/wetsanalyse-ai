"""Deelvragen bij een werkgebied (open keuze 4: optioneel) en de dekkingscheck ertegen."""
from __future__ import annotations

from sqlalchemy import insert

from app import db
from test_annotatie_v2 import ART
from test_bronnen_runs import _k, _start, _uitkomst
from test_werkgebieden import _bron, _nieuw, client, database, graaf  # noqa: F401


async def _dv(client, wg, vraag, status=201):
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/deelvragen",
                          json={"verwachte_revisie": wg["revisie"], "vraag": vraag})
    assert r.status_code == status, r.text
    return r.json()


async def _patch(client, wg, did, verwacht=200, **velden):
    r = await client.patch(f"/v1/werkgebieden/{wg['id']}/deelvragen/{did}",
                           json={"verwachte_revisie": wg["revisie"], **velden})
    assert r.status_code == verwacht, r.text
    return r.json()


async def _koppel(client, wg, did, verwacht=200, **velden):
    r = await client.put(f"/v1/werkgebieden/{wg['id']}/deelvragen/{did}/koppelingen",
                         json={"verwachte_revisie": wg["revisie"], **velden})
    assert r.status_code == verwacht, r.text
    return r.json()


async def _dekking(client, wg) -> dict:
    r = await client.get(f"/v1/werkgebieden/{wg['id']}/deelvragen/dekking")
    assert r.status_code == 200, r.text
    return r.json()


async def _begrip(wg, naam, status) -> str:
    bid = f"b-{naam}"
    nu = db.utcnow()
    async with db.get_engine().begin() as conn:
        await conn.execute(insert(db.begrippen).values(
            id=bid, werkgebied_id=wg["id"], status=status, revisie=1, inhoud={"naam": naam},
            aangemaakt_door="jurist-a", aangemaakt=nu, gewijzigd=nu))
    return bid


async def test_zonder_deelvragen_verandert_er_niets(client):
    wg = await _nieuw(client)
    assert wg["deelvragen"] == []
    assert await _dekking(client, wg) == {"deelvragen": [], "telling": {"geen_bron": 0, "met_bron": 0},
                                          "totaal": 0}


async def test_toevoegen_wijzigen_en_weghalen_dragen_de_revisie(client):
    wg = await _nieuw(client)
    wg = await _dv(client, wg, "  Wanneer is een  aanslag invorderbaar? ")
    assert wg["revisie"] == 2
    [d] = wg["deelvragen"]
    assert (d["vraag"], d["status"], d["herkomst"], d["volgorde"]) == \
        ("Wanneer is een aanslag invorderbaar?", "actief", "analist", 0)
    # Dezelfde vraag (andere hoofdletters en leestekens) nog eens: 409.
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/deelvragen",
                          json={"verwachte_revisie": wg["revisie"], "vraag": "wanneer is een aanslag invorderbaar"})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "al_gesteld"
    # Een oude revisie: 412.
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/deelvragen", json={"verwachte_revisie": 1, "vraag": "Wie?"})
    assert r.status_code == 412
    wg = await _patch(client, wg, d["id"], vraag="Wanneer is een belastingaanslag invorderbaar?")
    assert wg["deelvragen"][0]["vraag"] == "Wanneer is een belastingaanslag invorderbaar?"
    r = await client.delete(f"/v1/werkgebieden/{wg['id']}/deelvragen/{d['id']}",
                            params={"verwachte_revisie": wg["revisie"]})
    assert r.status_code == 200 and r.json()["deelvragen"] == []
    acties = [a["actie"] for a in (await client.get(f"/v1/werkgebieden/{wg['id']}/audit")).json()["audit"]]
    assert acties[:3] == ["deelvraag-verwijderd", "deelvraag-gewijzigd", "deelvraag-toegevoegd"]


async def test_voorstellen_van_lex_overnemen_en_afwijzen(client):
    wg = await _nieuw(client)
    wg = await _dv(client, wg, "Wie is de belastingschuldige?")
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/deelvragen/voorstellen",
                          json={"vragen": ["Wie is de belastingschuldige", "Wanneer vervalt de termijn?",
                                           "Welke uitzonderingen zijn er?"], "model": "m"})
    assert r.status_code == 200, r.text
    uit = r.json()
    assert len(uit["nieuw"]) == 2 and uit["overgeslagen"] == [{"vraag": "Wie is de belastingschuldige", "reden": "actief"}]
    wg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    assert wg["revisie"] == 2, "een voorstel raakt de scope niet"
    termijn, uitzondering = (d for d in wg["deelvragen"] if d["status"] == "voorgesteld")
    assert termijn["herkomst"] == "lex"
    # Een voorstel koppelen kan niet: eerst overnemen.
    await _koppel(client, wg, termijn["id"], verwacht=409, bronnen=[])
    wg = await _patch(client, wg, termijn["id"], status="actief")
    # Afwijzen vraagt een reden.
    await _patch(client, wg, uitzondering["id"], verwacht=422, status="afgewezen")
    wg = await _patch(client, wg, uitzondering["id"], status="afgewezen", reden="hoort bij een ander werkgebied")
    assert [d["vraag"] for d in wg["deelvragen"]] == ["Wie is de belastingschuldige?", "Wanneer vervalt de termijn?"]
    # Wat is afgewezen, stelt Lex niet opnieuw voor.
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/deelvragen/voorstellen",
                          json={"vragen": ["Welke uitzonderingen zijn er?"]})
    assert r.json()["nieuw"] == [] and r.json()["overgeslagen"][0]["reden"] == "afgewezen"


async def test_dekking_per_deelvraag(client):
    wg = await _nieuw(client)
    wg = (await _bron(client, wg, bron_iri=ART))["werkgebied"]
    wg = await _dv(client, wg, "Wanneer is een aanslag invorderbaar?")
    wg = await _dv(client, wg, "Wie is de belastingschuldige?")
    wg = await _dv(client, wg, "Welke termijnen gelden er?")
    a, b, c = wg["deelvragen"]
    sel = wg["bronnen"][0]["id"]
    geaccordeerd, concept = await _begrip(wg, "invorderbaar", "geaccordeerd"), await _begrip(wg, "termijn", "concept")
    wg = await _koppel(client, wg, a["id"], bronnen=[sel], begrippen=[geaccordeerd])
    wg = await _koppel(client, wg, b["id"], bronnen=[sel], begrippen=[concept])
    # Iets buiten het werkgebied: 422.
    r = await client.put(f"/v1/werkgebieden/{wg['id']}/deelvragen/{c['id']}/koppelingen",
                         json={"verwachte_revisie": wg["revisie"], "bronnen": ["vreemd"]})
    assert r.status_code == 422 and r.json()["detail"]["ids"] == ["vreemd"]
    d = await _dekking(client, wg)
    # De dekking is of er een bron bij hoort; een begrip telt niet (spoor K: begrippen horen bij het werkgebied).
    assert [x["stand"] for x in d["deelvragen"]] == ["met_bron", "met_bron", "geen_bron"]
    assert d["telling"] == {"geen_bron": 1, "met_bron": 2}
    assert d["deelvragen"][0]["bronnen"][0]["id"] == sel
    assert "begrippen" not in d["deelvragen"][0]
    # Een weggehaalde selectie telt niet meer mee.
    r = await client.delete(f"/v1/werkgebieden/{wg['id']}/bronnen/{sel}", params={"verwachte_revisie": wg["revisie"]})
    assert r.status_code == 200
    d = await _dekking(client, wg)
    assert d["deelvragen"][1]["bronnen"] == [] and d["deelvragen"][1]["stand"] == "geen_bron"


async def test_de_bronnenrun_zoekt_ook_per_deelvraag(client):
    wg = await _nieuw(client)
    zonder = await _start(client, wg, 201)
    wg = await _dv(client, wg, "Wanneer is een aanslag invorderbaar?")
    [d] = wg["deelvragen"]
    run = await _start(client, wg, 201)
    assert run["id"] != zonder["id"], "een nieuwe deelvraag is een nieuwe invoer"
    invoer = (await client.get(f"/v1/werkgebieden/{wg['id']}/bronnen-runs/{run['id']}",
                               params={"invoer": True})).json()["invoer"]
    assert invoer["deelvragen"] == [{"id": d["id"], "vraag": "Wanneer is een aanslag invorderbaar?"}]
    # Een voorstel dat nog niet is overgenomen, zit niet in de invoer.
    await client.post(f"/v1/werkgebieden/{wg['id']}/deelvragen/voorstellen", json={"vragen": ["Wie betaalt?"]})
    assert (await _start(client, wg, 200))["id"] == run["id"]

    # Opnemen van een kandidaat die bij de deelvraag gevonden is, koppelt de selectie eraan.
    k = _k(ART, "kern", ("deelvraag", ""))
    k["bewijs"][0]["detail"] = {"deelvraag_id": d["id"], "vraag": d["vraag"]}
    r = await _uitkomst(client, wg, run, [k], meting={"deelvraag": {"aantal": 1}})
    assert r.status_code == 200, r.text
    kid = (await client.get(f"/v1/werkgebieden/{wg['id']}/kandidaten")).json()["kandidaten"][0]["id"]
    wg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/kandidaten/{kid}/opnemen",
                          json={"verwachte_revisie": wg["revisie"]})
    assert r.status_code == 200, r.text
    wg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    actief = next(x for x in wg["deelvragen"] if x["status"] == "actief")
    assert actief["bronnen"] == [r.json()["selectie"]["id"]]


async def test_zonder_kern_of_analysevraag_maar_met_deelvragen_mag_een_run(client):
    r = await client.post("/v1/werkgebieden", json={"naam": "Leeg"})
    wg = await _dv(client, r.json(), "Wanneer is een aanslag invorderbaar?")
    await _start(client, wg, 201)


async def _verbeter(client, wg, vervangt, vragen, status=200):
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/deelvragen/voorstellen",
                          json={"vragen": vragen, "vervangt": vervangt, "model": "m"})
    assert r.status_code == status, r.text
    return r.json()


async def test_een_overgenomen_herformulering_vervangt_de_deelvraag(client):
    wg = await _nieuw(client)
    wg = (await _bron(client, wg, bron_iri=ART))["werkgebied"]
    wg = await _dv(client, wg, "Wie betaalt?")
    wg = await _dv(client, wg, "Wanneer is een aanslag invorderbaar?")
    oud, tweede = wg["deelvragen"]
    sel = wg["bronnen"][0]["id"]
    begrip = await _begrip(wg, "belastingschuldige", "geaccordeerd")
    wg = await _koppel(client, wg, oud["id"], bronnen=[sel], begrippen=[begrip])
    uit = await _verbeter(client, wg, oud["id"], ["Wie is de belastingschuldige van de aanslag?"])
    [nid] = uit["nieuw"]
    voorstel = next(d for d in uit["deelvragen"] if d["id"] == nid)
    assert (voorstel["status"], voorstel["vervangt"]) == ("voorgesteld", oud["id"])

    detail = (await client.get(f"/v1/werkgebieden/{wg['id']}/deelvragen/{oud['id']}")).json()
    assert [v["id"] for v in detail["voorstellen"]] == [nid] and detail["opvolgers"] == []

    wg = await _patch(client, wg, nid, status="actief")
    # De opvolger staat op de plek van de oude, met haar koppelingen; de oude is uit de lijst.
    assert [d["id"] for d in wg["deelvragen"]] == [nid, tweede["id"]]
    nieuw = wg["deelvragen"][0]
    assert (nieuw["bronnen"], nieuw["begrippen"]) == ([sel], [begrip])
    assert (await _dekking(client, wg))["deelvragen"][0]["stand"] == "met_bron"
    detail = (await client.get(f"/v1/werkgebieden/{wg['id']}/deelvragen/{oud['id']}")).json()
    assert detail["status"] == "vervangen" and detail["opvolgers"] == [{"id": nid, "vraag": nieuw["vraag"]}]
    acties = [a["actie"] for a in (await client.get(f"/v1/werkgebieden/{wg['id']}/audit")).json()["audit"]]
    assert "deelvraag-vervangen" in acties
    # Een vervangen deelvraag wijzig je niet meer, en Lex stelt haar tekst niet opnieuw voor.
    await _patch(client, wg, oud["id"], verwacht=409, vraag="Wie betaalt eigenlijk?")
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/deelvragen/voorstellen", json={"vragen": ["Wie betaalt?"]})
    assert r.json()["overgeslagen"][0]["reden"] == "vervangen"
    # De status `vervangen` zet de analist niet zelf.
    await _patch(client, wg, tweede["id"], verwacht=422, status="vervangen")


async def test_een_splitsing_vervangt_een_keer_en_elk_deel_erft(client):
    wg = await _nieuw(client)
    wg = (await _bron(client, wg, bron_iri=ART))["werkgebied"]
    wg = await _dv(client, wg, "Wie betaalt en wanneer?")
    [oud] = wg["deelvragen"]
    sel = wg["bronnen"][0]["id"]
    wg = await _koppel(client, wg, oud["id"], bronnen=[sel])
    a, b = (await _verbeter(client, wg, oud["id"], ["Wie betaalt?", "Wanneer moet er betaald zijn?"]))["nieuw"]
    wg = await _patch(client, wg, a, status="actief")
    wg = await _patch(client, wg, b, status="actief")
    assert [d["id"] for d in wg["deelvragen"]] == [a, b]
    assert all(d["bronnen"] == [sel] for d in wg["deelvragen"])
    acties = [x["actie"] for x in (await client.get(f"/v1/werkgebieden/{wg['id']}/audit")).json()["audit"]]
    assert acties.count("deelvraag-vervangen") == 1


async def test_vervangt_moet_een_actieve_deelvraag_zijn(client):
    wg = await _nieuw(client)
    await _verbeter(client, wg, "bestaat-niet", ["Wie betaalt?"], status=422)
    uit = await _verbeter(client, wg, "", ["Wie betaalt?"])
    # Een voorstel is geen actieve deelvraag: verbeteren kan pas na overnemen.
    r = await _verbeter(client, wg, uit["nieuw"][0], ["Wie is de belastingschuldige?"], status=422)
    assert r["detail"]["fout"] == "vervangt_onbekend"
    r = await client.get(f"/v1/werkgebieden/{wg['id']}/deelvragen/bestaat-niet")
    assert r.status_code == 404


async def test_een_kandidaat_van_een_vervangen_deelvraag_landt_bij_de_opvolger(client):
    wg = await _nieuw(client)
    wg = await _dv(client, wg, "Wanneer is een aanslag invorderbaar?")
    [oud] = wg["deelvragen"]
    run = await _start(client, wg, 201)
    k = _k(ART, "kern", ("deelvraag", ""))
    k["bewijs"][0]["detail"] = {"deelvraag_id": oud["id"], "vraag": oud["vraag"]}
    assert (await _uitkomst(client, wg, run, [k], meting={"deelvraag": {"aantal": 1}})).status_code == 200
    [nid] = (await _verbeter(client, wg, oud["id"], ["Wanneer is een belastingaanslag invorderbaar?"]))["nieuw"]
    wg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    wg = await _patch(client, wg, nid, status="actief")
    kid = (await client.get(f"/v1/werkgebieden/{wg['id']}/kandidaten")).json()["kandidaten"][0]["id"]
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/kandidaten/{kid}/opnemen",
                          json={"verwachte_revisie": wg["revisie"]})
    assert r.status_code == 200, r.text
    wg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    assert wg["deelvragen"][0]["id"] == nid and wg["deelvragen"][0]["bronnen"] == [r.json()["selectie"]["id"]]
