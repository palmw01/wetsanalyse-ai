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
from agent.agentvorm import CENTRAAL, CENTRAAL_BREED, Agent, CentraleAgent, agent_voor, vorm_van
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
    assert {"wijs_af", "meer_tools", "get_artikel", "zoek_definitie", "get_context", "antwoord_duiding", "antwoord_begrip"} <= namen
    assert not namen & {"subagent", "search_annotaties", "geldigheid", "raw_sparql"}
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
    assert set(agent.eigen_tools) == set(overdracht.OVERDRACHT) == {"wijs_af", "meer_tools"}
    p = profielen.PROFIELEN[CENTRAAL]
    assert not p.kiesbaar and CENTRAAL not in profielen.KIESBAAR, "een model kiest dit profiel niet"
    # De eigen tools staan niet in de toollaag: een profiel kan ze niet noemen, en een andere agent krijgt ze niet.
    assert not set(overdracht.OVERDRACHT) & profielen.grenzen().tools
    for naam in set(profielen.PROFIELEN) - {CENTRAAL, CENTRAAL_BREED}:
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


# --- de kernset en de overdracht aan het brede profiel (A2-2b) --------------------------------------------------

def _graaftools() -> set[str]:
    """De leestools van de graaf en de begrippen: alles uit de toollaag behalve de connectoren en de annotatietools."""
    from agent import tools
    return {t["name"] for t in tools.TOOLS} - tools.CONNECTOR_TOOLS - set(tools.ANNOTATIE_TOOL_NAMEN)


def test_de_kernset_en_de_rest_zijn_samen_de_graaftools():
    kern, breed = (set(profielen.PROFIELEN[n].tools) for n in (CENTRAAL, CENTRAAL_BREED))
    assert kern < breed == _graaftools(), "het brede profiel heeft elke graaftool; de kernset is een deel ervan"
    assert len(kern) == 10
    # De kernset op gebruik (de nulmeting van 12 nov 2026): wat een gewone vraag draagt.
    assert kern == {"search_wetgeving", "get_artikel", "get_lid", "list_regelingen", "get_bepaling", "zoek_opbouw",
                    "inhoudsopgave", "get_context", "follow_verwijzingen", "zoek_definitie"}


def test_de_twee_profielen_verschillen_alleen_in_tools_en_de_aanwijzingen_daarvoor():
    kern, breed = profielen.PROFIELEN[CENTRAAL], profielen.PROFIELEN[CENTRAAL_BREED]
    assert breed.instructie.startswith(kern.instructie + "\n\nMEER TOOLS:")
    for veld in ("kiesbaar", "methoderol", "connectors", "sjablonen", "skills", "modelklasse"):
        assert getattr(kern, veld) == getattr(breed, veld), veld
    # De instructie noemt geen tool die het profiel niet heeft: het model zou hem proberen aan te roepen.
    for p in (kern, breed):
        ontbreekt = {t for t in _graaftools() - set(p.tools) if t in p.instructie}
        assert not ontbreekt, f"{p.naam} noemt {sorted(ontbreekt)} maar heeft ze niet"
    assert "SAMEN OPHALEN" in kern.instructie and "in dezelfde ronde pas oplevert" in kern.instructie


def test_meer_tools_is_er_alleen_voor_de_kernset_en_wijs_af_voor_beide():
    assert set(agent_voor(CENTRAAL).eigen_tools) == {"wijs_af", "meer_tools"}
    assert set(agent_voor(CENTRAAL_BREED).eigen_tools) == {"wijs_af"}
    assert isinstance(agent_voor(CENTRAAL_BREED), CentraleAgent) and agent_voor(CENTRAAL_BREED).rol is Rol.CENTRAAL
    # De beschrijving noemt elke tool die erachter zit: zo weet het model wanneer het erom vraagt.
    rest = set(profielen.PROFIELEN[CENTRAAL_BREED].tools) - set(profielen.PROFIELEN[CENTRAAL].tools)
    assert not {t for t in rest if t not in overdracht.OVERDRACHT["meer_tools"].beschrijving}


def test_na_meer_tools_draait_dezelfde_beurt_met_het_brede_profiel():
    llm = FakeLLM([response([tool_block("t1", "meer_tools", {})], "tool_use"),
                   response([text_block("Antwoord.")], "end_turn")])
    events = _beurt(VRAAG, llm, stand="meten", gevraagd="centraal")
    eerste, tweede = llm.calls
    voor, na = ({t["name"] for t in c["tools"]} for c in (eerste, tweede))
    assert "geldigheid" not in voor and "meer_tools" in voor
    assert {"geldigheid", "grondslagen", "raw_sparql", "wijs_af"} <= na and "meer_tools" not in na
    assert "MEER TOOLS:" in tweede["system"] and "MEER TOOLS:" not in eerste["system"]
    # Het gesprek van de beurt blijft: de aanroep en zijn resultaat staan in de historie van de tweede ronde.
    [resultaat] = [b for m in tweede["messages"] if isinstance(m["content"], list)
                   for b in m["content"] if b.get("type") == "tool_result"]
    assert "extra tools" in resultaat["content"] and not resultaat.get("is_error")
    assert "".join(e["content"] for e in events if e["type"] == "token") == "Antwoord."


def test_een_tool_buiten_de_kernset_kan_alleen_na_de_overdracht():
    """Roept het model een tool aan die het niet kreeg, dan voert de code hem niet uit."""
    from agent.nodes.antwoord import BUITEN_PROFIEL

    graph = FakeGraph(result="")
    llm = FakeLLM([response([tool_block("t1", "geldigheid", {"bwb_id": "BWBR0004770"})], "tool_use"),
                   response([text_block("Antwoord.")], "end_turn")])
    _run(answer_stream(VRAAG, settings=make_settings(centrale_agent="meten"), llm=llm, graph=graph, agentvorm="centraal"))
    [resultaat] = [b for m in llm.calls[1]["messages"] if isinstance(m["content"], list)
                   for b in m["content"] if b.get("type") == "tool_result"]
    assert resultaat["content"] == BUITEN_PROFIEL and "meer_tools" in BUITEN_PROFIEL
    assert not graph.queries, "de tool is niet uitgevoerd"
    # Het brede profiel mag hem wel; een gewone specialist wordt hier niet op getoetst (bitgelijk met de supervisor).
    assert agent_voor(CENTRAAL_BREED).mag("geldigheid") and not agent_voor(CENTRAAL).mag("geldigheid")
    assert agent_voor(CENTRAAL).mag("get_artikel") and agent_voor(CENTRAAL).mag("antwoord_duiding")
    assert agent_voor("definitie").mag("geldigheid") and agent_voor("algemeen").mag("wat_dan_ook")


def test_de_eigen_tools_hebben_een_eigen_categorie_in_de_contextopbouw():
    from agent import contextdelen

    for naam in overdracht.OVERDRACHT:
        assert contextdelen.tool_categorie(naam) == contextdelen.AGENTTOOLS
    assert contextdelen.AGENTTOOLS in contextdelen.VOORVOEGSEL
