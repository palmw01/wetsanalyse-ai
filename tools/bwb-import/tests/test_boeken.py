"""Boeken: in een regeling met meer boeken draagt elke sleutel het boek; bij één boek is het boek de regeling zelf.

Rv (BWBR0001827) heeft vier boeken, en elk boek een "Titeldeel Eerste" waarvan de jci het boek niet noemt
(`&titeldeel=Eerste`). Zonder het boek in de sleutel landen die titeldelen op één IRI en weigert de importpoort de
regeling. Er komt bewust geen boeknode: die zou de padqueries en het toolschema van Lex veranderen. Een BW-boek (Boek 7 is
BWBR0005290) heeft precies één `<boek>`: dat blijft de regeling zelf, zodat geen bestaande IRI verschuift.
"""
from __future__ import annotations

from pathlib import Path

from bronmodel.bwb.parser import ToestandParser
from rdflib import RDF

from app.collect import collect
from app.graphdb_writer import GraphDbWriter
from app.rdf_vocab import Vocab

V = Vocab()


def _boek(nr: str, artikel: str) -> str:
    return (
        f'<boek bwb-ng-variabel-deel="/Boek{nr}"><kop><nr>{nr}</nr><label>Boek</label><titel>Boek {nr}</titel></kop>'
        f'<titeldeel bwb-ng-variabel-deel="/Boek{nr}/TiteldeelEerste"><kop><nr>Eerste</nr><label>Titel</label>'
        f"<titel>Titel van boek {nr}</titel></kop>"
        f'<meta-data><jcis><jci verwijzing="jci1.0:c:BWBR0000001&amp;titeldeel=Eerste"/></jcis></meta-data>'
        f'<artikel bwb-ng-variabel-deel="/Boek{nr}/TiteldeelEerste/Artikel{artikel}"><kop><nr>{artikel}</nr></kop>'
        f'<al>Tekst van artikel {artikel}.</al>'
        f'<meta-data><jcis><jci verwijzing="jci1.3:c:BWBR0000001&amp;artikel={artikel}"/></jcis></meta-data>'
        f"</artikel></titeldeel></boek>"
    )


def _toestand(tmp_path: Path, boeken: str) -> Path:
    pad = tmp_path / "toestand.xml"
    pad.write_text(
        '<toestand bwb-id="BWBR0000001"><wetgeving soort="wet"><wet-besluit><wettekst>'
        f"{boeken}</wettekst></wet-besluit></wetgeving></toestand>",
        encoding="utf-8",
    )
    return pad


def test_meer_boeken_geven_elk_deel_een_sleutel_met_het_boek(tmp_path: Path) -> None:
    wet = ToestandParser().parse(_toestand(tmp_path, _boek("Eerste", "1") + _boek("Tweede", "2")))
    assert [(d.soort, d.boek) for d in wet.structuurdelen] == [("titeldeel", "Eerste"), ("titeldeel", "Tweede")]
    assert wet.overgeslagen == []

    batch, summary = collect(wet)
    titeldelen = sorted(r["ref_key"] for r in batch.nodes["Titeldeel"])
    assert titeldelen == [
        "BWBR0000001#boek=Eerste#titeldeel=Eerste",
        "BWBR0000001#boek=Tweede#titeldeel=Eerste",
    ]
    # Artikelen houden hun sleutel: die is binnen de regeling al uniek.
    assert sorted(r["ref_key"] for r in batch.nodes["Artikel"]) == ["BWBR0000001#artikel=1", "BWBR0000001#artikel=2"]

    g, _ = GraphDbWriter(url="offline", repository="offline", vocab=V).build_graph(wet, verzameld=(batch, summary))
    assert len(set(g.subjects(RDF.type, V.klasse("Titeldeel")))) == 2
    assert len(set(g.objects(V.wet("BWBR0000001"), V.ns.heeftTiteldeel))) == 2


def test_een_enkel_boek_is_de_regeling_zelf(tmp_path: Path) -> None:
    wet = ToestandParser().parse(_toestand(tmp_path, _boek("7", "1")))
    assert [(d.soort, d.boek) for d in wet.structuurdelen] == [("titeldeel", None)]
    batch, summary = collect(wet)
    assert [r["ref_key"] for r in batch.nodes["Titeldeel"]] == ["BWBR0000001#titeldeel=Eerste"]


def test_een_vervallen_artikel_zonder_nr_krijgt_het_nummer_uit_zijn_label(tmp_path: Path) -> None:
    """Rv, art. 320b: de kop heeft alleen `<label>Artikel 320b</label>`."""
    pad = tmp_path / "toestand.xml"
    pad.write_text(
        '<toestand bwb-id="BWBR0000001"><wetgeving soort="wet"><wet-besluit><wettekst>'
        '<artikel bwb-ng-variabel-deel="/Artikel320b" label="Artikel 320b" status="vervallen">'
        "<kop><label>Artikel 320b</label></kop><al>Vervallen</al></artikel>"
        "</wettekst></wet-besluit></wetgeving></toestand>",
        encoding="utf-8",
    )
    assert ToestandParser().parse(pad).losse_artikelen[0].nummer == "320b"
