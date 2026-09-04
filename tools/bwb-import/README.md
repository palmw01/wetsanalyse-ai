# bwb-import

ETL-pijplijn die Nederlandse wetgeving uit het **Basiswettenbestand (BWB)**
importeert in **GraphDB** (RDF/SPARQL). Referentie-implementatie: de
Invorderingswet 1990 (`BWBR0004770`). De oplossing is uitbreidbaar naar de
volledige BWB-collectie zonder het datamodel te wijzigen.

## Pijplijn

```
SRU-discovery → toestand-XML downloaden → XSD-validatie → lxml-parse → collect → GraphDB-writer
```

1. **Downloader** – ontdekt toestanden via de SRU-zoekdienst en haalt de
   nieuwste toestand-XML op (met lokale cache in `data/`).
2. **Parser** – valideert (optioneel) tegen het officiële XSD en parset de
   echte toestand-structuur naar dataclasses. Drie documentsoorten: gewone
   wetten/besluiten (`<wet-besluit>/<wettekst>` met
   hoofdstuk/afdeling/…/artikel/lid), ministeriële regelingen
   (`<regeling>/<regeling-tekst>`, zelfde bouwstenen, bv. de Uitvoeringsregeling
   Invorderingswet 1990 `BWBR0004766`) én circulaires/beleidsregels
   (`<circulaire>/<circulaire-tekst>` met een recursieve
   `<circulaire.divisie>`-boom, bv. de Leidraad Invordering 2008
   `BWBR0024096`); een divisie is tegelijk container én tekstdrager, en kan naast subdivisies
   en onderdelen ook **eigen `<artikel>`-kinderen** hebben — het XSD staat dat toe en de
   Leidraad gebruikt het (tien onder `/Circulaire.divisie22bis`, één onder
   `/Circulaire.divisie79`). Ze worden in documentvolgorde met de subdivisies meegelezen.
3. **Collect** (`app/collect.py`) – loopt het model één keer door naar een
   opslag-agnostische `Batch` (nodes/relaties/verwijzingen + telling).
4. **Writer** (`app/graphdb_writer.py`) – vertaalt de `Batch` naar RDF-triples;
   elke wet in een eigen named graph. Re-import vervangt die graaf integraal
   (RDF4J Graph Store `PUT`) → idempotent.

## Datamodel (GraphDB / RDF)

Custom ontologie (`app/rdf_vocab.py` + T-Box in `app/ontology.py`) met twee
namespaces: resources onder `GRAPHDB_BASE_IRI` (default `urn:bwb:`),
de ontologie onder `GRAPHDB_ONTOLOGY_IRI` (default `urn:bwb-ns:`,
prefix `bwb:`).

Waarom een **URN** en geen http-IRI: een domeinnaam in het datamodel bindt de data aan wie dat
domein toevallig bezit, en verhuizen kost dan een herimport van álles. Dat een URN niet
dereferenceerbaar is, kost hier niets – elke citeerbare node krijgt een `owl:sameAs` naar
`wetten.overheid.nl`, en dát is de publieke, klikbare vindplaats.

De twee ruimtes zijn bewust **disjunct** (`urn:bwb:` naast `urn:bwb-ns:`, niet `urn:bwb:ns:`):
graph-qa herkent vindplaatsen door op de documentbasis te prefixen, dus een vocabulaire *onder* de
documentruimte zou predicaten als "bron" onder een antwoord laten verschijnen.

De vorm is `urn:bwb:{bwbId}[:{sleutel}:{waarde}]*`, bijvoorbeeld
`urn:bwb:BWBR0004770:artikel:9:lid:1`. Waarden worden percent-escaped, zodat een `:` in een
waarde niet als segmentgrens leest.

- **Klassen**: `bwb:Regeling/Hoofdstuk/Titeldeel/Afdeling/Paragraaf/Artikel/Lid/
  Onderdeel/Divisie/Bijlage` (+ abstracte `bwb:Structuurdeel`); elke node met een
  JuriConnect-identiteit draagt ook `bwb:Citeerbaar` (incl. `bwb:Bijlage`). Het
  documenttype staat als subklasse van `bwb:Regeling` op de top-node (`bwb:Wet`,
  `bwb:AMvB`, `bwb:KoninklijkBesluit`, `bwb:MinisterieleRegeling`,
  `bwb:Beleidsregel`, `bwb:Circulaire`; onbekende `soort` → alleen `bwb:Regeling`),
  naast de letterlijke bronwaarde in `bwb:soort`. Verder `bwb:Illustratie`
  (afbeelding, via `bwb:bevatIllustratie`), `bwb:Ondertekenaar` (ondertekenaar
  van de regeling) en `bwb:Organisatie` (verantwoordelijk ministerie uit de WTI);
  de laatste twee zijn `foaf:Agent` en krijgen een wet-overstijgende slug-IRI
  zodat dezelfde persoon/organisatie over regelingen heen samenvalt.
- **T-Box + ELI**: `app/ontology.py` schrijft een OWL/RDFS-schema (labels en
  comments `@nl`, domains/ranges) naar de named graph `BASE graph/ontologie`,
  met sub-axioma's naar **ELI** (`eli:LegalResource(Subdivision)`, `eli:has_part`,
  `eli:cites`, `eli:title`, …). De repository draait `rdfsplus-optimized`,
  dus SPARQL over `eli:`-termen werkt via inferentie.
- **Canonieke identiteit**: wet- en citeerbare nodes krijgen `owl:sameAs` naar
  `https://wetten.overheid.nl/{bwb_id}` resp. de jci-resolver-URL; de
  geïmporteerde toestand staat als `bwb:toestandUrl`. Wil je sameAs-expansie
  in een query uitzetten: `FROM onto:disable-sameAs`.
- **Vindplaats vs. identiteit**: `owl:sameAs` bestaat alleen waar de bron een échte jci geeft, en
  dat is lang niet overal — van de 800 Leidraad-divisies hebben er 113 een eigen `<jci>` (102/102
  op het topniveau, 10/306 één laag dieper, 1/389 daaronder). Voor de rest is er `bwb:bronUrl`: de
  anker-URL op de toestandspagina, afgeleid uit het `bwb-ng-variabel-deel`-pad
  (`…/BWBR0024096/2026-07-01#Circulaire.divisie25_Circulaire.divisie25.1`). Elke citeerbare node
  krijgt hem, ook die mét jci — anders wordt zijn aanwezigheid zélf een signaal.
  **Verzin nooit een jci.** Getest tegen wetten.overheid.nl: `&artikel=19.1.8` (door de redactie
  toegekend) redirect naar het juiste anker, maar `&artikel=25.1` en `&artikel=26.1.9` landen
  zonder anker op de hele regeling. Zo'n verzonnen verwijzing ziet er geldig uit en wijst naar de
  verkeerde tekst.
- **Dekking is een cijfer, geen oordeel** (`app/dekking.py`): de import legt de `<al>`-tekens in de
  bron naast de `bwb:tekst`-literals in de graaf en toont de uitkomst in het import-overzicht.
  `tests/test_dekking.py` bewaakt hem offline op de fixtures. Dit bestaat omdat elf
  Leidraad-artikelen (10.052 tekens) stil ontbraken: geen fout, geen lege node, geen waarschuwing.
- **En het cijfer bijt** (`BWB_MIN_DEKKING`, default 0,995): zakt een regeling eronder, dan eindigt
  de import met **exitcode 2** en wordt de container-app-job rood — net als de `vul-graaf`-workflow,
  die alleen `Succeeded` accepteert. Exitcode **1** blijft voorbehouden aan een import die niet
  geschreven kon worden; dat onderscheid bestaat zodat je in het logboek van een gefaalde job niet
  hoeft te zoeken welk van de twee het was.

  Drie dingen om te kennen. **Een 2 kost geen data**: `write_wet` doet de named-graph PUT vóórdat er
  iets te meten valt, dus de graaf is na een "gefaalde" run precies zo compleet als hij zonder deze
  controle geweest zou zijn. **De job probeert het eerst nog een keer**: `replicaRetryLimit: 1`
  betekent dat een dip een volledige tweede import uitlokt voordat de execution `Failed` wordt —
  verspilling, want de meting is deterministisch, maar die limiet verlagen zou echte tijdelijke
  fouten hun tweede kans afnemen. En **een onleesbare waarde zet de controle niet uit**: `_as_float`
  valt terug op de default met een waarschuwing, want stilzwijgend op 0 vallen door een tikfout is
  het ene faalgedrag dat een drempel niet mag hebben.

  Blijkt een dip legitiem — een regeling die nu eenmaal lager meet — verlaag dan `minDekking` in
  `deploy/azure/main.bicep`; 0 zet de controle helemaal uit. Dat is een bewuste, zichtbare keuze in
  plaats van een stille.
- **Predicaten**: `bwb:heeftHoofdstuk/…/heeftArtikel/heeftLid/heeftOnderdeel/
  heeftDivisie/heeftBijlage`, `bwb:bevatIllustratie`, `bwb:ondertekendDoor`,
  `bwb:volgtOp`, `bwb:verwijstNaar`; properties als
  `bwb:nummer/tekst/jci/refKey/labelId/voetnoot/definieertBegrip/aanhef/considerans/
  terugwerkendTot/…` (illustratie: `naam/formaat/breedte/hoogte`; ondertekenaar:
  `functie/naam/voornaam/achternaam/plaats`). Datums zijn `xsd:date`, tekst `@nl`.
- **WTI-relaties** (met `BWB_IMPORT_WTI`): naast de bestaande verrijking
  (citeertitels, rechtsgebieden als `skos:Concept`, `bwb:heeftGrondslag`) ook
  `bwb:uitgegevenDoor` (→ `bwb:Organisatie` uit `owms:kern/overheid:authority`),
  `bwb:inFamilie` (verwante regelingen uit de wetsfamilie) en per artikel/
  structuurdeel `bwb:grondslagVoor`/`bwb:bevoegdheidVoor`/`bwb:verwijzingDoor`
  (→ de gerelateerde `bwb:Regeling`; gekoppeld via de WTI-`label-id`).
- **IRI-schema (ref_key)**: wet = `BASE{bwb_id}`; dieper afgeleid van de jci:
  `BASE{bwb}/artikel/{nr}`, `…/artikel/2/lid/1/o/a` (onderdelen),
  `…/hoofdstuk/I` (structuurdelen). Een `verwijstNaar` wijst naar exact
  dezelfde IRI (open-world: geen stub-nodes; de doel-IRI krijgt inhoud zodra
  die wet volgt). Verwijzingen naar hele hoofdstukken/titeldelen/afdelingen/
  wetten blijven dus behouden.

  **Een structuurdeel draagt het volledige pad in zijn sleutel**
  (`{bwb}#hoofdstuk=VI#afdeling=1`, `jci_node_ref_key`), en dat is geen netheid. Tot 4 sep 2026
  werd alleen het laatste jci-segment aangehouden, waardoor élke "Afdeling 1" van een regeling op
  dezelfde node landde: 16 van de 93 afdelingen en 5 van de 27 paragrafen in de graaf hadden meer
  dan één ouder, met hun titels en artikelen op één hoop. Bij de Invorderingswet was `afdeling:1`
  tegelijk *Aansprakelijkheid* (hoofdstuk VI) en *Verhaalsrechten* (hoofdstuk IV).

  Een verwijzing schrijft dat pad vaak niet mee (ongeveer de helft van de afdelingsverwijzingen);
  een resolve-pas in `collect.py` koppelt die alsnog aan de juiste node zolang het nummer binnen de
  regeling uniek is. Is het dat niet, dan blijft de verwijzing een open stub — bij een écht ambigue
  verwijzing is dat eerlijker dan een gok. Artikel-, lid- en onderdeelsleutels zijn ongemoeid: die
  zijn binnen een regeling al uniek, en daar hangen de annotaties aan.
- **Het fallback-label van een verwijsdoel staat op `bwb:doelLabel`**, niet op `rdfs:label`. Elke
  wet zit in een eigen named graph, dus een fallback op `rdfs:label` komt náást het échte label te
  staan zodra de doelwet óók wordt geïmporteerd — en dan verdubbelt elke query die een label
  ophaalt haar rijen. Lezers gebruiken `COALESCE(rdfs:label, bwb:doelLabel)`.
- **Verwijzingen** met eigenschappen: een `bwb:Verwijzing`-tussenresource
  (`bwb:naar/soort/doc/doelLid/doelSoort/doelPad/ankerTekst/verwijzingId`)
  naast de directe `bwb:verwijstNaar`-edge. Ongetagde tekstverwijzingen
  ("artikel 3:2 Awb") worden gedetecteerd via `app/afkortingen.py` en
  gemarkeerd met `bwb:soort "tekstueel"` + `bwb:betrouwbaarheid "laag"`,
  zodat een chatbot erop kan filteren (uit te zetten met
  `BWB_DETECT_TEKSTUELE_REFS=false`).
- **Idempotentie**: elke wet in named graph `BASE graph/{bwb_id}`; `PUT` vervangt.

Stabiele sleutels komen uit het XML-attribuut `bwb-ng-variabel-deel`
(bv. `BWBR0004770/HoofdstukI/Artikel1`), zodat herimports idempotent zijn. De
ref_key is afgeleid uit de canonieke jci-verwijzing – daardoor ontstaan
cross-wet links vanzelf zodra de doelwet ook is geïmporteerd.

> **Migratie**: sinds de citeerbare-identiteit-uitbreiding wijzigen de IRI's
> van structuurdelen, leden en onderdelen. Eén her-import per wet volstaat
> (de named graph wordt integraal vervangen).
>
> Datzelfde geldt voor de padsleutel en `bwb:doelLabel` hierboven (4 sep 2026): de IRI's van
> hoofdstukken, titeldelen, afdelingen en paragrafen veranderen, artikelen en leden niet. De
> import-job draait automatisch na een deploy en wekelijks, dus er is geen migratiestap — maar tot
> die herimport draait, meet `eval/retrieval_smoke.py` in graph-qa nog de oude toestand.

## Full-text search (Lucene)

De writer waarborgt idempotent een GraphDB Lucene-connector `bwb_tekst`
(DutchAnalyzer, talen `nl` + ongetagd) over alle tekstvelden
(`tekst/titel/citeertitel/opschrift/aanhef/considerans/voetnoot/
definieertBegrip/rdfs:label`). Voorbeeldquery voor een chatbot:

```sparql
PREFIX luc: <http://www.ontotext.com/connectors/lucene#>
PREFIX inst: <http://www.ontotext.com/connectors/lucene/instance#>
PREFIX bwb: <urn:bwb-ns:>
SELECT ?node ?score ?tekst WHERE {
  [] a inst:bwb_tekst ;
     luc:query "rijksbelastingen AND invordering" ;
     luc:entities ?node .
  ?node luc:score ?score .
  OPTIONAL { ?node bwb:tekst ?tekst }
}
ORDER BY DESC(?score)
```

`luc:query` volgt de Lucene-syntax: `AND`/`OR`/`NOT`, `"exacte frase"`,
`wildcard*` en veldzoeken als `titel:invordering` (zonder veldprefix zoek je
in alle velden). graph-qa's `search_wetgeving`-tool gebruikt deze index voor
alle tekstuele zoekvragen.

## WTI-verrijking (optioneel)

Met `BWB_IMPORT_WTI=true` wordt per wet ook de wetstechnische informatie
geladen: officiële citeertitels en afkortingen (`bwb:afkorting`,
`bwb:alternatieveTitel`), eerstverantwoordelijk ministerie, rechtsgebieden en
overheidsdomeinen als `skos:Concept`en (`dcterms:subject`, hiërarchie via
`skos:broader`) en grondslag-relaties (`bwb:heeftGrondslag` ⊑ `eli:based_on`).
Best-effort: een falende WTI-download breekt de import niet.

## Installatie

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env   # vul GRAPHDB_* in (bij anonieme GraphDB volstaan de defaults)
```

> Vereist Python ≥ 3.13 (getest op 3.14; de container draait 3.13). De XSD's
> staan reeds in `schemas/`. `requirements.txt` pint `lxml>=5.3` omdat er voor
> Python 3.14 (nog) geen lxml-wheel voor `~=5.3` bestaat.

## Configuratie (`.env`)

| Variabele              | Default                       | Uitleg                                        |
|------------------------|-------------------------------|-----------------------------------------------|
| `GRAPHDB_URL`          | `http://graphdb:7200`         | GraphDB-basis-URL (intern op docker-netwerk)  |
| `GRAPHDB_REPOSITORY`   | `inning`                      | Doel-repository                               |
| `GRAPHDB_USER`         | –                             | Optioneel; leeg = anoniem                     |
| `GRAPHDB_PASSWORD`     | –                             | Optioneel                                     |
| `GRAPHDB_BASE_IRI`     | `urn:bwb:`       | IRI-namespace voor resources                  |
| `GRAPHDB_ONTOLOGY_IRI` | `urn:bwb-ns:`    | IRI-namespace voor de ontologie               |
| `BWB_DEFAULT_ID`       | `BWBR0004770`                 | Standaardregeling                             |
| `BWB_VALIDATE_XSD`     | `true`                        | XSD-validatie (niet-blokkerend)               |
| `BWB_DETECT_TEKSTUELE_REFS` | `true`                   | Ongetagde tekstverwijzingen detecteren        |
| `BWB_IMPORT_WTI`       | `false`                       | WTI-verrijking (titels/rechtsgebieden/grondslagen) |
| `BWB_SERVICE_API_KEY`  | –                             | Optionele API-key voor de service (`X-API-Key`-header) |
| `BWB_DATA_DIR`         | `data/`                       | Cache-map voor gedownloade XML                |
| `BWB_SCHEMAS_DIR`      | `schemas/`                    | Map met de officiële XSD's                    |
| `BWB_SRU_URL`          | `https://zoekservice.overheid.nl/sru/Search` | SRU-zoekdienst (discovery)     |
| `BWB_REPO_URL`         | `https://repository.officiele-overheidspublicaties.nl` | BWB-repository (downloads) |

## Gebruik

```bash
# Importeer de standaardregeling (Invorderingswet 1990)
.venv/bin/python main.py

# Of een andere regeling
.venv/bin/python main.py BWBR0005537

# Batch: meerdere regelingen in één run (sequentieel, per wet idempotent)
.venv/bin/python main.py BWBR0004770 BWBR0005537 BWBR0024096

# Naar een externe GraphDB
GRAPHDB_URL=https://graphdb.example .venv/bin/python main.py BWBR0004770
```

Na afloop verschijnt per wet een overzicht met tellingen per elementtype
(wetten, hoofdstukken, afdelingen, paragrafen, divisies, artikelen, leden,
onderdelen en relaties); de exit-code is 1 zodra één wet faalt.

## Service

```bash
.venv/bin/python -m uvicorn app.service:app --host 0.0.0.0 --port 8000
```

- `GET /health` → `{"status": "ok"}`
- `POST /import` met body `{"bwb_id": "BWBR0004770"}` → import + overzicht-JSON
  (zonder body wordt `BWB_DEFAULT_ID` geïmporteerd)
- `POST /import` met body `{"bwb_ids": ["BWBR0004770", "BWBR0005537"]}` →
  batch; respons `{"status": "ok"|"gedeeltelijk"|"mislukt", "resultaten": […]}`
  met per wet `status`/`overzicht`/`fout` (een falende wet breekt de batch niet)

Is `BWB_SERVICE_API_KEY` gezet, dan vereist `POST /import` de header
`X-API-Key: <key>` (anders 401).

De importer publiceert bewust geen poort: importeren is een schrijfactie op de graaf. Op Azure draait
hij als container-app-job – starten met `azure-infra` → actie `vul-graaf`, of automatisch na elke
`deploy` en wekelijks via de cron-trigger in `deploy/azure/main.bicep`.

## Deployment

De importer draait op Azure als **container-app-job** met een wekelijkse cron-trigger
(zie `deploy/azure/main.bicep`). Hij vult de graaf ook automatisch na elke infra-deploy,
want de GraphDB-opslag daar is niet-persistent. Het image `ghcr.io/palmw01/bwb-import` wordt door
`.github/workflows/bwb-import-docker-publish.yml` gebouwd en gepusht bij een push
naar `master` die `tools/bwb-import/**` raakt.
