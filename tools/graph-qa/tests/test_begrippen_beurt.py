"""Begrippen voorstellen (spoor D, fase AF2; sinds F3c de taak `voorstellen` van de begrippen-agent).

Bewaakt:
1. het verloop tegen een nep-api: werkgebied → run (nieuw, al klaar of al lopend) → keten → een uitkomst
   met een begrippenartefact en de fasen van de keten als meldingen;
2. een weigering van de api is een antwoord van Lex (zonder artefact), geen storing;
3. het artefact heeft de vorm van `api/app/gesprek_contracts.Artefact`, en de route bestaat niet meer
   als tekstpatroon: alleen de supervisor of een actie kiest haar.
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from agent import begrippen_beurt, begrippen_run
from agent.begrippen_beurt import begrippen_artefact, samenvatting
from agent.jas_pipeline.taal.provider import NullProvider
from agent.models import ChatRequest
from fakes import agent_ctx, make_settings
from test_begrippen_run import _als_api, _v1


def test_het_request_model():
    # Een getypte vraag om begrippen is geen harde route meer; de actie is een klik op een suggestie.
    r = ChatRequest(question="Stel begrippen voor", actie="begrippen_voorstellen", werkgebied_id="wg1")
    assert r.actie == "begrippen_voorstellen" and r.modus == "auto"
    with pytest.raises(ValueError):
        ChatRequest(question="x", modus="begrippen", werkgebied_id="wg1")
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


def _uit(gestopt: bool = False):
    settings = make_settings(wetsanalyse_api_url="http://api.test", wetsanalyse_api_token="t", qa_api_token="q")

    async def draai():
        api = begrippen_beurt.WetsanalyseApi(settings, "jurist")
        try:
            ctx = agent_ctx(api, settings=settings, run_id="beurt1", gestopt=gestopt, provider=NullProvider())
            return await begrippen_beurt.begrippen_kern(ctx, "wg1"), ctx.meldingen
        finally:
            await api.aclose()
    return asyncio.run(draai())


def test_een_nieuwe_run_rekent_en_geeft_een_begrippenartefact(nep):
    api = nep()
    uit, meldingen = _uit()
    assert any("Groeperen" in m for m in meldingen)      # de fasen van de keten, live
    assert uit.status == "ok" and uit.artefact == {"soort": "begrippen", "titel": "Invordering",
                                                   "ref": {"werkgebied_id": "wg1", "run_id": "r1"}}
    assert api.uitkomst is not None and uit.voorstellen == ["G1", "G2"] and uit.meting["model"] is False
    assert "**2** begrippen" in uit.tekst and "1 twijfelpunt " in uit.tekst


def test_al_klaar_op_deze_stand_rekent_niet_opnieuw(nep):
    api = nep(run_status="klaar")
    uit, _ = _uit()
    assert api.uitkomst is None and not any(p.endswith("/loopt") for _, p in api.aanroepen)
    assert uit.artefact["ref"]["run_id"] == "r1" and "al gerekend" in uit.tekst


def test_een_lopende_run_van_een_ander_wordt_afgewacht(nep):
    api = nep(run_status="loopt")
    uit, _ = _uit()
    assert api.uitkomst is None and api.peilingen == 2 and uit.artefact


def test_een_weigering_is_een_antwoord_zonder_artefact(nep):
    nep(weiger=(409, {"fout": "te_weinig_passages", "melding": "…"}))
    uit, _ = _uit()
    assert uit.status == "geweigerd" and uit.artefact is None and "minder dan twee" in uit.gesprekstekst


def test_een_storing_van_de_api_is_een_fout_voor_de_node(nep):
    from agent.wetsanalyse_api import WetsanalyseApiFout
    nep(weiger=(500, {}))
    with pytest.raises(WetsanalyseApiFout):
        _uit()


def test_de_begrippenroute_niet_via_chat():
    from fastapi.testclient import TestClient

    import api.main as main
    with TestClient(main.app) as c:
        r = c.post("/v1/chat", json={"question": "x", "actie": "begrippen_voorstellen", "werkgebied_id": "wg1"})
    assert r.status_code == 422
