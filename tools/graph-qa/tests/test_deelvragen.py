"""Lex stelt deelvragen voor (vervolg op spoor D fase F): de prompt, de validatie, de stroom tegen een
nep-api en nep-model, het api-contract (uit de bron gelezen) en het endpoint."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from agent import deelvragen
from agent.models import DeelvragenRunVerzoek
from agent.runstore import Run
from fakes import make_settings, response, text_block, tool_block

WG = {"id": "wg1", "naam": "Invorderbaarheid", "analysevraag": "Wanneer is een belastingaanslag invorderbaar?",
      "afbakening": "Alleen rijksbelastingen.", "deelvragen": [{"id": "d1", "vraag": "Wie is de belastingschuldige?"}]}


def test_de_prompt_noemt_de_vraag_de_afbakening_en_wat_er_al_staat():
    p = deelvragen.prompt(WG)
    assert "Analysevraag: Wanneer is een belastingaanslag invorderbaar?" in p
    assert "Afbakening: Alleen rijksbelastingen." in p and "- Wie is de belastingschuldige?" in p
    assert "(geen)" in deelvragen.prompt({**WG, "deelvragen": [], "afbakening": ""})


def test_de_validatie_houdt_alleen_echte_vragen_over():
    uit = deelvragen.valideer({"deelvragen": [
        "  Wanneer   vervalt de betalingstermijn? ", "wanneer vervalt de betalingstermijn?", "Geen vraag.", "Wie?",
        *[f"Vraag nummer {i}?" for i in range(12)]]})
    assert uit[0] == "Wanneer vervalt de betalingstermijn?"
    assert "Geen vraag." not in uit and "Wie?" not in uit
    assert len(uit) == deelvragen.MAX_DEELVRAGEN and len(set(map(str.casefold, uit))) == len(uit)
    assert deelvragen.valideer(None) == []


class NepApi:
    def __init__(self, wg=WG, weigert: int | None = None):
        self.wg, self.weigert = wg, weigert
        self.voorgesteld: list[tuple[list[str], str]] = []
        self.geboekt: list[str] = []

    async def haal_werkgebied(self, wid):
        return self.wg

    async def stel_deelvragen_voor(self, wid, vragen, model="", vervangt=""):
        if self.weigert:
            from agent.wetsanalyse_api import WetsanalyseApiFout
            raise WetsanalyseApiFout("nee", self.weigert, "")
        self.voorgesteld.append((vragen, model))
        return {"nieuw": [f"n{i}" for i in range(len(vragen) - 1)], "overgeslagen": [{"vraag": vragen[-1], "reden": "actief"}]}

    async def boek_verbruik(self, verbruik, *, model, gesprek_id, run_id):
        self.geboekt.append(run_id)
        return {}

    async def aclose(self):
        pass


class NepModel:
    def __init__(self, antwoorden):
        self.antwoorden = list(antwoorden)
        self.verzoeken: list[dict] = []

        class Meter:
            totaal = 10

            @staticmethod
            def als_dict():
                return {"invoer": 5, "uitvoer": 5}
        self.meter = Meter()

    def create(self, **kw):
        self.verzoeken.append(kw)
        return self.antwoorden.pop(0)


def _stroom(api, model) -> list[dict]:
    async def verzamel():
        return [e async for e in deelvragen.deelvragen_stroom(
            "wg1", Run(run_id="x", conversation_id="werkgebied:wg1:deelvragen"), settings=make_settings(),
            user_id="jurist", maak_llm=lambda _s: model, api=api)]
    return asyncio.run(verzamel())


def _tool(vragen):
    return response([tool_block("t1", deelvragen.TOOL, {"deelvragen": vragen})], "tool_use")


def test_de_stroom_stelt_voor_en_boekt_het_verbruik():
    api, model = NepApi(), NepModel([_tool(["Wanneer vervalt de termijn?", "Wie is de belastingschuldige?"])])
    events = _stroom(api, model)
    assert [e["type"] for e in events][-3:] == ["token", "opgeslagen", "done"]
    assert api.voorgesteld == [(["Wanneer vervalt de termijn?", "Wie is de belastingschuldige?"],
                                make_settings().llm_model)]
    assert api.geboekt == ["deelvragen-x"]
    token = next(e for e in events if e["type"] == "token")["content"]
    assert "**1** deelvraag" in token and "1 stonden er al" in token
    assert model.verzoeken[0]["tools"][0]["name"] == deelvragen.TOOL


def test_zonder_tool_aanroep_een_tweede_poging_en_daarna_niets():
    api = NepApi()
    model = NepModel([response([text_block("hmm")], "end_turn"), response([text_block("nee")], "end_turn")])
    events = _stroom(api, model)
    assert len(model.verzoeken) == 2 and api.voorgesteld == []
    assert "al enkelvoudig" in next(e for e in events if e["type"] == "token")["content"]


def test_zonder_analysevraag_geen_modelaanroep():
    api, model = NepApi(wg={**WG, "analysevraag": " "}), NepModel([])
    events = _stroom(api, model)
    assert events[-1]["type"] == "error" and events[-1]["soort"] == "invoer" and model.verzoeken == []


def test_een_weigering_van_de_api_is_een_fout():
    api, model = NepApi(weigert=404), NepModel([_tool(["Wanneer vervalt de termijn?"])])
    events = _stroom(api, model)
    assert events[-1]["type"] == "error" and events[-1]["soort"] == "api"
    assert api.geboekt == ["deelvragen-x"], "het verbruik telt ook als opslaan faalt"


def test_de_vragen_passen_in_het_api_contract():
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "api"))
    try:
        from app.werkgebied_contracts import DeelvraagVoorstellen
    except ImportError:
        pytest.skip("api-pakket niet importeerbaar in deze omgeving")
    finally:
        sys.path.pop(0)
    vragen = deelvragen.valideer({"deelvragen": [f"Vraag nummer {i}?" for i in range(20)]})
    DeelvraagVoorstellen(vragen=vragen, model="m")
    with pytest.raises(Exception):
        DeelvraagVoorstellen(vragen=vragen + ["Te veel?"] * 5)


def test_het_verzoek_en_het_endpoint(monkeypatch):
    with pytest.raises(Exception):
        DeelvragenRunVerzoek(werkgebied_id="wg 1")
    from fastapi.testclient import TestClient

    import api.main as main

    async def langzaam(werkgebied_id, run, **_kw):
        await asyncio.sleep(0.3)
        yield {"type": "done"}

    monkeypatch.setattr(main.settings, "graphdb_token", "test", raising=False)
    monkeypatch.setattr(main.settings, "graphdb_mcp_url", "https://graaf.test/mcp", raising=False)
    monkeypatch.setattr(main, "deelvragen_stroom", langzaam)
    monkeypatch.setattr(main, "runs", type(main.runs)())
    with TestClient(main.app) as c:
        assert c.post("/v1/deelvragen-runs", json={"werkgebied_id": "wg1"}).status_code == 503
        monkeypatch.setattr(type(main.settings), "legt_zelf_vast", property(lambda _s: True))
        main.app.dependency_overrides[main._budget_check] = lambda: None
        try:
            eerste = c.post("/v1/deelvragen-runs", json={"werkgebied_id": "wg1"})
            assert eerste.status_code == 201 and eerste.json()["conversation_id"] == "werkgebied:wg1:deelvragen"
            assert c.post("/v1/deelvragen-runs", json={"werkgebied_id": "wg1"}).status_code == 409
        finally:
            main.app.dependency_overrides.clear()
