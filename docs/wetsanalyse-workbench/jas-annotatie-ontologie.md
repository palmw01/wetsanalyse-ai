# JAS-annotatie-ontologie (de annotatielagen in de kennisgraaf)

De **annotatielaag per bronnode** staat naast de wettekst in GraphDB: elke markering, met haar klasse,
haar lokale ankers, haar levenscyclus en de laag waar ze bij hoort, als eigen nodes. Zo kan Lex
opgeslagen annotaties **doorzoeken** en kan de werkplek een al geannoteerde bepaling hergebruiken,
terwijl elke duiding herleidbaar blijft naar de bronnode en de tekstversie.

> **Dit document beschrijft contract 2 (sinds 22 sep 2026).** De laag hoort bij één canonieke
> bron-IRI – een artikel, een lid, een onderdeel – en niet meer bij een artikel als geheel. De
> specificatie van dat contract staat in
> [`../architectuur/annotatie-bronnodes.md`](../architectuur/annotatie-bronnodes.md); de projectie is
> `api/app/graaf_projectie_v2.py`.
>
> **Het v1-pad is historie.** `api/app/graaf_projectie.py`, `api/app/jas_ontologie.py` en de afdruk
> [`jas-ontologie.ttl`](jas-ontologie.ttl) beschrijven de oude laag per artikel
> (`urn:jas:graph:<bwbId>:artikel:<nr>`). Die wordt onder contract 2 niet meer geschreven; de code en
> de drift-test staan er nog voor het geval een omgeving nog op contract 1 draait.

## Wie schrijft, wie leest

- **Postgres is de waarheid.** De api (`annotatie_v2_lagen`, `annotatie_v2_elementen`) bewaart de laag;
  de graaf is een **projectie** die op elk moment opnieuw op te bouwen is.
- **De api is de enige schrijver** onder `urn:jas:`. Sinds 22 sep 2026 projecteert hij een laag
  **direct na elke geslaagde schrijftransactie** (`graaf_projectie_v2.na_mutatie`, best-effort op de
  achtergrond); de reconcile-lus (`JAS_PROJECTIE_INTERVAL`, standaard 60 s) is het vangnet voor wat
  daarbij misging. Tot die datum was de lus het enige pad, en stond een annotatie dus tot een minuut
  later in de graaf.
- **Lex leest**, en sinds contract 2 ook actief: `search_annotaties`, `get_annotatie` en
  `get_annotatiedekking` lopen via de api (`tools/graph-qa/agent/annotatie_read.py`). De api zoekt de
  kandidaten in de graaf en **verifieert ze daarna tegen Postgres** – een achterlopende projectie mag
  nooit een spookresultaat opleveren, en een storing nooit een leeg succes.
- Verdwijnt een laag uit Postgres, dan ruimt `verwijder_verweesde_projecties` haar graph op, na een
  hercontrole onder het schrijfslot.

GraphDB draait op Azure niet-persistent: een herstart wist ook deze graven. De projector ziet dat aan
de revisies in de graaf zelf en bouwt alle lagen opnieuw op uit Postgres.

> De api draait op `minReplicas: 0`. Staat hij stil, dan gebeurt er ook niets aan de projectie; een
> commit is zelf verkeer, dus in de praktijk haalt de directe projectie het ruim.

## Namespaces en IRI's

```
jas:  <urn:jas-ns:>            vocabulaire
oa:   <http://www.w3.org/ns/oa#>
```

De laag-id en het element-id worden gecodeerd met `quote(s, safe="")`.

| resource | IRI |
|---|---|
| named graph van een laag | `urn:jas:graph:v2:<laag-id>` |
| register | `urn:jas:graph:register:v2` (met `urn:jas:projectieschema:v2` voor de schemaversie) |
| laag | `urn:jas:laag:v2:<laag-id>` |
| markering | `urn:jas:element:<element-id>` |
| doel, positie, citaat, body | blanke nodes binnen de graph van de laag |
| bronnode (de wet) | `urn:bwb:…` – alleen als **object**, nooit als subject |

Van een jurist staat er in de graaf niets: de actor, de beslissingen en het auditspoor blijven in
Postgres. De graaf heeft geen authenticatie, dus hoort daar geen persoonsgegeven in.

## Het model

| node | typen | draagt |
|---|---|---|
| laag | `jas:AnnotatieLaag` | `jas:laagId`, `jas:revisie`, `jas:status`, `jas:schemaVersie` (2), `jas:bepaling` → de bronnode |
| markering | `jas:Markering` | `jas:inLaag` → de laag, `jas:elementId`, `jas:klasseNaam`, `jas:lifecycle`, `jas:verouderd`, `jas:tekst` (het letterlijke fragment), `jas:toelichting`, `oa:hasBody`, `oa:hasTarget` (één per anker) |
| body | `oa:TextualBody` | `rdf:value` – de toelichting van de annotator |
| doel | `oa:SpecificResource` | `oa:hasSource` → de bronnode, `jas:volgorde` (het hoeveelste anker), `jas:bronHash`, `jas:snapshotId`, `oa:hasSelector` |
| positie | `oa:TextPositionSelector` | `oa:start`, `oa:end` – **Unicode-codepunten binnen de eigen tekst van die bronnode**, niet binnen het artikel |
| citaat | `oa:TextQuoteSelector` | `oa:exact` – het letterlijke fragment |

Een element met meerdere ankers draagt meerdere `oa:hasTarget`-nodes, in bronvolgorde; de eigenaar
van de laag is de diepste gezamenlijke voorouder van die ankers.

De klasse staat als **naam** in `jas:klasseNaam` (canoniek uit `api/app/jas_klassen.py`), niet als
SKOS-concept: het v2-schema houdt de projectie opzettelijk plat, omdat de zoektool zijn kandidaten
toch tegen Postgres verifieert.

**Verouderd.** Verandert de wettekst van een bronnode, dan blijven de oude markeringen staan met
`jas:verouderd true`: het oordeel van de jurist is historie, geen afval. Een query naar de actuele
duiding filtert daarop.

## Voorbeeld

```turtle
GRAPH <urn:jas:graph:v2:8d9d3fb6…> {
  <urn:jas:laag:v2:8d9d3fb6…> a jas:AnnotatieLaag ;
      jas:laagId "8d9d3fb6…" ; jas:revisie 8 ; jas:status "geaccordeerd" ; jas:schemaVersie 2 ;
      jas:bepaling <urn:bwb:BWBR0004770:artikel:9:lid:1> .

  <urn:jas:element:867fc7b4166d> a jas:Markering ;
      jas:inLaag <urn:jas:laag:v2:8d9d3fb6…> ;
      jas:elementId "867fc7b4166d" ;
      jas:klasseNaam "Rechtsobject" ;
      jas:lifecycle "human_approved" ; jas:verouderd false ;
      jas:tekst "Een belastingaanslag" ;
      jas:toelichting "De belastingaanslag is het voorwerp van de rechtsbetrekking (invordering)." ;
      oa:hasBody [ a oa:TextualBody ; rdf:value "De belastingaanslag is het voorwerp …" ] ;
      oa:hasTarget [ a oa:SpecificResource ;
          oa:hasSource <urn:bwb:BWBR0004770:artikel:9:lid:1> ;
          jas:volgorde 0 ; jas:bronHash "fd044d7e…" ; jas:snapshotId "2968a6fe…" ;
          oa:hasSelector [ a oa:TextPositionSelector ; oa:start 0 ; oa:end 20 ] ;
          oa:hasSelector [ a oa:TextQuoteSelector ; oa:exact "Een belastingaanslag" ] ] .
}
```

## De wettekst blijft schoon (invarianten, met tests)

Lex bevraagt de union van alle graven (zonder `GRAPH`), de similarity-index pakt elke `urn:bwb-ns:tekst`
en de bronnencontrole telt elke `urn:bwb:`-string als vindplaats. Een annotatie mag daar nergens als
wettekst opduiken. Daarom:

1. **Geen subject onder `urn:bwb:`.** De wet komt alleen als object voor (`oa:hasSource`, `jas:bepaling`).
2. **Geen `urn:bwb-ns:`-predicaat**, dus ook geen `urn:bwb-ns:tekst`: het citaat staat in `oa:exact`
   en `jas:tekst`.
3. **Geen `rdfs:domain`, `rdfs:range`, `subPropertyOf`, `subClassOf` of `owl:sameAs`.** De repository
   draait met `rdfsplus-optimized`, en een range op een property die naar een wet-node wijst laat
   GraphDB triples áfleiden met een `urn:bwb:`-subject.
4. **De OA-ontologie wordt niet geladen** – om dezelfde reden.

Ook aan de antwoordkant blijft het gescheiden: `check_grounding`
(`tools/graph-qa/agent/grounding.py`) laat de resultaten van de annotatietools bewust buiten het
bewijs voor een wetsclaim. Een annotatie is afgeleide duiding en kan een vindplaats niet dragen.

**Herkomst in de graaf (optioneel).** Met `JAS_PROJECTIE_PROV=true` krijgt een element uit de
hybride keten `prov:wasGeneratedBy` een `prov:Activity` met `prov:wasAssociatedWith
<urn:jas:agent:pijplijn:hybrid_v1>`, `jas:beslistDoor` (regel/model/specificiteit), `jas:jasVersie`
en de gebruikte `jas:regel`-id's. Er komen geen personen in (die blijven in Postgres) en geen
domain/range. Standaard staat dit uit; het volledige spoor staat altijd in Postgres (`trace`).

## Structurele validatie (SHACL)

Sinds ADR-001 PR 14 beschrijft `api/app/shapes/jas-v2.ttl` dit model in SHACL. De shapes zijn
verdeeld in twee groepen, en die scheiding is de kern:

- **`jasv:RdfStructuur`**: de projectie is structureel geldige RDF volgens dit model (typen,
  cardinaliteit, datatypes, precies één positie- en één citaatselector, `oa:start < oa:end`).
- **`jasv:JasModel`**: het JAS-model klopt (klasse uit de dertien canonieke namen, geldige
  lifecycle en laagstatus, bron onder `urn:bwb:`, een SHA256-bronhash, en invariant 1 hierboven:
  geen subject onder `urn:bwb:`).

Wat SHACL niet kan zeggen, is of een annotatie **juridisch juist** is. Dat blijft de jurist.

De shapes zijn **niet-blokkerend**: ze draaien in `api/tests/test_shacl.py` (en dus in `poort`)
en via `app/shacl.valideer(graph)` als diagnose, niet in het schrijfpad. `pyshacl` is een
dev-afhankelijkheid; zonder die dependency geeft de diagnose `beschikbaar: false` in plaats van te
falen. Een drift-test houdt de klassen- en lifecycle-lijst in de shapes gelijk aan de api.

## Wie de laag leest

- **De api zelf**, voor `search_annotaties`: `graaf_projectie_v2.zoek_kandidaten` stelt een getypeerde
  SPARQL samen en controleert de treffers daarna tegen Postgres. Meer dan 10.000 kandidaten levert
  expliciet `partial` op in plaats van een stille afkapping.
- **De reconcile-lus**, om te zien welke lagen achterlopen of verdwenen zijn.

graph-qa leest de annotatiegraven **niet** rechtstreeks met SPARQL: zijn leestools lopen via de api,
zodat de verificatie tegen Postgres niet te omzeilen is.

## Buiten scope

- **Begrippen (activiteit 3)** worden hier niet geschreven.
- **Beslissingen, audit en dekking** blijven in Postgres. De graaf draagt de uitkomst (lifecycle,
  laagstatus), niet het spoor ernaartoe.
