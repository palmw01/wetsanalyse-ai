"""De meting van bronnen vinden (spoor D, fase A4), offline tegen de opgenomen graafantwoorden.

Bewaakt de set zelf (vorm, geen bepaling tegelijk verwacht én uitgesloten) en dat de standaard de
gemeten uitkomst houdt: alles wat nodig is gevonden en niets uitgeslotens voorgesteld. Een wijziging aan
de methoden die dat verandert, hoort een nieuwe meting in het logboek (en `--opnemen`) te krijgen.
"""
from __future__ import annotations

import json

from agent.bronnen_vinden import STANDAARD
from agent.graph.queries import is_bron_iri
from eval.bronselectie_eval import SETS, STANDAARD_SET, OpnameGraaf, laad_set, meet

SET = laad_set()


def test_de_set_is_goed_gevormd():
    assert SET["status"] == "concept" and SET["analysevraag"] and SET["kern"]
    verwacht = {v["bron_iri"] for v in SET["verwacht"]}
    uitgesloten = {u["bron_iri"] for u in SET["uitgesloten"]}
    assert not verwacht & uitgesloten
    assert all(is_bron_iri(i) for i in verwacht | uitgesloten | {k["bron_iri"] for k in SET["kern"]})
    assert all(v["rol"] in ("kern", "afhankelijkheid", "aanverwant") and v["motivering"] for v in SET["verwacht"])
    assert all(u["motivering"] for u in SET["uitgesloten"])


def test_de_standaard_houdt_de_gemeten_uitkomst():
    graaf = OpnameGraaf(json.loads((SETS / STANDAARD_SET / "graafantwoorden.json").read_text()))
    r = meet(graaf, SET, {"standaard": STANDAARD})["standaard"]
    assert graaf.ontbrekend == 0, "de opname dekt niet elke query: draai --opnemen"
    assert r["recall_nodig"] == 1.0
    assert r["overbodig"] == 0.0
    assert r["aantal"] <= 15


def test_de_meting_per_deelvraag_houdt_de_gemeten_uitkomst():
    """F3f: `bepaling_opties` op de set met deelvragen (blind gemeten 21 okt 2026, meetlogboek
    `bronselectie-2026-10-21`). Een wijziging die deze getallen verandert, hoort een nieuwe meting – en
    op een nieuwe set, want deze is dan een ontwikkelset."""
    from eval.bronselectie_eval import INTAKE_SET, meet_intake

    s = laad_set(INTAKE_SET)
    assert s["status"] == "concept" and s["deelvragen"] and s["regelingen"]
    assert {v["deelvraag"] for v in s["verwacht"]} == set(range(len(s["deelvragen"])))
    assert all(is_bron_iri(v["bron_iri"]) for v in s["verwacht"] + s["uitgesloten"])
    assert not {v["bron_iri"] for v in s["verwacht"]} & {u["bron_iri"] for u in s["uitgesloten"]}
    graaf = OpnameGraaf(json.loads((SETS / INTAKE_SET / "graafantwoorden.json").read_text()))
    r = meet_intake(graaf, s)
    assert graaf.ontbrekend == 0, "de opname dekt niet elke query: draai --opnemen"
    nieuw, oud = r["bepaling_opties"], r["vorige deelvraagmethode"]
    assert (nieuw["recall"], nieuw["recall_exact"], nieuw["uitgesloten"]) == (0.211, 0.211, 1)
    assert nieuw["recall_exact"] > oud["recall_exact"] and nieuw["uitgesloten"] <= oud["uitgesloten"]
    assert all(p["aantal"] <= 8 and p["gemarkeerd"] <= 2 for p in nieuw["per_deelvraag"])
