"""Het denkproces weerspiegelt de beurt één op één (E2E Rekeningafspraken 16 nov 2026, hoofdstuk *Het denkproces*).

De E2E vond regels die ontbraken (resultaten van gebeurde stappen, een geweigerde stap, de uitkomst van een subagent),
regels met een gat ("(art. )"), dubbele regels en regels over een stap die niet gebeurde. Deze tests toetsen het
mechanisme, niet één bepaling: beurten door de hele graaf, en voor elke uitgevoerde aanroep, elke weigering en elke
subagent een regel. De vorm (geen lege plekken) toetst `tests/conftest.py` voor de hele suite.
"""
from __future__ import annotations

import asyncio
import itertools
import json
from types import SimpleNamespace

import pytest

from agent import narratie, profielen, spoorbronnen as sb, subagent as sub
from agent.agent import answer_stream
from agent.narratie import STATUSTEKEN, denk_bij, doel_in_woorden, kindregel, lege_plekken
from agent.nodes import antwoord as antwoordnodes
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block
from test_subagent import ARTIKEL, OPDRACHT, STATE, Api, _kinderen

IRI = "urn:bwb:BWBR0004770:artikel:9"
GRAAF = f'?regeling\t?citeertitel\n<{IRI}>\t"Invorderingswet 1990"\n'


def _run(gen):
    async def alles():
        return [e async for e in gen]
    return asyncio.run(alles())


def _regels(events: list[dict]) -> list[str]:
    denk = ""
    for e in events:
        denk = denk_bij(denk, e)
    return [r.removeprefix(STATUSTEKEN) for r in denk.split("\n") if r.startswith(STATUSTEKEN)]


def _eind(events: list[dict]) -> list[dict]:
    return [e for e in events if e.get("type") == "tool_execution" and e.get("phase") == "end"]


def toets_een_op_een(events: list[dict]) -> None:
    """De generieke eis: elke aanroep die draaide heeft één resultaatregel met zijn bron als actor; elke weigering één regel
    "niet uitgevoerd"; elke regel heeft geen lege plek; geen regel staat er twee keer na elkaar."""
    eind = _eind(events)
    status = [e for e in events if e.get("type") == "status"]
    gedraaid = [e for e in eind if e.get("status") != "geweigerd"]
    geweigerd = [e for e in eind if e.get("status") == "geweigerd"]
    resultaat = [e for e in status if e.get("bron")]
    assert len(resultaat) == len(gedraaid), (
        f"{len(gedraaid)} aanroepen, {len(resultaat)} resultaatregels: {[e['message'] for e in status]}")
    assert [e["bron"] for e in resultaat] == [e.get("bron") for e in gedraaid]
    assert sum("niet uitgevoerd" in e["message"] for e in status) == len(geweigerd)
    regels = _regels(events)
    for regel in regels:
        assert not lege_plekken(regel), regel
    assert all(a != b for a, b in itertools.pairwise(regels)), regels


# --- door de hele graaf ---------------------------------------------------------------------------------------

#: Beurten van de centrale agent met verschillende tools, zoek en lees, en een ronde met meer aanroepen tegelijk.
BEURTEN = {
    "zoeken en lezen": [
        response([text_block("Ik zoek eerst."), tool_block("t1", "search_wetgeving", {"query": "uitstel"})], "tool_use"),
        response([tool_block("t2", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": "9"}),
                  tool_block("t3", "list_regelingen", {})], "tool_use"),
        response([text_block("Artikel 9 van de Invorderingswet 1990 gaat over betalen.")], "end_turn"),
    ],
    "dezelfde aanroep twee keer": [
        response([tool_block("t1", "list_regelingen", {})], "tool_use"),
        response([tool_block("t2", "list_regelingen", {})], "tool_use"),
        response([text_block("De Invorderingswet 1990.")], "end_turn"),
    ],
}


@pytest.mark.parametrize("naam", sorted(BEURTEN))
def test_elke_aanroep_heeft_zijn_regel_door_de_hele_graaf(naam):
    events = _run(answer_stream("Wat regelt de Invorderingswet 1990 over uitstel van betaling?",
                                settings=make_settings(), llm=FakeLLM(list(BEURTEN[naam])), graph=FakeGraph(result=GRAAF)))
    assert _eind(events), "de beurt riep een tool aan"
    toets_een_op_een(events)
    # Het denkproces noemt geen stap die niet gebeurde: de actieregels van Lex zonder route (die van `tools_node`) noemen
    # samen precies de aanroepen die draaiden, één deel per aanroep, in dezelfde volgorde van bron.
    delen = [d for e in events if e.get("type") == "status" and e["message"].startswith("Lex · ") and not e.get("route")
             for d in e["message"].removeprefix("Lex · ").split("; ") if d != "gebruikt wat er al is opgehaald"]
    gedraaid = [e for e in _eind(events) if e.get("status") != "geweigerd"]
    assert len(delen) == len(gedraaid), (delen, [e["tool"] for e in gedraaid])
    for deel, e in zip(delen, gedraaid, strict=True):
        assert deel == sb.toolregel({"name": e["tool"], "input": {}}).split(" ")[0] or \
            deel.split(" ")[0] == sb.toolregel({"name": e["tool"], "input": {}}).split(" ")[0], (deel, e["tool"])


def test_een_tool_buiten_het_profiel_staat_als_geweigerde_stap_in_het_denkproces():
    """D-5 voor elke weigering van `tools_node`: de stap die het model aankondigde staat erin, met waarom niet."""
    buiten = sorted(set(profielen.PROFIELEN["centraal_breed"].tools) - set(profielen.PROFIELEN["centraal"].tools)
                    - {"subagent", "regie_plan"})
    tool = next(t for t in buiten if sb.bron_van(t) is not None)
    llm = FakeLLM([
        response([text_block("Laat me dat ophalen."), tool_block("t1", tool, {"bwb_id": "BWBR0004770", "artikel": "9"})],
                 "tool_use"),
        response([text_block("Dat kan ik nu niet ophalen.")], "end_turn"),
    ], buiten_aanbod=True)  # de weigering van een tool buiten het profiel is wat hier getoetst wordt
    events = _run(answer_stream("Wat regelt de Invorderingswet 1990 over uitstel van betaling?", settings=make_settings(),
                                llm=llm, graph=FakeGraph(result=GRAAF)))
    toets_een_op_een(events)
    assert any("niet uitgevoerd: deze tool hoort niet bij de agent" in r for r in _regels(events))


def test_een_weigering_na_een_subagent_staat_in_het_denkproces(monkeypatch):
    """D-5: "Laat me eerst artikel 7a lid 4 ophalen", geweigerd met `na_subagent`, en het denkproces zweeg."""
    events: list[dict] = []
    monkeypatch.setattr(antwoordnodes, "get_stream_writer", lambda: events.append)
    # Sinds B-3 mag de centrale agent na een rapport twee bepalingen nalezen; zoeken en een derde bepaling niet.
    zoek = {"id": "t1", "name": "search_wetgeving", "input": {"query": "betalingsregeling"}}
    lid = {"id": "t2", "name": "get_lid", "input": {"bwb_id": "BWBR0004770", "artikel": "7a", "lid": "4"}}
    state = {"pending_tools": [zoek, lid], "messages": [], "source_trace": [], "specialist": "centraal", "nagelezen": 2,
             "subagenten": [{"uitkomst": "klaar", "rapport": True}], "run_id": "r"}
    antwoordnodes.tools_node(SimpleNamespace(settings=make_settings(), graph=None, stop_check=None), state)
    toets_een_op_een(events)
    regels = _regels(events)
    assert len(regels) == 2 and all("niet uitgevoerd" in r for r in regels), regels
    assert "na de subagent leest Lex niet zelf opnieuw" in regels[0]
    assert regels[1].startswith("Lex · leest artikel 7a, lid 4") and "hoogstens twee bepalingen" in regels[1]


# --- de resultaatregel ----------------------------------------------------------------------------------------

def test_elke_aanroep_heeft_een_uitkomst_ook_een_gelezen_stuk_zonder_bijzonderheden():
    """D-2/D-3: een gelezen stuk zonder "deels" zweeg; nu zegt elke uitgevoerde aanroep wat hij opleverde."""
    tools = {t["name"] for t in __import__("agent.tools", fromlist=["TOOLS"]).TOOLS}
    for tool in sorted(tools):
        if sb.bron_van(tool) is None:
            continue
        for eind in ({"status": "ok", "aantal": 0}, {"status": "ok", "aantal": 3}, {"status": "ok", "aantal": None},
                     {"status": "ok", "aantal": 2, "has_more": True}):
            regel = sb.uitkomstregel(tool, {"id": "kst-34002-3", "bwb_id": "BWBR1", "artikel": "9"}, eind, {})
            assert regel and not lege_plekken(regel), (tool, eind, regel)


def test_zoeken_binnen_een_stuk_telt_de_treffers_per_stuk():
    """D-2: twee zoekacties in twee stukken; van het ene stond alleen dat het iets opleverde."""
    regel = sb.uitkomstregel("get_kamerstuk", {"id": "kst-34002-G", "woorden": "rente"}, {"status": "ok", "aantal": 0}, {})
    assert regel == "kst-34002-G: niets gevonden"
    assert sb.uitkomstregel("get_kamerstuk", {"id": "kst-34002-3", "woorden": "rente"}, {"status": "ok", "aantal": 6},
                            {}) == "kst-34002-3: 6 gevonden"
    assert sb.uitkomstregel("get_uitspraak", {"id": "ECLI:NL:HR:2020:1"}, {"status": "ok", "aantal": 4}, {}) == \
        "ECLI:NL:HR:2020:1 gelezen"


def test_zoekacties_met_een_ander_filter_heten_anders():
    """D-8: drie zoekacties op dossier 34002 met een ander soort stuk heetten drie keer hetzelfde. Voor elke connector:
    een filter dat het werkwoord niet noemt, komt erachter met zijn label uit de beschrijving."""
    from bronmodel.connectors import CONNECTORS

    for c in CONNECTORS.values():
        for tool in c.tools - {c.leestool}:
            filters = [a for a in c.filters if a not in sb._GEEN_AFBAKENING | {"bwb_id", "artikel"}]
            regels = {sb.toolregel({"name": tool, "input": {f: f"waarde{i}"}}) for i, f in enumerate(filters)}
            assert len(regels) == len(filters), (c.naam, tool, regels)
    a = sb.toolregel({"name": "zoek_kamerstukken", "input": {"dossier": "34002", "soort": "memorie van toelichting"}})
    b = sb.toolregel({"name": "zoek_kamerstukken", "input": {"dossier": "34002", "soort": "nota van wijziging"}})
    assert a != b and a == "zoekt de Kamerstukken van dossier 34002 (soort stuk memorie van toelichting)"


# --- subagents ------------------------------------------------------------------------------------------------

def test_de_uitkomst_van_een_subagent_staat_in_het_denkproces_van_de_ouder():
    """De stappen van het kind staan in zijn deelgesprek; wat het opleverde, hoort in de beurt die het startte."""
    deels = ("get_uitspraak", json.dumps({"status": "ok", "volledig": False, "aantal": 30, "stuk": {
        "id": "ECLI:NL:HR:2020:1", "label": "HR 2020"}, "resultaten": [{"nr": 1, "tekst": "x"}]}))
    zoek = ("zoek_uitspraken", json.dumps({"status": "ok", "volledig": True, "aantal": 2, "resultaten": [
        {"id": "ECLI:NL:HR:2020:1"}, {"id": "ECLI:NL:HR:2021:2"}]}))
    kind = {"rapport": {"status": "klaar"}, "answer": "Gedaan.", "source_trace": [zoek, ARTIKEL, deels]}
    events: list[dict] = []
    kinderen, _, _ = _kinderen(kind)
    asyncio.run(sub.voer_uit(STATE, "bepalingen_duiden", OPDRACHT, events.append, settings=None, kinderen=kinderen,
                             gestopt=lambda: False, api=Api()))
    [regel] = _regels(events)
    assert regel.startswith("Subagent (bepalingen_duiden) · klaar, met een rapport: 3 aanroepen")
    assert "(1 deels)" in regel and "1 alleen gevonden" in regel
    # Het rapport uit code zegt het ook (D-4), en de controle ziet een claim "volledig gelezen".
    assert "(deels gelezen)" in sub.gelezen_tekst(kind)
    from agent.grounding import check_grounding
    assert check_grounding("De subagent las de uitspraken volledig door.", [deels]).beweringen


@pytest.mark.parametrize("uitkomst", sorted(narratie.KIND_UITKOMST))
def test_elke_uitkomst_van_een_subagent_heeft_een_zin(uitkomst):
    regel = kindregel(uitkomst, {})
    assert regel and not lege_plekken(regel) and "_" not in regel


# --- de regels zelf -------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("doel", "tekst"), [
    ({"bwbId": "BWBR0004770", "artikel": "7a", "lid": "1", "citeertitel": "Invorderingswet 1990"},
     "artikel 7a, lid 1 (Invorderingswet 1990)"),
    ({"bron_iri": "urn:bwb:BWBR0004770:artikel:7a:lid:1"}, "artikel 7a, lid 1 (BWBR0004770)"),
    ({"bron_iri": "urn:bwb:BWBR0004770:id:abc"}, "BWBR0004770"),
    ({}, ""),
])
def test_het_doel_in_woorden_heeft_geen_gat(doel, tekst, monkeypatch):
    """D-1: een doel met alleen een `bron_iri` gaf "(art. )"."""
    from agent import overzicht
    monkeypatch.setattr(overzicht, "_REGELINGEN_CACHE", [])
    assert doel_in_woorden(doel) == tekst


@pytest.mark.parametrize("regel", ["Lex · annoteert de aangewezen bepaling (art. )", "Lex · leest None",
                                   "Lex · zoekt {zoekterm}", "Lex · leest  artikel 9", "Bron · art. 9 ,",
                                   "Lex · ", "Controle · brongetrouwheid:"])
def test_een_regel_met_een_gat_valt_op(regel):
    assert lege_plekken(regel)


def test_in_de_dienst_haalt_stap_het_gat_weg(monkeypatch):
    monkeypatch.setattr(narratie, "STRIKT", False)
    events: list[dict] = []
    narratie._stap(events.append, "Lex", "annoteert de aangewezen bepaling (art. )")
    assert events[0]["message"] == "Lex · annoteert de aangewezen bepaling"
    with pytest.raises(AssertionError):
        monkeypatch.setattr(narratie, "STRIKT", True)
        narratie._stap(events.append, "Lex", "annoteert (art. )")


def test_de_controle_na_de_correctie_zegt_of_die_iets_hielp():
    """D-5: "Correctie · antwoord bijstellen" en daarna "8 vermeldingen niet teruggevonden", zonder dat te zien was dat de
    correctie niets herstelde."""
    from agent.narratie import _grounding_melding

    rapport = SimpleNamespace(niveau="onbepaald", onbevestigd=["a", "b"], unsupported=[], niet_letterlijk=[],
                              grounded=True, cited=[], citaten=0)
    regel = antwoordnodes.na_correctie(_grounding_melding(rapport), rapport)
    assert regel.startswith("brongetrouwheid na de correctie: 2 vermelding(en)") and regel.endswith("niet hersteld")
    goed = SimpleNamespace(niveau="gegrond", onbevestigd=[], unsupported=[], niet_letterlijk=[], grounded=True,
                           cited=["x"], citaten=0)
    assert antwoordnodes.na_correctie(_grounding_melding(goed), goed) == \
        "brongetrouwheid na de correctie: 1 verwijzing gecontroleerd"
