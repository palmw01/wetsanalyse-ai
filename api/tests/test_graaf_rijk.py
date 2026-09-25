"""Projectieschema 3: de graaf draagt alles wat Postgres over een markering weet en geen persoon is.

Eén realistisch element – met het herkomstspoor van de hybride keten, een alternatief, twee
beoordelingen van een jurist en de dekking van zijn bronnode – moet SHACL-conform zijn, zijn
rijkdom als triples dragen en géén actor of vrije commentaartekst bevatten."""
from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Graph, Literal, RDF, URIRef
from rdflib.compare import isomorphic

from app.graaf_projectie_v2 import JAS, OA, PROV, bouw_graaf, element_iri, klasse_iri, laag_iri, run_iri
from app.shacl import valideer

BRON = "urn:bwb:BWBR0004770:artikel:9:lid:1"
TEKST = "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet."
HASH = "a" * 64
LAAG = {"id": "laag-9-1", "revisie": 4, "status": "in_review", "bron_iri": BRON, "snapshot_id": "snap-1"}
RUN = {"model": "claude-sonnet-5", "provider": "anthropic_via_azure_foundry", "agent_versie": "1.6.0",
       "prompt_hash": "a91e", "methode_versie": "3c0d", "modus": "nieuw", "tijd": "2026-09-25T10:12:31+00:00",
       "instellingen": {"meting": {"taal_model": "nl_core_news_md"}}}
SPOOR = {
    "pijplijn": "hybrid_v1", "jas_versie": "1.0.10",
    "kandidaat": {"id": "k4", "label": "C004", "span": {"bron_iri": BRON, "start": 50, "eind": 86},
                  "mogelijke_klassen": ["Rechtsfeit", "Tijdsaanduiding", "Rechtsobject"],
                  "bewijs": [{"detector": "nominalisatie", "code": "NOMINALIZED_ACTION", "regel": "jas.feit.nominalisatie_van"},
                             {"detector": "tijd", "code": "TEMPORAL_MOMENT", "regel": "jas.tijd.tijdstip"}],
                  "spanopties": [{"soort": "kern", "start": 53, "eind": 64}, {"soort": "zinsdeel", "start": 50, "eind": 86}]},
    "beslissing": {"klasse": "Rechtsfeit", "door": "model", "status": "HUMAN_REVIEW"},
    "vraag": 'C004 | "de dagtekening van het aanslagbiljet" | toegestaan: Rechtsfeit, Tijdsaanduiding, Rechtsobject',
    "validatie": [], "twijfel": [{"label": "C004", "reden": "DETECTOR_CONFLICT"}],
    "resolutie": [{"label": "C004", "regel": "R-CONFLICT-HUMAN"}],
}
ELEMENT = {
    "id": "e3", "klasse": "Tijdsaanduiding", "tekst": "de dagtekening van het aanslagbiljet", "toelichting": "…",
    "lifecycle": "edited", "verouderd": False, "herkomst": "agent", "aandacht": "geel", "snapshot_id": "snap-1",
    "ankers": [{"bron_iri": BRON, "start": 50, "eind": 86, "tekst": TEKST[50:86], "bron_hash": HASH}],
    "alternatieven": [{"klasse": "Rechtsfeit", "motivatie": "de keuze van het model"}],
    "geproduceerd_door": RUN, "trace": SPOOR,
    "beslissingen": [
        {"type": "edit", "actor": "jdejurist", "tijd": "2026-09-25T10:14:00+00:00", "comment": "Zie het beleid van J. Jansen",
         "review_reason": "verkeerde_klasse", "wijziging": {"klasse": "Tijdsaanduiding"}},
        {"type": "comment", "actor": "jdejurist", "tijd": "2026-09-25T10:15:00+00:00", "comment": "privé opmerking",
         "review_reason": None, "wijziging": {}},
    ],
}
DEKKING = {BRON: {"dimensies": {"tijd": "uitgevoerd", "definitie": "overgeslagen"},
                  "ongedekt": [{"tekst": "is invorderbaar", "start": 21, "eind": 36}]}}
FIXTURE = Path(__file__).resolve().parents[2] / "tools" / "graph-qa" / "tests" / "fixtures" / "jas_laag_v3_voorbeeld.ttl"


@pytest.fixture(scope="module")
def graaf() -> Graph:
    return bouw_graaf(LAAG, [ELEMENT], dekking=DEKKING)


def test_de_rijke_laag_is_shacl_conform(graaf):
    pytest.importorskip("pyshacl")
    r = valideer(graaf)
    assert r["conform"] is True, r


def test_klasse_als_concept_en_classificerende_annotatie(graaf):
    e = element_iri("e3")
    assert (e, JAS.klasse, klasse_iri("Tijdsaanduiding")) in graaf
    assert (e, OA.hasBody, klasse_iri("Tijdsaanduiding")) in graaf
    assert (e, OA.motivatedBy, OA.classifying) in graaf
    assert (e, JAS.aandacht, Literal("geel")) in graaf and (e, JAS.herkomst, Literal("agent")) in graaf
    alt, = graaf.objects(e, JAS.alternatief)
    assert (alt, JAS.klasse, klasse_iri("Rechtsfeit")) in graaf
    assert len(list(graaf.objects(e, JAS.grensoptie))) == 2


def test_herkomst_als_prov_met_regels_en_codes_uit_de_vocabulaire(graaf):
    besluit, = graaf.objects(element_iri("e3"), PROV.wasGeneratedBy)
    assert (besluit, JAS.beslistDoor, URIRef("urn:jas-ns:besluit:model")) in graaf
    assert (besluit, JAS.regel, URIRef("urn:jas-ns:regel:jas.tijd.tijdstip")) in graaf
    assert (besluit, JAS.bewijs, URIRef("urn:jas-ns:code:NOMINALIZED_ACTION")) in graaf
    assert (besluit, JAS.twijfel, URIRef("urn:jas-ns:twijfel:DETECTOR_CONFLICT")) in graaf
    assert (besluit, JAS.resolutieregel, URIRef("urn:jas-ns:resolutie:R-CONFLICT-HUMAN")) in graaf
    assert str(graaf.value(besluit, JAS.modelvraag)).startswith("C004 |")
    ronde = graaf.value(besluit, PROV.wasInformedBy)
    assert ronde == run_iri(RUN) and (ronde, RDF.type, PROV.Activity) in graaf
    model = graaf.value(ronde, PROV.wasAssociatedWith)
    assert (model, RDF.type, PROV.SoftwareAgent) in graaf
    assert (ronde, JAS.taalModel, Literal("nl_core_news_md")) in graaf


def test_beoordelingen_zonder_persoon_en_zonder_commentaartekst(graaf):
    b = sorted(graaf.objects(element_iri("e3"), JAS.beoordeling), key=lambda n: int(graaf.value(n, JAS.volgorde)))
    assert [str(graaf.value(n, JAS.soort)) for n in b] == ["edit", "comment"]
    assert (b[0], JAS.van, klasse_iri("Rechtsfeit")) in graaf and (b[0], JAS.naar, klasse_iri("Tijdsaanduiding")) in graaf
    tekst = graaf.serialize(format="nt")
    assert "jdejurist" not in tekst and "Jansen" not in tekst and "privé" not in tekst


def test_dekking_per_bronnode_met_ongedekte_zinsdelen(graaf):
    d, = graaf.objects(laag_iri("laag-9-1"), JAS.dekking)
    o, = graaf.objects(d, JAS.ongedekt)
    assert (o, OA.hasSource, URIRef(BRON)) in graaf
    exact = {str(graaf.value(s, OA.exact)) for s in graaf.objects(o, OA.hasSelector) if graaf.value(s, OA.exact)}
    assert exact == {"is invorderbaar"}


def test_een_actor_in_een_beoordeling_breekt_de_shape(graaf):
    pytest.importorskip("pyshacl")
    g = Graph()
    for t in graaf:
        g.add(t)
    b = next(g.objects(element_iri("e3"), JAS.beoordeling))
    g.add((b, JAS.actor, Literal("jdejurist")))
    r = valideer(g)
    assert r["conform"] is False and any("persoon" in x["melding"] for x in r["jas_model"])


def test_graph_qa_fixture_v3_volgt_de_projectie(graaf):
    """Faalt dit na een wijziging aan de projectie: schrijf `bouw_graaf(LAAG, [ELEMENT], dekking=DEKKING)`
    als Turtle naar tools/graph-qa/tests/fixtures/jas_laag_v3_voorbeeld.ttl en draai daar de isolatietest."""
    assert isomorphic(Graph().parse(FIXTURE, format="turtle"), graaf)
