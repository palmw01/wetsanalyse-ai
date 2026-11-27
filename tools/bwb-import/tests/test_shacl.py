"""De vorm van een named graph: SHACL-shapes in `app/shapes/`, getoetst vóór de PUT (wetten en de kennisgroepenindex).

De shapes zijn afgeleid van wat de importer over veertien regelingen schrijft. Deze tests leggen vast dat elke
fixture eraan voldoet, dat ze echt bijten, en dat de importpoort een afwijkende graph nooit over een bestaande zet.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from bronmodel.bwb.parser import ToestandParser
from rdflib import RDF, Literal, URIRef

import app.kennisgroepen as kgi
import app.main as main_module
from app.dekking import Dekking, Stand, poortbesluit
from app.graphdb_writer import GraphDbWriter
from app.rdf_vocab import Vocab
from app.shacl import KENNISGROEPEN_SHAPES, Vormtoets, toets
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


# ---------------------------------------------------------------- de index van de kennisgroepstandpunten
#
# Dezelfde aanpak voor de named graph `urn:wa:graph:kennisgroepen` (`app/shapes/kennisgroepen.ttl`): de echte
# publicaties uit de fixtures zijn conform, de shapes bijten, en een afwijkende index vervangt nooit een bestaande.

KG_DATA = FIXTURES / "kennisgroepen"
KGO = kgi.KGO


def _kg(naam: str) -> dict:
    return json.loads((KG_DATA / f"{naam}.json").read_text(encoding="utf-8"))


def _kg_bron() -> tuple[list[dict], list[dict]]:
    return [_kg(n) for n in ("wp-22819", "wp-4785", "wp-586", "wp-8488")], [_kg("bericht-22821")]


def _index():
    g, _ = kgi.bouw_graph(*_kg_bron())
    return g


def test_de_index_uit_de_fixtures_is_conform() -> None:
    g = _index()
    # De fixtures raken alle vier de soorten nodes, anders toetst deze test minder dan hij belooft.
    for p in (KGO.rij, KGO.noemt, KGO.gebeurtenis):
        assert any(g.objects(None, p)), p
    uitslag = toets(g, KENNISGROEPEN_SHAPES)
    assert uitslag is not None and uitslag.conform, uitslag.regel() if uitslag else "geen pyshacl"


def test_de_kennisgroepen_shapes_bijten() -> None:
    g = _index()
    pub = next(iter(g.subjects(RDF.type, KGO.Standpunt)))
    g.remove((pub, KGO.kenmerk, None))
    g.set((pub, KGO.status, Literal("onbekend")))
    # De scheiding met de wet: geen bwb:-predicaat in deze graph (de shapes zijn gesloten).
    g.add((pub, URIRef("urn:bwb-ns:tekst"), Literal("x")))
    rij = next(iter(g.objects(pub, KGO.rij)))
    g.remove((rij, KGO.tekst, None))
    bepaling = next(n for n in g.objects(None, KGO.noemt) if str(g.value(n, KGO.doelsoort)) == "bepaling")
    g.remove((bepaling, KGO.artikel, None))
    uitslag = toets(g, KENNISGROEPEN_SHAPES)
    assert uitslag is not None and not uitslag.conform
    paden = {pad for pad, _c in uitslag.soorten}
    constraints = {c for _p, c in uitslag.soorten}
    assert {str(KGO.kenmerk), str(KGO.status), "urn:bwb-ns:tekst"} <= paden, uitslag.regel()
    assert {"ClosedConstraintComponent", "NodeConstraintComponent", "OrConstraintComponent"} <= constraints


def test_een_afwijkende_index_vervangt_nooit_een_bestaande() -> None:
    assert "blijft staan" in kgi.poortbesluit(1200, 1186, vormfouten="1 vormfout(en)")
    assert kgi.poortbesluit(1200, 0, vormfouten="1 vormfout(en)") == ""
    assert kgi.poortbesluit(1200, 1186) == ""


class _Bron:
    """Een nepbron die elke soort in één pagina geeft."""

    def __init__(self) -> None:
        publicaties, berichten = _kg_bron()
        self._soorten = {"wt_publication": publicaties, "posts": berichten}

    def get(self, url, headers=None, timeout=None):
        items = self._soorten[url.split("/wp/v2/", 1)[1].split("?", 1)[0]]
        return SimpleNamespace(headers={"X-WP-Total": str(len(items)), "X-WP-TotalPages": "1"},
                               raise_for_status=lambda: None, json=lambda: items)


class _Index:
    def __init__(self, aantal: int) -> None:
        self._aantal, self.geschreven = aantal, []

    def aantal(self) -> int:
        return self._aantal

    def vervang(self, graph) -> None:
        self.geschreven.append(len(graph))


def _afwijkend(monkeypatch) -> None:
    fout = Vormtoets(1, {(str(KGO.kenmerk), "MinCountConstraintComponent"): (1, "urn:wa:kennisgroepen:wp:1")})
    monkeypatch.setattr(kgi, "toets", lambda graph, pad: fout)


def test_verversen_toetst_de_vorm_voor_de_put() -> None:
    index = _Index(aantal=4)
    uit = kgi.ververs(index, _Bron(), slaap=lambda _: None)
    assert uit.geschreven and index.geschreven and uit.vorm == "conform" and uit.reden == ""


def test_verversen_laat_bij_vormfouten_de_oude_index_staan(monkeypatch) -> None:
    _afwijkend(monkeypatch)
    index = _Index(aantal=4)
    uit = kgi.ververs(index, _Bron(), slaap=lambda _: None)
    assert not uit.geschreven and not index.geschreven
    assert "vormfout" in uit.reden and "blijft staan" in uit.reden


def test_tegen_een_lege_index_wordt_hij_geschreven_met_een_signaal(monkeypatch) -> None:
    _afwijkend(monkeypatch)
    index = _Index(aantal=0)
    uit = kgi.ververs(index, _Bron(), slaap=lambda _: None)
    assert uit.geschreven and index.geschreven and "vormfout" in uit.reden


@pytest.mark.parametrize(("geschreven", "reden", "code"), [
    (True, "", 0),
    (True, "1 vormfout(en); geschreven, er stond geen index", 2),
    (False, "1 vormfout(en); de bestaande index (4 standpunten) blijft staan", 2),
])
def test_exitcode_van_de_index(monkeypatch, capsys, geschreven, reden, code) -> None:
    monkeypatch.setattr(kgi, "IndexSchrijver", lambda **_: None)
    monkeypatch.setattr(kgi, "ververs", lambda _s: kgi.Uitkomst(geschreven=geschreven, reden=reden, vorm="x"))
    settings = SimpleNamespace(graphdb_url="offline", graphdb_repository="offline", graphdb_user=None,
                               graphdb_password=None)
    assert main_module._kennisgroepen(settings, alleen_bij_verlies=False) == code
    if reden:
        assert reden in capsys.readouterr().out
