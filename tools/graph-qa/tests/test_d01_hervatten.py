"""D01 uit de meting van bundel 118 (14 nov 2026), het hervatten, met nepbronnen in de echte vorm (`get_uitspraak` door de
echte toollaag, uit `test_d01_zonder_duiding`).

Het kind stelde drie vragen in één keer, de jurist antwoordde, en de code hervatte het. Vier dingen gingen mis:

1. het hervatte deel vulde in zijn laatste ronde een rapport `klaar`; de controle vond een feit zonder bron, de
   correctieronde kon niet meer komen, en de code sloot het kind af. Het heette toch `klaar`, met een leeg rapport;
2. het plafond (300k) leek over beide delen samen te tellen. Dat doet het niet: de meter is per beurt (zie hieronder);
3. het hervatte deel begon op 30k, zonder de toolresultaten van het eerste deel, en las drie uitspraken opnieuw;
4. het eerste rapport bereikte de jurist niet, en bij HR:2023:176 en :183 stond "zie toelichting bij HR:2023:181"."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from agent import berichten
from agent import subagent as sub
from agent.grounding import check_grounding
from agent.models import SubagentOpdracht
from agent.nodes import antwoord as antwoordnodes
from agent.nodes import subagent_route as route
from agent.nodes.antwoord import MAX_TOKENS_SUBAGENT, SUBAGENT_AFGESLOTEN
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block
from test_d01_zonder_duiding import HOF, HR, PHR, TRACE, VRAAG
from test_subagent import STATE, Api, _kinderen

OPDRACHT = SubagentOpdracht(doel=VRAAG, onderwerp="BWBR0004770, artikel 36",
                            oplevering="Per uitspraak wat de rechter over de melding zegt.")
LEES = {json.loads(t)["stuk"]["id"]: t for n, t in TRACE if n == "get_uitspraak"}
# Opties zonder jaartal: een jaartal in een optie telt de controle nu als bewering (een vervolgpunt, niet dit geval).
VRAGEN = [{"tekst": "Welke periode?", "opties": ["Alleen de laatste jaren"]},
          {"tekst": "Welke instanties?", "opties": ["Alle instanties"]}]


def _nr(ecli: str, woord: str) -> int:
    return next(r["nr"] for r in json.loads(LEES[ecli])["resultaten"] if woord in r["tekst"])


def _lees(i: int, ecli: str):
    return response([tool_block(f"l{i}", "get_uitspraak", {"id": ecli})], "tool_use")


def _rapport(status: str, **extra) -> dict:
    return {"status": status, "gedaan": "Uitspraken gelezen.", "bevindingen": "", "onderbouwing": [], "open": [],
            "vragen": [], "extern": [], **extra}


def _beurt(monkeypatch, tmp_path, vraag: str, antwoorden, *, meter=None):
    """Eén beurt van het kind in het deelgesprek `kind-d01`, met een checkpoint op schijf: de tweede beurt ziet de eerste."""
    from agent.agent import answer_stream

    gelezen: list[str] = []

    def lees(_b, _state, _writer, tu, **_k):
        gelezen.append(tu["input"]["id"])
        return LEES[tu["input"]["id"]]

    monkeypatch.setattr(antwoordnodes, "execute_tool", lees)
    llm = FakeLLM(antwoorden)
    if meter is not None:
        llm.meter = meter
    resultaat: dict = {}

    async def alles():
        return [e async for e in answer_stream(
            vraag, "kind-d01", llm=llm, graph=FakeGraph(result=""), profiel="algemeen", opdracht=OPDRACHT,
            resultaat=resultaat,
            # Een krap venster: zonder de hervatting als vervolg van de beurt viel het eerste deel eruit (bundel 118).
            settings=make_settings(enable_planning=True, max_history_chars=2_000,
                                   checkpoint_db_path=str(tmp_path / "kind.db")))]

    asyncio.run(alles())
    return llm, resultaat, gelezen


def _eerste_deel(monkeypatch, tmp_path):
    vraag = _rapport("vraag", vragen=VRAGEN, bevindingen=f"{HR} gaat over het una-via-beginsel, niet over de melding.",
                     extern=[{"id": HR, "van_nr": (n := _nr(HR, "una-via")), "tot_nr": n}])
    return _beurt(monkeypatch, tmp_path, sub.opdracht_tekst(OPDRACHT),
                  [_lees(1, HR), _lees(2, HOF), response([tool_block("r1", "rapport", vraag)], "tool_use")])


def _hervatting() -> str:
    return sub.antwoord_tekst(VRAGEN, ["Alleen de laatste jaren", "Alle instanties"], van="van de gebruiker")


# -- 3: het hervatte deel ziet wat het eerste deel las --------------------------------------------------------------------

def test_het_hervatte_deel_ziet_wat_het_eerste_deel_las_en_leest_het_niet_opnieuw(monkeypatch, tmp_path):
    _, eerste, gelezen = _eerste_deel(monkeypatch, tmp_path)
    assert eerste["rapport"]["status"] == "vraag" and gelezen == [HR, HOF]

    klaar = _rapport("klaar", bevindingen=f"{HR} gaat over het una-via-beginsel; {HOF} over aanmerkelijk belang.",
                     extern=[{"id": HR, "van_nr": (n := _nr(HR, "una-via")), "tot_nr": n},
                             {"id": HOF, "van_nr": (m := _nr(HOF, "aanmerkelijk")), "tot_nr": m}])
    llm, tweede, gelezen = _beurt(monkeypatch, tmp_path, _hervatting(),
                                  [_lees(3, HR), response([tool_block("r2", "rapport", klaar)], "tool_use")])
    eerste_ronde = json.dumps(llm.calls[0]["messages"], ensure_ascii=False)
    # De toolresultaten van het eerste deel staan in het venster, ook met een venster van 2.000 tekens.
    assert "una-via-beginsel" in eerste_ronde and "aanmerkelijk belang" in eerste_ronde
    # Dezelfde aanroep in het hervatte deel gaat niet opnieuw naar de bron.
    assert gelezen == [], "HR:2026:586 is niet opnieuw opgehaald"
    assert "al uitgevoerd" in json.dumps(llm.calls[1]["messages"][-1], ensure_ascii=False)
    # Het rapport citeert uit wat het eerste deel las; de trace naar de ouder noemt het gelezen.
    assert tweede["rapport"]["status"] == "klaar"
    assert set(sub.steun_van([tweede])) == {HR, HOF}
    assert [i for i, _ in __import__("agent.gelezen", fromlist=["x"]).gelezen_en_gevonden(tweede["source_trace"])[0]] \
        == [HR, HOF]


def test_de_hervatting_is_geen_vraag_en_geen_knippunt():
    opdracht = {"role": "user", "content": sub.opdracht_tekst(OPDRACHT)}
    werk = [{"role": "assistant", "content": [{"type": "tool_use", "id": "a", "name": "get_uitspraak", "input": {}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "a", "content": "x" * 5_000}]},
            {"role": "assistant", "content": "Ik heb een vraag."}]
    hervat = {"role": "user", "content": _hervatting()}
    berichten_ = [opdracht, *werk, hervat]
    assert berichten.beurt_start(berichten_, hervat["content"]) == 0
    assert berichten._trim_messages(berichten_, 100, hervat["content"]) == berichten_
    assert berichten._snoei_historie([*berichten_, *werk], 6_000)[0] == opdracht, "de opslagrem knipt niet op de hervatting"
    # Een gewone vervolgvraag in het deelgesprek blijft een eigen beurt.
    vervolg = {"role": "user", "content": "En in 2025?"}
    assert berichten.beurt_start([*berichten_, *werk, vervolg], "En in 2025?") == 8
    assert berichten.toolresultaten(werk, {"get_uitspraak"}) == [("get_uitspraak", "x" * 5_000)]


# -- 1: een rapport in de laatste ronde gaat niet verloren --------------------------------------------------------------

def test_een_rapport_in_de_laatste_ronde_krijgt_geen_correctie_en_gaat_met_de_punten_mee(monkeypatch, tmp_path):
    _eerste_deel(monkeypatch, tmp_path)
    # Het hervatte deel zit bij het plafond (de schatting): deze ronde is de laatste.
    ronde = {"invoer": 60_000, "uitvoer": 0, "cache_lees": 0, "cache_schrijf": 0}
    meter = SimpleNamespace(invoer=MAX_TOKENS_SUBAGENT - 100_000, uitvoer=0, cache_lees=0, cache_schrijf=0,
                            aanroepen=[ronde])
    # Een feit zonder bron in de bevindingen: de datum staat in geen enkele uitspraak.
    klaar = _rapport("klaar", bevindingen=f"{HR} gaat over het una-via-beginsel, gewezen op 12 maart 2019.",
                     extern=[{"id": HR, "van_nr": (n := _nr(HR, "una-via")), "tot_nr": n}])
    llm, kind, _ = _beurt(monkeypatch, tmp_path, _hervatting(),
                          [response([tool_block("r2", "rapport", klaar)], "tool_use"),
                           response([text_block("Hersteld.")], "end_turn")], meter=meter)
    assert len(llm.calls) == 1, "geen correctieronde: die kan er niet meer komen"
    assert kind["rapport"]["status"] == "klaar" and not kind["afgesloten"] and kind["answer"] != SUBAGENT_AFGESLOTEN
    assert any("12 maart 2019" in p for p in kind["onbevestigd"])
    tekst = sub.rapport_tekst(sub.Afloop(profiel="algemeen", uitkomst="klaar"), kind)
    assert "Niet teruggevonden in wat de subagent las" in tekst and "12 maart 2019" in tekst


def test_sluit_de_code_een_kind_af_dan_heet_het_afgesloten_ook_met_een_rapport_ervoor(monkeypatch):
    """Het pad van bundel 118: een rapport `klaar` in de state en daarna de afsluiting door de code."""
    events = []
    monkeypatch.setattr(route, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(sub, "WetsanalyseApi", lambda *_a: Api())
    kinderen, _, _ = _kinderen({"rapport": {"status": "klaar"}, "answer": SUBAGENT_AFGESLOTEN, "afgesloten": True,
                                "source_trace": TRACE})
    b = SimpleNamespace(kinderen=kinderen, settings=SimpleNamespace(legt_zelf_vast=True), loop=None, stop_check=None,
                        graph=None)
    route.subagent_route_node(b, {**STATE, "question": VRAAG, "source_trace": []})
    [regie] = [e for e in events if e["type"] == "regie" and e["fase"] == "eind"]
    assert (regie["afgesloten"], regie["opgeleverd"]) == (1, 0)
    # En een correctie haalt het rapport weg, met het antwoord.
    monkeypatch.setattr(antwoordnodes, "get_stream_writer", lambda: events.append)
    upd = antwoordnodes.correct_node(SimpleNamespace(), {"beweringen": ["x"], "rapport": {"status": "klaar"}})
    assert upd["rapport"] == {} and upd["antwoord"] == {}


# -- 2: het plafond geldt per deel ------------------------------------------------------------------------------------

def test_het_plafond_geldt_per_deel_want_elke_beurt_heeft_een_eigen_meter(monkeypatch):
    """De 254k en de 249k van bundel 118 zijn twee meters: `_stroom_voor` maakt er één per beurt, en het hervatte deel is
    een nieuwe beurt (`subagent.hervat` start een nieuwe run). Zijn laatste ronde kwam van de schatting binnen zijn eigen
    300k (`volgende_ronde`)."""
    import inspect

    import api.main as main

    bron = inspect.getsource(main._stroom_voor)
    assert "meter = Verbruiksmeter()" in bron.split("def gewone_beurt")[1].split("voer_beurt_uit")[0]


# -- 4: een verwijzing naar een ander stuk is geen duiding ----------------------------------------------------------------

def test_zie_de_toelichting_bij_een_ander_stuk_is_geen_duiding():
    fout = check_grounding(f"- {HOF}: zie de toelichting bij {HR}.\n- {PHR} (Parket bij de Hoge Raad).", TRACE)
    assert f"verwijzing van {HOF} naar {HR} in plaats van een duiding" in fout.beweringen
    # Ook als het stuk de kop erboven is.
    kop = check_grounding(f"{HOF}\nZie toelichting bij {HR}.", TRACE)
    assert f"verwijzing van {HOF} naar {HR} in plaats van een duiding" in kop.beweringen
    # Een duiding met een verwijzing erbij is een duiding; een stuk zonder verwijzing ook.
    goed = check_grounding(f"In {HOF} beslist het hof over een voordeel uit aanmerkelijk belang in box 2 bij de "
                           f"vervreemding van aandelen; zie ook {HR}.", TRACE)
    assert not [b for b in goed.beweringen if b.startswith("verwijzing")]


def test_het_eerste_rapport_komt_via_het_hervatte_deel_bij_de_jurist():
    """Het hervatte deel krijgt zijn eerste rapport te zien en de opdracht de bevindingen ervan mee te nemen: de jurist ziet
    alleen het laatste rapport."""
    tekst = _hervatting()
    assert tekst.startswith(berichten.HERVATTING)
    assert "eerste rapport" in tekst and "lees het niet opnieuw" in tekst
