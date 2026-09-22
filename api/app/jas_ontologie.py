"""De `jas:`-ontologie: het vocabulaire waarmee de annotatielagen in de kennisgraaf staan.

Een markering is een W3C Web Annotation (`oa:`), met herkomst in PROV-O (`prov:`) en de JAS-klassen
als SKOS-concepten. Wat die twee standaarden niet dekken – de laag, de lidstand, de review-levenscyclus,
de Critic – staat hier onder `urn:jas-ns:`.

**Geen `rdfs:domain`, `rdfs:range`, `subPropertyOf` of `owl:sameAs`, met opzet.** De repository draait
met `rdfsplus-optimized`: een range op een property die naar een wet-node wijst (`oa:hasSource`,
`jas:bepaling`) laat GraphDB triples áfleiden met een `urn:bwb:`-subject. Die belanden in de union die
alle QA-queries van Lex bevragen, en daarmee zou een annotatie de wettekst vervuilen. Om dezelfde reden
worden de OA- en PROV-ontologieën zelf niet geladen. `tests/test_graaf_projectie.py` bewaakt dat.

Gegenereerd uit `jas_klassen.py`, de canonieke klassenlijst van de api. Het Turtle-bestand in
`docs/wetsanalyse-workbench/jas-ontologie.ttl` is een afdruk hiervan met een drift-test erop.
"""
from __future__ import annotations

import re

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, PROV, RDF, RDFS, SKOS, XSD

from .annotatie_contracts import Aandacht, BeslissingType, DocumentStatus, Lifecycle, ReviewReason
from .jas_klassen import JAS_KLASSEN_VOLGORDE

JAS = Namespace("urn:jas-ns:")
JASK = Namespace("urn:jas-ns:klasse:")
OA = Namespace("http://www.w3.org/ns/oa#")

ONTOLOGIE_GRAAF = URIRef("urn:jas:graph:ontologie")


def klasse_slug(klasse: str) -> str:
    """"Variabele en variabelewaarde" → "variabele-en-variabelewaarde"."""
    return re.sub(r"[^a-z0-9]+", "-", klasse.lower()).strip("-")


def klasse_iri(klasse: str) -> URIRef:
    return JASK[klasse_slug(klasse)]


def waarde_iri(soort: str, waarde: str) -> URIRef:
    """Een waarde uit een vaste lijst als eigen node: `jas:lifecycle-human_approved`.

    Een node in plaats van een string, zodat de waarde een label en een schema heeft en een query er
    zonder tekstvergelijking op kan filteren."""
    return JAS[f"{soort}-{waarde}"]


#: Klassen van het eigen vocabulaire: (lokale naam, label, uitleg).
_KLASSEN = (
    ("AnnotatieLaag", "annotatielaag", "De gedeelde JAS-annotatie van één artikel."),
    ("Lidstand", "lidstand", "De versie van de wettekst van één lid waarop de laag gebaseerd is."),
    ("Markering", "markering", "Eén JAS-markering: een fragment wettekst met zijn klasse."),
    ("Alternatief", "alternatief", "Een andere klasse die bij twijfel in aanmerking kwam."),
    ("CriticRonde", "Critic-ronde", "Eén oordeel van de Critic over een markering."),
    ("Beslissing", "beslissing", "Eén oordeel van een jurist over een markering."),
    ("AgentRun", "agent-ronde", "Eén beurt van Lex die markeringen voorstelde of hergebruikte."),
    ("Register", "register", "Welke lagen er in de kennisgraaf staan, en in welke versie."),
)

#: Properties: (lokale naam, object- of datatype-property, label).
_PROPERTIES = (
    ("inLaag", "object", "in laag"),
    ("heeftLidstand", "object", "heeft lidstand"),
    ("bepaling", "object", "bepaling in de wet"),
    ("inGraaf", "object", "in named graph"),
    ("lifecycle", "object", "reviewstatus"),
    ("aandacht", "object", "aandacht (Critic)"),
    ("status", "object", "status"),
    ("klasse", "object", "JAS-klasse"),
    ("voorstelKlasse", "object", "voorgestelde klasse"),
    ("beslissingType", "object", "soort beslissing"),
    ("reviewReden", "object", "reden"),
    ("heeftAlternatief", "object", "heeft alternatief"),
    ("heeftCriticRonde", "object", "heeft Critic-ronde"),
    ("heeftBeslissing", "object", "heeft beslissing"),
    ("bwbId", "data", "BWB-id"),
    ("artikel", "data", "artikel"),
    ("lid", "data", "lid"),
    ("slug", "data", "slug in de api"),
    ("elementId", "data", "element-id"),
    ("herkomst", "data", "aangemaakt door (agent of mens)"),
    ("gewijzigdDoor", "data", "laatst gewijzigd door (agent of mens)"),
    ("verouderd", "data", "hoort bij een oudere versie van de wettekst"),
    ("vindplaats", "data", "vindplaats"),
    ("bronHash", "data", "hash van het artikelcorpus"),
    ("lidHash", "data", "hash van het lidsegment"),
    ("motivatie", "data", "motivatie"),
    ("ronde", "data", "ronde"),
    ("actie", "data", "actie van de Critic"),
    ("toegepast", "data", "toegepast"),
    ("voorstelTekst", "data", "voorgesteld fragment"),
    ("opmerking", "data", "opmerking"),
    ("wijziging", "data", "wijziging (JSON)"),
    ("modus", "data", "modus"),
    ("criticRondes", "data", "aantal Critic-rondes"),
    ("stopReden", "data", "stopreden"),
    ("promptHash", "data", "prompt-hash"),
    ("methodeVersie", "data", "methodeversie"),
    ("versie", "data", "versie"),
)

#: De vaste waardelijsten als SKOS-schema's: (soort, enum).
_WAARDELIJSTEN = (
    ("lifecycle", Lifecycle),
    ("aandacht", Aandacht),
    ("status", DocumentStatus),
    ("beslissing", BeslissingType),
    ("reden", ReviewReason),
)


def bouw_ontologie() -> Graph:
    g = Graph()
    g.bind("jas", JAS)
    g.bind("jask", JASK)
    g.bind("skos", SKOS)
    g.bind("owl", OWL)
    g.bind("dcterms", DCTERMS)

    ont = URIRef("urn:jas-ns:")
    g.add((ont, RDF.type, OWL.Ontology))
    g.add((ont, RDFS.label, Literal("JAS-annotaties", lang="nl")))
    g.add((ont, DCTERMS.description, Literal(
        "Vocabulaire voor JAS-annotaties (activiteit 2 van de methode Wetsanalyse) op de BWB-graaf. "
        "Markeringen zijn W3C Web Annotations (oa:), herkomst staat in PROV-O.", lang="nl")))

    for naam, label, uitleg in _KLASSEN:
        g.add((JAS[naam], RDF.type, OWL.Class))
        g.add((JAS[naam], RDFS.label, Literal(label, lang="nl")))
        g.add((JAS[naam], RDFS.comment, Literal(uitleg, lang="nl")))

    for naam, soort, label in _PROPERTIES:
        g.add((JAS[naam], RDF.type, OWL.ObjectProperty if soort == "object" else OWL.DatatypeProperty))
        g.add((JAS[naam], RDFS.label, Literal(label, lang="nl")))

    schema = JAS.klassen
    g.add((schema, RDF.type, SKOS.ConceptScheme))
    g.add((schema, SKOS.prefLabel, Literal("JAS-klassen", lang="nl")))
    for i, klasse in enumerate(JAS_KLASSEN_VOLGORDE, start=1):
        c = klasse_iri(klasse)
        g.add((c, RDF.type, SKOS.Concept))
        g.add((c, SKOS.prefLabel, Literal(klasse, lang="nl")))
        g.add((c, SKOS.notation, Literal(i, datatype=XSD.integer)))
        g.add((c, SKOS.inScheme, schema))
        g.add((c, SKOS.topConceptOf, schema))

    for soort, enum in _WAARDELIJSTEN:
        lijst = JAS[f"{soort}-waarden"]
        g.add((lijst, RDF.type, SKOS.ConceptScheme))
        g.add((lijst, SKOS.prefLabel, Literal(soort, lang="nl")))
        for lid in enum:
            c = waarde_iri(soort, lid.value)
            g.add((c, RDF.type, SKOS.Concept))
            g.add((c, SKOS.prefLabel, Literal(lid.value, lang="nl")))
            g.add((c, SKOS.inScheme, lijst))

    # PROV/OA worden alleen gebruikt, niet geladen; hun namespaces horen wel in de afdruk.
    g.bind("prov", PROV)
    g.bind("oa", OA)
    return g


def ontologie_turtle() -> str:
    return bouw_ontologie().serialize(format="turtle")
