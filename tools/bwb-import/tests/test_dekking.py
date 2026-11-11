"""De dekkingsmeting: komt alle brontekst ook echt in de graaf?

Deze test maakt van "de graaf is volledig" een cijfer in plaats van een oordeel. Mist
`_parse_divisie` bijvoorbeeld een tak voor `<artikel>`-kinderen, dan vallen elf artikelen van de
Leidraad Invordering 2008 (10.052 tekens) stil weg — geen fout, geen lege node, geen waarschuwing.
Deze meting wijst dat direct aan.

Hij draait offline: parser → `build_graph` → tel de `bwb:tekst`-literals, en leg dat naast de
`<al>`-tekens in de bron. Geen GraphDB nodig.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from bronmodel.bwb.dekking import _tekst_zonder
from lxml import etree

from app.dekking import (
    STANDAARD_DREMPEL,
    Dekking,
    Stand,
    bron_tekens,
    meet,
    poortbesluit,
)

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


def test_bron_telt_bijlagen_mee_en_niets_dubbel(tmp_path: Path) -> None:
    """Bijlage 2 van de Awb ontbrak met een dekking van 104%, omdat de meting haar niet zag."""
    pad = tmp_path / "bijlage.xml"
    pad.write_text(
        '<toestand bwb-id="BWBR0000001"><wetgeving soort="wet"><wet-besluit>'
        "<wettekst><artikel><al>wettekst</al></artikel></wettekst>"
        '<bijlage><kop/><divisie><artikel><al>bijlagetekst</al></artikel></divisie></bijlage>'
        "</wet-besluit></wetgeving></toestand>",
        encoding="utf-8",
    )
    assert bron_tekens(pad) == len("wettekst") + len("bijlagetekst")


@pytest.mark.parametrize(
    ("bron", "graaf", "stand", "wti_mislukt", "schrijven", "reden"),
    [
        (1000, 1000, Stand(tekens=1000, wti=True), False, True, False),
        (1000, 800, Stand(tekens=1000), False, False, True),
        (1000, 800, Stand(), False, True, True),
        (1000, 800, Stand(tekens=800), False, True, True),
        (1000, 1000, Stand(tekens=1000, wti=True), True, False, True),
        (1000, 1000, Stand(tekens=1000), True, True, True),
        (0, 800, Stand(tekens=1000), False, False, True),
        (0, 1000, Stand(tekens=1000), False, True, False),
    ],
)
def test_poortbesluit(bron, graaf, stand, wti_mislukt, schrijven, reden) -> None:
    besluit = poortbesluit(
        Dekking("X", bron, graaf), stand, drempel=STANDAARD_DREMPEL, wti_mislukt=wti_mislukt
    )
    assert besluit.schrijven is schrijven
    assert bool(besluit.reden) is reden


def test_drempel_nul_zet_alleen_de_dipregel_uit() -> None:
    dip = poortbesluit(Dekking("X", 1000, 800), Stand(tekens=1000), drempel=0)
    assert dip.schrijven is True
    wti = poortbesluit(
        Dekking("X", 1000, 800), Stand(tekens=1000, wti=True), drempel=0, wti_mislukt=True
    )
    assert wti.schrijven is False
