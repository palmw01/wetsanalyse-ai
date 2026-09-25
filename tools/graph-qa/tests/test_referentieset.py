"""Geversioneerde referentieset: schema §10.4, manifest en adjudicatieguard (validatieplan V1)."""
from __future__ import annotations

import copy
import hashlib

import pytest

from agent.jas_klassen import JAS_KLASSEN
from eval.metrieken import controleer_status
from eval.referentieset import (
    ReferentieFout, casussen, dekkingsgaten, laad, sethash, valideer, valideer_casus,
)

TEKST = "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet."
VRAAG_TIJD = next(k.vraag for k in JAS_KLASSEN if k.naam == "Tijdsaanduiding").split("?")[0] + "?"


def _element(**over) -> dict:
    e = {"gid": "G1", "start": 37, "eind": 86, "tekst": "zes weken na de dagtekening van het aanslagbiljet",
         "klasse": "Tijdsaanduiding", "subtype": None, "context": None, "motivatie": "Termijn met startmoment.",
         "herkenningsvraag": None, "h2_ref": None, "annotation_status": None, "relaties": [], "adjudicatie": None}
    return {**e, **over}


def _casus(**over) -> dict:
    c = {"id": "T01", "familie": "IW", "split": "ontwikkeling", "bron_id": "L04", "vindplaats": "BWBR0004770/9/1",
         "versie": "2026-07-01", "tekst": TEKST, "tekst_sha256": hashlib.sha256(TEKST.encode()).hexdigest(),
         "source_status": None, "tekstsoort": "wet", "constructies": [], "referentie_status": "provisional",
         "gold": [_element()], "negatief": []}
    return {**c, **over}


def _adjudicated() -> dict:
    """Een casus met een volledig adjudicatierecord volgens §10.4/§11."""
    return _casus(
        referentie_status="adjudicated", source_status="valid", constructies=["termijn"],
        adjudicatie={"annotator_a": "jurist-a", "annotator_b": "jurist-b", "adjudicator": "jurist-c",
                     "datum": "2026-10-01", "protocolversie": "1"},
        gold=[_element(herkenningsvraag=VRAAG_TIJD, h2_ref="H2:108", annotation_status="correct",
                       adjudicatie={"verschil": "gelijk", "besluit": "gelijk"})])


def _manifest(cases: list[dict], **over) -> dict:
    m = {"referentie_versie": "vT", "protocolversie": None, "bevroren_op": None,
         "referentie_status": {c["id"]: c["referentie_status"] for c in cases}, "sha256": sethash(cases),
         "voorganger": None, "changelog": [], "toelichting": ""}
    return {**m, **over}


def test_actuele_versie_is_geldig_en_nog_volledig_provisional():
    cases = casussen()
    assert len(cases) == 24
    assert {c["referentie_status"] for c in cases} == {"provisional"}
    # Niet beoordeeld = leeg, niet ingevuld (V1: "niet: gold invullen").
    assert all(c["source_status"] is None and not c["constructies"] and not c["negatief"] for c in cases)
    assert all(g["annotation_status"] is None and g["adjudicatie"] is None for c in cases for g in c["gold"])
    _, manifest = laad()
    assert manifest["bevroren_op"] is None and manifest["referentie_versie"] == "v1"


def test_manifest_drift_faalt():
    cases, manifest = laad()
    gewijzigd = copy.deepcopy(cases)
    gewijzigd[0]["gold"][0]["motivatie"] += " (stil gecorrigeerd)"
    with pytest.raises(ReferentieFout, match="manifest-drift"):
        valideer(gewijzigd, manifest)
    with pytest.raises(ReferentieFout, match="bevroren"):
        valideer(gewijzigd, {**manifest, "bevroren_op": "2026-10-01"})
    with pytest.raises(ReferentieFout, match="referentie_status"):
        valideer(cases, {**manifest, "referentie_status": {**manifest["referentie_status"], "IW01": "gold"}})


def test_volledig_geadjudiceerde_casus_is_geldig_maar_alleen_in_een_bevroren_versie():
    c = _adjudicated()
    assert valideer_casus(c) == controleer_status(c) == "adjudicated"
    with pytest.raises(ReferentieFout, match="niet-bevroren"):
        valideer([c], _manifest([c]))
    valideer([c], _manifest([c], bevroren_op="2026-10-02", protocolversie="1"))


@pytest.mark.parametrize("breek", [
    lambda c: c.update(adjudicatie=None),
    lambda c: c["adjudicatie"].update(annotator_b=""),
    lambda c: c["adjudicatie"].pop("protocolversie"),
    lambda c: c.update(source_status=None),
    lambda c: c.update(source_status="unusable"),
    lambda c: c.update(constructies=[]),
    lambda c: c["gold"][0].update(annotation_status=None),
    lambda c: c["gold"][0].update(herkenningsvraag=None),
    lambda c: c["gold"][0].update(h2_ref=None),
    lambda c: c["gold"][0].update(adjudicatie=None),
], ids=["zonder-record", "zonder-annotator-b", "zonder-protocol", "bron-niet-gecontroleerd", "bron-onbruikbaar",
        "zonder-constructies", "element-zonder-status", "zonder-herkenningsvraag", "zonder-h2", "element-zonder-besluit"])
def test_adjudicated_zonder_volledig_record_faalt(breek):
    c = _adjudicated()
    breek(c)
    with pytest.raises(ReferentieFout):
        valideer_casus(c)
    with pytest.raises(ValueError):
        controleer_status(c)


@pytest.mark.parametrize("breek, fout", [
    (lambda c: c.update(onbekend_veld=1), "onbekend"),
    (lambda c: c.update(tekstsoort="roman"), "tekstsoort"),
    (lambda c: c.update(constructies=["zinsbouw"]), "constructies"),
    (lambda c: c.update(tekst_sha256="0" * 64), "tekst_sha256"),
    (lambda c: c["gold"][0].update(start=38, tekst="es weken na de dagtekening van het aanslagbiljet"), "woordgrenzen"),
    (lambda c: c["gold"][0].update(tekst="iets anders"), "verwacht"),
    (lambda c: c["gold"][0].update(klasse="Tijd"), "klasse"),
    (lambda c: c["gold"][0].update(subtype="variabelewaarde"), "subtype"),
    (lambda c: c["gold"][0].update(h2_ref="H2-108"), "H2:NN"),
    (lambda c: c["gold"][0].update(herkenningsvraag="Wanneer ongeveer?"), "letterlijk"),
    (lambda c: c["gold"][0].update(relaties=[{"soort": "norm", "naar_gid": "G9"}]), "onbekende gid"),
    (lambda c: c["gold"][0].update(relaties=[{"soort": "oorzaak", "naar_gid": "G1"}]), "soort"),
    (lambda c: c["gold"][0].update(annotation_status="debatable",
                                   adjudicatie={"verschil": "klasse", "besluit": "kies_a"}), "debatable"),
    (lambda c: c.update(gold=[_element(), _element()]), "dubbele gid"),
    (lambda c: c.update(negatief=[{"start": 24, "eind": 36, "tekst": "invorderbaar", "waarom_geen_element": ""}]),
     "waarom_geen_element"),
], ids=lambda x: x if isinstance(x, str) else "")
def test_schemafouten_worden_benoemd(breek, fout):
    c = _casus()
    breek(c)
    with pytest.raises(ReferentieFout, match=fout):
        valideer_casus(c)


def test_negatief_element_en_relatie_zijn_geldig():
    c = _casus(negatief=[{"start": 24, "eind": 36, "tekst": "invorderbaar",
                          "waarom_geen_element": "Naamwoordelijk deel van het gezegde, geen object."}],
               gold=[_element(relaties=[{"soort": "tijdsanker", "naar_gid": "G2"}]),
                     _element(gid="G2", start=0, eind=20, tekst="Een belastingaanslag", klasse="Rechtsobject")])
    assert valideer_casus(c) == "provisional"


def test_changelog_vraagt_een_voorganger():
    c = _casus()
    regel = {"casus": "T01", "gid": "G1", "reden": "span", "oud": "37-86", "nieuw": "37-85",
             "datum": "2026-10-03", "adjudicator": "jurist-c"}
    with pytest.raises(ReferentieFout, match="voorganger"):
        valideer([c], _manifest([c], changelog=[regel]))
    valideer([c], _manifest([c], changelog=[regel], voorganger="v1"))


def test_sethash_negeert_opmaak_niet_de_inhoud():
    c = _casus()
    assert sethash([c]) == sethash([dict(reversed(list(c.items())))])
    assert sethash([c]) != sethash([_casus(versie="2026-07-02")])


def test_dekkingsgaten_eisen_twee_voorkomens_in_twee_families():
    a = _casus(constructies=["termijn"])
    b = _casus(id="T02", familie="Awb", constructies=["termijn"])
    gaten = dekkingsgaten([a, b])
    assert "Tijdsaanduiding" not in gaten["klassen"] and "termijn" not in gaten["constructies"]
    assert "Rechtssubject" in gaten["klassen"] and "passief" in gaten["constructies"]
    assert "Tijdsaanduiding" in dekkingsgaten([a, _casus(id="T02", constructies=["termijn"])])["klassen"]
