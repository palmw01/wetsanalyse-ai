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


# --- één keuze voor het hele werkgebied (`PER_WERKGEBIED`, standaard uit) -------------------------------------------

def _toewijzing(*rijen) -> FakeLLM:
    return FakeLLM([response([tool_block("k1", "wijs_bepalingen_toe", {"toewijzingen": [
        {"nummer": n, "deelvraag": d, "rol": r} for n, d, r in rijen]})], "tool_use")])


def test_de_keuze_per_werkgebied_staat_standaard_uit():
    """Uit tot een meting beide vormen naast elkaar zette (`bronselectie_model_meting --werkgebied`)."""
    assert dk.PER_WERKGEBIED is False


def test_de_vereniging_gaat_om_de_beurt_en_onthoudt_waar_ze_gevonden_is():
    per = [dk.kandidaten([_optie("a"), _optie("b")], []), dk.kandidaten([_optie("b"), _optie("c")], []),
           dk.kandidaten([_optie("d")], [])]
    kand = dk.kandidaten_werkgebied(per)
    assert [k["bron_iri"] for k in kand] == ["a", "b", "d", "c"]
    assert {k["bron_iri"]: k["gevonden_bij"] for k in kand} == {"a": [0], "b": [0, 1], "d": [2], "c": [1]}


def test_de_vereniging_is_begrensd_en_houdt_de_herkomst_voorbij_de_grens():
    per = [dk.kandidaten([_optie(f"p{i}") for i in range(5)], []), dk.kandidaten([_optie("p4")], [])]
    kand = dk.kandidaten_werkgebied(per, maximaal=3)
    assert [k["bron_iri"] for k in kand] == ["p0", "p4", "p1"]
    assert kand[1]["gevonden_bij"] == [0, 1]


def test_het_model_zet_een_bepaling_bij_een_andere_deelvraag_dan_waar_ze_gevonden_is():
    """LB-08: 26a vond de zoekmachine bij deelvraag 3, ze hoort bij 1. Het model wijst aan, de code neemt over."""
    per = [dk.kandidaten([_optie("urn:bwb:X:artikel:26", "Terugvordering ...")], []), [],
           dk.kandidaten([_optie("urn:bwb:X:artikel:26a", "Het bedrag wordt teruggevorderd ..."),
                          _optie("urn:bwb:X:artikel:32", "Rente ...")], [])]
    kand = dk.kandidaten_werkgebied(per)
    llm = _toewijzing((1, 1, "kern"), (2, 1, "kern"), (3, 3, "kern"), (2, 1, "kern"), (9, 1, "kern"), (1, 7, "kern"),
                      (3, 2, "vreemd"))
    uit = dk.kies_werkgebied(llm, "m", ["Wanneer terugvorderen?", "Hoeveel?", "Welke rente?"], {"naam": "T"}, kand)
    assert [[k["bron_iri"].rsplit(":", 1)[-1] for k in dv] for dv in uit] == [["26", "26a"], ["32"], ["32"]]
    assert uit[1][0]["rol"] == "kern" and uit[0][1]["gevonden_bij"] == [2]
    assert len(llm.calls) == 1


def test_per_werkgebied_hoogstens_acht_per_deelvraag():
    kand = dk.kandidaten_werkgebied([dk.kandidaten([_optie(f"p{i}") for i in range(12)], [])])
    llm = _toewijzing(*[(i, 1, "kern") for i in range(1, 13)])
    assert len(dk.kies_werkgebied(llm, "m", ["v"], {}, kand)[0]) == dk.MAX_GEKOZEN


def test_per_werkgebied_zonder_tool_valt_terug():
    kand = dk.kandidaten_werkgebied([dk.kandidaten([_optie("a")], [])])
    llm = FakeLLM([response([text_block("Ik kies niets.")], "end_turn")])
    assert dk.kies_werkgebied(llm, "m", ["v"], {}, kand) is None


def test_per_werkgebied_zonder_kandidaten_geen_aanroep():
    llm = FakeLLM([])
    assert dk.kies_werkgebied(llm, "m", ["v", "w"], {}, []) == [[], []]
    assert not llm.calls


def test_de_prompt_per_werkgebied_noemt_alle_deelvragen_en_niet_waar_iets_gevonden_is():
    kand = dk.kandidaten_werkgebied([dk.kandidaten([_optie("a", "tekst a")], []),
                                     dk.kandidaten([_optie("b", "tekst b")], [])])
    tekst = dk.prompt_werkgebied(["Wanneer?", "Hoeveel?"], {"naam": "T", "buiten": "rente"}, kand)
    assert "Deelvragen:\n1. Wanneer?\n2. Hoeveel?" in tekst
    assert "1. a: tekst a" in tekst and "2. b: tekst b" in tekst
    assert "Buiten de afbakening: rente" in tekst and "gevonden" not in tekst


def test_het_schema_per_werkgebied_is_strict_en_klein():
    s = dk.schema_werkgebied()
    assert s["strict"] is True
    item = s["input_schema"]["properties"]["toewijzingen"]["items"]
    assert item["required"] == ["nummer", "deelvraag", "rol"] and item["additionalProperties"] is False


# --- de bronnenrun met de vlag ---------------------------------------------------------------------------------------

def _run_deelvraag(monkeypatch, llm, per_werkgebied):
    from agent import bronnen_vinden as bv

    lijsten = {"Wanneer?": [_optie("urn:bwb:BWBR0018472:artikel:26", "a")],
               "Welke rente?": [_optie("urn:bwb:BWBR0018472:artikel:26a", "b")]}
    monkeypatch.setattr(bv, "_kandidaten_bij",
                        lambda graph, vraag, *a: dk.kandidaten(lijsten[vraag], []))
    invoer = {"deelvragen": [{"id": "d1", "vraag": "Wanneer?"}, {"id": "d2", "vraag": "Welke rente?"}]}
    t1, t2 = bv._MODEL.set((llm, "m", {})), bv._PER_WERKGEBIED.set(per_werkgebied)
    try:
        v = bv.Verzameling([])
        bv._deelvraag(None, invoer, v)
    finally:
        bv._PER_WERKGEBIED.reset(t2)
        bv._MODEL.reset(t1)
    return v


def test_de_bronnenrun_per_werkgebied_legt_per_deelvraag_bewijs_vast(monkeypatch):
    llm = _toewijzing((1, 1, "kern"), (2, 1, "afhankelijkheid"))
    v = _run_deelvraag(monkeypatch, llm, True)
    assert len(llm.calls) == 1
    k = v.per_iri["urn:bwb:BWBR0018472:artikel:26a"]
    assert k["rol"] == "afhankelijkheid"
    assert k["bewijs"] == [{"methode": "deelvraag", "vanuit": "", "detail": {
        "deelvraag_id": "d1", "vraag": "Wanneer?", "route": "model_werkgebied", "bron": "pool",
        "gevonden_bij": ["d2"]}}]


def test_de_bronnenrun_valt_per_werkgebied_terug_op_de_keuze_per_deelvraag(monkeypatch):
    llm = FakeLLM([response([text_block("niets")], "end_turn"),
                   response([tool_block("k1", "kies_bepalingen", {"gekozen": [{"nummer": 1, "rol": "kern"}]})],
                            "tool_use"),
                   response([tool_block("k2", "kies_bepalingen", {"gekozen": []})], "tool_use")])
    v = _run_deelvraag(monkeypatch, llm, True)
    assert len(llm.calls) == 3
    assert [b["detail"]["route"] for b in v.per_iri["urn:bwb:BWBR0018472:artikel:26"]["bewijs"]] == ["model"]


def test_zonder_de_vlag_kiest_het_model_per_deelvraag(monkeypatch):
    llm = FakeLLM([response([tool_block(f"k{i}", "kies_bepalingen", {"gekozen": [{"nummer": 1, "rol": "kern"}]})],
                            "tool_use") for i in range(2)])
    v = _run_deelvraag(monkeypatch, llm, None)
    assert len(llm.calls) == 2 and all(c["tools"][0]["name"] == "kies_bepalingen" for c in llm.calls)
    assert {b["detail"]["route"] for k in v.per_iri.values() for b in k["bewijs"]} == {"model"}
