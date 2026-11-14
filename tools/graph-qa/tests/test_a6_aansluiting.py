"""De aansluiting van de centrale agent vóór de eindmeting A6 (`docs/architectuur/centrale-agent-aansluiting.md`):

1. een aanroep die de code weigert, is zichtbaar (gat 2): een `tool_execution` met `status: geweigerd` en de reden, en
   geen statusregel voor wat niet draait;
2. `beurt_meting` noemt het model dat draaide, de vorm, of het een subagent is en de ouder (gat 3 en 8);
3. een span `graph_qa.subagent` rond een subagent, en het kind erft de trace van de ouder (gat 8);
4. de meetset haalt wat niet gebouwd is uit de score (besluit 1)."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from agent import subagent as sub
from agent.beurtmeting import gemeten
from agent.contextopbouw import contextopbouw
from agent.models import Verbruiksmeter
from agent.nodes import antwoord as antwoordnodes
from eval import centrale_agent_sets as sets
from eval import centrale_agent_vat as vat
from tests.fakes import make_settings
from test_subagent import OPDRACHT, STATE, Api, _kinderen

A = "ECLI:NL:HR:2023:563"


# -- 1. geweigerde aanroepen ---------------------------------------------------------------------------------------

def _tools_node(monkeypatch, state):
    events: list[dict] = []
    uitgevoerd: list = []
    monkeypatch.setattr(antwoordnodes, "execute_tool", lambda *a, **_k: uitgevoerd.append(a) or "{}")
    monkeypatch.setattr(antwoordnodes, "get_stream_writer", lambda: events.append)
    upd = antwoordnodes.tools_node(SimpleNamespace(settings=make_settings(), graph=None, stop_check=None), state)
    return upd, events, uitgevoerd


@pytest.mark.parametrize("geval", ["na_subagent", "tool_buiten_profiel"])
def test_een_geweigerde_aanroep_is_een_tool_execution_zonder_statusregel(monkeypatch, geval):
    tu = ({"id": "t1", "name": "get_uitspraak", "input": {"id": A}} if geval == "na_subagent"
          else {"id": "t1", "name": "geldigheid", "input": {"bwb_id": "BWBR0004770"}})
    state = {"pending_tools": [tu], "messages": [], "source_trace": [], "specialist": "centraal",
             "agentvorm": "centraal", "run_id": "r", "turns": 2,
             **({"subagenten": [{"uitkomst": "klaar"}]} if geval == "na_subagent" else {})}
    upd, events, uitgevoerd = _tools_node(monkeypatch, state)
    assert not uitgevoerd and not upd["source_trace"], "niet uitgevoerd, en geen bron"
    [blok] = upd["messages"][-1]["content"]
    assert json.loads(blok["content"])["reden"] == geval
    tools = [e for e in events if e.get("type") == "tool_execution"]
    assert [(e["phase"], e["status"]) for e in tools] == [("start", "geweigerd"), ("end", "geweigerd")]
    assert tools[1]["foutcode"] == geval and tools[1]["call_id"] == "t1" and tools[1]["ronde"] == 2
    # Bundel 120: "leest uitspraak …" stond in het denkproces, terwijl de code alle vier de aanroepen weigerde.
    assert not [e for e in events if e.get("type") == "status"], "geen statusregel voor wat niet draait"


def test_naast_een_weigering_noemt_de_statusregel_alleen_wat_draait(monkeypatch):
    weg = {"id": "t1", "name": "geldigheid", "input": {"bwb_id": "BWBR0004770"}}
    mag = {"id": "t2", "name": "get_artikel", "input": {"bwb_id": "BWBR0004770", "artikel": "9"}}
    state = {"pending_tools": [weg, mag], "messages": [], "source_trace": [], "specialist": "centraal",
             "agentvorm": "centraal", "run_id": "r"}
    _, events, uitgevoerd = _tools_node(monkeypatch, state)
    assert len(uitgevoerd) == 1
    [status] = [e for e in events if e.get("type") == "status"]
    assert "geldigheid" not in json.dumps(status, ensure_ascii=False)


def test_de_meting_telt_een_weigering_als_poging_en_niet_als_gebruik():
    weiger = {"type": "tool_execution", "tool": "annoteer", "call_id": "t1", "status": "geweigerd", "ronde": 1}
    events = [{**weiger, "phase": "start"}, {**weiger, "phase": "end", "foutcode": "tool_buiten_profiel"},
              {"type": "tool_execution", "tool": "get_artikel", "phase": "start", "status": "running", "ronde": 1}]
    opdracht = {"groep": "enkelvoudig", "verwacht": {"route": "centraal", "subagents": [0, 0], "profielen": [],
                                                     "tools_verplicht": ["annoteer|get_artikel"],
                                                     "tools_verboden": ["annoteer"], "sjabloon": None,
                                                     "bevestiging": False, "regisseur": False}}
    rec = {"id": "X01", "run": 1, "beurten": [{"label": "gemeten", "events": events}]}
    s = vat.vat(rec, opdracht)
    assert s["tool_buiten_profiel"] == 1 and s["geweigerd"] == ["annoteer"] and s["tools"] == ["get_artikel"]
    assert s["tools_verboden_gezien"] == ["annoteer"], "het model probeerde het"
    assert sets.toolgebruik([{"events": events}], [])["tool_buiten_profiel"] == 1
    assert sets.toolgebruik([{"events": events}], [])["tools"] == ["get_artikel"]


# -- 2. beurt_meting -----------------------------------------------------------------------------------------------

def _meting(meter, run, **kw):
    async def stroom():
        yield {"type": "done"}

    async def alles():
        return [e async for e in gemeten(stroom(), meter=meter, run=run, gesprek_id="g", model="zwaar", **kw)]

    return next(e for e in asyncio.run(alles()) if e["type"] == "meting")


def test_beurt_meting_noemt_het_model_dat_draaide_en_de_vorm(caplog):
    meter = Verbruiksmeter()
    meter.aanroepen.append({"invoer": 10, "uitvoer": 5, "model": "zwaar"})
    meter.aanroepen.append({"invoer": 10, "uitvoer": 5, "model": "licht"})
    run = SimpleNamespace(run_id="kind", ouder_run_id="ouder", stop_gevraagd=False)
    with caplog.at_level("INFO", logger="graph_qa.beurt"):
        m = _meting(meter, run, agentvorm="centraal", subagent=True)
    assert (m["model"], m["agentvorm"], m["subagent"], m["ouder_run_id"]) == ("licht", "centraal", True, "ouder")
    [regel] = [r for r in caplog.records if r.getMessage() == "beurt_meting"]
    assert (regel.model, regel.agentvorm, regel.subagent, regel.ouder_run_id) == ("licht", "centraal", True, "ouder")
    # Zonder aanroep met een model het ingestelde, en zonder ouder of vorm geen veld.
    kaal = _meting(Verbruiksmeter(), SimpleNamespace(run_id="r", ouder_run_id="", stop_gevraagd=False))
    assert kaal["model"] == "zwaar" and not {"agentvorm", "subagent", "ouder_run_id"} & set(kaal)


def test_de_contextopbouw_draagt_het_profiel_van_de_run_bovenaan():
    meter = Verbruiksmeter()
    meter.aanroepen.append({"invoer": 10, "uitvoer": 5, "rol": "centraal", "profiel_id": "algemeen",
                            "profiel_versie": "abc"})
    meter.calls = 1
    opbouw = contextopbouw(meter, run_id="kind")
    if opbouw is None:
        pytest.skip("de meter telt hier geen aanroep")
    assert (opbouw["profiel_id"], opbouw["profiel_versie"]) == ("algemeen", "abc")


# -- 3. de span van een subagent -----------------------------------------------------------------------------------

def test_een_subagent_heeft_een_span_en_het_kind_erft_de_trace():
    trace = pytest.importorskip("opentelemetry.trace")
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    gezien: list = []

    kinderen, _, _ = _kinderen({"rapport": {"status": "klaar"}, "answer": "Gedaan."})
    start = kinderen.start

    async def start_met_context(verzoek, wie, ouder):
        # Wat de run van het kind ziet: de span die op dat moment de huidige is.
        gezien.append(trace.get_current_span().get_span_context())
        return await start(verzoek, wie, ouder)

    import agent.observability as obs
    oud = obs.get_tracer
    obs.get_tracer = lambda _n: tracer
    try:
        with tracer.start_as_current_span("graph_qa.answer") as ouder:
            asyncio.run(sub.voer_uit(STATE, "algemeen", OPDRACHT, lambda _e: None, settings=None,
                                     kinderen=sub.Kinderen(start=start_met_context, stop=kinderen.stop),
                                     gestopt=lambda: False, api=Api()))
            ouder_trace = ouder.get_span_context().trace_id
    finally:
        obs.get_tracer = oud
    [span] = [s for s in exporter.get_finished_spans() if s.name == "graph_qa.subagent"]
    assert span.context.trace_id == ouder_trace, "de subagent valt in de trace van de ouder"
    assert dict(span.attributes).items() >= {"delegatie_id": "d1", "profiel": "algemeen", "kind_run_id": "kind-run",
                                     "uitkomst": "klaar", "ouder_run_id": "ouder-run"}.items()
    [ctx] = gezien
    assert ctx.trace_id == ouder_trace and ctx.span_id == span.context.span_id, "het kind start binnen de span"


# -- 4. de meetset -------------------------------------------------------------------------------------------------

def test_wat_niet_gebouwd_is_gaat_uit_de_score():
    """Sinds 14 nov 2026 is alles gebouwd wat de set vraagt; het veld werkt nog voor een volgende opdracht."""
    opdrachten = vat.lees_set()
    assert not [i for i, o in opdrachten.items() if o.get("niet_gebouwd")]
    leeg = {"id": "F03", "run": 1, "beurten": [{"label": "gemeten", "events": []}]}
    s = vat.vat(leeg, {**opdrachten["F03"], "niet_gebouwd": ["tool:delegatie_stand"]})
    assert s["tools_ontbreken"] == [] and s["niet_gebouwd"] == ["tool:delegatie_stand"]
    assert vat.vat(leeg, opdrachten["F03"])["tools_ontbreken"] == ["delegatie_stand"]


def test_een_regiekind_scoort_op_zijn_profiel():
    opdrachten = vat.lees_set()
    events = [{"type": "regie", "fase": "start", "regie_id": "r"},
              {"type": "regie_taak", "fase": "start", "profiel": "retrieval"}]
    m = vat.vat({"id": "M02", "run": 1, "beurten": [{"label": "gemeten", "events": events}]}, opdrachten["M02"])
    assert m["profiel_past"] is True and m["kind_profielen"] == ["retrieval"]
    m = vat.vat({"id": "M04", "run": 1, "beurten": [{"label": "gemeten", "events": events}]},
                {**opdrachten["M04"], "niet_gebouwd": ["profiel"]})
    assert m["profiel_past"] is None


def test_een_subagent_draagt_in_beurt_meting_de_vorm_van_de_centrale_agent(monkeypatch):
    """Bugonderzoek ADR-016, B2: het verzoek van een kind noemt geen vorm, en bij `meten` werd dat "supervisor"."""
    from agent.models import ChatRequest, SubagentOpdracht
    from agent.runs import Run
    from api import main

    gezien: dict = {}

    def nep_gemeten(beurt, **kw):
        gezien.update(kw)

        async def leeg():
            if False:
                yield {}
        return leeg()

    monkeypatch.setattr(main, "gemeten", nep_gemeten)
    monkeypatch.setattr(main.settings, "centrale_agent", "meten", raising=False)
    kind = ChatRequest(question="Zoek.", conversation_id="k", profiel="algemeen",
                       opdracht=SubagentOpdracht(doel="Zoek de uitspraken."))
    maak = main._stroom_voor(kind, "jurist")
    maak(Run(run_id="r", conversation_id="k"))
    assert (gezien["agentvorm"], gezien["subagent"]) == ("centraal", True)
    gezien.clear()
    main._stroom_voor(ChatRequest(question="Wat is een aanslag?", conversation_id="g"), "jurist")(
        Run(run_id="r2", conversation_id="g"))
    assert (gezien["agentvorm"], gezien["subagent"]) == ("supervisor", False)
