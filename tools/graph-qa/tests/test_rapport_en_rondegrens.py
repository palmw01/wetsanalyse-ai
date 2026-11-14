"""Het rapport van een subagent valt niet om op één passage, en een subagent heeft een eigen rondegrens (ADR-016 §A2, §A4;
meting 14 nov 2026: S03 en D01 vielen na twee geweigerde rapporten terug op tekst, D01 had 13 rondes en 801k)."""
from __future__ import annotations

import pytest

from agent import subagent as sub
from agent.agentvorm import MAX_RONDES_SUBAGENT, SUBAGENT_INSTRUCTIE
from agent.nodes.antwoord import max_rondes, route_after_agent
from agent.sjablonen import Onvulbaar, extern, vul
from fakes import make_settings
from test_subagent import ARTIKEL, OPDRACHT, TIEN_1, _rapport

GOED = {"bepaling": TIEN_1, "van": "De ontvanger kan uitstel", "tot": "van zes maanden.", "waarom": "De bevoegdheid."}
FOUT = {"bepaling": TIEN_1, "van": "Dit staat er niet", "tot": "", "waarom": "x"}


def test_een_passage_die_niet_te_tonen_is_valt_weg_en_staat_onder_open():
    a = vul("rapport", _rapport(onderbouwing=[GOED, FOUT]), [ARTIKEL])
    koppen = [getattr(b, "kop", b.soort) for b in a.blokken]
    assert koppen == ["Gedaan", "Bevindingen", "citaten", "Niet als citaat getoond"]
    assert len(a.blokken[2].items) == 1 and "Dit staat er niet" in a.blokken[3].tekst


def test_zonder_enige_passage_weigert_de_code_wel():
    with pytest.raises(Onvulbaar) as fout:
        vul("rapport", _rapport(onderbouwing=[FOUT]), [ARTIKEL])
    assert fout.value.code == "passage_niet_te_tonen"
    with pytest.raises(Onvulbaar) as fout:
        vul("rapport", _rapport(onderbouwing=[]), [ARTIKEL])
    assert fout.value.code == "geen_passage"


def test_extern_weigert_voor_een_antwoord_en_slaat_over_voor_een_rapport():
    items = [{"id": "ECLI:NL:HR:2026:586", "van_nr": 1, "tot_nr": 2}]
    with pytest.raises(Onvulbaar):
        extern.blokken(items, [])
    overgeslagen: list[str] = []
    assert extern.blokken(items, [], overgeslagen=overgeslagen) == []
    assert overgeslagen and "niet gelezen" in overgeslagen[0]


def test_een_rapport_met_alleen_een_niet_gelezen_stuk_zegt_wat_niet_kon():
    """Via `sjablonen.vul`: het veld `extern` met een stuk dat niet gelezen is, geen passage uit de wet."""
    invoer = _rapport(onderbouwing=[], extern=[{"id": "ECLI:NL:HR:2026:586", "van_nr": 1, "tot_nr": 2}])
    with pytest.raises(Onvulbaar) as fout:
        vul("rapport", invoer, [ARTIKEL])
    assert "niet gelezen" in str(fout.value)
    a = vul("rapport", {**invoer, "onderbouwing": [GOED]}, [ARTIKEL])
    assert any(getattr(b, "kop", "") == "Niet als citaat getoond" for b in a.blokken)


def test_een_subagent_heeft_een_eigen_rondegrens():
    s = make_settings()
    assert max_rondes(s, {"opdracht": OPDRACHT.model_dump()}) == min(MAX_RONDES_SUBAGENT, s.max_turns)
    assert max_rondes(s, {}) == s.max_turns
    tool = [{"id": "t", "name": "get_artikel", "input": {}}]
    b = type("B", (), {"settings": s})()
    kind = {"opdracht": OPDRACHT.model_dump(), "pending_tools": tool}
    assert route_after_agent(b, {**kind, "turns": MAX_RONDES_SUBAGENT - 1}) == "tools"
    assert route_after_agent(b, {**kind, "turns": MAX_RONDES_SUBAGENT}) == "verify"
    assert route_after_agent(b, {"pending_tools": tool, "turns": MAX_RONDES_SUBAGENT}) == "tools", "de rest houdt max_turns"
    assert f"hoogstens {MAX_RONDES_SUBAGENT} rondes" in SUBAGENT_INSTRUCTIE


def test_zonder_rapport_noemt_de_code_wat_er_lag():
    afloop = sub.Afloop(profiel="duiding", uitkomst="niet_gelukt")
    tekst = sub.rapport_tekst(afloop, {"answer": "vrije tekst", "source_trace": [ARTIKEL]})
    assert tekst.startswith(sub.GEEN_RAPPORT["niet_gelukt"]) and "Wat hij las" in tekst and "vrije tekst" not in tekst
    assert sub.rapport_tekst(afloop, {}) == sub.GEEN_RAPPORT["niet_gelukt"]
