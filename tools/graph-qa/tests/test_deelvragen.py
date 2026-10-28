"""Lex stelt deelvragen voor (vervolg op spoor D fase F): de prompt, de validatie, de taak `voorstellen`
tegen een nep-api en nep-model, en het api-contract (uit de bron gelezen). Het eigen endpoint
`/v1/deelvragen-runs` is met F3e vervallen; de taak draait in het gesprek (deelvragen-agent)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from agent import deelvragen
from agent.agents import Context
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

    async def haal_werkgebied(self, wid):
        return self.wg

    async def stel_deelvragen_voor(self, wid, vragen, model="", vervangt=""):
        if self.weigert:
            from agent.wetsanalyse_api import WetsanalyseApiFout
            raise WetsanalyseApiFout("nee", self.weigert, "")
        self.voorgesteld.append((vragen, model))
        return {"nieuw": [f"n{i}" for i in range(len(vragen) - 1)], "overgeslagen": [{"vraag": vragen[-1], "reden": "actief"}]}



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


def _voorstellen(api, model):
    ctx = Context(api=api, settings=make_settings(), user_id="jurist", run_id="x", llm=model)
    return asyncio.run(deelvragen.voorstellen_kern(ctx, "wg1"))


def _tool(vragen):
    return response([tool_block("t1", deelvragen.TOOL, {"deelvragen": vragen})], "tool_use")


def test_de_taak_stelt_voor_met_het_model_van_de_beurt():
    api, model = NepApi(), NepModel([_tool(["Wanneer vervalt de termijn?", "Wie is de belastingschuldige?"])])
    uit = _voorstellen(api, model)
    assert uit.status == "ok" and uit.voorstellen == ["n0"] and uit.meting["opgeslagen"] is True
    assert api.voorgesteld == [(["Wanneer vervalt de termijn?", "Wie is de belastingschuldige?"],
                                make_settings().llm_model)]
    assert "**1** deelvraag" in uit.tekst and "1 stonden er al" in uit.tekst
    assert model.verzoeken[0]["tools"][0]["name"] == deelvragen.TOOL


def test_zonder_tool_aanroep_een_tweede_poging_en_daarna_niets():
    api = NepApi()
    model = NepModel([response([text_block("hmm")], "end_turn"), response([text_block("nee")], "end_turn")])
    uit = _voorstellen(api, model)
    assert len(model.verzoeken) == 2 and api.voorgesteld == []
    assert "al enkelvoudig" in uit.tekst


def test_zonder_analysevraag_geen_modelaanroep():
    api, model = NepApi(wg={**WG, "analysevraag": " "}), NepModel([])
    uit = _voorstellen(api, model)
    assert uit.status == "geweigerd" and uit.meting["soort"] == "invoer" and model.verzoeken == []


def test_een_weigering_van_de_api_is_een_fout():
    api, model = NepApi(weigert=404), NepModel([_tool(["Wanneer vervalt de termijn?"])])
    uit = _voorstellen(api, model)
    assert uit.status == "geweigerd" and uit.meting["soort"] == "api"
    assert len(model.verzoeken) == 1, "het model draaide, dus het verbruik telt mee in de beurt"


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


def test_het_endpoint_is_vervallen():
    import api.main as main
    paden = {getattr(r, "path", "") for r in main.app.routes}
    assert not paden & {"/v1/deelvragen-runs", "/v1/bronnen-runs", "/v1/begrippen-runs", "/v1/kaart-runs"}
