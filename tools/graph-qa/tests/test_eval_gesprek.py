"""De gesprekseval: scorers, de eval-annotatiepoort en de gouden gesprekken zelf.

Een meetinstrument dat stil verkeerd meet is erger dan geen: een verkeerd gespelde route of klasse
in de set maakt van een verwachting een verwachting die nooit kan slagen (of altijd). Vandaar de
guard op de set, net als `test_golden_annotatie.py` bij de annotatieset.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from agent.jas_klassen import GELDIGE_JAS_KLASSEN
from eval import run_eval
from eval.gesprek import (
    GOLDEN_GESPREK, Beurt, GesprekAnnotaties, routes_uit_status, run_gesprek_suite, score_beurt,
)

ROUTES = {"annotaties_lezen", "annotatie", "advies", "afgewezen", "definitie", "duiding", "algemeen"}
VELDEN = {"route", "niet_route", "tools_wel", "tools_niet", "max_tools", "bevat", "bevat_een",
          "verboden", "niet_ongegrond"}


def _cases():
    return run_eval.load_golden(GOLDEN_GESPREK)


def test_routes_uit_status_volgt_de_supervisorregels():
    assert routes_uit_status([
        "Supervisor · kiest de antwoord-worker · plan",
        "Specialist duiding · raadpleegt de kennisgraaf",
        "Graaf bevragen · get_lid",
        "Specialist duiding · raadpleegt de kennisgraaf",
    ]) == ["duiding"]
    assert routes_uit_status(["Lex · raadpleegt bestaande annotaties", "Specialist annotaties_lezen · x"]) \
        == ["annotaties_lezen"]
    assert routes_uit_status(["Supervisor · buiten de wet- en regelgeving in de graaf"]) == ["afgewezen"]
    assert routes_uit_status(["Lex · meer dan één artikel genoemd (9, 10)"]) == ["afgewezen"]
    assert routes_uit_status(["Supervisor · kiest de annotatie-worker · annoteer"]) == ["annotatie"]


def test_score_beurt_noemt_elke_afwijking():
    beurt = Beurt("v", "Antwoord over lid 2.", ["algemeen"], ["raw_sparql"] * 5, "ongegrond", None)
    fouten = score_beurt({"route": "duiding", "niet_route": ["algemeen"], "tools_wel": ["get_lid"],
                          "tools_niet": ["raw_sparql"], "max_tools": 3, "bevat": ["lid 3"],
                          "bevat_een": ["x", "y"], "verboden": ["lid 2"], "niet_ongegrond": True}, beurt)
    assert len(fouten) == 9
    assert score_beurt({"bevat": ["LID 2"], "max_tools": 5}, beurt) == []


def test_eval_poort_onthoudt_en_filtert():
    poort = GesprekAnnotaties(lambda q: "", [
        {"id": "a", "klasse": "Rechtssubject", "tekst": "de ontvanger", "eigenaar_iri": "urn:bwb:BWBR1:artikel:3:lid:1"},
        {"id": "b", "klasse": "Voorwaarde", "tekst": "indien", "eigenaar_iri": "urn:bwb:BWBR2:artikel:1"},
    ])
    poort.onthoud({"id": "c", "klasse": "Rechtssubject", "tekst": "de inspecteur",
                   "eigenaar_iri": "urn:bwb:BWBR2:artikel:11:lid:1"})
    assert [e["id"] for e in poort.zoeken({"jas_klassen": ["Rechtssubject"]})["resultaten"]] == ["a", "c"]
    assert [e["id"] for e in poort.zoeken({"bwb_id": "BWBR2"})["resultaten"]] == ["b", "c"]
    assert [e["id"] for e in poort.zoeken({"bron_iri": "urn:bwb:BWBR1:artikel:3"})["resultaten"]] == ["a"]
    assert poort.element("c")["element"]["tekst"] == "de inspecteur"
    assert poort.element("x")["status"] == "niet_gevonden"


def test_offline_gesprek_volgt_een_thread(tmp_path):
    cases, llm, graph, settings = run_eval._offline_gesprek_scenario(str(tmp_path / "cp.db"))
    res = asyncio.run(run_gesprek_suite(cases, settings=settings, llm=llm, graph=graph, stil=True))
    assert res[0].passed, [b.fouten for b in res[0].beurten]
    # De tweede beurt draaide in dezelfde thread: de eerste vraag zit in wat de specialist meekreeg.
    laatste = json.dumps(llm.calls[-1]["messages"], ensure_ascii=False)
    assert "Wat regelt artikel 9" in laatste


def test_gouden_gesprekken_zijn_geldig():
    cases = _cases()
    assert len({c["id"] for c in cases}) == len(cases)
    for c in cases:
        assert c["scenario"] in {"A", "B", "C", "R"}, c["id"]
        assert len(c["beurten"]) >= 2, f"{c['id']}: een gesprek heeft een vervolgbeurt nodig"
        for e in c.get("andere_annotaties") or []:
            assert e["klasse"] in GELDIGE_JAS_KLASSEN, e
            assert e["eigenaar_iri"].startswith("urn:bwb:BWBR"), e
        for b in c["beurten"]:
            v = b.get("verwacht") or {}
            assert set(v) <= VELDEN, (c["id"], set(v) - VELDEN)
            routes = ([v["route"]] if "route" in v else []) + list(v.get("niet_route") or [])
            assert set(routes) <= ROUTES, (c["id"], routes)


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["id"])
def test_elk_vervolg_toetst_iets(case):
    """Een vervolgbeurt zonder verwachting meet niets en telt toch als 'geslaagd'."""
    for b in case["beurten"][1:]:
        assert b.get("verwacht"), (case["id"], b["vraag"])
