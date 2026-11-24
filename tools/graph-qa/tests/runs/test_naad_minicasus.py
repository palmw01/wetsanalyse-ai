"""De naadtoets: de batch die graph-qa naar de api stuurt, als gedeeld voorbeeld (Lex Bench §20.5 stap 5, testplan
keten-e2e §3 punt 5).

Het routecontract bewaakt pad en methode, niet de vorm van wat er overgaat. Hier loopt de echte annotatieketen (met een
gescript model en een nepgraaf) door de echte driver (`voer_beurt_uit`) en de echte api-client, met alleen het netwerk
vervangen. Wat over de draad gaat, en de bronsnapshot die graph-qa daarbij bouwde, staan in
`tests/poort/data/naad_minicasus.json`; `api/tests/test_naad_minicasus.py` neemt precies dat voorbeeld als invoer voor de
keten in de api (opnemen, werkvoorraad, batch, beslissing, projectie, begrip, export). Verandert de vorm aan deze kant,
dan faalt deze test; werk het voorbeeld dan bewust bij met `NAAD_OPNEMEN=1` en laat de api-test zeggen of het past.

De taalanalyse staat vast op de provider zonder model (`null`). De naad gaat over de vorm tussen graph-qa en de api, niet
over de zinsontleding, en de poort heeft het spaCy-model niet: met het model erbij zou het voorbeeld lokaal anders zijn
dan in CI.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest

from agent.runstore import Run
from bron_fakes import bronrijen
from bronmodel import bouw_snapshot
from fakes import make_settings
from test_gedeelde_laag import ARTIKEL_TSV, _events

pytestmark = pytest.mark.risico("R21", laag=2)

VOORBEELD = Path(__file__).resolve().parents[4] / "tests" / "poort" / "data" / "naad_minicasus.json"
#: Wat per run verschilt en dus niet in het voorbeeld hoort.
VLUCHTIG = {"batch_id", "run", "beslisregister"}


@pytest.fixture(autouse=True)
def _zonder_taalmodel(monkeypatch):
    from agent.jas_pipeline import keten
    from agent.jas_pipeline.taal import maak_provider

    monkeypatch.setattr(keten, "_provider", lambda _spec: maak_provider("null"))


def _gestript(batch: dict) -> dict:
    return {k: v for k, v in batch.items() if k not in VLUCHTIG}


def _verstuurd() -> tuple[dict, dict]:
    """(de batch zoals de client hem verstuurt, de bronsnapshot van de beurt)."""
    from agent import beurt
    from agent.beurt import voer_beurt_uit
    from agent.wetsanalyse_api import WetsanalyseApi

    verstuurd: list[dict] = []

    def api(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/v1/annotatie/lagen/batch":
            verstuurd.append(json.loads(req.content))
            return httpx.Response(200, json={"lagen": [], "elementen": []})
        return httpx.Response(200, json={"id": 1})

    settings = make_settings(wetsanalyse_api_url="http://api:3000", wetsanalyse_api_token="t", qa_api_token="q")
    echt = beurt.WetsanalyseApi

    def client(*a, **k):
        c = WetsanalyseApi(*a, **k)
        c._client = httpx.AsyncClient(transport=httpx.MockTransport(api))
        return c

    events = _events()

    async def draai():
        async def stroom():
            for e in events:
                yield e
        beurt.WetsanalyseApi = client
        try:
            return [e async for e in voer_beurt_uit(stroom(), settings=settings, run=Run(run_id="r1", conversation_id="g1",
                                                                                       vraag="v"),
                                                    gesprek_id="g1", user_id="jurist")]
        finally:
            beurt.WetsanalyseApi = echt

    asyncio.run(draai())
    assert len(verstuurd) == 1, "de beurt stuurde geen of meer dan één batch"
    doel = next(e["doel"] for e in events if e["type"] == "doel")
    # Dezelfde bronrijen als de keten las (`bron_fakes.BronGraph`), en de snapshot die bronmodel daaruit bouwt.
    rijen = bronrijen(ARTIKEL_TSV, doel)
    snapshot = {"bronrijen": rijen, "snapshot_id": bouw_snapshot(
        rijen, bwb_id=doel["bwbId"], artikel=doel["artikel"], lid=doel.get("lid") or "")["snapshot_id"],
        "doel": {"bwb_id": doel["bwbId"], "artikel": doel["artikel"], "lid": doel.get("lid") or ""}}
    return verstuurd[0], snapshot


def test_de_batch_van_graph_qa_is_het_gedeelde_voorbeeld():
    batch, snapshot = _verstuurd()
    nu = {"snapshot": snapshot, "batch": _gestript(batch)}
    if os.environ.get("NAAD_OPNEMEN"):
        VOORBEELD.write_text(json.dumps(nu, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert VOORBEELD.exists(), "het gedeelde voorbeeld ontbreekt: draai met NAAD_OPNEMEN=1"
    assert json.loads(VOORBEELD.read_text(encoding="utf-8")) == json.loads(json.dumps(nu, sort_keys=True)), (
        "de batch of de snapshot van graph-qa veranderde: werk het voorbeeld bewust bij met NAAD_OPNEMEN=1, en draai "
        "api/tests/test_naad_minicasus.py")


def test_de_batch_draagt_wat_de_api_nodig_heeft():
    """Wat de volgende stap verwacht: ids van de bronnode, de snapshot van de beurt, en per element ankers op lidniveau."""
    batch, snapshot = _verstuurd()
    assert batch["snapshot_id"] == snapshot["snapshot_id"], "de batch hoort bij de snapshot die graph-qa las"
    assert batch["elementen"], "geen elementen: dan toetst de naad niets"
    for e in batch["elementen"]:
        assert e["ankers"] and all(":lid:" in a["bron_iri"] and a["bron_hash"] for a in e["ankers"])
        assert e.get("aandacht") in (None, "groen", "geel"), "naar_contract vertaalt een leeg oordeel naar None"
