"""De hybride annotatieketen door de echte graaf (ADR-001 PR 9), met een nep-LLM.

FakeLLM-volgorde: supervisor → ophaal-agent (tool_use) → ophaal-agent (doel-JSON) → classifier.
De classifier-nep leest de toegestane beslissingen uit de prompt – de labels bestaan pas na de
fusie – en kiest per label de eerste. Zo toetsen deze tests de keten, niet een geraden label.
"""
from __future__ import annotations

import asyncio
import json
import re
from types import SimpleNamespace

import pytest

from bron_fakes import answer_stream
from agent.jas_pipeline.classificatie import TOOL, valideer
from agent.jas_pipeline.kandidaten import GEEN_ANNOTATIE, CandidateStatus
from fakes import FakeGraph, _FakeStream, make_settings, response, text_block, tool_block

LID = "De ontvanger verleent binnen zes weken uitstel van betaling, indien de belastingplichtige daarom verzoekt."
LID_TSV = json.dumps(f'?nummer\t?tekst\t?jci\n"1"\t"{LID}"@nl\t"jci"')
DOEL_JSON = '{"bwbId":"BWBR0004770","artikel":"9","lid":"1","nummer":"","citeertitel":"IW 1990"}'
_REGEL = re.compile(r"^(C\d{3}) \| .*? \| toegestaan: ([^|]+)", re.MULTILINE)


class KetenLLM:
    """Drie vaste antwoorden, daarna een classifier die per label een beslissing kiest."""

    def __init__(self, kies=lambda toegestaan: toegestaan[0], tool_aanroep=True):
        self._responses = [
            response([text_block("WORKERS: annotatie\nPLAN: annoteer art 9 lid 1")], "end_turn"),
            response([tool_block("t1", "get_lid", {"bwb_id": "BWBR0004770", "artikel": "9", "lid": "1"})], "tool_use"),
            response([text_block(DOEL_JSON)], "end_turn"),
        ]
        self.kies, self.tool_aanroep, self.calls = kies, tool_aanroep, []

    def create(self, **kw):
        self.calls.append(kw)
        if self._responses:
            return self._responses.pop(0)
        if not self.tool_aanroep:
            return response([text_block("Ik weet het niet.")], "end_turn")
        items = [{"kandidaat": label, "beslissing": self.kies([t.strip() for t in toegestaan.split(",")]),
                  "optie": ""} for label, toegestaan in _REGEL.findall(kw["messages"][0]["content"])]
        return response([SimpleNamespace(type="tool_use", id="c1", name=TOOL, input={"beslissingen": items})],
                        "tool_use")

    def stream(self, **kw):
        """De ophaal-agent streamt; de classifier niet (die gaat via create)."""
        self.calls.append(kw)
        return _FakeStream(self._responses.pop(0))


def _draai(llm, **settings):
    async def verzamel():
        return [e async for e in answer_stream(
            "annoteer artikel 9 lid 1 van de Invorderingswet 1990",
            settings=make_settings(enable_decomposition=True, annotation_pipeline="hybrid_v1",
                                   taal_provider="null", **settings),
            llm=llm, graph=FakeGraph(result=LID_TSV))]
    return asyncio.run(verzamel())


def _elementen(events):
    return [e["element"] for e in events if e["type"] == "element"]


def test_een_classificatiecall_geen_critic_en_elementen_met_geldige_ankers():
    llm = KetenLLM()
    events = _draai(llm)
    assert len(llm.calls) == 4, "supervisor, ophaal ×2 en één classifier – geen Critic, geen herziening"
    classifier = llm.calls[3]
    assert classifier["tools"][0]["strict"] is True and classifier["tool_choice"] == {"type": "auto"}
    assert "DE DERTIEN JAS-KLASSEN" not in classifier["system"]
    elementen = _elementen(events)
    assert elementen
    doel = next(e["doel"] for e in events if e["type"] == "doel")
    segment, = doel["segmenten"]
    for el in elementen:
        a, = el["ankers"]
        assert segment["tekst"][a["start"]:a["eind"]] == a["tekst"] == el["tekst"]


def test_een_termijn_wordt_zonder_model_voorgesteld_ook_als_het_model_alles_afwijst():
    events = _draai(KetenLLM(kies=lambda _t: GEEN_ANNOTATIE))
    assert [(e["klasse"], e["tekst"]) for e in _elementen(events)] == [("Tijdsaanduiding", "binnen zes weken")]


def test_geen_tool_aanroep_gaat_via_een_nieuwe_poging_en_de_reviewer_naar_de_jurist():
    """Classifier zonder uitvoer (2 pogingen) → CLASSIFIER_ABSTAIN → gerichte reviewer, ook zonder
    uitvoer → resolver: HUMAN_REVIEW. De jurist krijgt ze geel, met alle mogelijke klassen."""
    llm = KetenLLM(tool_aanroep=False)
    events = _draai(llm)
    assert len(llm.calls) == 6                          # 3 vooraf, classifier ×2, reviewer ×1
    meting = next(e for e in events if e["type"] == "run")["run"]["instellingen"]["hybride"]["meting"]
    assert meting["llm_calls"] == 2 and meting["review_calls"] == 1
    assert meting["per_status"]["UNCERTAIN"] == 0 and meting["per_status"]["HUMAN_REVIEW"] > 0
    assert {t["regel"] for t in meting["resolutie"]} == {"R-ONGELDIG"}
    elementen = _elementen(events)
    regel = [e for e in elementen if e["tekst"] == "binnen zes weken"]
    assert regel and not regel[0]["aandacht"]            # het regelbesluit is niet betwist
    assert all(e["aandacht"] == "geel" for e in elementen if e["tekst"] != "binnen zes weken")


def test_run_draagt_de_hybride_provenance():
    run = next(e for e in _draai(KetenLLM()) if e["type"] == "run")["run"]
    inst = run["instellingen"]
    assert inst["annotation_pipeline"] == "hybrid_v1"
    h = inst["hybride"]
    assert h["taal_provider"] == "null" and h["classifier_granulariteit"] == "universeel"
    assert h["meting"]["kandidaten"] > 0 and h["meting"]["classifier_prompt"]
    assert h["meting"]["gedegradeerd"], "zonder parser hoort dat zichtbaar te zijn"


def test_granulariteit_per_familie_doet_een_call_per_familie():
    llm = KetenLLM()
    _draai(llm, classifier_granulariteit="familie")
    assert len(llm.calls) > 4


def test_ids_zijn_deterministisch_over_runs():
    a = [e["id"] for e in _elementen(_draai(KetenLLM()))]
    b = [e["id"] for e in _elementen(_draai(KetenLLM()))]
    assert a == b and len(set(a)) == len(a)


# --- de validatie van modeluitvoer ------------------------------------------------------------

def _kandidaat(label, klassen):
    from bronmodel import Span, tekst_hash
    from agent.jas_pipeline.kandidaten import Candidate, Evidence
    t = "x" * 20
    k = Candidate.maak(Span("urn:t", 0, 5, "xxxxx", tekst_hash(t)), klassen, [Evidence(detector="d", code="C")])
    return k.model_copy(update={"label": label})


def test_ongeldige_of_ontbrekende_beslissing_wordt_onzeker_met_reden():
    ks = [_kandidaat("C001", ["Voorwaarde"]), _kandidaat("C002", ["Rechtssubject"]), _kandidaat("C003", ["Operator"])]
    uit = valideer(ks, [{"kandidaat": "C001", "beslissing": "Tijdsaanduiding", "optie": ""},
                        {"kandidaat": "C002", "beslissing": "Rechtssubject", "optie": "C002.O9"}])
    assert [(b.status, b.reden.split(":")[0]) for b in uit] == [
        (CandidateStatus.UNCERTAIN, "CLASSIFIER_ONGELDIGE_KLASSE"),
        (CandidateStatus.UNCERTAIN, "CLASSIFIER_ONGELDIGE_OPTIE"),
        (CandidateStatus.UNCERTAIN, "CLASSIFIER_OMITTED")]


def test_geen_annotatie_is_een_afwijzing_door_het_model():
    [b] = valideer([_kandidaat("C001", ["Voorwaarde"])], [{"kandidaat": "C001", "beslissing": GEEN_ANNOTATIE, "optie": ""}])
    assert b.status is CandidateStatus.REJECTED and b.door == "model"


@pytest.mark.parametrize("tak", [{"enable_planning": True}, {"enable_decomposition": True}])
def test_graaf_hybride_tak_heeft_geen_critic(tak):
    from test_graafopbouw import structuur
    nodes, edges = structuur(**tak, annotation_pipeline="hybrid_v1")
    assert "hybride_annoteer" in nodes and not {"critic", "patch", "herzie", "annoteer"} & nodes
    assert ("hybride_annoteer", "emit", "", False) in edges or any(
        e[0] == "hybride_annoteer" and e[1] == "emit" for e in edges)
