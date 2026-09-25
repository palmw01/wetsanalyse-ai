"""Genereer de JAS-vocabulairegraaf en de verklaringen voor de api.

Bron: de dertien klassen (`agent/jas_klassen.py`, zelf gegenereerd uit de skill), de profielen met de
zestien officiële begrippen en hun H2-verwijzingen (`agent/jas_pipeline/profielen/`), de JAS-regels
(`REGELS`), de detectorregels (`agent/jas_pipeline/detectoren/regels/*.yaml`) en de leesbare
verklaringen van alle trace-codes (`agent/jas_pipeline/verklaringen.yaml`).

Doel: `api/app/vocabulaire/jas-vocabulaire.ttl` (de api projecteert hem naar de named graph
`urn:jas:graph:vocabulaire`, zodat een markering naar haar klasse, regels en codes kan wijzen) en
`api/app/vocabulaire/verklaringen.json` (de api serveert hem aan de werkplek en gebruikt hem in de
exports). Twee bestanden in de api, omdat de api geen graph-qa-code importeert.

Invarianten van de annotatiegraaf gelden ook hier: geen subject onder `urn:bwb:`, geen
domain/range/subClassOf/sameAs. De klassen zijn `skos:Concept`s; begrippen hangen met
`skos:broader` onder hun klasse.

    python scripts/genereer_jas_vocabulaire.py           # schrijven
    python scripts/genereer_jas_vocabulaire.py --check   # alleen vergelijken (drift-test)
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import yaml
from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import DCTERMS, SKOS

GRAPH_QA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GRAPH_QA))

from agent.jas_klassen import JAS_KLASSEN, REGELS  # noqa: E402
from agent.jas_pipeline.profielen import laad as laad_profielen  # noqa: E402
from agent.jas_pipeline.verklaringen import SECTIES, laad as laad_verklaringen  # noqa: E402

DOEL = GRAPH_QA.parents[1] / "api" / "app" / "vocabulaire"
TTL, JSON_ = DOEL / "jas-vocabulaire.ttl", DOEL / "verklaringen.json"
REGELMAP = GRAPH_QA / "agent" / "jas_pipeline" / "detectoren" / "regels"
JAS = Namespace("urn:jas-ns:")
JAS_VERSIE = "1.0.10"
SCHEMA = URIRef("urn:jas-ns:schema:jas-" + JAS_VERSIE)
# Per sectie van de verklaringen een eigen IRI-ruimte en type.
SECTIE_IRI = {"detectie": ("code", JAS.Detectiecode), "besluit": ("besluit", JAS.Besluitwijze),
              "twijfel": ("twijfel", JAS.Twijfelreden), "resolutie": ("resolutie", JAS.Resolutieregel),
              "validatie": ("validatie", JAS.Validatiecode), "classifier": ("classifier", JAS.Classifiercode)}


def slug(naam: str) -> str:
    """`Delegatiebevoegdheid en delegatie-invulling` → `DelegatiebevoegdheidEnDelegatieInvulling`.
    Zelfde functie als `api/app/graaf_projectie_v2.klasse_iri`; de api-test bewaakt dat."""
    return "".join(d[:1].upper() + d[1:] for d in re.split(r"[\s\-]+", naam.strip()) if d)


def klasse_iri(naam: str) -> URIRef:
    return URIRef("urn:jas-ns:klasse:" + slug(naam))


def detectorregels() -> list[dict]:
    uit = []
    for f in sorted(REGELMAP.glob("*.yaml")):
        if not f.name.startswith("_"):
            uit += yaml.safe_load(f.read_text(encoding="utf-8")) or []
    return sorted(uit, key=lambda r: r["id"])


def bouw() -> tuple[Graph, dict]:
    g = Graph()
    g.bind("jas", JAS)
    g.bind("skos", SKOS)
    g.bind("dcterms", DCTERMS)
    verklaringen = laad_verklaringen()
    profielen = laad_profielen()

    g.add((SCHEMA, RDF.type, SKOS.ConceptScheme))
    g.add((SCHEMA, SKOS.prefLabel, Literal("Juridisch Analyseschema", lang="nl")))
    g.add((SCHEMA, JAS.jasVersie, Literal(JAS_VERSIE)))
    g.add((SCHEMA, DCTERMS.source, Literal("docs/wetsanalyse/wetsanalyse-rijk/H2-JAS.md")))

    for i, k in enumerate(JAS_KLASSEN):
        iri, p = klasse_iri(k.naam), profielen[k.naam]
        g.add((iri, RDF.type, SKOS.Concept))
        g.add((iri, RDF.type, JAS.Klasse))
        g.add((iri, SKOS.inScheme, SCHEMA))
        g.add((iri, SKOS.topConceptOf, SCHEMA))
        g.add((iri, SKOS.prefLabel, Literal(k.naam, lang="nl")))
        g.add((iri, SKOS.definition, Literal(k.omschrijving, lang="nl")))
        g.add((iri, JAS.herkenningsvraag, Literal(k.vraag, lang="nl")))
        g.add((iri, JAS.uitdrukkingswijze, Literal(k.uitdrukkingswijze, lang="nl")))
        g.add((iri, JAS.volgorde, Literal(i)))
        for veld, bron in sorted(p.bron.items()):
            g.add((iri, DCTERMS.source, Literal(f"{veld} {bron}")))
        for b in p.data.get("begrippen", []):
            begrip = URIRef("urn:jas-ns:begrip:" + slug(b["naam"]))
            g.add((begrip, RDF.type, SKOS.Concept))
            g.add((begrip, RDF.type, JAS.Begrip))
            g.add((begrip, SKOS.inScheme, SCHEMA))
            g.add((begrip, SKOS.prefLabel, Literal(b["naam"], lang="nl")))
            g.add((begrip, SKOS.broader, iri))
            if b.get("subtype"):
                g.add((begrip, JAS.subtype, Literal(b["subtype"])))

    for r in REGELS:
        iri = URIRef("urn:jas-ns:regel:" + r.id)
        g.add((iri, RDF.type, JAS.Methoderegel))
        g.add((iri, SKOS.prefLabel, Literal(r.id)))
        g.add((iri, SKOS.definition, Literal(r.description, lang="nl")))
        g.add((iri, JAS.regelType, Literal(r.type.value)))
        for klasse in r.applies_to:
            g.add((iri, JAS.geldtVoor, klasse_iri(klasse)))

    for r in detectorregels():
        iri = URIRef("urn:jas-ns:regel:" + r["id"])
        g.add((iri, RDF.type, JAS.Detectorregel))
        g.add((iri, SKOS.prefLabel, Literal(verklaringen["detectie"][r["code"]]["naam"], lang="nl")))
        g.add((iri, JAS.code, URIRef("urn:jas-ns:code:" + r["code"])))
        g.add((iri, JAS.regelVersie, Literal(int(r.get("versie", 1)))))
        if r.get("bron"):
            g.add((iri, DCTERMS.source, Literal(r["bron"])))
        for klasse in r["klassen"]:
            g.add((iri, JAS.wijstAan, klasse_iri(klasse)))

    for sectie in SECTIES:
        ruimte, soort = SECTIE_IRI[sectie]
        for code, v in sorted(verklaringen[sectie].items()):
            iri = URIRef(f"urn:jas-ns:{ruimte}:{code}")
            g.add((iri, RDF.type, soort))
            g.add((iri, JAS.codeWaarde, Literal(code)))
            g.add((iri, SKOS.prefLabel, Literal(v["naam"], lang="nl")))
            g.add((iri, SKOS.definition, Literal(v["uitleg"], lang="nl")))

    json_uit = {
        "jas_versie": JAS_VERSIE,
        "klassen": [{"naam": k.naam, "iri": str(klasse_iri(k.naam)), "omschrijving": k.omschrijving,
                     "vraag": k.vraag, "bron": profielen[k.naam].bron,
                     "begrippen": profielen[k.naam].data.get("begrippen", [])} for k in JAS_KLASSEN],
        "regels": {**{r.id: {"naam": r.id, "uitleg": r.description, "soort": "methode"} for r in REGELS},
                   **{r["id"]: {"naam": verklaringen["detectie"][r["code"]]["naam"],
                                "uitleg": verklaringen["detectie"][r["code"]]["uitleg"],
                                "soort": "detector", "code": r["code"], "bron": r.get("bron", "")}
                      for r in detectorregels()}},
        **{s: verklaringen[s] for s in SECTIES},
    }
    inhoud = g.serialize(format="turtle") + json.dumps(json_uit, sort_keys=True, ensure_ascii=False)
    versie = hashlib.sha256(inhoud.encode("utf-8")).hexdigest()[:12]
    g.add((SCHEMA, JAS.vocabulaireVersie, Literal(versie)))
    json_uit["vocabulaire_versie"] = versie
    return g, json_uit


def main(check: bool) -> int:
    g, j = bouw()
    ttl = "# GEGENEREERD door tools/graph-qa/scripts/genereer_jas_vocabulaire.py – niet met de hand bewerken.\n" \
          + g.serialize(format="turtle")
    tekst_json = json.dumps(j, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if check:
        from rdflib.compare import isomorphic
        fout = []
        if not TTL.exists() or not isomorphic(Graph().parse(TTL, format="turtle"), g):
            fout.append(str(TTL))
        if not JSON_.exists() or json.loads(JSON_.read_text(encoding="utf-8")) != j:
            fout.append(str(JSON_))
        if fout:
            print("Verouderd – draai scripts/genereer_jas_vocabulaire.py: " + ", ".join(fout))
            return 1
        print("De vocabulaire komt overeen met de bronnen.")
        return 0
    DOEL.mkdir(parents=True, exist_ok=True)
    TTL.write_text(ttl, encoding="utf-8")
    JSON_.write_text(tekst_json, encoding="utf-8")
    print(f"Geschreven: {TTL} en {JSON_} (vocabulaire_versie {j['vocabulaire_versie']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--check" in sys.argv))
