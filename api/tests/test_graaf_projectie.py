"""Projectie van de annotatielagen naar de kennisgraaf: het RDF-model, de invarianten die de
wettekst schoon houden, en herstel na verlies van de graaf."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import OWL, PROV, RDF, RDFS, SKOS

from app.annotatie_contracts import (
    AgentRun, Aandacht, Alternatief, AnnotatieDocument, AnnotatieElement, Anker, Beslissing,
    BeslissingType, CriticRonde, Lifecycle, LidStand, ReviewReason,
)
from app.graaf_projectie import (
    REGISTER_GRAAF, GraafProjector, RepositoryOntbreekt, bouw_laaggraaf, bouw_register,
    laag_graaf_iri,
)
from app.jas_ontologie import JAS, JASK, OA, ONTOLOGIE_GRAAF, bouw_ontologie

T0 = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
LID1 = "urn:bwb:BWBR0004770:artikel:9:lid:1"
TTL = Path(__file__).resolve().parents[2] / "docs" / "wetsanalyse-workbench" / "jas-ontologie.ttl"
# graph-qa bewijst met deze laag dat zijn queries niet door annotaties vervuild raken
# (`tools/graph-qa/tests/test_annotatielaag_isolatie.py`). Hij kan de api niet importeren, dus hij
# krijgt een afdruk – en die moet de echte projectie blijven volgen.
GRAPH_QA_FIXTURE = (Path(__file__).resolve().parents[2] / "tools" / "graph-qa" / "tests" / "fixtures"
                    / "jas_laag_voorbeeld.ttl")


def _laag(**kw) -> AnnotatieDocument:
    run = AgentRun(model="claude-sonnet-4-6", agent_versie="0.4.0", modus="nieuw", leden=["1"],
                   prompt_hash="p1", methode_versie="m1", tijd=T0)
    el = AnnotatieElement(
        id="e1", klasse="Rechtssubject", tekst="de ontvanger", lid="1",
        toelichting="wie int", lifecycle=Lifecycle.human_approved, aandacht=Aandacht.geel,
        alternatieven=[Alternatief(klasse="Rechtsobject", motivatie="twijfel")],
        critic_rondes=[CriticRonde(ronde=1, aandacht=Aandacht.geel, motivatie="let op",
                                   voorstel_klasse="Rechtsobject", tijd=T0)],
        anker=Anker(lid="1", start=3, eind=15, voor="1. ", na=" kan", bron_hash="art", lid_hash="h1"),
        geproduceerd_door=run,
        beslissingen=[Beslissing(type=BeslissingType.approve, actor="jurist-a", tijd=T0,
                                 review_reason=ReviewReason.interpretatie)],
    )
    oud = AnnotatieElement(id="e0", klasse="Voorwaarde", tekst="indien", lid="1", verouderd=True,
                           verouderd_op=T0, lifecycle=Lifecycle.rejected)
    velden = dict(slug="laag1", bwbId="BWBR0004770", artikel="9", laag_sleutel="BWBR0004770:9",
                  citeertitel="Invorderingswet 1990", elementen=[el, oud], runs=[run],
                  leden={"1": LidStand(hash="h1", iri=LID1, bijgewerkt=T0)}, updated=T0)
    velden.update(kw)
    return AnnotatieDocument(**velden)


# --- het model -----------------------------------------------------------------------------------

def test_markering_is_een_web_annotation_op_het_lid():
    g = bouw_laaggraaf(_laag())
    a = URIRef("urn:jas:annotatie:BWBR0004770:artikel:9:e1")
    assert (a, RDF.type, OA.Annotation) in g
    assert (a, OA.hasBody, JASK.rechtssubject) in g
    doel = g.value(a, OA.hasTarget)
    assert g.value(doel, OA.hasSource) == URIRef(LID1)
    quote = next(s for s in g.objects(doel, OA.hasSelector) if (s, RDF.type, OA.TextQuoteSelector) in g)
    assert g.value(quote, OA.exact) == Literal("de ontvanger")
    positie = next(s for s in g.objects(doel, OA.hasSelector) if (s, RDF.type, OA.TextPositionSelector) in g)
    assert int(g.value(positie, OA.start)) == 3 and g.value(positie, JAS.lidHash) == Literal("h1")


def test_herkomst_en_oordeel_als_nodes():
    g = bouw_laaggraaf(_laag())
    a = URIRef("urn:jas:annotatie:BWBR0004770:artikel:9:e1")
    run = g.value(a, PROV.wasGeneratedBy)
    assert (run, RDF.type, JAS.AgentRun) in g
    assert (run, PROV.wasAssociatedWith, URIRef("urn:jas:agent:model:claude-sonnet-4-6")) in g
    assert g.value(run, JAS.promptHash) == Literal("p1")

    besl = g.value(a, JAS.heeftBeslissing)
    assert (besl, PROV.wasAssociatedWith, URIRef("urn:jas:agent:mens:jurist-a")) in g
    assert g.value(besl, JAS.beslissingType) == JAS["beslissing-approve"]
    assert g.value(besl, JAS.reviewReden) == JAS["reden-interpretatie"]

    assert g.value(a, JAS.lifecycle) == JAS["lifecycle-human_approved"]
    assert g.value(g.value(a, JAS.heeftAlternatief), JAS.klasse) == JASK.rechtsobject
    critic = g.value(a, JAS.heeftCriticRonde)
    assert g.value(critic, JAS.voorstelKlasse) == JASK.rechtsobject

    oud = URIRef("urn:jas:annotatie:BWBR0004770:artikel:9:e0")
    assert g.value(oud, JAS.verouderd) == Literal(True)
    assert g.value(oud, JAS.lifecycle) == JAS["lifecycle-rejected"]


def test_laag_en_lidstand():
    g = bouw_laaggraaf(_laag())
    laag = URIRef("urn:jas:laag:BWBR0004770:artikel:9")
    assert g.value(laag, JAS.bepaling) == URIRef("urn:bwb:BWBR0004770:artikel:9")
    ls = g.value(laag, JAS.heeftLidstand)
    assert g.value(ls, JAS.lidHash) == Literal("h1") and g.value(ls, JAS.bepaling) == URIRef(LID1)


def test_geen_annotatie_vervuilt_de_wettekst():
    """Een subject onder urn:bwb: of een urn:bwb-ns:tekst zou de annotatie in de union-queries, de
    similarity-index en de bronnencontrole van Lex laten opduiken als wettekst."""
    g = bouw_laaggraaf(_laag())
    g += bouw_register([_laag()])
    for s, p, _ in g:
        assert not str(s).startswith("urn:bwb:"), s
        assert not str(p).startswith("urn:bwb-ns:"), p
    # Het enige contact met de wet is een object: de bron van het doel en de bepaling.
    assert {str(o) for _, _, o in g if str(o).startswith("urn:bwb:")} == {
        LID1, "urn:bwb:BWBR0004770:artikel:9"}


def test_iri_segmenten_worden_geescaped_zoals_de_importer():
    g = bouw_laaggraaf(_laag(artikel="3:4", laag_sleutel="BWBR0004770:3:4"))
    assert URIRef("urn:jas:laag:BWBR0004770:artikel:3%3A4") in set(g.subjects())
    assert laag_graaf_iri(_laag(artikel="3:4")) == URIRef("urn:jas:graph:BWBR0004770:artikel:3%3A4")


def test_projectie_is_deterministisch():
    assert isomorphic(bouw_laaggraaf(_laag()), bouw_laaggraaf(_laag()))


# --- de ontologie --------------------------------------------------------------------------------

def test_ontologie_leidt_niets_af_op_wet_nodes():
    """`rdfsplus-optimized` zou met een domain/range triples áfleiden op urn:bwb:-nodes."""
    g = bouw_ontologie()
    for verboden in (RDFS.domain, RDFS.range, RDFS.subPropertyOf, RDFS.subClassOf, OWL.sameAs):
        assert not list(g.triples((None, verboden, None))), verboden
    concepten = set(g.subjects(SKOS.inScheme, JAS.klassen))
    assert len(concepten) == 13


def test_ontologie_ttl_is_actueel():
    """Het bestand in docs is een afdruk van `bouw_ontologie`. Faalt dit: draai
    `uv run python -c "from app.jas_ontologie import ontologie_turtle; print(ontologie_turtle())"`
    en schrijf het naar docs/wetsanalyse-workbench/jas-ontologie.ttl."""
    opgeslagen = Graph().parse(TTL, format="turtle")
    assert isomorphic(opgeslagen, bouw_ontologie())


def test_graph_qa_fixture_volgt_de_projectie():
    """Faalt dit na een wijziging aan het model: schrijf `bouw_laaggraaf(_laag())` als Turtle naar
    tools/graph-qa/tests/fixtures/jas_laag_voorbeeld.ttl en draai de isolatietest van graph-qa."""
    opgeslagen = Graph().parse(GRAPH_QA_FIXTURE, format="turtle")
    assert isomorphic(opgeslagen, bouw_laaggraaf(_laag()))


# --- schrijven naar een nep-GraphDB --------------------------------------------------------------

class NepGraphDB:
    """Genoeg Graph Store Protocol + ASK om de projector te testen."""

    def __init__(self) -> None:
        self.graven: dict[str, Graph] = {}
        self.volgorde: list[str] = []
        self.repo_bestaat = True
        self.falen = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if not self.repo_bestaat:
            return httpx.Response(404)
        if self.falen:
            return httpx.Response(503)
        if request.method == "PUT":
            assert request.headers["content-type"] == "text/turtle"
            graaf = request.url.params["graph"]
            self.graven[graaf] = Graph().parse(data=request.content.decode(), format="turtle")
            self.volgorde.append(graaf)
            return httpx.Response(204)
        query = parse_qs(request.content.decode())["query"][0]
        assert query.startswith("ASK")
        return httpx.Response(200, json={"boolean": str(REGISTER_GRAAF) in self.graven})


@pytest.fixture
async def omgeving(monkeypatch):
    monkeypatch.setenv("WETSANALYSE_AUTH_REQUIRED", "0")
    from app import db, graaf_projectie, ratelimit
    from app.annotatie_store import AnnotatieStore
    from app.config import get_settings
    from app.deps import get_annotatie_store
    from conftest import maak_testgebruikers

    get_settings.cache_clear()
    get_annotatie_store.cache_clear()
    ratelimit.reset()
    db.init_engine("sqlite+aiosqlite://")
    await db.create_all()
    await maak_testgebruikers("jurist-a")

    nep = NepGraphDB()
    client = httpx.AsyncClient(transport=httpx.MockTransport(nep))
    projector = GraafProjector("http://graphdb:7200", "inning", client=client)
    store = AnnotatieStore()
    await store.maak_document(_laag())
    yield nep, projector, store

    graaf_projectie.zet_projector(None)
    await client.aclose()
    get_settings.cache_clear()
    get_annotatie_store.cache_clear()
    await db.dispose_engine()


async def test_herstel_na_verlies_ontologie_eerst_register_laatst(omgeving):
    nep, projector, store = omgeving
    uitkomst = await projector.reconcile(store)
    assert uitkomst == {"volledig": True, "geprojecteerd": 1}
    laag_graaf = str(laag_graaf_iri(_laag()))
    assert nep.volgorde == [str(ONTOLOGIE_GRAAF), laag_graaf, str(REGISTER_GRAAF)]
    assert isomorphic(nep.graven[laag_graaf], bouw_laaggraaf(await store.laad_document("laag1")))
    assert (await store.projectie_telling()) == {"lagen": 1, "achterstand": 0}

    # Niets veranderd: de volgende ronde schrijft niets.
    nep.volgorde.clear()
    assert await projector.reconcile(store) == {"volledig": False, "geprojecteerd": 0}
    assert nep.volgorde == []

    # GraphDB herstart: alles weg → alles terug.
    nep.graven.clear()
    assert (await projector.reconcile(store))["volledig"] is True
    assert laag_graaf in nep.graven and str(REGISTER_GRAAF) in nep.graven


async def test_mislukte_projectie_laat_de_laag_vuil(omgeving):
    nep, projector, store = omgeving
    nep.falen = True
    with pytest.raises(httpx.HTTPStatusError):
        await projector.reconcile(store)
    assert (await store.projectie_telling())["achterstand"] == 1
    nep.falen = False
    await projector.reconcile(store)
    assert (await store.projectie_telling())["achterstand"] == 0


async def test_ontbrekende_repository_is_wachten(omgeving):
    nep, projector, store = omgeving
    nep.repo_bestaat = False
    with pytest.raises(RepositoryOntbreekt):
        await projector.reconcile(store)
    assert (await store.projectie_telling())["achterstand"] == 1


async def test_oudere_projectie_na_nieuwere_laat_de_laag_vuil(omgeving):
    _, projector, store = omgeving
    await projector.reconcile(store)
    doc = await store.laad_document("laag1")
    await store.muteer_document("laag1", "jurist-a", lambda d: None)     # nieuwe stand
    await store.markeer_geprojecteerd("laag1", doc.updated)               # de trage, oude PUT
    assert (await store.projectie_telling())["achterstand"] == 1


async def test_mutatie_projecteert_op_de_achtergrond(omgeving):
    import asyncio

    from app import graaf_projectie

    nep, projector, store = omgeving
    await projector.reconcile(store)
    graaf_projectie.zet_projector(projector)

    def keur_af(doc):
        doc.elementen[0].lifecycle = Lifecycle.rejected

    await store.muteer_document("laag1", "jurist-a", keur_af)
    await asyncio.gather(*projector._taken)
    g = nep.graven[str(laag_graaf_iri(_laag()))]
    a = URIRef("urn:jas:annotatie:BWBR0004770:artikel:9:e1")
    assert g.value(a, JAS.lifecycle) == JAS["lifecycle-rejected"]
    assert (await store.projectie_telling())["achterstand"] == 0


async def test_per_gebruiker_document_wordt_niet_geprojecteerd(omgeving):
    nep, projector, store = omgeving
    await store.maak_document(AnnotatieDocument(slug="prive", user_id="jurist-a",
                                                bwbId="BWBR0004770", artikel="10"))
    assert await projector.projecteer(store, "prive") is False
    await projector.reconcile(store)
    assert not any("artikel:10" in g for g in nep.graven)


async def test_admin_status_en_herprojecteer(omgeving, monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from app import graaf_projectie
    from app.config import get_settings

    nep, projector, store = omgeving
    monkeypatch.setenv("WETSANALYSE_ADMIN_TOKENS", "beheer:geheim")
    get_settings.cache_clear()
    from app.main import app

    admin = {"Authorization": "Bearer geheim"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/v1/admin/annotatie/herprojecteer", headers=admin)
        assert r.status_code == 409                      # projectie staat uit
        graaf_projectie.zet_projector(projector)
        await projector.reconcile(store)
        status = (await ac.get("/v1/admin/annotatie/projectie", headers=admin)).json()
        assert status["actief"] and status["lagen"] == 1 and status["achterstand"] == 0
        r = await ac.post("/v1/admin/annotatie/herprojecteer", headers=admin)
        assert r.status_code == 202 and r.json()["achterstand"] == 1
