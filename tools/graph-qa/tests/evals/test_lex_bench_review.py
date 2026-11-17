"""Lex Bench, de reviewer (plan §5, §22 besluit 4, LB2): de verschillen, de controle van een review en de telling.

Offline, tegen de opnames van de graaf: geen model, nul tokens. Een review is hier een vaste invoer; wat er vastligt is
welke categorie bij welk verschil mag, dat de tegenlezer Lex niet ziet, en dat team mist de casus niet wijzigt.
"""
from __future__ import annotations

import json

import pytest

from eval import lex_bench as lb
from eval import lex_bench_review as rv
from eval import lex_bench_team as team

pytestmark = pytest.mark.risico("R15", laag=1)

CASUS = "LB-06"


def _set_en_opname():
    pad = team.WORTEL / team.laad_casus(CASUS)["pad"]
    return (json.loads((pad / "set.json").read_text(encoding="utf-8")),
            json.loads((pad / "graafantwoorden.json").read_text(encoding="utf-8")))


def _als_team(s):
    """De eigen verwachting van de set als teamverwachting: dan moet L1 tegen het team gelijk zijn aan de scorekaart."""
    return {"casus_id": CASUS, "verwacht": s["verwacht"], "onenig": [],
            "uitgesloten": [dict(u, deelvraag=i) for u in s.get("uitgesloten", []) for i in range(len(s["deelvragen"]))]}


@pytest.fixture(scope="module")
def kaart():
    s, opname = _set_en_opname()
    return rv.lex_tegen_team(s, _als_team(s), opname)


def test_tegen_de_eigen_verwachting_geeft_het_de_scorekaart_van_l1(kaart):
    casus = next(c for c in lb.laad_manifest()["casussen"] if c["casus_id"] == CASUS)
    l1 = lb.scoor_casus(casus)
    for maat in ("recall_nodig", "recall", "precisie", "overlap"):
        assert kaart["maten"][maat] == l1["maten"][maat], maat
    assert sum(v["voorstel"] == "lex_mist" for v in kaart["verschillen"]) == l1["categorieen"]["lex_mist"]
    assert sum(v["voorstel"] == "lex_onterecht" for v in kaart["verschillen"]) == l1["categorieen"]["lex_onterecht"]


def test_de_verschillen_zijn_genummerd_en_herhaalbaar(kaart):
    s, opname = _set_en_opname()
    nogmaals = rv.lex_tegen_team(s, _als_team(s), opname)
    assert [v["verschil"] for v in kaart["verschillen"]] == [f"V{n}" for n in range(1, len(kaart["verschillen"]) + 1)]
    assert nogmaals == kaart


def _review(kaart, kies=lambda v: v["voorstel"]):
    return {"formulier": "lex-bench-review-1", "casus_id": CASUS, "modus": "verschillen", "run": "lb-06-proef-r",
            "oordelen": [{"verschil": v["verschil"], "deelvraag": v["deelvraag"], "bron_iri": v["bron_iri"],
                          "categorie": kies(v), "plek": "onbekend", "reden": "op de bron"} for v in kaart["verschillen"]]}


def test_een_review_volgens_de_voorstellen_klopt_en_telt(kaart):
    r = _review(kaart)
    assert rv.controleer(r, "verschillen", CASUS, kaart=kaart) == []
    uit = rv.verwerk(kaart, r)
    assert uit["categorieen"]["status"].startswith("voorstel van de reviewer")
    assert uit["categorieen"]["lex_mist"] + uit["categorieen"]["lex_onterecht"] == len(kaart["verschillen"])
    assert uit["nagekomen_voorstel"] == []


def test_team_mist_wordt_een_voorstel_voor_nagekomen_en_wijzigt_niets(kaart):
    onterecht = [v for v in kaart["verschillen"] if v["voorstel"] == "lex_onterecht"]
    assert onterecht, "de casus heeft een verschil nodig waar Lex koos"
    eerste = onterecht[0]["verschil"]
    r = _review(kaart, lambda v: "team_mist" if v["verschil"] == eerste else v["voorstel"])
    voor = json.dumps(kaart, sort_keys=True)
    uit = rv.verwerk(kaart, r)
    assert [n["bron_iri"] for n in uit["nagekomen_voorstel"]] == [onterecht[0]["bron_iri"]]
    assert uit["nagekomen_voorstel"][0]["nagekomen"] is True
    assert json.dumps(kaart, sort_keys=True) == voor


def test_een_categorie_die_niet_bij_het_verschil_past_gaat_niet_door(kaart):
    mist = next(v for v in kaart["verschillen"] if v["voorstel"] == "lex_mist")
    r = _review(kaart, lambda v: "team_mist" if v is mist else v["voorstel"])
    assert any("niet koos" in f for f in rv.controleer(r, "verschillen", CASUS, kaart=kaart))
    r = _review(kaart)
    r["oordelen"].pop()
    assert any("geen oordeel" in f for f in rv.controleer(r, "verschillen", CASUS, kaart=kaart))
    r = _review(kaart)
    r["oordelen"][0]["categorie"] = "eens"
    assert any("hoort niet bij de modus" in f for f in rv.controleer(r, "verschillen", CASUS, kaart=kaart))


def test_de_opdracht_noemt_de_verschillen_en_niet_de_coordinator(kaart):
    s, _ = _set_en_opname()
    tekst = rv.opdracht_verschillen(team.dossier_van(s), kaart, CASUS, "lb-06-proef-r")
    assert "## Voor de coördinator" not in tekst and '"verschil": "V1"' in tekst


# --- tegenlezen (besluit 4) ---

I1, I2, I3 = (f"urn:bwb:BWBR0004770:artikel:{n}:lid:1" for n in (1, 2, 3))
DOSSIER = {"naam": "Proef", "deelvragen": ["Eén?"]}


def _formulier():
    bep = {"rol": "kern", "zoekvraag": "a", "motivering": "draagt", "bewijs": {"tool": "bron_lezen", "citaat": "tekst"}}
    return {"formulier": "lex-bench-formulier-1", "casus_id": CASUS, "analist": "A", "run": "r-a",
            "deelvragen": [{"deelvraag": 0, "bepalingen": [dict(bep, bron_iri=I1), dict(bep, bron_iri=I2)],
                            "uitgesloten": [], "twijfel": []}]}


def _lezing(*oordelen):
    return {"formulier": "lex-bench-review-1", "casus_id": CASUS, "modus": "tegenlezen", "run": "r-r",
            "oordelen": [{"deelvraag": 0, "bron_iri": iri, "categorie": c, "reden": "op de bron", **extra}
                         for iri, c, extra in oordelen]}


def test_de_tegenlezer_ziet_lex_niet():
    tekst = rv.opdracht_tegenlezen(DOSSIER, _formulier(), CASUS, "r-r")
    assert lb.ROUTE_L1 not in tekst and "positie" not in tekst and "De verschillen" not in tekst
    assert I1 in tekst


def test_een_tegenlezing_zet_haar_bezwaren_in_onenig():
    lezing = _lezing((I1, "eens", {}), (I2, "hoort_er_niet_bij", {}),
                     (I3, "ontbreekt", {"bewijs": {"tool": "bron_lezen", "citaat": "mist"}}))
    casus = {"casus_id": CASUS, "niveau": "makkelijk", "gebruik": "ontwikkeling"}
    t = team.voeg_samen([_formulier()], DOSSIER, casus, "r", tegenlezing=lezing)
    assert [v["bron_iri"] for v in t["verwacht"]] == [I1]
    assert {(o["bron_iri"], o["soort"]) for o in t["onenig"]} == {(I2, "tegenlezer"), (I3, "tegenlezer")}
    drie = next(o for o in t["onenig"] if o["bron_iri"] == I3)
    assert drie["argumenten"] == {"A": {"plek": "niet genoemd"},
                                  "tegenlezer": {"plek": "ontbreekt", "motivering": "op de bron", "citaat": "mist"}}


@pytest.mark.parametrize("oordelen, melding", [
    (((I1, "eens", {}),), "geen oordeel"),
    (((I1, "eens", {}), (I2, "eens", {}), (I3, "ontbreekt", {})), "draagt bewijs"),
    (((I1, "eens", {}), (I2, "ontbreekt", {"bewijs": {"tool": "bron_lezen", "citaat": "x"}})), "staat al in het formulier"),
    (((I1, "eens", {}), (I2, "lex_mist", {})), "hoort niet bij de modus"),
    (((I1, "eens", {"plek": "onbekend"}), (I2, "eens", {})), "een plek hoort bij"),
])
def test_een_tegenlezing_met_een_fout_gaat_niet_door(oordelen, melding):
    fouten = rv.controleer(_lezing(*oordelen), "tegenlezen", CASUS, formulier=_formulier())
    assert any(melding in f for f in fouten), fouten


def test_een_tegenlezing_hoort_bij_een_analist():
    tweede = dict(_formulier(), analist="B")
    with pytest.raises(ValueError, match="één analist"):
        team.voeg_samen([_formulier(), tweede], DOSSIER, {"casus_id": CASUS, "niveau": "makkelijk",
                                                          "gebruik": "ontwikkeling"}, "r", tegenlezing=_lezing())
