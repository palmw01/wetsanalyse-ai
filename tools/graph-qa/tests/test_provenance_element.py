"""Provenance per element (ADR-001 PR 15): de zestien vragen uit opdracht §40, per element te
beantwoorden uit het element-spoor plus de `run` van de beurt – zonder de keten opnieuw te draaien.
"""
from __future__ import annotations

from agent.jas_pipeline.classificatie import kandidaatregel
from test_hybride_keten import KetenLLM, _draai


def _beurt(**kw):
    events = _draai(KetenLLM(**kw))
    run = next(e for e in events if e["type"] == "run")["run"]
    return [e["element"] for e in events if e["type"] == "element"], run


def _antwoorden(el, run):
    """Elk antwoord uit wat bewaard wordt: het element (met `trace`) en de run van de beurt."""
    t, inst = el["trace"], run["instellingen"]
    k, b = t["kandidaat"], t["beslissing"]
    return {
        "welke tekstspan": (el["ankers"][0]["bron_iri"], el["ankers"][0]["start"], el["ankers"][0]["eind"]),
        "waarom kandidaat": [e["code"] for e in k["bewijs"]],
        "welke detectoren": sorted({e["detector"] for e in k["bewijs"]}),
        "welke grammaticale structuur": [e["relatie"] for e in k["bewijs"]],   # leeg zonder parser
        "welke JAS-signalen": [e["regel"] for e in k["bewijs"] if e["regel"]],
        "welke mogelijke klassen": k["mogelijke_klassen"],
        "was een LLM nodig": b["door"] == "model",
        "welke exacte vraag": t["vraag"],
        "welke beslissing gaf het model": b["klasse"] if b["door"] == "model" else None,
        "welke validators draaiden": t["validatie"],
        "was er onzekerheid": t["twijfel"],
        "waarom reviewer of mens": t["resolutie"],
        "welke uiteindelijke beslissing": (el["klasse"], b["status"]),
        "welke JAS-versie": t["jas_versie"],
        "hoe geprojecteerd": el["ankers"],        # de projectie is een functie van ankers + klasse
        "welke provenance": (run["model"], run["prompt_hash"], run["methode_versie"],
                             inst["meting"]["classifier_prompt"],
                             inst["meting"]["taal_model"] or "geen parser"),
    }


def test_alle_zestien_vragen_zijn_per_element_te_beantwoorden():
    elementen, run = _beurt()
    assert elementen
    for el in elementen:
        a = _antwoorden(el, run)
        assert len(a) == 16
        assert a["waarom kandidaat"] and a["welke detectoren"] and a["welke mogelijke klassen"]
        assert a["welke JAS-versie"] == "1.0.10"
        assert a["welke uiteindelijke beslissing"][0] == el["klasse"]
        if a["was een LLM nodig"]:
            assert a["welke exacte vraag"].startswith(el["trace"]["kandidaat"]["label"] + " |")
            assert a["welke beslissing gaf het model"] == el["klasse"]
        else:
            assert a["welke exacte vraag"] == ""


def test_de_vraag_in_het_spoor_is_letterlijk_wat_het_model_zag():
    llm = KetenLLM()
    events = _draai(llm)
    prompt = llm.calls[3]["messages"][0]["content"]
    for el in (e["element"] for e in events if e["type"] == "element"):
        if el["trace"]["beslissing"]["door"] == "model":
            assert el["trace"]["vraag"] in prompt


def test_resolutie_en_twijfel_staan_in_het_spoor_van_het_betrokken_element():
    elementen, _ = _beurt(tool_aanroep=False)
    betwist = [el for el in elementen if el["aandacht"] == "geel"]
    assert betwist
    for el in betwist:
        assert el["trace"]["twijfel"] and el["trace"]["resolutie"]
        assert el["trace"]["beslissing"]["status"] == "HUMAN_REVIEW"


def test_kandidaatregel_is_een_regel_zonder_brontekst():
    from bronmodel import Span, tekst_hash
    from agent.jas_pipeline.kandidaten import Candidate, Evidence
    k = Candidate.maak(Span("urn:t", 0, 3, "abc", tekst_hash("abc")), ["Voorwaarde"],
                       [Evidence(detector="d", code="C")]).model_copy(update={"label": "C001"})
    assert "\n" not in kandidaatregel(k) and kandidaatregel(k).startswith('C001 | "abc"')
