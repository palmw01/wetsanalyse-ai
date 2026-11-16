"""De validator van methodesecties (ADR-014): één bron voor de generator en de werkplaats."""
import pytest
from bronmodel.methodesectie import SectieFout, lees_sectie

TEKST = "kop\n<!-- methode:duiding:begin -->\nOud.\n<!-- methode:duiding:end -->\nstaart\n"


def test_een_sectie_wordt_zonder_witruimte_gelezen():
    assert lees_sectie(TEKST, "duiding") == "Oud."


@pytest.mark.parametrize("tekst", [
    TEKST.replace("<!-- methode:duiding:end -->", ""),
    TEKST + "<!-- methode:duiding:begin -->",
    "<!-- methode:duiding:end -->\n<!-- methode:duiding:begin -->",
    TEKST.replace("Oud.", "   "),
])
def test_een_onduidelijke_sectie_wordt_geweigerd(tekst):
    with pytest.raises(SectieFout):
        lees_sectie(tekst, "duiding")


def test_een_ongeldig_sectie_id_wordt_geweigerd():
    with pytest.raises(SectieFout):
        lees_sectie(TEKST, "Duiding!")
