"""Genereer de referentiedocumentatie van de ontologieën in de kennisgraaf (`docs/ontologie/`).

Bron, en niets anders:

- **BWB** (wettekst): de T-Box uit `tools/bwb-import/app/ontology.py` en de shapes `tools/bwb-import/app/shapes/
  bwb-graaf.ttl`;
- **JAS** (annotatielagen): de shapes `api/app/shapes/jas-v2.ttl` en de vocabulaire `api/app/vocabulaire/
  jas-vocabulaire.ttl` (alleen de namen van de dertien klassen);
- **WA** (begrippen en afleidingsregels): `docs/ontologie/wa-vocabulaire.ttl` en de shapes `api/app/shapes/
  begrippen-wa.ttl` en `regels-wa.ttl`; NL-SBB alleen als verwijzing;
- **KGO** (kennisgroepen): `docs/ontologie/kg-vocabulaire.ttl` (geen shapes).

Doel: `docs/ontologie/bwb-ontologie.ttl` (de T-Box met versie), `docs/ontologie/README.md` (Markdown met
Mermaid-diagrammen, leesbaar op GitHub) en `docs/ontologie/ontologie.html` (dezelfde inhoud als pagina).

Versie per ontologie in `docs/ontologie/versies.json`: per versie de hash van haar bronnen. Verandert een bron zonder
dat de versie omhoog gaat, dan weigert de generator; elke versie moet in `CHANGELOG.md` staan.

`--check` (de drift-test, `tests/methode/test_ontologie_docs.py`) vergelijkt de gegenereerde bestanden met wat er
staat, en eist daarnaast dat elke term die de code schrijft (`WA.<term>`, `KGO.<term>`, `kgo:<term>`) in het
vocabulaire staat, dat de documentatievocabulaires geen `rdfs:domain`/`rdfs:range` dragen, en dat elke named graph
nog in de code voorkomt. De kwaliteitstoets (`toets`) toetst de ontologie zelf: label en uitleg per eigen term, verwijzingen
naar gedeclareerde of bekende termen, shapes tegen het vocabulaire en de shapes onderling; een fout laat `--check` falen,
een waarschuwing staat in de documentatie.

    uv run --extra dev python scripts/genereer_ontologie_docs.py           # schrijven
    uv run --extra dev python scripts/genereer_ontologie_docs.py --check   # alleen vergelijken
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, SH, XSD

WORTEL = Path(__file__).resolve().parents[3]
DOCS = WORTEL / "docs" / "ontologie"
TTL_BWB, README, HTML_, VERSIES, CHANGELOG = (DOCS / n for n in (
    "bwb-ontologie.ttl", "README.md", "ontologie.html", "versies.json", "CHANGELOG.md"))
SCHEMA = Namespace("https://schema.org/")
SCRIPT = "tools/graph-qa/scripts/genereer_ontologie_docs.py"

PREFIXEN = {
    "urn:bwb-ns:": "bwb", "urn:jas-ns:": "jas", "urn:wa-ns:": "wa", "urn:wa-kg-ns:": "kgo",
    "http://data.europa.eu/eli/ontology#": "eli", "http://xmlns.com/foaf/0.1/": "foaf",  # NOSONAR: namespace-id, geen verbinding
    "http://www.w3.org/ns/oa#": "oa", "http://www.w3.org/2004/02/skos/core#": "skos",
    "http://purl.org/dc/terms/": "dct", "http://www.w3.org/ns/prov#": "prov",
    "http://www.w3.org/2001/XMLSchema#": "xsd", "http://www.w3.org/2000/01/rdf-schema#": "rdfs",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf", "http://www.w3.org/2002/07/owl#": "owl",
    "http://www.w3.org/ns/shacl#": "sh",
}
#: Een eindpunt dat de shapes alleen met een patroon op de IRI vastleggen (open world, of in een andere graph): naar
#: welke klasse het wijst, voor het diagram.
PATROON_KLASSE = (
    ("^urn:bwb:BWB", "urn:bwb-ns:Citeerbaar"),
    ("^urn:jas:(element|impliciet):", "urn:jas-ns:Markering"),
    ("^urn:jas:element:", "urn:jas-ns:Markering"),
    ("^urn:jas-ns:klasse:", "urn:jas-ns:Klasse"),
)


def kort(iri) -> str:
    s = str(iri)
    for ns, p in PREFIXEN.items():
        if s.startswith(ns):
            return f"{p}:{s[len(ns):]}"
    return s


def lokaal(iri) -> str:
    return re.split(r"[#:/]", str(iri))[-1]


def lees(pad: str) -> str:
    return (WORTEL / pad).read_text(encoding="utf-8").replace("\r\n", "\n")


# ---------------------------------------------------------------------------------------------------- de bronnen

def bwb_tbox(versie: str | None) -> Graph:
    """De T-Box zoals de importer hem bouwt, met (alleen in de documentatie) versie en versie-IRI."""
    # De importer heet `app`, net als de api: een eerder geïmporteerde `app` gaat even opzij en komt daarna terug.
    pad = str(WORTEL / "tools" / "bwb-import")
    opzij = {n: m for n, m in sys.modules.items() if n == "app" or n.startswith("app.")}
    for n in opzij:
        del sys.modules[n]
    sys.path.insert(0, pad)
    try:
        from app.ontology import build_ontology  # noqa: PLC0415
        from app.rdf_vocab import Vocab  # noqa: PLC0415
    finally:
        sys.path.remove(pad)
        for n in [n for n in sys.modules if n == "app" or n.startswith("app.")]:
            del sys.modules[n]
        sys.modules.update(opzij)
    vocab = Vocab()
    g = build_ontology(vocab)
    if versie:
        g.add((vocab.ontology_resource, OWL.versionInfo, Literal(versie)))
        g.add((vocab.ontology_resource, OWL.versionIRI, URIRef(f"urn:bwb-ns:versie:{versie}")))
    return g


def tbox_turtle(versie: str | None) -> str:
    g = bwb_tbox(versie)
    g.bind("bwb", Namespace("urn:bwb-ns:"))
    kop = (f"# GEGENEREERD door {SCRIPT}; niet met de hand bewerken.\n"
           "# De T-Box van de BWB-graaf (bron: tools/bwb-import/app/ontology.py). De importer laadt dezelfde T-Box naar\n"
           "# de named graph urn:bwb:graph:ontologie; owl:versionInfo en owl:versionIRI staan alleen in dit bestand.\n"
           "# Wat een node moet hebben: tools/bwb-import/app/shapes/bwb-graaf.ttl.\n\n")
    return kop + g.serialize(format="turtle")


def graaf(*paden: str) -> Graph:
    g = Graph()
    for p in paden:
        g.parse(data=lees(p), format="turtle")
    return g


@dataclass
class Ontologie:
    sleutel: str
    titel: str
    kleur: str
    namespace: str
    inleiding: str
    vocab: list[str] = field(default_factory=list)       # bestanden met klassen en eigenschappen
    shapes: list[str] = field(default_factory=list)
    hashbronnen: list[str] = field(default_factory=list)
    formeel: list[tuple[str, str]] = field(default_factory=list)
    naamgeving: dict[str, str] = field(default_factory=dict)   # shape zonder doelklasse → klassenaam


ONTOLOGIEEN = [
    Ontologie(
        "bwb", "Wettekst (BWB)", "bwb", "urn:bwb-ns:",
        "De BWB-importer haalt de wettekst bij de officiële bron en schrijft per regeling één named graph. De "
        "**T-Box** zegt welke klassen en eigenschappen er zijn en hoe ze op ELI aansluiten; de **shapes** zeggen wat een "
        "node van elke klasse moet en mag hebben. De importer toetst elke graph vóór hij hem schrijft: een graph die "
        "afwijkt, vervangt nooit een bestaande. Resources staan onder `urn:bwb:` (bijvoorbeeld "
        "`urn:bwb:BWBR0004770:artikel:9:lid:1`), het vocabulaire onder `urn:bwb-ns:`: bewust disjunct.",
        shapes=["tools/bwb-import/app/shapes/bwb-graaf.ttl"],
        formeel=[("T-Box", "`docs/ontologie/bwb-ontologie.ttl`, gegenereerd uit `tools/bwb-import/app/ontology.py`"),
                 ("Shapes", "`tools/bwb-import/app/shapes/bwb-graaf.ttl`, blokkerend vóór elke PUT"),
                 ("Drift", "`tools/bwb-import/tests/test_ontology.py`, `test_shacl.py`")],
    ),
    Ontologie(
        "jas", "JAS-annotatielagen", "jas", "urn:jas-ns:",
        "Een markering is een W3C Web Annotation (`oa:Annotation`) op een bronnode: het doel met positie en letterlijk "
        "citaat, de JAS-klasse, de levenscyclus en het herkomstspoor. Eén laag hoort bij één bronnode en staat in een "
        "eigen named graph. Postgres is de waarheid; de api projecteert. Personen en vrije commentaartekst staan er "
        "nooit in. Er is bewust **geen T-Box**: met `rdfsplus-optimized` zou een `rdfs:range` op een property naar een "
        "wetsnode triples met de wet als subject laten afleiden. De shapes zijn verdeeld in de groepen "
        "*RDF-structuur* en *JAS-model*.",
        shapes=["api/app/shapes/jas-v2.ttl"],
        hashbronnen=["api/app/shapes/jas-v2.ttl"],
        formeel=[("Vocabulaire", "`api/app/vocabulaire/jas-vocabulaire.ttl` (SKOS: klassen, begrippen, regels, codes), "
                                 "gegenereerd door `tools/graph-qa/scripts/genereer_jas_vocabulaire.py`"),
                 ("Shapes", "`api/app/shapes/jas-v2.ttl`, diagnostisch (tests, CI, graafcontrole)"),
                 ("Uitleg", "`docs/wetsanalyse-workbench/jas-annotatie-ontologie.md`")],
        naamgeving={"GrensShape": "Grensoptie", "DimensieShape": "Dimensie"},
    ),
    Ontologie(
        "wa", "Begrippen en afleidingsregels", "wa", "urn:wa-ns:",
        "Per werkgebied staat er één named graph met het begrippenkader (`skos:ConceptScheme`, volgens NL-SBB) en de "
        "afleidingsregels. Een begrip rust op de passages die het dragen: elke koppeling wijst naar een markering met "
        "haar bewijsstand, en via die markering naar de bepaling. Een regel loopt naar de wettekst via zijn dragers. "
        "Begrippen zijn analyse-uitkomsten, geen wettelijke definities. Het NL-SBB-profiel (`api/app/shapes/"
        "nl-sbb-1.0.0.ttl`, Geonovum, CC-BY 4.0; herkomst in `api/app/shapes/BRON.md`) staat hier niet in: de tabellen "
        "geven alleen de eigen eisen. Het vocabulaire `wa-vocabulaire.ttl` is **alleen documentatie** en wordt niet "
        "in GraphDB geladen.",
        vocab=["docs/ontologie/wa-vocabulaire.ttl"],
        shapes=["api/app/shapes/begrippen-wa.ttl", "api/app/shapes/regels-wa.ttl"],
        formeel=[("Vocabulaire", "`docs/ontologie/wa-vocabulaire.ttl`, alleen documentatie"),
                 ("Shapes", "NL-SBB 1.0.0 (`api/app/shapes/nl-sbb-1.0.0.ttl`) en `begrippen-wa.ttl`, `regels-wa.ttl`; "
                            "diagnostisch (conformiteit)"),
                 ("Uitleg", "`api/CLAUDE.md` §Begrippen naar de kennisgraaf, `docs/architectuur/adr-003-nl-sbb-begrippencontract.md`")],
    ),
    Ontologie(
        "kgo", "Kennisgroepstandpunten", "kg", "urn:wa-kg-ns:",
        "Een index van de openbaar gepubliceerde standpunten van de kennisgroepen van de Belastingdienst. De graaf weet "
        "*dat* een standpunt over een bepaling gaat en *waar* het staat; de leestool van Lex haalt de inhoud. De index "
        "staat los van de wet: geen subject onder `urn:bwb:` en geen `bwb:`-typen, en een bepaling staat erin als tekst "
        "(BWB-id, artikel, lid), niet als IRI. Er zijn **geen shapes**: de kolom *aantal* is daarom leeg. Rij, "
        "verwijzing en gebeurtenis zijn in de graaf niet getypeerd; hun klassen bestaan alleen in de documentatie.",
        vocab=["docs/ontologie/kg-vocabulaire.ttl"],
        formeel=[("Vocabulaire", "`docs/ontologie/kg-vocabulaire.ttl`, alleen documentatie"),
                 ("Shapes", "geen"),
                 ("Schrijver", "`tools/bwb-import/app/kennisgroepen.py`")],
    ),
]

#: Mermaid in de kleuren van de Lex-app, op elk diagram (GitHub en de artifactviewer hebben elk hun eigen standaard).
THEMA = ('%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#F5F6F8", "primaryBorderColor": "#154273", '
         '"primaryTextColor": "#1A1A1A", "lineColor": "#4A5A6E", "secondaryColor": "#EDF0F4", "tertiaryColor": "#FFFFFF"}}}%%\n')

#: De named graphs, met het bestand waarin hun IRI staat (de check eist dat hij daar nog staat).
NAMED_GRAPHS = [
    ("bwb", "urn:bwb:graph:<bwb-id>", "De wettekst van één regeling", "BWB-importer, PUT per regeling",
     "tools/bwb-import/app/rdf_vocab.py", '"graph", bwb_id'),
    ("bwb", "urn:bwb:graph:ontologie", "De T-Box", "BWB-importer", "tools/bwb-import/app/rdf_vocab.py",
     '"graph", "ontologie"'),
    ("jas", "urn:jas:graph:v2:<laag-id>", "Eén annotatielaag op één bronnode", "api, na elke commit",
     "api/app/graaf_projectie_v2.py", "urn:jas:graph:v2:"),
    ("jas", "urn:jas:graph:register:v2", "Register van de lagen", "api", "api/app/graaf_projectie_v2.py",
     "urn:jas:graph:register:v2"),
    ("jas", "urn:jas:graph:vocabulaire", "De JAS-methode als SKOS", "api", "api/app/graaf_projectie_v2.py",
     "urn:jas:graph:vocabulaire"),
    ("wa", "urn:wa:graph:werkgebied:<id>", "Begrippenkader en afleidingsregels van één werkgebied",
     "api, na elke commit", "api/app/begrip_projectie.py", "urn:wa:graph:werkgebied:"),
    ("wa", "urn:wa:graph:register:begrippen", "Register van de werkgebied-graphs", "api",
     "api/app/begrip_projectie.py", "urn:wa:graph:register:begrippen"),
    ("kgo", "urn:wa:graph:kennisgroepen", "Index van de kennisgroepstandpunten", "BWB-importer",
     "packages/bronmodel/bronmodel/kennisgroepen.py", "urn:wa:graph:kennisgroepen"),
]
GRAPH_DIAGRAM = THEMA + """flowchart LR
  ont["urn:bwb:graph:ontologie<br/>T-Box"]:::bwb
  wet["urn:bwb:graph:#lt;bwb-id#gt;<br/>wettekst per regeling"]:::bwb
  voc["urn:jas:graph:vocabulaire<br/>JAS-methode"]:::jas
  laag["urn:jas:graph:v2:#lt;laag-id#gt;<br/>annotatielaag"]:::jas
  jreg["urn:jas:graph:register:v2"]:::jas
  wg["urn:wa:graph:werkgebied:#lt;id#gt;<br/>begrippen en regels"]:::wa
  breg["urn:wa:graph:register:begrippen"]:::wa
  kg["urn:wa:graph:kennisgroepen<br/>standpunten"]:::kg
  wet -->|instanties van de T-Box| ont
  laag -->|oa:hasSource, jas:bepaling| wet
  laag -->|jas:klasse| voc
  jreg -->|registreert| laag
  wg -->|wa:element| laag
  wg -->|wa:bron| wet
  breg -->|registreert| wg
  kg -.->|bwbId en artikel als tekst| wet
  classDef bwb fill:#E8EEF5,stroke:#154273,color:#1A1A1A
  classDef jas fill:#FBEFE2,stroke:#8E4600,color:#1A1A1A
  classDef wa fill:#E9F3E1,stroke:#2C6608,color:#1A1A1A
  classDef kg fill:#EDF0F4,stroke:#4A5A6E,color:#1A1A1A"""

#: Waar elk vocabulaire gebruikt wordt: (bestand, regex met de term als groep 1, namespace).
GEBRUIK = [
    ("api/app/begrip_projectie.py", r"\bWA\.(\w+)", "urn:wa-ns:"),
    ("api/app/regel_projectie.py", r"\bWA\.(\w+)", "urn:wa-ns:"),
    ("tools/bwb-import/app/kennisgroepen.py", r"\bKGO\.(\w+)", "urn:wa-kg-ns:"),
    ("tools/graph-qa/agent/adapters/kennisgroepen_bron.py", r"\bkgo:(\w+)", "urn:wa-kg-ns:"),
]
DOC_VOCABS = ["docs/ontologie/wa-vocabulaire.ttl", "docs/ontologie/kg-vocabulaire.ttl"]


# ---------------------------------------------------------------------------------------------------- het model

@dataclass
class Eigenschap:
    pad: str
    aantal: str
    soort: str
    uitleg: str = ""
    groep: str = ""
    doel: str | None = None       # klasse-IRI als het een relatie in het diagram is


@dataclass
class Klasse:
    iri: str
    label: str = ""
    uitleg: str = ""
    supers: list[str] = field(default_factory=list)
    eigenschappen: list[Eigenschap] = field(default_factory=list)
    noten: list[str] = field(default_factory=list)
    geldt_voor: list[str] = field(default_factory=list)


def _lit(g: Graph, s, p) -> str:
    vals = [str(o) for o in g.objects(s, p) if isinstance(o, Literal)]
    nl = [str(o) for o in g.objects(s, p) if isinstance(o, Literal) and o.language == "nl"]
    return (nl or vals or [""])[0]


def _lijst(g: Graph, node) -> list:
    return list(Collection(g, node)) if node is not None else []


def aantal(mn, mx) -> str:
    mn = int(mn) if mn is not None else 0
    if mx is not None and int(mx) == 0:
        return "0"
    hoog = "n" if mx is None else str(int(mx))
    return str(mn) if hoog == str(mn) else f"{mn}..{hoog}"


def _waarde(v) -> str:
    return f'"{v}"' if isinstance(v, Literal) and v.datatype is None and not isinstance(v.toPython(), (int, bool)) \
        else (kort(v) if isinstance(v, URIRef) else str(v))


class Shapes:
    def __init__(self, g: Graph, vocab: Graph, naamgeving: dict[str, str]):
        self.g, self.vocab, self.naamgeving = g, vocab, naamgeving

    def klasse_van_shape(self, shape) -> str | None:
        for p in (SH.targetClass, SH["class"]):
            doelen = list(self.g.objects(shape, p))
            if len(doelen) == 1:
                return str(doelen[0])
        if isinstance(shape, URIRef) and shape.endswith("Shape"):
            naam = lokaal(shape)
            ns = next((ns for ns in PREFIXEN if ns.endswith(":") and str(shape).startswith(ns[:-1])), None)
            basis = self.naamgeving.get(naam, naam[: -len("Shape")])
            if ns:
                return ns + basis
        return None

    def is_datatype_shape(self, shape) -> bool:
        return (shape, SH.datatype, None) in self.g and (shape, SH.property, None) not in self.g

    def pad(self, ps) -> str:
        p = self.g.value(ps, SH.path)
        if isinstance(p, BNode):
            inv = self.g.value(p, SH.inversePath)
            return "^" + kort(inv) if inv is not None else "?"
        return kort(p)

    def eigenschap(self, ps) -> Eigenschap:
        g = self.g
        mn, mx = g.value(ps, SH.minCount), g.value(ps, SH.maxCount)
        qv = g.value(ps, SH.qualifiedValueShape)
        if qv is not None:
            mn, mx = g.value(ps, SH.qualifiedMinCount), g.value(ps, SH.qualifiedMaxCount)
        delen, doel = [], None
        if (k := g.value(ps, SH["class"])) is not None:
            delen.append(f"→ {kort(k)}"); doel = str(k)
        if (n := g.value(ps, SH.node)) is not None:
            if self.is_datatype_shape(n):
                dt = g.value(n, SH.datatype)
                talen = _lijst(g, g.value(n, SH.languageIn))
                delen.append(kort(dt) + (" @" + ",".join(map(str, talen)) if talen else ""))
            else:
                doel = self.klasse_van_shape(n)
                delen.append(f"→ {kort(doel) if doel else kort(n)}")
        if qv is not None:
            doel = self.klasse_van_shape(qv)
            delen.append(f"→ {kort(doel)} (gekwalificeerd)")
        if (dt := g.value(ps, SH.datatype)) is not None:
            delen.append(kort(dt))
        if (nk := g.value(ps, SH.nodeKind)) is not None:
            delen.append(lokaal(nk))
        if (inn := g.value(ps, SH["in"])) is not None:
            delen.append(" · ".join(_waarde(v) for v in _lijst(g, inn)))
        if (hv := g.value(ps, SH.hasValue)) is not None:
            delen.append(f"= {_waarde(hv)}")
        if (pat := g.value(ps, SH.pattern)) is not None:
            delen.append(f"patroon {pat}")
            if doel is None:
                doel = next((k for pre, k in PATROON_KLASSE if str(pat).startswith(pre)), None)
        for p, teken in ((SH.minInclusive, "≥"), (SH.minLength, "lengte ≥")):
            if (v := g.value(ps, p)) is not None:
                delen.append(f"{teken} {v}")
        if (lt := g.value(ps, SH.lessThan)) is not None:
            delen.append(f"< {kort(lt)}")
        groep = g.value(ps, SH.group)
        uitleg = _lit(g, ps, SH.message) or _lit(self.vocab, g.value(ps, SH.path), RDFS.comment)
        return Eigenschap(self.pad(ps), aantal(mn, mx), "; ".join(delen) or "–", uitleg,
                          lokaal(groep) if groep is not None else "", doel)

    def logica(self, shape) -> list[str]:
        noten = []
        for p, woord in ((SH["or"], "minstens één van"), (SH.xone, "precies één van")):
            if (lijst := self.g.value(shape, p)) is None:
                continue
            delen = []
            for lid in _lijst(self.g, lijst):
                eisen = []
                for ps in list(self.g.objects(lid, SH.property)) + ([lid] if (lid, SH.path, None) in self.g else []):
                    eisen.append(_eis(self.eigenschap(ps)))
                delen.append(" en ".join(eisen))
            noten.append(f"{woord.capitalize()}: " + " | ".join(f"({d})" for d in delen) + ".")
        for sq in sorted(self.g.objects(shape, SH.sparql), key=lambda q: _lit(self.g, q, SH.message)):
            ernst = "Waarschuwing" if (shape, SH.severity, SH.Warning) in self.g else "Fout"
            noten.append(f"{ernst} (SPARQL-regel) als: “{_lit(self.g, sq, SH.message)}”")
        return noten


def _eis(e: Eigenschap) -> str:
    """Eén eis binnen sh:or/sh:xone, leesbaar: `x = v`, `geen x`, `x aanwezig`."""
    if e.soort.startswith("= "):
        return f"{e.pad} {e.soort}"
    if e.aantal == "0":
        return f"geen {e.pad}"
    return f"{e.pad} aanwezig" if e.aantal.startswith("1") else f"{e.pad} {e.aantal}"


def _is_klasse(r: str) -> bool:
    return not r.startswith(str(XSD)) and not r.endswith("langString")


def _samen(x: Eigenschap, e: Eigenschap) -> Eigenschap:
    """Twee shapes op hetzelfde pad (een gekwalificeerde en een maximum) worden één regel."""
    soort = "; ".join(dict.fromkeys(s for s in (x.soort, e.soort) if s != "–")) or "–"
    return Eigenschap(x.pad, x.aantal if x.aantal != "0..n" else e.aantal, soort, x.uitleg or e.uitleg,
                      x.groep or e.groep, x.doel or e.doel)


class Model:
    """De klassen van één ontologie, uit haar vocabulaire en haar shapes."""

    def __init__(self, o: Ontologie):
        self.o = o
        self.vocab = graaf(*o.vocab) if o.vocab else (bwb_tbox(None) if o.sleutel == "bwb" else Graph())
        self.shapes = graaf(*o.shapes) if o.shapes else Graph()
        self.sh = Shapes(self.shapes, self.vocab, o.naamgeving)
        self.klassen: dict[str, Klasse] = {}
        for c in sorted(set(self.vocab.subjects(RDF.type, OWL.Class))):
            if str(c).startswith(o.namespace):
                self.klasse(str(c))
        for shape in self._node_shapes():
            self._lees_shape(shape)
        self._lees_vocab()
        for k in self.klassen.values():
            k.eigenschappen.sort(key=lambda e: (e.aantal == "", not e.aantal.startswith("1"), e.pad))

    def klasse(self, iri: str) -> Klasse:
        if iri not in self.klassen:
            u = URIRef(iri)
            self.klassen[iri] = Klasse(iri, _lit(self.vocab, u, RDFS.label), _lit(self.vocab, u, RDFS.comment),
                                       sorted(str(s) for s in self.vocab.objects(u, RDFS.subClassOf)))
        return self.klassen[iri]

    def _node_shapes(self) -> list:
        g = self.shapes
        kandidaten = set(g.subjects(RDF.type, SH.NodeShape)) | set(g.objects(None, SH.node)) | \
            set(g.objects(None, SH.qualifiedValueShape))
        return sorted((s for s in kandidaten if not self.sh.is_datatype_shape(s)), key=str)

    def _doelklasse(self, shape) -> tuple[str | None, list[str]]:
        """Op welke klasse een shape valt; bij meer doelklassen hun gedeelde superklasse."""
        doelen = sorted(str(t) for t in self.shapes.objects(shape, SH.targetClass))
        if len(doelen) > 1:
            gedeeld = set.intersection(*(set(map(str, self.vocab.objects(URIRef(d), RDFS.subClassOf)))
                                         for d in doelen))
            return (sorted(gedeeld)[0] if gedeeld else doelen[0]), doelen
        if (obj := self.shapes.value(shape, SH.targetObjectsOf)) is not None:
            rng = self.vocab.value(obj, RDFS.range)
            return (str(rng) if rng is not None else None), []
        return self.sh.klasse_van_shape(shape), []

    def _lees_shape(self, shape) -> None:
        iri, geldt_voor = self._doelklasse(shape)
        if iri is None:
            return
        k = self.klasse(iri)
        k.geldt_voor = sorted(set(k.geldt_voor) | set(geldt_voor))
        for ps in sorted(self.shapes.objects(shape, SH.property), key=self.sh.pad):
            e = self.sh.eigenschap(ps)
            if any(x.pad == e.pad for x in k.eigenschappen):
                k.eigenschappen = [_samen(x, e) if x.pad == e.pad else x for x in k.eigenschappen]
            else:
                k.eigenschappen.append(e)
        k.noten.extend(n for n in self.sh.logica(shape) if n not in k.noten)

    def _lees_vocab(self) -> None:
        """Eigenschappen met een domein in het vocabulaire die de shapes niet noemen (zonder eis)."""
        for p in sorted(set(self.vocab.subjects(SCHEMA.domainIncludes, None))):
            bereik = sorted(str(r) for r in self.vocab.objects(p, SCHEMA.rangeIncludes))
            doel = next((r for r in bereik if _is_klasse(r)), None)
            soort = ", ".join(("→ " if _is_klasse(r) else "") + kort(r) for r in bereik) or "–"
            for d in self.vocab.objects(p, SCHEMA.domainIncludes):
                k = self.klasse(str(d))
                if not any(e.pad == kort(p) for e in k.eigenschappen):
                    k.eigenschappen.append(Eigenschap(kort(p), "", soort, _lit(self.vocab, p, RDFS.comment), "", doel))


def bouw_model(o: Ontologie) -> tuple[dict[str, Klasse], Graph, Graph]:
    m = Model(o)
    return m.klassen, m.vocab, m.shapes


# ---------------------------------------------------------------------------------------------------- de toets

#: Namespaces van buiten waarnaar een vocabulaire mag verwijzen zonder ze zelf te declareren.
BEKEND_EXTERN = ("http://data.europa.eu/eli/ontology#", "http://xmlns.com/foaf/0.1/", "http://www.w3.org/ns/oa#",  # NOSONAR: namespace-id, geen verbinding
                 "http://www.w3.org/2004/02/skos/core#", "http://purl.org/dc/terms/", "http://www.w3.org/ns/prov#",
                 str(XSD), str(RDF), str(RDFS), str(OWL), "urn:bwb-ns:", "urn:jas-ns:")
LETTERLIJK = (str(XSD), str(RDF.langString), str(RDF.HTML))
FOUT, WAARSCHUWING = "fout", "waarschuwing"


def _bereik(vocab: Graph, p) -> set[str]:
    return {str(r) for r in vocab.objects(p, RDFS.range)} | {str(r) for r in vocab.objects(p, SCHEMA.rangeIncludes)}


def _toets_termen(o: Ontologie, vocab: Graph, gedeclareerd: set) -> list[tuple[str, str]]:
    """Elke eigen term een label en uitleg; elke verwijzing naar een gedeclareerde of bekende term."""
    uit = []
    for t in sorted((t for t in gedeclareerd if str(t).startswith(o.namespace)), key=str):
        if not any(isinstance(lab, Literal) and lab.language == "nl" for lab in vocab.objects(t, RDFS.label)):
            uit.append((FOUT, f"`{kort(t)}` heeft geen `rdfs:label` in het Nederlands"))
        if not list(vocab.objects(t, RDFS.comment)):
            uit.append((WAARSCHUWING, f"`{kort(t)}` heeft geen uitleg (`rdfs:comment`)"))
        if (t, RDF.type, OWL.ObjectProperty) in vocab and (t, RDF.type, OWL.DatatypeProperty) in vocab:
            uit.append((FOUT, f"`{kort(t)}` is zowel object- als datatype-eigenschap"))
    for p in (RDFS.subClassOf, RDFS.subPropertyOf, RDFS.range, RDFS.domain, SCHEMA.domainIncludes, SCHEMA.rangeIncludes):
        for s, doel in sorted(vocab.subject_objects(p), key=str):
            d = str(doel)
            if d.startswith(o.namespace) and doel not in gedeclareerd:
                uit.append((FOUT, f"`{kort(s)}` {kort(p)} `{kort(doel)}`: die term is niet gedeclareerd"))
            elif not d.startswith(o.namespace) and not d.startswith(BEKEND_EXTERN):
                uit.append((WAARSCHUWING, f"`{kort(s)}` {kort(p)} `{d}`: onbekende externe term"))
    return uit


def _toets_eigenschap(o: Ontologie, vocab: Graph, shapes: Graph, ps, gedeclareerd: set) -> list[tuple[str, str]]:
    uit, pad = [], shapes.value(ps, SH.path)
    naam = kort(pad) if isinstance(pad, URIRef) else "(pad)"
    mn, mx = shapes.value(ps, SH.minCount), shapes.value(ps, SH.maxCount)
    if mn is not None and mx is not None and int(mn) > int(mx):
        uit.append((FOUT, f"`{naam}`: minCount {mn} is groter dan maxCount {mx}"))
    dt, klasse = shapes.value(ps, SH.datatype), shapes.value(ps, SH["class"])
    if dt is not None and not str(dt).startswith(LETTERLIJK):
        uit.append((FOUT, f"`{naam}`: datatype `{kort(dt)}` is geen XSD- of RDF-datatype"))
    if (inn := shapes.value(ps, SH["in"])) is not None and (inn, RDF.first, None) not in shapes and inn != RDF.nil:
        uit.append((FOUT, f"`{naam}`: `sh:in` is geen lijst"))
    if klasse is not None and str(klasse).startswith(o.namespace) and len(vocab) and klasse not in gedeclareerd:
        uit.append((FOUT, f"`{naam}`: `sh:class {kort(klasse)}` is niet gedeclareerd"))
    if not isinstance(pad, URIRef) or not str(pad).startswith(o.namespace) or not len(vocab):
        return uit
    if pad not in gedeclareerd:
        return uit + [(FOUT, f"`{naam}` staat in de shapes maar niet in het vocabulaire")]
    bereik = _bereik(vocab, pad)
    if dt is not None and (pad, RDF.type, OWL.ObjectProperty) in vocab:
        uit.append((FOUT, f"`{naam}`: de shape eist een datatype, het vocabulaire zegt objecteigenschap"))
    if klasse is not None and (pad, RDF.type, OWL.DatatypeProperty) in vocab:
        uit.append((FOUT, f"`{naam}`: de shape eist een klasse, het vocabulaire zegt datatype-eigenschap"))
    if dt is not None and bereik and str(dt) not in bereik:
        uit.append((WAARSCHUWING, f"`{naam}`: datatype `{kort(dt)}` in de shape, bereik "
                                  + ", ".join(f"`{kort(b)}`" for b in sorted(bereik)) + " in het vocabulaire"))
    return uit


def toets(o: Ontologie) -> list[tuple[str, str]]:
    """De kwaliteitstoets van één ontologie: termen, shapes tegen het vocabulaire, en de shapes zelf."""
    m = Model(o)
    vocab, shapes = m.vocab, m.shapes
    gedeclareerd = set(vocab.subjects(RDF.type, OWL.Class)) | set(vocab.subjects(RDF.type, OWL.ObjectProperty)) | \
        set(vocab.subjects(RDF.type, OWL.DatatypeProperty)) | \
        {s for s in vocab.subjects(RDFS.label, None) if isinstance(s, URIRef) and str(s).startswith(o.namespace)}
    uit = _toets_termen(o, vocab, gedeclareerd) if len(vocab) else []
    for ps in sorted(set(shapes.subjects(SH.path, None)), key=str):
        uit += _toets_eigenschap(o, vocab, shapes, ps, gedeclareerd)
    for c in sorted(set(shapes.objects(None, SH.targetClass)), key=str):
        if str(c).startswith(o.namespace) and len(vocab) and c not in gedeclareerd:
            uit.append((FOUT, f"doelklasse `{kort(c)}` is niet gedeclareerd"))
    if len(vocab) and len(shapes):
        in_shapes = {p for p in shapes.objects(None, SH.path) if isinstance(p, URIRef)}
        zonder = sorted(kort(p) for p in gedeclareerd if str(p).startswith(o.namespace)
                        and (p, RDF.type, OWL.Class) not in vocab and p not in in_shapes)
        if zonder:
            uit.append((WAARSCHUWING, f"{len(zonder)} eigenschappen zonder eis in de shapes (alleen in het vocabulaire): "
                                      + ", ".join(f"`{z}`" for z in zonder)))
    return sorted(set(uit), key=lambda x: (x[0] != FOUT, x[1]))


# ---------------------------------------------------------------------------------------------------- het diagram

def toon(o: Ontologie, pad: str) -> str:
    """Een pad in het diagram: zonder het eigen voorvoegsel, anders mét (rdfs:label is niet bwb:label)."""
    pad = pad.lstrip("^")
    eigen = PREFIXEN.get(o.namespace, "") + ":"
    # Een dubbele punt in een member of label breekt Mermaid; U+2236 (∶) ziet er hetzelfde uit.
    return (pad[len(eigen):] if pad.startswith(eigen) else pad).replace(":", "\u2236")


def mid(iri: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", kort(iri))


def erfdiagram(klassen: dict[str, Klasse]) -> str | None:
    """Alleen de klassenhiërarchie (met de externe superklassen), als die meer is dan een paar lijnen."""
    lijnen = [(s, k.iri) for k in klassen.values() for s in k.supers]
    if len(lijnen) < 4:
        return None
    regels = [THEMA + "classDiagram", "  direction BT"]
    for iri in sorted({x for paar in lijnen for x in paar}):
        regels.append(f'  class {mid(iri)}["{kort(iri)}"]')
    regels += [f"  {mid(s)} <|-- {mid(k)}" for s, k in lijnen]
    return "\n".join(regels)


def mermaid(o: Ontologie, klassen: dict[str, Klasse], met_erf: bool) -> str:
    """De klassen met hun eigenschappen en relaties. Staat de hiërarchie in een eigen diagram, dan blijven klassen
    zonder eigen eigenschappen hier weg en tekent het alleen erfelijkheid tussen klassen die er al staan."""
    regels = [THEMA + "classDiagram", "  direction TB"]
    doelen = {e.doel for k in klassen.values() for e in k.eigenschappen if e.doel and e.aantal != "0"}
    toon_k = [k for k in klassen.values() if not met_erf or k.eigenschappen or k.iri in doelen]
    knopen: set[str] = set()

    def knoop(iri: str):
        if iri not in knopen:
            knopen.add(iri)
            regels.append(f'  class {mid(iri)}["{kort(iri)}"]')

    for k in toon_k:
        knoop(k.iri)
        for e in k.eigenschappen:
            if e.doel is None and e.aantal != "0":
                regels.append(f"  {mid(k.iri)} : {toon(o, e.pad)} {e.aantal}".rstrip())
    namen = {k.iri for k in toon_k}
    for k in toon_k:
        for s in k.supers:
            if met_erf and s not in namen:
                continue
            knoop(s)
            regels.append(f"  {mid(s)} <|-- {mid(k.iri)}")
        for e in k.eigenschappen:
            if e.doel and e.aantal != "0":
                knoop(e.doel)
                regels.append(f"  {mid(k.iri)} --> {mid(e.doel)} : {toon(o, e.pad)} {e.aantal}".rstrip())
    return "\n".join(regels)


# ---------------------------------------------------------------------------------------------------- het document

def blokken(versies: dict) -> list[tuple]:
    """Het document als blokken, zodat Markdown en HTML dezelfde inhoud hebben."""
    b: list[tuple] = [
        ("h1", "Ontologie van de kennisgraaf"),
        ("p", f"Gegenereerd door `{SCRIPT}` uit de T-Box, de SHACL-shapes en de vocabulaires; niet met de hand "
              "bewerken. Wat er in de kennisgraaf staat, in welke named graph, met welke klassen en eigenschappen, en "
              "wat daarvan formeel is vastgelegd. De wettekst is het fundament; annotaties, begrippen en regels wijzen "
              "er met een IRI naar en schrijven er nooit in."),
        ("table", ["Ontologie", "Namespace", "Versie"],
         [[o.titel, f"`{o.namespace}`", versies[o.sleutel]["versie"]] for o in ONTOLOGIEEN]),
        ("p", "Het **aantal** in de tabellen komt uit de shapes: `1` is verplicht, `0..1` optioneel en enkelvoudig, "
              "`0..n` optioneel en meervoudig, `0` verboden. Een lege cel betekent dat alleen het vocabulaire de "
              "eigenschap noemt, zonder eis. Een pijl (→) wijst naar een klasse."),
        ("h2", "Named graphs", "graphs", "lint"),
        ("p", "Elke soort inhoud staat in een eigen named graph. De pijlen zijn verwijzingen: een annotatie, begrip of "
              "regel noemt een bepaling als object van een triple, nooit als subject."),
        ("mermaid", GRAPH_DIAGRAM),
        ("table", ["Named graph", "Inhoud", "Schrijver"], [[f"`{iri}`", inh, wie] for _, iri, inh, wie, _, _ in NAMED_GRAPHS]),
    ]
    for o in ONTOLOGIEEN:
        klassen, vocab, _ = bouw_model(o)
        b += [("h2", o.titel, o.sleutel, o.kleur), ("p", o.inleiding),
              ("table", ["Vastgelegd", "Waar"], [[a, w] for a, w in o.formeel]),
              ]
        erf = erfdiagram(klassen)
        if erf:
            b += [("h3", "Klassenhiërarchie"), ("mermaid", erf)]
        b += [("h3", "Klassendiagram"), ("mermaid", mermaid(o, klassen, met_erf=bool(erf)))]
        if o.sleutel == "jas":
            voc = graaf("api/app/vocabulaire/jas-vocabulaire.ttl")
            namen = sorted(_lit(voc, k, URIRef("http://www.w3.org/2004/02/skos/core#prefLabel"))
                           for k in voc.subjects(RDF.type, URIRef("urn:jas-ns:Klasse")))
            soorten = sorted({kort(t) for t in voc.objects(None, RDF.type) if str(t).startswith("urn:jas-ns:")})
            b.append(("p", f"**De vocabulaire** (`urn:jas:graph:vocabulaire`) bevat de dertien klassen ({', '.join(namen)}) "
                           f"als `skos:Concept`, met de typen {', '.join(f'`{s}`' for s in soorten)}."))
        b.append(("h3", "Klassen"))
        kaarten = []
        for k in sorted(klassen.values(), key=lambda k: (not k.iri.startswith(o.namespace), kort(k.iri))):
            if not k.eigenschappen and not k.noten:
                continue
            noot = " ".join(filter(None, [
                k.uitleg,
                ("Subklasse van " + ", ".join(f"`{kort(s)}`" for s in k.supers) + ".") if k.supers else "",
                ("Geldt voor " + ", ".join(f"`{kort(c)}`" for c in k.geldt_voor) + ".") if k.geldt_voor else "",
                *k.noten]))
            groep = any(e.groep for e in k.eigenschappen)
            kop = ["eigenschap", "aantal", "soort"] + (["groep"] if groep else []) + ["uitleg"]
            rijen = [[f"`{e.pad}`", e.aantal, e.soort] + ([e.groep] if groep else []) + [e.uitleg]
                     for e in k.eigenschappen]
            label = k.label if k.label.lower() != lokaal(k.iri).lower() else ""
            kaarten.append((kort(k.iri), label, noot, kop, rijen))
        b.append(("kaarten", kaarten, o.kleur))
        bevindingen = toets(o)
        b.append(("h3", "Kwaliteitstoets"))
        b.append(("table", ["ernst", "bevinding"], [[e, t] for e, t in bevindingen]) if bevindingen else
                 ("p", "Geen bevindingen."))
        if o.sleutel == "bwb":
            rijen = []
            for p in sorted(set(vocab.subjects(RDF.type, OWL.ObjectProperty)) | set(vocab.subjects(RDF.type, OWL.DatatypeProperty))):
                soort = "object" if (p, RDF.type, OWL.ObjectProperty) in vocab else "datatype"
                rng = vocab.value(p, RDFS.range)
                sup = ", ".join(f"`{kort(s)}`" for s in sorted(vocab.objects(p, RDFS.subPropertyOf)))
                rijen.append([f"`{kort(p)}`", soort, f"`{kort(rng)}`" if rng is not None else "", sup,
                              _lit(vocab, p, RDFS.comment)])
            b += [("h3", "Alle eigenschappen van de T-Box"),
                  ("table", ["eigenschap", "soort", "bereik", "ELI", "uitleg"], rijen)]
    b += [
        ("h2", "Wat formeel is vastgelegd", "formeel", "muted"),
        ("table", ["Ontologie", "T-Box", "SHACL", "Wanneer getoetst"], [
            ["Wettekst", "ja, met ELI", "ja", "blokkerend, per graph vóór de PUT"],
            ["JAS-annotaties", "nee, bewust", "ja", "diagnostisch: tests, CI, graafcontrole"],
            ["Begrippen en regels", "alleen documentatie", "ja (NL-SBB + eigen)", "diagnostisch: conformiteit"],
            ["Kennisgroepen", "alleen documentatie", "nee", "alleen de importpoort (volledig, niet krimpen)"]]),
        ("p", "**Waarom de documentatievocabulaires niet in de graaf staan.** De repository draait met "
              "`rdfsplus-optimized`. Een `rdfs:domain` of `rdfs:range` in de graaf laat GraphDB triples afleiden, en een "
              "range op een property naar een wetsnode zou een triple met de wet als subject opleveren. Daarom gebruiken "
              "`wa-vocabulaire.ttl` en `kg-vocabulaire.ttl` `schema:domainIncludes` en `schema:rangeIncludes`, en worden "
              "ze nergens geladen. De check bewaakt dat ze geen `rdfs:domain` of `rdfs:range` krijgen."),
        ("p", "**Wat de shapes niet zeggen.** Geen shape toetst of een markering, begrip of regel juridisch klopt. Dat "
              "blijft het oordeel van de jurist."),
        ("p", "Wijzigingen per versie: `docs/ontologie/CHANGELOG.md`."),
    ]
    return b


# ---------------------------------------------------------------------------------------------------- weergave

def md_inline(t: str) -> str:
    return t.replace("|", "\\|").replace("\n", " ")


def naar_markdown(b: list[tuple]) -> str:
    uit = [f"<!-- GEGENEREERD door {SCRIPT}; niet met de hand bewerken. -->", ""]
    for blok in b:
        soort = blok[0]
        if soort == "h1":
            uit += [f"# {blok[1]}", ""]
        elif soort in ("h2", "h3"):
            uit += [("## " if soort == "h2" else "### ") + blok[1], ""]
        elif soort == "p":
            uit += [blok[1], ""]
        elif soort == "mermaid":
            uit += ["```mermaid", blok[1], "```", ""]
        elif soort == "table":
            uit += ["| " + " | ".join(blok[1]) + " |", "|" + "---|" * len(blok[1])]
            uit += ["| " + " | ".join(md_inline(str(c)) for c in r) + " |" for r in blok[2]] + [""]
        elif soort == "kaarten":
            for naam, label, noot, kop, rijen in blok[1]:
                uit += [f"#### `{naam}`" + (f" ({label})" if label else ""), ""]
                if noot:
                    uit += [noot, ""]
                uit += ["| " + " | ".join(kop) + " |", "|" + "---|" * len(kop)]
                uit += ["| " + " | ".join(md_inline(str(c)) for c in r) + " |" for r in rijen] + [""]
    return "\n".join(uit).rstrip() + "\n"


def h_inline(t: str) -> str:
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    return re.sub(r"(?<![\w*])\*([^*]+)\*(?![\w*])", r"<em>\1</em>", t)


def h_tabel(kop, rijen, klasse="") -> str:
    th = "".join(f"<th>{html.escape(k)}</th>" for k in kop)
    tr = "".join("<tr>" + "".join(
        f'<td class="{"k" if kop[i] == "aantal" else ""}">' +
        (f'<span class="pill{" must" if str(c).startswith("1") else " nooit" if str(c) == "0" else ""}">{html.escape(str(c))}</span>'
         if kop[i] == "aantal" and c else h_inline(str(c))) + "</td>" for i, c in enumerate(r)) + "</tr>" for r in rijen)
    return f'<div class="tw{klasse}"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


#: De huisstijl van de Lex-app (`frontend/app/globals.css`): Fira, lintblauw, de lichte vlakken, zachte schaduw en kaarten
#: van 14px. De app heeft (nog) geen donkere modus; deze pagina wel, met het merk in zijn donkere stand.
CSS = """:root{--paper:#fff;--surface:#F5F6F8;--surface-2:#EDF0F4;--ink:#1A1A1A;--lint:#154273;--muted:#4A5A6E;
--faint:#5F6A78;--line:#D1D6DD;--link:#01689B;--bwb:#154273;--jas:#8E4600;--wa:#2C6608;--kg:#4A5A6E;
--tint:rgb(21 66 115/.09);--tint-tekst:#154273;--rood-bg:#FBE7E5;--rood:#B0261A;--fig:#fff;
--merk-vlak:#154273;--merk-vorm:#fff;--merk-markering:#FFD84D;
--schaduw:0 1px 2px rgb(21 66 115/.06),0 1px 3px rgb(21 66 115/.05);
--f:"Fira Sans",system-ui,sans-serif;--m:"Fira Mono",ui-monospace,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#0F1B2A;--surface:#152335;--surface-2:#1B2C42;
--ink:#E8EFF7;--lint:#9CC3EC;--muted:#A9B7C8;--faint:#93A3B6;--line:#2A3D55;--link:#7DB9E8;--bwb:#9CC3EC;--jas:#E7A95A;
--wa:#8FCB6E;--kg:#A9B7C8;--tint:rgb(156 195 236/.14);--tint-tekst:#C7DDF4;--rood-bg:#3A1C1A;--rood:#F19A90;
--merk-vlak:transparent;--merk-vorm:#E8EFF7;--schaduw:none;color-scheme:dark}}
:root[data-theme="dark"]{--paper:#0F1B2A;--surface:#152335;--surface-2:#1B2C42;--ink:#E8EFF7;--lint:#9CC3EC;--muted:#A9B7C8;
--faint:#93A3B6;--line:#2A3D55;--link:#7DB9E8;--bwb:#9CC3EC;--jas:#E7A95A;--wa:#8FCB6E;--kg:#A9B7C8;--tint:rgb(156 195 236/.14);
--tint-tekst:#C7DDF4;--rood-bg:#3A1C1A;--rood:#F19A90;--merk-vlak:transparent;--merk-vorm:#E8EFF7;--schaduw:none;color-scheme:dark}
*{box-sizing:border-box}body{background:var(--paper);color:var(--ink);font:16px/1.6 var(--f);margin:0;-webkit-font-smoothing:antialiased}
a{color:var(--link)}::selection{background:rgb(21 66 115/.16)}
.wrap{max-width:1120px;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.balk{border-bottom:1px solid var(--line);background:var(--paper)}
.balk .wrap{display:flex;align-items:center;justify-content:space-between;gap:16px;padding-block:12px}
.logo{display:flex;align-items:center;gap:10px;line-height:1.2}.logo svg{width:32px;height:32px;flex:none}
.logo b{display:block;font-weight:600;font-size:1.125rem;color:var(--lint)}.logo small{display:block;font-size:.75rem;color:var(--muted)}
.balk .waar{font-size:.8125rem;color:var(--muted)}
.kop{background:var(--surface);border-bottom:1px solid var(--line)}.kop .wrap{padding-block:28px 24px}
h1,h2,h3{color:var(--lint);letter-spacing:-.01em;text-wrap:balance}
h1{font:600 clamp(1.75rem,4vw,2.25rem)/1.15 var(--f);margin:0 0 10px}
h2{font:600 1.5rem/1.2 var(--f);margin:48px 0 8px;display:flex;align-items:center;gap:10px;scroll-margin-top:64px}
h2 .dot{width:12px;height:12px;border-radius:3px}h3{font:600 1.0625rem/1.3 var(--f);margin:28px 0 8px}
main{padding-bottom:64px}p{max-width:76ch;font-size:.9375rem}
code{font:.84em var(--m);background:var(--surface-2);padding:.05em .35em;border-radius:4px;overflow-wrap:anywhere}
nav{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--paper);border-bottom:1px solid var(--line)}
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);z-index:10;background:var(--paper)}
nav .wrap{padding-block:10px;display:flex;gap:6px;overflow-x:auto;scrollbar-width:none}
nav a{flex:none;text-decoration:none;color:var(--ink);font-size:.8125rem;padding:5px 12px;border-radius:10px;border:1px solid var(--line);
background:var(--paper);box-shadow:var(--schaduw);display:inline-flex;align-items:center;gap:6px}
nav a:hover,nav a:focus-visible{border-color:var(--lint);outline:none}
.dot{width:9px;height:9px;border-radius:2px;display:inline-block}
.fig{background:var(--fig);border:1px solid var(--line);border-radius:14px;padding:14px;overflow-x:auto;margin:8px 0;box-shadow:var(--schaduw)}
.fig pre{margin:0;color:#1A1A1A;font:12px/1.4 var(--f);white-space:pre}
.tw{background:var(--paper);border:1px solid var(--line);border-radius:14px;overflow-x:auto;margin:10px 0;box-shadow:var(--schaduw)}
table{border-collapse:collapse;width:100%;font-size:.8125rem}th,td{text-align:left;padding:7px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{font:500 .6875rem/1.2 var(--f);text-transform:uppercase;letter-spacing:.06em;color:var(--muted);background:var(--surface)}
tr:last-child td{border-bottom:0}td.k{white-space:nowrap}
.pill{display:inline-block;font:500 .6875rem/1.6 var(--m);padding:0 8px;border-radius:999px;background:var(--surface-2);color:var(--muted)}
.pill.must{background:var(--tint);color:var(--tint-tekst)}.pill.nooit{background:var(--rood-bg);color:var(--rood)}
.kaarten{display:grid;gap:16px}.kaart{background:var(--paper);border:1px solid var(--line);border-radius:14px;overflow:hidden;min-width:0;box-shadow:var(--schaduw)}
.kaart h4{margin:0;padding:10px 14px;font:600 .9375rem/1.3 var(--f);border-bottom:1px solid var(--line);display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.kaart h4 code{background:none;padding:0;font-size:.875rem;color:var(--ink)}.kaart h4 span{font-weight:400;color:var(--muted);font-size:.8125rem}
.kaart h4::before{content:"";width:9px;height:9px;border-radius:2px;background:var(--kleur)}
.kaart p{font-size:.8125rem;color:var(--muted);margin:8px 14px}.kaart .tw{border:0;border-radius:0;margin:0;box-shadow:none}
.k-bwb{--kleur:var(--bwb)}.k-jas{--kleur:var(--jas)}.k-wa{--kleur:var(--wa)}.k-kg{--kleur:var(--kg)}
@media (max-width:560px){th,td{padding:6px 8px}.balk .waar{display:none}}"""

#: Het beeldmerk van Lex (`frontend/merk/lex-merk.svg`), met de merktokens zodat de donkere stand werkt.
MERK = ('<svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="7" fill="var(--merk-vlak)"/>'
        '<g fill="var(--merk-vorm)"><rect x="6" y="6" width="20" height="4"/><rect x="6" y="14" width="6" height="4"/>'
        '<rect x="6" y="22" width="14" height="4"/></g><rect x="16" y="14" width="10" height="4" fill="var(--merk-markering)"/></svg>')


def naar_html(b: list[tuple]) -> str:
    nav = "".join(f'<a href="#{blk[2]}"><span class="dot" style="background:var(--{blk[3]})"></span>{html.escape(blk[1])}</a>'
                  for blk in b if blk[0] == "h2")
    delen, kop_klaar = [], False
    for blk in b:
        soort = blk[0]
        if soort == "h1":
            delen.append(f'<header class="balk"><div class="wrap"><span class="logo">{MERK}<span><b>Lex</b>'
                         '<small>Juridische analyse met AI</small></span></span><span class="waar">Kennisgraaf · referentie'
                         f'</span></div></header><div class="kop"><div class="wrap"><h1>{html.escape(blk[1])}</h1>')
        elif soort == "h2":
            if not kop_klaar:
                delen.append(f'</div></div><nav aria-label="Inhoud"><div class="wrap">{nav}</div></nav><main class="wrap">')
                kop_klaar = True
            delen.append(f'<h2 id="{blk[2]}"><span class="dot" style="background:var(--{blk[3]})"></span>{html.escape(blk[1])}</h2>')
        elif soort == "h3":
            delen.append(f"<h3>{html.escape(blk[1])}</h3>")
        elif soort == "p":
            delen.append(f"<p>{h_inline(blk[1])}</p>")
        elif soort == "mermaid":
            delen.append(f'<div class="fig"><pre class="mermaid">{html.escape(blk[1], quote=False)}</pre></div>')
        elif soort == "table":
            delen.append(h_tabel(blk[1], blk[2]))
        elif soort == "kaarten":
            kaarten = []
            for naam, label, noot, kop, rijen in blk[1]:
                kaarten.append(f'<div class="kaart k-{blk[2]}"><h4><code>{html.escape(naam)}</code>'
                               + (f"<span>{html.escape(label)}</span>" if label else "") + "</h4>"
                               + (f"<p>{h_inline(noot)}</p>" if noot else "") + h_tabel(kop, rijen) + "</div>")
            delen.append('<div class="kaarten">' + "".join(kaarten) + "</div>")
    delen.append("</main>")
    # Mermaid verkleint een diagram tot de breedte van de pagina. Op een breed scherm tonen we het op ware grootte (met
    # scrollen), zodat de tekst leesbaar blijft; op een telefoon schaalt het mee met het scherm.
    delen.append("<script>(function(){var mq=window.matchMedia('(min-width: 768px)');function zet(){"
                 "document.querySelectorAll('.fig svg').forEach(function(s){var v=s.viewBox&&s.viewBox.baseVal;"
                 "if(!v||!v.width)return;if(mq.matches){s.style.maxWidth='none';s.style.width=Math.ceil(v.width)+'px'}"
                 "else{s.style.maxWidth='100%';s.style.width='100%'}})}"
                 "new MutationObserver(zet).observe(document.body,{childList:true,subtree:true});"
                 "if(mq.addEventListener)mq.addEventListener('change',zet);zet()})();</script>")
    return ("<title>Ontologie van de kennisgraaf</title>\n"
            '<meta name="claude:viewport-fit-sides" content="cover">\n'
            f"<!-- GEGENEREERD door {SCRIPT}; niet met de hand bewerken. -->\n"
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fira+Sans:wght@400;500;600;700&amp;family=Fira+Mono:wght@400;500&amp;display=swap">\n'
            f"<style>\n{CSS}\n</style>\n" + "\n".join(delen) + "\n")


# ---------------------------------------------------------------------------------------------------- versies en checks

def bronhash(o: Ontologie) -> str:
    if o.sleutel == "bwb":
        tekst = tbox_turtle(None) + lees(o.shapes[0])
    elif o.sleutel == "jas":
        voc = graaf("api/app/vocabulaire/jas-vocabulaire.ttl")
        namen = sorted(str(n) for k in voc.subjects(RDF.type, URIRef("urn:jas-ns:Klasse"))
                       for n in voc.objects(k, URIRef("http://www.w3.org/2004/02/skos/core#prefLabel")))
        tekst = lees(o.shapes[0]) + "\n".join(namen)
    else:
        tekst = "".join(lees(p) for p in o.vocab + o.shapes)
    return hashlib.sha256(tekst.encode("utf-8")).hexdigest()


def controleer_versies(versies: dict, schrijven: bool) -> list[str]:
    fouten = []
    log = CHANGELOG.read_text(encoding="utf-8") if CHANGELOG.exists() else ""
    for o in ONTOLOGIEEN:
        v = versies.setdefault(o.sleutel, {"versie": "1.0.0", "historie": {}})
        h, historie = bronhash(o), v.setdefault("historie", {})
        if historie.get(v["versie"]) not in (None, h):
            fouten.append(f"{o.sleutel}: de bronnen veranderden maar versie {v['versie']} niet; verhoog `versie` in "
                          f"{VERSIES.relative_to(WORTEL)} en noteer het in CHANGELOG.md")
        elif v["versie"] not in historie:
            if schrijven:
                historie[v["versie"]] = h
            else:
                fouten.append(f"{o.sleutel}: versie {v['versie']} staat niet in de historie; draai de generator")
        if not re.search(rf"^## {re.escape(o.sleutel)} {re.escape(v['versie'])}\b", log, re.M):
            fouten.append(f"{o.sleutel}: CHANGELOG.md mist een kop `## {o.sleutel} {v['versie']}`")
    return fouten


def controleer_termen() -> list[str]:
    fouten = []
    gedeclareerd = Graph()
    for p in DOC_VOCABS:
        g = graaf(p)
        for verboden in (RDFS.domain, RDFS.range):
            if (None, verboden, None) in g:
                fouten.append(f"{p}: gebruikt {kort(verboden)}; alleen schema:domainIncludes/rangeIncludes")
        gedeclareerd += g
    namen = {str(s) for s in gedeclareerd.subjects(RDFS.label, None)}
    for pad, patroon, ns in GEBRUIK:
        for term in sorted(set(re.findall(patroon, lees(pad)))):
            if ns + term not in namen:
                fouten.append(f"{pad}: {ns}{term} is niet gedeclareerd (met rdfs:label) in het documentatievocabulaire")
    for _, iri, _, _, pad, teken in NAMED_GRAPHS:
        if teken not in lees(pad):
            fouten.append(f"named graph {iri}: `{teken}` staat niet meer in {pad}")
    return fouten


def genereer(versies: dict) -> dict[Path, str]:
    b = blokken(versies)
    return {TTL_BWB: tbox_turtle(versies["bwb"]["versie"]), README: naar_markdown(b), HTML_: naar_html(b)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--check", action="store_true", help="alleen vergelijken; niets schrijven")
    args = p.parse_args(argv)
    versies = json.loads(VERSIES.read_text(encoding="utf-8")) if VERSIES.exists() else {}
    fouten = controleer_versies(versies, schrijven=not args.check) + controleer_termen() + [
        f"{o.sleutel}: {tekst}" for o in ONTOLOGIEEN for ernst, tekst in toets(o) if ernst == FOUT]
    if fouten:
        print("\n".join(fouten), file=sys.stderr)
        return 1
    bestanden = genereer(versies)
    bestanden[VERSIES] = json.dumps(versies, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    afwijkend = [pad for pad, inhoud in bestanden.items()
                 if not pad.exists() or pad.read_text(encoding="utf-8") != inhoud]
    if args.check:
        if afwijkend:
            print("De ontologiedocumentatie loopt achter: " + ", ".join(str(a.relative_to(WORTEL)) for a in afwijkend)
                  + f". Draai: cd tools/graph-qa && uv run --extra dev python scripts/{Path(__file__).name}",
                  file=sys.stderr)
            return 1
        return 0
    for pad in afwijkend:
        pad.write_text(bestanden[pad], encoding="utf-8")
        print(f"geschreven: {pad.relative_to(WORTEL)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
