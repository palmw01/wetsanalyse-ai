"""De meting van bronnen vinden (spoor D, fase A4), offline tegen de opgenomen graafantwoorden.

Bewaakt de set zelf (vorm, geen bepaling tegelijk verwacht én uitgesloten) en dat de standaard de
gemeten uitkomst houdt: alles wat nodig is gevonden en niets uitgeslotens voorgesteld. Een wijziging aan
de methoden die dat verandert, hoort een nieuwe meting in het logboek (en `--opnemen`) te krijgen.
"""
from __future__ import annotations

import json

import pytest

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
    f3f, oud = r["F3f (21 okt)"], r["vorige deelvraagmethode"]
    assert (f3f["recall"], f3f["recall_exact"], f3f["uitgesloten"]) == (0.211, 0.211, 1)
    assert f3f["recall_exact"] > oud["recall_exact"] and f3f["uitgesloten"] <= oud["uitgesloten"]
    # De pool vóór de rangschikking (3 nov 2026): de index vond met F3f 11 van de 19, de top 8 er 4. De helft
    # van het verlies zat in de rangschikking, de andere helft in het zoeken zelf.
    assert (f3f["recall_pool"], f3f["pool"]) == (0.579, 479)
    # Zoeken per term en op de delen van een samenstelling, de kop voor de hele pool en RRF (meetlogboek
    # `bronselectie-2026-11-03`). Deze set is daarvoor de ontwikkelset; de held-out set staat ernaast.
    vorige = r["zonder per_regeling"]
    assert (vorige["recall"], vorige["recall_exact"], vorige["uitgesloten"], vorige["recall_pool"]) == \
        (0.421, 0.421, 0, 0.842)
    # Om de beurt per regeling, wet eerst (meetlogboek `bronselectie-2026-11-03-rangsignaal`).
    nieuw = r["bepaling_opties"]
    assert (nieuw["recall"], nieuw["recall_nodig"], nieuw["uitgesloten"], nieuw["recall_pool"]) == \
        (0.474, 0.533, 0, 0.842)
    from eval.bronselectie_eval import ROUTES
    from agent.deelvraag_zoeken import MAX_PER_DEELVRAAG, MAX_VERWEZEN

    for naam, profiel in ((n, p) for n, p in r.items() if "pool" in p):
        # Met `verwijzingen` (aan sinds stap 8) komen er hoogstens `MAX_VERWEZEN` verwezen bepalingen bij.
        extra = MAX_VERWEZEN if ROUTES[naam].profiel.verwijzingen else 0
        assert all(p["aantal"] <= MAX_PER_DEELVRAAG + extra and p["gemarkeerd"] <= 2 for p in profiel["per_deelvraag"])
        assert all(p["in_pool"] >= p["gevonden"] for p in profiel["per_deelvraag"] if "in_pool" in p)


# --- de (vroegere) blinde sets: alleen het pad en de vorm, de uitkomst staat in Lex Bench -------------------------
# Hun uitkomst bij de blinde meting staat in `docs/lex-bench/bronselectie/held-out.json` (`python -m eval.lex_bench`), niet
# hier: een pin op een blinde uitkomst maakt de set rood voor wie de code afstemt, en dan is ze niet meer blind voor het
# afstemmen (plan Lex Bench §4.5, §20.4).

from eval import lex_bench  # noqa: E402


@pytest.mark.parametrize("naam", [s["set"] for s in lex_bench.laad()["sets"]])
def test_een_blinde_set_meet_offline_en_in_de_juiste_vorm(naam):
    """Het pad zonder model: de opname dekt elke query, elke route in het register bestaat nog en geeft maten in de vorm
    van het rapport. Geen uitkomst: die vergelijkt Lex Bench."""
    s = laad_set(naam)
    assert {v["deelvraag"] for v in s["verwacht"]} <= set(range(len(s["deelvragen"])))
    assert all(is_bron_iri(v["bron_iri"]) for v in s["verwacht"] + s["uitgesloten"])
    assert not {v["bron_iri"] for v in s["verwacht"]} & {u["bron_iri"] for u in s["uitgesloten"]}
    routes = next(x["uitkomst"] for x in lex_bench.laad()["sets"] if x["set"] == naam)
    nu, ontbrekend = lex_bench.meet_set(naam, list(routes))
    assert ontbrekend == 0, "de opname dekt niet elke query: draai --opnemen"
    assert set(nu) == set(routes), "een route uit het register bestaat niet meer"
    for route, maten in nu.items():
        assert set(routes[route]) <= set(maten), f"{route}: een maat uit het register ontbreekt"
        assert all(0 <= v <= 1 for m, v in maten.items() if m != "uitgesloten"), (route, maten)


def test_het_register_van_lex_bench_is_goed_gevormd_en_het_script_faalt_niet_op_een_verschil():
    reg = lex_bench.laad()
    assert reg["sets"] and all(s["meting"] and s["uitkomst"] for s in reg["sets"])
    assert all((SETS / s["set"] / "set.json").exists() for s in reg["sets"]), "een set uit het register bestaat niet"
    eerste = {**reg, "sets": [{**reg["sets"][0], "uitkomst": {
        r: {m: -1 for m in v} for r, v in reg["sets"][0]["uitkomst"].items()}}]}
    rijen = lex_bench.vergelijk(eerste)
    assert rijen and not any(r["gelijk"] for r in rijen), "een verzonnen uitkomst wijkt af"
    assert {"set", "route", "maat", "toen", "nu", "gelijk"} <= set(rijen[0])


def test_de_gebeurtenis_en_de_grondslag_op_de_ontwikkelset():
    """Zoekvragen a–d, PR 3 (4 nov 2026): op de ontwikkelset kwijtschelding stelt Lex de gebeurtenis bovenaan voor als
    de naam haar noemt, en op plek 3 zonder de naam; de grondslag vindt Iw 26 lid 1 en Uitv.reg. 7 lid 1, niet art. 10
    (dat draagt geen signaal van bestaansrecht). Een ontwikkelset: de blinde meting is `verrekening-concept`."""
    from eval.bronselectie_eval import meet_zoekvragen

    s = laad_set("kwijtschelding-concept")
    graaf = OpnameGraaf(json.loads((SETS / "kwijtschelding-concept" / "graafantwoorden.json").read_text()))
    r = meet_zoekvragen(graaf, s)
    assert graaf.ontbrekend == 0
    assert (r["plek_met_naam"], r["plek_zonder_naam"]) == (1, 3)
    assert (r["grondslag_recall"], r["grondslag_precisie"], len(r["grondslag"])) == (0.667, 0.25, 8)


@pytest.mark.parametrize("naam, pool, recall_nodig, juist, per_zoekvraag", [
    ("kwijtschelding-concept", 226, 1.0, 0.87, {"a": (2, 2), "b": (3, 3), "c": (5, 5), "d": (13, 13)}),
    ("bestuurdersaansprakelijkheid-concept", 218, 0.889, 0.95, {"a": (1, 1), "b": (3, 4), "c": (3, 3), "d": (13, 14)}),
    ("bezwaar-ontvankelijkheid-concept", 104, 0.615, 0.111, {"a": (2, 5), "b": (7, 10), "c": (0, 1), "d": (0, 1)}),
    ("invorderbaarheid-deelvragen-concept", 116, 0.818, 0.636, {"a": (0, 0), "b": (10, 12), "c": (1, 1), "d": (0, 5)}),
])
def test_de_pool_van_de_zoekvragen_op_de_ontwikkelsets(naam, pool, recall_nodig, juist, per_zoekvraag):
    """Zoekvragen a–d (PR 4, bijgesteld in PR 5): de pool vanuit de grondslag, zonder model. Op kwijtschelding vond het
    zoeken per deelvraag 0,33 van de verwachte bepalingen (blind); de pool alles wat nodig is, sinds een uitsluitstam
    die in de helft van de omgeving staat niet meer telt ("belastin" uit "gemeentelijke belastingen"). Bezwaar blijft
    zwak: de grondslag van het bezwaar (Awb 7:1, AWR 26a) heeft geen signaal van bestaansrecht. Ontwikkelsets; de
    blinde meting (`verrekening-concept`) komt later."""
    from eval.bronselectie_eval import meet_zoekvragen

    graaf = OpnameGraaf(json.loads((SETS / naam / "graafantwoorden.json").read_text()))
    r = meet_zoekvragen(graaf, laad_set(naam))
    assert graaf.ontbrekend == 0
    assert (r["pool"], r["pool_recall_nodig"], r["zoekvraag_juist"]) == (pool, recall_nodig, juist)
    assert {z: (x["gevonden"], x["verwacht"]) for z, x in r["per_zoekvraag"].items()} == per_zoekvraag


@pytest.mark.parametrize("naam, oud, nieuw", [
    ("kwijtschelding-concept", 0.095, (0.292, 0.333, 0.219, 0)),     # PR 6: de brugtermen (0,29 → 0,33)
    ("bestuurdersaansprakelijkheid-concept", 0.222, (0.409, 0.444, 0.219, 0)),
    ("bezwaar-ontvankelijkheid-concept", 0.533, (0.368, 0.4, 0.188, 0)),
    ("invorderbaarheid-deelvragen-concept", 0.364, (0.333, 0.455, 0.188, 0)),
])
def test_de_deelvraag_kiest_in_de_pool(naam, oud, nieuw):
    """Zoekvragen a–d, PR 5 (4 nov 2026): per deelvraag de opties uit de pool, met de zoekvraag van de vraagvorm als
    voorkeur en de woorden gewogen naar hun zeldzaamheid in de pool. Recall nodig tegen het zoeken op de woorden van de
    deelvraag: kwijtschelding 0,10 → 0,29, bestuurdersaansprakelijkheid 0,22 → 0,44, invorderbaarheid 0,36 → 0,46;
    bezwaar 0,53 → 0,40 (een zwakke pool). Geen uitgesloten bepaling. Ontwikkelsets."""
    from eval.bronselectie_eval import meet_intake

    graaf = OpnameGraaf(json.loads((SETS / naam / "graafantwoorden.json").read_text()))
    r = meet_intake(graaf, laad_set(naam))
    assert graaf.ontbrekend == 0
    assert r["bepaling_opties"]["recall_nodig"] == oud
    z = r["zoekvragen (PR 5)"]
    assert (z["recall"], z["recall_nodig"], z["precisie"], z["uitgesloten"]) == nieuw


@pytest.mark.parametrize("naam,woorden,zoekvragen", [
    ("termijnen-deelvragen-concept", 0.125, 0.062),
    # De blinde set Verrekening staat niet meer hier maar in Lex Bench (`held-out.json`), om dezelfde reden als hierboven.
])
def test_de_standaard_van_stap_8_houdt_de_gemeten_uitkomst(naam, woorden, zoekvragen):
    """Stap 8 van het plan Termijnen (16 nov 2026): `termen_idf`, `verwijzingen`, `brug_omschrijving` en
    `overzicht_streng` staan aan. Termijnen is de ontwikkelset van het plan; de blinde set Verrekening (meetlogboek
    `bronselectie-2026-11-16-blind`) staat in Lex Bench. Recall nodig op de woordenroute en op de zoekvragenroute."""
    from eval.bronselectie_eval import ROUTES, meet_intake

    graaf = OpnameGraaf(json.loads((SETS / naam / "graafantwoorden.json").read_text()))
    r = meet_intake(graaf, laad_set(naam), {k: ROUTES[k] for k in ("standaard (stap 8)", "zoekvragen standaard (stap 8)")})
    assert graaf.ontbrekend == 0
    assert round(r["standaard (stap 8)"]["recall_nodig"], 3) == woorden
    assert round(r["zoekvragen standaard (stap 8)"]["recall_nodig"], 3) == zoekvragen
