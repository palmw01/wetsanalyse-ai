"""De agentvorm (ADR-016, randvoorwaarde): elke agent van de open laag is een Python-`Agent` met een profiel.

Wat deze tests vastleggen:

1. **Elke modelaanroep van een rol met een toollus komt uit `agent/agentvorm.py`.** Een profiel kan dus niet buiten de
   basisklasse draaien: zonder `Agent` geen modelaanroep.
2. **De antwoordketen staat één keer in de code**, in `voeg_keten_toe`. Er is geen tweede lus naast de graaf.
3. **Wat een agent meestuurt, volgt uit zijn profiel**, en is wat `agent_node` vóór de agentvorm zelf samenstelde.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agent import agentvorm, profielen, specialists, tools
from agent.agentvorm import Agent, agent_voor
from agent.config import Settings
from agent.llm_stap import Rol
from agent.methode import instructies
from agent.orchestrator import build_graph
from agent.prompts import SYSTEM_PROMPT
from agent.sjablonen import EXTERN
from tests.fakes import FakeGraph, FakeLLM, make_settings, response, text_block

AGENT = Path(agentvorm.__file__).resolve().parent
MODELSTAPPEN = {"stroom", "aanroep", "vraag_tool"}
LUSROLLEN = {r.name for r in Rol if r.lus}


def _rol_van(aanroep: ast.Call) -> str | None:
    """De `Rol.X` in de argumenten van een modelstap, of `None` als de rol geen letterlijke `Rol.X` is."""
    for arg in aanroep.args:
        if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name) and arg.value.id == "Rol":
            return arg.attr
    return None


def _modelstappen() -> list[tuple[str, int, str | None]]:
    """Elke aanroep van de gedeelde modelstap in `agent/`: (bestand, regel, rol)."""
    uit = []
    for pad in sorted(AGENT.rglob("*.py")):
        if pad.name == "llm_stap.py":
            continue
        for knoop in ast.walk(ast.parse(pad.read_text(encoding="utf-8"))):
            if isinstance(knoop, ast.Call) and getattr(knoop.func, "id", getattr(knoop.func, "attr", "")) in MODELSTAPPEN:
                uit.append((pad.relative_to(AGENT).as_posix(), knoop.lineno, _rol_van(knoop)))
    return uit


def test_er_zijn_rollen_met_een_lus_en_de_toets_vindt_modelstappen():
    assert {"OPHAAL", "ANTWOORD"} <= LUSROLLEN
    assert len(_modelstappen()) >= 5, "de AST-toets vindt de modelstappen niet meer"


def test_elke_modelaanroep_met_een_toollus_komt_uit_de_agentvorm():
    """Buiten `agentvorm.py` noemt elke modelstap een vaste rol zonder lus. Een rol met een lus, of een rol die pas bij
    het draaien bekend is, hoort bij een `Agent`."""
    buiten = [s for s in _modelstappen() if s[0] != "agentvorm.py"]
    fout = [s for s in buiten if s[2] is None or s[2] in LUSROLLEN]
    assert not fout, f"een modelaanroep van de open laag buiten de agentvorm: {fout}"
    binnen = [s for s in _modelstappen() if s[0] == "agentvorm.py"]
    assert len(binnen) == 1, "de agentvorm heeft één plek voor de modelaanroep"


def test_de_antwoordketen_staat_een_keer_in_de_code():
    """De nodes van de keten registreert alleen `voeg_keten_toe`; `build_graph` sluit haar aan."""
    for bestand in ("orchestrator.py",):
        bron = (AGENT / bestand).read_text(encoding="utf-8")
        for node in ("agent", "tools", "sjabloon", "verify", "correct", "finalize"):
            assert f'add("{node}"' not in bron, f"{bestand} registreert de node {node} zelf"
    assert (AGENT / "agentvorm.py").read_text(encoding="utf-8").count('add("agent"') == 1


@pytest.mark.parametrize("naam", sorted(profielen.PROFIELEN))
def test_wat_een_agent_meestuurt_volgt_uit_zijn_profiel(naam: str):
    agent, p = agent_voor(naam), profielen.PROFIELEN[naam]
    assert isinstance(agent, Agent) and agent.profiel is p
    assert agent.systeemtekst == SYSTEM_PROMPT + "\n\n" + instructies(p.rol) + "\n\n" + p.instructie
    assert agent.instructie == specialists.get(naam).system
    assert agent.tools == specialists.SPECIALISTS[naam].tools
    assert agent.methoderol == p.rol and agent.versie == profielen.versie(p)
    # Zonder connector in de beurt: zijn eigen sjablonen. Met een connector die hij noemt: ook `antwoord_extern`.
    assert agent.sjablonen({}) == frozenset(p.sjablonen) and agent.extern({}) == ()
    stand = {c: {"aan": True} for c in tools.CONNECTORS}
    verwacht = tuple(c for c in stand if c in p.connectors) if p.sjablonen else ()
    assert agent.extern(stand) == verwacht
    assert agent.sjablonen(stand) == frozenset(p.sjablonen) | ({EXTERN} if verwacht else set())


def test_de_rol_en_het_model_horen_bij_de_agent():
    s = Settings().model_copy(update={"llm_model": "sterk", "llm_model_ophaal": "licht", "llm_model_router": "router"})
    assert agent_voor("retrieval").rol is Rol.OPHAAL and agent_voor("retrieval").model(s) == "licht"
    for naam in ("definitie", "duiding", "algemeen", "annotaties_lezen", "begrippen_lezen"):
        assert agent_voor(naam).rol is Rol.ANTWOORD and agent_voor(naam).model(s) == "sterk"
    assert agent_voor(None) == agent_voor("bestaat_niet") == agent_voor(" Algemeen ") == agent_voor("algemeen")


def test_de_ronde_draagt_het_profiel_naar_de_meting(caplog):
    """`profiel_id` en `profiel_versie` staan op `model_aanroep` (ADR-016 §A3); het verzoek zelf verandert er niet door."""
    import logging

    llm = FakeLLM([response([text_block("Antwoord.")], "end_turn")])
    agent = agent_voor("duiding")
    with caplog.at_level(logging.INFO, logger="graph_qa.llm"):
        agent.ronde(llm, make_settings(), systeem=[agent.systeemtekst], berichten=[{"role": "user", "content": "x"}],
                    berichtpunten=(), bronnen=None, bronstand={}, kader={})
    [regel] = [r for r in caplog.records if r.getMessage() == "model_aanroep"]
    assert (regel.profiel_id, regel.profiel_versie, regel.rol) == ("duiding", agent.versie, "antwoord")
    assert "profiel_id" not in llm.calls[0] and "kader" not in llm.calls[0]


def test_een_agent_draait_de_ene_graaf():
    """Er is één graafopbouw; de keten erin is die van de agentvorm."""
    g = build_graph(make_settings(), FakeLLM([]), FakeGraph())
    assert {"agent", "tools", "sjabloon", "verify", "correct", "finalize"} <= set(g.nodes)
