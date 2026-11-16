import pytest
from rdflib import Dataset, Literal, URIRef
from rdflib.plugins.sparql.parser import parseQuery

from app.graaf_projectie_v2 import JAS, OA, REGISTER, SCHEMA, SCHEMA_VERSIE, bouw_graaf, graph_iri, laag_iri, zoek_query


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
    register.add((SCHEMA, JAS.versie, Literal(SCHEMA_VERSIE)))
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


KWAAD = ['" } UNION { ?s ?p ?o } #', '") } UNION { ?s ?p ?o } #', "> } SERVICE <https://example.org> { ?s ?p ?o } #",
         "\\n", "\n} ; DELETE WHERE { ?s ?p ?o } #", "'SERVICE'", '\\" ) } #']


def _vorm(query: str):
    """De structuur van een query: de geparste algebra met elke literal en elke code-IRI vervangen door een plaatshouder.
    Een injectie die slaagt, verandert die structuur (een UNION, een SERVICE, een extra patroon); een waarde die als
    gegeven binnenkomt, verandert alleen een literal. Alleen parsen (zoals deze tests eerst deden) ziet dat niet: een
    geslaagde injectie parseert ook (testplan api V5)."""
    from rdflib.plugins.sparql import prepareQuery
    from rdflib.plugins.sparql.parserutils import CompValue

    def plat(x):
        if isinstance(x, Literal):
            return "LITERAL"
        if isinstance(x, URIRef) and str(x).startswith("urn:jas-ns:besluit:"):
            return "CODE"
        if isinstance(x, CompValue):
            return (x.name, tuple((k, plat(v)) for k, v in x.items() if not k.startswith("_")))
        if isinstance(x, dict):
            return tuple((k, plat(v)) for k, v in x.items() if not str(k).startswith("_"))
        if isinstance(x, (list, tuple)):
            return tuple(plat(v) for v in x)
        if isinstance(x, (set, frozenset)):
            return tuple(sorted(repr(plat(v)) for v in x))
        return repr(x)
    return plat(prepareQuery(query).algebra)


#: Elk filter van `zoek_query` dat tekst van buiten aanneemt, met een onschuldige waarde in de vorm die het verwacht.
VRIJE_VELDEN = {"tekst": "betaling", "query": "betaling", "jas_klassen": ["Voorwaarde"], "lifecycle": ["voorgesteld"],
                "laagstatus": ["in_review"], "herkomst": ["agent"], "aandacht": ["geel"], "subtype": ["parameter"],
                "beslist_door": ["model"]}


def test_elk_filter_van_zoek_query_is_ingedeeld():
    """Een nieuw filter in `zoek_query` moet hier een plek krijgen: als vrij veld (dan toetst de test hieronder het), of als
    veld dat de code zelf valideert of alleen een vaste keuze is."""
    import inspect
    import re

    from app import graaf_projectie_v2
    bron = inspect.getsource(graaf_projectie_v2.zoek_query)
    sleutels = set(re.findall(r'filters\.get\("(\w+)"', bron)) | set(re.findall(r'filters\["(\w+)"\]', bron))
    sleutels |= {k for k in re.findall(r'\(\("(\w+)", "\w+"\)', bron)} | set(re.findall(r'\("(\w+)", "\w+"\)', bron))
    gevalideerd_of_vast = {"scoped_nodes", "bron_iri", "scope", "bwb_id", "met_twijfel", "inclusief_verouderd",
                           "tekstveld", "match"}
    assert sleutels, "de zoektocht vindt niets: dan toetst deze test niets"
    assert sleutels - gevalideerd_of_vast - set(VRIJE_VELDEN) == set(), "een filter zonder injectietoets"


@pytest.mark.parametrize("veld", sorted(VRIJE_VELDEN))
@pytest.mark.parametrize("kwaad", KWAAD)
def test_tekst_van_buiten_verandert_de_query_niet(veld, kwaad):
    onschuldig = VRIJE_VELDEN[veld]
    kwaadaardig = [kwaad] if isinstance(onschuldig, list) else kwaad
    assert _vorm(zoek_query({veld: kwaadaardig})) == _vorm(zoek_query({veld: onschuldig}))


def test_de_vormtoets_ziet_een_geslaagde_injectie():
    """De positieve controle: een query met een extra UNION heeft een andere vorm, ook als hij geldig parseert."""
    gewoon = zoek_query({"tekst": "betaling"})
    geinjecteerd = gewoon.replace("OPTIONAL { ?e jas:klasseNaam ?klasse }",
                                  "OPTIONAL { ?e jas:klasseNaam ?klasse } { ?s ?p ?o } UNION { ?s ?p ?o }", 1)
    assert geinjecteerd != gewoon
    parseQuery(geinjecteerd)
    assert _vorm(geinjecteerd) != _vorm(gewoon)


def test_source_iri_injection_rejected():
    with pytest.raises(ValueError):
        zoek_query({"bron_iri": "urn:bwb:BWBR1> } SERVICE <https://example.org> {"})


def test_exact_match_case_sensitive():
    ds = dataset()
    assert list(ds.query(zoek_query({"tekst": "betaling", "tekstveld": "citaat", "match": "exact"})))
    assert not list(ds.query(zoek_query({"tekst": "BETALING", "tekstveld": "citaat", "match": "exact"})))


def _rijke_dataset():
    """Twee markeringen met verschillende herkomst, aandacht, subtype en spoor."""
    ds = Dataset()
    laag = {"id": "layer-r", "bron_iri": "urn:bwb:BWBR0004770:artikel:9", "revisie": 1, "status": "in_review"}
    anker = {"bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:1", "start": 0, "eind": 4, "tekst": "Alfa", "bron_hash": "a"}
    agent = {"id": "agent", "klasse": "Voorwaarde", "tekst": "Alfa", "toelichting": "", "lifecycle": "voorgesteld",
             "herkomst": "agent", "aandacht": "geel", "jas_subtype": "parameter", "ankers": [anker],
             "trace": {"pijplijn": "hybrid_v1", "beslissing": {"door": "model"}, "twijfel": [{"reden": "DETECTOR_CONFLICT"}]}}
    mens = {"id": "mens", "klasse": "Voorwaarde", "tekst": "Alfa", "toelichting": "", "lifecycle": "human_approved",
            "herkomst": "mens", "ankers": [{**anker, "start": 0, "eind": 4}]}
    graph = ds.graph(graph_iri(laag["id"]))
    for triple in bouw_graaf(laag, [agent, mens]):
        graph.add(triple)
    ds.graph(REGISTER).add((SCHEMA, JAS.versie, Literal(SCHEMA_VERSIE)))
    ds.graph(REGISTER).add((laag_iri(laag["id"]), JAS.inGraaf, graph.identifier))
    ds.graph(REGISTER).add((laag_iri(laag["id"]), JAS.revisie, Literal(1)))
    return ds


@pytest.mark.parametrize("filters, verwacht", [
    ({"herkomst": ["mens"]}, {"mens"}),
    ({"herkomst": ["agent", "mens"]}, {"agent", "mens"}),
    ({"aandacht": ["geel"]}, {"agent"}),
    ({"aandacht": ["groen"]}, set()),
    ({"subtype": ["parameter"]}, {"agent"}),
    ({"beslist_door": ["model"]}, {"agent"}),
    ({"beslist_door": ["regel"]}, set()),
    ({"met_twijfel": True}, {"agent"}),
    ({"met_twijfel": False}, {"mens"}),
    ({"herkomst": ["agent"], "met_twijfel": False}, set()),
])
def test_herkomstfilters_vinden_precies_wat_de_projectie_schreef(filters, verwacht):
    ds = _rijke_dataset()
    assert {str(r.id) for r in ds.query(zoek_query(filters))} == verwacht


def test_een_verbijzonderende_tijdsaanduiding_reist_tot_in_de_graaf():
    """ADR-001 PR 8 (aanvulling 7 nov 2026): een duur is één Tijdsaanduiding met subtype "verbijzondert parameter".
    Het contract laat dat subtype toe (en geen verzonnen variant), de projectie schrijft `jas:subtype` en de
    zoekvraag vindt hem terug."""
    from pydantic import ValidationError

    from app.annotatie_v2_contracts import Element, Zoekvraag

    anker = {"bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:1", "start": 0, "eind": 13, "tekst": "binnen 48 uur",
             "bron_hash": "a"}
    duur = {"id": "duur", "klasse": "Tijdsaanduiding", "tekst": "binnen 48 uur", "toelichting": "",
            "lifecycle": "voorgesteld", "herkomst": "agent", "jas_subtype": "verbijzondert parameter", "ankers": [anker]}
    Element.model_validate(duur)
    with pytest.raises(ValidationError):
        Element.model_validate({**duur, "jas_subtype": "verbijzondert"})
    assert Zoekvraag(subtype=["verbijzondert parameter"]).subtype == ["verbijzondert parameter"]

    ds = Dataset()
    laag = {"id": "layer-t", "bron_iri": "urn:bwb:BWBR0004770:artikel:9", "revisie": 1, "status": "in_review"}
    graph = ds.graph(graph_iri(laag["id"]))
    for triple in bouw_graaf(laag, [duur]):
        graph.add(triple)
    ds.graph(REGISTER).add((SCHEMA, JAS.versie, Literal(SCHEMA_VERSIE)))
    ds.graph(REGISTER).add((laag_iri(laag["id"]), JAS.inGraaf, graph.identifier))
    ds.graph(REGISTER).add((laag_iri(laag["id"]), JAS.revisie, Literal(1)))
    assert Literal("verbijzondert parameter") in set(graph.objects(None, JAS.subtype))
    assert {str(r.id) for r in ds.query(zoek_query({"subtype": ["verbijzondert parameter"]}))} == {"duur"}
    assert not list(ds.query(zoek_query({"subtype": ["parameter"]})))


def test_terugval_is_een_eigen_beslisser_in_de_graaf():
    """Een voorlopige klasse na ABSTAIN draagt `besluit:terugval`, niet `besluit:model`."""
    ds = Dataset()
    laag = {"id": "layer-t", "bron_iri": "urn:bwb:BWBR0004770:artikel:9", "revisie": 1, "status": "in_review"}
    anker = {"bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:5", "start": 0, "eind": 9, "tekst": "één maand", "bron_hash": "a"}
    el = {"id": "t", "klasse": "Rechtsobject", "tekst": "één maand", "toelichting": "", "lifecycle": "voorgesteld",
          "herkomst": "agent", "aandacht": "geel", "ankers": [anker],
          "trace": {"pijplijn": "hybrid_v1", "beslissing": {"door": "terugval"}, "twijfel": [{"reden": "CLASSIFIER_ABSTAIN"}]}}
    graph = ds.graph(graph_iri(laag["id"]))
    for triple in bouw_graaf(laag, [el]):
        graph.add(triple)
    ds.graph(REGISTER).add((SCHEMA, JAS.versie, Literal(SCHEMA_VERSIE)))
    ds.graph(REGISTER).add((laag_iri(laag["id"]), JAS.inGraaf, graph.identifier))
    ds.graph(REGISTER).add((laag_iri(laag["id"]), JAS.revisie, Literal(1)))
    assert [str(r.id) for r in ds.query(zoek_query({"beslist_door": ["terugval"]}))] == ["t"]
    assert not list(ds.query(zoek_query({"beslist_door": ["model"]})))
