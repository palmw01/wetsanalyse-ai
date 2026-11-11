"""Tests voor verwijzingsherkenning (gestructureerd + tekst-fallback)."""

from __future__ import annotations

from bronmodel.bwb.models import VerwijzingSoort
from bronmodel.bwb.references import (
    detect_textual_references,
    extract_references,
    jci_doel,
    jci_doel_ref_key,
    jci_node_ref_key,
    jci_to_ref_key,
)
from lxml import etree


def _ankers(tekst: str, *, eigen_bwb_id: str = "BWBR0004770") -> list[str]:
    return [v.tekst for v in detect_textual_references(tekst, eigen_bwb_id=eigen_bwb_id)]


def test_jci_doel_ontleedt_bwb_artikel_lid() -> None:
    assert jci_doel("jci1.3:c:BWBR0005537&artikel=3:40") == ("BWBR0005537", "3:40", None)
    assert jci_doel("jci1.3:c:BWBR0004770&artikel=1&lid=2&z=2026-01-01") == (
        "BWBR0004770",
        "1",
        "2",
    )
    # Verwijzing naar een heel hoofdstuk: geen concreet artikel.
    assert jci_doel("jci1.3:c:BWBR0004770&hoofdstuk=I") == ("BWBR0004770", None, None)
    assert jci_doel(None) == (None, None, None)


def test_jci_to_ref_key_blijft_artikelniveau() -> None:
    # ref_key negeert het lid (lid-precisie zit op de relatie, niet de sleutel).
    assert jci_to_ref_key("jci1.3:c:BWBR0004770&artikel=1&lid=2") == "BWBR0004770#artikel=1"
    assert jci_to_ref_key("jci1.3:c:BWBR0004770&hoofdstuk=I") is None


def test_jci_geneste_divisie_neemt_laatste_artikel() -> None:
    # Geneste circulaire-divisies dragen het pad als herhaalde &artikel=-segmenten;
    # het laatste (meest specifieke) bepaalt het doel, zodat sub- en ouder-divisie
    # niet op dezelfde ref_key samenvallen.
    doc = "jci1.3:c:BWBR0024096&artikel=79&artikel=79.5a&z=2026-01-01&g=2026-01-01"
    assert jci_doel(doc) == ("BWBR0024096", "79.5a", None)
    assert jci_to_ref_key(doc) == "BWBR0024096#artikel=79.5a"


def test_detect_textual_references_spec_voorbeelden() -> None:
    assert _ankers("zie artikel 4 hierboven") == ["artikel 4"]
    assert _ankers("artikel 12a is van toepassing") == ["artikel 12a"]
    assert _ankers("op grond van artikel 10.1") == ["artikel 10.1"]
    assert _ankers("volgens artikel 3:2 Awb") == ["artikel 3:2 Awb"]
    assert _ankers("onrechtmatige daad (artikel 6:162 BW)") == ["artikel 6:162 BW"]


def test_detect_textual_references_resolutie() -> None:
    # Zonder afkorting: intern (eigen wet); met afkorting: via de map; BW per boek.
    (intern,) = detect_textual_references("zie artikel 4", eigen_bwb_id="BWBR0004770")
    assert intern.soort == VerwijzingSoort.TEKSTUEEL
    assert (intern.doel_bwb_id, intern.doel_artikel) == ("BWBR0004770", "4")
    (awb,) = detect_textual_references("volgens artikel 3:2 Awb", eigen_bwb_id="BWBR0004770")
    assert awb.doel_bwb_id == "BWBR0005537"
    (bw6,) = detect_textual_references("artikel 6:162 BW", eigen_bwb_id="BWBR0004770")
    assert bw6.doel_bwb_id == "BWBR0005289"
    # Onbekende afkorting: overslaan (te onzeker).
    assert detect_textual_references("artikel 3 Xyz", eigen_bwb_id="BWBR0004770") == []


def test_losse_woorden_niet_als_wet() -> None:
    # "en" mag niet als wetafkorting worden gezien.
    assert _ankers("artikel 4 en artikel 5") == ["artikel 4", "artikel 5"]


def test_naam_na_het_artikel_is_geen_eigen_wet() -> None:
    """Art. 9 lid 9 Invorderingswet: artikel 167 staat in het Douanewetboek, niet in die wet."""
    zin = (
        "In afwijking van het vierde lid is een uitnodiging tot betaling die is vastgesteld "
        "overeenkomstig een op een kalendermaand betrekking hebbende, aanvullende aangifte als "
        "bedoeld in artikel 167, eerste lid, van het Douanewetboek van de Unie invorderbaar "
        "vijftien dagen na de maand waarover de aangifte is gedaan."
    )
    assert _ankers(zin) == []


def test_naam_na_opsomming_leden_en_volzinnen() -> None:
    """Tussen het nummer en de naam kan van alles staan dat nog bij de aanwijzing hoort."""
    assert _ankers("de artikelen 107 en 108 van het Verdrag betreffende de werking") == []
    assert _ankers("artikel 116, zesde lid, tweede en derde volzin, van het Douanewetboek") == []
    # Artikel 15 staat in de verordening; artikel 8:45 is wel van de eigen wet.
    assert _ankers("artikel 15, derde lid, eerste alinea, van de in artikel 8:45 genoemde") == [
        "artikel 8:45"
    ]
    assert _ankers("artikelen 4.3 tot en met 4.5b van de Wet inkomstenbelasting 2001") == []
    assert _ankers("artikel 3 van Verordening (EU) nr. 1407/2013 van de Commissie") == []
    assert _ankers("artikel 5, eerste lid, onderdeel e, onder 1°, van de Wet") == []
    # "De wet" in een lagere regeling is de hogere wet, niet de regeling zelf.
    assert _ankers("artikel 22bis, tweede of derde lid, van de wet") == []
    assert _ankers("artikel 10bis.4, vierde lid, of artikel 10bis.5, vijfde lid, van de Wet") == []


def test_herkende_naam_achter_van_wijst_naar_die_regeling() -> None:
    (awb,) = detect_textual_references(
        "artikel 3:2, eerste lid, van de Awb", eigen_bwb_id="BWBR0004770"
    )
    assert (awb.doel_bwb_id, awb.doel_artikel) == ("BWBR0005537", "3:2")
    assert awb.tekst == "artikel 3:2 Awb"
    (bw,) = detect_textual_references(
        "de artikelen 1:10 en volgende van het BW", eigen_bwb_id="BWBR0024096"
    )
    assert (bw.doel_bwb_id, bw.doel_artikel) == ("BWBR0002656", "1:10")


def test_verwijzing_naar_de_eigen_regeling_blijft_intern() -> None:
    assert _ankers("artikel 25.5.1 van deze leidraad") == ["artikel 25.5.1"]
    assert _ankers("artikel 14.1.4, laatste volzin, van de leidraad") == ["artikel 14.1.4"]
    assert _ankers("artikel 35.12.2 van de Leidraad") == ["artikel 35.12.2"]
    assert _ankers("artikel 9, tweede lid, is van overeenkomstige toepassing") == ["artikel 9"]
    # Een zin die na het nummer stopt zegt niets over de volgende zin.
    assert _ankers("zie artikel 9. Van de Wet is geen sprake") == ["artikel 9"]


def test_artikelnummer_wordt_niet_afgekapt() -> None:
    """Met één letter werd "artikel 30fa" artikel 30f en "artikel 53ter" artikel 53t."""
    assert _ankers("artikel 30fa, eerste lid") == ["artikel 30fa"]
    assert _ankers("artikel 53ter, is te wijten") == ["artikel 53ter"]
    assert _ankers("artikel 1cbis.2 is van toepassing") == ["artikel 1cbis.2"]


def test_jci_doel_ref_key_alle_niveaus() -> None:
    assert jci_doel_ref_key("jci1.3:c:BWBR0005537&artikel=3:40") == (
        "BWBR0005537#artikel=3:40",
        "artikel",
    )
    assert jci_doel_ref_key("jci1.3:c:BWBR0004770&hoofdstuk=I&artikel=1&lid=2&z=2026-01-01") == (
        "BWBR0004770#artikel=1#lid=2",
        "lid",
    )
    assert jci_doel_ref_key("jci1.3:c:BWBR0004770&hoofdstuk=I&artikel=2&lid=1&o=aa&o=1") == (
        "BWBR0004770#artikel=2#lid=1#o=aa#o=1",
        "onderdeel",
    )
    # Hele-structuur-doelen worden niet gedropt.
    assert jci_doel_ref_key("jci1.3:c:BWBR0005537&titeldeel=4.1") == (
        "BWBR0005537#titeldeel=4.1",
        "titeldeel",
    )
    assert jci_doel_ref_key("jci1.3:c:BWBR0005537&hoofdstuk=6") == (
        "BWBR0005537#hoofdstuk=6",
        "hoofdstuk",
    )
    assert jci_doel_ref_key("jci1.3:c:BWBR0005537&afdeling=10.2.1") == (
        "BWBR0005537#afdeling=10.2.1",
        "afdeling",
    )
    # Hele wet.
    assert jci_doel_ref_key("jci1.3:c:BWBR0028093") == ("BWBR0028093", "wet")
    assert jci_doel_ref_key(None) == (None, None)
    assert jci_doel_ref_key("geen-jci") == (None, None)


def test_extract_references_intern_vs_extern() -> None:
    xml = """
    <lid>
      <al>Zie
        <intref bwb-id="BWBR0004770" doc="jci1.3:c:BWBR0004770&amp;artikel=4"
                bwb-ng-variabel-deel="/HoofdstukI/Artikel4">artikel 4</intref> en
        <extref bwb-id="BWBR0005537"
                doc="jci1.3:c:BWBR0005537&amp;artikel=3:40">artikel 3:40</extref>.
      </al>
    </lid>
    """
    element = etree.fromstring(xml)
    verwijzingen = extract_references(element, eigen_bwb_id="BWBR0004770")
    assert len(verwijzingen) == 2
    intern = next(v for v in verwijzingen if v.doel_bwb_id == "BWBR0004770")
    extern = next(v for v in verwijzingen if v.doel_bwb_id == "BWBR0005537")
    assert intern.soort == VerwijzingSoort.INTERN
    assert intern.doel_pad == "/HoofdstukI/Artikel4"
    assert extern.soort == VerwijzingSoort.EXTERN


def test_extref_naar_eigen_wet_is_intern() -> None:
    # Een extref naar de eigen wet wordt als intern beschouwd.
    xml = (
        '<lid><al><extref bwb-id="BWBR0004770" doc="jci1.3:c:BWBR0004770&amp;artikel=2">'
        "artikel 2</extref></al></lid>"
    )
    element = etree.fromstring(xml)
    (verwijzing,) = extract_references(element, eigen_bwb_id="BWBR0004770")
    assert verwijzing.soort == VerwijzingSoort.INTERN


def test_meta_data_verwijzingen_genegeerd() -> None:
    xml = """
    <lid>
      <al>Tekst zonder ref.</al>
      <meta-data><jcis>
        <extref bwb-id="BWBR9999999" doc="x">verborgen</extref>
      </jcis></meta-data>
    </lid>
    """
    element = etree.fromstring(xml)
    assert extract_references(element, eigen_bwb_id="BWBR0004770") == []


def test_node_ref_key_draagt_het_volledige_structuurpad() -> None:
    """De identiteit van een structuurdeel is het PAD, niet het laatste segment.

    `jci_doel_ref_key` houdt alleen het laatste segment aan, en dat is voor een verwijzing prima
    ("ik verwijs naar afdeling 1") maar fataal als identiteit: dan is elke "Afdeling 1" van een
    regeling dezelfde node. In de graaf krijgen dan 16 van de 93 afdelingen en 5 van de 27
    paragrafen meer dan één ouder, met hun titels en artikelen op één hoop.
    """
    assert jci_node_ref_key("jci1.3:c:BWBR0002320&hoofdstuk=VIII&afdeling=1&z=2026-04-11") == (
        "BWBR0002320#hoofdstuk=VIII#afdeling=1",
        "afdeling",
    )
    # Twee afdelingen "1" in verschillende hoofdstukken zijn nu verschillende nodes.
    assert jci_node_ref_key("jci1.3:c:BWBR0004770&hoofdstuk=IV&afdeling=1")[0] != jci_node_ref_key(
        "jci1.3:c:BWBR0004770&hoofdstuk=VI&afdeling=1"
    )[0]


def test_node_ref_key_laat_hierarchische_nummering_ongemoeid() -> None:
    """De Awb nummert haar afdelingen al hiërarchisch (10.2.1) en heeft geen hoofdstuk-segment.

    Daar was ook geen collisie, en de sleutel moet dus exact gelijk blijven — anders verandert de
    IRI van 69 afdelingen zonder dat er iets mee mis was.
    """
    assert jci_node_ref_key("jci1.3:c:BWBR0005537&afdeling=10.2.1") == (
        "BWBR0005537#afdeling=10.2.1",
        "afdeling",
    )
    assert jci_node_ref_key("jci1.3:c:BWBR0005537&afdeling=10.2.1") == jci_doel_ref_key(
        "jci1.3:c:BWBR0005537&afdeling=10.2.1"
    )


def test_node_ref_key_raakt_artikelen_niet() -> None:
    """Artikel-, lid- en onderdeelsleutels zijn binnen een regeling al uniek.

    Zou het pad daar ook in komen, dan verandert élke artikel-IRI in de graaf — inclusief die
    waaraan de annotaties van juristen hangen.
    """
    for doc in (
        "jci1.3:c:BWBR0004770&hoofdstuk=VI&afdeling=1&artikel=36",
        "jci1.3:c:BWBR0004770&hoofdstuk=VI&afdeling=1&artikel=36&lid=2",
        "jci1.3:c:BWBR0004770&hoofdstuk=I&artikel=2&lid=1&o=aa&o=1",
    ):
        assert jci_node_ref_key(doc) == jci_doel_ref_key(doc)


def test_node_ref_key_zonder_structuur_is_de_wet() -> None:
    assert jci_node_ref_key("jci1.3:c:BWBR0028093") == ("BWBR0028093", "wet")
    assert jci_node_ref_key(None) == (None, None)
    assert jci_node_ref_key("geen-jci") == (None, None)


def test_jci_naar_bronnode_iri_volgt_de_gedeelde_vectoren() -> None:
    """Dezelfde vectoren als `bronDoel` in de werkplek (frontend/lib/jci-vectoren.json): de jci van
    een vindplaats moet in de werkplek op precies de IRI uitkomen die de importer schrijft."""
    import json
    from pathlib import Path

    import pytest

    from app.rdf_vocab import Vocab

    pad = Path(__file__).resolve().parents[3] / "frontend" / "lib" / "jci-vectoren.json"
    if not pad.exists():
        pytest.skip("frontend niet aanwezig")
    vocab = Vocab()
    for v in json.loads(pad.read_text(encoding="utf-8"))["vectoren"]:
        if not v["ref"].startswith("jci"):
            continue
        ref_key, soort = jci_node_ref_key(v["ref"])
        iri = None if soort == "wet" else str(vocab.by_ref_key(ref_key))
        assert iri == (v["iri"] if v["soort"] not in (None, "regeling") else None), v["ref"]
