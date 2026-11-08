"""De gegenereerde relatiecatalogus (ADR-011, `app/jas_relaties.py`) tegen de klassen en subtypes van de api."""
from __future__ import annotations

import re

import pytest

from app import jas_relaties as rel
from app.annotatie_v2_contracts import Element
from app.validation import GELDIGE_JAS_KLASSEN

SUBTYPEN = set(re.search(r"\^\(\|([^)]*)\)\$", Element.model_fields["jas_subtype"].metadata[0].pattern)
               .group(1).split("|"))


@pytest.mark.parametrize("code", sorted(rel.RELATIETYPEN))
def test_elk_type_noemt_bestaande_klassen_en_subtypes(code):
    t = rel.RELATIETYPEN[code]
    assert set(t["van"]) | set(t["naar"]) <= GELDIGE_JAS_KLASSEN
    for paar in t["paren"]:
        assert {paar.get("van_subtype", ""), paar.get("naar_subtype", "")} - {""} <= SUBTYPEN
    assert rel.drager_kant(code) in ("van", "naar")


def test_de_lijsten_bovenaan_kennen_alleen_bestaande_klassen():
    assert set(rel.CENTRALE_KLASSEN) <= GELDIGE_JAS_KLASSEN
    assert rel.IMPLICIET_TOEGESTAAN == ("Rechtssubject",)
    assert set(rel.KARDINALITEIT) <= GELDIGE_JAS_KLASSEN


def test_toegestaan_volgt_de_klassen_van_het_type():
    assert rel.toegestaan("plichthebbende", "Rechtssubject", "Rechtsbetrekking")
    assert not rel.toegestaan("plichthebbende", "Rechtsbetrekking", "Rechtssubject")   # richting telt
    assert not rel.toegestaan("bestaat_niet", "Rechtssubject", "Rechtsbetrekking")
    assert rel.toegestaan("uitvoer", "Afleidingsregel", "Tijdsaanduiding")             # een regel levert een moment op


def test_waarde_eist_het_subtype_van_het_paar():
    par, tijd = "Parameter en parameterwaarde", "Tijdsaanduiding"
    assert rel.toegestaan("waarde", par, par, "parameterwaarde")
    assert not rel.toegestaan("waarde", par, par, "parameter")
    assert rel.toegestaan("waarde", par, tijd, "parameterwaarde", "verbijzondert parameter")
    assert not rel.toegestaan("waarde", par, tijd, "parameterwaarde", "")
    # Een variabelewaarde hoort niet bij een parameter.
    assert not rel.toegestaan("waarde", "Variabele en variabelewaarde", par, "variabelewaarde")


def test_volgorde_alleen_bij_invoer_en_operand():
    assert {c for c, t in rel.RELATIETYPEN.items() if t["volgorde"]} == {"invoer", "operand"}
