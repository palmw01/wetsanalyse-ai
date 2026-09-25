"""Guard: de JAS-annotatielagen in de graaf veranderen niets aan wat Lex over de wet te zien krijgt.

Sinds 22 sep 2026 staan er naast de wetten ook annotatielagen in GraphDB (`urn:jas:graph:*`, door de
api geprojecteerd). De querybouwers bevragen de union van álle graven zonder `GRAPH`, en de
bronnencontrole telt elke BWB-verwijzing in een toolresultaat als vindplaats. Een annotatie is
afgeleide duiding: ze mag nooit als wettekst terugkomen, en ook niet als bron meetellen.

Deze test draait elke querybouwer op een klein stuk BWB-graaf, één keer kaal en één keer met een
annotatielaag plus de jas-ontologie erbij, en eist identieke resultaten. De laag is een afdruk van
de echte projectie (`api/app/graaf_projectie.py`); de api bewaakt dat die afdruk actueel blijft.

rdflib voert de queries uit, dus Lucene (`luc:`) levert hier niets op – met en zonder laag. Dat is
geen gat: de FTS-connector indexeert alleen de BWB-typen (`Regeling`…`Bijlage`), niet `oa:` of `jas:`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

rdflib = pytest.importorskip("rdflib", reason="rdflib is een dev-only afhankelijkheid")
from rdflib import Dataset, URIRef  # noqa: E402

from agent.graph import queries as q  # noqa: E402
from agent.provenance import citations_in, collect_sources  # noqa: E402

from test_sparql_syntax import GEVALLEN  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
ONTOLOGIE_TTL = Path(__file__).resolve().parents[3] / "docs" / "wetsanalyse-workbench" / "jas-ontologie.ttl"
# De JAS-vocabulaire (klassen, begrippen, regels, codes als skos:Concept) staat sinds plan-herkomst
# PR 3 ook in de graaf. Ze draagt de klassenamen als prefLabel – precies wat een zoektool van Lex
# niet als wettekst mag teruggeven.
VOCABULAIRE_TTL = Path(__file__).resolve().parents[3] / "api" / "app" / "vocabulaire" / "jas-vocabulaire.ttl"


def _dataset(met_laag: bool) -> Dataset:
    ds = Dataset(default_union=True)
    ds.graph(URIRef("urn:bwb:graph:BWBR0004770")).parse(FIXTURES / "bwb_voorbeeld.ttl", format="turtle")
    if met_laag:
        ds.graph(URIRef("urn:jas:graph:BWBR0004770:artikel:9")).parse(
            FIXTURES / "jas_laag_voorbeeld.ttl", format="turtle")
        ds.graph(URIRef("urn:jas:graph:ontologie")).parse(ONTOLOGIE_TTL, format="turtle")
        ds.graph(URIRef("urn:jas:graph:vocabulaire")).parse(VOCABULAIRE_TTL, format="turtle")
    return ds


@pytest.fixture(scope="module")
def kaal() -> Dataset:
    return _dataset(False)


@pytest.fixture(scope="module")
def met_laag() -> Dataset:
    return _dataset(True)


def _rijen(ds: Dataset, sparql: str) -> list[tuple] | None:
    """De rijen, of None als rdflib de query niet kan uitvoeren. Dat laatste is rdflib, niet de
    query: `get_regeling_info` doet `GROUP_CONCAT` over een ongebonden variabele, wat GraphDB
    netjes als lege string behandelt en rdflib laat struikelen."""
    try:
        return sorted(tuple(str(v) if v is not None else "" for v in rij) for rij in ds.query(sparql))
    except Exception:  # noqa: BLE001
        return None


# Extra gevallen die op de fixture echt iets vinden; de zoekterm "recht" raakt zowel een
# thesaurusterm (Belastingrecht) als de helft van de JAS-klassen (Rechtssubject, Rechtsobject, …).
EXTRA = [
    ("resolve_begrip+recht", q.resolve_begrip("recht")),
    ("resolve_begrip+voorgesteld",
     q.resolve_begrip("voorgesteld")),
    ("get_artikel+9", q.get_artikel("BWBR0004770", "9")),
    ("get_lid+9.1", q.get_lid("BWBR0004770", "9", "1")),
    ("context+9.1", q.context("BWBR0004770", "9", "1")),
    ("verwijst_naar_deze+10",
     q.verwijst_naar_deze("BWBR0004770", "10")),
    ("follow_verwijzingen+9",
     q.follow_verwijzingen("BWBR0004770", "9")),
]


@pytest.mark.parametrize(("naam", "sparql"), GEVALLEN + EXTRA, ids=[g[0] for g in GEVALLEN + EXTRA])
def test_query_ziet_de_annotatielaag_niet(naam: str, sparql: str, kaal: Dataset, met_laag: Dataset):
    zonder = _rijen(kaal, sparql)
    if zonder is None:
        pytest.skip("rdflib kan deze query niet uitvoeren (GraphDB wel) – niet te vergelijken")
    assert _rijen(met_laag, sparql) == zonder, (
        f"{naam}: de annotatielaag verandert het resultaat – een annotatie komt terug als wettekst")


def test_de_fixture_vindt_echt_iets(kaal: Dataset):
    """Zonder rijen zou 'identiek' niets bewijzen."""
    gevonden = {naam for naam, sparql in EXTRA + GEVALLEN if _rijen(kaal, sparql)}
    assert {"get_artikel+9", "get_lid+9.1", "context+9.1", "verwijst_naar_deze+10",
            "resolve_begrip+recht", "count_by_type", "list_regelingen"} <= gevonden


def test_de_laag_staat_er_echt_in(kaal: Dataset, met_laag: Dataset):
    """En zonder laag in de graaf zou 'identiek' evenmin iets bewijzen."""
    markering = ("ASK { ?a a <http://www.w3.org/ns/oa#Annotation> ; "
                 "<http://www.w3.org/ns/oa#hasTarget>/<http://www.w3.org/ns/oa#hasSource> "
                 "<urn:bwb:BWBR0004770:artikel:9:lid:1> }")
    klasse = ("ASK { ?c a <http://www.w3.org/2004/02/skos/core#Concept> ; "
              "<http://www.w3.org/2004/02/skos/core#prefLabel> ?l FILTER(STR(?l) = 'Rechtssubject') }")
    for ask in (markering, klasse):
        assert met_laag.query(ask).askAnswer is True
        assert kaal.query(ask).askAnswer is False


def test_annotatie_iri_is_geen_bron():
    """`urn:jas:annotatie:BWBR0004770:…` bevat een BWB-id. Telde dat als losse bron, dan leek een
    annotatie de wettekst te onderbouwen terwijl er geen wettekst was opgehaald."""
    tekst = ("markering <urn:jas:annotatie:BWBR0004770:artikel:9:e1> in laag "
             "<urn:jas:laag:BWBR0004770:artikel:9> – graaf urn:jas:graph:BWBR0004770:artikel:9")
    assert citations_in(tekst) == []
    assert collect_sources([("raw_sparql", tekst)]) == []


def test_bwb_verwijzing_naast_annotatie_telt_nog_wel():
    tekst = "urn:jas:annotatie:BWBR0004770:artikel:9:e1 over urn:bwb:BWBR0004770:artikel:9:lid:1 (BWBR0002320)"
    assert citations_in(tekst) == ["urn:bwb:BWBR0004770:artikel:9:lid:1", "BWBR0002320"]
