"""Begrippen over werkgebieden heen (fase F4): het overzicht, de verificatie voor Lex en één begrip."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.begrippen_overzicht import normaal, treffer
from app.gesprek_contracts import Artefact
from test_annotatie_v2 import snapshot
from test_begrip_onderhoud import _geaccordeerd
from test_begrippen import _annoteer, _begrip, _beslis, _url, _werkgebied
from test_werkgebieden import _nieuw, client, database, graaf, snapshot2  # noqa: F401


async def _wijzig(client, wg, b, **inhoud) -> dict:
    r = await client.patch(_url(wg, b), json={"verwachte_revisie": b["revisie"], "inhoud": {**b["inhoud"], **inhoud}})
    assert r.status_code == 200, r.text
    return r.json()


async def _zoek(client, **params) -> dict:
    r = await client.get("/v1/begrippen", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_treffer_ordent_naam_term_definitie():
    assert treffer("termijn", "Termijn", [], "") == 0
    assert treffer("TERMIJN", "Betalingstermijn", ["termijn"], "") == 1
    assert treffer("termijn", "Betalingstermijn", [], "") == 2
    assert treffer("termijn", "Uitstel", ["betalingstermijn"], "") == 3
    assert treffer("termijn", "Uitstel", [], "Een langere termijn.") == 4
    assert treffer("betaling uitstel", "Uitstel", [], "Later betaling.") == 5
    assert treffer("aanslag", "Uitstel", [], "") is None
    assert normaal("  Belastingschuldigé ") == "belastingschuldige"


async def test_zoeken_over_werkgebieden_met_eigen_werkgebied_eerst(client):
    a = await _nieuw(client, "Termijnen")
    b = await _nieuw(client, "Invordering")
    await _begrip(client, a, naam="Termijn")
    await _begrip(client, b, naam="Termijn")
    await _begrip(client, b, naam="Uitstel van betaling")

    alles = await _zoek(client)
    assert alles["totaal"] == 3 and alles["volgende_offset"] is None
    r = await _zoek(client, q="termijn", eerst=b["id"])
    assert [(x["naam"], x["werkgebied_naam"]) for x in r["resultaten"]] == [("Termijn", "Invordering"),
                                                                            ("Termijn", "Termijnen")]
    r = await _zoek(client, q="termijn", eerst=a["id"])
    assert r["resultaten"][0]["werkgebied_id"] == a["id"]
    r = await _zoek(client, werkgebied_id=b["id"])
    assert {x["naam"] for x in r["resultaten"]} == {"Termijn", "Uitstel van betaling"}
    r = await _zoek(client, limit=2)
    assert len(r["resultaten"]) == 2 and r["volgende_offset"] == 2


async def test_alternatieve_term_en_definitie_vinden_het_begrip(client):
    wg = await _nieuw(client)
    b = await _begrip(client, wg, naam="Uitstel van betaling")
    await _wijzig(client, wg, b, alternatieve_termen=["betalingsuitstel"], definitie="Later betalen dan de termijn.")
    assert [x["naam"] for x in (await _zoek(client, q="Betalingsuitstel"))["resultaten"]] == ["Uitstel van betaling"]
    assert [x["naam"] for x in (await _zoek(client, q="termijn"))["resultaten"]] == ["Uitstel van betaling"]
    assert (await _zoek(client, q="aanslag"))["resultaten"] == []


async def test_gearchiveerd_en_verwijderd_bestaan_hier_niet(client):
    wg = await _nieuw(client, "Weg")
    b = await _begrip(client, wg, naam="Termijn")
    andere = await _nieuw(client, "Blijft")
    weg = await _begrip(client, andere, naam="Termijn")
    r = await client.delete(_url(andere, weg), params={"verwachte_revisie": weg["revisie"]})
    assert r.status_code == 200, r.text
    r = await client.delete(f"/v1/werkgebieden/{wg['id']}", params={"verwachte_revisie": wg["revisie"]})
    assert r.status_code == 200, r.text
    assert (await _zoek(client))["resultaten"] == []
    assert (await client.get(f"/v1/begrippen/{b['id']}")).status_code == 404
    v = (await client.post("/v1/begrippen/verifieer", json={"ids": [b["id"], weg["id"]]})).json()
    assert v["begrippen"] == {b["id"]: None, weg["id"]: None}


async def test_status_vervangen_noemt_de_opvolger_en_geaccordeerd_gaat_voor(client):
    ids = await _annoteer()
    await _beslis(ids["lid1"], "approve", snapshot())
    await _beslis(ids["awr"], "approve", snapshot2())
    wg = await _werkgebied(client)
    oud = await _geaccordeerd(client, wg, [ids["lid1"]])
    nieuw = (await client.post(_url(wg, oud, "nieuwe-betekenis"),
                               json={"verwachte_revisie": oud["revisie"], "reden": "Ruimer."})).json()
    akkoord = await _geaccordeerd(client, wg, [ids["awr"]], naam="Belastingschuldige")

    r = await _zoek(client, q="belastingschuldige")
    assert [(x["id"], x["status"]) for x in r["resultaten"]] == [
        (akkoord["id"], "geaccordeerd"), (nieuw["id"], "concept"), (oud["id"], "vervangen")]
    vervangen = r["resultaten"][2]
    assert vervangen["vervangen_door"] == {"begrip_id": nieuw["id"], "naam": "Belastingschuldige"}
    assert r["resultaten"][0]["aantal_dragend"] == 1
    assert [x["id"] for x in (await _zoek(client, status=["concept", "vervangen"]))["resultaten"]] == [
        nieuw["id"], oud["id"]]
    assert (await client.get("/v1/begrippen", params={"status": "onbekend"})).status_code == 422


async def test_verifieer_geeft_de_stand_van_nu_en_de_projectiehash(client):
    wg = await _nieuw(client)
    leeg = await _nieuw(client, "Zonder begrippen")
    b = await _begrip(client, wg, naam="Termijn")
    v = (await client.post("/v1/begrippen/verifieer",
                           json={"ids": [b["id"], "bestaat-niet"], "werkgebieden": [leeg["id"]]})).json()
    assert v["begrippen"]["bestaat-niet"] is None
    assert v["begrippen"][b["id"]]["status"] == "concept"
    hash_voor = v["werkgebieden"][wg["id"]]["projectie_hash"]
    assert hash_voor and v["werkgebieden"][leeg["id"]] == {"projectie_hash": None}
    await _wijzig(client, wg, b, definitie="Een tijdvak.")
    v = (await client.post("/v1/begrippen/verifieer", json={"ids": [b["id"]]})).json()
    assert v["werkgebieden"][wg["id"]]["projectie_hash"] != hash_voor
    assert (await client.post("/v1/begrippen/verifieer", json={"ids": ["x"] * 51})).status_code == 422


async def test_een_begrip_met_werkgebied_en_relaties(client):
    wg = await _nieuw(client, "Termijnen")
    b = await _begrip(client, wg, naam="Termijn")
    ander = await _begrip(client, wg, naam="Betalingstermijn")
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/relaties",
                          json={"van_begrip": b["id"], "naar_begrip": ander["id"], "type": "hierarchie"})
    assert r.status_code == 201, r.text
    r = await client.get(f"/v1/begrippen/{b['id']}")
    assert r.status_code == 200, r.text
    x = r.json()
    assert x["werkgebied"] == {"id": wg["id"], "naam": "Termijnen"}
    assert x["begrip"]["inhoud"]["naam"] == "Termijn" and "koppelingen" in x["begrip"]
    assert [(y["type"], y["naar_naam"]) for y in x["relaties"]] == [("hierarchie", "Betalingstermijn")]
    assert (await client.get("/v1/begrippen/bestaat-niet")).status_code == 404


def test_artefact_met_een_begrip():
    a = Artefact(soort="begrippen", titel="Termijn",
                 ref={"werkgebied_id": "w", "begrip_id": "b", "kaart_run_id": "k", "actie": "voorbeelden"})
    assert a.ref["begrip_id"] == "b"
    Artefact(soort="begrippen", ref={"werkgebied_id": "w", "run_id": "r"})
    with pytest.raises(ValidationError):
        Artefact(soort="begrippen", ref={"werkgebied_id": "w"})
    with pytest.raises(ValidationError):
        Artefact(soort="begrippen", ref={"begrip_id": "b"})


async def test_een_geaccordeerd_begrip_met_een_veranderde_passage_vraagt_herbeoordeling(client):
    ids = await _annoteer()
    await _beslis(ids["lid1"], "approve", snapshot())
    wg = await _werkgebied(client)
    b = await _geaccordeerd(client, wg, [ids["lid1"]])
    concept = await _begrip(client, wg, [ids["lid2"]], naam="Ander")
    assert {x["id"]: x["herbeoordelen"] for x in (await _zoek(client))["resultaten"]} == {b["id"]: 0, concept["id"]: 0}
    # De jurist past de annotatie aan: de dragende passage is niet meer wat er geaccordeerd werd.
    await _beslis(ids["lid1"], "heropen", snapshot())
    await _beslis(ids["lid1"], "edit", snapshot(), wijziging={"klasse": "Rechtsobject"})
    rijen = {x["id"]: x for x in (await _zoek(client))["resultaten"]}
    assert rijen[b["id"]]["herbeoordelen"] == 1
    assert rijen[concept["id"]]["herbeoordelen"] == 0, "alleen een geaccordeerd begrip vraagt herbeoordeling"
    v = (await client.post("/v1/begrippen/verifieer", json={"ids": [b["id"]]})).json()
    assert v["begrippen"][b["id"]]["herbeoordelen"] == 1


async def test_door_mij_bewerkt_en_de_tellers_per_status(client):
    """`mijn` volgt de revisies; `per_status` telt met dezelfde filters, zonder het statusfilter."""
    a = await _nieuw(client, "Termijnen")
    t = await _begrip(client, a, naam="Termijn")
    await _begrip(client, a, naam="Uitstel van betaling")
    b = {"X-User-Id": "jurist-b"}
    r = await client.get("/v1/begrippen", params={"mijn": "true"}, headers=b)
    assert r.json()["resultaten"] == [] and r.json()["per_status"] == {}
    await client.patch(_url(a, t), json={"verwachte_revisie": t["revisie"], "inhoud": {**t["inhoud"], "uitleg": "x"}},
                       headers=b)
    r = await client.get("/v1/begrippen", params={"mijn": "true"}, headers=b)
    assert [x["naam"] for x in r.json()["resultaten"]] == ["Termijn"]
    alles = await _zoek(client, status="geaccordeerd")
    assert alles["totaal"] == 0 and alles["per_status"] == {"concept": 2}
    assert (await _zoek(client, q="termijn"))["per_status"] == {"concept": 1}
