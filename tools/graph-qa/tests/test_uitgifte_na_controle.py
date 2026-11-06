"""De jurist ziet een antwoord pas na de controle, en afgekeurde tekst nooit (C1, besluit 2).

De oude volgorde stuurde het antwoord vóór `verify` de deur uit: na een correctieronde stonden de
afgekeurde en de herziene tekst aan elkaar in beeld en in het bericht, en het oordeel ging alleen
over de tweede. Tekst in het denkproces is net zo goed in beeld: dat paneel staat tijdens de beurt open.
"""
from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from typing import Any

import pytest

from agent.agent import answer_stream
from agent.beurt import voer_beurt_uit
from agent.runs import Run
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block

AFGEKEURD = "Afgekeurd antwoord met BWBR9999999."
HERZIEN = "Herzien antwoord zonder citatie."
ART_IRI = "urn:bwb:BWBR0004770:artikel:9"


def _run(gen):
    async def collect():
        return [ev async for ev in gen]

    return asyncio.run(collect())


def _tekst(events: list[dict[str, Any]], soort: str) -> str:
    return "".join(e.get("content", "") for e in events if e["type"] == soort)


def _alles(events: list[dict[str, Any]]) -> str:
    """Alles wat naar de werkplek gaat, als tekst: wat hierin staat kan in beeld komen."""
    return " ".join(str(e) for e in events)


def _correctie(*antwoorden: str) -> tuple[Any, FakeLLM, FakeGraph]:
    settings = make_settings(enable_planning=False, grounding_correct=True)
    llm = FakeLLM([response([text_block(a)], "end_turn") for a in antwoorden])
    return settings, llm, FakeGraph(result="")


def test_na_een_correctieronde_gaat_alleen_de_herziene_tekst_de_deur_uit():
    settings, llm, graph = _correctie(AFGEKEURD, HERZIEN)
    events = _run(answer_stream("vraag", settings=settings, llm=llm, graph=graph))
    assert llm.index == 2
    assert _tekst(events, "token") == HERZIEN
    assert AFGEKEURD not in _alles(events)


def test_het_bericht_draagt_alleen_de_herziene_tekst(monkeypatch):
    class NepApi:
        def __init__(self) -> None:
            self.berichten: list[dict[str, Any]] = []

        async def voeg_bericht_toe(self, _gesprek_id: str, bericht: dict[str, Any]) -> dict[str, Any]:
            self.berichten.append(bericht)
            return {}

        async def aclose(self) -> None: ...

    nep = NepApi()
    monkeypatch.setattr("agent.beurt.WetsanalyseApi", lambda *_a, **_k: nep)
    _, llm, graph = _correctie(AFGEKEURD, HERZIEN)
    settings = make_settings(enable_planning=False, grounding_correct=True,
                             wetsanalyse_api_url="http://api", wetsanalyse_api_token="t", qa_api_token="q")

    async def draai():
        stroom = answer_stream("vraag", settings=settings, llm=llm, graph=graph)
        return [e async for e in voer_beurt_uit(stroom, settings=settings, run=Run(run_id="r1", conversation_id="g1", vraag="vraag"),
                                                gesprek_id="g1", user_id="jurist")]

    asyncio.run(draai())
    assert len(nep.berichten) == 1
    assert nep.berichten[0]["tekst"] == HERZIEN
    assert AFGEKEURD not in nep.berichten[0]["denk"]


def test_blijft_ook_de_herziene_tekst_afgekeurd_dan_staat_hij_er_met_het_oordeel():
    """Besluit 6 nov 2026: niet verbergen, want de controle keurt ook terechte citaten af. Het oordeel
    gaat over precies deze tekst, en de afgekeurde eerste versie blijft weg."""
    tweede = "Nog steeds BWBR8888888."
    settings, llm, graph = _correctie(AFGEKEURD, tweede)
    events = _run(answer_stream("vraag", settings=settings, llm=llm, graph=graph))
    grounding = next(e for e in events if e["type"] == "grounding")
    assert _tekst(events, "token") == tweede
    assert grounding["niveau"] == "ongegrond" and "BWBR8888888" in grounding["unsupported"]
    assert AFGEKEURD not in _alles(events)


def test_sneuvelt_de_correctieronde_dan_komt_de_afgekeurde_tekst_niet_vrij():
    settings, _llm, graph = _correctie(AFGEKEURD)

    class FaaltInRondeTwee(FakeLLM):
        def stream(self, **kw: Any):
            if self.index == 1:
                raise RuntimeError("provider weg")
            return super().stream(**kw)

    llm = FaaltInRondeTwee([response([text_block(AFGEKEURD)], "end_turn")])
    events = _run(answer_stream("vraag", settings=settings, llm=llm, graph=graph))
    assert "error" in [e["type"] for e in events]
    assert _tekst(events, "token") == ""
    assert AFGEKEURD not in _alles(events)


def test_narratie_gaat_na_de_ronde_naar_het_denkproces_het_eindantwoord_niet():
    settings = make_settings(enable_planning=False)
    graph = FakeGraph(result=f"<{ART_IRI}> bwb:tekst 'x' .")
    llm = FakeLLM([
        response([text_block("Ik zoek nu op."),
                  tool_block("t1", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": "9"})], "tool_use"),
        response([text_block("De definitie is helder.")], "end_turn"),
    ])
    events = _run(answer_stream("vraag", settings=settings, llm=llm, graph=graph))
    assert "Ik zoek nu op." in _tekst(events, "reason")
    assert "De definitie is helder." not in _tekst(events, "reason")
    assert _tekst(events, "token") == "De definitie is helder."


def test_het_eindantwoord_op_de_beurtlimiet_gaat_ook_niet_naar_het_denkproces():
    """Het vangnet laat de tools vallen: deze ronde is dan alsnog het eindantwoord."""
    settings = make_settings(enable_planning=False, max_turns=1)
    llm = FakeLLM([response([text_block("Laatste woord."),
                             tool_block("t1", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": "9"})], "tool_use")])
    events = _run(answer_stream("vraag", settings=settings, llm=llm, graph=FakeGraph(result="")))
    assert _tekst(events, "reason") == ""
    assert _tekst(events, "token") == "Laatste woord."


def test_de_token_komt_na_de_controle():
    settings, llm, graph = _correctie("Antwoord.")
    events = _run(answer_stream("vraag", settings=settings, llm=llm, graph=graph))
    types = [e["type"] for e in events]
    controle = next(i for i, e in enumerate(events) if e.get("message", "").startswith("Controle"))
    assert controle < types.index("token") < types.index("grounding")


def test_afgekeurde_synthese_komt_niet_in_beeld():
    settings = make_settings(enable_decomposition=True, grounding_correct=True)
    llm = FakeLLM([
        response([text_block("SPECIALIST: algemeen\nPLAN: opsplitsen")], "end_turn"),
        response([text_block("1. Eerste?\n2. Tweede?")], "end_turn"),
        response([text_block("Bevinding een.")], "end_turn"),
        response([text_block("Bevinding twee.")], "end_turn"),
        response([text_block(AFGEKEURD)], "end_turn"),
        response([text_block(HERZIEN)], "end_turn"),
    ])
    events = _run(answer_stream("vraag", settings=settings, llm=llm, graph=FakeGraph(result="")))
    assert _tekst(events, "token") == HERZIEN
    assert AFGEKEURD not in _alles(events)


@pytest.mark.parametrize("bestand", ["antwoord.py", "overzicht.py", "decompositie.py"])
def test_binnen_de_antwoordketen_stuurt_alleen_finalize_een_token(bestand: str):
    """Een controle die volgt op publicatie houdt niets tegen. Een nieuwe `token` in deze keten hoort
    daarom niet te kunnen ontstaan zonder dat deze test het ziet."""
    boom = ast.parse((Path(__file__).parents[1] / "agent" / "nodes" / bestand).read_text(encoding="utf8"))
    plekken = [f.name for f in ast.walk(boom) if isinstance(f, ast.FunctionDef)
               for n in ast.walk(f) if isinstance(n, ast.Constant) and n.value == "token"]
    assert set(plekken) <= {"finalize_node"}
