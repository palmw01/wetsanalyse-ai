"""De begrippenrun (spoor D, levering 3a): manifest van de api → keten → uitkomst terug naar de api.

Drie dingen bewaakt deze suite:
1. de uitkomst heeft de vorm van het api-contract (`api/app/begrippen_run_contracts.py`), gelezen uit
   de bron zoals `test_contract_drift.py` dat doet;
2. op de referentieset levert de run precies de groepen van de keten, met een letterlijke definitie
   waar een lid de term van een begripsbepaling is;
3. het verloop tegen een nep-api: loopt → status per fase → uitkomst → opgeslagen → done, en elk
   faalpad meldt de api `mislukt` en geeft een `error` in plaats van een stille afloop.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx
import pytest

from agent import begrippen_run
from agent.begrippen_pipeline.keten import analyseer
from agent.begrippen_run import manifest_uit, naar_uitkomst
from agent.jas_pipeline.taal.provider import NullProvider
from agent.runstore import Run
from eval.begrippen_eval import manifest_uit as eval_manifest
from fakes import make_settings
from test_contract_drift import _api_velden

SETS = Path(__file__).resolve().parents[3] / "docs" / "wetsanalyse" / "referentieset-begrippen"
CONTRACT = Path(__file__).resolve().parents[3] / "api" / "app" / "begrippen_run_contracts.py"


def _v1():
    d = SETS / "v1"
    return eval_manifest(json.loads((d / "bronnen.json").read_text()), json.loads((d / "cases.json").read_text()))


def _als_api(manifest) -> dict:
    """Het manifest zoals de api het meegeeft (`GET …?manifest=true`)."""
    return {"bronnen": [b.model_dump() for b in manifest.bronnen],
            "formuleringen": [f.model_dump() for f in manifest.formuleringen]}


# --- 1. het contract -----------------------------------------------------------------------------

def test_de_uitkomst_heeft_de_velden_van_het_api_contract():
    m = _v1()
    uit = naar_uitkomst(m, analyseer(m, NullProvider()))
    assert set(uit) <= set(_api_velden("UitkomstInvoer", CONTRACT))
    paren = [("UitkomstGroep", uit["groepen"]), ("UitkomstRelatie", uit["relaties"]), ("UitkomstVraag", uit["vragen"])]
    for klasse, rijen in paren:
        velden = set(_api_velden(klasse, CONTRACT))
        for rij in rijen:
            assert set(rij) <= velden, (klasse, set(rij) - velden)
    for g in uit["groepen"]:
        assert re.fullmatch(r"G[0-9a-f]{6,64}", g["id"]) and len(g["leden"]) >= 2
        assert set(g["voorstel"]) <= set(_api_velden("Voorstel", CONTRACT)) and g["voorstel"]["naam"]


def test_het_manifest_van_de_api_is_een_manifest_van_de_keten():
    m = _v1()
    assert manifest_uit(_als_api(m)).id == m.id


# --- 2. de inhoud ----------------------------------------------------------------------------------

def test_op_de_referentieset_dezelfde_groepen_als_de_keten_met_een_letterlijke_definitie():
    pytest.importorskip("spacy")
    from agent.jas_pipeline.taal.provider import SpacyProvider
    try:
        provider = SpacyProvider()
    except Exception:  # noqa: BLE001 – geen model geïnstalleerd
        pytest.skip("spaCy-model ontbreekt")
    m = _v1()
    keten = analyseer(m, provider)
    uit = naar_uitkomst(m, keten)
    assert [g["leden"] for g in uit["groepen"]] == [list(g.leden) for g in keten.groepen]
    assert uit["manifest_id"] == m.id
    met_definitie = [g for g in uit["groepen"] if g["voorstel"].get("definitie")]
    assert met_definitie, "minstens één groep draagt de letterlijke definitie van een begripsbepaling"
    for g in met_definitie:
        bron = m.bron(g["voorstel"]["definitie_bron_iri"])
        assert g["voorstel"]["definitie"] in bron.tekst                    # letterlijk, geen herformulering
        assert g["voorstel"]["definitie_vindplaats"] == bron.label


# --- 3. het verloop tegen een nep-api -------------------------------------------------------------

class NepApi:
    def __init__(self, manifest: dict, weiger_uitkomst: bool = False):
        self.manifest, self.weiger = manifest, weiger_uitkomst
        self.aanroepen: list[tuple[str, str]] = []
        self.uitkomst: dict | None = None
        self.mislukt: str | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        pad = request.url.path
        self.aanroepen.append((request.method, pad.rsplit("/", 1)[-1]))
        if request.method == "GET":
            return httpx.Response(200, json={"id": "r1", "manifest_id": "M", "manifest": self.manifest})
        if pad.endswith("/loopt"):
            return httpx.Response(200, json={})
        if pad.endswith("/uitkomst"):
            if self.weiger:
                return httpx.Response(422, json={"detail": {"fout": "onbekend_element", "melding": "nee"}})
            self.uitkomst = json.loads(request.content)
            return httpx.Response(200, json={"status": "klaar"})
        if pad.endswith("/mislukt"):
            self.mislukt = json.loads(request.content)["reden"]
            return httpx.Response(200, json={})
        return httpx.Response(404)


@pytest.fixture
def nep(monkeypatch):
    def maak(manifest: dict, **kw) -> NepApi:
        api = NepApi(manifest, **kw)
        echte = begrippen_run.WetsanalyseApi

        class MetTransport(echte):
            def __init__(self, settings, user_id):
                super().__init__(settings, user_id)
                self._client = httpx.AsyncClient(transport=httpx.MockTransport(api))

        monkeypatch.setattr(begrippen_run, "WetsanalyseApi", MetTransport)
        return api
    return maak


def _settings():
    return make_settings(wetsanalyse_api_url="http://api.test", wetsanalyse_api_token="t", qa_api_token="q")


def _events(run: Run) -> list[dict]:
    async def verzamel() -> list[dict]:
        return [e async for e in begrippen_run.begrippen_stroom("wg1", "r1", run, settings=_settings(),
                                                                user_id="jurist", provider=NullProvider())]
    return asyncio.run(verzamel())


def test_het_verloop_van_manifest_tot_opgeslagen(nep):
    api = nep(_als_api(_v1()))
    events = _events(Run(run_id="x", conversation_id="werkgebied:wg1"))
    soorten = [e["type"] for e in events]
    assert soorten[0] == "status" and soorten[-2:] == ["opgeslagen", "done"]
    assert any("Groeperen" in e.get("message", "") for e in events)           # de fasen van de keten
    assert [a for a in api.aanroepen] == [("GET", "r1"), ("POST", "loopt"), ("PUT", "uitkomst")]
    assert api.uitkomst["manifest_id"] == _v1().id and api.mislukt is None


def test_een_geweigerde_uitkomst_is_een_zichtbare_fout(nep):
    api = nep(_als_api(_v1()), weiger_uitkomst=True)
    events = _events(Run(run_id="x", conversation_id="werkgebied:wg1"))
    assert events[-1]["type"] == "error" and events[-1]["soort"] == "api"
    assert api.mislukt and "422" in api.mislukt


def test_een_ongeldig_manifest_meldt_mislukt(nep):
    kapot = _als_api(_v1())
    kapot["formuleringen"][0] = {**kapot["formuleringen"][0], "tekst": "staat er niet"}
    api = nep(kapot)
    events = _events(Run(run_id="x", conversation_id="werkgebied:wg1"))
    assert events[-1] == {"type": "error", "message": "Het manifest van dit werkgebied is ongeldig voor de keten.",
                          "soort": "manifest"}
    assert api.mislukt.startswith("Ongeldig manifest")


def test_stoppen_voor_de_keten_schrijft_niets(nep):
    api = nep(_als_api(_v1()))
    run = Run(run_id="x", conversation_id="werkgebied:wg1")
    run.stop_gevraagd = True
    events = _events(run)
    assert events[-1] == {"type": "done"} and api.uitkomst is None and api.mislukt == "Gestopt op verzoek."


# --- het endpoint ---------------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    import api.main as main

    async def langzaam(werkgebied_id, run_id, run, **_kw):
        await asyncio.sleep(0.3)
        yield {"type": "done"}

    monkeypatch.setattr(main.settings, "graphdb_token", "test", raising=False)
    monkeypatch.setattr(main.settings, "graphdb_mcp_url", "https://graaf.test/mcp", raising=False)
    monkeypatch.setattr(main, "begrippen_stroom", langzaam)
    monkeypatch.setattr(main, "runs", type(main.runs)())
    with TestClient(main.app) as c:
        yield c, main


def test_zonder_api_geen_begrippenrun(client, monkeypatch):
    c, main = client
    monkeypatch.setattr(type(main.settings), "legt_zelf_vast", property(lambda _s: False))
    assert c.post("/v1/begrippen-runs", json={"werkgebied_id": "wg1", "run_id": "r1"}).status_code == 503


def test_een_begrippenrun_per_werkgebied_tegelijk(client, monkeypatch):
    c, main = client
    monkeypatch.setattr(type(main.settings), "legt_zelf_vast", property(lambda _s: True))
    assert c.post("/v1/begrippen-runs", json={"werkgebied_id": "../x", "run_id": "r1"}).status_code == 422
    eerste = c.post("/v1/begrippen-runs", json={"werkgebied_id": "wg1", "run_id": "r1"})
    assert eerste.status_code == 201 and eerste.json()["conversation_id"] == "werkgebied:wg1"
    tweede = c.post("/v1/begrippen-runs", json={"werkgebied_id": "wg1", "run_id": "r2"})
    assert tweede.status_code == 409 and tweede.json()["detail"]["run_id"] == eerste.json()["run_id"]
    # Een ander werkgebied mag tegelijk.
    assert c.post("/v1/begrippen-runs", json={"werkgebied_id": "wg2", "run_id": "r3"}).status_code == 201
