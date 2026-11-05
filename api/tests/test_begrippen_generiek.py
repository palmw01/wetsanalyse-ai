"""Generieke begrippen (ADR-006): één begrip boven de werkgebieden, gebruikt zonder kopie, met passages per werkgebied."""
from __future__ import annotations

from rdflib import DCTERMS as DCT, SKOS, URIRef

from app import begrip_projectie, db
from test_annotatie_v2 import ART
from test_begrippen import DEFINITIE, _annoteer, _begrip, _keur_alles_goed, _url, _werkgebied
from test_begrippen import client, database, graaf, snapshot2  # noqa: F401
from test_werkgebieden import _bron, _nieuw


async def geaccordeerd(client, wg, ids, naam="Belastingschuldige") -> dict:
    """Een begrip door de poort: één passage, beoordeeld, met definitie en toelichting."""
    b = await _begrip(client, wg, [ids["lid1"]], naam=naam)
    r = await client.patch(_url(wg, b), json={"verwachte_revisie": b["revisie"], "inhoud": {"naam": naam, **DEFINITIE}})
    assert r.status_code == 200, r.text
    b = r.json()
    r = await client.patch(_url(wg, b, "koppelingen", b["koppelingen"][0]["id"]),
                           json={"verwachte_revisie": b["revisie"], "beoordeling": "akkoord"})
    assert r.status_code == 200, r.text
    b = r.json()
    r = await client.post(_url(wg, b, "accorderen"), json={"verwachte_revisie": b["revisie"]})
    assert r.status_code == 200, r.text
    return r.json()


async def generiek(client) -> tuple[dict, dict, dict]:
    ids = await _annoteer()
    await _keur_alles_goed(ids)
    wg = await _werkgebied(client)
    b = await geaccordeerd(client, wg, ids)
    r = await client.post(_url(wg, b, "generiek-maken"), json={"verwachte_revisie": b["revisie"]})
    assert r.status_code == 200, r.text
    return ids, wg, r.json()


async def tweede(client, g) -> tuple[dict, dict]:
    """Een tweede werkgebied dat het generieke begrip gebruikt."""
    ander = await _nieuw(client, "Ander")
    ander = (await _bron(client, ander, bron_iri=ART))["werkgebied"]
    r = await client.post(f"/v1/werkgebieden/{ander['id']}/begrippen/gebruik", json={"begrip_id": g["id"]})
    assert r.status_code == 200, r.text
    return ander, r.json()


async def test_generiek_maken_houdt_identiteit_en_passages_en_dit_werkgebied_gebruikt_het(client):
    _, wg, g = await generiek(client)
    assert g["kader"] == "generiek" and g["werkgebied_id"] is None and g["ontstaan_in"] == wg["id"]
    assert g["kader_iri"] == "urn:wa:kader:generiek" and g["iri"].startswith("urn:wa:begrip:")
    assert g["status"] == "geaccordeerd" and len(g["koppelingen"]) == 1
    assert [(x["werkgebied_id"], x["passages"]) for x in g["gebruik"]] == [(wg["id"], 1)]
    lijst = (await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen")).json()["begrippen"]
    assert [(x["id"], x["kader"]) for x in lijst] == [(g["id"], "generiek")]


async def test_alleen_een_geaccordeerd_begrip_wordt_generiek(client):
    ids = await _annoteer()
    wg = await _werkgebied(client)
    b = await _begrip(client, wg, [ids["lid1"]])
    r = await client.post(_url(wg, b, "generiek-maken"), json={"verwachte_revisie": b["revisie"]})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "niet_geaccordeerd"


async def test_dezelfde_term_staat_een_keer_generiek(client):
    ids, _, g = await generiek(client)
    ander = await _nieuw(client, "Ander")
    ander = (await _bron(client, ander, bron_iri=ART))["werkgebied"]
    b = await geaccordeerd(client, ander, {"lid1": ids["lid2"]}, naam="belastingschuldige ")
    r = await client.post(_url(ander, b, "generiek-maken"), json={"verwachte_revisie": b["revisie"]})
    assert r.status_code == 409
    assert r.json()["detail"]["fout"] == "al_generiek" and r.json()["detail"]["begrip_id"] == g["id"]


async def test_een_tweede_werkgebied_gebruikt_het_met_eigen_passages(client):
    ids, _, g = await generiek(client)
    ander = await _nieuw(client, "Ander")
    ander = (await _bron(client, ander, bron_iri=ART))["werkgebied"]
    assert (await client.get(_url(ander, g))).status_code == 404, "zonder gebruik is het er niet"
    r = await client.post(f"/v1/werkgebieden/{ander['id']}/begrippen/gebruik", json={"begrip_id": g["id"]})
    assert r.status_code == 200 and r.json()["koppelingen"] == []
    r = await client.post(f"/v1/werkgebieden/{ander['id']}/begrippen/gebruik", json={"begrip_id": g["id"]})
    assert r.status_code == 200, "idempotent"
    b = r.json()
    r = await client.post(_url(ander, b, "koppelingen"), json={"verwachte_revisie": b["revisie"],
                                                               "element_ids": [ids["lid2"]], "rol": "duiding"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "geaccordeerd", "een passage heropent het generieke begrip niet"
    assert [k["element_id"] for k in r.json()["koppelingen"]] == [ids["lid2"]], "hier alleen de eigen passages"
    alles = (await client.get(f"/v1/begrippen/{g['id']}")).json()
    assert alles["werkgebied"] is None
    assert {k["element_id"] for k in alles["begrip"]["koppelingen"]} == {ids["lid1"], ids["lid2"]}
    assert len(alles["begrip"]["gebruik"]) == 2


async def test_de_inhoud_wijzig_je_niet_vanuit_een_werkgebied(client):
    _, wg, g = await generiek(client)
    inhoud = {"naam": g["inhoud"]["naam"], **DEFINITIE, "uitleg": "Wie betaalt."}
    r = await client.patch(_url(wg, g), json={"verwachte_revisie": g["revisie"], "inhoud": inhoud})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "generiek"
    r = await client.post(_url(wg, g, "heropenen"), json={"verwachte_revisie": g["revisie"]})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "generiek"
    r = await client.patch(f"/v1/begrippen/{g['id']}", json={"verwachte_revisie": g["revisie"], "inhoud": inhoud})
    assert r.status_code == 200, r.text
    assert r.json()["inhoud"]["uitleg"] == "Wie betaalt." and r.json()["status"] == "concept"
    r2 = await client.post(f"/v1/begrippen/{g['id']}/accorderen", json={"verwachte_revisie": r.json()["revisie"]})
    assert r2.status_code == 200 and r2.json()["status"] == "geaccordeerd"
    # De audit van het werkgebied dat het gebruikt noemt de wijziging.
    audit = (await client.get(f"/v1/werkgebieden/{wg['id']}/audit")).json()["audit"]
    assert any(a["actie"] == "begrip-gewijzigd" and a["detail"]["begrip_id"] == g["id"] for a in audit)
    revs = (await client.get(f"/v1/begrippen/{g['id']}/revisies")).json()["revisies"]
    assert revs[0]["actie"] == "begrip-geaccordeerd"


async def test_verwijderen_kan_niet_zolang_het_gebruikt_wordt(client):
    _, wg, g = await generiek(client)
    r = await client.delete(f"/v1/begrippen/{g['id']}", params={"verwachte_revisie": g["revisie"]})
    assert r.status_code == 409 and r.json()["detail"]["fout"] == "in_gebruik"
    assert (await client.delete(f"/v1/werkgebieden/{wg['id']}/begrippen/gebruik/{g['id']}")).status_code == 200
    assert (await client.get(_url(wg, g))).status_code == 404
    weg = await client.get(f"/v1/begrippen/{g['id']}")
    assert weg.json()["begrip"]["koppelingen"] == [], "de passages van dit werkgebied gaan los"
    r = await client.delete(f"/v1/begrippen/{g['id']}", params={"verwachte_revisie": g["revisie"]})
    assert r.status_code == 200, r.text
    assert (await client.get(f"/v1/begrippen/{g['id']}")).status_code == 404


async def test_het_overzicht_toont_het_een_keer_en_filtert_op_kader(client):
    _, wg, g = await generiek(client)
    await _begrip(client, wg, naam="Lokaal")
    alles = (await client.get("/v1/begrippen")).json()["resultaten"]
    assert sorted((x["naam"], x["kader"]) for x in alles) == [("Belastingschuldige", "generiek"), ("Lokaal", "werkgebied")]
    rij = next(x for x in alles if x["kader"] == "generiek")
    assert rij["gebruikt_in"] == 1 and rij["werkgebied_naam"] == "" and rij["id"] == g["id"]
    gevraagd = (await client.get("/v1/begrippen", params={"kader": "generiek"})).json()["resultaten"]
    assert [x["naam"] for x in gevraagd] == ["Belastingschuldige"]
    per_wg = (await client.get("/v1/begrippen", params={"werkgebied_id": wg["id"]})).json()["resultaten"]
    assert {x["naam"] for x in per_wg} == {"Belastingschuldige", "Lokaal"}


async def test_een_gewist_werkgebied_laat_het_generieke_begrip_staan(client):
    _, wg, g = await generiek(client)
    wg = (await client.get(f"/v1/werkgebieden/{wg['id']}")).json()
    r = await client.delete(f"/v1/werkgebieden/{wg['id']}", params={"verwachte_revisie": wg["revisie"]})
    assert r.status_code == 200, r.text
    uit = (await client.get(f"/v1/begrippen/{g['id']}")).json()["begrip"]
    assert uit["gebruik"] == [] and uit["koppelingen"] == []


# --- doorwerking en combineren (G2) ----------------------------------------------------------------------------

async def test_een_wijziging_staat_bij_herbeoordelen_en_een_passage_elders_niet(client):
    ids, wg, g = await generiek(client)
    ander, b = await tweede(client, g)
    h = (await client.get(f"/v1/werkgebieden/{wg['id']}/herbeoordelingen")).json()
    assert h["generiek"] == []
    # Een passage in het tweede werkgebied verandert de inhoud niet.
    r = await client.post(_url(ander, b, "koppelingen"), json={"verwachte_revisie": b["revisie"],
                                                               "element_ids": [ids["lid2"]], "rol": "duiding"})
    assert r.status_code == 200, r.text
    assert (await client.get(f"/v1/werkgebieden/{wg['id']}/herbeoordelingen")).json()["generiek"] == []
    nu = (await client.get(f"/v1/begrippen/{g['id']}")).json()["begrip"]
    inhoud = {**nu["inhoud"], "definitie": "Een andere definitie."}
    r = await client.patch(f"/v1/begrippen/{g['id']}", json={"verwachte_revisie": nu["revisie"], "inhoud": inhoud})
    assert r.status_code == 200, r.text
    h = (await client.get(f"/v1/werkgebieden/{wg['id']}/herbeoordelingen")).json()["generiek"]
    assert [x["begrip_id"] for x in h] == [g["id"]] and h[0]["velden"] == ["definitie"]
    assert h[0]["toen"]["definitie"] == DEFINITIE["definitie"] and h[0]["nu"]["definitie"] == "Een andere definitie."
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/begrippen/gebruik/{g['id']}/bevestigen")
    assert r.status_code == 200, r.text
    assert (await client.get(f"/v1/werkgebieden/{wg['id']}/herbeoordelingen")).json()["generiek"] == []
    h = (await client.get(f"/v1/werkgebieden/{ander['id']}/herbeoordelingen")).json()["generiek"]
    assert len(h) == 1, "het andere werkgebied moet het zelf nog zien"


async def test_een_nieuwe_betekenis_neemt_elk_werkgebied_zelf_over(client):
    _, wg, g = await generiek(client)
    r = await client.post(f"/v1/begrippen/{g['id']}/nieuwe-betekenis",
                          json={"verwachte_revisie": g["revisie"], "reden": "Ruimer na de wetswijziging."})
    assert r.status_code == 201, r.text
    opv = r.json()
    assert opv["kader"] == "generiek" and opv["status"] == "concept" and opv["koppelingen"] == []
    h = (await client.get(f"/v1/werkgebieden/{wg['id']}/herbeoordelingen")).json()["generiek"]
    assert h[0]["opvolger"]["begrip_id"] == opv["id"]
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/begrippen/gebruik/{g['id']}/opvolger")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == opv["id"] and [k["beoordeling"] for k in r.json()["koppelingen"]] == ["open"]
    assert (await client.get(_url(wg, g))).status_code == 404
    assert (await client.get(f"/v1/werkgebieden/{wg['id']}/herbeoordelingen")).json()["generiek"] == []
    # Verwijder je de opvolger (eerst het gebruik stoppen), dan krijgt het oude begrip zijn status terug.
    assert (await client.delete(f"/v1/werkgebieden/{wg['id']}/begrippen/gebruik/{opv['id']}")).status_code == 200
    opv = (await client.get(f"/v1/begrippen/{opv['id']}")).json()["begrip"]
    r = await client.delete(f"/v1/begrippen/{opv['id']}", params={"verwachte_revisie": opv["revisie"]})
    assert r.status_code == 200 and r.json()["hersteld"] == [g["id"]]
    assert (await client.get(f"/v1/begrippen/{g['id']}")).json()["begrip"]["status"] == "geaccordeerd"


async def test_combineren_vervangt_het_lokale_begrip_en_laat_het_generieke_staan(client):
    ids, _, g = await generiek(client)
    ander = await _nieuw(client, "Ander")
    ander = (await _bron(client, ander, bron_iri=ART))["werkgebied"]
    lokaal = await _begrip(client, ander, [ids["lid2"]], naam="Schuldenaar")
    r = await client.post(_url(ander, lokaal, "combineren-generiek"), json={
        "verwachte_revisie": lokaal["revisie"], "generiek_id": g["id"], "reden": "Zelfde begrip."})
    assert r.status_code == 200, r.text
    uit = r.json()
    assert uit["id"] == g["id"] and uit["inhoud"] == g["inhoud"] and uit["status"] == "geaccordeerd"
    assert [k["element_id"] for k in uit["koppelingen"]] == [ids["lid2"]]
    assert uit["koppelingen"][0]["beoordeling"] == "open"
    oud = (await client.get(_url(ander, lokaal))).json()
    assert oud["status"] == "vervangen" and oud["vervangen_door"]["begrip_id"] == g["id"]


async def test_een_lokaal_begrip_krijgt_een_relatie_met_het_generieke(client):
    ids, _, g = await generiek(client)
    ander, _ = await tweede(client, g)
    lokaal = await _begrip(client, ander, [ids["lid2"]], naam="Belastingschuldige bij aanslag")
    r = await client.post(f"/v1/werkgebieden/{ander['id']}/relaties", json={
        "van_begrip": lokaal["id"], "naar_begrip": g["id"], "type": "hierarchie"})
    assert r.status_code == 201, r.text
    rel = (await client.get(f"/v1/begrippen/{g['id']}")).json()["relaties"]
    assert [(x["van_naam"], x["naar_naam"]) for x in rel] == [("Belastingschuldige bij aanslag", "Belastingschuldige")]


# --- de graaf (G3) --------------------------------------------------------------------------------------------

async def test_het_generieke_kader_is_een_eigen_graph_en_een_werkgebied_noemt_het_gebruik(client):
    ids, wg, g = await generiek(client)
    ander, b = await tweede(client, g)
    await client.post(_url(ander, b, "koppelingen"), json={"verwachte_revisie": b["revisie"],
                                                           "element_ids": [ids["lid2"]], "rol": "duiding"})
    async with db.get_engine().connect() as conn:
        inv = await begrip_projectie.invoer(conn, "generiek")
        van_wg = await begrip_projectie.invoer(conn, ander["id"])
    assert inv is not None and [x["id"] for x in inv["begrippen"]] == [g["id"]]
    assert len(inv["begrippen"][0]["koppelingen"]) == 2, "de passages uit alle werkgebieden"
    assert van_wg["begrippen"] == [] and van_wg["gebruikt"] == [g["id"]]
    graaf_g = begrip_projectie.bouw_graaf(inv)
    concept = begrip_projectie.begrip_iri(g["id"])
    assert (concept, SKOS.inScheme, URIRef("urn:wa:kader:generiek")) in graaf_g
    assert len(list(graaf_g.objects(concept, DCT.source))) >= 1
    graaf_w = begrip_projectie.bouw_graaf(van_wg)
    assert (begrip_projectie.kader_iri(ander["id"]), begrip_projectie.WA.gebruiktBegrip, concept) in graaf_w
    assert (concept, SKOS.inScheme, None) not in graaf_w, "een begrip staat in precies één kader"
    assert sorted(await _stand()) == sorted(["generiek", wg["id"], ander["id"]])


async def _stand() -> list[str]:
    return list(await begrip_projectie.postgres_stand())


async def test_een_relatie_met_het_generieke_begrip_staat_in_de_graph_van_het_werkgebied(client):
    ids, _, g = await generiek(client)
    ander, _ = await tweede(client, g)
    lokaal = await _begrip(client, ander, [ids["lid2"]], naam="Bij aanslag")
    r = await client.post(f"/v1/werkgebieden/{ander['id']}/relaties", json={
        "van_begrip": lokaal["id"], "naar_begrip": g["id"], "type": "hierarchie"})
    assert r.status_code == 201, r.text
    async with db.get_engine().connect() as conn:
        graaf_w = begrip_projectie.bouw_graaf(await begrip_projectie.invoer(conn, ander["id"]))
    assert (begrip_projectie.begrip_iri(g["id"]), begrip_projectie.ISOTHES.broaderGeneric,
            begrip_projectie.begrip_iri(lokaal["id"])) in graaf_w


async def test_het_generieke_kader_exporteert_als_turtle_met_conformiteit(client):
    _, _, g = await generiek(client)
    r = await client.get("/v1/begrippen/export")
    assert r.status_code == 200 and "urn:wa:kader:generiek" in r.text and g["id"] in r.text
    c = await client.get("/v1/begrippen/conformiteit")
    assert c.status_code == 200 and g["id"] in c.json()["begrippen"]
