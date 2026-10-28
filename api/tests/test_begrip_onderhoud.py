"""Onderhoud van begrippen (spoor D, fase F1): herbeoordeling, herkoppeling, bevestigen en dekking.

Acceptatie: een gewijzigde dragende passage verschijnt bij de geraakte begrippen; de oude bewijsstand
blijft."""
from __future__ import annotations

from sqlalchemy import delete

from app import annotatie_v2_store as store, db
from app.begrip_onderhoud_store import opvolgers
from test_annotatie_v2 import ONE, TWO, element, request, snapshot
from test_begrippen import DEFINITIE, _annoteer, _begrip, _beslis, _url, _werkgebied
from test_begrippen_runs import _groep, _start, _uitkomst
from test_werkgebieden import client, database, graaf, snapshot2  # noqa: F401


async def _geaccordeerd(client, wg, element_ids, naam="Belastingschuldige") -> dict:
    b = await _begrip(client, wg, element_ids, naam=naam)
    b = (await client.patch(_url(wg, b), json={"verwachte_revisie": b["revisie"],
                                               "inhoud": {"naam": naam, **DEFINITIE}})).json()
    for k in b["koppelingen"]:
        b = (await client.patch(_url(wg, b, "koppelingen", k["id"]),
                                json={"verwachte_revisie": b["revisie"], "beoordeling": "akkoord"})).json()
    r = await client.post(_url(wg, b, "accorderen"), json={"verwachte_revisie": b["revisie"]})
    assert r.status_code == 200, r.text
    return r.json()


async def _herbeoordelingen(client, wg, **params) -> dict:
    r = await client.get(f"/v1/werkgebieden/{wg['id']}/herbeoordelingen", params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def _herannoteer(tekst: str) -> str:
    """Lid 2 opnieuw annoteren op een nieuwe wettekst; geeft het id van het nieuwe element."""
    changed = snapshot(TWO, second=tekst)
    view = await store.weergave(changed)
    revs = {l["bron_iri"]: l["revisie"] for l in view["lagen"]}
    uit = await store.batch(request(changed, [element(changed, TWO, 0, len(tekst))], batch_id="herannotatie",
                                    revisions=revs), changed, "lex")
    return uit["elementen"][0]["id"]


# --- de acceptatie --------------------------------------------------------------------------------

async def test_een_gewijzigde_dragende_passage_verschijnt_en_de_oude_bewijsstand_blijft(client, graaf):
    ids = await _annoteer()
    await _beslis(ids["lid2"], "approve", snapshot())
    wg = await _werkgebied(client)
    b = await _geaccordeerd(client, wg, [ids["lid2"]])
    assert (await _herbeoordelingen(client, wg))["begrippen"] == []

    # De wet verandert: "Beta" wordt "Other". Nog niet opnieuw geannoteerd.
    graaf.tweede_lid = "Other"
    [h] = (await _herbeoordelingen(client, wg))["begrippen"]
    assert (h["begrip_id"], h["naam"], h["status"]) == (b["id"], "Belastingschuldige", "geaccordeerd")
    [k] = h["koppelingen"]
    assert k["toen"]["tekst"] == "Beta"
    assert [x["stand"] for x in k["bron"]] == ["gewijzigd"] and k["bron"][0]["fragment_gelijk"] is False
    assert any("ook op de gemarkeerde plek" in r for r in k["redenen"]), k["redenen"]
    assert k["opvolgers"] == [] and k["opnieuw_annoteren"] == [TWO]
    assert k["acties"] == ["loskoppelen"]                       # bevestigen kan niet: het fragment is weg
    # De status verandert niet vanzelf.
    assert (await client.get(_url(wg, b))).json()["status"] == "geaccordeerd"

    # Herannotatie: het oude element veroudert, er komt een nieuw element – de opvolger.
    nieuw = await _herannoteer("Other")
    [h] = (await _herbeoordelingen(client, wg))["begrippen"]
    [k] = h["koppelingen"]
    assert k["actualiteit"] == "gewijzigd" and k["nu"]["verouderd"] is True
    [o] = k["opvolgers"]
    assert o["element_id"] == nieuw and o["tekst"] == "Other"
    assert {(s["richting"], s["uitleg"]) for s in o["signalen"]} >= {
        ("steun", "Zelfde JAS-klasse (Rechtssubject)."), ("tegen", "Andere tekst."),
        ("steun", "Op dezelfde plek in de bepaling.")}
    assert k["acties"] == ["herkoppelen", "loskoppelen"]

    r = await client.post(_url(wg, b, "koppelingen", k["koppeling_id"], "herkoppelen"),
                          json={"verwachte_revisie": h["revisie"], "element_id": nieuw})
    assert r.status_code == 200, r.text
    b2 = r.json()
    [kn] = b2["koppelingen"]
    assert (kn["element_id"], kn["beoordeling"], kn["actualiteit"]) == (nieuw, "akkoord", "actueel")
    # De oude bewijsstand blijft, bij de nieuwe koppeling te lezen.
    assert kn["vervangt"]["element_id"] == ids["lid2"] and kn["vervangt"]["bewijs"]["tekst"] == "Beta"
    # Geaccordeerd blijft geaccordeerd; de aandacht zegt wat er nog openstaat.
    assert b2["status"] == "geaccordeerd"
    assert b2["aandachtspunten"] == ["1 dragende annotatie is nog niet door een jurist beoordeeld."]
    assert (await _herbeoordelingen(client, wg))["begrippen"] == []
    acties = [x["actie"] for x in (await client.get(_url(wg, b, "revisies"))).json()["revisies"]]
    assert acties[0] == "koppeling-herkoppeld"


async def test_fragment_nog_letterlijk_dan_bevestigen_met_een_tweede_bewijsstand(client, graaf):
    ids = await _annoteer()
    await _beslis(ids["lid2"], "approve", snapshot())
    wg = await _werkgebied(client)
    b = await _geaccordeerd(client, wg, [ids["lid2"]])

    graaf.tweede_lid = "Beta gamma"                              # "Beta" staat er nog op 0:4
    [h] = (await _herbeoordelingen(client, wg))["begrippen"]
    [k] = h["koppelingen"]
    assert k["bron"][0]["fragment_gelijk"] is True
    assert any("staat er nog letterlijk" in r for r in k["redenen"])
    assert k["acties"] == ["bevestigen", "loskoppelen"]

    r = await client.post(_url(wg, b, "koppelingen", k["koppeling_id"], "bevestigen"),
                          json={"verwachte_revisie": h["revisie"], "motivatie": "Alleen aangevuld."})
    assert r.status_code == 200, r.text
    b2 = r.json()
    [kb] = b2["koppelingen"]
    assert kb["bewijs"] == next(x for x in b["koppelingen"])["bewijs"]      # het bewijs is onveranderd
    [bev] = kb["bevestigingen"]
    assert (bev["door"], bev["motivatie"]) == ("jurist-a", "Alleen aangevuld.")
    assert b2["status"] == "geaccordeerd" and b2["revisie"] == b["revisie"] + 1
    assert (await _herbeoordelingen(client, wg))["begrippen"] == []

    # Nog eens bevestigen verandert niets.
    r = await client.post(_url(wg, b, "koppelingen", k["koppeling_id"], "bevestigen"),
                          json={"verwachte_revisie": b2["revisie"]})
    assert r.status_code == 200 and r.json()["revisie"] == b2["revisie"]


async def test_een_gewijzigde_annotatie_bevestigen_maakt_haar_weer_actueel(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    b = await _begrip(client, wg, [ids["lid1"]])
    await _beslis(ids["lid1"], "edit", snapshot(), wijziging={"klasse": "Rechtsobject"})
    [h] = (await _herbeoordelingen(client, wg, begrip_id=b["id"]))["begrippen"]
    [k] = h["koppelingen"]
    assert k["actualiteit"] == "gewijzigd" and k["toen"]["klasse"] == "Rechtssubject"
    assert k["nu"]["klasse"] == "Rechtsobject"
    assert "De annotatie veranderde (klasse, tekst of anker)." in k["redenen"]
    assert "bevestigen" in k["acties"] and "herkoppelen" not in k["acties"]
    r = await client.post(_url(wg, b, "koppelingen", k["koppeling_id"], "bevestigen"),
                          json={"verwachte_revisie": h["revisie"]})
    [kb] = r.json()["koppelingen"]
    assert kb["actualiteit"] == "actueel" and kb["bewijs"]["klasse"] == "Rechtssubject"
    assert b["status"] == "concept" and r.json()["status"] == "concept"


async def test_een_verdwenen_passage_bevestig_je_niet(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    b = await _begrip(client, wg, [ids["awr"]])
    async with db.get_engine().begin() as conn:
        await conn.execute(delete(db.annotatie_v2_elementen).where(db.annotatie_v2_elementen.c.id == ids["awr"]))
    [h] = (await _herbeoordelingen(client, wg))["begrippen"]
    [k] = h["koppelingen"]
    assert (k["actualiteit"], k["nu"], k["acties"]) == ("verdwenen", None, ["loskoppelen"])
    r = await client.post(_url(wg, b, "koppelingen", k["koppeling_id"], "bevestigen"),
                          json={"verwachte_revisie": h["revisie"]})
    assert r.status_code == 422 and r.json()["detail"]["fout"] == "niet_te_bevestigen"


async def test_herkoppelen_naar_dezelfde_passage_of_buiten_het_werkgebied(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    b = await _begrip(client, wg, [ids["lid1"]])
    k = b["koppelingen"][0]
    r = await client.post(_url(wg, b, "koppelingen", k["id"], "herkoppelen"),
                          json={"verwachte_revisie": b["revisie"], "element_id": ids["lid1"]})
    assert r.status_code == 422 and r.json()["detail"]["fout"] == "zelfde_passage"
    r = await client.post(_url(wg, b, "koppelingen", k["id"], "herkoppelen"),
                          json={"verwachte_revisie": b["revisie"], "element_id": "bestaat-niet"})
    assert r.status_code == 422 and r.json()["detail"]["fout"] == "element_buiten_werkgebied"
    r = await client.post(_url(wg, b, "koppelingen", k["id"], "herkoppelen"),
                          json={"verwachte_revisie": b["revisie"] + 5, "element_id": ids["lid2"]})
    assert r.status_code == 412


# --- dekking --------------------------------------------------------------------------------------

async def test_dekking_telt_elk_element_een_keer(client):
    ids = await _annoteer()
    await _beslis(ids["lid1"], "approve", snapshot())
    wg = await _werkgebied(client)
    await _geaccordeerd(client, wg, [ids["lid1"]])
    await _begrip(client, wg, [ids["awr"]], naam="Wet")
    url = f"/v1/werkgebieden/{wg['id']}/dekking"
    d = (await client.get(url)).json()
    per = {e["element_id"]: e["stand"] for e in d["elementen"]}
    assert per == {ids["lid1"]: "gekoppeld", ids["awr"]: "voorstel", ids["lid2"]: "te_verwerken"}
    assert d["totalen"] == {"te_verwerken": 1, "voorstel": 1, "gekoppeld": 1, "buiten_behandeling": 0}
    assert d["totaal"] == 3 and d["laatste_run"] is None and d["nieuw_sinds_run"] == 0

    assert (await client.post(url + "/buiten-behandeling", json={"element_ids": [ids["lid2"]], "reden": " "})
            ).status_code == 422
    r = await client.post(url + "/buiten-behandeling", json={"element_ids": ["vreemd"], "reden": "x"})
    assert r.status_code == 422 and r.json()["detail"]["element_ids"] == ["vreemd"]
    r = await client.post(url + "/buiten-behandeling",
                          json={"element_ids": [ids["lid2"], ids["lid2"]], "reden": "Alleen een verwijzing."})
    assert r.json() == {"element_ids": [ids["lid2"]]}
    # Twee keer is idempotent.
    assert (await client.post(url + "/buiten-behandeling", json={"element_ids": [ids["lid2"]], "reden": "x"})
            ).json() == {"element_ids": []}
    d = (await client.get(url)).json()
    lid2 = next(e for e in d["elementen"] if e["element_id"] == ids["lid2"])
    assert (lid2["stand"], lid2["buiten_behandeling"]["reden"]) == ("buiten_behandeling", "Alleen een verwijzing.")

    assert (await client.delete(url + f"/buiten-behandeling/{ids['lid2']}")).status_code == 200
    assert (await client.delete(url + f"/buiten-behandeling/{ids['lid2']}")).status_code == 404
    d = (await client.get(url)).json()
    assert next(e for e in d["elementen"] if e["element_id"] == ids["lid2"])["stand"] == "te_verwerken"
    audit = (await client.get(f"/v1/werkgebieden/{wg['id']}/audit")).json()
    acties = [a["actie"] for a in audit["audit"]]
    assert "element-buiten-behandeling" in acties and "element-in-behandeling" in acties


async def test_een_open_groep_is_een_voorstel_en_wat_de_run_niet_zag_is_nieuw(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    run = await _start(client, wg, 201)
    r = await _uitkomst(client, wg, run, [_groep("G0000001", [ids["lid1"], ids["lid2"]])])
    assert r.status_code == 200, r.text
    url = f"/v1/werkgebieden/{wg['id']}/dekking"
    d = (await client.get(url)).json()
    assert {e["element_id"]: e["stand"] for e in d["elementen"]} == {
        ids["lid1"]: "voorstel", ids["lid2"]: "voorstel", ids["awr"]: "te_verwerken"}
    assert (d["laatste_run"], d["nieuw_sinds_run"]) == (run["id"], 0)

    # Een nieuwe annotatie na de run: de keten zag haar nog niet.
    snap = snapshot()
    view = await store.weergave(snap)
    revs = {l["bron_iri"]: l["revisie"] for l in view["lagen"]}
    extra = (await store.batch(request(snap, [element(snap, ONE, 7, 11)], batch_id="extra", revisions=revs),
                               snap, "lex"))["elementen"][0]["id"]
    d = (await client.get(url)).json()
    assert d["nieuw_sinds_run"] == 1
    assert [e["element_id"] for e in d["elementen"] if e["nieuw_sinds_run"]] == [extra]


# --- opvolgers (zuiver) ---------------------------------------------------------------------------

def test_een_opvolger_die_elders_primair_is_krijgt_een_tegensignaal():
    ref = {"tekst": "Alfa", "klasse": "Rechtssubject", "eigenaar_iri": ONE,
           "ankers": [{"bron_iri": ONE, "start": 2, "eind": 6}]}
    kandidaten = [
        {"id": "oud", "tekst": "Alfa", "klasse": "Rechtssubject", "eigenaar_iri": ONE, "ankers": ref["ankers"]},
        {"id": "ver", "tekst": "alfa", "klasse": "Rechtssubject", "eigenaar_iri": ONE,
         "ankers": [{"bron_iri": ONE, "start": 7, "eind": 11}]},
        {"id": "hier", "tekst": "Alfa", "klasse": "Rechtsobject", "eigenaar_iri": ONE,
         "ankers": [{"bron_iri": ONE, "start": 2, "eind": 6}]},
        {"id": "weg", "tekst": "Alfa", "klasse": "Rechtssubject", "eigenaar_iri": ONE, "verouderd": True,
         "ankers": ref["ankers"]},
        {"id": "elders", "tekst": "Alfa", "klasse": "Rechtssubject", "eigenaar_iri": TWO,
         "ankers": [{"bron_iri": TWO, "start": 0, "eind": 4}]},
    ]
    uit = opvolgers(ref, "oud", kandidaten, {"ver": {"begrip_id": "B2", "naam": "Ander"}}, "B1", "duiding")
    assert [o["element_id"] for o in uit] == ["hier", "ver"]       # dezelfde plek eerst
    ver = {s["uitleg"] for s in uit[1]["signalen"]}
    assert "Zelfde tekst, op hoofdletters en spaties na." in ver
    assert 'Duidt al het begrip "Ander" aan; als duiding kan het hier niet.' in ver
    assert "Andere JAS-klasse: Rechtssubject → Rechtsobject." in {s["uitleg"] for s in uit[0]["signalen"]}
