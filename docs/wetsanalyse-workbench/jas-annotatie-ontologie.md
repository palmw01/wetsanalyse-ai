# JAS-annotatie-ontologie (de annotatielagen in de kennisgraaf)

De **gedeelde annotatielaag per artikel** staat naast de wettekst in GraphDB: elke markering, met haar
klasse, haar plek in de tekst, de Critic-rondes, de oordelen van juristen en de Lex-beurt die haar
voorstelde, als eigen nodes. Zo kan Lex een al geannoteerd artikel **uit de graaf halen** in plaats van
het opnieuw te annoteren, en blijft elke duiding herleidbaar naar artikel, lid en tekstversie.

De vocabulaire zelf staat als Turtle in [`jas-ontologie.ttl`](jas-ontologie.ttl) – een afdruk van
`api/app/jas_ontologie.py`, met een drift-test erop. De projectie is `api/app/graaf_projectie.py`.

## Wie schrijft, wie leest

- **Postgres is de waarheid.** De api (`annotatie_documenten`, rijen met een `laag_sleutel`) bewaart de
  laag; de graaf is een **projectie** die op elk moment opnieuw op te bouwen is.
- **De api is de enige schrijver** onder `urn:jas:`. Na elke mutatie van een laag vervangt hij haar
  named graph (Graph Store `PUT`, idempotent); een reconcile-lus haalt achterstand in.
- **graph-qa leest alleen** – via de bestaande read-only MCP-client, met een expliciete `GRAPH`.

GraphDB draait op Azure niet-persistent: een herstart wist ook deze graven. Het **register**
(`urn:jas:graph:register`) is daarvoor de verklikker: ontbreekt het, dan schrijft de api eerst de
ontologie, dan alle lagen, en het register als laatste. Ontbreekt de repository `inning` zelf, dan wacht
hij op de importer (`jas_projectie_wacht` in de log). Stand opvragen: `GET /v1/admin/annotatie/projectie`;
alles opnieuw: `POST /v1/admin/annotatie/herprojecteer`.

> De api draait op `minReplicas: 0`. Na een GraphDB-herstart komt de laag dus pas terug zodra de api
> weer verkeer krijgt. Annoteert Lex in dat venster opnieuw, dan kost dat tokens maar geen reviewstatus:
> de api negeert voorstellen voor een lid waarvan de hash niet veranderde.

## Namespaces en IRI's

```
jas:  <urn:jas-ns:>            vocabulaire
jask: <urn:jas-ns:klasse:>     de dertien JAS-klassen (skos:Concept)
oa:   <http://www.w3.org/ns/oa#>
prov: <http://www.w3.org/ns/prov#>
```

Segmenten worden gecodeerd zoals de importer dat doet (`quote(s, safe="")`), dus artikel `3:4` wordt
`3%3A4`.

| resource | IRI |
|---|---|
| named graph van een laag | `urn:jas:graph:<bwbId>:artikel:<nr>` |
| register | `urn:jas:graph:register` (subject `urn:jas:register`) |
| ontologie | `urn:jas:graph:ontologie` |
| laag | `urn:jas:laag:<bwbId>:artikel:<nr>` |
| lidstand | `…laag…:lid:<lid>` |
| agent-ronde | `…laag…:run:<index in runs[]>` (append-only, dus stabiel) |
| markering | `urn:jas:annotatie:<bwbId>:artikel:<nr>:<element-id>` |
| onderdelen daarvan | `…:doel`, `…:quote`, `…:positie`, `…:toelichting`, `…:alt:<n>`, `…:critic:<ronde>`, `…:beslissing:<n>` |
| Lex / model / jurist | `urn:jas:agent:lex:<versie>`, `urn:jas:agent:model:<model>`, `urn:jas:agent:mens:<userid>` |

Van een jurist staat alleen de opaque userid in de graaf, nooit naam of e-mail: de graaf heeft geen
authenticatie.

## Het model

| node | typen | draagt |
|---|---|---|
| laag | `jas:AnnotatieLaag` | `jas:bwbId`, `jas:artikel`, `jas:slug`, `jas:bepaling` → artikel-node, `jas:status`, `dcterms:title`, `dcterms:modified`, `jas:heeftLidstand` |
| lidstand | `jas:Lidstand` | `jas:lid`, `jas:lidHash`, `jas:bepaling` → lid-node, `prov:generatedAtTime` |
| markering | `oa:Annotation`, `jas:Markering` | `oa:motivatedBy oa:classifying`, `oa:hasBody` (klasse + toelichting), `jas:klasse`, `oa:hasTarget`, `jas:inLaag`, `jas:elementId`, `jas:lid`, `jas:lifecycle`, `jas:aandacht`, `jas:herkomst`, `jas:gewijzigdDoor`, `jas:verouderd` (+ `prov:invalidatedAtTime`), `prov:wasGeneratedBy`, `prov:wasAttributedTo` |
| doel | `oa:SpecificResource` | `oa:hasSource` → lid-node, `oa:hasSelector` → quote + positie |
| quote | `oa:TextQuoteSelector` | `oa:exact` (het letterlijke citaat), `oa:prefix`, `oa:suffix` |
| positie | `oa:TextPositionSelector` | `oa:start`, `oa:end`, `jas:bronHash`, `jas:lidHash` |
| alternatief | `jas:Alternatief` | `jas:klasse`, `jas:motivatie` |
| Critic-ronde | `jas:CriticRonde`, `prov:Activity` | `jas:ronde`, `jas:aandacht`, `jas:motivatie`, `jas:actie`, `jas:toegepast`, `jas:voorstelKlasse`, `jas:voorstelTekst`, `prov:used`, `prov:endedAtTime` |
| beslissing | `jas:Beslissing`, `prov:Activity` | `jas:beslissingType`, `jas:reviewReden`, `jas:opmerking`, `jas:wijziging` (JSON), `prov:wasAssociatedWith` → jurist, `prov:used`, `prov:endedAtTime` |
| agent-ronde | `jas:AgentRun`, `prov:Activity` | `prov:wasAssociatedWith` → Lex + model, `jas:modus`, `jas:lid`, `jas:promptHash`, `jas:methodeVersie`, `jas:criticRondes`, `jas:stopReden`, `prov:startedAtTime` |

Vaste waarden (lifecycle, aandacht, status, beslissingstype, reden) zijn nodes, geen strings:
`jas:lifecycle-human_approved`, `jas:aandacht-geel`, `jas:beslissing-approve`, … – elk een `skos:Concept`
in een eigen schema, zodat een query zonder tekstvergelijking kan filteren.

**Verouderd.** Verandert de wettekst van een lid, dan blijven de oude markeringen staan met
`jas:verouderd true`: het oordeel van de jurist is historie, geen afval. Een query naar de actuele
duiding filtert daarop.

## Voorbeeld

```turtle
GRAPH <urn:jas:graph:BWBR0004770:artikel:9> {
  <urn:jas:laag:BWBR0004770:artikel:9> a jas:AnnotatieLaag ;
      jas:bwbId "BWBR0004770" ; jas:artikel "9" ;
      jas:bepaling <urn:bwb:BWBR0004770:artikel:9> ;
      jas:status jas:status-in_review ;
      jas:heeftLidstand <urn:jas:laag:BWBR0004770:artikel:9:lid:1> .

  <urn:jas:laag:BWBR0004770:artikel:9:lid:1> a jas:Lidstand ;
      jas:lid "1" ; jas:lidHash "9f3a1c02" ;
      jas:bepaling <urn:bwb:BWBR0004770:artikel:9:lid:1> .

  <urn:jas:annotatie:BWBR0004770:artikel:9:e7k2> a oa:Annotation, jas:Markering ;
      oa:motivatedBy oa:classifying ;
      oa:hasBody jask:rechtssubject ;
      oa:hasTarget <urn:jas:annotatie:BWBR0004770:artikel:9:e7k2:doel> ;
      jas:lifecycle jas:lifecycle-human_approved ; jas:aandacht jas:aandacht-geel ;
      jas:verouderd false ;
      jas:heeftBeslissing <urn:jas:annotatie:BWBR0004770:artikel:9:e7k2:beslissing:1> ;
      prov:wasGeneratedBy <urn:jas:laag:BWBR0004770:artikel:9:run:0> .

  <urn:jas:annotatie:BWBR0004770:artikel:9:e7k2:doel> a oa:SpecificResource ;
      oa:hasSource <urn:bwb:BWBR0004770:artikel:9:lid:1> ;
      oa:hasSelector <urn:jas:annotatie:BWBR0004770:artikel:9:e7k2:quote> ,
                     <urn:jas:annotatie:BWBR0004770:artikel:9:e7k2:positie> .
  <urn:jas:annotatie:BWBR0004770:artikel:9:e7k2:quote> a oa:TextQuoteSelector ;
      oa:exact "de ontvanger" ; oa:prefix "1. " ; oa:suffix " kan" .
  <urn:jas:annotatie:BWBR0004770:artikel:9:e7k2:positie> a oa:TextPositionSelector ;
      oa:start 3 ; oa:end 15 ; jas:lidHash "9f3a1c02" .

  <urn:jas:annotatie:BWBR0004770:artikel:9:e7k2:beslissing:1> a jas:Beslissing, prov:Activity ;
      jas:beslissingType jas:beslissing-approve ;
      prov:wasAssociatedWith <urn:jas:agent:mens:palmw01> .
}
```

## De wettekst blijft schoon (invarianten, met tests)

Lex bevraagt de union van alle graven (zonder `GRAPH`), de similarity-index pakt elke `urn:bwb-ns:tekst`
en de bronnencontrole telt elke `urn:bwb:`-string als vindplaats. Een annotatie mag daar nergens als
wettekst opduiken. Daarom (`api/tests/test_graaf_projectie.py`):

1. **Geen subject onder `urn:bwb:`.** De wet komt alleen als object voor (`oa:hasSource`, `jas:bepaling`).
2. **Geen `urn:bwb-ns:`-predicaat**, dus ook geen `urn:bwb-ns:tekst`: het citaat staat in `oa:exact`.
3. **Geen `rdfs:domain`, `rdfs:range`, `subPropertyOf`, `subClassOf` of `owl:sameAs`** in de
   jas-ontologie. De repository draait met `rdfsplus-optimized`, en een range op een property die naar
   een wet-node wijst laat GraphDB triples áfleiden met een `urn:bwb:`-subject.
4. **De OA- en PROV-ontologieën worden niet geladen** – om dezelfde reden.

## Buiten scope (nog)

- **QA-gebruik.** De antwoord-worker van Lex gebruikt de laag nog niet. Dat raakt de grounding: een
  annotatie is afgeleide duiding en mag nooit als wettekst tellen (zie `docs/kennisbank/PLAN.md`).
- **Begrippen (activiteit 3)** worden hier niet geschreven.
