"""Na een rapport vat de centrale agent samen, en wat gelezen is staat apart van wat alleen gevonden is (ADR-016 §A4;
meting bundel 115, 14 nov 2026: S01 las na `klaar` 17 keer zelf opnieuw voor 376k, en D01 noemde 16 uitspraken "gelezen"
waarvan het kind er 7 alleen in een zoekresultaat zag)."""
from __future__ import annotations

import json
from types import SimpleNamespace

from agent import subagent as sub
from agent.gelezen import gelezen_en_gevonden
from agent.grounding import check_grounding
from agent.nodes import antwoord as antwoordnodes
from agent.nodes.antwoord import NA_RAPPORT, NA_SUBAGENT, na_subagent
from agent.nodes import subagent_route as route
from fakes import make_settings
from test_subagent import STATE, Api, _kinderen

A, B, C, D = "ECLI:NL:HR:2020:1", "ECLI:NL:HR:2021:2", "ECLI:NL:HR:2022:3", "ECLI:NL:HR:2019:9"


def _zoek(*eclis: str) -> tuple[str, str]:
    return "zoek_uitspraken", json.dumps({"status": "ok", "volledig": True, "aantal": len(eclis), "resultaten": [
        {"id": e, "label": f"HR {e[-6:]}"} for e in eclis]})


def _lees(ecli: str, tekst: str = "De rechter overweegt.") -> tuple[str, str]:
    return "get_uitspraak", json.dumps({"status": "ok", "volledig": True, "aantal": 1, "stuk": {
        "id": ecli, "label": f"HR {ecli[-6:]}", "link": "https://example.org"}, "resultaten": [{"nr": 1, "tekst": tekst}]})


TRACE = [_zoek(A, B, C), _lees(A, f"Zie ook {D}.")]


def test_na_een_rapport_klaar_leest_de_centrale_agent_niet_zelf_opnieuw():
    assert na_subagent({"subagenten": [{"uitkomst": "klaar"}]}, "get_uitspraak") == NA_RAPPORT
    assert na_subagent({"subagenten": [{"uitkomst": "vraag"}]}, "zoek_uitspraken") == NA_RAPPORT
    # Een kind dat niet afrondde, houdt zijn eigen aanwijzing, ook naast een dat wel afrondde.
    assert na_subagent({"subagenten": [{"uitkomst": "klaar"}, {"uitkomst": "niet_gelukt"}]}, "get_artikel") == NA_SUBAGENT
    assert na_subagent({"subagenten": [{"uitkomst": "klaar"}]}, "antwoord_extern") == "", "afronden kan altijd"
    assert "Lees niet zelf opnieuw" in sub.als_toolresultaat("algemeen", "klaar", "x")


def test_de_weigering_na_klaar_gaat_door_tools_node(monkeypatch):
    uitgevoerd = []
    monkeypatch.setattr(antwoordnodes, "execute_tool", lambda *a, **_k: uitgevoerd.append(a) or "{}")
    monkeypatch.setattr(antwoordnodes, "get_stream_writer", lambda: (lambda _e: None))
    tu = {"id": "t1", "name": "get_uitspraak", "input": {"id": A}}
    state = {"pending_tools": [tu], "messages": [], "source_trace": [], "specialist": "centraal",
             "agentvorm": "centraal", "subagenten": [{"uitkomst": "klaar"}], "run_id": "r"}
    upd = antwoordnodes.tools_node(SimpleNamespace(settings=make_settings(), graph=None, stop_check=None), state)
    [blok] = upd["messages"][-1]["content"]
    assert blok["content"] == NA_RAPPORT and not uitgevoerd


def test_gelezen_is_wat_een_leestool_gaf_en_gevonden_wat_alleen_een_zoektool_noemde():
    gelezen, gevonden = gelezen_en_gevonden(TRACE)
    assert [i for i, _ in gelezen] == [A]
    assert [i for i, _ in gevonden] == [B, C], "een verwijzing in een gelezen stuk is geen gelezen stuk"
    # Een stuk zonder tekst (alleen een PDF) is niet gelezen.
    pdf = ("get_uitspraak", json.dumps({"status": "error", "reden": "alleen_pdf", "stuk": {"id": B, "label": "HR"}}))
    assert [i for i, _ in gelezen_en_gevonden([*TRACE, pdf])[0]] == [A]


def test_het_rapport_uit_code_noemt_gelezen_en_alleen_gevonden_apart():
    tekst = sub.rapport_tekst(sub.Afloop(profiel="algemeen", uitkomst="niet_gelukt"), {"source_trace": TRACE})
    assert "Gelezen (1;" in tekst and "Alleen in zoekresultaten gezien, niet gelezen (2;" in tekst
    klaar = sub.rapport_tekst(sub.Afloop(profiel="algemeen", uitkomst="klaar"),
                              {"rapport": {"status": "klaar"}, "answer": "Bevindingen.", "source_trace": TRACE})
    assert klaar.startswith("Bevindingen.") and "niet gelezen (2;" in klaar


def test_verify_toetst_een_aantal_gelezen_stukken_tegen_wat_er_gelezen_is():
    """Een zoekresultaat met drie treffers maakt geen drie gelezen uitspraken."""
    fout = check_grounding("De subagent las 3 uitspraken van de Hoge Raad over de melding.", TRACE)
    assert any("gelezen (gelezen: 1)" in b for b in fout.beweringen) and fout.niveau != "gegrond"
    goed = check_grounding("De subagent las 1 uitspraken; 3 uitspraken vond hij in de zoekresultaten.", TRACE)
    assert not any("gelezen (gelezen" in b for b in goed.beweringen)


def test_het_eind_van_de_regie_noemt_het_model_van_het_kind(monkeypatch):
    """Meting bundel 115: bij S01 ontbrak het model van het kind in de meting; het eind van de regie draagt het nu ook."""
    events = []
    monkeypatch.setattr(route, "get_stream_writer", lambda: events.append)
    monkeypatch.setattr(sub, "WetsanalyseApi", lambda *_a: Api())
    kinderen, _, _ = _kinderen({"rapport": {"status": "klaar"}, "answer": "Per uitspraak: …", "source_trace": [],
                                "modellen": ["claude-licht"]})
    vraag = "Vat per uitspraak samen wat de rechter over artikel 36 van de Invorderingswet 1990 zegt."
    b = SimpleNamespace(kinderen=kinderen, settings=SimpleNamespace(legt_zelf_vast=True), loop=None, stop_check=None,
                        graph=None)
    route.subagent_route_node(b, {**STATE, "question": vraag, "source_trace": []})
    [taak] = [e for e in events if e["type"] == "regie_taak" and e["fase"] == "eind"]
    [regie] = [e for e in events if e["type"] == "regie" and e["fase"] == "eind"]
    assert taak["modellen"] == ["claude-licht"] and regie["kinderen"][0]["modellen"] == ["claude-licht"]

    from eval.centrale_agent_vat import vat

    regel = next(r for r in (json.loads(x) for x in open("eval/golden_centrale_agent_delegatie.jsonl")
                             if x.startswith("{")) if r["id"] == "D01")
    opdracht = regel
    rij = vat({"id": "D01", "run": 1, "beurten": [{"label": "gemeten", "events": [e for e in events if e["type"] == "regie"]}]},
              opdracht)
    assert rij["kind_modellen"] == ["claude-licht"], "ook zonder het eind-event van de taak"
