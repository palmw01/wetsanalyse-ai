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
    for profiel in (p for p in r.values() if "pool" in p):
        assert all(p["aantal"] <= 8 and p["gemarkeerd"] <= 2 for p in profiel["per_deelvraag"])
        assert all(p["in_pool"] >= p["gevonden"] for p in profiel["per_deelvraag"] if "in_pool" in p)


def test_de_held_out_meting_houdt_haar_uitkomst():
    """De blinde meting van 3 nov 2026 (meetlogboek `bronselectie-2026-11-03`), offline op haar opname, met
    de gecorrigeerde telling. Het zoeken generaliseerde (pool 0,56 → 0,94), de rangschikking maar half
    (recall nodig 0,36 → 0,27). Deze set is na die ene run ook een ontwikkelset."""
    from eval.bronselectie_eval import meet_intake

    naam = "invorderbaarheid-deelvragen-concept"
    s = laad_set(naam)
    graaf = OpnameGraaf(json.loads((SETS / naam / "graafantwoorden.json").read_text()))
    r = meet_intake(graaf, s)
    assert graaf.ontbrekend == 0
    vorige, f3f = r["zonder per_regeling"], r["F3f (21 okt)"]
    assert (vorige["recall"], vorige["recall_nodig"], vorige["precisie"], vorige["recall_pool"]) == \
        (0.333, 0.273, 0.281, 0.944)
    assert (f3f["recall"], f3f["recall_nodig"], f3f["precisie"], f3f["recall_pool"]) == (0.278, 0.364, 0.156, 0.556)
    nieuw = r["bepaling_opties"]
    assert (nieuw["recall"], nieuw["recall_nodig"], nieuw["precisie"]) == (0.389, 0.364, 0.281)
    assert nieuw["uitgesloten"] == f3f["uitgesloten"] == 0


def test_de_held_out_meting_van_het_rangsignaal_houdt_haar_uitkomst():
    """De blinde meting van 3 nov 2026 op de set bestuurdersaansprakelijkheid (meetlogboek
    `bronselectie-2026-11-03-rangsignaal`), één keer live, daarna offline op haar opname. Om de beurt per
    regeling verandert hier niets; de fusie verliest het van F3f. Het verlies zit in woorden: de analist
    schrijft "melden", "loonheffing", "aansprakelijk stellen", de wet "mededeling", "loonbelasting",
    "aansprakelijkstelling". Deze set is na die ene run een ontwikkelset."""
    from eval.bronselectie_eval import meet_intake

    naam = "bestuurdersaansprakelijkheid-concept"
    s = laad_set(naam)
    graaf = OpnameGraaf(json.loads((SETS / naam / "graafantwoorden.json").read_text()))
    r = meet_intake(graaf, s)
    assert graaf.ontbrekend == 0
    nieuw, f3f, zonder_fusie = r["bepaling_opties"], r["F3f (21 okt)"], r["zonder fusie"]
    assert (nieuw["recall"], nieuw["recall_nodig"], nieuw["uitgesloten"], nieuw["recall_pool"]) == \
        (0.227, 0.222, 3, 0.909)
    assert (f3f["recall"], f3f["recall_nodig"], f3f["recall_pool"]) == (0.318, 0.389, 0.455)
    assert (zonder_fusie["recall"], zonder_fusie["recall_nodig"]) == (0.364, 0.389)


def test_de_held_out_meting_van_het_meezoekende_dossier_houdt_haar_uitkomst():
    """De blinde meting van 4 nov 2026 op de set kwijtschelding (meetlogboek `bronselectie-2026-11-04-dossier`),
    één keer live, daarna offline op haar opname. Geen van de vier dossiervlaggen won op de ontwikkelsets, en hier
    evenmin: de woordenkloof zit al in het zoeken (pool 0,33). De deelvragen en de analysevraag zeggen nergens
    "kwijtschelding"; alleen de naam van het werkgebied doet dat, en die leest het zoeken niet. Deze set is na die
    ene run een ontwikkelset."""
    from eval.bronselectie_eval import meet_intake

    naam = "kwijtschelding-concept"
    s = laad_set(naam)
    assert s["aanleiding"] and s["doel"] and s["praktijkvoorbeeld"]
    assert {v["deelvraag"] for v in s["verwacht"]} == set(range(len(s["deelvragen"])))
    assert all(is_bron_iri(v["bron_iri"]) for v in s["verwacht"] + s["uitgesloten"])
    graaf = OpnameGraaf(json.loads((SETS / naam / "graafantwoorden.json").read_text()))
    r = meet_intake(graaf, s)
    assert graaf.ontbrekend == 0
    nieuw, alles = r["bepaling_opties"], r["met dossier (alles)"]
    assert (nieuw["recall"], nieuw["recall_nodig"], nieuw["uitgesloten"], nieuw["recall_pool"]) == \
        (0.083, 0.095, 0, 0.333)
    # Per dossierterm een lijst vergroot de pool, maar verdringt de opties van de deelvraag en deelt ze meer.
    assert (alles["recall_nodig"], alles["recall_pool"]) == (0.048, 0.542) and alles["gedeeld"] > nieuw["gedeeld"]
    for v in ("dossier_velden", "dossier_omgeving", "gelijkenis"):
        assert r[f"met {v}"]["recall_nodig"] == nieuw["recall_nodig"]
