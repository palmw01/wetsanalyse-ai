"""Skills laden in drie niveaus (ADR-016 §A2): de beschrijvingen in het voorvoegsel, de kern met `laad_skill`, een
reference met `lees_skill`, uit het bronpakket. Skilltekst is methode, geen bron."""
from __future__ import annotations

from types import SimpleNamespace

from agent import overdracht, skills
from agent.agentvorm import agent_voor
from agent.overdracht import CENTRAAL


def test_elke_methode_skill_staat_met_zijn_beschrijving_in_het_voorvoegsel_van_de_centrale_agent():
    assert set(skills.namen()) >= {"wetsanalyse", "wetsuitvoering"}
    tekst = agent_voor(CENTRAAL).systeemtekst
    assert "SKILLS:" in tekst and all(f"- {n}: " in tekst for n in skills.namen())
    assert all(0 < len(skills.beschrijving(n)) <= skills.MAX_BESCHRIJVING + 2 for n in skills.namen())
    # Een specialist van de supervisor houdt zijn systeemtekst byte-gelijk (ADR-010, P19).
    assert "SKILLS:" not in agent_voor("duiding").systeemtekst


def test_de_kern_is_de_rol_agent_of_anders_skill_md():
    wa = skills.kern("wetsanalyse")
    assert wa.startswith("SKILL wetsanalyse (methode, geen bron)") and "[basis]" in wa and "References" in wa
    wu = skills.kern("wetsuitvoering")
    assert "---" not in wu.split("\n", 2)[2][:10], "zonder frontmatter"
    assert "scenario" in wu and "References (lees_skill): " in wu


def test_een_reference_lezen_en_wat_niet_bestaat():
    tekst, ok = skills.antwoord("lees", "wetsuitvoering", "scenario")
    assert ok and tekst.startswith("SKILL wetsuitvoering, reference scenario")
    assert skills.antwoord("lees", "wetsuitvoering", "references/scenario.md")[1], "met pad en extensie mag ook"
    tekst, ok = skills.antwoord("lees", "wetsuitvoering", "bestaat-niet")
    assert not ok and "Kies uit" in tekst
    assert not skills.antwoord("laad", "onbekend")[1]


def test_laden_is_methode_en_geen_bron(monkeypatch):
    events: list[dict] = []
    monkeypatch.setattr(overdracht, "get_stream_writer", lambda: events.append)
    tu = {"id": "t1", "name": "lees_skill", "input": {"skill": "wetsuitvoering", "sectie": "scenario"}}
    upd = overdracht.overdracht_node(SimpleNamespace(), {"pending_tools": [tu], "source_trace": [("x", "y")]})
    [blok] = upd["messages"][0]["content"]
    assert blok["content"].startswith("SKILL wetsuitvoering") and not blok.get("is_error")
    assert "source_trace" not in upd, "skilltekst komt niet in de trace"
    assert overdracht.route_na_overdracht(None, upd) == "agent"
    assert any(e.get("type") == "status" and "Methode" in str(e) for e in events)
    fout = overdracht.overdracht_node(SimpleNamespace(), {"pending_tools": [{**tu, "input": {"skill": "x"}}]})
    assert fout["messages"][0]["content"][0]["is_error"]
