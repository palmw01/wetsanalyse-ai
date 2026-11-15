"""De modelkeuzes per agentprofiel en per stap: wat de beheerder koos, komt echt bij de modelaanroep aan.

Zonder stand (geen api, of nog niet gelezen) blijft elk verzoek byte-gelijk; de keuze voor het agentprofiel wint, dan die
voor subagents, dan die voor de stap; het standaardprofiel vervangt alleen het gewone model, niet een eigen env-knop; een
model dat de straat niet heeft valt terug.
"""
from __future__ import annotations

import asyncio
import logging

import pytest
from bronmodel.modelkeuzes import AGENTS, KEUZES, STAPPEN

from agent import llm_stap, modelkeuze, profielen
from agent.llm_stap import Rol
from tests.fakes import FakeLLM, make_settings, response, text_block

BASIS = "claude-sonnet-4-6"


@pytest.fixture(autouse=True)
def schoon():
    modelkeuze.vergeet()
    yield
    modelkeuze.vergeet()


def _stand(**keuzes: str) -> modelkeuze.Stand:
    """`agent_duiding="claude-x"` wordt de sleutel `agent:duiding`."""
    return modelkeuze.Stand(basis=BASIS, standaard=("sonnet", BASIS),
                            keuzes={k.replace("_", ":", 1): (f"p-{k}", m) for k, m in keuzes.items()})


def _ok(n: int = 1) -> FakeLLM:
    return FakeLLM([response([text_block("ok")], "end_turn") for _ in range(n)])


def test_het_beheer_kent_elk_agentprofiel_en_elke_stap_zonder_profiel_precies_een_keer():
    """`bronmodel.modelkeuzes` is de lijst van het beheer: elk agentprofiel, elke rol zonder toollus en de subagent."""
    agents = [k.naam for k in KEUZES if k.groep == AGENTS]
    stappen = [k.naam for k in KEUZES if k.groep == STAPPEN]
    assert sorted(agents) == sorted(profielen.PROFIELEN) and len(set(agents)) == len(agents)
    assert sorted(stappen) == sorted([r.naam for r in Rol if not r.lus] + ["subagent"])
    assert all(k.sleutel == f"{'agent' if k.groep == AGENTS else 'stap'}:{k.naam}" for k in KEUZES)


def test_een_lusrol_draait_altijd_met_een_agentprofiel():
    """Daarom staat een lusrol niet als stap in het beheer: elke lus hoort bij de rol van een profiel."""
    rollen_met_profiel = {Rol.CENTRAAL if p.rol == "agent" else
                          next((r for r in Rol if r.lus and r.methoderol == p.rol), Rol.ANTWOORD)
                          for p in profielen.PROFIELEN.values()}
    assert {r for r in Rol if r.lus} <= rollen_met_profiel


def test_zonder_stand_blijft_alles_zoals_het_was():
    assert modelkeuze.kies(["stap:jas_classifier"], BASIS) == (BASIS, {"modelbron": "env"})


def test_de_eerste_sleutel_met_een_keuze_wint_en_de_standaard_vervangt_alleen_het_gewone_model():
    modelkeuze.zet(modelkeuze.Stand(basis=BASIS, standaard=("nieuw", "claude-opus-4-7"),
                                    keuzes={"agent:duiding": ("licht", "claude-haiku-4-5"),
                                            "stap:subagent": ("klein", "claude-haiku-3")}))
    assert modelkeuze.kies(["agent:duiding", "stap:subagent", "stap:antwoord"], BASIS)[0] == "claude-haiku-4-5"
    assert modelkeuze.kies(["agent:algemeen", "stap:subagent", "stap:antwoord"], BASIS) == (
        "claude-haiku-3", {"modelprofiel": "klein", "modelsleutel": "stap:subagent", "modelbron": "keuze"})
    assert modelkeuze.kies(["agent:algemeen", "stap:antwoord"], BASIS) == (
        "claude-opus-4-7", {"modelprofiel": "nieuw", "modelbron": "standaard"})
    # Een eigen env-knop (LLM_MODEL_OPHAAL) is geen "standaard": die blijft.
    assert modelkeuze.kies(["agent:retrieval", "stap:ophaal"], "claude-env-ophaal")[0] == "claude-env-ophaal"


def test_een_stap_draait_op_het_gekozen_model_en_logt_profiel_en_sleutel(caplog):
    modelkeuze.zet(_stand(stap_jas_classifier="claude-haiku-4-5"))
    llm = _ok()
    with caplog.at_level(logging.INFO, logger="graph_qa.llm"):
        llm_stap.aanroep(llm, Rol.JAS_CLASSIFIER, model=BASIS, max_tokens=10, system="s", tools=[], messages=[])
    assert llm.calls[0]["model"] == "claude-haiku-4-5"
    r = next(r for r in caplog.records if r.getMessage() == "model_aanroep")
    assert (r.model, r.modelprofiel, r.modelsleutel, r.modelbron) == (
        "claude-haiku-4-5", "p-stap_jas_classifier", "stap:jas_classifier", "keuze")


def test_een_agent_draait_op_de_keuze_van_zijn_profiel():
    """De agentvorm zet `profiel_id` in het kader; daarop beslist de keuze, niet op de rol die vijf profielen delen."""
    modelkeuze.zet(_stand(agent_duiding="claude-haiku-4-5"))
    llm = _ok(2)
    for profiel in ("duiding", "definitie"):
        llm_stap.aanroep(llm, Rol.ANTWOORD, kader={"profiel_id": profiel}, model=BASIS, max_tokens=10, system="s",
                         tools=[], messages=[])
    assert [c["model"] for c in llm.calls] == ["claude-haiku-4-5", BASIS]


def test_een_subagent_volgt_zijn_profiel_en_anders_de_keuze_voor_subagents():
    modelkeuze.zet(_stand(agent_duiding="claude-zwaar", stap_subagent="claude-haiku-4-5"))
    llm = _ok(3)
    for kader in ({"profiel_id": "duiding", "modelrol": "subagent"}, {"profiel_id": "algemeen", "modelrol": "subagent"},
                  {"profiel_id": "algemeen"}):
        llm_stap.aanroep(llm, Rol.ANTWOORD, kader=kader, model=BASIS, max_tokens=10, system="s", tools=[], messages=[])
    assert [c["model"] for c in llm.calls] == ["claude-zwaar", "claude-haiku-4-5", BASIS]


def test_zonder_keuze_is_het_verzoek_byte_gelijk():
    modelkeuze.zet(_stand())
    llm = _ok()
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
    modelkeuze.zet(_stand(stap_supervisor="claude-bestaat-niet"))
    llm = _EenModelWeg("claude-bestaat-niet", [response([text_block("a")], "end_turn")])
    with caplog.at_level(logging.WARNING, logger="graph_qa.modelkeuze"):
        llm_stap.aanroep(llm, Rol.SUPERVISOR, model=BASIS, max_tokens=10, system="— rol supervisor\n\n", tools=[],
                         messages=[])
    assert [c["model"] for c in llm.calls] == [BASIS]
    assert any(r.getMessage() == "modelprofiel_terugval" for r in caplog.records)
    assert modelkeuze.kies(["stap:supervisor"], BASIS)[0] == BASIS


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

    modelkeuze.zet(_stand(agent_algemeen="claude-weg"))
    llm = Stroom([response([text_block("ok")], "end_turn")])
    with llm_stap.stroom(llm, Rol.ANTWOORD, kader={"profiel_id": "algemeen"}, model=BASIS, max_tokens=10, system="s",
                         tools=[], messages=[]) as s:
        s.final_message()
    assert llm.calls[-1]["model"] == BASIS


def test_ververs_leest_de_api_een_keer_per_minuut_en_houdt_de_stand_bij_een_storing(monkeypatch):
    from agent import wetsanalyse_api

    std = {"profiel": "sonnet", "model": BASIS, "bron": "standaard"}
    antwoorden = [{"standaard": std, "keuzes": {
        "stap:subagent": {"profiel": "licht", "model": "claude-haiku-4-5", "bron": "keuze"},
        "stap:supervisor": {"profiel": "gpt", "model": "gpt-5", "bron": "keuze"},
        "agent:duiding": std}}]
    gevraagd = []

    async def modelkeuzes(self):
        gevraagd.append(1)
        if not antwoorden:
            raise RuntimeError("api weg")
        return antwoorden.pop(0)

    monkeypatch.setattr(wetsanalyse_api.WetsanalyseApi, "modelkeuzes", modelkeuzes)
    settings = make_settings(wetsanalyse_api_url="http://api", wetsanalyse_api_token="t", llm_model=BASIS)
    asyncio.run(modelkeuze.ververs(settings, nu=1000.0))
    asyncio.run(modelkeuze.ververs(settings, nu=1030.0))          # binnen de minuut: niet opnieuw
    assert len(gevraagd) == 1
    s = modelkeuze.stand()
    # Alleen een eigen keuze met een Claude-model telt; een sleutel die de standaard volgt is geen keuze.
    assert s is not None and set(s.keuzes) == {"stap:subagent"} and s.standaard == ("sonnet", BASIS)
    asyncio.run(modelkeuze.ververs(settings, nu=1100.0))          # de api is weg: de stand blijft
    assert len(gevraagd) == 2 and modelkeuze.kies(["stap:subagent"], BASIS)[0] == "claude-haiku-4-5"


def test_zonder_api_wordt_er_niets_gelezen():
    asyncio.run(modelkeuze.ververs(make_settings(wetsanalyse_api_url="")))
    assert modelkeuze.stand() is None
