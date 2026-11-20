"""L-1-2 (met M-1-1): een contextbron waarnaar een beoordeelde relatie wijst, staat als signaal in de dekking van het
werkgebied. De rol van de bron verandert niet vanzelf; de jurist beslist."""
from __future__ import annotations

from app import annotatie_v2_relaties as rel, annotatie_v2_store as store
from app.annotatie_v2_contracts import RelatieBeslissing, RelatieInvoer
from gedeelde_bron import ART, ART2, ONE, _bron, _nieuw, client, database, element, graaf, request, snapshot  # noqa: F401


async def test_een_beoordeelde_relatie_naar_een_contextbron_is_een_signaal(client):
    snap = snapshot()
    uit = await store.batch(request(snap, [{**element(snap, ONE, 2, 6), "klasse": "Rechtsbetrekking"}]), snap, "lex")
    eid = uit["elementen"][0]["id"]
    wg = await _nieuw(client)
    wg = (await _bron(client, wg, bron_iri=ART))["werkgebied"]
    wg = (await _bron(client, wg, bron_iri=ART2, rol="context"))["werkgebied"]
    dekking = f"/v1/werkgebieden/{wg['id']}/deelvragen/dekking"
    assert (await client.get(dekking)).json()["contextsignalen"] == []

    revisie = (await store.weergave(snap))["lagen"][0]["revisie"]
    gelegd = await rel.leg(RelatieInvoer(van={"soort": "element", "id": eid}, naar={"soort": "bron", "id": ART2},
                                         type="uitzondering_op", verwachte_revisies={ONE: revisie}), "jurist")
    [signaal] = (await client.get(dekking)).json()["contextsignalen"]
    assert signaal["bron_iri"] == ART2 and [r["id"] for r in signaal["relaties"]] == [gelegd["relatie"]["id"]]
    assert signaal["melding"].endswith("Wordt dit een bron om te analyseren?")

    # Een afgewezen relatie telt niet: alleen wat een jurist vastlegde of goedkeurde.
    laag = gelegd["laag"]
    await rel.beslis(gelegd["relatie"]["id"], RelatieBeslissing(type="reject", verwachte_revisies={ONE: laag["revisie"]}),
                     "jurist")
    assert (await client.get(dekking)).json()["contextsignalen"] == []
