"""De afleidingsregels in de graph van hun werkgebied (ADR-018 §7; regels herleidbaar, 20 nov 2026): alle regels met
hun status, de weg regel → drager → markering → bronnode, de voorwaarden met hun verwijzing, en de conformiteit."""
from __future__ import annotations

from rdflib import RDF, Literal, URIRef

from app import begrip_projectie as bp, db, regel_projectie as rp
from app.graaf_projectie_v2 import element_iri
from test_regels import _begrip, _inhoud, _opzet, _url
from gedeelde_bron import ONE, client, database, graaf  # noqa: F401

WA, PROV, DCT = rp.WA, rp.PROV, rp.DCT


async def _invoer(wid: str) -> dict:
    async with db.get_engine().connect() as conn:
        return await bp.invoer(conn, wid)


async def _twee_regels(client):
    wg, ids, b = await _opzet(client)
    onder = (await client.post(_url(wg), json={"inhoud": _inhoud(b), "dragers": [
        {"element_id": ids["ar"], "rol": "grondslag"}, {"element_id": ids["rs"], "rol": "invoer"}]})).json()
    uit = await _begrip(client, wg, "uitbetaling", ids["ar"], rol="afgeleid")
    regel_b = await _begrip(client, wg, "bepalen van de uitbetaling", ids["ar"], rol="afgeleid")
    boven = (await client.post(_url(wg), json={"inhoud": {
        "soort": "beslisregel", "regelbegrip_id": regel_b["id"], "uitvoer_begrip_id": uit["id"],
        "invoer": [{"begrip_id": b["uit"]["id"]}],
        "gevallen": [{"voorwaarden": {"verband": "een_van", "delen": [
            {"tekst": "het termijnbedrag is bepaald", "geval_van": {"regel_id": onder["id"], "geval": ""}},
            {"tekst": "het bedrag is positief", "element_ids": [ids["var"]]}]},
            "uitkomst": [{"soort": "tekst", "tekst": "in één keer"}]}]},
        "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    assert "id" in onder and "id" in boven, (onder, boven)
    return wg, ids, onder, boven


async def test_een_regel_is_in_de_graaf_te_volgen_tot_de_bronnode(client):
    wg, ids, onder, boven = await _twee_regels(client)
    inv = await _invoer(wg["id"])
    assert [r["id"] for r in inv["regels"]] == sorted([onder["id"], boven["id"]])
    g = bp.bouw_graaf(inv)
    r = rp.regel_iri(onder["id"])
    assert (r, RDF.type, WA.Afleidingsregel) in g and (r, WA.status, Literal("concept")) in g
    assert (r, WA.inKader, bp.kader_iri(wg["id"])) in g
    # Regel → markering → bronnode, in één stap en via de drager.
    assert (r, WA.rustOp, element_iri(ids["ar"])) in g
    assert (r, PROV.wasDerivedFrom, URIRef(ONE)) in g
    dragers = list(g.objects(r, WA.drager))
    assert {str(g.value(d, WA.rol)) for d in dragers} == {"grondslag", "invoer"}
    assert all(g.value(d, WA.element) is not None and g.value(d, WA.elementHash) for d in dragers)
    assert {g.value(d, WA.bron) for d in dragers} >= {URIRef(ONE)}
    # De voorwaarde van de bovenste regel verwijst naar het geval van de onderste; de andere rust op een markering.
    bladen = list(g.subjects(RDF.type, WA.Voorwaarde))
    assert {g.value(v, WA.gevalVan) for v in bladen} >= {rp.geval_iri(onder["id"], 1)}
    assert any((v, WA.rustOp, element_iri(ids["var"])) in g for v in bladen)
    assert (g.value(next(g.subjects(RDF.type, WA.Voorwaardengroep)), WA.verband)) == Literal("een_van")
    assert g.value(r, WA.regeltekst) is not None
    # De wettekst blijft schoon: geen subject onder urn:bwb:.
    assert not any(str(s).startswith("urn:bwb:") for s in g.subjects())


async def test_alle_regels_met_hun_status_en_vervanging(client):
    wg, ids, onder, boven = await _twee_regels(client)
    r = await client.post(_url(wg, boven["id"], "afwijzen"),
                          json={"verwachte_revisie": boven["revisie"], "reden": "Dubbel", "opvolger_id": onder["id"]})
    assert r.status_code == 200, r.text
    g = bp.bouw_graaf(await _invoer(wg["id"]))
    assert (rp.regel_iri(boven["id"]), WA.status, Literal("vervangen")) in g
    assert (rp.regel_iri(boven["id"]), DCT.isReplacedBy, rp.regel_iri(onder["id"])) in g
    assert (rp.regel_iri(onder["id"]), DCT.replaces, rp.regel_iri(boven["id"])) in g


async def test_de_export_neemt_alleen_geaccordeerde_regels(client):
    wg, *_ = await _twee_regels(client)
    inv = await _invoer(wg["id"])
    assert "regels" not in bp.alleen_geaccordeerd(inv)
    g = bp.bouw_graaf(bp.alleen_geaccordeerd(inv))
    assert not list(g.subjects(RDF.type, WA.Afleidingsregel))


async def test_een_werkgebied_zonder_regels_houdt_zijn_vorm(client):
    wg, *_ = await _opzet(client)
    assert "regels" not in await _invoer(wg["id"])


async def test_de_regels_zijn_conform_en_een_kale_voorwaarde_is_een_waarschuwing(client):
    wg, ids, onder, boven = await _twee_regels(client)
    g = bp.bouw_graaf(await _invoer(wg["id"]))
    c = rp.conformiteit(g)
    if not c["beschikbaar"]:
        return
    assert all(v["conform"] for v in c["regels"].values()), c
    # Zonder markering en zonder verwijzing: een waarschuwing, geen fout.
    blad = next(v for v in g.subjects(RDF.type, WA.Voorwaarde) if g.value(v, WA.gevalVan) is not None)
    g.remove((blad, WA.gevalVan, None))
    c = rp.conformiteit(g)
    meldingen = c["regels"][str(rp.regel_iri(boven["id"]))]["meldingen"]
    assert c["regels"][str(rp.regel_iri(boven["id"]))]["conform"] and any(m["ernst"] == "waarschuwing" for m in meldingen)
    # Een drager zonder bron: een fout.
    d = next(g.objects(rp.regel_iri(onder["id"]), WA.drager))
    g.remove((d, WA.bron, None))
    assert rp.conformiteit(g)["regels"][str(rp.regel_iri(onder["id"]))]["conform"] is False


def test_de_rooktest_volgt_markering_bronnode_en_tekst():
    q = rp.NIET_HERLEIDBAAR
    for stuk in ("wa:rustOp", "oa:hasTarget/oa:hasSource", "bwb:tekst", "bwb:jci", "bwb:bronUrl", "urn:jas:graph:"):
        assert stuk in q


async def test_de_graafcontrole_volgt_een_regel_tot_de_wettekst(client, monkeypatch):
    """Eind tot eind in de nep-graaf: zonder JAS-laag en bronnode is elke regel niet herleidbaar; met de markering in een
    laag en de bronnode met tekst en jci valt de regel uit die lijst."""
    from rdflib import Namespace
    from app.graafcontrole import controleer
    from graafdb_fake import installeer

    nep = installeer(monkeypatch)
    wg, ids, onder, boven = await _twee_regels(client)
    await bp.reconcile()
    uit = (await controleer(shacl=True))["begrippen"]
    assert uit["achterstand"] == [] and uit["afwijkingen"] == [] and uit["regels_niet_conform"] == 0
    assert {r["regel_id"] for r in uit["regels_niet_herleidbaar"]} == {onder["id"], boven["id"]}

    oa, bwb = Namespace("http://www.w3.org/ns/oa#"), Namespace("urn:bwb-ns:")
    jas = nep.ds.graph(URIRef("urn:jas:graph:v2:test"))
    bron = nep.ds.graph(URIRef("urn:bwb:graph:BWBR0004770"))
    for eid in (ids["ar"], ids["rs"], ids["var"]):
        doel = URIRef(f"urn:test:doel:{eid}")
        jas.add((element_iri(eid), oa.hasTarget, doel))
        jas.add((doel, oa.hasSource, URIRef(ONE)))
    bron.add((URIRef(ONE), bwb.tekst, Literal("😀 Alfa Alfa", lang="nl")))
    bron.add((URIRef(ONE), bwb.jci, Literal("jci1.3:c:BWBR0004770&artikel=9&lid=1")))
    uit = (await controleer(shacl=False))["begrippen"]
    assert uit["regels_niet_herleidbaar"] == []


async def test_een_voorbeeld_staat_met_zijn_waarden_in_de_graaf(client):
    wg, ids, b = await _opzet(client)
    vb = {"invoer": "12 termijnen", "uitkomst": "100", "waarden": [{"begrip_id": b["in"]["id"], "waarde": "12"}]}
    r = await client.post(_url(wg), json={"inhoud": {**_inhoud(b), "voorbeelden": [vb]},
                                          "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})
    regel = r.json()
    g = bp.bouw_graaf(await _invoer(wg["id"]))
    [v] = list(g.objects(rp.regel_iri(regel["id"]), WA.voorbeeld))
    assert (v, WA.inGeval, rp.geval_iri(regel["id"], 1)) in g and (v, WA.oordeel, Literal("open")) in g
    [w] = list(g.objects(v, WA.waarde))
    assert (w, WA.waarde, Literal("12")) in g and (w, WA.begrip, bp.begrip_iri(b["in"]["id"])) in g


def test_een_voorbeeld_met_van_geval_breekt_de_dragers_niet():
    """SonarQube S8510: de lus over `van_geval` heette ook `x`, en overschreef zo de regel; daarna las `x["dragers"]` een
    geval-verwijzing en liep de projectie vast op een KeyError."""
    from rdflib import Graph, URIRef

    from app.regel_projectie import WA, bouw

    regel = {
        "id": "r1", "status": "concept", "revisie": 1, "herkomst": "mens", "vervangen_door": None, "opvolger_van": None,
        "regeltekst": {"tekst": "", "gevallen": []},
        "inhoud": {"soort": "afleiding", "regelbegrip_id": "b1", "uitvoer_begrip_id": "b2", "gevallen": [{"label": "A"}],
                   "voorbeelden": [{"invoer": "x", "uitkomst": "y", "van_geval": [{"regel_id": "r2", "geval": "B"}]}]},
        "dragers": [{"id": "d1", "rol": "grondslag", "beoordeling": "akkoord", "element_id": "e1", "element_hash": "h",
                     "tekst": "passage", "geval": None, "bron": ["urn:bwb:BWBR0004770:artikel:9"]}],
    }
    g = Graph()
    bouw(g, URIRef("urn:wa:kader:test"), [regel])
    assert (URIRef("urn:wa:regeldrager:d1"), WA.rol, None) in g
    assert any(g.objects(None, WA.gevalVan))
