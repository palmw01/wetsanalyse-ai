"""Een gesprek overleeft stoppen, een crash en een toolfout (C2).

Anthropic weigert een `tool_use` zonder `tool_result` direct erna met een 400, en de checkpointer
bewaart de `tool_use` al voordat `tools_node` draait. Stoppen in de zoekronde maakte zo elke volgende
vraag in dat gesprek onmogelijk, en de melding raadde aan een nieuw gesprek te beginnen.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from agent.agent import _foutmelding, answer_stream
from agent.berichten import _schoon_messages, _trim_messages
from agent.nodes.antwoord import HERHAALD, _al_gedaan
from agent.resultaat import fout, is_fout
from eval.scoring import is_infrastructuurfout
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block

ART = {"bwb_id": "BWBR0004770", "artikel": "9"}


def _run(gen):
    async def collect():
        return [ev async for ev in gen]

    return asyncio.run(collect())


def assert_geldige_reeks(messages: list[dict[str, Any]]) -> None:
    """De regel van de provider: elk tool_use heeft direct erna zijn tool_result, en omgekeerd."""
    for i, m in enumerate(messages):
        inhoud = m.get("content")
        blokken = inhoud if isinstance(inhoud, list) else []
        gebruik = [b["id"] for b in blokken if b.get("type") == "tool_use"]
        volgend = messages[i + 1].get("content") if i + 1 < len(messages) else None
        uitkomst = {b.get("tool_use_id") for b in volgend if b.get("type") == "tool_result"} if isinstance(volgend, list) else set()
        assert set(gebruik) <= uitkomst, f"open tool_use in bericht {i}"
        for b in blokken:
            if b.get("type") == "tool_result":
                vorig = messages[i - 1].get("content") if i else None
                ids = {x.get("id") for x in vorig if x.get("type") == "tool_use"} if isinstance(vorig, list) else set()
                assert b["tool_use_id"] in ids, f"los tool_result in bericht {i}"
        assert blokken or isinstance(inhoud, str), f"leeg bericht {i}"


# --- _schoon_messages -------------------------------------------------------------------------------

def test_open_tool_use_valt_weg_en_de_tekst_ernaast_blijft():
    uit = _schoon_messages([
        {"role": "user", "content": "vraag 1"},
        {"role": "assistant", "content": [{"type": "text", "text": "Ik zoek."},
                                          {"type": "tool_use", "id": "t1", "name": "x", "input": {}}]},
        {"role": "user", "content": "vraag 2"},
    ])
    assert_geldige_reeks(uit)
    assert uit[1]["content"] == [{"type": "text", "text": "Ik zoek."}]


def test_een_bericht_met_alleen_een_open_tool_use_valt_helemaal_weg():
    uit = _schoon_messages([
        {"role": "user", "content": "vraag 1"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "x", "input": {}}]},
        {"role": "user", "content": "vraag 2"},
    ])
    assert [m["content"] for m in uit] == ["vraag 1", "vraag 2"]


def test_een_open_tool_use_aan_het_eind_valt_ook_weg():
    uit = _schoon_messages([
        {"role": "user", "content": "vraag"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "x", "input": {}}]},
    ])
    assert_geldige_reeks(uit)


def test_een_afgemaakte_ronde_blijft_ongemoeid():
    reeks = [
        {"role": "user", "content": "vraag"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "x", "input": {}},
                                          {"type": "tool_use", "id": "t2", "name": "y", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "a"},
                                     {"type": "tool_result", "tool_use_id": "t2", "content": "b"}]},
    ]
    assert _schoon_messages(reeks) == reeks


def test_alleen_het_open_deel_van_een_ronde_valt_weg():
    uit = _schoon_messages([
        {"role": "user", "content": "vraag"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "x", "input": {}},
                                          {"type": "tool_use", "id": "t2", "name": "y", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "a"}]},
    ])
    assert [b["id"] for b in uit[1]["content"]] == ["t1"]
    assert_geldige_reeks(uit)


# --- De hele beurt ----------------------------------------------------------------------------------

class StopNa:
    """Stopt bij de n-de nodegrens, of laat de node daar crashen."""

    def __init__(self, n: int, crash: bool = False) -> None:
        self.n, self.crash, self.teller = n, crash, 0

    def __call__(self) -> bool:
        self.teller += 1
        if self.teller < self.n:
            return False
        if self.crash:
            raise RuntimeError("replica weg")
        return True


def _eerste_llm() -> FakeLLM:
    return FakeLLM([
        response([text_block("Ik zoek."), tool_block("t1", "get_artikel", ART),
                  tool_block("t2", "get_artikel", {**ART, "artikel": "10"})], "tool_use"),
        response([tool_block("t3", "get_artikel", {**ART, "artikel": "11"})], "tool_use"),
        response([text_block("Antwoord 1.")], "end_turn"),
    ])


@pytest.mark.parametrize("crash", [False, True], ids=["stop", "crash"])
@pytest.mark.parametrize("moment", range(1, 11))
def test_na_elke_afbreking_is_de_volgende_beurt_een_geldige_reeks(moment: int, crash: bool, tmp_path):
    settings = make_settings(enable_planning=False, grounding_correct=False,
                             checkpoint_db_path=str(tmp_path / "cp.db"))
    graph = FakeGraph(result="<urn:bwb:BWBR0004770:artikel:9> bwb:tekst 'x' .")
    _run(answer_stream("vraag 1", "c1", settings=settings, llm=_eerste_llm(), graph=graph,
                       stop_check=StopNa(moment, crash)))
    tweede = FakeLLM([response([text_block("Antwoord 2.")], "end_turn")])
    events = _run(answer_stream("vraag 2", "c1", settings=settings, llm=tweede, graph=FakeGraph(result="")))
    assert "error" not in [e["type"] for e in events]
    naar_model = [c for c in tweede.calls if c.get("tools")]
    assert naar_model, "de tweede beurt bereikte het model niet"
    assert_geldige_reeks(naar_model[-1]["messages"])
    assert naar_model[-1]["messages"][-1]["content"] == "vraag 2"


# --- Het venster in de correctieronde ---------------------------------------------------------------

def _lopende_beurt(omvang: int) -> list[dict[str, Any]]:
    uit: list[dict[str, Any]] = [{"role": "user", "content": "vraag"}]
    for i in range(3):
        uit += [{"role": "assistant", "content": [{"type": "tool_use", "id": f"t{i}", "name": "x", "input": {}}]},
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"t{i}", "content": "b" * omvang}]}]
    return uit


def _resultaten(messages: list[dict[str, Any]]) -> list[int]:
    return [len(b["content"]) for m in messages if isinstance(m["content"], list)
            for b in m["content"] if b.get("type") == "tool_result"]


def test_de_bron_krimpt_niet_in_de_correctieronde():
    reeks = [*_lopende_beurt(8000), {"role": "assistant", "content": [{"type": "text", "text": "Fout antwoord."}]},
             {"role": "user", "content": "Let op: herstel het citaat."}]
    assert _resultaten(_trim_messages(reeks, 10_000, "vraag")) == [8000, 8000, 8000]


def test_de_vraag_valt_niet_uit_het_venster_in_de_correctieronde():
    """Roept het model in de correctieronde nieuwe tools aan, dan was het correctiebericht een geldig
    venster-begin: de vraag en de opgehaalde tekst verdwenen."""
    reeks = [*_lopende_beurt(100), {"role": "assistant", "content": [{"type": "text", "text": "Fout antwoord."}]},
             {"role": "user", "content": "Let op: herstel het citaat."},
             {"role": "assistant", "content": [{"type": "tool_use", "id": "t9", "name": "x", "input": {}}]},
             {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t9", "content": "b" * 9000}]}]
    assert _trim_messages(reeks, 1000, "vraag")[0]["content"] == "vraag"


def test_een_vraag_die_met_let_op_begint_is_gewoon_een_vraag():
    reeks = [{"role": "user", "content": "oud"}, {"role": "assistant", "content": "antwoord"},
             *[{**m, "content": "Let op: geldt dit ook?"} if i == 0 else m for i, m in enumerate(_lopende_beurt(8000))]]
    assert _resultaten(_trim_messages(reeks, 10_000, "Let op: geldt dit ook?")) == [8000, 8000, 8000]


# --- Toolfouten -------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw", [
    "Fout bij tool 'x': kapot",
    "Onbekende tool: x",
    fout("te_groot", "past niet"),
    json.dumps({"status": "unavailable", "volledig": False}),
    json.dumps({"status": "invalid_request", "volledig": False}),
])
def test_is_fout_herkent_elke_foutvorm(raw: str):
    assert is_fout(raw)


@pytest.mark.parametrize("raw", ["<urn:x> a <urn:y> .", json.dumps({"status": "ok", "resultaten": []}),
                                 json.dumps({"status": "partial"}), "[1, 2]"])
def test_is_fout_laat_een_resultaat_met_rust(raw: str):
    assert not is_fout(raw)


class GraafDieEerstFaalt(FakeGraph):
    def __init__(self, fouten: int) -> None:
        super().__init__(result="<urn:bwb:BWBR0004770:artikel:9> bwb:tekst 'x' .")
        self.fouten = fouten

    def sparql(self, query: str) -> str:
        if self.fouten > 0 and "citeertitel" not in query:
            self.fouten -= 1
            raise ValueError("tijdelijk kapot")
        return super().sparql(query)


def _tool_results(llm: FakeLLM) -> list[dict[str, Any]]:
    return [b for m in llm.calls[-1]["messages"] if isinstance(m["content"], list)
            for b in m["content"] if b.get("type") == "tool_result"]


def _herhaalde_aanroep(rondes: int) -> FakeLLM:
    return FakeLLM([*[response([tool_block(f"t{i}", "get_artikel", ART)], "tool_use") for i in range(rondes)],
                    response([text_block("Klaar.")], "end_turn")])


def test_een_tijdelijke_toolfout_mag_opnieuw_en_draagt_is_error():
    settings = make_settings(enable_planning=False, grounding_correct=False)
    graph, llm = GraafDieEerstFaalt(1), _herhaalde_aanroep(2)
    _run(answer_stream("vraag", settings=settings, llm=llm, graph=graph))
    eerste, tweede = _tool_results(llm)
    assert eerste["is_error"] is True and "Fout bij tool" in eerste["content"]
    assert "is_error" not in tweede and '"status":"ok"' in tweede["content"]
    assert HERHAALD not in tweede["content"]


def test_een_blijvende_toolfout_wordt_niet_eindeloos_herhaald():
    settings = make_settings(enable_planning=False, grounding_correct=False)
    graph, llm = GraafDieEerstFaalt(99), _herhaalde_aanroep(4)
    _run(answer_stream("vraag", settings=settings, llm=llm, graph=graph))
    assert graph.fouten == 97                        # twee pogingen, daarna het bewaarde resultaat
    laatste = _tool_results(llm)[-1]
    assert laatste["is_error"] is True and HERHAALD in laatste["content"]


def test_al_gedaan_onthoudt_een_geslaagd_resultaat():
    state = {"question": "v", "messages": [
        {"role": "user", "content": "v"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "a", "name": "x", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "a", "content": "goed"}]},
    ]}
    assert list(_al_gedaan(state).values()) == ["goed"]


# --- Foutmeldingen ----------------------------------------------------------------------------------

class Fout(Exception):
    def __init__(self, body: Any = None, status_code: int | None = None, bericht: str = "") -> None:
        super().__init__(bericht)
        self.body, self.status_code, self.message = body, status_code, bericht


def _soort(naam: str) -> type[Fout]:
    return type(naam, (Fout,), {})


def _body(soort: str, bericht: str = "x") -> dict[str, Any]:
    return {"type": "error", "error": {"type": soort, "message": bericht}}


@pytest.mark.parametrize("exc", [
    _soort("RateLimitError")(),
    _soort("OverloadedError")(),
    _soort("ServiceUnavailableError")(),
    _soort("APIStatusError")(_body("overloaded_error"), 200),     # midden in de stream, bij HTTP 200
    _soort("APIStatusError")(_body("rate_limit_error"), 200),
])
def test_overbelasting_krijgt_de_wachtmelding(exc):
    assert "overbelast" in _foutmelding(exc)


def test_alleen_een_echt_te_lang_gesprek_heet_te_lang():
    lang = _soort("BadRequestError")(_body("invalid_request_error", "prompt is too long: 250000 tokens"), 400)
    assert "te lang" in _foutmelding(lang)
    assert "te lang" in _foutmelding(_soort("RequestTooLargeError")(None, 413))
    kapot = _soort("BadRequestError")(_body("invalid_request_error", "messages.3: tool_use ids were found"), 400)
    assert "te lang" not in _foutmelding(kapot)
    assert "nieuw gesprek" not in _foutmelding(kapot)


def test_een_streamfout_is_voor_de_eval_een_storing_en_voor_de_jurist_overbelasting():
    """`soort` blijft de exception-naam: die telt de eval als infrastructuur, geen gezakte case."""
    class StreamFout(FakeLLM):
        def stream(self, **_kw: Any):
            raise _soort("APIStatusError")(_body("overloaded_error"), 200)

    settings = make_settings(enable_planning=False)
    events = _run(answer_stream("vraag", settings=settings, llm=StreamFout([]), graph=FakeGraph(result="")))
    fout_event = next(e for e in events if e["type"] == "error")
    assert "overbelast" in fout_event["message"]
    assert is_infrastructuurfout(fout_event["message"], fout_event["soort"])


def test_de_eval_telt_de_namen_van_overbelasting_als_storing():
    assert is_infrastructuurfout("x", "OverloadedError")


def test_een_mislukte_verbinding_lekt_geen_details():
    class Kapot(FakeGraph):
        def initialize(self) -> None:
            raise RuntimeError("https://intern.voorbeeld:7200/mcp weigert token abc")

    events = _run(answer_stream("vraag", settings=make_settings(), llm=FakeLLM([]), graph=Kapot(result="")))
    fout_event = next(e for e in events if e["type"] == "error")
    assert "intern.voorbeeld" not in fout_event["message"]
    assert fout_event["soort"] == "RuntimeError"
