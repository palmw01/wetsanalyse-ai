"""De proef `Zoekprofiel.model_kiest` (pilot LB3): de code levert de kandidaten, het model wijst nummers aan, de code
neemt iri en tekst over. Zonder model en zonder graaf."""
from __future__ import annotations

from agent import deelvraag_keuze as dk
from agent.deelvraag_zoeken import STANDAARD_PROFIEL
from fakes import FakeLLM, response, text_block, tool_block


def _optie(iri: str, tekst: str = "", **extra) -> dict:
    return {"bron_iri": iri, "label": iri.rsplit(":", 1)[-1], "tekst": tekst, **extra}


def test_de_vlag_staat_standaard_aan():
    """Aan sinds de meting `bronselectie-2026-11-17-model`; zonder model in de run kiest de code."""
    assert STANDAARD_PROFIEL.model_kiest is True


def test_zonder_model_in_de_run_kiest_de_code():
    from agent import bronnen_vinden
    assert bronnen_vinden._MODEL.get() is None
    assert bronnen_vinden._model_kiest(None, "v", [], {}, [], None, "") is None


def test_kandidaten_om_de_beurt_ontdubbeld_en_zonder_buiten():
    pool = [_optie("a"), _optie("b"), _optie("c")]
    woorden = [_optie("b"), _optie("x", buiten=True), _optie("d"), _optie("e")]
    kand = dk.kandidaten(pool, woorden)
    assert [k["bron_iri"] for k in kand] == ["a", "b", "d", "c", "e"]
    assert [k["bron"] for k in kand] == ["pool", "woorden", "woorden", "pool", "woorden"]


def test_kandidaten_begrensd():
    pool = [_optie(f"p{i}") for i in range(30)]
    woorden = [_optie(f"w{i}") for i in range(30)]
    kand = dk.kandidaten(pool, woorden, maximaal=6)
    assert [k["bron_iri"] for k in kand] == ["p0", "w0", "p1", "w1", "p2", "w2"]


def test_het_model_wijst_aan_de_code_neemt_over():
    kand = dk.kandidaten([_optie("urn:bwb:X:artikel:4", "De dwangsom bedraagt ...")],
                         [_optie("urn:bwb:X:artikel:5", "Het bestuursorgaan beslist ...")])
    llm = FakeLLM([response([tool_block("k1", "kies_bepalingen", {"gekozen": [
        {"nummer": 2, "rol": "kern"}, {"nummer": 2, "rol": "kern"}, {"nummer": 9, "rol": "kern"},
        {"nummer": 1, "rol": "afhankelijkheid"}]})], "tool_use")])
    gekozen = dk.kies(llm, "m", "Welke dwangsom?", {"naam": "Termijn"}, kand)
    assert [(g["bron_iri"], g["rol"]) for g in gekozen] == [
        ("urn:bwb:X:artikel:5", "kern"), ("urn:bwb:X:artikel:4", "afhankelijkheid")]
    assert gekozen[0]["tekst"] == "Het bestuursorgaan beslist ..."


def test_hoogstens_acht():
    kand = dk.kandidaten([_optie(f"p{i}") for i in range(12)], [])
    llm = FakeLLM([response([tool_block("k1", "kies_bepalingen", {"gekozen": [
        {"nummer": i, "rol": "kern"} for i in range(1, 13)]})], "tool_use")])
    assert len(dk.kies(llm, "m", "v", {}, kand)) == dk.MAX_GEKOZEN


def test_zonder_tool_valt_de_code_terug():
    kand = dk.kandidaten([_optie("a")], [])
    llm = FakeLLM([response([text_block("Ik kies niets.")], "end_turn")])
    assert dk.kies(llm, "m", "v", {}, kand) is None


def test_zonder_kandidaten_geen_aanroep():
    llm = FakeLLM([])
    assert dk.kies(llm, "m", "v", {}, []) == []
    assert not llm.calls


def test_de_prompt_noemt_dossier_vraag_en_genummerde_tekst():
    kand = dk.kandidaten([_optie("a", "x " * 400)], [])
    tekst = dk.prompt("Welke termijn?", {"naam": "Termijnen", "buiten": "bezwaar"}, kand)
    assert "Werkgebied: Termijnen" in tekst and "Buiten de afbakening: bezwaar" in tekst
    assert "Deelvraag: Welke termijn?" in tekst and "1. a: " in tekst
    assert len(tekst) < 800
