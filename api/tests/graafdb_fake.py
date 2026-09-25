"""Een GraphDB-protocol op een rdflib-`Dataset`, voor tests zonder GraphDB.

Bedient wat de api gebruikt: `PUT`/`GET …/rdf-graphs/service?graph=…` (graph-store-protocol) en
`POST …/repositories/<repo>` met `query` of `…/statements` met `update`. Zelfde aanpak als de
adapter in `test_projector_v2_integration.py`, maar herbruikbaar en zonder repository-beheer.

Gebruik: `ds = installeer(monkeypatch)`; daarna praten `graaf_projectie_v2` en `graafcontrole` via
`httpx.AsyncClient` met deze dataset. `storing(True)` laat elk verzoek met 503 falen.
"""
from __future__ import annotations

import json
from urllib.parse import parse_qs

import httpx
from rdflib import Dataset, URIRef

URL = "http://graphdb-test"


class NepGraphDB:
    def __init__(self) -> None:
        self.ds = Dataset()
        self.plat = False

    def storing(self, aan: bool = True) -> None:
        self.plat = aan

    async def __call__(self, req: httpx.Request) -> httpx.Response:
        if self.plat:
            return httpx.Response(503, request=req)
        if req.url.path.endswith("/rdf-graphs/service"):
            graph = self.ds.graph(URIRef(req.url.params["graph"]))
            if req.method == "PUT":
                graph.remove((None, None, None))
                graph.parse(data=req.content.decode(), format="turtle")
                return httpx.Response(204, request=req)
            if not len(graph):
                return httpx.Response(404, request=req)
            return httpx.Response(200, text=graph.serialize(format="turtle"), request=req,
                                  headers={"Content-Type": "text/turtle"})
        data = parse_qs(req.content.decode())
        if "update" in data:
            self.ds.update(data["update"][0])
            return httpx.Response(204, request=req)
        if "query" in data:
            result = self.ds.query(data["query"][0])
            return httpx.Response(200, json=json.loads(result.serialize(format="json")), request=req)
        return httpx.Response(404, request=req)


def installeer(monkeypatch) -> NepGraphDB:
    from app.config import get_settings

    nep = NepGraphDB()
    echte = httpx.AsyncClient

    def fabriek(**kwargs):
        kwargs.setdefault("transport", httpx.MockTransport(nep))
        return echte(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", fabriek)
    monkeypatch.setenv("GRAPHDB_URL", URL)
    monkeypatch.setenv("GRAPHDB_REPOSITORY", "test")
    get_settings.cache_clear()
    return nep
