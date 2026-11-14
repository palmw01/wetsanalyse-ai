"""Een subagent sluit af in code, en de centrale agent doet het werk daarna niet opnieuw (ADR-016 §A2, §A4; meting
bundel 114, 14 nov 2026: geen kind rondde af met een rapport, S01, D01 en P01 liepen tegen de rondegrens, en de centrale
agent las daarna alles zelf opnieuw, P01 21 aanroepen voor 1,5M)."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from agent import subagent as sub
from agent.agentvorm import MAX_RONDES_SUBAGENT
from agent.nodes import antwoord as antwoordnodes
from agent.nodes.antwoord import (MAX_TOKENS_SUBAGENT, NA_SUBAGENT, SUBAGENT_AFGESLOTEN, laatste_ronde,
                                  met_laatste_ronde, na_subagent)
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block
from test_subagent import ARTIKEL, OPDRACHT, ZIN_1, _rapport


def _lees(i: int):
    return response([tool_block(f"t{i}", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": str(10 + i)})], "tool_use")


def _kindbeurt(monkeypatch, antwoorden, *, meter=None):
    from agent.agent import answer_stream

    monkeypatch.setattr(antwoordnodes, "execute_tool", lambda *_a, **_k: ARTIKEL[1])
    llm = FakeLLM(antwoorden)
    if meter is not None:
        llm.meter = meter
    resultaat: dict = {}

    async def alles():
        return [e async for e in answer_stream(sub.opdracht_tekst(OPDRACHT), "kind-1",
                                               settings=make_settings(enable_planning=True), llm=llm,
                                               graph=FakeGraph(result=ARTIKEL[1]), profiel="duiding",
                                               opdracht=OPDRACHT, resultaat=resultaat)]

    asyncio.run(alles())
    return llm, resultaat


def _laatste_bericht(call) -> str:
    return json.dumps((call.get("messages") or call.get("berichten"))[-1], ensure_ascii=False)


def test_de_laatste_ronde_zegt_de_code_en_het_kind_rondt_af_met_het_rapport(monkeypatch):
    lezen = [_lees(i) for i in range(MAX_RONDES_SUBAGENT - 1)]
    llm, resultaat = _kindbeurt(monkeypatch, [*lezen, response([tool_block("r", "rapport", _rapport())], "tool_use")])
    assert len(llm.calls) == MAX_RONDES_SUBAGENT
    assert "LAATSTE RONDE (de rondegrens" in _laatste_bericht(llm.calls[-1])
    assert not any("LAATSTE RONDE" in _laatste_bericht(c) for c in llm.calls[:-1])
    # De melding staat achter de toolresultaten: het voorvoegsel en de tools zijn dezelfde als de ronde ervoor.
    assert llm.calls[-1]["tools"] == llm.calls[-2]["tools"] and llm.calls[-1]["system"] == llm.calls[-2]["system"]
    assert resultaat["rapport"]["status"] == "klaar" and ZIN_1 in resultaat["answer"]


def test_leest_het_kind_in_zijn_laatste_ronde_toch_door_dan_sluit_de_code_af_met_wat_hij_las(monkeypatch):
    lezen = [_lees(i) for i in range(MAX_RONDES_SUBAGENT)]
    llm, resultaat = _kindbeurt(monkeypatch, lezen)
    assert len(llm.calls) == MAX_RONDES_SUBAGENT, "geen ronde meer na de laatste, ook geen correctieronde"
    assert resultaat["answer"] == SUBAGENT_AFGESLOTEN and not (resultaat.get("rapport") or {}).get("status")
    tekst = sub.rapport_tekst(sub.Afloop(profiel="duiding", uitkomst="niet_gelukt"), resultaat)
    assert "Wat hij las" in tekst


def test_bij_het_tokenplafond_is_de_volgende_ronde_de_laatste(monkeypatch):
    meter = SimpleNamespace(invoer=MAX_TOKENS_SUBAGENT, uitvoer=0, cache_lees=0, cache_schrijf=0)
    llm, resultaat = _kindbeurt(monkeypatch, [_lees(0), _lees(1)], meter=meter)
    assert len(llm.calls) == 1 and "LAATSTE RONDE (het tokenplafond" in _laatste_bericht(llm.calls[0])
    assert resultaat["answer"] == SUBAGENT_AFGESLOTEN


def test_alleen_een_subagent_heeft_een_laatste_ronde_en_een_plafond():
    b = SimpleNamespace(settings=make_settings(), llm=SimpleNamespace(
        meter=SimpleNamespace(invoer=10 * MAX_TOKENS_SUBAGENT, uitvoer=0, cache_lees=0, cache_schrijf=0)))
    assert laatste_ronde(b, {"turns": 99}) == ""
    kind = {"opdracht": OPDRACHT.model_dump(), "turns": 0}
    assert laatste_ronde(b, kind) == "plafond"
    assert laatste_ronde(b, {**kind, "turns": MAX_RONDES_SUBAGENT - 1}) == "rondegrens"
    b.llm.meter.invoer = 0
    assert laatste_ronde(b, kind) == ""
    # Een venster dat niet op een user-bericht eindigt, blijft zoals het is.
    venster = [{"role": "assistant", "content": "x"}]
    assert met_laatste_ronde(venster, "plafond") == venster


def test_na_een_subagent_die_niet_afrondde_leest_de_centrale_agent_niet_zelf_opnieuw():
    niet_af = {"subagenten": [{"uitkomst": "niet_gelukt"}]}
    assert na_subagent(niet_af, "get_artikel") == NA_SUBAGENT
    assert na_subagent(niet_af, "get_uitspraak") == NA_SUBAGENT, "ook een connectortool"
    assert na_subagent({"subagenten": [{"uitkomst": "mislukt"}]}, "search_wetgeving") == NA_SUBAGENT
    # Sjablonen en eigen tools blijven: afronden en de gebruiker vragen kan altijd.
    assert na_subagent(niet_af, "antwoord_duiding") == "" and na_subagent(niet_af, "wijs_af") == ""
    # Een subagent die klaar was, een vraag stelde of niet startte (een 409, het budget): dan mag het wel.
    for uitkomst in ("klaar", "vraag", "niet_gestart", "budget_op"):
        assert na_subagent({"subagenten": [{"uitkomst": uitkomst}]}, "get_artikel") == ""
    # Het kind zelf valt er niet onder.
    assert na_subagent({**niet_af, "opdracht": OPDRACHT.model_dump()}, "get_artikel") == ""


def test_de_weigering_gaat_door_tools_node_en_het_rapport_zegt_het_vooraf(monkeypatch):
    uitgevoerd = []
    monkeypatch.setattr(antwoordnodes, "execute_tool", lambda *a, **_k: uitgevoerd.append(a) or ARTIKEL[1])
    monkeypatch.setattr(antwoordnodes, "get_stream_writer", lambda: (lambda _e: None))
    tu = {"id": "t1", "name": "get_artikel", "input": {"bwb_id": "BWBR0004770", "artikel": "10"}}
    state = {"pending_tools": [tu], "messages": [], "source_trace": [], "specialist": "centraal",
             "agentvorm": "centraal", "subagenten": [{"uitkomst": "niet_gelukt"}], "run_id": "r"}
    b = SimpleNamespace(settings=make_settings(), graph=None, stop_check=None)
    upd = antwoordnodes.tools_node(b, state)
    [blok] = upd["messages"][-1]["content"]
    assert "na_subagent" in blok["content"] and not uitgevoerd
    kop = sub.als_toolresultaat("algemeen", "niet_gelukt", "")
    assert "Doe het werk niet opnieuw" in kop
    assert "Doe het werk niet opnieuw" not in sub.als_toolresultaat("algemeen", "klaar", "x")


# -- punt 4: in een antwoord valt een aanwijzing die niet klopt weg, als er iets anders te tonen is ---------------------

def test_een_uitleg_met_een_passage_die_niet_te_tonen_is_toont_de_andere_en_zegt_het():
    from agent.sjablonen import vul
    from test_rapport_en_rondegrens import FOUT, GOED

    a = vul("antwoord_duiding", {"kort_antwoord": "De ontvanger kan uitstel verlenen.", "onderbouwing": [GOED, FOUT],
                                 "twijfel": []}, [ARTIKEL])
    assert [b.soort for b in a.blokken] == ["toelichting", "citaten", "leemte"]
    assert len(a.blokken[1].items) == 1
    leemte = a.blokken[2].tekst
    assert "niet als citaat getoond" in leemte and "Dit staat er niet" not in leemte, "geen modeltekst in het antwoord"


def test_zonder_iets_te_tonen_weigert_de_uitleg_zoals_altijd():
    import pytest

    from agent.sjablonen import Onvulbaar, vul
    from test_rapport_en_rondegrens import FOUT

    with pytest.raises(Onvulbaar) as fout:
        vul("antwoord_duiding", {"kort_antwoord": "x", "onderbouwing": [FOUT], "twijfel": []}, [ARTIKEL])
    assert fout.value.code == "passage_niet_te_tonen"


def test_een_aanwijzing_in_extern_die_niet_klopt_valt_weg_naast_een_die_klopt():
    import pytest

    from agent.sjablonen import Onvulbaar, vul
    from test_extern_sjabloon import ID, TRACE

    goed, fout = {"id": ID, "van_nr": 1, "tot_nr": 3}, {"id": ID, "van_nr": 2, "tot_nr": 9}
    a = vul("antwoord_extern", {"kort_antwoord": "De MvT legt het doel uit.", "extern": [goed, fout], "twijfel": []}, TRACE)
    assert [b.soort for b in a.blokken] == ["toelichting", "extern", "leemte"]
    assert "niet als citaat getoond" in a.blokken[-1].tekst and "Haal" not in a.blokken[-1].tekst
    with pytest.raises(Onvulbaar):
        vul("antwoord_extern", {"kort_antwoord": "x", "extern": [fout], "twijfel": []}, TRACE)


def test_als_subsjabloon_toont_de_uitleg_de_wettekst_en_laat_de_foute_aanwijzing_weg():
    import pytest

    from agent.sjablonen import Onvulbaar, vul
    from test_extern_sjabloon import ID, TRACE
    from test_rapport_en_rondegrens import GOED

    trace = [ARTIKEL, *TRACE]
    fout = {"id": ID, "van_nr": 2, "tot_nr": 9}
    a = vul("antwoord_duiding", {"kort_antwoord": "De ontvanger kan uitstel verlenen.", "onderbouwing": [GOED],
                                 "extern": [fout], "twijfel": []}, trace)
    assert [b.soort for b in a.blokken] == ["toelichting", "citaten", "leemte"]
    # Alleen een foute aanwijzing in extern en geen passage: de weigering zoals altijd.
    with pytest.raises(Onvulbaar):
        vul("antwoord_duiding", {"kort_antwoord": "x", "onderbouwing": [], "extern": [fout], "twijfel": []}, trace)


# -- een grote beurt houdt haar gesprek in de correctieronde -----------------------------------------------------------

def test_de_correctieronde_na_een_grote_beurt_krijgt_de_hele_beurt(monkeypatch):
    """Meting bundel 114: P01 (2,34M) eindigde met één zin. De correctie was het enige platte user-bericht in de lopende
    beurt, de opslagrem knipte daarop, en de laatste aanroep kreeg alleen de correctie."""
    from agent import berichten
    from agent.agent import answer_stream

    groot = json.dumps({"status": "ok", "volledig": True, "aantal": 1, "resultaten": [{"tekst": "x " * 3000}]})
    monkeypatch.setattr(antwoordnodes, "execute_tool", lambda *_a, **_k: groot)
    monkeypatch.setattr(berichten, "MAX_HISTORIE_CHARS", 20_000)
    lezen = [response([tool_block(f"t{i}", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": str(i)})], "tool_use")
             for i in range(6)]
    llm = FakeLLM([*lezen, response([text_block("Volgens BWBR0009999 is het zo.")], "end_turn"),
                   response([text_block("Hersteld antwoord.")], "end_turn")])

    async def alles():
        return [e async for e in answer_stream("Wat zegt artikel 10 van de Invorderingswet 1990?",
                                               settings=make_settings(centrale_agent="meten"), llm=llm,
                                               graph=FakeGraph(result=""), agentvorm="centraal")]

    asyncio.run(alles())
    correctie, vorige = llm.calls[-1]["messages"], llm.calls[-2]["messages"]
    assert json.dumps(correctie[-1], ensure_ascii=False).find("Let op") >= 0
    assert correctie[:len(vorige)] == vorige, "de correctieronde houdt de beurt"
