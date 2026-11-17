"""Het eindantwoord behandelt elk rapport `klaar` (meting P01 na #1618, 16 nov 2026; meetverslag
`centrale-agent-2026-11-16-p01`). Twee subagents rapporteerden `klaar`; het antwoord vatte de Kamerstukken per stuk samen
en noemde de rechtspraak (13 gelezen arresten) alleen als aantal onder Twijfel.

`verify` toetst nu of het antwoord van elk kind met een rapport `klaar` minstens één stuk noemt buiten twijfel en leemte.
Ontbreekt er een, dan volgt één correctieronde met de opdracht het mee te nemen, niet om iets te schrappen. Ging het
daarna nog mis, dan geen tweede ronde en geen `onbevestigd`: het is geen feit zonder bron.

`MAX_STUKKEN` (4 per antwoord) was in P01 niet de oorzaak: het antwoord gebruikte er 2, en geen aanroep werd geweigerd."""
from __future__ import annotations

import json
from types import SimpleNamespace

from agent import subagent as sub
from agent.nodes import antwoord as antwoordnodes
from agent.sjablonen.extern import MAX_STUKKEN
from fakes import FakeGraph, FakeLLM, make_settings

KST = ["kst-35305-6", "Kamerstukken II 2019/20, 35305, nr. 6"]
ECLI = ["ECLI:NL:HR:2019:576", "HR 12 april 2019"]
KINDEREN = [
    {"profiel": "wetsgeschiedenis_lezen", "uitkomst": "klaar", "rapport": True, "stukken": [KST]},
    {"profiel": "rechtspraak_lezen", "uitkomst": "klaar", "rapport": True, "stukken": [ECLI]},
]


def _antwoord(*blokken):
    return {"sjabloon": "extern", "blokken": [{"soort": "toelichting", "door": "lex",
                                               "tekst": "Hieronder volgt een samenvatting per bron."}, *blokken]}


EXTERN_KST = {"soort": "extern", "id": KST[0], "label": KST[1], "kern": "De nota gaat niet over artikel 22."}
TWIJFEL = {"soort": "twijfel", "punten": ["Van de 103 uitspraken zijn er alleen 11 van de Hoge Raad gelezen, waaronder "
                                          f"{ECLI[0]}."]}


def test_een_rapport_alleen_onder_twijfel_ontbreekt():
    ontbrekend = sub.ontbrekende_rapporten(KINDEREN, _antwoord(EXTERN_KST, TWIJFEL), "")
    assert [a["profiel"] for a in ontbrekend] == ["rechtspraak_lezen"]
    bewering = sub.ontbreekt_bewering(ontbrekend[0])
    assert bewering.startswith(sub.RAPPORT_ONTBREEKT) and "rechtspraak_lezen" in bewering and ECLI[1] in bewering


def test_een_rapport_dat_het_antwoord_noemt_is_behandeld():
    extern_ecli = {"soort": "extern", "id": ECLI[0], "label": ECLI[1]}
    assert sub.ontbrekende_rapporten(KINDEREN, _antwoord(EXTERN_KST, extern_ecli, TWIJFEL), "") == []
    # Ook in het korte antwoord, bij label of in een citeervorm.
    kort = {"soort": "toelichting", "tekst": "In HR 12 april 2019 legt de Hoge Raad de maatstaf uit."}
    assert sub.ontbrekende_rapporten(KINDEREN, _antwoord(EXTERN_KST, kort), "") == []
    citeer = {"soort": "toelichting", "tekst": "Kamerstuk 35305, nr. 6 en ecli nl hr 2019 576 gaan erover."}
    assert sub.ontbrekende_rapporten(KINDEREN, _antwoord(citeer), "") == []


def test_vrije_tekst_telt_alleen_voor_de_kop_over_twijfel():
    tekst = f"**{KST[0]}**: de nota gaat niet over artikel 22.\n\n**Twijfel**\n- {ECLI[0]} en 12 andere uitspraken."
    assert [a["profiel"] for a in sub.ontbrekende_rapporten(KINDEREN, None, tekst)] == ["rechtspraak_lezen"]
    assert sub.ontbrekende_rapporten(KINDEREN, None, tekst.replace("**Twijfel**", "")) == []


def test_alleen_een_rapport_klaar_met_stukken_naast_de_wet_telt():
    anders = [{**KINDEREN[1], "uitkomst": "niet_gelukt"}, {**KINDEREN[1], "rapport": False},
              {"profiel": "bepalingen_duiden", "uitkomst": "klaar", "rapport": True}]
    assert sub.ontbrekende_rapporten(anders, _antwoord(EXTERN_KST), "") == []


def test_de_stukken_van_een_rapport_komen_uit_wat_het_citeert_en_las():
    lezing = ("get_uitspraak", json.dumps({"status": "ok", "volledig": True, "aantal": 1,
                                           "stuk": {"id": ECLI[0], "label": ECLI[1]},
                                           "resultaten": [{"nr": 1, "tekst": "De Hoge Raad oordeelt."}]}))
    kind = {"antwoord": {"blokken": [{"soort": "extern", "id": KST[0], "label": KST[1]}]},
            "source_trace": [lezing, ("get_artikel", "{}")]}
    assert sub.stukken_van_rapport(kind) == [KST, ECLI]
    assert sub.Afloop(profiel="x", stukken=[ECLI]).als_dict()["stukken"] == [ECLI]
    assert "stukken" not in sub.Afloop(profiel="x").als_dict()


def _verify(state, monkeypatch, **settings):
    monkeypatch.setattr(antwoordnodes, "get_stream_writer", lambda: (lambda _e: None))
    b = SimpleNamespace(graph=FakeGraph(result=""), llm=FakeLLM([]), settings=make_settings(**settings))
    return antwoordnodes.verify_node(b, {"question": "Vat de rechtspraak en de Kamerstukken per bron samen.",
                                         "source_trace": [], "subagenten": KINDEREN, **state})


def test_verify_vraagt_een_correctieronde_en_correct_vraagt_het_rapport_mee_te_nemen(monkeypatch):
    uit = _verify({"answer": f"**{KST[0]}**: de nota gaat niet over artikel 22.\n\n**Twijfel**\n- Niet alle arresten zijn gelezen."},
                  monkeypatch)
    assert uit["grounded"] is False and any(b.startswith(sub.RAPPORT_ONTBREEKT) for b in uit["beweringen"])
    assert not any(b.startswith(sub.RAPPORT_ONTBREEKT) for b in uit["onbevestigd"])
    correctie = antwoordnodes.correct_node(None, {"beweringen": uit["beweringen"], "subagenten": KINDEREN})
    tekst = correctie["messages"][0]["content"]
    assert "rechtspraak_lezen" in tekst and "Neem dat rapport mee" in tekst and str(MAX_STUKKEN) in tekst
    assert "Schrap" not in tekst, "een ontbrekend rapport gaat erin, niet eruit"


def test_na_de_correctie_geen_tweede_ronde_en_geen_onbevestigd(monkeypatch):
    uit = _verify({"answer": f"**{KST[0]}**: de nota gaat niet over artikel 22.", "corrected": True}, monkeypatch)
    assert not any(b.startswith(sub.RAPPORT_ONTBREEKT) for b in uit["beweringen"] + uit["onbevestigd"])


def test_een_subagent_zelf_en_zonder_correctie_valt_erbuiten(monkeypatch):
    tekst = f"**{KST[0]}**: de nota gaat niet over artikel 22."
    assert not _verify({"answer": tekst, "opdracht": {"doel": "x"}}, monkeypatch)["beweringen"]
    assert not _verify({"answer": tekst}, monkeypatch, grounding_correct=False)["beweringen"]
