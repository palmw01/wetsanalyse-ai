"""Begrippen naar de kennisgraaf (spoor D, fase F3): NL-SBB-projectie, conformiteit, Turtle-export en de
graafcontrole. De graaf is de nep-GraphDB (`graafdb_fake`), gevuld door de échte projectie."""
from __future__ import annotations

import asyncio
import hashlib

import pytest
from rdflib import Graph, Literal, URIRef

from app import begrip_projectie as bp, db
from app.begrip_projectie import DCT, ISOTHES, SKOS, WA, begrip_iri, graph_iri, kader_iri
from graafdb_fake import installeer
from test_begrip_onderhoud import _geaccordeerd
from test_begrippen import _annoteer, _begrip, _keur_alles_goed, _url, _werkgebied
from test_annotatie_v2 import LAW, ONE
from test_werkgebieden import client, database, graaf, snapshot2  # noqa: F401


def _rel(wg) -> str:
    return f"/v1/werkgebieden/{wg['id']}/relaties"


async def _werkgebied_met_begrippen(client):
    """Een geaccordeerd begrip met een relatie naar een concept (zonder definitie)."""
    ids = await _annoteer()
    await _keur_alles_goed(ids)
    wg = await _werkgebied(client)
    a = await _geaccordeerd(client, wg, [ids["lid1"]], naam="aanslag")
    b = await _begrip(client, wg, [ids["awr"]], naam="navorderingsaanslag")
    r = await client.post(_rel(wg), json={"van_begrip": a["id"], "naar_begrip": b["id"], "type": "hierarchie",
                                          "toelichting": "Een navorderingsaanslag is een soort aanslag."})
    assert r.status_code == 201, r.text
    return ids, wg, a, b


async def _invoer(wid: str) -> dict:
    async with db.get_engine().connect() as conn:
        return await bp.invoer(conn, wid)


def test_de_nl_sbb_shapes_zijn_de_vastgepinde_versie():
    data = (bp.SHAPES / f"nl-sbb-{bp.NL_SBB_VERSIE}.ttl").read_bytes()
    assert hashlib.sha256(data).hexdigest() == "9f123fc852d6debccdf0bead2e498e686d0832fbeb04abf7b211df17e0b3e9af"
    assert "nl-sbb-1.0.0.ttl" in (bp.SHAPES / "BRON.md").read_text()


# --- de graph ------------------------------------------------------------------------------------

async def test_de_graph_volgt_nl_sbb_met_eigen_predicaten(client):
    ids, wg, a, b = await _werkgebied_met_begrippen(client)
    g = bp.bouw_graaf(await _invoer(wg["id"]))
    k, ca, cb = kader_iri(wg["id"]), begrip_iri(a["id"]), begrip_iri(b["id"])
    assert (k, DCT.title, Literal(wg["naam"], lang="nl")) in g
    assert "geen wettelijke definities" in str(g.value(k, URIRef("http://www.w3.org/2000/01/rdf-schema#comment")))
    assert (ca, SKOS.inScheme, k) in g and (ca, SKOS.prefLabel, Literal("aanslag", lang="nl")) in g
    assert g.value(ca, SKOS.definition) is not None and g.value(cb, SKOS.definition) is None
    assert (ca, WA.status, Literal("geaccordeerd")) in g and (cb, WA.status, Literal("concept")) in g
    assert g.value(ca, WA.geaccordeerdOp) is not None
    # De relatie houdt haar type; alleen de hiërarchie heeft ook een ISO 25964-tegenhanger.
    assert (ca, WA.heeftSoort, cb) in g and (cb, ISOTHES.broaderGeneric, ca) in g
    assert (ca, SKOS.related, cb) not in g
    # De bron: een brondocument met de bronnode als object, nooit als subject.
    [doc] = g.objects(ca, DCT.source)
    assert g.value(doc, WA.bron) == URIRef(ONE)
    assert not [s for s in g.subjects() if str(s).startswith("urn:bwb:")]
    # Een koppeling wijst naar het element en draagt de bewijsstand.
    [kop] = g.objects(ca, WA.koppeling)
    assert str(g.value(kop, WA.element)) == f"urn:jas:element:{ids['lid1']}" and g.value(kop, WA.elementHash)
    # Geen personen.
    assert "jurist-a" not in g.serialize(format="turtle")


async def test_conformiteit_per_begrip(client):
    _ids, wg, a, b = await _werkgebied_met_begrippen(client)
    c = bp.conformiteit(bp.bouw_graaf(await _invoer(wg["id"])))
    assert c["beschikbaar"] and c["nl_sbb_versie"] == "1.0.0"
    ca, cb = c["begrippen"][str(begrip_iri(a["id"]))], c["begrippen"][str(begrip_iri(b["id"]))]
    assert ca["conform"] is True and not [m for m in ca["meldingen"] if m["ernst"] == "fout"]
    # Het concept zonder definitie is niet NL-SBB-conform; de melding noemt skos:definition.
    assert cb["conform"] is False
    assert any(m["laag"] == "nl_sbb" and m["ernst"] == "fout" and m["pad"].endswith("#definition")
               for m in cb["meldingen"])
    assert c["kader"] == []

    r = await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen/conformiteit")
    assert r.status_code == 200
    assert {k: v["conform"] for k, v in r.json()["begrippen"].items()} == {a["id"]: True, b["id"]: False}


def test_eigen_shapes_vangen_een_kapotte_koppeling():
    inv = {"schema": 1, "werkgebied": {"id": "w1", "naam": "W", "analysevraag": ""}, "relaties": [],
           "begrippen": [{"id": "b1", "status": "geaccordeerd", "revisie": 2, "geaccordeerd_op": None,
                          "geaccordeerd_revisie": None, "gewijzigd": None,
                          "inhoud": {"naam": "x", "definitie": "Een x.", "definitie_herkomst": ""},
                          "koppelingen": [{"id": "k1", "element_id": "e1", "rol": "duiding", "beoordeling": "akkoord",
                                           "element_hash": "", "vindplaats": "", "tekst": "", "bron": []}]}]}
    c = bp.conformiteit(bp.bouw_graaf(inv))
    meldingen = {m["melding"] for m in c["begrippen"][str(begrip_iri("b1"))]["meldingen"] if m["laag"] == "eigen"}
    assert "De definitie heeft geen herkomst (letterlijk, samengesteld of geformuleerd)." in meldingen
    assert "Een geaccordeerd begrip mist het tijdstip of de revisie van het accorderen." in meldingen
    assert "Een koppeling draagt haar bewijsstand (element-hash)." in meldingen
    # Eigen meldingen maken een begrip niet on-NL-SBB-conform: dat zegt alleen het profiel.
    assert c["begrippen"][str(begrip_iri("b1"))]["conform"] is True


# --- projectie ------------------------------------------------------------------------------------

async def test_projectie_reconcile_en_herstel(client, monkeypatch):
    nep = installeer(monkeypatch)
    _ids, wg, a, _b = await _werkgebied_met_begrippen(client)
    wid = wg["id"]
    assert await bp.reconcile() == 1
    g = nep.ds.graph(graph_iri(wid))
    assert (begrip_iri(a["id"]), SKOS.prefLabel, Literal("aanslag", lang="nl")) in g
    assert (await bp.register())[wid]["hash"] == bp.invoer_hash(await _invoer(wid))
    assert await bp.reconcile() == 0                                   # bij: niets te doen

    # Een wijziging in Postgres: de hash wijkt af, de lus schrijft opnieuw.
    r = await client.patch(_url(wg, a), json={"verwachte_revisie": a["revisie"],
                                              "inhoud": {**a["inhoud"], "alternatieve_termen": ["belastingaanslag"]}})
    assert r.status_code == 200, r.text
    assert await bp.reconcile() == 1
    assert (begrip_iri(a["id"]), SKOS.altLabel, Literal("belastingaanslag", lang="nl")) in nep.ds.graph(graph_iri(wid))

    # Graph verloren (GraphDB herstart), register nog wel: toch weer opgebouwd.
    nep.ds.remove_graph(nep.ds.graph(graph_iri(wid)))
    assert await bp.reconcile() == 1 and len(nep.ds.graph(graph_iri(wid)))

    # Gearchiveerd: graph en registerregel weg.
    w = (await client.get(f"/v1/werkgebieden/{wid}")).json()
    assert (await client.delete(f"/v1/werkgebieden/{wid}", params={"verwachte_revisie": w["revisie"]})).status_code == 200
    assert await bp.reconcile() == 1
    assert not len(nep.ds.graph(graph_iri(wid))) and wid not in await bp.register()


async def test_direct_na_de_commit(client, monkeypatch):
    nep = installeer(monkeypatch)
    bp.activeer(True)
    try:
        _ids, wg, a, _b = await _werkgebied_met_begrippen(client)
        await asyncio.gather(*list(bp._taken))
        g = nep.ds.graph(graph_iri(wg["id"]))
        assert (begrip_iri(a["id"]), WA.status, Literal("geaccordeerd")) in g
        # Een geweigerde mutatie (412) projecteert niets en laat geen notitie achter op de verbinding.
        bp._geschreven.clear()
        r = await client.patch(_url(wg, a), json={"verwachte_revisie": 1, "inhoud": a["inhoud"]})
        assert r.status_code == 412
        assert not bp._taken
    finally:
        await bp.stop()


async def test_projectie_laat_een_besluit_niet_falen_als_graphdb_hapert(client, monkeypatch):
    nep = installeer(monkeypatch)
    nep.storing(True)
    bp.activeer(True)
    try:
        _ids, wg, a, _b = await _werkgebied_met_begrippen(client)
        await asyncio.gather(*list(bp._taken))
        assert (await client.get(_url(wg, a))).status_code == 200
    finally:
        await bp.stop()
    nep.storing(False)
    assert await bp.reconcile() == 1


# --- export ---------------------------------------------------------------------------------------

async def test_turtle_export(client, monkeypatch):
    nep = installeer(monkeypatch)
    nep.ds.update(f'INSERT DATA {{ GRAPH <urn:bwb:graph:BWBR0004770> {{ <{ONE}> '
                  f'<http://www.w3.org/2002/07/owl#sameAs> <https://wetten.overheid.nl/jci1.3:c:BWBR0004770&artikel=9&lid=1> }} }}')
    _ids, wg, a, b = await _werkgebied_met_begrippen(client)
    r = await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen/export", params={"formaat": "ttl"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/turtle")
    g = Graph().parse(data=r.text, format="turtle")
    k, ca, cb = kader_iri(wg["id"]), begrip_iri(a["id"]), begrip_iri(b["id"])
    # Standaard alleen geaccordeerd; een relatie naar een begrip dat niet meegaat, gaat ook niet mee.
    assert (ca, SKOS.prefLabel, None) in g and (cb, SKOS.prefLabel, None) not in g
    assert (ca, WA.heeftSoort, cb) not in g
    assert (k, DCT.conformsTo, bp.NL_SBB) in g and (k, WA.nlSbbVersie, Literal("1.0.0")) in g
    assert (ca, WA.nlSbbConform, Literal(True)) in g
    [doc] = g.objects(ca, DCT.source)
    assert str(g.value(doc, URIRef("http://xmlns.com/foaf/0.1/page"))).startswith("https://wetten.overheid.nl/jci1.3:")

    r = await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen/export", params={"formaat": "ttl", "inclusief": "alle"})
    g = Graph().parse(data=r.text, format="turtle")
    assert (cb, WA.nlSbbConform, Literal(False)) in g and (ca, WA.heeftSoort, cb) in g


async def test_turtle_export_zonder_graaf_en_zonder_begrippen(client):
    wg = await _werkgebied(client)
    r = await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen/export", params={"formaat": "ttl"})
    assert r.status_code == 200
    g = Graph().parse(data=r.text, format="turtle")
    assert (kader_iri(wg["id"]), None, None) in g and not list(g.subjects(None, SKOS.Concept))


# --- samenhang en graafcontrole ------------------------------------------------------------------

async def test_samenhang_voor_de_werkplek(client):
    ids, wg, a, b = await _werkgebied_met_begrippen(client)
    r = await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen/samenhang")
    assert r.status_code == 200, r.text
    d = r.json()
    assert {x["naam"]: x["status"] for x in d["begrippen"]} == {"aanslag": "geaccordeerd", "navorderingsaanslag": "concept"}
    assert {(x["begrip_id"], x["element_id"], x["rol"]) for x in d["koppelingen"]} == {
        (a["id"], ids["lid1"], "duiding"), (b["id"], ids["awr"], "duiding")}
    [rel] = d["relaties"]
    assert (rel["van_begrip"], rel["type"], rel["naar_begrip"]) == (a["id"], "hierarchie", b["id"])
    assert d["voorstellen"] == []


async def test_graafcontrole_ziet_de_begrippengraph(client, monkeypatch):
    from app.graafcontrole import controleer

    nep = installeer(monkeypatch)
    _ids, wg, a, _b = await _werkgebied_met_begrippen(client)
    uit = await controleer(shacl=True)
    assert uit["begrippen"]["achterstand"] == [{"werkgebied_id": wg["id"]}]
    await bp.reconcile()
    uit = await controleer(shacl=True)
    assert uit["begrippen"]["achterstand"] == [] and uit["begrippen"]["afwijkingen"] == []
    assert uit["begrippen"]["invariant_schoon"] and uit["begrippen"]["nl_sbb_niet_conform"] == 1
    # Iemand wijzigt de graph met de hand.
    nep.ds.graph(graph_iri(wg["id"])).add((begrip_iri(a["id"]), SKOS.altLabel, Literal("vervalst", lang="nl")))
    uit = await controleer(shacl=False)
    assert [x["soort"] for x in uit["begrippen"]["afwijkingen"]] == ["inhoud_wijkt_af"] and uit["in_orde"] is False
    # Een wettekst-subject in een begrippengraph breekt de invariant.
    nep.ds.graph(graph_iri(wg["id"])).add((URIRef(LAW), SKOS.prefLabel, Literal("x")))
    assert (await controleer(shacl=False))["begrippen"]["invariant_schoon"] is False


@pytest.fixture(autouse=True)
def _schoon():
    bp._geschreven.clear()
    yield
    bp.activeer(False)
