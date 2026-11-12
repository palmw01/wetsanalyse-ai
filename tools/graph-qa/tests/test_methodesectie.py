"""De validator van methodesecties (ADR-014 C7): één bron voor de generator en voor een voorstel uit de werkplek."""
import pytest
from bronmodel.methodesectie import MAX_TEKENS, SectieFout, lees_sectie, vervang_sectie

TEKST = "kop\n<!-- methode:duiding:begin -->\nOud.\n<!-- methode:duiding:end -->\nstaart\n"


def test_vervangen_laat_de_rest_byte_gelijk():
    nieuw = vervang_sectie(TEKST, "duiding", "  Nieuw.  ")
    assert nieuw == TEKST.replace("Oud.", "Nieuw.")
    assert lees_sectie(nieuw, "duiding") == "Nieuw."


@pytest.mark.parametrize("tekst", [
    TEKST.replace("<!-- methode:duiding:end -->", ""),
    TEKST + "<!-- methode:duiding:begin -->",
    "<!-- methode:duiding:end -->\n<!-- methode:duiding:begin -->",
    TEKST.replace("Oud.", "   "),
])
def test_een_onduidelijke_sectie_wordt_geweigerd(tekst):
    with pytest.raises(SectieFout):
        lees_sectie(tekst, "duiding")


@pytest.mark.parametrize("nieuw", ["", "  ", "x" * (MAX_TEKENS + 1), "a <!-- methode:x:end --> b", "a --> b"])
def test_een_nieuwe_tekst_die_de_vorm_breekt_wordt_geweigerd(nieuw):
    with pytest.raises(SectieFout):
        vervang_sectie(TEKST, "duiding", nieuw)


def test_een_ongeldig_sectie_id_wordt_geweigerd():
    with pytest.raises(SectieFout):
        lees_sectie(TEKST, "Duiding!")
