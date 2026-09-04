"""De dekkingsmeting: komt alle brontekst ook echt in de graaf?

Deze test is er omdat "de graaf is volledig" tot nu toe een oordeel was en geen cijfer. Elf
artikelen van de Leidraad Invordering 2008 (10.052 tekens) vielen anderhalve maand lang stil weg
omdat `_parse_divisie` geen tak had voor `<artikel>`-kinderen — geen fout, geen lege node, geen
waarschuwing. Deze meting had dat op dag één aangewezen.

Hij draait offline: parser → `build_graph` → tel de `bwb:tekst`-literals, en leg dat naast de
`<al>`-tekens in de bron. Geen GraphDB nodig.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from app.dekking import STANDAARD_DREMPEL, _tekst_zonder, bron_tekens, meet

FIXTURES = Path(__file__).parent / "fixtures"

# Dezelfde drempel als de import-job hanteert; de motivering staat bij `STANDAARD_DREMPEL`. Hem hier
# opnieuw opschrijven zou betekenen dat de test en de productiecode uit elkaar kunnen lopen.
DREMPEL = STANDAARD_DREMPEL


@pytest.mark.parametrize(
    "fixture",
    ["sample_toestand.xml", "sample_regeling.xml", "sample_circulaire.xml"],
)
def test_alle_brontekst_haalt_de_graaf(fixture: str) -> None:
    dekking = meet(FIXTURES / fixture)
    assert dekking.verhouding >= DREMPEL, dekking.regel()


def test_circulaire_dekking_bevat_de_artikelen_in_een_divisie() -> None:
    """De regressietest op het gat: haal je de `<artikel>`-tak weg, dan zakt dit cijfer."""
    dekking = meet(FIXTURES / "sample_circulaire.xml")
    assert dekking.ontbrekend == 0, dekking.regel()


def test_bron_telt_een_lijst_binnen_een_alinea_niet_dubbel() -> None:
    """De valkuil die de eerste meting vervuilde.

    Een `<al>` kan een `<lijst>` bevatten, en die `<li>`-items worden in de graaf eigen
    `Onderdeel`-nodes. Telt de bronmeting ze zowel via de omhullende alinea als via de `<li>` zelf,
    dan is de bron kunstmatig groter dan de graaf ooit kan zijn — dat suggereerde ten onrechte een
    gat van 3–13% bij álle regelingen.
    """
    xml = (
        '<toestand bwb-id="BWBR0000001"><wetgeving soort="wet"><wet-besluit><wettekst>'
        "<artikel><kop><nr>1</nr></kop><tekst>"
        "<al>De aanhef<lijst><li><li.nr>a.</li.nr><al>het onderdeel</al></li></lijst></al>"
        "</tekst></artikel>"
        "</wettekst></wet-besluit></wetgeving></toestand>"
    )
    pad = FIXTURES / "_tijdelijk_lijst.xml"
    pad.write_text(xml, encoding="utf-8")
    try:
        # "De aanhef" (9) + "het onderdeel" (13) = 22; met dubbeltelling zou het 35 zijn.
        assert bron_tekens(pad) == 22
    finally:
        pad.unlink()


def test_tekst_zonder_slaat_redactionele_opmerkingen_over() -> None:
    alinea = etree.fromstring(
        "<al>De wettekst<opmerkingen-inhoud>redactionele noot</opmerkingen-inhoud></al>"
    )
    assert _tekst_zonder(alinea) == "De wettekst"
