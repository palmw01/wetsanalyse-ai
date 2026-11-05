"""`agent/plekken.py`: vindplaats, titel en bepaling uit de graaf, met de query echt uitgevoerd."""
from __future__ import annotations

from rdflib import Dataset, Literal, Namespace, URIRef
from rdflib.namespace import RDF

from agent import plekken
from agent.graph.results import parse_select

BWB = Namespace("urn:bwb-ns:")
D92 = URIRef("urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.2")
O_D = URIRef("urn:bwb:BWBR0024096:artikel:9:o:d")
L1 = URIRef("urn:bwb:BWBR0004770:artikel:9:lid:1")


class RdflibGraaf:
    """Voert de query uit op een rdflib-dataset en geeft hem terug zoals de MCP: SPARQL-TSV."""

    def __init__(self, ds: Dataset) -> None:
        self.ds = ds

    def sparql(self, query: str) -> str:
        res = self.ds.query(query)
        kop = [str(v) for v in res.vars]
        regels = ["\t".join("?" + k for k in kop)]
        for rij in res:
            regels.append("\t".join("" if w is None else (f"<{w}>" if isinstance(w, URIRef) else f'"{w}"')
                                    for w in rij))
        return "\n".join(regels)


def _graaf(met_jas_laag: bool = False) -> RdflibGraaf:
    ds = Dataset(default_union=True)
    g = ds.graph(URIRef("urn:bwb:graph:BWBR0024096"))
    g.add((D92, RDF.type, BWB.Divisie))
    g.add((D92, BWB.vindplaats, Literal("Artikel 9.2")))
    g.add((D92, BWB.titel, Literal("Afwijking van de betalingstermijnen", lang="nl")))
    g.add((O_D, RDF.type, BWB.Onderdeel))
    g.add((O_D, BWB.vindplaats, Literal("Artikel 9.2, onderdeel d")))
    g.add((O_D, BWB.inBepaling, D92))
    if met_jas_laag:  # een annotatielaag zegt iets óver de bronnode, maar geeft haar geen plek
        jas = ds.graph(URIRef("urn:jas:graph:v2:x"))
        jas.add((URIRef("urn:jas:element:1"), URIRef("urn:jas-ns:bron"), O_D))
    return RdflibGraaf(ds)


def test_plekken_uit_de_graaf():
    uit = plekken.plekken(_graaf(), [str(O_D), str(D92), str(L1), "geen-iri"])
    assert uit[str(O_D)] == {"vindplaats": "Artikel 9.2, onderdeel d", "titel": "", "bepaling": str(D92)}
    assert uit[str(D92)] == {"vindplaats": "Artikel 9.2", "titel": "Afwijking van de betalingstermijnen",
                             "bepaling": ""}
    assert str(L1) not in uit                       # de graaf weet er niets van: de aanroeper valt terug
    assert plekken.plekken(_graaf(met_jas_laag=True), [str(O_D)]) == {str(O_D): uit[str(O_D)]}


def test_plekken_in_porties_en_een_storing_kost_alleen_de_naam(monkeypatch):
    monkeypatch.setattr(plekken, "PER_QUERY", 1)
    graaf = _graaf()
    gevraagd = []
    echt = graaf.sparql
    graaf.sparql = lambda q: gevraagd.append(q) or echt(q)
    assert len(plekken.plekken(graaf, [str(O_D), str(D92)])) == 2 and len(gevraagd) == 2

    class Kapot:
        def sparql(self, q):
            raise RuntimeError("graaf hapert")
    assert plekken.plekken(Kapot(), [str(O_D)]) == {}
    assert parse_select(_graaf().sparql(plekken.q_plekken([str(O_D)])))
