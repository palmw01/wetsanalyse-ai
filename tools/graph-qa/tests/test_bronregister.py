"""Een vervolgantwoord mag steunen op wat eerder in het gesprek letterlijk is opgehaald.

De controle toetste alleen de trace van de huidige beurt: wie doorvroeg en het vorige citaat
herhaalde, kreeg `ongegrond` en een correctie die de onderbouwing eruit haalde. Het register maakt
eerder opgehaalde wettekst weer bewijs – en alleen dat: modeltekst en annotaties tellen niet.
"""
from __future__ import annotations

import asyncio

from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block

from agent.agent import answer_stream
from agent.bronregister import MAX_ITEMS, bij, controletrace

TEKST = "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet."
TSV = f'?node\t?tekst\n<urn:bwb:BWBR0004770:artikel:9:lid:1>\t"{TEKST}"'


def _run(gen):
    async def collect():
        return [ev async for ev in gen]
    return asyncio.run(collect())


def test_register_houdt_alleen_opgehaalde_wettekst():
    reg = bij([], [("get_lid", "a"), ("search_annotaties", "{}"), ("get_lid", "Fout bij tool x"),
                   ("get_lid", ""), ("get_lid", "a")])
    assert reg == [["get_lid", "a"]]
    reg = bij(reg, [("get_artikel", str(i)) for i in range(MAX_ITEMS + 5)])
    assert len(reg) == MAX_ITEMS and reg[-1] == ["get_artikel", str(MAX_ITEMS + 4)]
    assert controletrace({"bronregister": [["get_lid", "x"]], "source_trace": [("get_artikel", "y")]}) \
        == [("get_lid", "x"), ("get_artikel", "y")]


def _gesprek(tmp_path, tweede_antwoord: str):
    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"))
    llm1 = FakeLLM([
        response([text_block("WORKERS: antwoord\nSPECIALIST: duiding\nPLAN: lid 1")], "end_turn"),
        response([tool_block("t1", "get_lid", {"bwb_id": "BWBR0004770", "artikel": "9", "lid": "1"})], "tool_use"),
        response([text_block(f'Artikel 9 lid 1 (BWBR0004770): "{TEKST}"')], "end_turn"),
    ])
    _run(answer_stream("Wat zegt artikel 9 lid 1 IW 1990?", "g", settings=settings, llm=llm1, graph=FakeGraph(result=TSV)))
    llm2 = FakeLLM([
        response([text_block("VRAAG: Wat betekent die termijn?\nWORKERS: antwoord\nSPECIALIST: duiding\nPLAN: leg uit")],
                 "end_turn"),
        response([text_block(tweede_antwoord)], "end_turn"),
        # Alleen gebruikt als de controle een correctie vraagt.
        response([text_block("Gecorrigeerd antwoord.")], "end_turn"),
    ])
    events = _run(answer_stream("Wat betekent die termijn?", "g", settings=settings, llm=llm2, graph=FakeGraph(result="")))
    grounding = next(e for e in events if e["type"] == "grounding")
    sources = next(e for e in events if e["type"] == "sources")["sources"]
    return grounding, sources, llm2


def test_een_eerder_opgehaald_citaat_is_gegrond(tmp_path):
    grounding, sources, llm = _gesprek(
        tmp_path, 'De termijn loopt vanaf de dagtekening: "invorderbaar zes weken na de dagtekening" (BWBR0004770).')
    assert grounding["niveau"] == "gegrond", grounding
    assert len(llm.calls) == 2, "geen correctieronde nodig"
    assert any("BWBR0004770" in s["uri"] for s in sources), "de hergebruikte bron staat in de lijst"


def test_een_verzonnen_citaat_blijft_ongegrond(tmp_path):
    grounding, _, llm = _gesprek(tmp_path, 'De wet zegt: "de ontvanger mag altijd uitstel van betaling geven".')
    assert len(llm.calls) == 3, "het register maakt geen modeltekst tot bron: de controle vraagt een correctie"
    assert "Let op" in str(llm.calls[2]["messages"][-1])


def test_een_annotatie_onderbouwt_geen_wettekst():
    reg = bij([], [("search_annotaties", f'{{"resultaten": [{{"tekst": "{TEKST}"}}]}}')])
    assert reg == []
