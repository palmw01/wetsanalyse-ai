"""De gescripte `FakeLLM` is streng (Lex Bench §20.5 stap 2, testplan graph-qa P0-4): een aanroep die het script niet
voorzag en een tool die het verzoek niet aanbood, zijn een leesbare fout, geen kale `IndexError` en geen toets van iets
wat een echt model niet kan."""
from __future__ import annotations

import pytest

from fakes import FakeLLM, ScriptFout, response, text_block, tool_block

TOOLS = [{"name": "get_artikel", "input_schema": {}}]


def test_een_ronde_te_veel_zegt_wat_er_gevraagd_werd():
    llm = FakeLLM([response([text_block("a")], "end_turn")])
    llm.create(messages=[{"role": "user", "content": "eerste"}], tools=TOOLS)
    with pytest.raises(ScriptFout, match=r"modelronde 2, gescript waren er 1.*user.*tweede"):
        llm.create(messages=[{"role": "user", "content": "tweede"}], tools=TOOLS)


def test_een_tool_die_niet_werd_aangeboden_is_een_fout():
    llm = FakeLLM([response([tool_block("t1", "geldigheid", {})], "tool_use")])
    with pytest.raises(ScriptFout, match="geldigheid aan, maar het verzoek bood die niet aan"):
        llm.create(messages=[], tools=TOOLS)


def test_een_aangeboden_tool_en_een_bewuste_uitzondering_gaan_door():
    assert FakeLLM([response([tool_block("t1", "get_artikel", {})], "tool_use")]).create(messages=[], tools=TOOLS)
    buiten = FakeLLM([response([tool_block("t1", "geldigheid", {})], "tool_use")], buiten_aanbod=True)
    assert buiten.create(messages=[], tools=TOOLS)
