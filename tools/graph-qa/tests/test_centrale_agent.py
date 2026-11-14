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


#: De overdrachten die elk profiel van de centrale agent heeft, naast wijs_af (en meer_tools in de kernset).
VASTE_ROUTES = ("taakagent", "werkgebied", "toon_bepaling", "toon_overzicht", "lees_annotaties", "lees_begrippen",
                "toon_stukken")

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
    assert "overdracht" not in uit.nodes and "subagent_vervolg" not in uit.nodes
    for stand in ("meten", "aan"):
        g = build_graph(make_settings(centrale_agent=stand), FakeLLM([]), FakeGraph())
        # De overdracht, en de klik op de vraagkaart van een subagent (ADR-016 §A4).
        assert set(g.nodes) == set(uit.nodes) | {"overdracht", "subagent_vervolg", "subagent_plan", "regie_voorstel",
                                                 "subagent_route"}
        edges = {(e.source, e.target) for e in g.compile().get_graph().edges}
        oud = {(e.source, e.target) for e in uit.compile().get_graph().edges}
        assert edges - oud == {("agent", "overdracht"), ("overdracht", "agent"), ("overdracht", "afwijzen"),
                               ("overdracht", "agent_taak"), ("overdracht", "werkgebied_intake"),
                               ("overdracht", "bronselectie"), ("overdracht", "bepaling_lezen"),
                               ("overdracht", "overzicht_bouwen"), ("overdracht", "annotaties_zoeken"),
                               ("overdracht", "begrippen_zoeken"), ("overdracht", "bron_lijst"),
                               ("supervisor", "subagent_vervolg"), ("advance", "subagent_vervolg"),
                               ("subagent_vervolg", "agent"), ("subagent_vervolg", "__end__"),
                               ("overdracht", "subagent_plan"), ("subagent_plan", "__end__"),
                               ("overdracht", "regie_voorstel"), ("regie_voorstel", "__end__"),
                               ("supervisor", "subagent_route"), ("advance", "subagent_route"),
                               ("subagent_route", "agent")}
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
    assert {"wijs_af", "meer_tools", "subagent", "subagenten", "regie_plan", "hervat_subagent", "get_artikel", "zoek_definitie", "get_context", "antwoord_duiding",
            "antwoord_begrip"} <= namen
    assert not namen & {"rapport", "search_annotaties", "geldigheid", "raw_sparql"}
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
    assert set(agent.eigen_tools) == set(overdracht.OVERDRACHT) == {"wijs_af", "meer_tools", "subagent", "subagenten", "regie_plan", "hervat_subagent", *VASTE_ROUTES}
    p = profielen.PROFIELEN[CENTRAAL]
    assert not p.kiesbaar and CENTRAAL not in profielen.KIESBAAR, "een model kiest dit profiel niet"
    # De eigen tools staan niet in de toollaag: een profiel kan ze niet noemen, en een andere agent krijgt ze niet.
    assert not set(overdracht.OVERDRACHT) & profielen.grenzen().tools
    for naam in set(profielen.PROFIELEN) - {CENTRAAL, CENTRAAL_BREED}:
        assert type(agent_voor(naam)) is Agent and not agent_voor(naam).eigen_tools
        # Ook als subagent: één laag, geen overdracht en geen `subagent` (ADR-016 §A1).
        assert not agent_voor(naam, subagent=True).eigen_tools


def test_een_overdrachtstool_heeft_een_strict_schema():
    """Behalve de delegatietools: die zijn niet strict om de grammatica van het verzoek klein te houden
    (`tests/test_strict_grenzen.py`). Hun schema heeft wel dezelfde vorm."""
    for o in overdracht.OVERDRACHT.values():
        s = o.schema
        assert s["strict"] is (o.naam not in {"subagent", "subagenten", "regie_plan", "hervat_subagent"})
        assert s["input_schema"]["additionalProperties"] is False
        assert s["input_schema"]["required"] == sorted(o.invoer)
        assert all(n in overdracht.doelen() for n in (o.ingangen if o.naar == overdracht.INGANG else (o.naar,)))


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
    # De kernset op gebruik (de nulmeting en de rondes van A2): wat een gewone vraag draagt.
    assert kern == {"search_wetgeving", "get_artikel", "get_lid", "list_regelingen", "get_bepaling", "zoek_opbouw",
                    "inhoudsopgave", "get_context", "follow_verwijzingen", "zoek_definitie", "get_regeling_info"}


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


def test_een_keuzevraag_van_de_centrale_agent_heeft_de_vorm_die_de_doorvraagroute_herkent():
    """De doorvraagroute in code (R3) herkent een open keuzevraag aan haar vorm ("Bedoel je …?"). De specialisten
    schreven die vorm; de centrale agent niet altijd, en dan ging een vervolg ("En het tweede lid?") naar het model in
    plaats van naar de vaste doorvraag (ronde 2 van A2, gesprek v-artikel-zonder-wet). De instructie legt de vorm vast."""
    from agent.verduidelijken import doorvraag, open_keuzevraag

    voorbeeld = "Bedoel je artikel 3:1, 3:2, of een ander artikel?"
    for naam in (CENTRAAL, CENTRAAL_BREED):
        assert "NIET GOKKEN" in profielen.PROFIELEN[naam].instructie and voorbeeld in profielen.PROFIELEN[naam].instructie
    assert open_keuzevraag("De Awb heeft geen artikel 3. " + voorbeeld) == voorbeeld
    assert doorvraag("En het tweede lid?", "De Awb heeft geen artikel 3. " + voorbeeld)


def test_meer_tools_is_er_alleen_voor_de_kernset_en_wijs_af_voor_beide():
    assert set(agent_voor(CENTRAAL).eigen_tools) == {"wijs_af", "meer_tools", "subagent", "subagenten", "regie_plan", "hervat_subagent", *VASTE_ROUTES}
    assert set(agent_voor(CENTRAAL_BREED).eigen_tools) == {"wijs_af", "subagent", "subagenten", "regie_plan", "hervat_subagent", *VASTE_ROUTES}
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


# --- de taakagents en het werkgebied (A2-3a) --------------------------------------------------------------------
# Meetronde S6 (13 nov 2026): de centrale agent bereikte de deelvragen-agent en het aanvullen van het werkgebied niet;
# "stel deelvragen voor" werd vrije tekst. De overdrachten gaan naar dezelfde routes als de keuze van de supervisor.

def _werkgebiedbeurt(vraag: str, llm: FakeLLM) -> list[dict]:
    from tests.test_agents import NepApi, _api_settings

    async def verzamel():
        return [e async for e in answer_stream(vraag, None, settings=_api_settings(centrale_agent="meten"), llm=llm,
                                               graph=FakeGraph(), user_id="jurist", run_id="r1", werkgebied_id="wg1",
                                               agent_api=lambda s, u: NepApi(), agentvorm="centraal")]
    return asyncio.run(verzamel())


def test_een_taak_van_de_deelvragenagent_gaat_naar_dezelfde_route_als_bij_de_supervisor():
    llm = FakeLLM([response([tool_block("t1", "taakagent", {"agent": "deelvragen", "taak": "dekking"})], "tool_use")])
    events = _werkgebiedbeurt("Hoe sta ik ervoor met deelvraag 2?", llm)
    assert len(llm.calls) == 1 and "rol agent" in llm.calls[0]["system"], "één ronde van de centrale agent, geen supervisor"
    assert any(e["type"] == "status" and e.get("route") == "deelvragen" for e in events)
    token = "".join(e["content"] for e in events if e["type"] == "token")
    assert token.startswith("Dekking in werkgebied *Invorderbaarheid*") and "Wanneer vervalt" not in token


def test_een_taak_die_niet_bij_de_agent_hoort_weigert_de_code():
    llm = FakeLLM([response([tool_block("t1", "taakagent", {"agent": "begrippen", "taak": "dekking"})], "tool_use"),
                   response([text_block("Welke deelvraag bedoel je?")], "end_turn")])
    events = _werkgebiedbeurt("Hoe sta ik ervoor met deelvraag 2?", llm)
    assert len(llm.calls) == 2
    [resultaat] = [b for m in llm.calls[1]["messages"] if isinstance(m["content"], list)
                   for b in m["content"] if b.get("type") == "tool_result"]
    assert resultaat["is_error"] is True and "voorstellen" in resultaat["content"] and "relaties" in resultaat["content"]
    assert not any(e["type"] == "status" and e.get("route") == "deelvragen" for e in events)


@pytest.mark.parametrize(("taak", "route", "stap"), [
    ("aanvullen", "werkgebied", "vult met je het dossier aan"),
    ("bronselectie", "bronselectie", "bepaalt met je de bronnen per deelvraag"),
])
def test_het_werkgebied_gaat_naar_dezelfde_route_als_bij_de_supervisor(taak, route, stap):
    llm = FakeLLM([response([tool_block("t1", "werkgebied", {"taak": taak})], "tool_use")])
    events = _werkgebiedbeurt("Kun je het praktijkvoorbeeld toevoegen?", llm)
    assert len(llm.calls) >= 1 and "rol agent" in llm.calls[0]["system"]
    assert any(e["type"] == "status" and e.get("route") == route and stap in e["message"] for e in events)


def test_de_overdrachten_volgen_de_registers():
    """De taken komen uit het register van de agents; de beschrijving noemt elke taak, zodat het model weet wanneer."""
    from agent.agents import register
    o = overdracht.OVERDRACHT["taakagent"]
    taken = {t for a in overdracht.TAAKAGENTS for t in register.taken(a)}
    assert set(o.invoer["taak"]["enum"]) == taken and set(o.invoer["agent"]["enum"]) == set(overdracht.TAAKAGENTS)
    assert all(f"{t} (" in o.beschrijving for t in taken)
    w = overdracht.OVERDRACHT["werkgebied"]
    assert all(f"{t}:" in w.beschrijving for t in overdracht.WERKGEBIED_TAKEN)


# --- de tekst van een bepaling alleen via code (A2-3b) ----------------------------------------------------------
# Meetronde S6, golden_duiding: bij "wat betekent lid X" koos de centrale agent het bepalingssjabloon (12/18 tegen 17/18).
# Dat sjabloon heeft hij niet meer; de tekst toont de workflow van de route vóór het model, via `toon_bepaling`.

def test_de_centrale_agent_heeft_het_bepalingssjabloon_niet_en_toont_de_tekst_via_code():
    for naam in (CENTRAAL, CENTRAAL_BREED):
        p = profielen.PROFIELEN[naam]
        assert "antwoord_bepaling" not in p.sjablonen and "antwoord_bepaling" not in p.instructie
        assert "toon_bepaling" in p.instructie


def _tool_resultaat(verzoek: dict) -> dict:
    [resultaat] = [b for m in verzoek["messages"] if isinstance(m["content"], list)
                   for b in m["content"] if b.get("type") == "tool_result"]
    return resultaat


def test_toon_bepaling_gaat_naar_de_bepalingsroute_en_de_terugval_is_dezelfde_agent():
    llm = FakeLLM([response([tool_block("t1", "toon_bepaling", {"bwb_id": "BWBR0004770", "artikel": "9", "lid": "2"})],
                            "tool_use"),
                   response([text_block("Antwoord.")], "end_turn")])
    events = _beurt("Geef de tekst van artikel 9 lid 2 (BWBR0004770).", llm, stand="meten", gevraagd="centraal")
    assert any(e["type"] == "status" and e.get("route") == "bepaling" for e in events)
    # De lege nepgraaf levert geen tekst: de beurt gaat terug naar de agent, en dat is de centrale agent.
    assert "rol agent" in llm.calls[-1]["system"]


@pytest.mark.parametrize(("vraag", "invoer", "reden"), [
    ("Wat betekent artikel 9 lid 2 (BWBR0004770)?", {"bwb_id": "BWBR0004770", "artikel": "9", "lid": "2"},
     "antwoord_duiding"),
    ("Geef de tekst van artikel 9 lid 2.", {"bwb_id": "Invorderingswet", "artikel": "9", "lid": "2"}, "geen BWB-id"),
    ("Geef de tekst van bepaling 25.1 (BWBR0024096).", {"bwb_id": "BWBR0024096", "artikel": "25.1", "lid": ""},
     "get_bepaling"),
])
def test_toon_bepaling_weigert_wat_geen_vraag_naar_de_tekst_is(vraag, invoer, reden):
    llm = FakeLLM([response([tool_block("t1", "toon_bepaling", invoer)], "tool_use"),
                   response([text_block("Antwoord.")], "end_turn")])
    events = _beurt(vraag, llm, stand="meten", gevraagd="centraal")
    resultaat = _tool_resultaat(llm.calls[1])
    assert resultaat["is_error"] is True and reden in resultaat["content"]
    assert not any(e["type"] == "status" and e.get("route") == "bepaling" for e in events)


def test_de_uitlegregel_is_dezelfde_als_voor_het_model():
    from agent.bepaling_workflow import _is_tekstvraag, is_uitlegvraag
    assert is_uitlegvraag("Wat betekent artikel 9 lid 2 Iw?") and not _is_tekstvraag("Wat staat er in artikel 9 lid 2? Wat betekent dat?")
    assert not is_uitlegvraag("Wat staat er in artikel 9 lid 2 Iw?") and _is_tekstvraag("Wat staat er in artikel 9 lid 2 Iw?")


# --- de routes op de herschreven vraag (A2-3c) ------------------------------------------------------------------
# In een gesprek herschreef de supervisor een vervolgvraag, en daarop draaiden de regels voor een overzicht en voor het
# lezen van annotaties en begrippen. De centrale agent herschrijft niet: hij geeft de vraag zelfstandig geformuleerd
# mee aan een overdracht, en de code draait dezelfde regel (`supervisie.NA_HERSCHRIJVEN`).

VERVOLG = [("toon_overzicht", "overzicht", "Welke artikelen gaan over verrekening?"),
           ("lees_annotaties", "annotaties", "Welke annotaties zijn er al bij artikel 9 lid 2 van de Invorderingswet 1990?"),
           ("lees_begrippen", "begrippen", "Welke begrippen hebben we al vastgelegd over de belastingschuldige?")]


def test_elke_vaste_route_draait_een_regel_van_de_supervisor_en_staat_in_het_profiel():
    from agent.nodes.supervisie import NA_HERSCHRIJVEN
    for tool, regel, _ in VERVOLG:
        assert regel in NA_HERSCHRIJVEN
        assert overdracht.OVERDRACHT[tool].schema["input_schema"]["required"] == ["vraag"]
        for naam in (CENTRAAL, CENTRAAL_BREED):
            assert tool in profielen.PROFIELEN[naam].instructie


@pytest.mark.parametrize(("tool", "route", "vraag"), [
    ("toon_overzicht", "overzicht", VERVOLG[0][2]),
    ("lees_annotaties", "annotaties_lezen", VERVOLG[1][2]),
    ("lees_begrippen", "begrippen_lezen", VERVOLG[2][2]),
])
def test_een_vervolgvraag_gaat_via_de_overdracht_naar_de_route_van_de_supervisor(tool, route, vraag):
    llm = FakeLLM([response([tool_block("t1", tool, {"vraag": vraag})], "tool_use"),
                   response([text_block("Antwoord.")], "end_turn")])
    events = _beurt("En die?", llm, stand="meten", gevraagd="centraal")
    assert "rol agent" in llm.calls[0]["system"], "de eerste ronde is de centrale agent, geen supervisor"
    assert any(e["type"] == "status" and e.get("route") == route for e in events)
    assert not any(e["type"] == "status" and e.get("route") == "afgewezen" for e in events)


def test_valt_het_overzicht_terug_dan_is_dat_de_centrale_agent():
    llm = FakeLLM([response([tool_block("t1", "toon_overzicht", {"vraag": VERVOLG[0][2]})], "tool_use"),
                   response([text_block("Antwoord.")], "end_turn")])
    _beurt("En over verrekening?", llm, stand="meten", gevraagd="centraal")
    # De lege nepgraaf bouwt geen overzicht: terug naar de agent, en dat is de centrale agent, niet `algemeen`.
    assert "rol agent" in llm.calls[-1]["system"]


@pytest.mark.parametrize(("tool", "vraag"), [
    ("toon_overzicht", "Wat betekent artikel 9 van de Invorderingswet 1990?"),
    ("lees_annotaties", "Wat betekent artikel 9 van de Invorderingswet 1990?"),
    ("lees_begrippen", "Wat betekent het begrip belastingschuldige?"),
    ("toon_overzicht", ""),
])
def test_een_vraag_die_niet_bij_de_route_past_weigert_de_code(tool, vraag):
    llm = FakeLLM([response([tool_block("t1", tool, {"vraag": vraag})], "tool_use"),
                   response([text_block("Antwoord.")], "end_turn")])
    _beurt("En dat?", llm, stand="meten", gevraagd="centraal")
    resultaat = _tool_resultaat(llm.calls[1])
    assert resultaat["is_error"] is True and "Beantwoord haar zelf" in resultaat["content"]


# --- een lijst stukken in een vervolgvraag, en de bronkeuze daarna (A2-3c-2) --------------------------------------
# "Wat is het laatste?" na een vraag over dossier 32140 noemt geen bron. De bronkeuze viel vóór de eerste ronde op de
# getypte vraag; wat daarbij alleen deze beurt buiten de keuze viel, gaat voor de lijstroute weer mee.

LAATSTE = "Wat is het laatste Kamerstuk in dossier 32140?"


def _stukken(stand: dict, vraag: str = LAATSTE, monkeypatch=None):
    from agent.nodes import supervisie
    from tests.test_na_herschrijven import _bouw

    events: list = []
    monkeypatch.setattr(overdracht, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: events.append)
    state = {"question": "Wat is het laatste?", "modus": "auto", "specialist": CENTRAAL, "bronstand": stand,
             "bronkeuze": ["rechtspraak"], "messages": []}
    b = _bouw("")
    uit = overdracht.OVERDRACHT["toon_stukken"].zet(b, state, {"vraag": vraag})
    return b, state, uit, events


def _bron(aan: bool, reden: str, label: str) -> dict:
    return {"aan": aan, "reden": reden, "label": label}


def test_een_lijst_uit_een_bron_die_deze_beurt_buiten_de_keuze_viel_zet_die_bron_weer_aan(monkeypatch):
    from agent.nodes.supervisie import _entry_node
    stand = {"kamerstukken": _bron(False, "niet_nodig", "Kamerstukken"), "rechtspraak": _bron(True, "aan", "Rechtspraak")}
    b, state, uit, events = _stukken(stand, monkeypatch=monkeypatch)
    assert uit["bron_lijst"]["connector"] == "kamerstukken" and uit["zelfstandige_vraag"] == LAATSTE
    assert uit["bronstand"]["kamerstukken"]["aan"] is True and uit["bronkeuze"] == ["kamerstukken"]
    assert uit["specialist"] == CENTRAAL
    assert any(e.get("type") == "bronstand" for e in events)
    assert _entry_node(b, {**state, **uit}) == "bron_lijst"


def test_staat_de_gevraagde_bron_uit_dan_dezelfde_melding_als_bij_de_supervisor(monkeypatch):
    from agent.nodes.supervisie import _entry_node
    stand = {"kamerstukken": _bron(False, "straat", "Kamerstukken"), "rechtspraak": _bron(True, "aan", "Rechtspraak")}
    b, state, uit, events = _stukken(stand, monkeypatch=monkeypatch)
    assert uit["afwijzen"] is True and "Kamerstukken" in uit["afwijs_melding"]
    assert any(e.get("type") == "bron_uit" for e in events)
    assert _entry_node(b, {**state, **uit}) == "afwijzen"


@pytest.mark.parametrize("vraag", ["Wat betekent artikel 9 van de Invorderingswet 1990?", ""])
def test_een_vraag_die_geen_lijstvraag_is_weigert_de_code(monkeypatch, vraag):
    stand = {"kamerstukken": _bron(True, "aan", "Kamerstukken")}
    _, _, uit, _ = _stukken(stand, vraag, monkeypatch=monkeypatch)
    assert isinstance(uit, str) and "zoektool" in uit


def test_heropend_zet_alleen_niet_nodig_terug():
    from agent import bronkeuze
    stand = {"a": _bron(False, "niet_nodig", "A"), "b": _bron(False, "straat", "B"), "c": _bron(True, "aan", "C")}
    assert bronkeuze.actief(bronkeuze.heropend(stand)) == ["a", "c"]


# --- de afrondregel gelijk aan die van de duiding-specialist (meting #1457) ----------------------------------------
# Na een weigering volgde de supervisor de melding en vulde het sjabloon (2/2); de centrale agent viel terug op tekst
# (0/2), en F04 probeerde het sjabloon niet. Het verschil zat in de instructie: duiding zegt "je schrijft geen antwoord
# in tekst", centraal had een ruimere uitweg naar tekst.

def test_de_centrale_agent_heeft_de_afrondregel_van_de_duiding_specialist():
    duiding = profielen.PROFIELEN["duiding"].instructie
    assert "je schrijft geen antwoord in tekst" in duiding
    for naam in (CENTRAAL, CENTRAAL_BREED):
        p = profielen.PROFIELEN[naam].instructie
        assert "je schrijft geen antwoord in tekst" in p
        assert "Weigert de code het sjabloon, verbeter dan de aanroep" in p
        assert "of gaat de vraag om iets wat in geen sjabloon past" not in p
