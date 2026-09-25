"""De JAS-vocabulaire: gegenereerd uit de methode (graph-qa), geprojecteerd door de api.

Wat hier bewaakt wordt, is wat de api eraan vastknoopt: elke klasse van de api vindt zijn concept
onder `klasse_iri`, de vocabulaire houdt zich aan de invarianten van de annotatiegraaf, en de
projectie zet hem neer als hij ontbreekt of een andere versie draagt – en anders niet."""
from __future__ import annotations

import httpx
from rdflib import Graph, Literal, RDF, URIRef
from rdflib.namespace import OWL, RDFS, SKOS

from app import graaf_projectie_v2 as projectie
from app.config import get_settings
from app.jas_klassen import JAS_KLASSEN_VOLGORDE
from graafdb_fake import installeer

JAS_NS = "urn:jas-ns:"


def _graaf() -> Graph:
    return Graph().parse(projectie.VOCABULAIRE_TTL, format="turtle")


def test_elke_klasse_van_de_api_heeft_een_concept():
    g = _graaf()
    for naam in JAS_KLASSEN_VOLGORDE:
        iri = projectie.klasse_iri(naam)
        assert (iri, RDF.type, URIRef(JAS_NS + "Klasse")) in g, naam
        assert (iri, SKOS.prefLabel, Literal(naam, lang="nl")) in g, naam
        assert g.value(iri, SKOS.definition), naam


def test_de_vocabulaire_houdt_zich_aan_de_invarianten():
    g = _graaf()
    assert not [s for s in g.subjects() if str(s).startswith("urn:bwb:")]
    verboden = {RDFS.domain, RDFS.range, RDFS.subClassOf, RDFS.subPropertyOf, OWL.sameAs}
    assert not [p for p in g.predicates() if p in verboden]
    assert not [p for p in g.predicates() if str(p).startswith("urn:bwb-ns:")]


def test_zestien_officiele_begrippen_onder_hun_klasse():
    g = _graaf()
    begrippen = set(g.subjects(RDF.type, URIRef(JAS_NS + "Begrip")))
    assert len(begrippen) == 16
    for b in begrippen:
        assert g.value(b, SKOS.broader) in {projectie.klasse_iri(n) for n in JAS_KLASSEN_VOLGORDE}


def test_versie_in_ttl_en_json_is_dezelfde():
    versie, ttl = projectie.vocabulaire()
    assert (projectie.VOCAB_SCHEMA, URIRef(JAS_NS + "vocabulaireVersie"), Literal(versie)) in _graaf()
    assert projectie.verklaringen()["vocabulaire_versie"] == versie


def test_de_verklaringen_dekken_de_klassen_en_de_codes():
    v = projectie.verklaringen()
    assert [k["naam"] for k in v["klassen"]] == list(JAS_KLASSEN_VOLGORDE)
    assert v["detectie"]["TEMPORAL_DURATION"]["naam"] == "Termijn"
    assert "R-CONFLICT-HUMAN" in v["resolutie"] and "DETECTOR_CONFLICT" in v["twijfel"]


async def test_de_projectie_zet_de_vocabulaire_neer_en_alleen_als_het_moet(monkeypatch):
    nep = installeer(monkeypatch)
    try:
        async with httpx.AsyncClient() as client:
            assert await projectie.zorg_voor_vocabulaire(client) is True
            assert await projectie.zorg_voor_vocabulaire(client) is False
        assert len(nep.ds.graph(projectie.VOCABULAIRE)) == len(_graaf())
    finally:
        get_settings.cache_clear()
