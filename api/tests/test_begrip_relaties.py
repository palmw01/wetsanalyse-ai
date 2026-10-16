"""Begripsrelaties en opvolging (spoor D, fase F2)."""
from __future__ import annotations

from test_begrip_onderhoud import _geaccordeerd, _herbeoordelingen
from test_begrippen import DEFINITIE, _annoteer, _begrip, _beslis, _url, _werkgebied
from test_begrippen_runs import _start, _uitkomst
from test_annotatie_v2 import snapshot
from test_werkgebieden import client, database, graaf, snapshot2  # noqa: F401


def _rel(wg, *rest) -> str:
    return "/".join([f"/v1/werkgebieden/{wg['id']}/relaties", *rest])


async def _twee(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    a = await _begrip(client, wg, [ids["lid1"]], naam="belastingaanslag")
    b = await _begrip(client, wg, [ids["awr"]], naam="navorderingsaanslag")
    return ids, wg, a, b


# --- voorstellen uit de keten ---------------------------------------------------------------------

async def test_een_relatie_tussen_passages_wordt_een_voorstel_tussen_begrippen(client):
    ids, wg, a, b = await _twee(client)
    run = await _start(client, wg, 201)
    r = await _uitkomst(client, wg, run, [], relaties=[
        {"kandidaat_id": "P1", "hypothese": "inclusie", "van": ids["lid1"], "naar": ids["awr"], "aandacht": "geel",
         "uitleg": ["onder X wordt mede verstaan Y"]},
        # Binnen één begrip is het geen begripsrelatie.
        {"kandidaat_id": "P2", "hypothese": "kwalificatie", "van": ids["lid1"], "naar": ids["lid1"], "aandacht": "geel"},
    ])
    assert r.status_code == 200, r.text
    d = (await client.get(_rel(wg))).json()
    [v] = d["voorstellen"]
    assert (v["van_naam"], v["type"], v["naar_naam"], v["beoordeling"]) == (
        "belastingaanslag", "inclusie", "navorderingsaanslag", "voorgesteld")
    assert v["bewijs"]["van"]["tekst"] == "Alfa" and v["bewijs"]["uitleg"] == ["onder X wordt mede verstaan Y"]
    assert d["relaties"] == []

    # Akkoord: een rij met herkomst Lex; het voorstel is weg.
    r = await client.post(_rel(wg), json={"voorstel_id": v["id"]})
    assert r.status_code == 201, r.text
    [x] = r.json()["relaties"]
    assert (x["herkomst"], x["beoordeling"], x["type"]) == ("lex", "akkoord", "inclusie")
    assert r.json()["voorstellen"] == []
    # Per begrip te filteren.
    assert len((await client.get(_rel(wg), params={"begrip_id": b["id"]})).json()["relaties"]) == 1
    # Twee keer: 409.
    r = await client.post(_rel(wg), json={"van_begrip": a["id"], "naar_begrip": b["id"], "type": "inclusie"})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "al_vastgelegd"


async def test_een_afgewezen_voorstel_komt_niet_terug(client):
    ids, wg, a, b = await _twee(client)
    run = await _start(client, wg, 201)
    await _uitkomst(client, wg, run, [], relaties=[
        {"kandidaat_id": "P1", "hypothese": "kwalificatie", "van": ids["lid1"], "naar": ids["awr"], "aandacht": "geel"}])
    [v] = (await client.get(_rel(wg))).json()["voorstellen"]
    assert (await client.post(_rel(wg, "voorstellen", v["id"], "afwijzen"), json={"reden": " "})).status_code == 422
    r = await client.post(_rel(wg, "voorstellen", v["id"], "afwijzen"), json={"reden": "Geen fictie."})
    assert r.status_code == 200 and r.json()["voorstellen"] == []
    [x] = r.json()["relaties"]
    assert (x["beoordeling"], x["toelichting"]) == ("afgewezen", "Geen fictie.")
    assert (await client.post(_rel(wg), json={"voorstel_id": v["id"]})).status_code == 409


# --- zelf vastleggen ------------------------------------------------------------------------------

async def test_zelf_vastleggen_met_regels(client):
    ids, wg, a, b = await _twee(client)
    r = await client.post(_rel(wg), json={"van_begrip": a["id"], "naar_begrip": b["id"], "type": "verwant"})
    assert r.status_code == 422                                     # verwant vraagt een toelichting
    r = await client.post(_rel(wg), json={"van_begrip": a["id"], "naar_begrip": a["id"], "type": "hierarchie"})
    assert r.status_code == 422 and r.json()["detail"]["fout"] == "zelfde_begrip"
    r = await client.post(_rel(wg), json={"van_begrip": a["id"], "naar_begrip": b["id"], "type": "opvolging"})
    assert r.status_code == 422                                     # opvolging maakt alleen de api
    r = await client.post(_rel(wg), json={"van_begrip": b["id"], "naar_begrip": a["id"], "type": "hierarchie",
                                          "toelichting": "Een navorderingsaanslag is een soort aanslag."})
    assert r.status_code == 201
    [x] = r.json()["relaties"]
    assert x["herkomst"] == "analist"
    assert (await client.delete(_rel(wg, x["id"]))).json()["relaties"] == []
    acties = [a_["actie"] for a_ in (await client.get(f"/v1/werkgebieden/{wg['id']}/audit")).json()["audit"]]
    assert "relatie-vastgelegd" in acties and "relatie-verwijderd" in acties


async def test_een_veranderde_kant_staat_bij_het_andere_begrip_in_de_herbeoordeling(client):
    ids, wg, a, b = await _twee(client)
    await client.post(_rel(wg), json={"van_begrip": a["id"], "naar_begrip": b["id"], "type": "inclusie"})
    assert (await _herbeoordelingen(client, wg))["begrippen"] == []
    a = (await client.patch(_url(wg, a), json={"verwachte_revisie": a["revisie"],
                                               "inhoud": {"naam": "belastingaanslag", **DEFINITIE}})).json()
    [h] = (await _herbeoordelingen(client, wg))["begrippen"]
    assert h["begrip_id"] == b["id"] and h["koppelingen"] == []
    [d] = h["relaties"]
    assert d["ander"]["naam"] == "belastingaanslag" and "veranderde" in d["reden"]
    [x] = (await client.get(_rel(wg))).json()["relaties"]
    assert x["veranderd"] is True
    await client.post(_rel(wg, x["id"], "bevestigen"))
    assert (await _herbeoordelingen(client, wg))["begrippen"] == []


# --- opvolging ------------------------------------------------------------------------------------

async def test_nieuwe_betekenis_vervangt_en_geeft_de_duiding_vrij(client):
    ids = await _annoteer()
    await _beslis(ids["lid1"], "approve", snapshot())
    wg = await _werkgebied(client)
    oud = await _geaccordeerd(client, wg, [ids["lid1"]])
    r = await client.post(_url(wg, oud, "nieuwe-betekenis"), json={"verwachte_revisie": oud["revisie"],
                                                                   "reden": "Na de wetswijziging ruimer."})
    assert r.status_code == 201, r.text
    nieuw = r.json()
    assert nieuw["id"] != oud["id"] and nieuw["status"] == "concept"
    assert nieuw["inhoud"]["definitie"] == DEFINITIE["definitie"]
    [k] = nieuw["koppelingen"]
    assert (k["element_id"], k["rol"], k["beoordeling"]) == (ids["lid1"], "duiding", "open")
    assert nieuw["vervangt"] == [{"begrip_id": oud["id"], "naam": "Belastingschuldige", "reden": "Na de wetswijziging ruimer."}]
    o = (await client.get(_url(wg, oud))).json()
    assert o["status"] == "vervangen" and o["vervangen_door"]["begrip_id"] == nieuw["id"]
    # De primaire duiding is bij de opvolger; het oude begrip is alleen-lezen.
    lijst = (await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen")).json()
    assert lijst["primair"][ids["lid1"]]["begrip_id"] == nieuw["id"]
    r = await client.patch(_url(wg, oud), json={"verwachte_revisie": o["revisie"], "inhoud": {"naam": "x"}})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "vervangen"
    # Opvolging weghalen gaat niet los, wel via de opvolger: dan komt het oude terug.
    [rel] = (await client.get(_rel(wg))).json()["relaties"]
    assert rel["type"] == "opvolging" and (await client.delete(_rel(wg, rel["id"]))).status_code == 409
    r = await client.delete(_url(wg, nieuw), params={"verwachte_revisie": nieuw["revisie"]})
    assert r.json()["hersteld"] == [oud["id"]]
    o = (await client.get(_url(wg, oud))).json()
    assert (o["status"], o["vervangen_door"]) == ("geaccordeerd", None)
    assert (await client.get(_url(wg, oud, "revisies"))).json()["revisies"][0]["actie"] == "begrip-hersteld"


async def test_combineren_houdt_een_identiteit(client):
    ids, wg, a, b = await _twee(client)
    r = await client.post(_url(wg, a, "combineren"), json={
        "verwachte_revisie": a["revisie"], "ander_begrip_id": b["id"], "ander_revisie": b["revisie"],
        "reden": "Zelfde begrip."})
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["id"] == a["id"] and "navorderingsaanslag" in c["inhoud"]["alternatieve_termen"]
    assert {k["element_id"] for k in c["koppelingen"]} == {ids["lid1"], ids["awr"]}
    assert c["vervangt"][0]["begrip_id"] == b["id"]
    assert (await client.get(_url(wg, b))).json()["status"] == "vervangen"
    # Met een verouderde revisie van de ander: 412 en niets veranderd.
    _, wg2, a2, b2 = await _twee(client)
    r = await client.post(_url(wg2, a2, "combineren"), json={
        "verwachte_revisie": a2["revisie"], "ander_begrip_id": b2["id"], "ander_revisie": b2["revisie"] + 3,
        "reden": "x"})
    assert r.status_code == 412
    assert (await client.get(_url(wg2, b2))).json()["status"] == "concept"
    r = await client.post(_url(wg2, a2, "combineren"), json={
        "verwachte_revisie": a2["revisie"], "ander_begrip_id": a2["id"], "ander_revisie": a2["revisie"], "reden": "x"})
    assert r.status_code == 422
