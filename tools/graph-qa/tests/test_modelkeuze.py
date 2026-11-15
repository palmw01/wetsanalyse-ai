"""Het modelprofiel per rol: wat de beheerder koos, komt echt bij de modelaanroep aan.

Zonder stand (geen api, of nog niet gelezen) blijft elk verzoek byte-gelijk; een keuze voor de rol wint; het
standaardprofiel vervangt alleen het gewone model, niet een eigen env-knop; een model dat de straat niet heeft valt terug.
"""
from __future__ import annotations

import asyncio
import logging

import pytest
from bronmodel.modelrollen import NAMEN

from agent import llm_stap, modelkeuze
from agent.llm_stap import Rol
from tests.fakes import FakeLLM, make_settings, response, text_block

BASIS = "claude-sonnet-4-6"


@pytest.fixture(autouse=True)
def schoon():
    modelkeuze.vergeet()
    yield
    modelkeuze.vergeet()


def _stand(**rollen: str) -> modelkeuze.Stand:
    return modelkeuze.Stand(basis=BASIS, standaard=("sonnet", BASIS),
                            rollen={r: (f"p-{r}", m) for r, m in rollen.items()})


def test_de_rollen_van_het_beheer_zijn_die_van_de_modelstap():
    """`bronmodel.modelrollen` is de lijst van het beheer: elke `Rol` plus de subagent, niets erbij."""
    assert set(NAMEN) == {r.naam for r in Rol} | {"subagent"}


def test_zonder_stand_blijft_alles_zoals_het_was():
    assert modelkeuze.kies("jas_classifier", BASIS) == (BASIS, {"modelbron": "env"})


def test_de_keuze_voor_de_rol_wint_en_de_standaard_vervangt_alleen_het_gewone_model():
    modelkeuze.zet(modelkeuze.Stand(basis=BASIS, standaard=("nieuw", "claude-opus-4-7"),
                                    rollen={"supervisor": ("licht", "claude-haiku-4-5")}))
    assert modelkeuze.kies("supervisor", BASIS) == ("claude-haiku-4-5", {"modelprofiel": "licht", "modelbron": "rol"})
    assert modelkeuze.kies("antwoord", BASIS) == ("claude-opus-4-7",
                                                  {"modelprofiel": "nieuw", "modelbron": "standaard"})
    # Een eigen env-knop (LLM_MODEL_OPHAAL) is geen "standaard": die blijft.
    assert modelkeuze.kies("ophaal", "claude-env-ophaal")[0] == "claude-env-ophaal"


def test_een_aanroep_draait_op_het_gekozen_model_en_logt_het_profiel(caplog):
    modelkeuze.zet(_stand(jas_classifier="claude-haiku-4-5"))
    llm = FakeLLM([response([text_block("ok")], "end_turn")])
    with caplog.at_level(logging.INFO, logger="graph_qa.llm"):
        llm_stap.aanroep(llm, Rol.JAS_CLASSIFIER, model=BASIS, max_tokens=10, system="s", tools=[], messages=[])
    assert llm.calls[0]["model"] == "claude-haiku-4-5"
    regel = next(r for r in caplog.records if r.getMessage() == "model_aanroep")
    assert (regel.model, regel.modelprofiel, regel.modelbron) == ("claude-haiku-4-5", "p-jas_classifier", "rol")


def test_zonder_keuze_is_het_verzoek_byte_gelijk():
    modelkeuze.zet(_stand())
    llm = FakeLLM([response([text_block("ok")], "end_turn")])
    llm_stap.aanroep(llm, Rol.JAS_REVIEWER, model=BASIS, max_tokens=10, system="s", tools=[], messages=[])
    assert llm.calls[0] == {"model": BASIS, "max_tokens": 10, "system": "s", "tools": [], "messages": []}


class _Weg(Exception):
    status_code = 404


class _EenModelWeg(FakeLLM):
    def __init__(self, weg: str, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.weg = weg

    def create(self, **kwargs):
        if kwargs["model"] == self.weg:
            raise _Weg("model not found")
        return super().create(**kwargs)


def test_een_model_dat_de_straat_niet_heeft_valt_terug_en_blijft_terug(caplog):
    modelkeuze.zet(_stand(supervisor="claude-bestaat-niet"))
    llm = _EenModelWeg("claude-bestaat-niet", [response([text_block("a")], "end_turn"),
                                              response([text_block("b")], "end_turn")])
    with caplog.at_level(logging.WARNING, logger="graph_qa.modelkeuze"):
        llm_stap.aanroep(llm, Rol.SUPERVISOR, model=BASIS, max_tokens=10, system="— rol supervisor\n\n", tools=[],
                         messages=[])
    assert [c["model"] for c in llm.calls] == [BASIS]
    assert any(r.getMessage() == "modelprofiel_terugval" for r in caplog.records)
    # De rest van het proces ook: geen tweede poging op het kapotte model.
    assert modelkeuze.kies("supervisor", BASIS)[0] == BASIS


def test_een_stream_valt_ook_terug():
    class Stroom(FakeLLM):
        def stream(self, **kwargs):
            if kwargs["model"] == "claude-weg":
                class Kapot:
                    def __enter__(self):
                        raise _Weg("model not found")

                    def __exit__(self, *_):
                        return False
                return Kapot()
            return super().stream(**kwargs)

    modelkeuze.zet(_stand(antwoord="claude-weg"))
    llm = Stroom([response([text_block("ok")], "end_turn")])
    with llm_stap.stroom(llm, Rol.ANTWOORD, model=BASIS, max_tokens=10, system="s", tools=[],
                         messages=[]) as s:
        s.final_message()
    assert llm.calls[-1]["model"] == BASIS


def test_een_subagent_heeft_zijn_eigen_rol():
    """De subagent draait met de rol van zijn profiel, maar het beheer kiest zijn model apart (`modelrol`)."""
    modelkeuze.zet(_stand(antwoord="claude-zwaar", subagent="claude-haiku-4-5"))
    llm = FakeLLM([response([text_block("ok")], "end_turn"), response([text_block("ok")], "end_turn")])
    llm_stap.aanroep(llm, Rol.ANTWOORD, kader={"modelrol": "subagent"}, model=BASIS, max_tokens=10, system="s",
                     tools=[], messages=[])
    llm_stap.aanroep(llm, Rol.ANTWOORD, model=BASIS, max_tokens=10, system="s", tools=[], messages=[])
    assert [c["model"] for c in llm.calls] == ["claude-haiku-4-5", "claude-zwaar"]


def test_ververs_leest_de_api_een_keer_per_minuut_en_houdt_de_stand_bij_een_storing(monkeypatch):
    from agent import wetsanalyse_api

    antwoorden = [{"standaard": {"profiel": "sonnet", "model": BASIS},
                   "rollen": {"subagent": {"profiel": "licht", "model": "claude-haiku-4-5"},
                              "supervisor": {"profiel": "gpt", "model": "gpt-5"}}}]
    gevraagd = []

    async def modelrollen(self):
        gevraagd.append(1)
        if not antwoorden:
            raise RuntimeError("api weg")
        return antwoorden.pop(0)

    monkeypatch.setattr(wetsanalyse_api.WetsanalyseApi, "modelrollen", modelrollen)
    settings = make_settings(wetsanalyse_api_url="http://api", wetsanalyse_api_token="t", llm_model=BASIS)
    asyncio.run(modelkeuze.ververs(settings, nu=1000.0))
    asyncio.run(modelkeuze.ververs(settings, nu=1030.0))          # binnen de minuut: niet opnieuw
    assert len(gevraagd) == 1
    # Alleen een Claude-model telt; de rest geldt niet.
    assert modelkeuze.kies("subagent", BASIS)[0] == "claude-haiku-4-5"
    assert modelkeuze.kies("supervisor", BASIS)[0] == BASIS
    asyncio.run(modelkeuze.ververs(settings, nu=1100.0))          # de api is weg: de stand blijft
    assert len(gevraagd) == 2 and modelkeuze.kies("subagent", BASIS)[0] == "claude-haiku-4-5"


def test_zonder_api_wordt_er_niets_gelezen():
    asyncio.run(modelkeuze.ververs(make_settings(wetsanalyse_api_url="")))
    assert modelkeuze.stand() is None
