"""V2 regressies met een echte bronboom en gescheiden API/graaf-poorten."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from bronmodel import bouw_snapshot

from agent.agent import answer_stream
from agent.annotatie import _verwerk, pas_critic_toe
from agent.annotatie_read import AnnotatieReadApi
from agent.bron_annotatie import corpus_segmenten, lokale_elementen
from agent.grounding import check_grounding
from agent.provenance import collect_sources
from agent.tools import anthropic_schemas, dispatch
from agent.tools.annotatie_tools import ANNOTATIE_TOOL_NAMEN, is_leesvraag
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block

BWB = "BWBR0004770"
REG = f"urn:bwb:{BWB}"
ART = REG + ":artikel:9"
L1, L2 = ART + ":lid:1", ART + ":lid:2"
T1 = "Een belastingaanslag is invorderbaar zes weken na de dagtekening."
T2 = "De ontvanger kan uitstel van betaling verlenen."
ROWS = [
    {"node": REG, "type": "Regeling", "nummer": "", "tekst": ""},
    {"node": ART, "parent": REG, "type": "Artikel", "nummer": "9", "tekst": ""},
    {"node": L1, "parent": ART, "type": "Lid", "nummer": "1", "tekst": T1},
    {"node": L2, "parent": ART, "type": "Lid", "nummer": "2", "tekst": T2},
]


def snapshot(iri=L1, rows=None):
    return bouw_snapshot(rows or ROWS, bron_iri=iri, bwb_id=BWB)


class ReadApi:
    def __init__(self, snap, *, completed=False, status="ok", afgerond=()):
        self.snap, self.completed, self.status = snap, completed, status
        self.afgerond = list(afgerond)
        self.calls = []

    def zoeken(self, filters):
        self.calls.append(("zoeken", filters))
        return {"status": self.status, "resultaten": [], "volledig": self.status == "ok"}

    def element(self, id):
        self.calls.append(("element", id))
        return {"status": "ok", "element": {"id": id, "tekst": T1, "bron_iri": L1}}

    def dekking(self, doel):
        self.calls.append(("dekking", doel))
        return {"status": self.status, "snapshot_id": self.snap["snapshot_id"],
                "voltooid": self.completed, "parent_context": self.completed,
                "bereik": [s["bron_iri"] for s in self.snap["segmenten"]] if self.completed else []}

    def weergave(self, doel):
        self.calls.append(("weergave", doel))
        return {"schema_versie": 2, "snapshot_id": self.snap["snapshot_id"], "elementen": [],
                "lagen": [{"id": f"laag-{i}", "bron_iri": iri, "revisie": 3, "status": "geaccordeerd"}
                          for i, iri in enumerate(self.afgerond)]}


def run(gen):
    async def collect():
        return [e async for e in gen]
    return asyncio.run(collect())


def test_iw9_lid1_only_selected_source_and_local_sha256_anchor():
    snap = snapshot()
    llm = FakeLLM([
        response([text_block(json.dumps({"elementen": [{"klasse": "Rechtsobject", "tekst": "belastingaanslag"}]}))], "end_turn"),
        response([text_block('{"oordelen": [], "ontbrekend": []}')], "end_turn"),
    ])
    graph, api = FakeGraph(result=ROWS), ReadApi(snap)
    events = run(answer_stream("annoteer artikel 9 lid 1", doel={"bron_iri": L1},
                              llm=llm, graph=graph, annotaties=api, settings=make_settings(critic_max_rondes=0),
                              run_id="regressie", user_id="jurist"))
    assert not [e for e in events if e["type"] == "error"], events
    target = next(e["doel"] for e in events if e["type"] == "doel")
    assert target["bron_iri"] == L1
    assert [s["tekst"] for s in target["segmenten"]] == [T1]
    assert T2 not in target["leden_teksten"][0]["tekst"]
    element, = [e["element"] for e in events if e["type"] == "element"]
    anchor, = element["ankers"]
    assert element["eigenaar_iri"] == L1
    assert anchor["bron_iri"] == L1 and len(anchor["bron_hash"]) == 64
    assert T1[anchor["start"]:anchor["eind"]] == "belastingaanslag"
    assert "anker" not in element
    assert [c[0] for c in api.calls] == ["dekking", "weergave"]


@pytest.mark.parametrize("split", [False, True])
def test_completed_node_reuse_costs_no_model_calls(split):
    llm = FakeLLM([])
    events = run(answer_stream("annoteer lid 1", doel={"bron_iri": L1}, llm=llm,
                              graph=FakeGraph(result=ROWS), annotaties=ReadApi(snapshot(), completed=True),
                              settings=make_settings(enable_kandidaat_splitsing=split)))
    assert not [e for e in events if e["type"] == "error"], events
    assert llm.calls == []
    assert next(e["hergebruik"] for e in events if e["type"] == "hergebruik")["volledig"]
    executions = [e for e in events if e["type"] == "tool_execution"]
    assert any(e["tool"] == "get_annotatiedekking" and e["phase"] == "end" for e in executions)


def test_unknown_requested_lid_never_falls_back_to_article():
    llm = FakeLLM([])
    events = run(answer_stream("annoteer lid 99", doel={"bwbId": BWB, "artikel": "9", "lid": "99"},
                              llm=llm, graph=FakeGraph(result=ROWS), annotaties=ReadApi(snapshot()),
                              settings=make_settings()))
    assert not llm.calls
    assert not any(e["type"] in {"element", "doel", "run"} for e in events)
    assert "lid" in " ".join(e.get("content", "") for e in events)


def test_coverage_outage_does_not_trigger_new_annotation():
    llm = FakeLLM([])
    events = run(answer_stream("annoteer", doel={"bron_iri": L1}, llm=llm,
                              graph=FakeGraph(result=ROWS), annotaties=ReadApi(snapshot(), status="unavailable"),
                              settings=make_settings()))
    assert not llm.calls
    assert not any(e["type"] == "element" for e in events)
    assert any(e.get("status") == "unavailable" for e in events)


def test_multianchors_use_lca_and_same_text_in_siblings_stays_separate():
    rows = [{**r, "tekst": "De ontvanger betaalt."} if r["node"] in {L1, L2} else r for r in ROWS]
    snap = snapshot(ART, rows)
    corpus, spans = corpus_segmenten(snap["segmenten"])
    bron = {"bron_snapshot": snap, "corpus_segmenten": spans}
    def anchor(iri):
        return {"bron_iri": iri, "tekst": "De ontvanger", "start": 0, "eind": 12}
    raw = {"elementen": [
        {"klasse": "Rechtssubject", "tekst": "De ontvanger", "ankers": [anchor(L1)]},
        {"klasse": "Rechtssubject", "tekst": "De ontvanger", "ankers": [anchor(L2)]},
        {"klasse": "Afleidingsregel", "tekst": "De ontvanger\n\nDe ontvanger", "ankers": [anchor(L1), anchor(L2)]},
    ]}
    elements, rejected = _verwerk(json.dumps(raw), corpus, BWB, "9", bron=bron)
    assert not rejected
    actual = lokale_elementen([e.model_dump() for e in elements], bron)
    assert [e["eigenaar_iri"] for e in actual] == [L1, L2, ART]
    assert len(actual[-1]["ankers"]) == 2
    ambiguous, rejected = _verwerk(json.dumps({"elementen": [{"klasse": "Rechtssubject", "tekst": "De ontvanger"}]}),
                                  corpus, BWB, "9", bron=bron)
    assert not ambiguous and rejected


@pytest.mark.parametrize("decomposition", [False, True])
def test_read_route_tools_execute_api_and_emit_actual_events(decomposition):
    responses = ([response([text_block("1. Zoek bestaande annotaties")], "end_turn")] if decomposition else [])
    responses += [response([tool_block("c1", "search_annotaties", {"klasse": "Rechtssubject"})], "tool_use"),
                  response([text_block("Er zijn geen treffers binnen dit filter.")], "end_turn")]
    llm, api, graph = FakeLLM(responses), ReadApi(snapshot()), FakeGraph()
    events = run(answer_stream("zoek bestaande annotaties", doel={"bron_iri": L1},
                              llm=llm, graph=graph, annotaties=api,
                              settings=make_settings(enable_decomposition=decomposition), run_id="r1"))
    assert not [e for e in events if e["type"] == "error"], events
    assert api.calls == [("zoeken", {"klasse": "Rechtssubject"})]
    assert graph.queries == []
    assert not any(e["type"] in {"element", "doel", "run"} for e in events)
    trace = [e for e in events if e["type"] == "tool_execution"]
    assert [(e["phase"], e["call_id"]) for e in trace] == [("start", "c1"), ("end", "c1")]
    assert all(e["run_id"] == "r1" for e in trace)
    assert trace[-1]["status"] == "ok" and trace[-1]["aantal"] == 0


def test_annotation_evidence_cannot_ground_law_claim():
    data = json.dumps({"element": {"tekst": T1, "bron_iri": L1}})
    trace = [("get_annotatie", data)]
    assert collect_sources(trace) == []
    report = check_grounding(f'{BWB}: "{T1}"', trace)
    assert not report.grounded
    assert check_grounding(f'{BWB}: "{T1}"', trace + [("get_lid", T1 + BWB)]).grounded


def test_read_api_transport_failure_is_explicit_and_filter_is_not_sparql():
    def handler(request):
        assert request.url.path == "/v1/annotatie/zoeken"
        assert request.headers["x-user-id"] == "jurist"
        assert json.loads(request.content)["tekst"] == '" } SERVICE <bad> {'
        return httpx.Response(503)
    settings = make_settings(wetsanalyse_api_url="http://api", wetsanalyse_api_token="token")
    port = AnnotatieReadApi(settings, "jurist", transport=httpx.MockTransport(handler))
    result = json.loads(dispatch("search_annotaties", FakeGraph(), {"tekst": '" } SERVICE <bad> {'}, annotaties=port))
    assert result["status"] == "unavailable" and result["volledig"] is False


def test_tools_are_explicit_and_read_intent_does_not_match_annotation_request():
    assert ANNOTATIE_TOOL_NAMEN <= {s["name"] for s in anthropic_schemas()}
    assert is_leesvraag("toon opgeslagen annotaties")
    assert not is_leesvraag("annoteer dit artikel opnieuw")


@pytest.mark.parametrize("vraag", [
    # `markeringen?` maakte alleen de slot-n optioneel en matchte dus nooit het enkelvoud; een vraag
    # naar de klasse of de elementen werd helemaal niet als leesvraag herkend (22 sep 2026).
    "welke markering is een Rechtssubject?",
    "welke elementen hebben de klasse Rechtssubject?",
    "welke klasse heeft 'de ontvanger'?",
    "hoeveel elementen zijn er geclassificeerd als Rechtsobject?",
    "wat is er gemarkeerd in artikel 9?",
])
def test_vraag_naar_bestaande_markeringen_gaat_naar_de_leesroute(vraag):
    assert is_leesvraag(vraag)


@pytest.mark.parametrize("vraag", [
    "markeer en classificeer de JAS-elementen in artikel 9",   # opdracht, geen vraag
    "voeg een element toe",
    "verwijder de markering",
    "wat zegt artikel 9 lid 1?",                                # gewone wetsvraag
    "welke voorwaarde geldt voor uitstel van betaling?",        # klassenaam is ook gewone taal
])
def test_schrijfopdracht_en_wetsvraag_blijven_buiten_de_leesroute(vraag):
    assert not is_leesvraag(vraag)


def test_mcp_uses_trusted_actor_and_rejects_model_supplied_identity(monkeypatch):
    from agent import mcp_server
    calls = []
    class Port(ReadApi):
        def __init__(self, settings, user_id):
            super().__init__(snapshot())
            calls.append(user_id)
    monkeypatch.setattr(mcp_server, "AnnotatieReadApi", Port)
    settings = make_settings(annotatie_read_user_id="configured-user")
    graph = FakeGraph()
    result = json.loads(mcp_server.dispatch_mcp("search_annotaties", {}, graph, settings))
    assert result["status"] == "ok" and calls == ["configured-user"]
    rejected = mcp_server.dispatch_mcp("search_annotaties", {"user_id": "someone-else"}, graph, settings)
    assert json.loads(rejected)["status"] == "invalid_request"
    assert not graph.queries


@pytest.mark.parametrize("status", [401, 403, 503])
def test_read_api_auth_errors_are_not_empty_success(status):
    port = AnnotatieReadApi(make_settings(wetsanalyse_api_url="http://api", wetsanalyse_api_token="token"),
                           "jurist", transport=httpx.MockTransport(lambda request: httpx.Response(status)))
    result = port.zoeken({})
    assert result["status"] == "unavailable" and result["http_status"] == status
    assert result["volledig"] is False and "resultaten" not in result


def test_unknown_identity_fails_before_transport():
    def fail(request):
        raise AssertionError("No actor was configured")
    port = AnnotatieReadApi(make_settings(wetsanalyse_api_url="http://api", wetsanalyse_api_token="token"),
                           transport=httpx.MockTransport(fail))
    assert port.zoeken({})["reden"] == "annotatie_gebruikerscontext_ontbreekt"


@pytest.mark.parametrize("status", [409, 422])
def test_invalid_search_requests_are_not_outages_or_empty_results(status):
    port = AnnotatieReadApi(make_settings(wetsanalyse_api_url="http://api", wetsanalyse_api_token="token"),
                           "jurist", transport=httpx.MockTransport(lambda request: httpx.Response(status)))
    result = port.zoeken({})
    assert result["status"] == "invalid_request" and "resultaten" not in result
    assert "begin_opnieuw" in result["reden"] if status == 409 else result["reden"] == "ongeldige_zoekargumenten"


def test_invalid_tool_schema_is_typed_and_does_not_execute():
    api = ReadApi(snapshot())
    result = json.loads(dispatch("search_annotaties", FakeGraph(), {"limit": -1}, annotaties=api))
    assert result["status"] == "invalid_request" and result["volledig"] is False
    assert api.calls == []


def test_worker_health_exposes_required_annotation_contract():
    from api.main import health
    assert asyncio.run(health())["annotatie_contract_versie"] == "2"


def test_empty_or_failed_tool_evidence_cannot_be_reported_as_no_annotations():
    from agent.tools.annotatie_tools import begrens_antwoord
    assert "niet kunnen raadplegen" in begrens_antwoord("Geen annotaties.", [])
    output = begrens_antwoord("Geen annotaties.", [("search_annotaties", '{"status":"unavailable"}')])
    assert "betekent niet" in output and not output.startswith("Geen annotaties")


def test_server_persists_node_target_and_actual_tool_trace_with_batch(monkeypatch):
    from agent import beurt
    snap = snapshot()
    saved = {}
    class WriterApi:
        def __init__(self, *args):
            pass
        async def zet_bronnode_batch(self, data):
            saved["batch"] = data
            return {"doel": data["doel"], "snapshot_id": data["snapshot_id"]}
        async def voeg_bericht_toe(self, id, message):
            saved["bericht"] = message
        async def aclose(self):
            pass
    monkeypatch.setattr(beurt, "WetsanalyseApi", WriterApi)
    writer = beurt.BeurtSchrijver()
    writer.verwerk({"type": "doel", "doel": {"schema_versie": 2, "bron_iri": L1,
                    "snapshot_id": snap["snapshot_id"], "label": "Lid 1", "bereik": [L1],
                    "verwachte_revisies": {L1: 3}}})
    writer.verwerk({"type": "run", "run": {"modus": "nieuw"}})
    writer.verwerk({"type": "tool_execution", "tool": "get_annotatiedekking", "call_id": "c1", "phase": "end"})
    writer.verwerk({"type": "element", "element": {"id": "e1", "klasse": "Rechtsobject", "tekst": T1,
                    "ankers": [{"bron_iri": L1, "tekst": T1, "start": 0, "eind": len(T1),
                                "bron_hash": snap["segmenten"][0]["bron_hash"]}]}})
    writer.verwerk({"type": "suggestie", "suggestie": {"element_id": "human-7",
                    "aandacht": "geel", "motivatie": "Controleer de klasse"}})
    events = run(beurt._leg_vast(writer, settings=make_settings(), run=SimpleNamespace(run_id="r1"),
                                gesprek_id="g1", gestopt=False, user_id="jurist"))
    assert saved["batch"]["suggesties"] == [{"element_id": "human-7", "aandacht": "geel",
                                            "motivatie": "Controleer de klasse"}]
    assert saved["batch"]["batch_id"] == "r1"
    assert saved["batch"]["verwachte_revisies"] == {L1: 3}
    assert saved["batch"]["dekking"] == {"voltooid": True, "bereik": [L1], "parent_context": True}
    assert saved["bericht"]["annotatie_doel"]["bron_iri"] == L1
    assert saved["bericht"]["tool_executions"][0]["call_id"] == "c1"
    assert events[-1]["annotatie_doel"]["bron_iri"] == L1


def test_local_critic_correction_cannot_jump_to_same_quote_in_another_node():
    snap = snapshot(ART)
    corpus, spans = corpus_segmenten(snap["segmenten"])
    bron = {"bron_snapshot": snap, "corpus_segmenten": spans}
    proposals, _ = _verwerk(json.dumps({"elementen": [{"klasse": "Rechtsobject", "tekst": T1}]}),
                            corpus, BWB, "9", bron=bron)
    old = proposals[0].model_dump()
    changed, _, _ = pas_critic_toe([old], [{"id": old["id"], "aandacht": "rood", "actie": "vervang",
                                         "voorstel_tekst": "De ontvanger"}], corpus)
    assert changed[0]["tekst"] == T1
    assert changed[0]["ankers"][0]["bron_iri"] == L1


@pytest.mark.parametrize("batch_fails", [True, False])
def test_write_conflict_and_saved_annotation_chat_failure_are_distinguished(monkeypatch, batch_fails):
    from agent import beurt
    from agent.wetsanalyse_api import WetsanalyseApiFout
    class Api:
        def __init__(self, *args):
            pass
        async def zet_bronnode_batch(self, data):
            if batch_fails:
                raise WetsanalyseApiFout("conflict", 409)
            return {}
        async def voeg_bericht_toe(self, id, message):
            raise WetsanalyseApiFout("chat offline", 503)
        async def aclose(self):
            pass
    monkeypatch.setattr(beurt, "WetsanalyseApi", Api)
    writer = beurt.BeurtSchrijver()
    writer.doel = {"schema_versie": 2, "bron_iri": L1, "snapshot_id": "s", "bereik": [L1]}
    writer.run = {"modus": "nieuw"}
    events = run(beurt._leg_vast(writer, settings=make_settings(), run=SimpleNamespace(run_id="r1"),
                                gesprek_id="g1", gestopt=False, user_id="jurist"))
    assert len(events) == 1 and events[0]["type"] == "error"
    if batch_fails:
        assert events[0]["foutcode"] == "annotatie_conflict"
        assert "annotatie_doel" not in events[0]
    else:
        assert events[0]["annotatie_doel"]["bron_iri"] == L1
        assert "is bewaard" in events[0]["message"]


@pytest.mark.parametrize("split", [False, True])
def test_current_api_human_marking_receives_critic_advice_without_client_context(split):
    from copy import deepcopy
    from agent.bron_annotatie import bevroren_markeringen
    snap = snapshot()
    human = {"id": "mens-1", "herkomst": "mens", "klasse": "Rechtsobject", "tekst": T1,
             "eigenaar_iri": L1, "lifecycle": "human_approved", "ankers": [
                 {"bron_iri": L1, "start": 0, "eind": len(T1), "tekst": T1,
                  "bron_hash": snap["segmenten"][0]["bron_hash"]}]}
    original = deepcopy(human)
    class HumanApi(ReadApi):
        def weergave(self, doel):
            return {**super().weergave(doel), "elementen": [human],
                    "lagen": [{"bron_iri": L1, "revisie": 7, "status": "geaccordeerd"}]}
    replies = [response([text_block('{"elementen": []}')], "end_turn"),
               response([text_block(json.dumps({"oordelen": [{"id": "mens-1", "aandacht": "rood",
                   "motivatie": "Controleer de klasse", "actie": "vervang", "voorstel_klasse": "Rechtsfeit"}],
                   "ontbrekend": []}))], "end_turn")]
    if split:
        replies.insert(0, response([text_block('{"kandidaten": []}')], "end_turn"))
    llm = FakeLLM(replies)
    events = run(answer_stream("beoordeel annotaties opnieuw", doel={"bron_iri": L1},
        hergebruik="opnieuw", llm=llm, graph=FakeGraph(result=ROWS), annotaties=HumanApi(snap),
        settings=make_settings(critic_max_rondes=0, enable_kandidaat_splitsing=split)))
    assert human == original
    assert not [e for e in events if e["type"] == "element"]
    suggestions = [e["suggestie"] for e in events if e["type"] == "suggestie"]
    assert suggestions and suggestions[0]["element_id"] == "mens-1"
    assert suggestions[0]["voorstel_klasse"] == "Rechtsfeit"
    goal = next(e["doel"] for e in events if e["type"] == "doel")
    assert goal["verwachte_revisies"] == {L1: 7}
    human["ankers"][0]["bron_hash"] = "obsolete"
    assert bevroren_markeringen({"bron_snapshot": snap, "annotatie_weergave": {"elementen": [human]}}) == []


def test_node_advice_keeps_identity_and_snapshot_and_cannot_write_even_with_goal():
    from agent.models import ChatRequest
    req = ChatRequest(question="motiveer dit element", modus="advies", doel={"bron_iri": L1},
        context={"bron_iri": L1, "snapshot_id": "snapshot-from-view", "element_id": "human-7",
                 "fragment": T1, "klasse": "Rechtsobject"})
    llm = FakeLLM([
        response([tool_block("t1", "get_lid", {"bwb_id": BWB, "artikel": "9", "lid": "1"})], "tool_use"),
        response([text_block("De belastingaanslag is hier het object.")], "end_turn"),
        response([text_block("gegrond")], "end_turn"),
    ])
    api = ReadApi(snapshot())
    events = run(answer_stream(req.question, modus=req.modus, doel=req.doel, context=req.context,
        settings=make_settings(enable_decomposition=False), llm=llm,
        graph=FakeGraph(result='?tekst\n"'+T1+'"'), annotaties=api))
    assert {e["type"] for e in events}.isdisjoint({"element", "doel", "suggestie", "run"})
    assert not api.calls
    prompt = json.dumps(llm.calls[0], ensure_ascii=False)
    assert L1 in prompt and "snapshot-from-view" in prompt and "human-7" in prompt


@pytest.mark.parametrize("hergebruik", ["auto", "opnieuw"])
def test_afgeronde_bepaling_stopt_voordat_er_een_modelronde_draait(hergebruik):
    # Live gezien op 22 sep 2026: een volledige ronde op een afgeronde laag, daarna 409 en de
    # melding "probeer opnieuw". Nu stopt de beurt vóór de eerste modelcall, met de echte reden.
    llm = FakeLLM([])
    events = run(answer_stream("annoteer artikel 9 lid 1", doel={"bron_iri": L1}, llm=llm, hergebruik=hergebruik,
                              graph=FakeGraph(result=ROWS), annotaties=ReadApi(snapshot(), afgerond=[L1]),
                              settings=make_settings()))
    assert llm.calls == []
    assert not any(e["type"] in {"element", "doel", "run"} for e in events)
    tekst = " ".join(e.get("content", "") for e in events)
    assert "afgerond" in tekst and "Heropen" in tekst


def test_afgeronde_bepaling_mag_wel_hergebruikt_worden():
    llm = FakeLLM([])
    events = run(answer_stream("annoteer lid 1", doel={"bron_iri": L1}, llm=llm, graph=FakeGraph(result=ROWS),
                              annotaties=ReadApi(snapshot(), completed=True, afgerond=[L1]), settings=make_settings()))
    assert llm.calls == [] and not [e for e in events if e["type"] == "error"], events
    assert next(e["hergebruik"] for e in events if e["type"] == "hergebruik")["volledig"]


def test_afgerond_lid_telt_als_klaar_binnen_een_open_artikel():
    llm = FakeLLM([
        response([text_block(json.dumps({"elementen": [
            {"klasse": "Rechtsobject", "tekst": "belastingaanslag"},
            {"klasse": "Rechtssubject", "tekst": "De ontvanger"}]}))], "end_turn"),
        response([text_block('{"oordelen": [], "ontbrekend": []}')], "end_turn"),
    ])
    events = run(answer_stream("annoteer artikel 9", doel={"bron_iri": ART}, llm=llm, graph=FakeGraph(result=ROWS),
                              annotaties=ReadApi(snapshot(ART), afgerond=[L1]),
                              settings=make_settings(critic_max_rondes=0), run_id="deels", user_id="jurist"))
    assert not [e for e in events if e["type"] == "error"], events
    # Lid 1 is afgerond: daar komt niets bij, lid 2 wordt gewoon geannoteerd.
    owners = [e["element"]["eigenaar_iri"] for e in events if e["type"] == "element"]
    assert owners == [L2]
    prompt = json.dumps(llm.calls, ensure_ascii=False, default=str)
    assert "lokaal al geannoteerd" in prompt and L1 in prompt.split("lokaal al geannoteerd", 1)[1]


def test_409_op_een_afgeronde_laag_krijgt_een_eerlijke_melding(monkeypatch):
    from agent import beurt
    from agent.wetsanalyse_api import WetsanalyseApiFout
    class Api:
        def __init__(self, *args):
            pass
        async def zet_bronnode_batch(self, data):
            raise WetsanalyseApiFout("conflict", 409, "Heropen de laag voordat je haar wijzigt.")
        async def aclose(self):
            pass
    monkeypatch.setattr(beurt, "WetsanalyseApi", Api)
    writer = beurt.BeurtSchrijver()
    writer.doel = {"schema_versie": 2, "bron_iri": L1, "snapshot_id": "s", "bereik": [L1]}
    writer.run = {"modus": "nieuw"}
    events = run(beurt._leg_vast(writer, settings=make_settings(), run=SimpleNamespace(run_id="r1"),
                                gesprek_id="g1", gestopt=False, user_id="jurist"))
    assert events[0]["foutcode"] == "annotatie_afgerond"
    assert "heropen" in events[0]["message"] and "Probeer" not in events[0]["message"]


@pytest.mark.parametrize("body,reden", [
    ({"detail": "Heropen de laag voordat je haar wijzigt."}, "Heropen de laag voordat je haar wijzigt."),
    ({"detail": {"fout": "revisie_conflict", "bron_iri": L1}}, "revisie_conflict"),
    ({"detail": [{"loc": ["body"], "input": "geheime invoer"}]}, ""),
    ({"detail": "x" * 500}, ""),
])
def test_api_reden_neemt_alleen_korte_serverteksten_over(body, reden):
    from agent.wetsanalyse_api import api_reden
    assert api_reden(httpx.Response(409, json=body)) == reden
