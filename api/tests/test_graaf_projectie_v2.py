import pytest
from rdflib import Dataset, Literal, URIRef
from rdflib.plugins.sparql.parser import parseQuery

from app.graaf_projectie_v2 import JAS, OA, REGISTER, SCHEMA, bouw_graaf, graph_iri, laag_iri, zoek_query


def dataset():
    ds = Dataset()
    laag = {"id": "layer-1", "bron_iri": "urn:bwb:BWBR0004770:artikel:9", "revisie": 2, "status": "in_review"}
    element = {"id": "e1", "klasse": "Voorwaarde", "tekst": "betaling", "toelichting": "Termijn voor betaling",
               "lifecycle": "proposed", "ankers": [
                   {"bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:1", "start": 3, "eind": 11, "tekst": "betaling", "bron_hash": "a"},
                   {"bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:2", "start": 0, "eind": 8, "tekst": "betaling", "bron_hash": "b"}]}
    graph = ds.graph(graph_iri(laag["id"]))
    for triple in bouw_graaf(laag, [element]):
        graph.add(triple)
    register = ds.graph(REGISTER)
    register.add((SCHEMA, JAS.versie, Literal(2)))
    register.add((laag_iri(laag["id"]), JAS.inGraaf, graph.identifier))
    register.add((laag_iri(laag["id"]), JAS.revisie, Literal(2)))
    # An unrelated graph has the exact same vocabulary; it must never leak into search.
    for triple in bouw_graaf({**laag, "id": "unregistered"}, [{**element, "id": "not-visible"}]):
        ds.graph(URIRef("urn:unregistered")).add(triple)
    return ds


def test_query_really_filters_registered_graph_and_deduplicates_targets():
    ds = dataset()
    query = zoek_query({"tekst": "BETALING", "jas_klassen": ["Voorwaarde"],
                        "scoped_nodes": ["urn:bwb:BWBR0004770:artikel:9:lid:1"]})
    assert [str(row.id) for row in ds.query(query)] == ["e1"]
    assert not list(ds.query(zoek_query({"jas_klassen": ["Rechtsobject"]})))


def test_local_anchor_sources_have_their_own_offsets():
    ds = dataset()
    graph = ds.graph(graph_iri("layer-1"))
    assert len(list(graph.triples((None, OA.hasSource, None)))) == 2
    assert not any(str(s).startswith("urn:bwb:") for s, _, _ in graph)


def test_old_graph_revision_is_not_searchable():
    ds = dataset()
    ds.graph(REGISTER).set((laag_iri("layer-1"), JAS.revisie, Literal(3)))
    assert not list(ds.query(zoek_query({"tekst": "betaling"})))


@pytest.mark.parametrize("tekst", ['" } UNION { ?s ?p ?o } #', "\\n", "betaling", "'SERVICE'"])
def test_text_cannot_change_query_structure(tekst):
    parseQuery(zoek_query({"tekst": tekst}))


def test_source_iri_injection_rejected():
    with pytest.raises(ValueError):
        zoek_query({"bronnode_id": "urn:bwb:BWBR1> } SERVICE <https://example.org> {"})


def test_exact_match_case_sensitive():
    ds = dataset()
    assert list(ds.query(zoek_query({"tekst": "betaling", "tekstveld": "citaat", "match": "exact"})))
    assert not list(ds.query(zoek_query({"tekst": "BETALING", "tekstveld": "citaat", "match": "exact"})))
