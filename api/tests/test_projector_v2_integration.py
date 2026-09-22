"""Echte PostgreSQL-transacties met uitvoerende HTTP/SPARQL-testadapter.

Zonder ANNOTATIE_TEST_GRAPHDB_URL voert RDFLib de HTTP-query's en updates uit;
met deze optionele URL draait hetzelfde scenario op een gelicenseerde GraphDB.
Elke test bezit een UUID-schema/repository; geen gedeelde repository wordt aangepast.
"""
import asyncio
import os
import uuid
import json
from urllib.parse import parse_qs

import httpx
import pytest
from rdflib import Dataset, Literal, URIRef
from sqlalchemy import select

from app import db, graaf_projectie_v2 as projection
from app import annotatie_v2_store as store
from app.annotatie_v2_contracts import Beslissing
from app.config import get_settings
from test_annotatie_v2 import ONE, element, request, snapshot
from test_annotatie_v2_postgres import postgres_schema  # noqa: F401 – pytest fixture

pytestmark = pytest.mark.skipif(not os.getenv("ANNOTATIE_TEST_DSN"), reason="PostgreSQL-integratieserver ontbreekt")

CONFIG = '''@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>.
@prefix rep: <http://www.openrdf.org/config/repository#>.
@prefix sr: <http://www.openrdf.org/config/repository/sail#>.
@prefix sail: <http://www.openrdf.org/config/sail#>.
@prefix graphdb: <http://www.ontotext.com/config/graphdb#>.
[] a rep:Repository ; rep:repositoryID "REPOSITORY" ; rdfs:label "Isolated projector test" ;
rep:repositoryImpl [ rep:repositoryType "graphdb:SailRepository" ; sr:sailImpl [
sail:sailType "graphdb:Sail" ; graphdb:ruleset "empty" ; graphdb:repository-type "file-repository" ;
graphdb:storage-folder "storage" ; graphdb:enable-context-index "true" ; ] ].'''


@pytest.fixture
async def graphdb(monkeypatch):
    url = os.getenv("ANNOTATIE_TEST_GRAPHDB_URL", "").rstrip("/")
    repository = "annotatie-test-" + uuid.uuid4().hex
    if not url:
        url = "http://graphdb-protocol-test"
        dataset = Dataset()
        real_client = httpx.AsyncClient
        async def engine(req):
            if "/rest/repositories" in req.url.path:
                return httpx.Response(201 if req.method == "POST" else 204, request=req)
            if req.method == "PUT" and req.url.path.endswith("/rdf-graphs/service"):
                graph = dataset.graph(URIRef(req.url.params["graph"]))
                graph.remove((None, None, None))
                graph.parse(data=req.content.decode(), format="turtle")
                return httpx.Response(204, request=req)
            data = parse_qs(req.content.decode())
            if "update" in data:
                dataset.update(data["update"][0])
                return httpx.Response(204, request=req)
            if "query" in data:
                result = dataset.query(data["query"][0])
                return httpx.Response(200, json=json.loads(result.serialize(format="json")), request=req)
            return httpx.Response(404, request=req)
        def client_factory(**kwargs):
            kwargs.setdefault("transport", httpx.MockTransport(engine))
            return real_client(**kwargs)
        monkeypatch.setattr(projection.httpx, "AsyncClient", client_factory)
    async with httpx.AsyncClient(timeout=45) as client:
        if os.getenv("ANNOTATIE_TEST_GRAPHDB_URL"):
            for attempt in range(45):
                try:
                    ready = await client.get(url + "/rest/repositories", timeout=2)
                    if ready.is_success:
                        break
                except httpx.HTTPError:
                    pass
                if attempt == 44:
                    pytest.fail("GraphDB is na 90 seconden nog niet gereed")
                await asyncio.sleep(2)
        response = await client.post(url + "/rest/repositories", files={
            "config": ("test.ttl", CONFIG.replace("REPOSITORY", repository), "text/turtle")})
        response.raise_for_status()
        monkeypatch.setenv("GRAPHDB_URL", url)
        monkeypatch.setenv("GRAPHDB_REPOSITORY", repository)
        get_settings.cache_clear()
        try:
            yield client, url + "/repositories/" + repository
        finally:
            response = await client.delete(url + "/rest/repositories/" + repository)
            response.raise_for_status()
            get_settings.cache_clear()


async def _marker(layer_id):
    async with db.get_engine().connect() as conn:
        return (await conn.execute(select(db.annotatie_v2_lagen.c.geprojecteerd_revisie).where(
            db.annotatie_v2_lagen.c.id == layer_id))).scalar_one()


async def test_partial_http_failure_retry_and_repository_recovery(graphdb, monkeypatch):
    client, repo = graphdb
    snap = snapshot(ONE)
    created = await store.batch(request(snap, [element(snap)]), snap, "a")
    layer_id, eid = created["lagen"][0]["id"], created["elementen"][0]["id"]
    assert await projection.projecteer(layer_id)
    assert (await projection.zoek_kandidaten({"jas_klassen": ["Rechtssubject"]}))["ids"] == [eid]
    await store.beslis(eid, Beslissing(type="approve", snapshot_id=snap["snapshot_id"],
                                      verwachte_revisies={ONE: 1}), snap, "b")
    real_client = httpx.AsyncClient
    async def fail_register(req):
        if req.url.path.endswith("/statements"):
            return httpx.Response(503, request=req)
        return await client.send(req)
    with monkeypatch.context() as patch:
        patch.setattr(projection.httpx, "AsyncClient", lambda **kw: real_client(
            **kw, transport=httpx.MockTransport(fail_register)))
        with pytest.raises(httpx.HTTPStatusError):
            await projection.projecteer(layer_id)
    assert await _marker(layer_id) == 1  # PUT succeeded, registry failed: no false acknowledgement
    partial = await projection.zoek_kandidaten({"lifecycle": ["human_approved"]})
    assert partial["ids"] == [] and layer_id not in partial["manifest"]
    assert await projection.projecteer(layer_id)
    assert await _marker(layer_id) == 2
    assert (await projection.zoek_kandidaten({"lifecycle": ["human_approved"]}))["ids"] == [eid]
    response = await client.post(repo + "/statements", data={"update": "CLEAR ALL"})
    response.raise_for_status()
    assert not (await projection.zoek_kandidaten({}))["beschikbaar"]
    assert await projection.reconcile() == 1  # actual graph loss, although DB marker still equals2
    assert (await projection.zoek_kandidaten({}))["ids"] == [eid]


async def test_orphans_removed_but_existing_and_foreign_graphs_preserved(graphdb):
    client, repo = graphdb
    snap = snapshot(ONE)
    created = await store.batch(request(snap, [element(snap)]), snap, "a")
    layer_id = created["lagen"][0]["id"]
    await projection.projecteer(layer_id)
    orphan = "orphan-" + uuid.uuid4().hex
    owner = projection.laag_iri(orphan).n3()
    graph = projection.graph_iri(orphan).n3()
    foreign = "urn:bwb:graph:protected-test-source"
    corrupt_id = "corrupt-" + uuid.uuid4().hex
    statement = f'''PREFIX jas: <urn:jas-ns:>
INSERT DATA {{ GRAPH {graph} {{ {owner} jas:revisie 1 }}
GRAPH <{foreign}> {{ <urn:test:source> jas:tekst "protected" }}
GRAPH <{projection.REGISTER}> {{
 {owner} jas:laagId {Literal(orphan).n3()} ; jas:inGraaf {graph} ; jas:revisie 1 .
 {projection.laag_iri(corrupt_id).n3()} jas:laagId {Literal(corrupt_id).n3()} ; jas:inGraaf <{foreign}> .
}} }}'''
    (await client.post(repo + "/statements", data={"update": statement})).raise_for_status()
    assert await projection.verwijder_verweesde_projecties() == 1
    assert await projection.verwijder_verweesde_projecties() == 0
    response = await client.post(repo, data={"query": f"ASK {{ GRAPH <{foreign}> {{ ?s ?p ?o }} }}"})
    assert response.json()["boolean"]
    response = await client.post(repo, data={"query": f"ASK {{ GRAPH {graph} {{ ?s ?p ?o }} }}"})
    assert not response.json()["boolean"]
    assert layer_id in (await projection.zoek_kandidaten({}))["manifest"]


async def test_projector_rowlock_keeps_concurrent_review_dirty(graphdb, monkeypatch):
    client, _ = graphdb
    snap = snapshot(ONE)
    created = await store.batch(request(snap, [element(snap)]), snap, "a")
    layer_id, eid = created["lagen"][0]["id"], created["elementen"][0]["id"]
    paused, resume = asyncio.Event(), asyncio.Event()
    real_client = httpx.AsyncClient
    async def pause_put(req):
        if req.method == "PUT":
            paused.set()
            await asyncio.wait_for(resume.wait(), 10)
        return await client.send(req)
    with monkeypatch.context() as patch:
        patch.setattr(projection.httpx, "AsyncClient", lambda **kw: real_client(
            **kw, transport=httpx.MockTransport(pause_put)))
        projecting = asyncio.create_task(projection.projecteer(layer_id))
        await asyncio.wait_for(paused.wait(), 10)
        reviewing = asyncio.create_task(store.beslis(eid, Beslissing(type="approve",
            snapshot_id=snap["snapshot_id"], verwachte_revisies={ONE: 1}), snap, "b"))
        await asyncio.sleep(0.05)
        assert not reviewing.done()  # DB rowlock, not the process-local projection lock
        resume.set()
        await asyncio.wait_for(asyncio.gather(projecting, reviewing), 15)
    layer = await store.laag_detail(layer_id)
    assert layer["revisie"] == 2 and layer["geprojecteerd_revisie"] < 2
    assert await projection.reconcile() == 1
    assert (await projection.zoek_kandidaten({"lifecycle": ["human_approved"]}))["ids"] == [eid]


async def test_commit_staat_direct_in_de_graaf_zonder_de_lus(graphdb):
    projection.activeer(True)
    try:
        snap = snapshot(ONE)
        created = await store.batch(request(snap, [element(snap)]), snap, "a")
        layer_id, eid = created["lagen"][0]["id"], created["elementen"][0]["id"]
        await asyncio.gather(*projection._taken)
        assert await _marker(layer_id) == 1
        assert (await projection.zoek_kandidaten({}))["ids"] == [eid]
        await store.beslis(eid, Beslissing(type="approve", snapshot_id=snap["snapshot_id"],
                                          verwachte_revisies={ONE: 1}), snap, "b")
        await asyncio.gather(*projection._taken)
        assert await _marker(layer_id) == 2
        assert (await projection.zoek_kandidaten({"lifecycle": ["human_approved"]}))["ids"] == [eid]
    finally:
        await projection.stop()
