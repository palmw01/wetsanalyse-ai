# bwb-import

ETL-pijplijn die Nederlandse wetgeving uit het **Basiswettenbestand (BWB)**
importeert in **GraphDB** (RDF/SPARQL). Op Azure gaat het om zeven regelingen (param `bwbIds` in
`deploy/azure/main.bicep`): `BWBR0002320`, `BWBR0004766`, `BWBR0004770` (Invorderingswet 1990, de
standaardregeling), `BWBR0005537`, `BWBR0018472`, `BWBR0019237` en `BWBR0024096`. Een andere regeling
importeer je met haar BWB-id, zolang ze tot een van de drie documentsoorten hieronder behoort.

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
  Onderdeel/Divisie/Bijlage` (+ abstracte `bwb:Structuurdeel`) en `bwb:Verwijzing`; elke node met een
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
  comments `@nl`, domains/ranges) naar de named graph `BASE graph:ontologie`,
  met sub-axioma's naar **ELI** (`eli:LegalResource(Subdivision)`, `eli:has_part`,
  `eli:cites`, `eli:title`, …). De repository draait `rdfsplus-optimized`,
  dus SPARQL over `eli:`-termen werkt via inferentie.
- **Canonieke identiteit**: wet- en citeerbare nodes krijgen `owl:sameAs` naar
  `https://wetten.overheid.nl/{bwb_id}` resp. de jci-resolver-URL; de
  geïmporteerde toestand staat als `bwb:toestandUrl`. Wil je sameAs-expansie
  in een query uitzetten: `FROM onto:disable-sameAs`.
- **Vindplaats vs. identiteit**: `owl:sameAs` bestaat alleen waar de bron een échte jci geeft, en
  dat is lang niet overal — bij de meting waarop dit ontwerp rust hadden van de 800 Leidraad-divisies
  er 113 een eigen `<jci>` (102/102 op het topniveau, 10/306 één laag dieper, 1/389 daaronder). Voor de rest is er `bwb:bronUrl`: de
  anker-URL op de toestandspagina, afgeleid uit het `bwb-ng-variabel-deel`-pad
  (`…/BWBR0024096/2026-07-01#Circulaire.divisie25_Circulaire.divisie25.1`). Elke citeerbare node
  krijgt hem, ook die mét jci — anders wordt zijn aanwezigheid zélf een signaal.
  **Verzin nooit een jci.** Getest tegen wetten.overheid.nl: `&artikel=19.1.8` (door de redactie
  toegekend) redirect naar het juiste anker, maar `&artikel=25.1` en `&artikel=26.1.9` landen
  zonder anker op de hele regeling. Zo'n verzonnen verwijzing ziet er geldig uit en wijst naar de
  verkeerde tekst.
- **Dekking is een cijfer, geen oordeel** (`app/dekking.py`): de import legt de `<al>`-tekens in de
  bron naast de `bwb:tekst`-literals in de graaf en toont de uitkomst in het import-overzicht.
  `tests/test_dekking.py` bewaakt hem offline op de fixtures. Ontbrekende tekst geeft anders geen
  fout, geen lege node en geen waarschuwing: hij is gewoon stil weg.
- **En het cijfer bijt, vóór de PUT** (`BWB_MIN_DEKKING`, default 0,995): de import bouwt de graph
  offline, meet hem tegen de bron (bijlagen tellen mee) en beslist dan pas of hij de bestaande named
  graph mag vervangen (`dekking.poortbesluit`). Een PUT vervangt alles, dus een controle erna kan niets
  tegenhouden. De regel is **vervang nooit door minder**:

  - een toestand zonder tekst wordt nooit geschreven (exitcode **1**);
  - onder de drempel wordt alleen geschreven als er minstens zoveel tekst komt te staan als er stond.
    Een lege graaf wordt dus gevuld: na een GraphDB-herstart is een onvolledige wet beter dan geen wet;
  - een mislukte WTI vervangt geen verrijkte graph. Op een graph zonder WTI wordt wel geschreven.

  Sloeg de poort aan, dan eindigt de import met exitcode **2** en wordt de container-app-job rood,
  net als de `vul-graaf`-workflow, die alleen `Succeeded` accepteert. De graaf gaat bij een 2 niet
  achteruit, maar hij kan achterlopen op de bron. Het overzicht en de JSON noemen de reden, en
  `tegengehouden` als de bestaande graph bleef staan. Exitcode **1** blijft voor een wet die niet
  gelezen of geschreven kon worden. De XSD-uitslag staat in het overzicht en blokkeert niet.

  Twee dingen om te kennen. **De job probeert het eerst nog een keer**: `replicaRetryLimit: 1`
  betekent dat een dip een volledige tweede import uitlokt voordat de execution `Failed` wordt.
  Bij een dip is dat verspilling, bij een tijdelijke WTI-fout juist de bedoeling. En **een
  onleesbare waarde zet de controle niet uit**: `_as_float` valt terug op de default met een
  waarschuwing, want stilzwijgend op 0 vallen door een tikfout is het ene faalgedrag dat een
  drempel niet mag hebben.

  Blijkt een dip legitiem — een regeling die nu eenmaal lager meet — verlaag dan `minDekking` in
  `deploy/azure/main.bicep`; 0 zet de dipregel uit. Dat is een bewuste, zichtbare keuze in plaats
  van een stille. De lege toestand en de WTI-regel blijven dan gelden.
- **Een bijlage is een volwaardig deel, met een eigen identiteit.** Hoofdstukken in een bijlage staan
  in de bron als `<divisie>` met een koplabel (Bijlage 2 van de Awb) en worden gewone structuurdelen.
  Een artikelnummer is alleen binnen de wettekst uniek: Bijlage 2 en 3 van de Awb hebben allebei een
  artikel 1. Daarom krijgt alles in een bijlage de wet-lokale vorm die de bijlage zelf al heeft
  (`urn:bwb:BWBR0005537:id:BWBR0005537%2FBijlage2%2FDivisie1%2FArtikel1`), met `bwb:vindplaats`
  "Bijlage 2, artikel 1". `bwb:jci` houdt de echte jci; een sleutel uit die jci zou de bijlage weglaten.
  Een jci die in een bijlage wijst, wijst daarom nooit naar een node in de wet zelf, en "artikel 16"
  zonder wetsnaam in een bijlage is geen verwijzing naar de eigen wet.
- **Onbekende structuur is een signaal, geen stilte en geen crash.** Wat de parser in een container niet
  kent, komt in `Wet.overgeslagen` en weegt in de importpoort als een dip. Een ParseError zou op een
  lege graaf de hele wet weghouden; stil overslaan is hoe Bijlage 2 verdween, en de drempel heeft
  genoeg speling om een heel artikel te verbergen.
- **Tekst ná een opsomming is een eigen node.** De bron zet een `<al>` achter een `<lijst>` in
  hetzelfde element (art. 6 lid 2 c Uitvoeringsregeling Awir, art. 24 lid 1 IW 1990, en bij de
  Leidraad vaak). Zo'n reeks alinea's wordt een ongenummerde `bwb:Onderdeel` met
  `bwb:label "Slottekst"`, tussen de onderdelen van zijn houder (`Onderdeel.slottekst`,
  `_parse_onderdelen` in `app/parser.py`); lijst en tekst mogen afwisselen. `bwb:tekst` van de houder
  is alleen wat vóór de eerste lijst staat. Een `<al>` heeft geen jci, dus de IRI is wet-lokaal
  (`…:id:…%2FSlottekst1`) en de node is niet citeerbaar; zijn `bwb:vindplaats` is die van zijn ouder.
  De volgorde staat in `bwb:volgtOp` (alleen tussen onderdelen van een houder met een slottekst, zodat
  de rest van de regeling haar snapshot-id houdt) en `bwb:volgnummer` (alle onderdelen, om op te
  sorteren).
- **Predicaten**: `bwb:heeftHoofdstuk/…/heeftArtikel/heeftLid/heeftOnderdeel/
  heeftDivisie/heeftBijlage`, `bwb:bevatIllustratie`, `bwb:ondertekendDoor`,
  `bwb:volgtOp`, `bwb:verwijstNaar`, `bwb:heeftVerwijzing`, `bwb:inBepaling`; properties als
  `bwb:nummer/tekst/jci/refKey/labelId/voetnoot/definieertBegrip/aanhef/considerans/
  terugwerkendTot/…` (illustratie: `naam/formaat/breedte/hoogte/alt`; ondertekenaar:
  `functie/naam/voornaam/achternaam/plaats`). Datums zijn `xsd:date`, tekst `@nl`.
- **Brondata per tekstdeel** (artikel, divisie, bijlage; uit het eigen `meta-data/brondata`):
  naast `bwb:bron` en `bwb:inwerking` (uit de attributen) ook `bwb:dossier` (meerwaardig: het
  Kamerdossier van de wet die de tekst zijn huidige inhoud gaf, plus dat van een `<juncto>`),
  `bwb:inwerkingtredingsbron` (de Stb van het inwerkingtredingsbesluit) en `bwb:opmerking`
  (redactioneel, vaak over overgangsrecht). Art. 9 Iw → dossier 35910. Een ministeriële regeling of
  beleidsregel heeft geen Kamerdossier; dat veld blijft dan leeg.
- **WTI-relaties** (met `BWB_IMPORT_WTI`): naast de bestaande verrijking
  (citeertitels, rechtsgebieden als `skos:Concept`, `bwb:heeftGrondslag`) ook
  `bwb:uitgegevenDoor` (→ `bwb:Organisatie` uit `owms:kern/overheid:authority`),
  `bwb:inFamilie` (verwante regelingen uit de wetsfamilie) en per artikel/
  structuurdeel `bwb:grondslagVoor`/`bwb:bevoegdheidVoor`/`bwb:verwijzingDoor`
  (→ de gerelateerde `bwb:Regeling`; gekoppeld via de WTI-`label-id`).
- **IRI-schema (ref_key)**: wet = `BASE{bwb_id}`; dieper afgeleid van de jci
  (`Vocab.by_ref_key` in `app/rdf_vocab.py`): `BASE{bwb}:artikel:{nr}`,
  `…:artikel:2:lid:1:o:a` (onderdelen), `…:hoofdstuk:I:afdeling:1` (structuurdelen).
  Niet-citeerbare nodes krijgen `BASE{bwb}:id:{xml-id}`. Een `verwijstNaar` wijst naar exact
  dezelfde IRI (open-world: geen stub-nodes; de doel-IRI krijgt inhoud zodra
  die wet volgt). Verwijzingen naar hele hoofdstukken/titeldelen/afdelingen/
  wetten blijven dus behouden.

  **Een structuurdeel draagt het volledige pad in zijn sleutel**
  (`{bwb}#hoofdstuk=VI#afdeling=1`, `jci_node_ref_key` in `app/references.py`), en dat is geen
  netheid. Met alleen het laatste jci-segment landt élke "Afdeling 1" van een regeling op dezelfde
  node, met titels en artikelen van verschillende afdelingen op één hoop: bij de Invorderingswet
  zijn zowel *Aansprakelijkheid* (hoofdstuk VI) als *Verhaalsrechten* (hoofdstuk IV) `afdeling:1`.

  Een verwijzing schrijft dat pad vaak niet mee (ongeveer de helft van de afdelingsverwijzingen).
  Daarom **verzamelt de batch-import eerst alle wetten en schrijft hij pas daarna**
  (`run_imports` in `app/main.py`): uit alle verzamelde wetten samen komt één `structuurindex` —
  padloze sleutel → volledige ref_key, en alleen als dat nummer binnen die regeling ondubbelzinnig
  is — waarmee `koppel_structuurverwijzingen` (`app/collect.py`) de doelen met een exacte lookup
  rechtzet.

  Die volgorde is het hele punt. Los je een verwijzing op tijdens de import van de *citerende* wet,
  dan kan dat per definitie niet voor een doel in een ándere wet: die is dan nog niet gezien, en de
  verwijzing landt op een lege node. Een run met één wet heeft precies die grens.

  Is het nummer binnen de doelwet niet ondubbelzinnig, dan blijft de verwijzing een open stub; bij
  een écht ambigue verwijzing is dat eerlijker dan een gok. Hetzelfde geldt voor een doel in een wet
  die niet in de run zit: open-world, de IRI krijgt inhoud zodra die wet volgt.

  Artikel-, lid- en onderdeelsleutels zijn ongemoeid: die zijn binnen een regeling al uniek, en daar
  hangen de annotaties aan.
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
  **Een verwijzing volgt haar hele tekst.** De `doc` stopt in de BWB altijd bij het artikel; lid en
  onderdeel staan alleen in de ankertekst ("artikel 25, derde lid"). `deeldoelen` (`app/references.py`)
  leest die tekst, en `koppel_deelverwijzingen` (`app/collect.py`) laat `bwb:verwijstNaar` uitkomen op
  elk genoemd lid of onderdeel dat in de run bestaat, met terugval van onderdeel op lid op artikel.
  Het artikel is ook de uitkomst voor een wet buiten de run en voor tekst die niet eenduidig is
  ("artikelen 3 en 4, eerste lid"); `bwb:doelLid` bewaart dan het genoemde lid. Een
  run met één wet kent alleen die wet, dus de batch-import levert de fijnste koppeling. Ongetagde
  tekstverwijzingen blijven op artikelniveau. Wie inkomende verwijzingen van een artikel wil, loopt
  mee over `(bwb:heeftLid|bwb:heeftOnderdeel)*`.
- **Idempotentie**: elke wet in named graph `BASE graph:{bwb_id}` (bij de default `urn:bwb:graph:BWBR…`); `PUT` vervangt.

Stabiele sleutels komen uit het XML-attribuut `bwb-ng-variabel-deel`
(bv. `BWBR0004770/HoofdstukI/Artikel1`), zodat herimports idempotent zijn. De
ref_key is afgeleid uit de canonieke jci-verwijzing – daardoor ontstaan
cross-wet links vanzelf zodra de doelwet ook is geïmporteerd.

Verander je het IRI-schema, dan is er geen migratiestap nodig: de import vervangt elke named graph
integraal en draait na elke deploy en wekelijks. Tot die herimport meet
`tools/graph-qa/eval/retrieval_smoke.py` nog de oude toestand. Let op: de annotatielagen van de api
hangen aan artikel-, lid- en onderdeel-IRI's; die mogen niet zomaar verschuiven.

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

## Similarity-index (`bwb_similarity`)

Na het schrijven waarborgt de batch-import ook de native GraphDB text-similarity-index
`bwb_similarity` (`ensure_similarity_index`) over alle `bwb:tekst`-literals binnen de eigen
IRI-ruimte. graph-qa's `semantic_search` gebruikt hem (env `SIMILARITY_INDEX=bwb_similarity` op
graph-qa); zonder index valt die tool terug op `search_wetgeving`.

Twee regels:

- **Hij wordt pas ná het schrijven aangemaakt**, niet in `prepare()`. Een similarity-index is een
  momentopname die bij het aanmaken wordt getraind; over een lege graaf gebouwd vindt hij nooit
  iets. De Lucene-connector loopt daarentegen live mee.
- **Een bestaande index wordt niet herbouwd.** Een mislukte aanmaak is nooit fataal voor de
  import; hij logt een waarschuwing. Achtergrond: `tools/graph-qa/docs/embeddings-runbook.md`.

GraphDB bewaart de index niet over een herstart heen (de opslag op Azure is niet-persistent); de
eerstvolgende import, via de graafwacht, bouwt hem opnieuw.

## WTI-verrijking (optioneel)

Met `BWB_IMPORT_WTI=true` wordt per wet ook de wetstechnische informatie
geladen: officiële citeertitels en afkortingen (`bwb:afkorting`,
`bwb:alternatieveTitel`), eerstverantwoordelijk ministerie, rechtsgebieden en
overheidsdomeinen als `skos:Concept`en (`dcterms:subject`, hiërarchie via
`skos:broader`) en grondslag-relaties (`bwb:heeftGrondslag` ⊑ `eli:based_on`).
Een mislukte WTI-download laat de wet gewoon lezen, maar is poortwerk: een verrijkte graph wordt niet
vervangen door een onverrijkte, en de import eindigt met exitcode 2. Het eerstverantwoordelijke ministerie staat
ook als TOOI-URI op `bwb:eerstverantwoordelijkeOrganisatie` (met `rdfs:label`), via de snapshot
`app/tooi_ministeries.json` (CC0, met bron en datum; ook historische namen). Een onbekende naam blijft
alleen tekst en wordt gelogd (`app/tooi.py`).

## Installatie

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env   # zet GRAPHDB_URL; lokaal is dat http://localhost:7200
```

> Vereist Python ≥ 3.13 (`pyproject.toml`); de container draait 3.14. De officiële XSD's
> staan in `schemas/`.

## Configuratie (`.env`)

| Variabele              | Default                       | Uitleg                                        |
|------------------------|-------------------------------|-----------------------------------------------|
| `GRAPHDB_URL`          | `http://graphdb:7200`         | GraphDB-basis-URL; de default is een containernaam |
| `GRAPHDB_REPOSITORY`   | `inning`                      | Doel-repository                               |
| `GRAPHDB_USER`         | –                             | Optioneel; leeg = anoniem                     |
| `GRAPHDB_PASSWORD`     | –                             | Optioneel                                     |
| `GRAPHDB_BASE_IRI`     | `urn:bwb:`                    | IRI-namespace voor resources                  |
| `GRAPHDB_ONTOLOGY_IRI` | `urn:bwb-ns:`                 | IRI-namespace voor de ontologie               |
| `BWB_DEFAULT_ID`       | `BWBR0004770`                 | Standaardregeling                             |
| `BWB_VALIDATE_XSD`     | `true`                        | XSD-validatie (niet-blokkerend)               |
| `BWB_DETECT_TEKSTUELE_REFS` | `true`                   | Ongetagde tekstverwijzingen detecteren        |
| `BWB_IMPORT_WTI`       | `false`                       | WTI-verrijking (titels/rechtsgebieden/grondslagen); op Azure `true` |
| `BWB_MIN_DEKKING`      | `0.995`                       | Ondergrens tekstdekking; eronder exitcode 2; `0` = uit |
| `BWB_DATA_DIR`         | `data/` (in de projectwortel) | Cache-map voor gedownloade XML                |
| `BWB_SCHEMAS_DIR`      | `schemas/` (in de projectwortel) | Map met de officiële XSD's                 |
| `BWB_SRU_URL`          | `https://zoekservice.overheid.nl/sru/Search` | SRU-zoekdienst (discovery)     |

## Gebruik

```bash
# Importeer de standaardregeling (Invorderingswet 1990)
.venv/bin/python main.py

# Of een andere regeling
.venv/bin/python main.py BWBR0005537

# Batch: meerdere regelingen in één run (eerst alles verzamelen, dan schrijven; per wet idempotent)
.venv/bin/python main.py BWBR0004770 BWBR0005537 BWBR0024096

# Alleen importeren als er een regeling in de graaf ontbreekt (de stand van de graafwacht)
.venv/bin/python main.py BWBR0004770 BWBR0005537 --alleen-bij-verlies

# Naar een andere GraphDB
GRAPHDB_URL=http://localhost:7200 .venv/bin/python main.py BWBR0004770
```

Na afloop verschijnt per wet een overzicht met tellingen per elementtype
(wetten, hoofdstukken, afdelingen, paragrafen, divisies, artikelen, leden,
onderdelen en relaties), de tekstdekking, de XSD-uitslag en wat de importpoort besloot. Exitcodes:
**0** goed, **1** een wet kon niet gelezen of geschreven worden, **2** de importpoort sloeg aan (zie
*En het cijfer bijt*).

`--alleen-bij-verlies` doet eerst één SPARQL-peiling (`GraphDbWriter.graaf_is_compleet`): staat
van elke gevraagde regeling tekst in de repository, dan stopt hij met exitcode 0
zonder overheid.nl te benaderen. Een HTTP-fout of onleesbaar antwoord in die peiling telt als "niet
compleet": een ontbrekende repository geeft een 404, en dat is precies de toestand waarvoor de peiling
bestaat.

## Tests

```bash
.venv/bin/python -m pytest -q
```

De tests draaien offline op de fixtures in `tests/fixtures/`. CI draait dezelfde suite vóór de
image-build.

## Uitrol op Azure

Het image `ghcr.io/palmw01/bwb-import` wordt door `.github/workflows/bwb-import-docker-publish.yml`
getest, gebouwd en gepusht bij een push naar `master` die `tools/bwb-import/**` raakt (Markdown
uitgezonderd), of handmatig via `workflow_dispatch`. `deploy/azure/main.bicep` rolt het uit als twee
container-app-jobs met dezelfde CLI, dezelfde lijst regelingen (param `bwbIds`) en dezelfde env
(`BWB_IMPORT_WTI=true`, `BWB_VALIDATE_XSD=true`, `BWB_DETECT_TEKSTUELE_REFS=true`,
`BWB_MIN_DEKKING` uit param `minDekking`):

| job | trigger | wat hij doet |
|---|---|---|
| `<appName>-bwb-import` | cron `0 3 * * 1` (maandag 03:00 UTC), en `azure-infra` → `deploy` of `vul-graaf` | volledige import; `replicaRetryLimit: 1` |
| `<appName>-graafwacht` | cron `*/15 * * * *` | `--alleen-bij-verlies`: één peiling, alleen bij verlies een volledige import; geen retry |

De graafwacht bestaat omdat GraphDB op Azure niet-persistent is en na een onverwachte herstart leeg
opkomt, zonder repository `inning`. Die repository maakt alleen de importer aan
(`GraphDbWriter.ensure_constraints`), dus zonder graafwacht blijft de graaf leeg tot de volgende
deploy of de weekcron. Draait de graafwacht precies terwijl de graaf wordt gevuld, dan start hij een
tweede import; dat is idempotent, alleen verspilling.

Handmatig starten: `azure-infra` → actie `vul-graaf` (start de import-job en wacht hem af), of
`az containerapp job start -n <appName>-bwb-import -g <resource-group>`. Zonder GraphDB-licentie
komt de graaf read-only op en faalt de import op het eerste schrijfverzoek; zie
`deploy/azure/README.md`.
