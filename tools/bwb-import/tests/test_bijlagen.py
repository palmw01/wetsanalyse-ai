"""Een bijlage komt helemaal in de graaf, op een eigen identiteit.

Bijlage 2 van de Awb (66.086 tekens, twaalf artikelen) ontbrak volledig: de parser keek alleen naar
directe `<artikel>`-kinderen, en de artikelen staan onder `<divisie>`-en. Geen fout, geen waarschuwing,
en de dekking stond op 104% omdat ze bijlagen niet telde.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from bronmodel.bwb.parser import ToestandParser
from bronmodel.bwb.references import jci_doel_ref_key, jci_node_ref_key
from rdflib import Literal, URIRef
from test_slottekst import _snapshot

from app.collect import collect
from app.dekking import Dekking, Stand, meet, poortbesluit
from app.graphdb_writer import GraphDbWriter
from app.rdf_vocab import Vocab

FIXTURE = Path(__file__).parent / "fixtures" / "sample_bijlage_divisies.xml"
V = Vocab()
AWB = "urn:bwb:BWBR0005537"


def _iri(pad: str) -> URIRef:
    return URIRef(f"{AWB}:id:BWBR0005537" + pad.replace("/", "%2F"))


def _graaf(wet=None):
    wet = wet or ToestandParser().parse(FIXTURE)
    return GraphDbWriter(url="o", repository="o", vocab=V).build_graph(wet)[0]


def _toestand(tmp_path: Path, inhoud: str) -> Path:
    pad = tmp_path / "toestand.xml"
    pad.write_text(
        f'<toestand bwb-id="BWBR0000001"><wetgeving soort="wet">{inhoud}</wetgeving></toestand>',
        encoding="utf-8",
    )
    return pad


def test_divisie_in_een_bijlage_wordt_een_hoofdstuk() -> None:
    bijlage = ToestandParser().parse(FIXTURE).bijlagen[0]
    assert [d.soort for d in bijlage.structuurdelen] == ["hoofdstuk"]
    assert bijlage.structuurdelen[0].artikelen[0].id == "BWBR0005537/Bijlage2/Divisie1/Artikel1"


def test_gelijke_artikelnummers_in_bijlagen_blijven_gescheiden() -> None:
    graaf = _graaf()
    assert (_iri("/Bijlage2/Divisie1/Artikel1"), V.ns.tekst, None) not in graaf  # tekst staat op het lid
    assert (_iri("/Bijlage3/Artikel1"), V.ns.tekst, None) in graaf
    assert (URIRef(f"{AWB}:artikel:1"), None, None) not in graaf


def test_hoofdstuk_van_de_bijlage_valt_niet_samen_met_dat_van_de_wet() -> None:
    graaf = _graaf()
    assert (URIRef(f"{AWB}:hoofdstuk:1"), V.ns.titel, Literal("Eerste hoofdstuk", lang="nl")) in graaf
    assert (_iri("/Bijlage2/Divisie1"), V.ns.heeftArtikel, _iri("/Bijlage2/Divisie1/Artikel1")) in graaf
    assert (URIRef(f"{AWB}:hoofdstuk:1"), V.ns.titel,
            Literal("Eerste hoofdstuk van de bijlage", lang="nl")) not in graaf


def test_lid_en_onderdeel_krijgen_ook_de_wetlokale_identiteit() -> None:
    graaf = _graaf()
    lid = _iri("/Bijlage2/Divisie1/Artikel1/Lid1")
    assert (lid, V.ns.vindplaats, Literal("Bijlage 2, artikel 1, lid 1")) in graaf
    onderdeel = _iri("/Bijlage2/Divisie1/Artikel1/Lid1/Opsomming_1/Onderdeela")
    assert (onderdeel, V.ns.vindplaats, Literal("Bijlage 2, artikel 1, lid 1, onderdeel a")) in graaf
    assert not [s for s in graaf.subjects() if str(s).startswith(f"{AWB}:artikel:1:")]


def test_de_echte_jci_blijft_en_er_wordt_er_geen_verzonnen() -> None:
    graaf = _graaf()
    artikel = _iri("/Bijlage3/Artikel1")
    assert "bijlage=3" in str(next(graaf.objects(artikel, V.ns.jci)))
    assert not list(graaf.objects(artikel, URIRef("http://www.w3.org/2002/07/owl#sameAs")))
    assert str(next(graaf.objects(artikel, V.ns.bronUrl))).endswith("#Bijlage3_Artikel1")


def test_tekstuele_verwijzing_in_een_bijlage_wijst_niet_naar_de_eigen_wet() -> None:
    """"Artikel 16" in Bijlage 2 is een artikel van een andere wet, niet artikel 16 van de Awb."""
    batch, _ = collect(ToestandParser().parse(FIXTURE))
    assert not [v for v in batch.verwijzingen if v["to"] == "BWBR0005537#artikel=16"]


@pytest.mark.parametrize("functie", [jci_doel_ref_key, jci_node_ref_key])
def test_een_jci_in_een_bijlage_landt_niet_op_de_wet(functie) -> None:
    assert functie("jci1.3:c:BWBR0005537&bijlage=2&hoofdstuk=1") == ("BWBR0005537", "wet")
    assert functie("jci1.3:c:BWBR0005537&bijlage=3&artikel=1") == ("BWBR0005537", "wet")


def test_alle_tekst_van_de_bijlage_haalt_de_graaf() -> None:
    dekking = meet(FIXTURE)
    assert dekking.ontbrekend == 0, dekking.regel()


def test_de_bronboom_leest_de_artikelen_onder_hun_bijlage() -> None:
    """Wat api en graph-qa zien. `bronmodel` weigert de hele regeling bij een dubbele node."""
    nodes = _snapshot("sample_bijlage_divisies", "BWBR0005537")["nodes"]
    artikel = next(n for n in nodes if n["bron_iri"] == str(_iri("/Bijlage2/Divisie1/Artikel1")))
    assert artikel["parent_iri"] == str(_iri("/Bijlage2/Divisie1"))
    hoofdstuk = next(n for n in nodes if n["bron_iri"] == artikel["parent_iri"])
    assert hoofdstuk["parent_iri"] == str(_iri("/Bijlage2"))


def test_twee_bepalingen_op_een_iri_stoppen_de_import() -> None:
    wet = ToestandParser().parse(FIXTURE)
    batch, summary = collect(wet)
    rij = next(r for r in batch.nodes["Artikel"] if r["id"].endswith("Bijlage3/Artikel1"))
    rij["ref_key"] = "BWBR0005537#artikel=1:1"
    schrijver = GraphDbWriter(url="o", repository="o", vocab=V)
    with pytest.raises(ValueError, match="dezelfde IRI"):
        schrijver.build_graph(wet, verzameld=(batch, summary))


@pytest.mark.parametrize(
    ("inhoud", "melding"),
    [
        ("<wet-besluit><wettekst><deel><al>x</al></deel></wettekst></wet-besluit>", "wettekst/deel"),
        (
            "<wet-besluit><wettekst><hoofdstuk><kop/><onbekend/></hoofdstuk></wettekst></wet-besluit>",
            "hoofdstuk/onbekend",
        ),
        (
            "<wet-besluit><wettekst/><bijlage><divisie><kop><label>Deel</label></kop></divisie></bijlage>"
            "</wet-besluit>",
            "bijlage/divisie",
        ),
        ("<circulaire><circulaire-tekst/><verzonnen/></circulaire>", None),
        ("<circulaire><circulaire-tekst><verzonnen/></circulaire-tekst></circulaire>", "circulaire-tekst/verzonnen"),
    ],
)
def test_onbekende_structuur_wordt_gemeld(tmp_path: Path, inhoud: str, melding: str | None) -> None:
    wet = ToestandParser().parse(_toestand(tmp_path, inhoud))
    if melding:
        assert melding in wet.overgeslagen
    else:
        assert wet.overgeslagen == []


def test_tekst_en_meta_in_een_bijlage_zijn_niet_onbekend(tmp_path: Path) -> None:
    wet = ToestandParser().parse(
        _toestand(
            tmp_path,
            "<wet-besluit><wettekst/><bijlage><kop/><al>tekst</al><lijst/><table/><plaatje/>"
            "<meta-data/></bijlage></wet-besluit>",
        )
    )
    assert wet.overgeslagen == []


def test_bijlage_bij_een_circulaire_wordt_gelezen(tmp_path: Path) -> None:
    wet = ToestandParser().parse(
        _toestand(
            tmp_path,
            '<circulaire><circulaire-tekst/><bijlage bwb-ng-variabel-deel="/B"><al>Tekst.</al></bijlage>'
            "</circulaire>",
        )
    )
    assert [b.tekst for b in wet.bijlagen] == ["Tekst."]


def test_onbekende_structuur_weegt_in_de_poort_als_een_dip() -> None:
    """Bij volle dekking: de speling van de drempel kan een heel artikel verbergen."""
    vol = Dekking("X", 1000, 1000)
    behouden = poortbesluit(vol, Stand(tekens=1100), drempel=0.995, overgeslagen=["wettekst/deel"])
    assert behouden.schrijven is False
    gevuld = poortbesluit(vol, Stand(), drempel=0.995, overgeslagen=["wettekst/deel"])
    assert gevuld.schrijven is True
    assert "wettekst/deel" in (gevuld.reden or "")
