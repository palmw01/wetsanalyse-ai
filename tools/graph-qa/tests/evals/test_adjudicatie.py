"""Blind formulier, vergelijking A/B en adjudicatie (adjudicatieprotocol v1, validatieplan V2)."""
from __future__ import annotations

import copy
import json
import re

import pytest

from eval.adjudicatie import (
    PROTOCOLVERSIE, adjudiceer, besluitsjabloon, overeenstemming, valideer_annotatie, vergelijk,
)
from eval.referentieset import ReferentieFout, bevries, casussen, sethash, valideer, valideer_casus
from scripts.blind_formulier import ZICHTBAAR, gegevens, render

CASUS = next(c for c in casussen() if c["id"] == "IW01")
TEKST = CASUS["tekst"]
T, RO, RB = "Tijdsaanduiding", "Rechtsobject", "Rechtsbetrekking"


def _el(fragment: str, klasse: str, **over) -> dict:
    s = TEKST.index(fragment)
    return {"start": s, "eind": s + len(fragment), "tekst": fragment, "klasse": klasse,
            "motivatie": f"{klasse} volgens de annotator.", "herkenningsvraag": {
                T: "Wanneer, op welk moment?", RO: "Wat is het voorwerp van een recht of plicht?",
                RB: "Hoe verhouden twee rechtssubjecten zich tot elkaar?"}[klasse],
            "h2_ref": "H2:100", **over}


def _ann(naam: str, elementen: list[dict], **over) -> dict:
    return {"protocolversie": PROTOCOLVERSIE, "annotator": naam, "casus_id": "IW01",
            "tekst_sha256": CASUS["tekst_sha256"], "source_status": "valid", "elementen": elementen,
            "negatief": [], **over}


A = _ann("jurist-a", [
    _el("Een belastingaanslag", RO),
    _el("zes weken na de dagtekening van het aanslagbiljet", T),
    _el("de dagtekening", RO),
    _el("het aanslagbiljet", RO),
])
B = _ann("jurist-b", [
    _el("Een belastingaanslag", RO),                                  # gelijk
    _el("zes weken na de dagtekening", T),                            # span (te smal t.o.v. A)
    _el("de dagtekening", T),                                         # klasse
    _el("Een belastingaanslag is invorderbaar", RB),                  # alleen B
])


# --- blind formulier ----------------------------------------------------------------------------

def _payload(html: str) -> dict:
    m = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S)
    return json.loads(m.group(1))


def test_formulier_toont_alleen_bron_en_klassen_geen_systeem_of_conceptoutput():
    html = render(gegevens())
    data = _payload(html)
    assert set(data) == {"protocolversie", "referentie_versie", "klassen", "casussen"}
    assert len(data["casussen"]) == 24 and all(set(c) == set(ZICHTBAAR) for c in data["casussen"])
    # Geen conceptmarkering, dossiertoelichting of reviewvraag, ook niet als losse tekst in de pagina.
    for c in casussen():
        for veld in ("grammatica", "samenhang", "scenario", "reviewvraag"):
            assert c[veld] not in html, (c["id"], veld)
        for g in c["gold"]:
            assert g["motivatie"] not in html, (c["id"], g["gid"])
    for verboden in ('"gold"', '"annotaties"', "possible_classes", "evidence", "beslissing", "aandacht"):
        assert verboden not in html


def test_formulier_biedt_herkenningsvragen_die_de_validator_accepteert():
    data = gegevens(ids=["IW01"])
    assert [c["id"] for c in data["casussen"]] == ["IW01"]
    tijd = next(k for k in data["klassen"] if k["naam"] == T)
    el = _el("zes weken na de dagtekening van het aanslagbiljet", T, herkenningsvraag=tijd["vragen"][1])
    c = copy.deepcopy(CASUS)
    c["gold"] = [{**el, "gid": "G1", "subtype": None, "context": None, "annotation_status": None,
                  "relaties": [], "adjudicatie": None}]
    assert valideer_casus(c) == "provisional"


def test_formulier_sluit_een_script_in_de_brontekst_niet_voortijdig_af():
    data = gegevens(ids=["IW01"])
    data["casussen"][0]["tekst"] = "a </script><script>alert(1)</script> b"
    html = render(data)
    assert _payload(html)["casussen"][0]["tekst"] == "a </script><script>alert(1)</script> b"


# --- annotatorbestand ---------------------------------------------------------------------------

@pytest.mark.parametrize("breek, fout", [
    (lambda a: a.update(tekst_sha256="0" * 64), "andere tekstversie"),
    (lambda a: a.update(protocolversie="0"), "protocolversie"),
    (lambda a: a.update(annotator=""), "annotator"),
    (lambda a: a.update(source_status=None), "source_status"),
    (lambda a: a["elementen"][0].update(start=1, tekst="en belastingaanslag"), "woordgrenzen"),
    (lambda a: a["elementen"][0].pop("h2_ref"), "ontbreekt"),
])
def test_annotatorbestand_wordt_tegen_de_casus_gevalideerd(breek, fout):
    a = copy.deepcopy(A)
    breek(a)
    with pytest.raises(ReferentieFout, match=fout):
        valideer_annotatie(a, CASUS)


# --- vergelijken --------------------------------------------------------------------------------

def test_vergelijking_op_positie():
    rijen = [(v.soort, v.tekst, v.klasse_a, v.klasse_b) for v in vergelijk(A, B, TEKST)]
    assert rijen == [
        ("gelijk", "Een belastingaanslag", RO, RO),
        ("alleen_b", "Een belastingaanslag is invorderbaar", None, RB),
        ("span", "zes weken na de dagtekening van het aanslagbiljet", T, T),
        ("klasse", "de dagtekening", RO, T),
        ("alleen_a", "het aanslagbiljet", RO, None),
    ]
    assert [v.id for v in vergelijk(A, B, TEKST)] == ["V01", "V02", "V03", "V04", "V05"]


def test_meerdere_functies_op_dezelfde_span_worden_een_op_een_gekoppeld():
    a = _ann("a", [_el("de dagtekening", RO), _el("de dagtekening", T)])
    b = _ann("b", [_el("de dagtekening", T)])
    assert [(v.soort, v.klasse_a, v.klasse_b) for v in vergelijk(a, b, TEKST)] == [
        ("alleen_a", RO, None), ("gelijk", T, T)]


def test_overeenstemming_en_kappa():
    o = overeenstemming(vergelijk(A, B, TEKST))
    assert o["per_soort"] == {"gelijk": 1, "alleen_b": 1, "span": 1, "klasse": 1, "alleen_a": 1}
    assert o["positie_overeenstemming"] == pytest.approx(2 / 5)
    # Twee paren op dezelfde positie: (RO,RO) en (RO,T) → po = 1/2, pe = (2·1)/4 = 1/2 → κ = 0.
    assert o["kappa_klasse"] == pytest.approx(0.0)

    a = _ann("a", [_el("Een belastingaanslag", RO), _el("de dagtekening", T),
                   _el("het aanslagbiljet", RO), _el("zes weken", T)])
    b = _ann("b", [_el("Een belastingaanslag", RO), _el("de dagtekening", T),
                   _el("het aanslagbiljet", T), _el("zes weken", T)])
    # po = 3/4; A: RO 2, T 2; B: RO 1, T 3 → pe = (2·1 + 2·3)/16 = 1/2 → κ = 0.5.
    assert overeenstemming(vergelijk(a, b, TEKST))["kappa_klasse"] == pytest.approx(0.5)
    assert overeenstemming([])["positie_overeenstemming"] is None


# --- adjudiceren en bevriezen -------------------------------------------------------------------

BESLUITEN = {"verschillen": {"V02": {"besluit": "kies_b"}, "V03": {"besluit": "kies_a"},
                             "V04": {"besluit": "debatable"}, "V05": {"besluit": "geen"}}}


def test_besluitsjabloon_vraagt_alleen_om_echte_verschillen():
    assert set(besluitsjabloon(A, B, vergelijk(A, B, TEKST))["verschillen"]) == {"V02", "V03", "V04", "V05"}


def test_adjudicatie_levert_een_casus_die_na_bevriezen_adjudicated_is():
    uit = adjudiceer(CASUS, A, B, BESLUITEN, "jurist-c", "2026-10-01")
    assert [(g["gid"], g["tekst"], g["klasse"], g["annotation_status"], g["adjudicatie"]["besluit"])
            for g in uit["gold"]] == [
        ("G01", "Een belastingaanslag", RO, "correct", "gelijk"),
        ("G02", "Een belastingaanslag is invorderbaar", RB, "correct", "kies_b"),
        ("G03", "zes weken na de dagtekening van het aanslagbiljet", T, "correct", "kies_a"),
        ("G04", "de dagtekening", RO, "debatable", "debatable"),
        ("G05", "de dagtekening", T, "debatable", "debatable"),
    ]
    casus = {**copy.deepcopy(CASUS), **uit, "constructies": ["termijn", "naamwoordelijk_gezegde"],
             "referentie_status": "review_pending"}
    assert valideer_casus(casus) == "review_pending"
    bevroren = bevries([casus])
    assert valideer_casus(bevroren[0]) == "adjudicated"
    manifest = {"referentie_versie": "vT", "protocolversie": PROTOCOLVERSIE, "bevroren_op": "2026-10-02",
                "referentie_status": {"IW01": "adjudicated"}, "sha256": sethash(bevroren), "voorganger": None,
                "changelog": [], "toelichting": ""}
    valideer(bevroren, manifest)


def test_adjudicatie_weigert_ontbrekende_of_onmogelijke_besluiten():
    zonder = copy.deepcopy(BESLUITEN)
    del zonder["verschillen"]["V04"]
    with pytest.raises(ReferentieFout, match="V04"):
        adjudiceer(CASUS, A, B, zonder, "jurist-c", "2026-10-01")
    onmogelijk = copy.deepcopy(BESLUITEN)
    onmogelijk["verschillen"]["V02"] = {"besluit": "kies_a"}          # V02 is alleen B
    with pytest.raises(ReferentieFout, match="kies_a"):
        adjudiceer(CASUS, A, B, onmogelijk, "jurist-c", "2026-10-01")
    with pytest.raises(ReferentieFout, match="dezelfde persoon"):
        adjudiceer(CASUS, A, {**B, "annotator": "jurist-a"}, BESLUITEN, "jurist-c", "2026-10-01")
    with pytest.raises(ReferentieFout, match="gezamenlijk"):
        adjudiceer(CASUS, A, B, BESLUITEN, "jurist-a", "2026-10-01")
    assert adjudiceer(CASUS, A, B, {**BESLUITEN, "gezamenlijk": True}, "jurist-a", "2026-10-01")


def test_verschil_in_bronstatus_vraagt_een_besluit():
    b = {**B, "source_status": "ambiguous"}
    assert besluitsjabloon(A, b, vergelijk(A, b, TEKST))["source_status"] is None
    with pytest.raises(ReferentieFout, match="source_status"):
        adjudiceer(CASUS, A, b, BESLUITEN, "jurist-c", "2026-10-01")
    uit = adjudiceer(CASUS, A, b, {**BESLUITEN, "source_status": "valid"}, "jurist-c", "2026-10-01")
    assert uit["source_status"] == "valid"


def test_bevriezen_maakt_alleen_review_pending_adjudicated():
    assert [c["referentie_status"] for c in bevries(casussen())] == ["provisional"] * 24
