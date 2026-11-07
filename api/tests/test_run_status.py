"""De statusmachine van de runs (`app/runs.py`): een klare run verandert niet meer (AS-B2).

Vroeger lazen `loopt` en `mislukt` eerst de status en schreven daarna. Kwam de uitkomst daartussen, dan maakte een late
`loopt` of `mislukt` van een klare run weer een lopende of mislukte. Nu is het één conditionele UPDATE."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app import bronnen_run_store, db, runs
from test_annotatie_v2 import ART
from test_bronnen_runs import _k, _start, _uitkomst
from test_werkgebieden import ART2, _bron, _nieuw, client, database, graaf  # noqa: F401


async def _klare_run(client) -> tuple[dict, dict]:
    wg = (await _bron(client, await _nieuw(client), bron_iri=ART))["werkgebied"]
    run = await _start(client, wg, 201)
    r = await _uitkomst(client, wg, run, [_k(ART2, "afhankelijkheid", ("definitie", ""))])
    assert r.json()["status"] == "klaar", r.text
    return wg, run


async def _status(run_id: str) -> str:
    async with db.get_engine().connect() as conn:
        return (await conn.execute(select(db.bronnen_runs.c.status).where(db.bronnen_runs.c.id == run_id))).scalar()


async def test_een_klare_run_blijft_klaar(client):
    _, run = await _klare_run(client)
    assert await runs.zet_loopt(db.bronnen_runs, run["id"]) is False
    with pytest.raises(HTTPException) as e:
        await runs.zet_mislukt(db.bronnen_runs, run["id"], "te laat")
    assert e.value.status_code == 409
    assert await _status(run["id"]) == "klaar"


async def test_een_late_melding_na_een_oude_lezing_overschrijft_niets(client, monkeypatch):
    """De race zelf: de store las de run nog als lopend, maar intussen kwam de uitkomst."""
    wg, run = await _klare_run(client)
    echt = bronnen_run_store.haal

    async def oud(werkgebied_id, run_id, met_invoer=False):
        return {**await echt(werkgebied_id, run_id, met_invoer), "status": "loopt"}
    monkeypatch.setattr(bronnen_run_store, "haal", oud)
    with pytest.raises(HTTPException) as e:
        await bronnen_run_store.mislukt(wg["id"], run["id"], "te laat")
    assert e.value.status_code == 409
    await bronnen_run_store.loopt(wg["id"], run["id"])
    assert await _status(run["id"]) == "klaar"


async def test_loopt_en_mislukt_over_http(client):
    wg, run = await _klare_run(client)
    base = f"/v1/werkgebieden/{wg['id']}/bronnen-runs/{run['id']}"
    assert (await client.post(f"{base}/loopt")).json()["status"] == "klaar"
    assert (await client.post(f"{base}/mislukt", json={"reden": "x"})).status_code == 409
    nieuw = (await _bron(client, (await client.get(f"/v1/werkgebieden/{wg['id']}")).json(), bron_iri=ART2,
                         rol="context"))["werkgebied"]
    run2 = await _start(client, nieuw, 201)
    base2 = f"/v1/werkgebieden/{wg['id']}/bronnen-runs/{run2['id']}"
    assert (await client.post(f"{base2}/loopt")).json()["status"] == "loopt"
    r = (await client.post(f"{base2}/mislukt", json={"reden": "spaCy ontbreekt"})).json()
    assert (r["status"], r["reden"]) == ("mislukt", "spaCy ontbreekt")
