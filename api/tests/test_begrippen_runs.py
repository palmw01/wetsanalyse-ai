"""Voorstellen van Lex (spoor D, levering 3): het manifest, runs, de uitkomst van graph-qa en de
besluiten over betekenisgroepen."""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import update

from app import annotatie_v2_store as store, begrip_manifest, db
from test_annotatie_v2 import ART, LAW, ONE, TWO, element, request, snapshot
from test_werkgebieden import ART2, _bron, _nieuw, client, database, graaf, snapshot2  # noqa: F401

SETS = Path(__file__).resolve().parents[2] / "docs" / "wetsanalyse" / "referentieset-begrippen"
VECTOREN = json.loads((SETS / "manifest-id.vectoren.json").read_text())


# --- het manifest -------------------------------------------------------------------------------

@pytest.mark.parametrize("vector", VECTOREN["vectoren"], ids=lambda v: v["set"])
def test_het_manifest_id_rekent_zoals_de_keten(vector):
    d = SETS / vector["set"]
    bronnen = json.loads((d / "bronnen.json").read_text())["bronnen"]
    formuleringen = json.loads((d / "cases.json").read_text())["formuleringen"]
    assert begrip_manifest.manifest_id(bronnen, formuleringen) == vector["manifest_id"]


async def _annoteer() -> dict[str, str]:
    """Twee keer "Alfa" in lid 1, "Beta" in lid 2, "Deze" in de AWR, en één element over twee leden."""
    snap = snapshot()
    a1, a2, b = element(snap, ONE, 2, 6), element(snap, ONE, 7, 11), element(snap, TWO, 0, 4)
    multi = dict(klasse="Voorwaarde", tekst=a1["tekst"] + " " + b["tekst"], ankers=[*a1["ankers"], *b["ankers"]])
    uit = await store.batch(request(snap, [a1, a2, b, multi]), snap, "lex")
    snap2 = snapshot2()
    uit2 = await store.batch(request(snap2, [element(snap2, ART2, 0, 4)], batch_id="awr"), snap2, "lex")
    ids: dict[str, str] = {}
    for e in uit["elementen"] + uit2["elementen"]:
        sleutel = "multi" if len(e["ankers"]) > 1 else {(ONE, 2): "alfa1", (ONE, 7): "alfa2", (TWO, 0): "beta",
                                                         (ART2, 0): "awr"}[(e["ankers"][0]["bron_iri"], e["ankers"][0]["start"])]
        ids[sleutel] = e["id"]
    return ids


async def _werkgebied(client) -> dict:
    wg = await _nieuw(client)
    wg = (await _bron(client, wg, bron_iri=ART))["werkgebied"]
    return (await _bron(client, wg, bron_iri=ART2, rol="context"))["werkgebied"]


async def _start(client, wg, status=None) -> dict:
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/begrippen-runs")
    if status:
        assert r.status_code == status, r.text
    return r.json()


def _groep(gid: str, leden: list[str], naam="alfa", **extra) -> dict:
    return {"id": gid, "leden": leden, "aandacht": "groen", "uitleg": ["Zelfde term"], "conflicten": [],
            "voorstel": {"naam": naam, **extra}}


async def _uitkomst(client, wg, run, groepen, **extra):
    return await client.put(f"/v1/werkgebieden/{wg['id']}/begrippen-runs/{run['id']}/uitkomst",
                            json={"manifest_id": run["manifest_id"], "groepen": groepen, **extra})


async def test_het_manifest_draagt_wat_de_keten_nodig_heeft(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    run = await _start(client, wg, 201)
    run = (await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen-runs/{run['id']}", params={"manifest": True})).json()
    m = run["manifest"]
    assert {f["element_id"] for f in m["formuleringen"]} == {ids["alfa1"], ids["alfa2"], ids["beta"], ids["awr"]}
    # Het element over twee leden past niet in een Formulering: overgeslagen, met reden.
    assert [x["element_id"] for x in run["overgeslagen"]] == [ids["multi"]]
    assert all(sorted(f) == VECTOREN["velden"]["formulering"] for f in m["formuleringen"])
    assert all(sorted(b) == VECTOREN["velden"]["bron"] for b in m["bronnen"])
    per_bron = {b["bron_iri"]: b for b in m["bronnen"]}
    assert per_bron[ONE]["regeling"] == "BWBR0004770" and per_bron[ART2]["regeling"] == "BWBR0002320"
    assert per_bron[ONE]["label"] == "Artikel 9 · Lid 1 – Wet"
    for f in m["formuleringen"]:                                    # letterlijk op het anker
        assert per_bron[f["bron_iri"]]["tekst"][f["start"]:f["eind"]] == f["tekst"]
    assert run["manifest_id"] == begrip_manifest.manifest_id(m["bronnen"], m["formuleringen"])


async def test_een_tweede_start_op_hetzelfde_manifest_rekent_niet_opnieuw(client):
    await _annoteer()
    wg = await _werkgebied(client)
    a = await _start(client, wg, 201)
    b = await _start(client, wg, 200)
    assert (a["id"], b["nieuw"]) == (b["id"], False)
    # Een vastgelopen run mag opnieuw.
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.begrippen_runs).values(gewijzigd=db.utcnow() - timedelta(minutes=10)))
    c = await _start(client, wg, 201)
    assert c["id"] != a["id"]


async def test_te_weinig_passages_is_geen_run(client):
    wg = await _werkgebied(client)
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/begrippen-runs")
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "te_weinig_passages"


# --- de uitkomst ----------------------------------------------------------------------------------

async def test_de_uitkomst_wordt_getoetst_en_is_idempotent(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    run = await _start(client, wg)
    goed = [_groep("Gabc123", [ids["alfa1"], ids["alfa2"]])]
    r = await _uitkomst(client, wg, run, [_groep("Gabc123", [ids["alfa1"], "verzonnen"])])
    assert r.status_code == 422 and r.json()["detail"]["element_ids"] == ["verzonnen"]
    r = await client.put(f"/v1/werkgebieden/{wg['id']}/begrippen-runs/{run['id']}/uitkomst",
                         json={"manifest_id": "Manders", "groepen": goed})
    assert r.status_code == 422
    assert (await _uitkomst(client, wg, run, goed)).json()["status"] == "klaar"
    assert (await _uitkomst(client, wg, run, goed)).status_code == 200          # nog eens: hetzelfde
    assert (await _uitkomst(client, wg, run, [_groep("Gdef456", [ids["alfa1"], ids["beta"]])])).status_code == 409

    g = (await client.get(f"/v1/werkgebieden/{wg['id']}/groepen")).json()
    [groep] = g["groepen"]
    assert groep["besluit"] == "open"
    assert [(x["tekst"], x["vindplaats"]) for x in groep["leden"]] == [("Alfa", "Artikel 9 · Lid 1 – Wet")] * 2


async def test_mislukt_en_loopt(client):
    await _annoteer()
    wg = await _werkgebied(client)
    run = await _start(client, wg)
    base = f"/v1/werkgebieden/{wg['id']}/begrippen-runs/{run['id']}"
    assert (await client.post(f"{base}/loopt")).json()["status"] == "loopt"
    r = await client.post(f"{base}/mislukt", json={"reden": "spaCy ontbreekt"})
    assert (r.json()["status"], r.json()["reden"]) == ("mislukt", "spaCy ontbreekt")
    # Na een mislukte run mag een nieuwe start.
    assert (await _start(client, wg, 201))["id"] != run["id"]


# --- besluiten over groepen --------------------------------------------------------------------------

async def test_overnemen_maakt_een_begrip_met_de_letterlijke_definitie(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    run = await _start(client, wg)
    await _uitkomst(client, wg, run, [_groep("Gabc123", [ids["alfa1"], ids["alfa2"]], definitie="de eerste letter",
                                              definitie_vindplaats="Artikel 9 · Lid 1 – Wet")])
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/groepen/overnemen",
                          json={"groep_ids": ["Gabc123"], "naam": "Alfa"})
    assert r.status_code == 201, r.text
    b = r.json()
    assert (b["status"], b["inhoud"]["definitie"], b["inhoud"]["definitie_herkomst"]) == ("concept", "de eerste letter", "letterlijk")
    assert {(k["element_id"], k["rol"]) for k in b["koppelingen"]} == {(ids["alfa1"], "duiding"), (ids["alfa2"], "duiding")}
    groep = (await client.get(f"/v1/werkgebieden/{wg['id']}/groepen")).json()["groepen"][0]
    assert (groep["besluit"], groep["begrip_id"]) == ("overgenomen", b["id"])
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/groepen/overnemen", json={"groep_ids": ["Gabc123"], "naam": "Alfa"})
    assert r.status_code == 409


async def test_combineren_en_splitsen(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    run = await _start(client, wg)
    await _uitkomst(client, wg, run, [_groep("Gaaa111", [ids["alfa1"], ids["alfa2"]]),
                                      _groep("Gbbb222", [ids["beta"], ids["awr"]], naam="beta")])
    base = f"/v1/werkgebieden/{wg['id']}/groepen"
    # Splitsen: alleen een deel van de leden; een lid van buiten de groepen mag niet.
    r = await client.post(f"{base}/overnemen", json={"groep_ids": ["Gbbb222"], "naam": "Beta", "element_ids": [ids["alfa1"]]})
    assert r.status_code == 422
    r = await client.post(f"{base}/overnemen", json={"groep_ids": ["Gbbb222"], "naam": "Beta", "element_ids": [ids["beta"]]})
    assert [k["element_id"] for k in r.json()["koppelingen"]] == [ids["beta"]]
    # Splitsen laat de rest staan (fase D): Gbbb222 blijft open met alleen de AWR-passage.
    g = {x["id"]: x for x in (await client.get(base)).json()["groepen"]}
    assert (g["Gbbb222"]["besluit"], [x["element_id"] for x in g["Gbbb222"]["leden"]]) == ("open", [ids["awr"]])
    assert g["Gbbb222"]["afgehandeld"] == 1
    # Een passage die al een begrip werd, kan dat niet nog eens.
    r = await client.post(f"{base}/overnemen", json={"groep_ids": ["Gbbb222"], "naam": "Beta", "element_ids": [ids["beta"]]})
    assert r.status_code == 409 and r.json()["detail"]["element_ids"] == [ids["beta"]]
    # Combineren neemt de rest: daarna zijn beide groepen overgenomen.
    r = await client.post(f"{base}/overnemen", json={"groep_ids": ["Gaaa111", "Gbbb222"], "naam": "Samen"})
    assert r.status_code == 201
    assert {k["element_id"] for k in r.json()["koppelingen"]} == {ids["alfa1"], ids["alfa2"], ids["awr"]}
    assert {x["besluit"] for x in (await client.get(base)).json()["groepen"]} == {"overgenomen"}


async def test_combineren_van_twee_open_groepen(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    run = await _start(client, wg)
    await _uitkomst(client, wg, run, [_groep("Gaaa111", [ids["alfa1"], ids["alfa2"]]),
                                      _groep("Gbbb222", [ids["beta"], ids["awr"]], naam="beta")])
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/groepen/overnemen",
                          json={"groep_ids": ["Gaaa111", "Gbbb222"], "naam": "Samen"})
    assert r.status_code == 201
    assert len(r.json()["koppelingen"]) == 4
    assert {g["besluit"] for g in (await client.get(f"/v1/werkgebieden/{wg['id']}/groepen")).json()["groepen"]} == {"overgenomen"}


async def test_koppelen_aan_een_bestaand_begrip_dat_erop_lijkt(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    bestaand = (await client.post(f"/v1/werkgebieden/{wg['id']}/begrippen", json={"inhoud": {"naam": "De Alfa"}})).json()
    run = await _start(client, wg)
    await _uitkomst(client, wg, run, [_groep("Gaaa111", [ids["alfa1"], ids["alfa2"]])])
    groep = (await client.get(f"/v1/werkgebieden/{wg['id']}/groepen")).json()["groepen"][0]
    assert [x["begrip_id"] for x in groep["lijkt_op"]] == [bestaand["id"]]      # naam = term, zonder lidwoord
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/groepen/Gaaa111/koppelen", json={"begrip_id": bestaand["id"]})
    assert r.status_code == 200 and len(r.json()["koppelingen"]) == 2


async def test_een_afwijzing_blijft_staan_als_de_groep_terugkomt(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    run = await _start(client, wg)
    await _uitkomst(client, wg, run, [_groep("Gaaa111", [ids["alfa1"], ids["alfa2"]])])
    await client.post(f"/v1/werkgebieden/{wg['id']}/groepen/Gaaa111/afwijzen", json={"reden": "Verschillende betekenis"})
    # Een nieuwe annotatie: ander manifest, dus de laatste run is verouderd en er komt een nieuwe.
    snap2 = snapshot2()
    await store.batch(request(snap2, [element(snap2, ART2, 5, 8)], batch_id="awr2", revisions={ART2: 1}), snap2, "lex")
    assert (await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen-runs/laatste")).json()["run"]["verouderd"] is True
    run2 = await _start(client, wg, 201)
    await _uitkomst(client, wg, run2, [_groep("Gaaa111", [ids["alfa1"], ids["alfa2"]])])
    groep = (await client.get(f"/v1/werkgebieden/{wg['id']}/groepen")).json()["groepen"][0]
    assert (groep["besluit"], groep["reden"]) == ("afgewezen", "Verschillende betekenis")
    # En heropenen draait het terug.
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/groepen/Gaaa111/heropenen")
    assert r.json()["groepen"][0]["besluit"] == "open"


async def test_een_twijfelvraag_beantwoorden(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    run = await _start(client, wg)
    await _uitkomst(client, wg, run, [], vragen=[{"kandidaat_id": "P1", "van": ids["alfa1"], "naar": ids["beta"]}])
    base = f"/v1/werkgebieden/{wg['id']}/begrippen-runs/{run['id']}/vragen"
    assert (await client.post(f"{base}/P9", json={"antwoord": "samen"})).status_code == 404
    r = await client.post(f"{base}/P1", json={"antwoord": "apart"})
    assert r.json()["vragen_besluiten"]["P1"]["antwoord"] == "apart"
    # De werkplek toont de vraag letterlijk: ook passages buiten een groep komen mee.
    g = (await client.get(f"/v1/werkgebieden/{wg['id']}/groepen")).json()
    assert set(g["passages"]) == {ids["alfa1"], ids["beta"]}
    assert (g["passages"][ids["beta"]]["tekst"], g["passages"][ids["beta"]]["vindplaats"]) == ("Beta", "Artikel 9 · Lid 2 – Wet")


async def test_samen_bij_een_twijfelvraag_maakt_een_begrip_ook_met_een_losse_passage(client):
    """Een twijfelvraag gaat meestal over passages die de keten níét groepeerde. "Samen" moet dan
    toch een begrip kunnen worden: de groep van de ene passage plus de andere, losse passage."""
    ids = await _annoteer()
    wg = await _werkgebied(client)
    run = await _start(client, wg)
    await _uitkomst(client, wg, run, [_groep("Gaaa111", [ids["alfa1"], ids["alfa2"]])],
                    vragen=[{"kandidaat_id": "P1", "van": ids["alfa1"], "naar": ids["beta"]}])
    base = f"/v1/werkgebieden/{wg['id']}/groepen/overnemen"
    r = await client.post(base, json={"groep_ids": ["Gaaa111"], "naam": "Alfa",
                                      "element_ids": [ids["alfa1"], ids["alfa2"], ids["beta"]]})
    assert r.status_code == 201, r.text
    assert {k["element_id"] for k in r.json()["koppelingen"]} == {ids["alfa1"], ids["alfa2"], ids["beta"]}
    assert (await client.get(f"/v1/werkgebieden/{wg['id']}/groepen")).json()["groepen"][0]["besluit"] == "overgenomen"
    # Zonder groep: twee losse passages uit de voorstellen.
    r = await client.post(base, json={"groep_ids": [], "naam": "Deze", "element_ids": [ids["awr"]]})
    assert r.status_code == 201, r.text
    # Een passage buiten het manifest van de voorstellen, of helemaal niets: geweigerd.
    assert (await client.post(base, json={"groep_ids": [], "naam": "X", "element_ids": ["verzonnen"]})).status_code == 422
    assert (await client.post(base, json={"groep_ids": [], "naam": "X"})).status_code == 422


def test_de_vindplaats_noemt_de_regeling_bij_naam():
    """De wortel van de bronboom heet in de graaf kaal "Regeling"; de vindplaats in de voorstellen en
    de werkvoorraad gebruikt de citeertitel (acceptatie 15 okt 2026: "Artikel 9 · Lid 5 – Regeling")."""
    from app.werkgebied_inventaris import nodes_met_titel
    snap = {"doel": {"citeertitel": "Invorderingswet 1990"}, "nodes": [
        {"bron_iri": "urn:bwb:B", "parent_iri": "", "type": "Regeling", "label": "Regeling"},
        {"bron_iri": "urn:bwb:B:artikel:9", "parent_iri": "urn:bwb:B", "type": "Artikel", "label": "Artikel 9"},
        {"bron_iri": "urn:bwb:B:artikel:9:lid:5", "parent_iri": "urn:bwb:B:artikel:9", "type": "Lid", "label": "Lid 5"}]}
    nodes = nodes_met_titel(snap)
    assert begrip_manifest._vindplaats(nodes, "urn:bwb:B:artikel:9:lid:5") == "Artikel 9 · Lid 5 – Invorderingswet 1990"
    assert snap["nodes"][0]["label"] == "Regeling"                 # de snapshot zelf blijft ongemoeid
    from app.werkgebied_werkvoorraad import _regeling
    assert _regeling(nodes, "urn:bwb:B:artikel:9:lid:5") == "Invorderingswet 1990"
