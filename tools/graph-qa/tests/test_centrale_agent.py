"""De centrale agent zonder subagents (ADR-016 §A1 en §A7, stap A2-2), achter de vlag `CENTRALE_AGENT`.

Wat deze tests vastleggen:

1. **De vlag heeft drie standen.** `uit` negeert het verzoek per run (het slot voor productie), `meten` draait de
   supervisor tenzij de run om de centrale agent vraagt, `aan` omgekeerd.
2. **Met `uit` is Lex bitgelijk**: dezelfde graaf, dezelfde eerste modelaanroep (de supervisor).
3. **De centrale agent antwoordt zelf**: geen supervisorstap, het profiel `centraal` met de methoderol `agent`, en zijn
   eigen tool `wijs_af`. Een afwijzing komt uit code; een afwijzing van een bronvraag weigert de code.

De routes vóór het model blijven voor beide vormen dezelfde code (`tests/test_routering.py`).
"""
from __future__ import annotations

import asyncio

import pytest

from agent import overdracht, profielen
from agent.agent import answer_stream
from agent.agentvorm import CENTRAAL, Agent, CentraleAgent, agent_voor, vorm_van
from agent.config import Settings
from agent.llm_stap import Rol
from agent.methodepakket import PAKKET
from agent.nodes import supervisie
from agent.orchestrator import build_graph
from tests.fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block


def _run(gen):
    async def collect():
        return [ev async for ev in gen]

    return asyncio.run(collect())


def _beurt(vraag: str, llm: FakeLLM, *, stand: str, gevraagd: str | None = None):
    return _run(answer_stream(vraag, settings=make_settings(centrale_agent=stand), llm=llm, graph=FakeGraph(result=""),
                              agentvorm=gevraagd))


def _supervisor_dan_antwoord() -> FakeLLM:
    return FakeLLM([response([text_block("SPECIALIST: duiding\nPLAN: kort plan.")], "end_turn"),
                    response([text_block("Antwoord.")], "end_turn")])


VRAAG = "Hoe hangt de aansprakelijkheid van een bestuurder samen met de invordering?"


# --- de vlag ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("stand", "gevraagd", "verwacht"), [
    ("uit", None, "supervisor"), ("uit", "centraal", "supervisor"), ("uit", "supervisor", "supervisor"),
    ("meten", None, "supervisor"), ("meten", "centraal", "centraal"), ("meten", "supervisor", "supervisor"),
    ("aan", None, "centraal"), ("aan", "centraal", "centraal"), ("aan", "supervisor", "supervisor"),
    ("onzin", "centraal", "supervisor"),
])
def test_de_straat_beslist_of_een_run_mag_kiezen(stand, gevraagd, verwacht):
    assert vorm_van(stand, gevraagd) == verwacht


def test_de_vlag_staat_standaard_uit_en_komt_uit_de_omgeving():
    assert Settings().centrale_agent == "uit"
    assert Settings.from_env({"CENTRALE_AGENT": " Meten "}).centrale_agent == "meten"
    assert Settings.from_env({}).centrale_agent == "uit"
    with pytest.raises(ValueError):
        Settings.from_env({"CENTRALE_AGENT": "true"})


def test_met_uit_negeert_lex_het_verzoek_per_run():
    """Het slot voor productie: ook een run die om de centrale agent vraagt, krijgt de supervisor."""
    llm = _supervisor_dan_antwoord()
    _beurt(VRAAG, llm, stand="uit", gevraagd="centraal")
    assert "rol supervisor" in llm.calls[0]["system"] and llm.calls[0]["tools"] == []
    assert "rol duiding" in llm.calls[1]["system"]


def test_met_uit_is_de_graaf_die_van_voorheen():
    uit = build_graph(make_settings(), FakeLLM([]), FakeGraph())
    assert "overdracht" not in uit.nodes
    for stand in ("meten", "aan"):
        g = build_graph(make_settings(centrale_agent=stand), FakeLLM([]), FakeGraph())
        assert set(g.nodes) == set(uit.nodes) | {"overdracht"}
        edges = {(e.source, e.target) for e in g.compile().get_graph().edges}
        oud = {(e.source, e.target) for e in uit.compile().get_graph().edges}
        assert edges - oud == {("agent", "overdracht"), ("overdracht", "agent"), ("overdracht", "afwijzen")}
        assert not oud - edges


def test_met_meten_draait_de_supervisor_tenzij_de_run_anders_vraagt():
    llm = _supervisor_dan_antwoord()
    _beurt(VRAAG, llm, stand="meten")
    assert "rol supervisor" in llm.calls[0]["system"]


# --- de centrale agent -----------------------------------------------------------------------------------------

def test_de_centrale_agent_antwoordt_zelf_zonder_supervisorstap():
    llm = FakeLLM([response([text_block("Antwoord.")], "end_turn")])
    events = _beurt(VRAAG, llm, stand="meten", gevraagd="centraal")
    assert len(llm.calls) == 1, "geen supervisorstap, één ronde"
    [verzoek] = llm.calls
    assert "rol agent" in verzoek["system"] and "rol supervisor" not in verzoek["system"]
    for sectie in PAKKET["rollen"]["agent"]:
        assert PAKKET["secties"][sectie]["tekst"] in verzoek["system"]
    namen = {t["name"] for t in verzoek["tools"]}
    assert {"wijs_af", "get_artikel", "zoek_definitie", "get_context", "antwoord_duiding", "antwoord_begrip"} <= namen
    assert not namen & {"subagent", "search_annotaties"}
    assert any(e["type"] == "status" and e.get("route") == CENTRAAL for e in events)
    assert "".join(e["content"] for e in events if e["type"] == "token") == "Antwoord."


def test_met_aan_is_de_centrale_agent_de_standaard_en_mag_een_run_de_supervisor_vragen():
    llm = FakeLLM([response([text_block("Antwoord.")], "end_turn")])
    _beurt(VRAAG, llm, stand="aan")
    assert "rol agent" in llm.calls[0]["system"]
    llm = _supervisor_dan_antwoord()
    _beurt(VRAAG, llm, stand="aan", gevraagd="supervisor")
    assert "rol supervisor" in llm.calls[0]["system"]


def test_het_profiel_centraal_is_een_python_agent_met_zijn_eigen_tools():
    agent = agent_voor(CENTRAAL)
    assert isinstance(agent, CentraleAgent) and isinstance(agent, Agent)
    assert agent.rol is Rol.CENTRAAL and agent.methoderol == "agent"
    assert set(agent.eigen_tools) == set(overdracht.OVERDRACHT) == {"wijs_af"}
    p = profielen.PROFIELEN[CENTRAAL]
    assert not p.kiesbaar and CENTRAAL not in profielen.KIESBAAR, "een model kiest dit profiel niet"
    # De eigen tools staan niet in de toollaag: een profiel kan ze niet noemen, en een andere agent krijgt ze niet.
    assert not set(overdracht.OVERDRACHT) & profielen.grenzen().tools
    for naam in set(profielen.PROFIELEN) - {CENTRAAL}:
        assert type(agent_voor(naam)) is Agent and not agent_voor(naam).eigen_tools


def test_een_overdrachtstool_heeft_een_strict_schema():
    for o in overdracht.OVERDRACHT.values():
        s = o.schema
        assert s["strict"] is True and s["input_schema"]["additionalProperties"] is False
        assert s["input_schema"]["required"] == sorted(o.invoer)
        assert o.naar in overdracht.doelen()


def test_afwijzen_is_een_tool_en_de_tekst_komt_uit_code():
    llm = FakeLLM([response([tool_block("t1", "wijs_af", {})], "tool_use")])
    events = _beurt("Wat voor weer wordt het morgen?", llm, stand="meten", gevraagd="centraal")
    assert len(llm.calls) == 1, "na de overdracht schrijft het model niets meer"
    tekst = "".join(e["content"] for e in events if e["type"] == "token")
    assert tekst.startswith("Deze vraag gaat niet over Nederlandse wet- en regelgeving")
    assert any(e["type"] == "status" and e.get("route") == "afgewezen" for e in events)


def test_een_afwijzing_van_een_bronvraag_weigert_de_code():
    """Een vraag over een bron naast de wet is nooit buiten de scope (ADR-013): het model werkt verder."""
    # Met een artikel erbij is er ook wetgeving te zoeken: de vaste melding "bron staat uit" pakt de vraag dan niet.
    vraag = "Wat zegt de memorie van toelichting over artikel 36 van de Invorderingswet 1990?"
    assert supervisie.bronnen_in_vraag(vraag)
    llm = FakeLLM([response([tool_block("t1", "wijs_af", {})], "tool_use"),
                   response([text_block("De Kamerstukken staan in deze beurt uit.")], "end_turn")])
    events = _beurt(vraag, llm, stand="meten", gevraagd="centraal")
    assert len(llm.calls) == 2
    [resultaat] = [b for m in llm.calls[1]["messages"] if isinstance(m["content"], list)
                   for b in m["content"] if b.get("type") == "tool_result"]
    assert resultaat["is_error"] is True and "Wijs de vraag niet af" in resultaat["content"]
    assert not any(e["type"] == "status" and e.get("route") == "afgewezen" for e in events)


def test_een_overdracht_naast_andere_tools_laat_alleen_de_overdracht_over():
    llm = FakeLLM([response([tool_block("t1", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": "9"}),
                             tool_block("t2", "wijs_af", {})], "tool_use")])
    events = _beurt("Wat voor weer wordt het morgen?", llm, stand="meten", gevraagd="centraal")
    assert len(llm.calls) == 1
    assert "".join(e["content"] for e in events if e["type"] == "token").startswith("Deze vraag gaat niet over")


def test_de_centrale_agent_neemt_alleen_de_gewone_vraag_over():
    """Een adviesvraag blijft de vaste route naar de duiding; de centrale agent is er voor wat geen route pakt."""
    assert supervisie._centraal({"agentvorm": "centraal", "modus": "auto"})
    assert not supervisie._centraal({"agentvorm": "centraal", "modus": "advies"})
    assert not supervisie._centraal({"agentvorm": "supervisor", "modus": "auto"})
    assert not supervisie._centraal({"modus": "auto"})
