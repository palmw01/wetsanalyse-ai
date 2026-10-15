"""De begrippenroute in het gesprek (spoor D, fase AF2): "stel begrippen voor" binnen een werkgebied.

Bewaakt:
1. welke vragen de route ingaan – en dat "wat betekent het begrip X?" dat niet doet;
2. het verloop tegen een nep-api: werkgebied → run (nieuw, al klaar of al lopend) → keten → bericht
   met een begrippenartefact → `opgeslagen` met hetzelfde artefact → `done`;
3. een weigering van de api is een antwoord van Lex (bewaard, zonder artefact), geen storing;
4. het artefact heeft de vorm van `api/app/gesprek_contracts.Artefact` en het request-model de regels.
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from agent import begrippen_beurt, begrippen_run
from agent.begrippen_beurt import begrippen_artefact, is_begrippenvraag, samenvatting
from agent.jas_pipeline.taal.provider import NullProvider
from agent.models import ChatRequest
from agent.runstore import Run
from fakes import make_settings
from test_begrippen_run import _als_api, _v1


@pytest.mark.parametrize("vraag", ["Stel begrippen voor", "welke begrippen zitten in dit werkgebied?",
                                   "Maak de begrippen", "Kun je begrippen voorstellen?"])
def test_vragen_om_begrippen(vraag):
    assert is_begrippenvraag(vraag)


@pytest.mark.parametrize("vraag", ["Wat betekent het begrip 'belastingschuldige'?", "Annoteer artikel 9",
                                   "Begrippen", "Hoe verhouden de begrippen zich tot de wet"])
def test_geen_vraag_om_begrippen(vraag):
    assert not is_begrippenvraag(vraag)


def test_het_request_model():
    assert ChatRequest(question="Stel begrippen voor", werkgebied_id="wg1").is_begrippenbeurt
    assert ChatRequest(question="iets anders", werkgebied_id="wg1", modus="begrippen").is_begrippenbeurt
    # Zonder werkgebied gewoon een vraag, en met een werkgebied blijft een andere vraag een gewone beurt.
    assert not ChatRequest(question="Stel begrippen voor").is_begrippenbeurt
    assert not ChatRequest(question="Wat regelt artikel 9?", werkgebied_id="wg1").is_begrippenbeurt
    with pytest.raises(ValueError):
        ChatRequest(question="x", modus="begrippen")
    with pytest.raises(ValueError):
        ChatRequest(question="x", werkgebied_id="../wg")


def test_het_artefact_past_in_het_gesprekscontract():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "api"))
    try:
        from app.gesprek_contracts import Artefact
    except ImportError:
        pytest.skip("api-pakket niet importeerbaar in deze omgeving")
    finally:
        sys.path.pop(0)
    a = Artefact(**begrippen_artefact("wg1", "r1", "Invordering"))
    assert a.soort == "begrippen" and a.ref == {"werkgebied_id": "wg1", "run_id": "r1"}


def test_de_samenvatting_noemt_de_getallen():
    assert "**3** begrippen" in samenvatting("Inv", 3, 10, 0, al_gerekend=False)
    assert "**1** begrip " in samenvatting("Inv", 1, 2, 2, al_gerekend=False)
    assert "2 twijfelpunten" in samenvatting("Inv", 1, 2, 2, al_gerekend=False)
    assert "al gerekend" in samenvatting("Inv", 0, 2, 0, al_gerekend=True)


# --- het verloop tegen een nep-api ----------------------------------------------------------------

class NepApi:
    def __init__(self, run_status: str = "wacht", weiger: tuple[int, dict] | None = None):
        self.run_status, self.weiger = run_status, weiger
        self.manifest = _als_api(_v1())
        self.aanroepen: list[tuple[str, str]] = []
        self.berichten: list[dict] = []
        self.uitkomst: dict | None = None
        self.peilingen = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        pad, m = request.url.path, request.method
        self.aanroepen.append((m, pad))
        if pad == "/v1/werkgebieden/wg1" and m == "GET":
            return httpx.Response(200, json={"id": "wg1", "naam": "Invordering"})
        if pad == "/v1/werkgebieden/wg1/begrippen-runs" and m == "POST":
            if self.weiger:
                return httpx.Response(self.weiger[0], json={"detail": self.weiger[1]})
            return httpx.Response(200, json={"id": "r1", "status": self.run_status, "aantal_formuleringen": 10,
                                             "nieuw": self.run_status == "wacht"})
        if pad.endswith("/begrippen-runs/r1") and m == "GET":
            self.peilingen += 1
            return httpx.Response(200, json={"id": "r1", "status": "klaar" if self.peilingen > 1 else "loopt",
                                             "manifest_id": "M", "manifest": self.manifest})
        if pad.endswith("/loopt"):
            return httpx.Response(200, json={})
        if pad.endswith("/uitkomst"):
            self.uitkomst = json.loads(request.content)
            return httpx.Response(200, json={"status": "klaar"})
        if pad.endswith("/groepen"):
            groepen = [{"id": "G1", "besluit": "open"}, {"id": "G2", "besluit": "open"}, {"id": "G3", "besluit": "afgewezen"}]
            return httpx.Response(200, json={"run": {"uitkomst": {"vragen": [{"kandidaat_id": "P1"}]}}, "groepen": groepen})
        if pad == "/v1/gesprekken/g1/berichten":
            self.berichten.append(json.loads(request.content))
            return httpx.Response(201, json={"id": 1})
        if pad.startswith("/v1/gesprekken/"):
            return httpx.Response(404)
        return httpx.Response(500)


@pytest.fixture
def nep(monkeypatch):
    def maak(**kw) -> NepApi:
        api = NepApi(**kw)
        echte = begrippen_beurt.WetsanalyseApi

        class MetTransport(echte):
            def __init__(self, settings, user_id):
                super().__init__(settings, user_id)
                self._client = httpx.AsyncClient(transport=httpx.MockTransport(api))

        monkeypatch.setattr(begrippen_beurt, "WetsanalyseApi", MetTransport)
        monkeypatch.setattr(begrippen_run, "WetsanalyseApi", MetTransport)
        monkeypatch.setattr(begrippen_beurt, "PEIL_S", 0.0)
        return api
    return maak


def _events(gesprek: str = "g1", run: Run | None = None) -> list[dict]:
    request = ChatRequest(question="Stel begrippen voor", conversation_id=gesprek, werkgebied_id="wg1")
    run = run or Run(run_id="beurt1", conversation_id=gesprek)
    settings = make_settings(wetsanalyse_api_url="http://api.test", wetsanalyse_api_token="t", qa_api_token="q")

    async def verzamel() -> list[dict]:
        return [e async for e in begrippen_beurt.begrippen_beurt(request, run, settings=settings, user_id="jurist",
                                                                  provider=NullProvider())]
    return asyncio.run(verzamel())


def test_een_nieuwe_run_rekent_en_legt_een_begrippenartefact_vast(nep):
    api = nep()
    events = _events()
    soorten = [e["type"] for e in events]
    assert soorten[-3:] == ["token", "opgeslagen", "done"] and "status" in soorten
    assert any("Groeperen" in e.get("message", "") for e in events)      # de fasen van de keten, live
    artefact = {"soort": "begrippen", "titel": "Invordering", "ref": {"werkgebied_id": "wg1", "run_id": "r1"}}
    assert events[-2] == {"type": "opgeslagen", "run_id": "beurt1", "artefact": artefact}
    assert api.uitkomst is not None
    [bericht] = api.berichten
    assert bericht["artefact"] == artefact and bericht["run_id"] == "beurt1" and bericht["rol"] == "assistant"
    assert "**2** begrippen" in bericht["tekst"] and "1 twijfelpunt " in bericht["tekst"]
    assert "Groeperen" in bericht["denk"]


def test_al_klaar_op_deze_stand_rekent_niet_opnieuw(nep):
    api = nep(run_status="klaar")
    events = _events()
    assert api.uitkomst is None and not any(p.endswith("/loopt") for _, p in api.aanroepen)
    assert events[-2]["artefact"]["ref"]["run_id"] == "r1"
    assert "al gerekend" in api.berichten[0]["tekst"]


def test_een_lopende_run_van_een_ander_wordt_afgewacht(nep):
    api = nep(run_status="loopt")
    events = _events()
    assert api.uitkomst is None and api.peilingen == 2
    assert events[-2]["type"] == "opgeslagen" and "artefact" in events[-2]


def test_een_weigering_is_een_antwoord_zonder_artefact(nep):
    api = nep(weiger=(409, {"fout": "te_weinig_passages", "melding": "…"}))
    events = _events()
    assert events[-2] == {"type": "opgeslagen", "run_id": "beurt1"}
    [bericht] = api.berichten
    assert "artefact" not in bericht and "minder dan twee" in bericht["tekst"]


def test_een_storing_van_de_api_is_een_zichtbare_fout(nep):
    nep(weiger=(500, {}))
    events = _events()
    assert events[-2]["type"] == "error" and events[-1] == {"type": "done"}


def test_een_verwijderd_gesprek_eindigt_stil(nep):
    api = nep()
    events = _events(gesprek="weg")
    assert events[-1] == {"type": "done"} and not any(e["type"] in ("opgeslagen", "error") for e in events)
    assert api.berichten == []


# --- de endpoints ----------------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    import api.main as main

    gestart: list[str] = []

    async def nep_beurt(request, run, **_kw):
        gestart.append(request.werkgebied_id)
        yield {"type": "done"}

    monkeypatch.setattr(main.settings, "graphdb_token", "test", raising=False)
    monkeypatch.setattr(main.settings, "graphdb_mcp_url", "https://graaf.test/mcp", raising=False)
    monkeypatch.setattr(main, "begrippen_beurt", nep_beurt)
    monkeypatch.setattr(main, "runs", type(main.runs)())
    with TestClient(main.app) as c:
        yield c, main, gestart


def test_een_vraag_om_begrippen_in_een_werkgebied_gaat_de_begrippenroute_in(client, monkeypatch):
    c, main, gestart = client
    # Pas na de start: met schrijfpad en zonder QA_API_TOKEN weigert de dienst op te starten.
    monkeypatch.setattr(type(main.settings), "legt_zelf_vast", property(lambda _s: True))
    main.app.dependency_overrides[main._budget_check] = lambda: None
    try:
        r = c.post("/v1/runs", json={"question": "Stel begrippen voor", "conversation_id": "g1", "werkgebied_id": "wg1"})
        assert r.status_code == 201
        for _ in range(50):
            if gestart:
                break
            asyncio.run(asyncio.sleep(0.02))
        assert gestart == ["wg1"]
    finally:
        main.app.dependency_overrides.clear()


def test_de_begrippenroute_niet_via_chat(client):
    c, _main, _ = client
    r = c.post("/v1/chat", json={"question": "x", "modus": "begrippen", "werkgebied_id": "wg1"})
    assert r.status_code == 422
