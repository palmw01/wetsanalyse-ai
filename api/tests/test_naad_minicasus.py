"""De naadtoets: één vaste minicasus door de echte overgangen van de api, met de batch die graph-qa echt verstuurt
(Lex Bench §20.5 stap 5, testplan keten-e2e §3 punt 5).

Het voorbeeld `tests/poort/data/naad_minicasus.json` maakt `tools/graph-qa/tests/test_naad_minicasus.py` uit de echte
annotatieketen en de echte api-client: de bronrijen die graph-qa las en de batch zoals hij over de draad gaat. Hier bouwt
de api met zijn eigen `snapshot_uit` de snapshot uit dezelfde rijen, en neemt hij de batch aan. Elke stap toetst wat de
volgende verwacht (ids, lidniveau, ankers):

opnemen in het werkgebied → de werkvoorraad → de batch van graph-qa → een beslissing → de projectie naar de graaf
(rdflib) → een begrip op de markering → de Turtle-export.

Zonder model en zonder graaf. Dit is de dynamische tegenhanger van het routecontract: dat ziet pad en methode, dit de
vorm van wat er overgaat.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from rdflib import Dataset, Literal

from app import annotatie_v2, bron_resolver, db
from app import graaf as graafmodule
from app import graaf_projectie_v2 as projectie
from test_werkgebieden import client, database  # noqa: F401

pytestmark = pytest.mark.risico("R21", laag=2)

VOORBEELD = json.loads((Path(__file__).resolve().parents[2] / "tests" / "poort" / "data" / "naad_minicasus.json")
                       .read_text(encoding="utf-8"))
RIJEN = VOORBEELD["snapshot"]["bronrijen"]
BATCH = VOORBEELD["batch"]
LID = BATCH["elementen"][0]["ankers"][0]["bron_iri"]


@pytest.fixture
def graaf(monkeypatch):
    """De graaf van de api geeft de bronrijen van het voorbeeld; de api bouwt er zelf de snapshot uit."""
    async def rijen(_bwb):
        return [dict(r) for r in RIJEN]

    async def leeg(*_a, **_k):
        return []

    for module in (bron_resolver, annotatie_v2, graafmodule):
        if hasattr(module, "haal_bronrijen"):
            monkeypatch.setattr(module, "haal_bronrijen", rijen)
    monkeypatch.setattr(graafmodule, "sparql_select", leeg)
    from app import werkgebieden
    monkeypatch.setattr(werkgebieden, "_resolve_bron", bron_resolver.resolve_bron)


async def test_de_minicasus_loopt_door_elke_naad_van_de_api(client, graaf):  # noqa: F811
    # 1. Opnemen: de bron op lidniveau in een werkgebied.
    r = await client.post("/v1/werkgebieden", json={"naam": "Naadtoets", "analysevraag": "Wie kan uitstel verlenen?"})
    assert r.status_code == 201, r.text
    wg = r.json()
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/bronnen", json={"verwachte_revisie": wg["revisie"], "bron_iri": LID})
    assert r.status_code in (200, 201), r.text
    antwoord = r.json()
    wg = antwoord.get("werkgebied", antwoord)
    assert any(b["bron_iri"] == LID for b in wg["bronnen"]), "de bron staat op lidniveau in het werkgebied"

    # 2. De werkvoorraad noemt precies die bron.
    r = await client.get(f"/v1/werkgebieden/{wg['id']}/annotatie-werkvoorraad")
    assert r.status_code == 200, r.text
    voorraad = r.json()
    assert LID in json.dumps(voorraad), "de werkvoorraad noemt de opgenomen bepaling"

    # 3. De batch van graph-qa: de api bouwt dezelfde snapshot uit dezelfde rijen, en neemt hem aan.
    r = await client.post("/v1/annotatie/lagen/batch", json={**BATCH, "batch_id": "naad-1", "run": {"pijplijn": "hybrid_v1"}})
    assert r.status_code == 200, f"de api weigert de batch van graph-qa: {r.text}"
    r = await client.get("/v1/annotatie/weergave", params={"bron_iri": LID})
    assert r.status_code == 200, r.text
    weergave = r.json()
    assert weergave["snapshot_id"] == BATCH["snapshot_id"], "api en graph-qa leiden dezelfde snapshot af"
    element = next(e for e in weergave["elementen"] if e["tekst"] == BATCH["elementen"][0]["tekst"])
    assert element["ankers"][0]["bron_iri"] == LID and element["ankers"][0]["start"] == BATCH["elementen"][0]["ankers"][0]["start"]

    # 4. Een beslissing op dat element.
    revisies = {laag["bron_iri"]: laag["revisie"] for laag in weergave["lagen"]}
    r = await client.post(f"/v1/annotatie/elementen/{element['id']}/beslissing",
                          json={"type": "approve", "verwachte_revisies": revisies, "snapshot_id": weergave["snapshot_id"]})
    assert r.status_code == 200, r.text

    # 5. De projectie: de laag als named graph, vindbaar op de tekst van de markering.
    async with db.get_engine().connect() as conn:
        lagen = (await conn.execute(db.annotatie_v2_lagen.select())).mappings().all()
    assert lagen, "geen laag vastgelegd"
    ds = Dataset()
    for laag in lagen:
        r = await client.get("/v1/annotatie/weergave", params={"bron_iri": laag["bron_iri"]})
        elementen = [e for e in r.json()["elementen"] if e.get("laag_id", laag["id"]) == laag["id"]]
        g = ds.graph(projectie.graph_iri(laag["id"]))
        for triple in projectie.bouw_graaf(dict(laag), elementen):
            g.add(triple)
        ds.graph(projectie.REGISTER).add((projectie.laag_iri(laag["id"]), projectie.JAS.inGraaf, g.identifier))
        ds.graph(projectie.REGISTER).add((projectie.laag_iri(laag["id"]), projectie.JAS.revisie, Literal(laag["revisie"])))
    ds.graph(projectie.REGISTER).add((projectie.SCHEMA, projectie.JAS.versie, Literal(projectie.SCHEMA_VERSIE)))
    gevonden = [str(rij.id) for rij in ds.query(projectie.zoek_query({"tekst": element["tekst"], "match": "exact",
                                                                       "tekstveld": "citaat"}))]
    assert element["id"] in gevonden, "de markering is niet vindbaar in de geprojecteerde graaf"

    # 6. Een begrip op de markering.
    r = await client.post(f"/v1/werkgebieden/{wg['id']}/begrippen",
                          json={"inhoud": {"naam": "ontvanger"}, "element_ids": [element["id"]], "rol": "duiding"})
    assert r.status_code == 201, r.text
    begrip = r.json()

    # 7. De Turtle-export noemt het begrip.
    r = await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen/export", params={"formaat": "ttl", "inclusief": "alle"})
    assert r.status_code == 200, r.text
    assert "ontvanger" in r.text and begrip["id"] in r.text, "het begrip staat niet in de export"
