"""De referentieset en de scorers van de begrippenketen (ADR-004)."""
from __future__ import annotations

import copy

import pytest

from eval import begrippen_eval as be


@pytest.fixture(scope="module")
def ref():
    return be.laad()


def test_de_actuele_set_is_geldig_en_provisional(ref):
    _, _, manifest = ref
    assert manifest["referentie_status"] == "provisional"
    assert manifest["bevroren_op"] is None


def test_de_set_dekt_de_lastige_gevallen(ref):
    _, cases, _ = ref
    categorieen = {p["categorie"] for p in cases["paren"]}
    assert {"homoniem", "afwijking", "kop_van_samenstelling", "gelijkstelling", "mede_verstaan",
            "aanwijzend_voornaamwoord", "verwijzing_bedoeld_in"} <= categorieen


@pytest.mark.parametrize("sabotage, fout", [
    (lambda b, c: b["bronnen"][0].__setitem__("tekst", b["bronnen"][0]["tekst"] + " "), "bron_hash"),
    (lambda b, c: c["formuleringen"][0].__setitem__("start", 1), "letterlijk"),
    (lambda b, c: c["paren"][0].__setitem__("relatie", "lijkt_op"), "onbekende relatie"),
    (lambda b, c: c["paren"][0].__setitem__("motivatie", " "), "gok"),
    (lambda b, c: c["paren"].append({**c["paren"][0], "id": "R99", "relatie": "verschillend"}),
     "tegelijk"),
])
def test_elke_stille_afwijking_wordt_geweigerd(ref, sabotage, fout):
    bronnen, cases, manifest = copy.deepcopy(ref)
    sabotage(bronnen, cases)
    with pytest.raises(be.ReferentieFout, match=fout):
        be.valideer(bronnen, cases, manifest)


def test_een_gewijzigde_set_vraagt_een_nieuwe_hash(ref):
    bronnen, cases, manifest = copy.deepcopy(ref)
    cases["paren"][0]["motivatie"] += " (aangescherpt)"
    with pytest.raises(be.ReferentieFout, match="hash"):
        be.valideer(bronnen, cases, manifest)


def test_gevalideerd_kan_alleen_bevroren(ref):
    bronnen, cases, manifest = copy.deepcopy(ref)
    manifest["referentie_status"] = "adjudicated"
    with pytest.raises(be.ReferentieFout, match="bevroren"):
        be.valideer(bronnen, cases, manifest)


def test_manifest_voor_de_keten_volgt_de_referentie(ref):
    bronnen, cases, _ = ref
    m = be.manifest_uit(bronnen, cases)
    assert len(m.formuleringen) == len(cases["formuleringen"])
    assert m.bron("urn:bwb:BWBR0004770:artikel:2:lid:1:o:m").aanhef == "Deze wet verstaat onder:"


def test_bcubed_op_een_bekend_voorbeeld():
    items = ["a", "b", "c", "d"]
    assert be.bcubed([{"a", "b"}, {"c", "d"}], [{"a", "b"}, {"c", "d"}], items)["f"] == 1.0
    # Alles in één cluster: precisie per item 2/4, recall 1.
    alles = be.bcubed([{"a", "b", "c", "d"}], [{"a", "b"}, {"c", "d"}], items)
    assert alles == {"precisie": 0.5, "recall": 1.0, "f": 0.6667}
    # Alles los: precisie 1, recall per item 1/2.
    los = be.bcubed([], [{"a", "b"}, {"c", "d"}], items)
    assert (los["precisie"], los["recall"]) == (1.0, 0.5)


def test_scoor_telt_symmetrisch_en_gericht_juist():
    cases = {"formuleringen": [{"element_id": x} for x in "abc"],
             "paren": [{"van": "a", "naar": "b", "relatie": "zelfde_betekenis"},
                       {"van": "a", "naar": "c", "relatie": "hierarchie"}]}
    goed = be.Voorspelling(groepen=(("a", "b"),), relaties=(("hierarchie", "a", "c"),))
    verkeerd_om = be.Voorspelling(groepen=(("a", "b"),), relaties=(("hierarchie", "c", "a"),))
    assert be.scoor(goed, cases)["per_relatie"]["hierarchie"]["tp"] == 1
    assert be.scoor(verkeerd_om, cases)["per_relatie"]["hierarchie"]["tp"] == 0


def test_de_nulmeting_voegt_homoniemen_samen_en_de_scorer_ziet_het():
    r = be.meet("lemma")
    assert r["deterministisch"]
    assert "f18~f19" in r["samengevoegd_verschillend"]          # 'termijnen' in twee betekenissen
    assert r["per_relatie"]["hierarchie"]["recall"] == 0.0      # de nulmeting kent geen relaties
