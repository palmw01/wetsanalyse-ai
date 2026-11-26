"""De vorm van een named graph: SHACL-shapes in `app/shapes/bwb-graaf.ttl`, getoetst vóór de PUT.

De shapes zijn afgeleid van wat de importer over veertien regelingen schrijft. Deze tests leggen vast dat elke
fixture eraan voldoet, dat ze echt bijten, en dat de importpoort een afwijkende graph nooit over een bestaande zet.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bronmodel.bwb.parser import ToestandParser
from rdflib import Literal

from app.dekking import Dekking, Stand, poortbesluit
from app.graphdb_writer import GraphDbWriter
from app.rdf_vocab import Vocab
from app.shacl import toets
from app.wti_parser import WtiParser

pytest.importorskip("pyshacl")

FIXTURES = Path(__file__).parent / "fixtures"
V = Vocab()
FIXTURE_XML = sorted(p.name for p in FIXTURES.glob("*.xml") if p.name != "sample_wti.xml")


def _graph(bestand: str, *, wti: bool = False):
    wet = ToestandParser().parse(FIXTURES / bestand)
    writer = GraphDbWriter(url="offline", repository="offline", vocab=V)
    g, _ = writer.build_graph(
        wet, wti=WtiParser().parse(FIXTURES / "sample_wti.xml") if wti else None
    )
    return g


@pytest.mark.parametrize("bestand", FIXTURE_XML)
def test_elke_fixture_is_conform(bestand: str) -> None:
    uitslag = toets(_graph(bestand))
    assert uitslag is not None and uitslag.conform, uitslag.regel() if uitslag else "geen pyshacl"


def test_met_wti_is_de_regeling_conform() -> None:
    uitslag = toets(_graph("sample_toestand.xml", wti=True))
    assert uitslag is not None and uitslag.conform, uitslag.regel()


def test_de_shapes_bijten() -> None:
    g = _graph("sample_toestand.xml")
    lid = next(iter(g.subjects(predicate=None, object=V.klasse("Lid"))))
    g.remove((lid, V.ns.vindplaats, None))
    artikel = next(iter(g.subjects(predicate=None, object=V.klasse("Artikel"))))
    g.add((artikel, V.ns.jci, Literal("geen-jci")))
    uitslag = toets(g)
    assert uitslag is not None and not uitslag.conform
    paden = {pad for pad, _c in uitslag.soorten}
    assert str(V.ns.vindplaats) in paden and str(V.ns.jci) in paden


def test_een_afwijkende_graph_vervangt_nooit_een_bestaande() -> None:
    dekking = Dekking("BWBR0000001", bron_tekens=1000, graaf_tekens=2000)
    besluit = poortbesluit(dekking, Stand(tekens=1000), drempel=0.995, vormfouten="1 vormfout(en)")
    assert besluit.schrijven is False


def test_tegen_een_lege_graaf_wordt_hij_wel_geschreven_met_een_signaal() -> None:
    dekking = Dekking("BWBR0000001", bron_tekens=1000, graaf_tekens=1000)
    besluit = poortbesluit(dekking, Stand(), drempel=0.995, vormfouten="1 vormfout(en)")
    assert besluit.schrijven is True and "vormfout" in (besluit.reden or "")
