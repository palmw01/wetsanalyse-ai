# CLAUDE.md – wetsanalyse-api

Headless FastAPI-backend voor de **Wetsanalyse-werkplek**: een zelfstandige, Dockeriseerbare dienst
die de [frontend](../frontend) (werkplek, login, beheervenster) en graph-qa bedient. Lees ook de
projectroot-`CLAUDE.md`. Endpoints, env-vars met defaults en lokaal draaien staan in
[`README.md`](README.md); dit bestand gaat over hoe de code in elkaar zit en wat je niet mag breken.

## Wat de API doet

1. **Het JAS-annotatiedomein** (`/v1/annotatie/*`): markeringen, beslissingen, append-only audit,
   export. De agent stelt voor, de jurist beslist, de API bewaart de review-state en projecteert hem
   naar de kennisgraaf. Eén laag per bronnode (artikel, lid of onderdeel) – zie §*Annotaties*.
2. **De chatgeschiedenis** (`/v1/gesprekken/*`), per gebruiker gescopet.
3. **Login en gebruikersbeheer** (`/v1/auth/*`, `/v1/admin/users`, `/v1/admin/registraties`): de API
   is de identiteitsbron van de webapp.
4. **LLM-modelprofielbeheer** (`/v1/admin/profiles`).
5. **Tokenbudget** (`/v1/verbruik/*`, `/v1/admin/budget`, `/v1/admin/verbruik`).
6. **Berichten** (release notes, `/v1/berichten/*` + `/v1/admin/berichten/*`) met leesbewijzen per
   (bericht, gebruiker), en **gebruikersfeedback** (`/v1/feedback` + `/v1/admin/feedback/*`).
7. **Werkgebieden** (`/v1/werkgebieden/*`, spoor D levering 1): benoemde analyses met
   bronselecties en een inventaris van de geannoteerde elementen – zie §*Werkgebieden*.
8. **Begrippen** (`/v1/werkgebieden/{id}/begrippen/*`, spoor D levering 2): begrippen per werkgebied
   met koppelingen naar annotatie-elementen, beoordeling, revisies en export – zie §*Begrippen*.
9. **Voorstellen van Lex** (`/v1/werkgebieden/{id}/begrippen-runs/*`, `…/groepen/*`, levering 3a):
   het manifest voor de begrippenketen, runs en de betekenisgroepen – zie §*Voorstellen van Lex*.
10. **Lex naast de kaart** (`/v1/werkgebieden/{id}/begrippen/{begrip_id}/kaart-runs/*`, `…/voorstellen/*`,
   fase E): voorstellen per veld van een begrip en de besluiten erover – zie §*Lex naast de kaart*.
11. **Bronnen vinden met Lex** (`/v1/werkgebieden/{id}/bronnen-runs/*`, `…/kandidaten/*`, fase A):
   kandidaatbepalingen met rol en bewijs per ontdekmethode, en de besluiten erover – zie §*Bronnen
   vinden met Lex*.
12. **Onderhoud van begrippen** (`/v1/werkgebieden/{id}/herbeoordelingen`, `…/koppelingen/{k}/herkoppelen`
   en `/bevestigen`, `…/dekking/*`, fase F1): geraakte dragende passages, opvolgers na herannotatie en de
   dekking van het werkgebied – zie §*Onderhoud van begrippen*.
13. **Begripsrelaties en opvolging** (`/v1/werkgebieden/{id}/relaties/*`, `…/begrippen/{b}/nieuwe-betekenis`
   en `/combineren`, fase F2) – zie §*Begripsrelaties en opvolging*.
14. **Begrippen naar de kennisgraaf** (`…/begrippen/export?formaat=ttl`, `…/begrippen/conformiteit`,
   `…/begrippen/samenhang`, fase F3): NL-SBB-projectie per werkgebied, conformiteit en Turtle-export –
   zie §*Begrippen naar de kennisgraaf*.
15. **Begrippen over werkgebieden heen** (`/v1/begrippen`, `/v1/begrippen/verifieer`, `/v1/begrippen/{id}`,
   fase F4): het overzicht in de webapp en de verificatie van wat Lex in de graaf vond – zie §*Begrippen
   lezen*.
16. **Deelvragen** (`/v1/werkgebieden/{id}/deelvragen/*`, vervolg op F): optionele deelvragen bij een
   werkgebied, voorstellen van Lex en de dekkingscheck per deelvraag – zie §*Deelvragen*.

> **De wettekst komt uit de graaf.** De API leest uit GraphDB de **bronboom** (`bron_resolver.py`):
> daarmee toetst hij ankers, legt hij snapshots vast en levert hij de segmenten van de weergave.

## Architectuur (`app/`)

| Module | Rol |
|---|---|
| `main.py` | Routers, `/health`, `/ready`, gzip voor grote antwoorden (`GZipMiddleware`, ≥1 kB; Starlette slaat `text/event-stream` over), lifespan: LLM-throttle, DB-init met bounded retry (`_init_db_met_retry`), seeding van profiel en budgetbeleid, start van de projectielussen als `GRAPHDB_URL` gezet is. |
| `config.py` | `Settings` uit de env; `_read_secret` leest `NAAM` of `NAAM_FILE`. |
| `db.py` | Async SQLAlchemy Core: engine en alle tabellen. Zie §*Schema*. |
| `deps.py` | `get_gesprek_store`. |
| `auth.py`, `api_tokens.py` | Client-bearer (`require_client`) en admin-bearer (`require_admin`). |
| `user.py`, `users.py`, `registraties.py`, `routers/auth.py` | Login, 2FA, zelfregistratie. |
| `llm_profile.py`, `profiles.py`, `secrets_crypto.py`, `llm/` | Modelprofielen, Fernet-versleuteling, LiteLLM-client, `llm/throttle.py`. |
| `verbruik.py`, `verbruik_contracts.py`, `routers/verbruik.py` | Tokenbudget. |
| `berichten.py`, `feedback.py` + routers | Release notes en feedback. |
| `gesprek_contracts.py`, `gesprek_store.py`, `routers/gesprekken.py` | Chatgeschiedenis. |
| `annotatie_v2.py` (router), `annotatie_v2_store.py`, `annotatie_v2_contracts.py`, `annotatie_v2_zoeken.py` | Het annotatiedomein. |
| `bron_resolver.py` + `packages/bronmodel` | Bronboom ophalen uit de BWB-named graph, snapshot bouwen, ankers valideren. `bronmodel` is een lokaal pakket dat de API en graph-qa delen (één bronidentiteit en ankerbasis). |
| `graaf_projectie_v2.py`, `vocabulaire/` | Projectie van de lagen naar GraphDB, en de JAS-vocabulaire. |
| `graafcontrole.py`, `shacl.py`, `shapes/jas-v2.ttl` | Controle achteraf: klopt de graaf met Postgres? |
| `samenhang.py` | Structuur, annotaties en verwijzingen van één artikel (of het overzicht van een structuurdeel), voor de graafweergave; de bouwstenen (`bronknoop`, `markeringen`, `verwijzingen`) deelt hij met `graaf.py`. |
| `graaf.py` | De complete graaf (`/graaf`): alle regelingen met structuur, verwijzingen en markeringen; structuur en verwijzingen gecachet per `(bwb_id, toestandUrl)`. |
| `knoopinfo.py` | Wat de kennisgraaf over één knoop weet (`/knoop`), voor de inspector van de graaf. |
| `werkgebieden.py` (router), `werkgebied_store.py`, `werkgebied_contracts.py`, `werkgebied_inventaris.py`, `werkgebied_werkvoorraad.py` | Werkgebieden: bronselecties, revisies, audit, de inventaris en de annotatie-werkvoorraad. |
| `werkgebied_deelvragen.py` | Deelvragen: opslag, voorstellen van Lex, koppelingen en de dekkingscheck. |
| `begrippen.py` (router), `begrip_store.py`, `begrip_contracts.py` | Begrippen: inhoud, koppelingen met bewijsstand, actualiteit, de accorderingspoort, revisies en export. |
| `begrippen_runs.py` (router), `begrippen_run_store.py`, `begrippen_run_contracts.py`, `begrip_manifest.py` | Voorstellen van Lex: manifest voor de begrippenketen, runs, betekenisgroepen en besluiten. |
| `begrip_voorstellen.py` (router), `begrip_voorstel_store.py`, `begrip_voorstel_contracts.py` | Lex naast de kaart: kaartruns en voorstellen per veld, overnemen en afwijzen. |
| `bronnen_runs.py` (router), `bronnen_run_store.py`, `bronnen_run_contracts.py` | Bronnen vinden met Lex: runs van de ontdekmethoden, kandidaatbepalingen en hun besluiten. |
| `begrip_onderhoud.py` (router), `begrip_onderhoud_store.py`, `begrip_onderhoud_contracts.py` | Onderhoud van begrippen: herbeoordelingen, opvolgers, herkoppelen, bevestigen en dekking. |
| `begrip_relaties.py` (router), `begrip_relatie_store.py`, `begrip_relatie_contracts.py` | Begripsrelaties (voorstellen uit de keten, vastleggen, afwijzen, doorwerking) en opvolging: nieuwe betekenis, combineren. |
| `begrip_projectie.py`, `shapes/nl-sbb-1.0.0.ttl`, `shapes/begrippen-wa.ttl` | Begrippen naar de kennisgraaf (NL-SBB), conformiteit per begrip en de Turtle-export. |
| `begrippen_overzicht.py` (router) | Begrippen over werkgebieden heen: zoeken, verifiëren voor Lex, één begrip. |
| `annotatie_statistiek.py`, `scripts/statistiek.py` | Reviewstatistiek over de elementen: uitkomst per klasse en per model, klasse-verschuivingen, aandacht tegenover correctie. |
| `jas_klassen.py`, `validation.py` | De dertien JAS-klassen, volgorde en kleuren (canoniek); `GELDIGE_JAS_KLASSEN`, `JAS_KLASSE_KLEUREN`, `jas_sorteersleutel`. |
| `ratelimit.py` | In-process rate limit per client. |
| `observability.py` | JSON-logging en OpenTelemetry. |

## Annotaties: bronnodes

De specificatie is [`docs/architectuur/annotatie-bronnodes.md`](../docs/architectuur/annotatie-bronnodes.md)
(ankers, dekkingsregels, leestools, uitvoeringsspoor); het RDF-model staat in
[`docs/wetsanalyse-workbench/jas-annotatie-ontologie.md`](../docs/wetsanalyse-workbench/jas-annotatie-ontologie.md).
Hieronder wat je moet weten om de code te wijzigen.

- **Een laag hoort bij één canonieke bron-IRI** – een artikel, een lid of een onderdeel. Lagen zijn
  **gedeeld**, niet per gebruiker: wie wat deed staat in `annotatie_v2_audit` en in de beslissingen
  op het element. Elke route vraagt wel een actieve gebruiker (`actieve_userid`).
- **Postgres is de waarheid, RDF een herbouwbare projectie.** Tabellen: `annotatie_v2_state`,
  `_snapshots`, `_lagen`, `_elementen`, `_batches`, `_dekking`, `_audit`.
- **Eén globaal schrijfslot.** `annotatie_v2_store.schrijftransactie` neemt een rij-lock op
  `annotatie_v2_state` (id 1) en serialiseert zo alle kleine schrijfacties, ook over processen en
  replica's heen. Geen process-local locks.
- **Revisies en snapshots.** Elke laag draagt een revisie; schrijfacties sturen
  `verwachte_revisies` mee en krijgen **412** bij een tussentijdse wijziging. Elke schrijfactie legt
  de snapshot van de bronboom vast; een beslissing of export tegen een andere bronstand geeft
  **409**.
- **Revisiehistorie.** `schrijftransactie` houdt bij welke lagen `_raak` raakte en welke
  auditregels er vielen, en schrijft ná de laatste mutatie (vóór de commit) per laag één regel
  `revisie` met `laag_id` in een eigen kolom. `GET lagen/{laag_id}/revisies` leest alleen die regels.
  Een geweigerde mutatie (409/412) schrijft er dus geen. Geef `_audit` een `laag_id` mee waar de
  regel bij één laag hoort; een regel zonder laag (de `batch`) telt bij elke laag van de transactie.
- **Grenskeuze** (`type: "grens"`, `wijziging: {"optie": i}`): de jurist kiest een van de
  grensopties die de keten voorstelde (`trace.kandidaat.spanopties`). De client stuurt alleen de
  index; `_grens_wijziging` rekent het anker uit de brontekst en daarna loopt het als een `edit`
  (validatie, eigenaar, `edited`, slot). De beslissing legt `voor` en `nieuw` vast.
- **Batches zijn idempotent** op `batch_id` plus payload (`POST lagen/batch`). Een eigen markering
  van de jurist (`POST elementen`) loopt door hetzelfde pad met `mens=True`.
- **De API toetst ankers zelf** (`annotatie_v2_store.valideer`): klasse bestaat, fragment niet
  leeg, elk anker valt binnen het gevraagde bereik, `tekst[start:eind]` van de bronnode is exact het
  ankerfragment en de `bron_hash` klopt, geen dubbele ankers, en de elementtekst is de
  ankerfragmenten in volgorde. De eigenaar van het element volgt uit de ankers
  (`bronmodel.valideer_ankers`), niet uit wat de client zegt.
- **Verouderd.** Wijkt de hash van een geankerde bronnode af van de actuele bron, dan is het
  element verouderd: alleen-lezen (409), telt niet mee bij afronden. De lifecycle blijft staan als
  historie.
- **Een oordeel vergrendelt.** Een element in `human_approved`/`rejected`/`published` dat van de
  agent komt of al beslissingen draagt, accepteert alleen `comment` en `heropen`
  (`annotatie_v2_store.beslis`). Afronden (`zet_status` → `geaccordeerd`) kan pas als elk actueel
  element beoordeeld is en de bron niet veranderde.
- **Wissen van één element** (`DELETE elementen/{id}`) mag alleen voor een eigen, nog niet
  beoordeelde markering.
- **Verwijderen van de bepaling in beeld mag iedereen** (`POST weergave/verwijder`,
  `annotatie_v2_store.verwijder_weergave`): alle lagen op het doel en de bronnodes eronder, met hun
  elementen, in één transactie onder het schrijfslot en met de revisietoets (412).
  - **De dekking gaat mee**, anders leest Lex de bepaling bij de volgende beurt als "al
    geannoteerd". Een dekkingsrij van een ruimere bepaling houdt haar bereik buiten deze scope en
    verliest `voltooid`.
  - **Een element van een ruimere laag blijft staan.** Valt het met één anker in deze bepaling, dan
    is het daar een verwijzing, geen eigendom.
  - **De audit blijft**: per laag een regel `laag-verwijderd` naast de bestaande regels. Daaruit
    leest de weergave `verwijderd: {op}`, zodat een heropend gesprek "verwijderd" toont in plaats
    van een leeg paneel.
  - **Geen afhankelijkheid van de brongraaf.** De route neemt de bewaarde snapshot
    (`historische_snapshot`); alleen een bronstand die nooit is weggeschreven wordt opnieuw
    opgehaald, en die geeft 409 als hij intussen veranderde.
  - **De graaf direct, de lus als vangnet**: na de commit `graaf_projectie_v2.verwijder_projecties`
    (DROP van de graph plus de registerregels). Hapert GraphDB, dan meldt de respons
    `graaf: "volgt"` en ruimt `verwijder_verweesde_projecties` de wees bij de volgende ronde op.
- **Zoeken** (`annotatie_v2_zoeken.zoek`) haalt kandidaten uit de graaf en **verifieert ze tegen
  Postgres** (manifest van lagen en revisies). Elk filter staat dus twee keer: in `zoek_query`
  (SPARQL) en in de Python-controle – ook de herkomstfilters `herkomst`, `aandacht`, `subtype`,
  `beslist_door` en `met_twijfel` (`_past_herkomst`). `tools/graph-qa/tests/test_contract_drift.py`
  bewaakt dat het toolschema van `search_annotaties` niets vraagt wat `Zoekvraag` niet kent. Een storing of een achterlopende projectie is nooit
  een leeg, succesvol resultaat: de respons draagt `volledig`.
- **Bronboom** (`bron_resolver.resolve_bron`): leest alleen de expliciete BWB-named graph, nooit
  een union met de annotatiegraphs. Zonder `GRAPHDB_URL` of bij een haperende GraphDB geeft de
  router 503; een ongeldige bron-IRI 422.
- **`/verklaringen`** levert `vocabulaire/verklaringen.json`: leesbare namen voor alles wat in een
  `trace` kan staan. Dat bestand en `vocabulaire/jas-vocabulaire.ttl` worden **gegenereerd** door
  `tools/graph-qa/scripts/genereer_jas_vocabulaire.py`; bewerk ze niet met de hand.
  `tests/test_vocabulaire.py` bewaakt dat elke klasse van de API een concept heeft.
- **Export** (`POST weergave/export`, `annotatie_export.py`): `json` (v3, schema in
  `schemas/annotatie-export-v3.schema.json`, ook op `GET export-schema`), `csv`, `pdf` en `trig`.
  `herkomst_regels` zet het spoor om in de leesbare namen uit `verklaringen.json`, met dezelfde
  opzoekregels als `frontend/lib/waarom.ts`. De oude CSV-kolommen blijven vooraan staan; nieuwe komen
  erachter. TriG bouwt per laag met `laag_invoer` + `bouw_graaf`, dus exact wat de projectie schrijft.
- **`/samenhang`** (`samenhang.py`) geeft drie soorten relaties en niets anders: de bronboom, de
  letterlijke verwijzingen uit de BWB-import (één stap in en uit, max. `MAX_VERWIJZINGEN`) en de
  actuele markeringen. Er wordt niets afgeleid. Een markeringsknoop draagt herkomst, aandacht,
  subtype, `beslist_door` en `twijfel` uit het element, zodat de werkplek erop kan filteren. Is het
  doel een **structuurdeel** (hoofdstuk, titeldeel, afdeling, paragraaf), dan is het een overzicht: het
  deel met de structuur en artikelen eronder, zonder leden, onderdelen, markeringen en verwijzingen
  (die horen bij een geopend artikel; anders wordt een hoofdstuk een kluwen van honderden knopen).
  **`/samenhang/meer`** (hoogstens 30 `bron_iri`'s) geeft de samenhang van meerdere doelen in één
  verzoek en haalt per regeling de bronboom één keer op (`bron_resolver.haal_bronrijen` +
  `snapshot_uit`); een doel dat niet resolvet staat in `fouten`. Een overzicht opent zo 15 delen met 4
  bronbomen in plaats van 15.
  **`/graaf`** (`graaf.py`, `bwb_id` herhaalbaar, leeg = alle) levert de complete graaf in dezelfde
  `Knoop`/`Relatie`-vorm, zonder tekst (≈2 MB JSON voor alles, gzip). Structuur (`haal_bronrijen`) en
  uitgaande verwijzingen (uit de named graph van de regeling, zonder LIMIT) staan per proces in een
  cache onder `(bwb_id, bwb:toestandUrl)`: een herimport met een nieuwe toestand ververst vanzelf.
  Markeringen komen altijd vers (`store.actuele_elementen`). `versie` = hash van de toestanden; daarop
  cachet de werkplek de layout. Een BWB-id gaat letterlijk een query in en wordt strikt gevalideerd.
  Het label van een deel krijgt zijn nummer (`_label`: de bronboom draagt "Hoofdstuk" en "II" apart);
  bewust hier en niet in `bronmodel`, waar het de snapshot-identiteit van bestaande lagen zou raken.
  **`POST /plaatsen`** (`graaf.plaatsen`, hoogstens 500 `bron_iris`) geeft per bepaling de regeling en het pad
  eronder (hoofdstuk/afdeling/divisie › artikel › lid › onderdeel) met `_label` en `volgorde`, om in de
  werkplek te groeperen (spoor H). De structuur per regeling staat in een eigen cache op `(bwb_id,
  toestandUrl)` (`_structuur`) die `/graaf` deelt; een onbekende IRI krijgt `pad: []`. Alleen het BWB-id gaat
  een query in.
  **`/knoop`** (`knoopinfo.py`, `bron_iri`) geeft wat de BWB-import en de WTI-verrijking verder aan
  één knoop hangen, letterlijk en zonder afleiding: de bekende predicaten in vaste groepen met een
  Nederlandse naam (`FEITEN`: geldigheid – ook die van de regeling erboven –, herkomst, regeling,
  grondslag en bevoegdheid – ook inkomend `heeftGrondslag` –, genoemd in, begrip, vindplaats), de
  `bwb:Verwijzing`-knopen van en naar de knoop (soort, soort doel, pad, betrouwbaarheid: wat een lijn
  in de graaf niet draagt), en **alle** uitgaande triples ruw, zodat er nooit iets ontbreekt. Een
  nieuw predicaat verschijnt dus eerst alleen ruw; geef hem een plek in `FEITEN`. De IRI gaat
  letterlijk een query in en moet `samenhang._IRI` volledig matchen (422); een haperende graaf 503.

### Projectie naar de kennisgraaf

`graaf_projectie_v2.py`. Named graph `urn:jas:graph:v2:<laag-id>`, register
`urn:jas:graph:register:v2`. De API is de enige schrijver onder `urn:jas:`; graph-qa leest alleen.

- **Direct na de commit.** Elke laagwijziging loopt via `_raak`, die de laag op de verbinding
  noteert; `schrijftransactie` roept ná een geslaagde commit `na_mutatie` aan, die op de achtergrond
  projecteert. Een geweigerde mutatie (409/412) projecteert dus niets, en een haperende GraphDB laat
  de beslissing van een jurist niet falen.
- **De lus is het vangnet** (`lus`, interval `JAS_PROJECTIE_INTERVAL`). `reconcile` vergelijkt de
  revisies die **in de graaf** staan met Postgres, zodat ook een lege GraphDB na een herstart wordt
  opgemerkt en opnieuw gevuld, ruimt verweesde projecties op (na een hercontrole onder het
  schrijfslot) en zet de vocabulaire neer als die ontbreekt. Elke tiende ronde logt hij de lichte
  graafcontrole (`annotatie_graaf_afwijking`, voor Grafana).
- **`projecteer`** neemt een rij-lock op de laag en een lock per laag in het proces, en schrijft
  `geprojecteerd_revisie` pas na een geslaagde `PUT` plus registerupdate.
- **Invarianten** (getest, en gecontroleerd door `graafcontrole.py`): geen subject onder `urn:bwb:`,
  geen `urn:bwb-ns:`-predicaat en geen schema-axioma's (domain/range/subClassOf/sameAs) in een
  `urn:jas:graph:*`. Anders duikt een annotatie op als wettekst in de queries, de similarity-index of
  de bronnencontrole van Lex.
- **Herkomst in RDF.** `bouw_graaf` zet per element een `prov:Activity` voor de run (model als
  `prov:SoftwareAgent`) en de beoordelingen erbij.
- **Graafcontrole per laag** (`graafcontrole.controleer_laag`, via `GET /v1/annotatie/elementen/{id}/graaf`
  voor elke actieve gebruiker): dezelfde toetsen als hieronder voor één laag (`_controleer_laag` is
  gedeeld), zonder verweesde graphs en invarianten. Het endpoint geeft er de Turtle van het element
  bij, gebouwd met `bouw_graaf` – het technisch detail in de werkplek.
- **Graafcontrole** (`GET /v1/admin/annotatie/graafcontrole`, alleen lezend): consistentie
  (register, revisies, verweesde graphs), bouw (opgehaalde graph isomorf met `bouw_graaf` uit de
  Postgres-stand), SHACL per niveau (`rdf`/`jas_model`) en de invarianten. Een laag die nog niet
  geprojecteerd is heet achterstand, geen afwijking. Een onbereikbare graaf levert
  `graaf_beschikbaar: false` en `in_orde: null`, nooit "in orde". SHACL draait nooit in het
  schrijfpad; zonder pyshacl geeft `shacl.valideer` `beschikbaar: False`.

### Reviewstatistiek

`annotatie_statistiek.rapport` telt over element-dicts wat juristen met de voorstellen deden: de
zwaarste beslissing per element, per klasse en per model (`geproduceerd_door`), de
klasse-verschuivingen (uit `voor` en `wijziging` van een edit – `beslis` legt `voor` daarvoor vast)
en per aandacht-niveau hoe vaak de jurist corrigeerde. Twee ingangen op dezelfde functie:
`GET /v1/admin/annotatie-statistiek` (de `limit` laatst gewijzigde lagen, achter het admin-token
omdat het een meting van de agent is) en `scripts/statistiek.py` over JSON-exports. Aggregeren
gebeurt in Python, want de elementen staan als JSON en de tests draaien op SQLite.

## Werkgebieden

`werkgebieden.py`, `werkgebied_store.py`, `werkgebied_inventaris.py`; het ontwerp staat in PLAN
spoor D (*Werkgebied als node*).

- **Gedeeld**, zoals de annotaties: elke actieve gebruiker ziet en wijzigt alle werkgebieden; wie
  wat deed staat in `werkgebied_audit` (alleen inserts).
- **Eén schrijfpad per mutatie** (`werkgebied_store._gewijzigd`): rij-lock op het werkgebied
  (`FOR UPDATE`), `verwachte_revisie` → 412 `{fout: "revisie_conflict", revisie}`, revisie +1,
  auditregel. Het annotatieslot (`annotatie_v2_state`) blijft erbuiten: een werkgebied schrijft
  geen annotaties.
- **Aanmaken vanuit het gesprek is idempotent** (activiteit 1): graph-qa stuurt de `intake_id` mee,
  en een tweede `POST` met dezelfde id geeft hetzelfde werkgebied terug (unieke index
  `ux_werkgebieden_intake`; de race tussen replica's vangt de `IntegrityError`). Zonder `intake_id`
  is elk verzoek een nieuw werkgebied.
- **Het dossier** (spoor F, F2): naast naam, analysevraag en afbakening draagt een werkgebied
  `aanleiding`, `context` en `doel` (startactiviteit a van de Leidraad) en een `praktijkvoorbeeld`
  (activiteit 1b), elk vrije tekst; wijzigen loopt door hetzelfde schrijfpad. Bij het aanmaken mogen
  `deelvragen` (`{vraag, herkomst: analist|lex}`) mee: actief, op volgorde, één keer per genormaliseerde
  vraag, in dezelfde transactie; de auditregel `aangemaakt` telt ze. Lex gebruikt dit dossier als
  context voor elk voorstel (graph-qa).
- **Een bronselectie wordt geverifieerd** via de bronresolver (`bron_iri`, of `bwb_id` + `artikel`
  (+ `lid`)); de canonieke `bron_iri`, het label, `snapshot_id` en `bron_hash` worden bewaard.
  Dezelfde bron met dezelfde rol en hetzelfde bereik opnieuw toevoegen is idempotent (200, geen
  revisiesprong); met een andere rol of ander bereik 409.
- **De lijst** (`GET /v1/werkgebieden`) met `mijn=true` geeft alleen werkgebieden met een auditregel
  van deze gebruiker (*Door mij bewerkt* in de webapp, zoals bij de annotaties). Met `bron_iri` alleen de
  werkgebieden met een actieve selectie die die bepaling omvat (`werkgebied_store.omvat`: de bepaling zelf,
  of bij `onderliggend` een bronnode eronder volgens het pad van de IRI) – voor de bronpagina (spoor G3).
  Een selectie op een structuurdeel draagt de artikelen niet in haar pad en mist deze toets: liever een
  gemiste dan een verkeerde.
- **Een selectie weghalen is soft** (een tijdstip). De annotaties van de bron blijven altijd staan.
- **Een werkgebied verwijderen is echt wissen**, net als een annotatie (`DELETE /v1/werkgebieden/{id}`,
  `werkgebied_store.verwijder`/`wis`): onder het rij-slot en met de revisietoets (412) gaan het werkgebied
  en elke rij in `WERKGEBIED_TABELLEN` weg, plus de begriprevisies en de deelvraagkoppelingen via hun
  ouder. **De audit blijft**, met een laatste regel `werkgebied-verwijderd`; via `_audit` volgt de
  begrippengraaf (geen werkgebied → DROP van de graph). De annotaties blijven: die horen bij een
  bronnode. De `intake_id` is daarna weer vrij. Een nieuwe tabel met `werkgebied_id` (of `begrip_id`)
  hoort in de wislijst; `tests/test_werkgebied_verwijderen.py` faalt anders – behalve `gesprekken`: die
  worden los (`werkgebied_id = ""`), niet gewist, want een gesprek is een verslag van de gebruiker. Archiveren bestaat niet
  meer: oude gearchiveerde rijen blijven onzichtbaar (`gearchiveerd` geeft 404), maar worden niet
  automatisch gewist.
- **Een verwijderd object zegt wanneer en door wie.** `GET` op een verwijderd werkgebied of begrip
  geeft `404 {fout: "verwijderd", soort, op, door, melding}` uit de audit (`niet_gevonden`; ook voor
  oude gearchiveerde werkgebieden en soft verwijderde begrippen); een id dat nooit bestond blijft een
  gewone 404. De werkplek toont dan "… is verwijderd op … door …", zoals bij een annotatie.
- **De inventaris** (`GET {id}/elementen`) leest per regeling één bronboom en de actuele
  elementen. Elk element staat één keer in de inventaris; `analyseren` wint van `context`;
  `deels_buiten` als een anker buiten de selecties valt; afgewezen elementen worden alleen geteld.
  Per selectie is `bron_gewijzigd` een signaal, geen ongeldigverklaring. Een onbereikbare bron geeft
  `onbereikbaar` en `volledig: false`, nooit een stil kleinere inventaris.
- **De annotatie-werkvoorraad** (`GET {id}/annotatie-werkvoorraad`, `werkgebied_werkvoorraad.py`,
  fase B) zegt wat Lex nog moet annoteren. Alleen selecties met rol *analyseren*; contextbronnen
  worden geteld. De eenheden volgen `bronmodel.annotatie_eenheden` – de regel van de keuzekaart, dus
  een artikel met leden per lid – en staan elk één keer. De stand per eenheid komt uit Postgres
  (lagen, elementen, dekking): `afgerond`, `te_beoordelen`, `beoordeeld`, `zonder_markeringen`
  (geannoteerd, niets gevonden – telt dus niet als nieuw) of `nieuw`; `te_annoteren` is de lijst
  `nieuw`. De schatting is de mediaan van het verbruik van de laatste 20 annotatiebeurten van de
  gebruiker (run met een annotatie-artefact of `annotatie_doel`) keer het aantal; zonder geschiedenis
  `null`, nooit een verzonnen getal. Een onbereikbare bron: `volledig: false` plus een open punt.
  **Het bereik** (`?bereik=werkgebied|deelvragen[&deelvraag_id=]`, default het hele werkgebied): met
  `deelvragen` alleen de selecties die aan de actieve deelvragen gekoppeld zijn (`selecties_in_bereik`;
  een selectie onder meer deelvragen telt één keer), met `deelvraag_id` die van één. De respons draagt dan
  `bereik`, `deelvragen` (`{id, vraag, selecties}`) en `buiten_bereik` (analysebronnen die niet meegaan).
  `deelvraag_id` zonder `bereik=deelvragen` 422; een onbekende deelvraag 404; een niet-actieve 409
  `niet_actief`; geen actieve deelvragen 409 `geen_deelvragen` (elk met `melding`).
- Tests: `tests/test_werkgebieden.py` en `tests/test_werkgebied_werkvoorraad.py` (SQLite) en
  `tests/test_werkgebieden_postgres.py` (het rij-slot, met `ANNOTATIE_TEST_DSN`).

## Begrippen

`begrippen.py`, `begrip_store.py`, `begrip_contracts.py`; het ontwerp staat in PLAN spoor D
(*Elementen, groepen en begrippen*, *Datamodel*).

- **Een slank begrip volgens NL-SBB** (spoor I1, `BegripInhoud`): naam, alternatieve termen,
  definitie, uitleg (`rdfs:comment`), context (de *toelichting*, `skos:scopeNote`) en voorbeelden
  (tekst + oordeel). JAS-duiding, begripstype, geldigheid, eigenschappen, onderbouwing en open vragen
  bestaan niet meer; een oude rij verliest ze bij het lezen (`begrip_store.slank`, `extra="ignore"`).
  **De herkomst kiest niemand**: `begrip_store.met_afgeleid` rekent bij elke schrijfactie herkomst en
  `definitie_door` – een ongewijzigde definitie houdt ze, een nieuwe of andere tekst is `geformuleerd`
  door de `analist`, geen definitie heeft geen herkomst. Letterlijk wordt een definitie alleen door een
  overgenomen brondefinitie (kaartvoorstel of het akkoord op een groep).
- **Eén kader per werkgebied, impliciet.** Een begrip hangt aan een werkgebied; het kader heeft geen
  tabel, alleen een afgeleide IRI (`urn:wa:kader:<werkgebied>`). Begrippen zijn analyse-uitkomsten,
  nooit wettelijke definities; de export zegt dat ook.
- **Tabellen**: `begrippen` (inhoud als JSON, status `concept`/`geaccordeerd`, revisie),
  `begrip_revisies` (per revisie een **volledige kopie** van de inhoud, plus actie en detail – anders
  dan bij de annotatielagen bewaren we de oude inhoud wél) en `begrip_koppelingen`. De audit gaat in
  `werkgebied_audit` (acties `begrip-*`, `koppeling-*`), zodat het werkgebied één tijdlijn heeft.
- **Eén schrijfpad** (`begrip_store._gewijzigd`): eerst de rij-lock op het werkgebied, dan die op het
  begrip – altijd in die volgorde, anders kunnen twee transacties elkaar vastzetten. Daarna
  `verwachte_revisie` → 412, revisie +1, revisiekopie en auditregel. De revisie van het werkgebied gaat
  niet omhoog: die gaat over de scope. Zonder echte wijziging (dezelfde inhoud, een element dat al
  gekoppeld is) gebeurt er niets, ook geen revisie.
- **Elke mutatie behalve accorderen maakt een geaccordeerd begrip weer een concept** – met één
  uitzondering: herkoppelen en bevestigen (fase F1) laten de inhoud staan en het begrip geaccordeerd.
  Een **vervangen** begrip (fase F2) is alleen-lezen: elke mutatie 409 `vervangen`.
- **Een 412 draagt een `melding`**, net als de 409's (`al_primair`, `al_gekoppeld`, `poort`): de
  werkplek toont die tekst waar hij de fout niet zelf afhandelt, in plaats van ruwe JSON. Dat geldt ook
  voor de werkgebieden.
- **Per begrip één koppeling per element en rol.** Bij koppelen idempotent; een rol ombuigen naar een
  rol die dat element bij dit begrip al heeft geeft 409 `al_gekoppeld`. Een wijziging die niets
  verandert, is geen revisie.
- **Een koppeling draagt haar bewijsstand** (tekst, klasse, ankers met `bron_hash`, eigenaar, laag,
  snapshot, vindplaats, `element_hash`). Annotatie-elementen worden **hard** verwijderd
  (`annotatie_v2_store.verwijder`/`verwijder_weergave`), dus er is geen foreign key en geen cascade.
  Koppelen kan alleen met elementen uit de inventaris van het werkgebied (`bewijzen`: actueel, niet
  verworpen, binnen de selecties; anders 422 `element_buiten_werkgebied`). Dat vraagt de graaf, en
  gebeurt dus vóór de schrijftransactie.
- **Actualiteit bij het lezen**, uit Postgres zonder graaf: `actueel`, `gewijzigd` (`element_hash`
  over tekst, klasse, subtype en ankers wijkt af, of het element is verouderd; een oordeel van een
  jurist telt niet als wijziging), `verworpen` of `verdwenen`. Plus `annotatie_beoordeeld`
  (lifecycle `human_approved`/`edited`/`published`).
- **Eén primaire duiding per element per werkgebied**: een tweede `duiding` van hetzelfde element
  aan een ander begrip geeft 409 `al_primair` (met de naam van dat begrip). Ook bij het ombuigen van
  een rol. Het werkgebiedslot maakt dit race-vrij; `GET …/begrippen` geeft per element het primaire
  begrip mee (`primair`).
- **De poort** (`begrip_store.poort`) staat bij elke GET als `accorderen: {mag, redenen}`; accorderen
  zonder geeft 409 `{fout: "poort", redenen}`. Voorwaarden: definitie, toelichting (`context`),
  minstens één aanduidende passage, en elke dragende koppeling (`duiding`/`definitie`, niet
  afgewezen) beoordeeld, actueel en op een door een jurist beoordeelde annotatie. Een voorbeeld is
  geen voorwaarde. Elke analist mag accorderen; de revisie en de audit leggen vast wie.
- **Verwijderen is echt wissen** (`DELETE …/begrippen/{id}`, `begrip_store.verwijder`/`wis_begrippen`):
  het begrip met zijn revisies, koppelingen, relaties (beide richtingen), voorstellen en kaartruns
  (`BEGRIP_TABELLEN`), en zijn plek bij de deelvragen; een betekenisgroep houdt haar uitkomst en verliest
  alleen `begrip_id`. Eerst zet `_herstel_voorgangers` een vervangen voorganger terug. De audit
  `begrip-verwijderd` blijft. Een vervangen begrip zelf gaat niet weg (409: verwijder de opvolger).
- **Export** (`GET …/begrippen/export?formaat=json|csv|ttl`; Turtle zie §*Begrippen naar de kennisgraaf*): JSON (`begrippen-export-v1`) met de
  volledige begrippen en koppelingen. CSV heeft één rij per koppeling met vindplaats en bron-IRI, zodat
  elke passage terug te vinden is; cellen krijgen dezelfde formuleverdediging als de annotatie-export.
- Tests: `tests/test_begrippen.py` (SQLite, met de acceptatie uit PLAN) en
  `tests/test_begrippen_postgres.py` (de sloten, met `ANNOTATIE_TEST_DSN`).

## Voorstellen van Lex

`begrippen_runs.py`, `begrippen_run_store.py`, `begrip_manifest.py`; het ontwerp is ADR-004 en
PLAN spoor D (*Verwerking*). De keten zelf draait in graph-qa (`agent/begrippen_run.py`); de api
bouwt de invoer, toetst en bewaart de uitkomst, en legt de besluiten vast.

- **Het manifest** (`begrip_manifest.bouw`) komt uit dezelfde inventaris als de tab Elementen
  (`inventaris_met_bronbomen`), dus met contextbronnen: een definitie buiten de analyseselectie
  hoort juist mee. Vorm = `Bron`/`Formulering` van `begrippen_pipeline.model`; `aanhef` is de tekst
  van de directe ouder (de houder: "Deze wet verstaat onder:"), `label` de vindplaats. Een element met
  meer dan één anker, of dat verouderd is, staat in `overgeslagen` met reden – nooit stil weg.
- **`manifest_id` rekent zoals `Manifest.id`.** Twee diensten, dus geen import:
  `docs/wetsanalyse/referentieset-begrippen/manifest-id.vectoren.json` legt id's en veldnamen vast,
  en zowel `tests/test_begrippen_runs.py` als graph-qa `tests/test_begrippen_manifest_drift.py`
  toetsen ertegen. Wijzigt het model van de keten, laat de vectoren dan door de keten herberekenen.
- **Runs zijn idempotent op (werkgebied, manifest)**: een tweede start geeft de bestaande run (200,
  `nieuw: false`). Een run in `wacht`/`loopt` die `VERLOPEN` (5 min) niets van zich liet horen, telt
  als `mislukt` en mag opnieuw; graph-qa meldt `…/loopt` bij de start. Een onvolledige inventaris of
  minder dan twee passages: 409 met melding, geen run.
- **De uitkomst wordt getoetst** (`PUT …/uitkomst`): zelfde `manifest_id`, en elk genoemd element-id
  staat in het manifest (422 `onbekend_element`). Dezelfde uitkomst nog eens is idempotent; een andere
  op een klare run 409. `…/uitkomst`, `…/loopt` en `…/mislukt` zijn voor graph-qa; de BFF laat ze niet
  door.
- **Een besluit hoort bij de groep** (`betekenisgroepen`, sleutel werkgebied + groep-id = de inhoudshash
  van de keten). Komt dezelfde groep in een latere run terug, dan blijft een afwijzing staan.
- **Overnemen** (`POST groepen/overnemen`) maakt één begrip (concept) met de gekozen leden als
  `duiding` – meer groepen is combineren, een deel van de leden splitsen. De letterlijke
  brondefinitie gaat alleen mee als er precies één is (herkomst `letterlijk`). Zonder kaart komt de
  context uit de vindplaatsen (`context_uit`, de tweeling van graph-qa `kaart._context`; een
  drift-test in `test_begrippen_akkoord.py` bewaakt de zin). Een passage buiten de gekozen groepen mag
  mee (het antwoord *samen* op een twijfelvraag), mits ze in het manifest van de laatste klare run
  staat; `groep_ids` mag dan leeg zijn. Uit elke gekozen groep moet minstens één eigen passage mee.
  `lijkt_op` per groep: begrippen die een passage delen of de voorgestelde naam als naam of
  alternatieve term dragen.
- **Akkoord** (`POST groepen/akkoord`, fase D) is overnemen plus het oordeel van de jurist, in **één
  transactie** (`_neem_over`): begrip, koppelingen met `beoordeling: akkoord`, accorderen als de poort
  het toelaat (`begrip_store.accordeer_in`), groepsbesluit en – met `kandidaat_id` of `kandidaat_ids`
  (spoor H4: alle vragen tussen de gekozen passages van een term, ≤ 500) – de twijfelvragen als *samen*.
  Een onbekende vraag is 404; een vraag waarvan een kant niet bij de gekozen passages hoort 422
  `vraag_buiten_keuze`. Antwoord `{begrip, geaccordeerd, poort}`: lukt accorderen niet, dan blijft het een
  concept en noemt de poort wat er openstaat. Met `aanpassing` wijzigt de jurist naam, definitie,
  context of alternatieve termen; een gewijzigde definitie wordt `geformuleerd` (een herkomst kiezen kan
  niet meer, spoor I1). Bij combineren kiest `definitie_van` welke
  groep zijn definitie en kaart meegeeft. Een tweede akkoord geeft 409 `al_besloten` met
  `begrippen: {groep: begrip}`.
- **Splitsen laat de rest staan.** Worden niet alle leden van een groep een begrip, dan blijft de
  groep open met de overige leden (kolom `afgehandeld`); pas als alle leden zijn afgehandeld is ze
  `overgenomen` of `gekoppeld`. Een afgehandelde passage nog eens kiezen geeft 409.
- **Koppelen** aan een bestaand begrip (`POST groepen/{id}/koppelen`) gaat langs hetzelfde pad, in
  één transactie; met `akkoord: true` zijn de koppelingen beoordeeld en wordt een geaccordeerd begrip
  opnieuw geaccordeerd als de poort het toelaat.
- `GET …/groepen` geeft per open groep **`poort_vooraf`**: de poort op de inhoud en de koppelingen
  zoals een akkoord ze nu zou maken. Per passage staat de stand van de annotatie nú
  (`lifecycle`, `annotatie_beoordeeld`), want het manifest is de stand bij de run.
- **Sloten**: altijd eerst het werkgebied, dan de groepen, dan het begrip. De `*_in`-varianten in
  `begrip_store` (`maak_in`, `koppel_in`, `accordeer_in`, `_gewijzigd_in`) draaien in de transactie
  van de aanroeper.
- Besluiten en runs komen in `werkgebied_audit` (`begrippen-run-gestart`, `begrippen-voorgesteld`,
  `groep-*` – waaronder `groep-akkoord` met `geaccordeerd` en de aangepaste velden –,
  `vraag-beantwoord`). Een besluit wijzigt nooit annotaties.

**De verdieping** (`begrippen_verdieping.py`, fase C): het model op twijfelparen en kaarten, bovenop de
laatste klare run. graph-qa rekent (`agent/begrippen_verdieping.py`), de api bewaart en toetst.

- `GET …/verdieping` is de **werkvoorraad**: twijfelvragen (behalve `Z-RELATIE-GAAT-VOOR`) en groepen
  zonder definitie, min wat in een klare batch zit; plus de klare batches, een schatting (mediaan
  tokens per item over de laatste 20 batches van de gebruiker; anders `null`) en het budget. `aantal`
  is wat een `bevestiging` (`soort: "begrippen_verdiepen"`) noemt.
- `PUT …/begrippen-runs/{run}/batches/{batch_id}` bewaart **één afgeronde batch** (`begrippen_batches`;
  alleen klare batches staan erin, dus een herstart doet de rest). Idempotent op (run, batch-id) +
  inhoud; een andere inhoud onder dezelfde id 409. Een vraagbatch noemt alleen twijfelvragen van de run.
- `PUT …/begrippen-runs/{run}/verdieping` zet de uitkomst: de groepen na hergroeperen (ook nieuwe,
  `door: model`) met hun kaart, de oordelen en de vragen die open blijven, in `begrippen_runs.verdieping`.
  Idempotent op inhoud; daarna geen batches meer.
- **De garanties toetst de api zelf** tegen het manifest (`garanties`, dezelfde codes als graph-qa
  `toetsen.garanties`): fragment-id volgt uit bron en offsets (`fragment_id`, zelfde hash), de tekst
  staat letterlijk op de offsets, een letterlijke definitie staat in haar bron, een samengestelde is
  precies haar fragmenten (`SCHEIDING`). Anders 422 `garantie` en wordt er niets bewaard.
- `GET …/groepen` geeft na de verdieping de groepen ná hergroeperen, plus elke groep van de keten met
  een besluit; per groep `door` en `kaart`, en bovenaan `verdieping` (open vragen, oordelen, model).
  `lijkt_op` kijkt ook naar de alternatieve termen van de kaart.
- **Overnemen** vult het begrip uit de kaart: alternatieve termen, context en de definitie met haar
  herkomst; de bron draagt het begrip via zijn passages (`dct:source`). Een definitie gaat alleen mee als er precies één is.
- Tests: `tests/test_begrippen_verdieping.py`.

## Lex naast de kaart

`begrip_voorstellen.py`, `begrip_voorstel_store.py`, `begrip_voorstel_contracts.py`; PLAN spoor D, fase E.
Vier acties op één begrip: `brondefinitie` (een graafquery, geen model), `scherper`, `betekenisverschil`
(met een ander begrip, `ander_begrip_id`) en `voorbeelden`. graph-qa rekent, de api legt vast en toetst.

- **Een voorstel is geen wijziging.** `begrip_voorstellen` is een eigen tabel; Lex schrijft nooit in het
  begrip. `POST …/voorstellen/{id}/overnemen` loopt door `begrip_store._gewijzigd_in` (revisie, kopie,
  audit `voorstel-overgenomen` met voorstel-id, actie en model) en zet het besluit in dezelfde
  transactie. Sloten: werkgebied → begrip → voorstel.
- **Niets stil overschreven.** Een definitievoorstel bewaart `basis` (de definitie en herkomst bij het
  starten). Wijkt het begrip daarvan af, dan 409 `voorstel_verouderd` met `toen`, `nu` en `voorstel`;
  `GET …/voorstellen` meldt het vooraf als `verouderd`. Vervangen kan dan alleen bewust: met
  `nu_gezien` = de definitie die de analist naast het voorstel zag (klopt die niet meer: weer 409). Uitleg, toelichting en voorbeelden worden
  toegevoegd, nooit vervangen; wat er al staat, geeft geen revisie (wel het besluit).
- **Herkomst gaat mee.** `BegripInhoud.definitie_door` (`lex` | `analist` | leeg) zet de api, nooit de
  client (`begrip_store.met_afgeleid`): een ongewijzigde definitie houdt wie haar voorstelde, een nieuwe of
  andere tekst is van de analist. Overnemen zet `lex` en de herkomst van het voorstel; met `aanpassing`
  wordt het `geformuleerd` + `analist`. Het akkoordpad van fase D zet `lex` (of `analist` bij een aanpassing).
  Het afgeleide veld telt niet als gewijzigd veld in de revisie.
- **De run**: `POST …/kaart-runs` legt de invoer vast (begrip op zijn revisie, de actuele dragende
  passages die in het manifest staan, het manifest, de selecties). Idempotent op (actie, revisie van
  begrip en ander begrip, manifest): een lopende run, of een klare met open voorstellen, komt terug;
  anders een nieuwe. `voorbeelden` zonder definitie en `scherper`/`betekenisverschil` zonder passages: 409.
- **De garanties toetst de api zelf** (`begrippen_verdieping.definitie_fouten`/`fragment_fouten`):
  fragmenten letterlijk in het manifest, samengesteld = precies de fragmenten, letterlijk = in de bron.
  Een brondefinitie buiten het manifest wordt tegen de bronboom uit de graaf getoetst. Een veld dat
  niet bij de actie hoort: 422 `VELD_HOORT_NIET_BIJ_ACTIE`. Een geformuleerde definitie is nooit groen.
- `GET …/voorstellen` geeft ook per model-actie een schatting (mediaan tokens van de laatste 20 klare
  runs van de gebruiker) en het budget, voor de knoppen.
- Tests: `tests/test_begrip_voorstellen.py`.

## Onderhoud van begrippen

`begrip_onderhoud.py`, `begrip_onderhoud_store.py`, `begrip_onderhoud_contracts.py`; PLAN spoor D, fase F1.
Acceptatie: *een gewijzigde dragende passage verschijnt bij de geraakte begrippen; de oude bewijsstand blijft.*

- **Twee bronnen van verandering.** `begrip_store.actualiteit` ziet alleen Postgres: een gewijzigde,
  verworpen, verdwenen of door herannotatie verouderde annotatie. Een nieuwe wettekst zonder herannotatie
  ziet hij niet. `GET …/herbeoordelingen` (`?begrip_id=`) vraagt daarom ook de bronboom
  (`inventaris_met_bronbomen`) en zet per anker `bron_signalen`: `ongewijzigd`, `gewijzigd` (met
  `fragment_gelijk`: staat het gemarkeerde fragment nog letterlijk op zijn offsets), `weg` of `onbekend`
  (regeling niet op te halen – een open punt, nooit "ongewijzigd").
- **Het bewijs verandert nooit.** Per geraakte koppeling: `toen` (het bewijs), `nu` (het element),
  `bron`, `redenen` (zinnen voor de werkplek), `opvolgers`, `opnieuw_annoteren` en `acties`.
- **Opvolgers** (`opvolgers`, zuiver): herannotatie maakt een nieuw element met een nieuw id. Kandidaat =
  actueel element op een bronnode van de oude ankers of met dezelfde eigenaar; signalen met richting
  (klasse, tekst, plek, al elders primair). Geen score: de volgorde is plek → tekst → positie.
- **Herkoppelen** (`POST …/koppelingen/{k}/herkoppelen {verwachte_revisie, element_id}`): nieuwe koppeling
  met de rol van de oude en `beoordeling: akkoord` (de analist zag toen en nu), de oude krijgt
  `verwijderd` + `vervangen_door`. De nieuwe draagt bij het lezen `vervangt` met het oude bewijs. Dezelfde
  passage: 422 `zelfde_passage`; buiten het werkgebied 422; al primair elders 409 `al_primair`.
- **Bevestigen** (`POST …/bevestigen`): voegt aan `bevestigingen` een stand toe (`element_hash`, ankers
  met de bron-hash van nu); daarna rekent de actualiteit daartegen (`referentie_hash`). Alleen als de
  annotatie bestaat, niet verworpen en niet verouderd is (422 `niet_te_bevestigen`), en elk fragment
  letterlijk op zijn plek staat (422 `fragment_weg`). Niets te bevestigen: geen revisie.
- **Geaccordeerd blijft geaccordeerd** bij herkoppelen en bevestigen (besloten 16 okt 2026). Wat dan nog
  openstaat, noemt `aandachtspunten` (ook een dragende annotatie die een jurist nog niet beoordeelde).
- **Dekking** (`GET …/dekking`): elk element van de inventaris één keer, voorrang `gekoppeld` (dragend
  aan een geaccordeerd begrip) → `buiten_behandeling` → `voorstel` (concept-begrip of open groep van de
  laatste klare run) → `te_verwerken`; plus `nieuw_sinds_run` (niet in manifest of `overgeslagen` van die
  run). `POST …/dekking/buiten-behandeling {element_ids, reden}` (reden verplicht, idempotent, tabel
  `werkgebied_element_besluiten`) en `DELETE …/buiten-behandeling/{element_id}` (soft). Audit
  `element-buiten-behandeling` / `element-in-behandeling`; geen revisie, het raakt de scope niet.
- Tests: `tests/test_begrip_onderhoud.py`.

## Begripsrelaties en opvolging

`begrip_relaties.py`, `begrip_relatie_store.py`, `begrip_relatie_contracts.py`; PLAN spoor D, fase F2.

- **Tabel `begrip_relaties`**: van, naar, `type` (`kwalificatie`, `inclusie`, `uitsluiting`, `hierarchie`,
  `verwant`, `opvolging`), `herkomst` (`lex` | `analist` | `systeem`), bewijs, toelichting, `beoordeling`
  (`akkoord` | `afgewezen`), `stand_van`/`stand_naar` (hash van definitie + context bij het vastleggen),
  soft delete. Audit `relatie-*`, `begrip-vervangen`, `begrip-opgevolgd`, `begrip-gecombineerd`,
  `begrip-hersteld`. Geen platslaan tot "verwant": de typen houden hun juridische betekenis.
- **Voorstellen worden afgeleid** (`_voorstellen`): een relatie tussen twee elementen uit de laatste klare
  run (`uitkomst.relaties`), die elk primair een ander, niet vervangen begrip aanduiden. Id
  `R<hash(van, naar, type)>`. Lezen schrijft niets; `POST …/relaties {voorstel_id}` legt vast (herkomst
  `lex`), `POST …/relaties/voorstellen/{id}/afwijzen {reden}` schrijft een afgewezen rij, en die sleutel
  komt niet terug. Een voorstel dat er niet meer is: 409 `voorstel_weg`.
- **Zelf vastleggen**: `{van_begrip, naar_begrip, type}`; `verwant` vraagt een toelichting (422);
  `opvolging` kan niet (422); naar zichzelf 422 `zelfde_begrip`; dezelfde actieve relatie 409
  `al_vastgelegd`; een vervangen begrip 409 `vervangen`. `DELETE …/relaties/{id}` (opvolging niet: 409).
- **Doorwerking** (`doorwerking`): wijkt de stand van één kant af van wat bij het vastleggen gold, dan staat
  de relatie bij het begrip aan de andere kant in `GET …/herbeoordelingen` (`relaties`), en in
  `GET …/relaties` als `veranderd`. `POST …/relaties/{id}/bevestigen` legt de stand van nu vast.
- **Nieuwe betekenis** (`POST …/begrippen/{b}/nieuwe-betekenis {verwachte_revisie, reden}`), één
  transactie: het begrip wordt `vervangen`, een nieuw concept krijgt de inhoud en alle niet-afgewezen
  koppelingen (met hun bewaarde bewijs, opnieuw `open`), plus een relatie `opvolging` met de vorige status
  in het bewijs. **Combineren** (`POST …/begrippen/{b}/combineren {verwachte_revisie, ander_begrip_id,
  ander_revisie, reden}`): de ander wordt vervangen, `b` krijgt diens passages (open) en naam als
  alternatieve term. Beide begrippen dragen hun revisie (412).
- **Een vervangen begrip** houdt geen primaire duiding vast (`_toets_primair`, `primaire_duidingen`),
  telt niet in de dekking en de herbeoordeling, en staat niet bij `lijkt_op`. `GET` van een begrip geeft
  `vervangen_door` en `vervangt`. **De opvolger verwijderen** zet het vervangen begrip terug op zijn vorige
  status (`_herstel_voorgangers`, revisie `begrip-hersteld`) en neemt zijn relaties mee.
- Tests: `tests/test_begrip_relaties.py`.

## Begrippen naar de kennisgraaf

`begrip_projectie.py`, `shapes/`; PLAN spoor D, fase F3; ADR-003 (NL-SBB is het datacontract).

- **Per werkgebied één named graph** `urn:wa:graph:werkgebied:<id>`, register
  `urn:wa:graph:register:begrippen` (`wa:werkgebiedId`, `wa:projectieHash`, `wa:inGraaf`). Kader =
  `skos:ConceptScheme` met `dct:title` en de toelichting "analyse-uitkomst, geen wettelijke definitie";
  begrip = `skos:Concept` (`prefLabel`, `altLabel`, `definition`, `rdfs:comment` = uitleg, `scopeNote` =
  context, `example` = voorbeelden met oordeel *wel*, `inScheme`, `dct:source` → `foaf:Document` met
  vindplaats). Eigen predicaten onder `urn:wa-ns:`: status, revisie, herkomst en `definitieDoor`,
  JAS-klasse (IRI uit de vocabulaire), geaccordeerd-op, en per koppeling (`urn:wa:koppeling:<id>`) rol,
  beoordeling, element (`urn:jas:element:<id>`), `elementHash` (de bewijsstand, of de laatste bevestiging)
  en de bronnode. **Alle begrippen met hun status**, ook concepten en vervangen begrippen.
- **Relaties houden hun type**: `wa:kwalificeert`, `wa:omvat`, `wa:omvatNiet`, `wa:heeftSoort`,
  `wa:verwantMet`, plus een `wa:Begripsrelatie` met herkomst. Alleen een hiërarchie krijgt ook
  `isothes:broaderGeneric` (de soort → de bredere term); opvolging is `dct:isReplacedBy`/`dct:replaces`.
  Alleen relaties met beoordeling *akkoord*.
- **Postgres is de waarheid.** `invoer(conn, werkgebied_id)` leest alles wat de graph draagt;
  `bouw_graaf` is zuiver en de projectie hangt niet van de brongraaf af. `invoer_hash` is de stand in
  het register. Geen personen, en geen subject onder `urn:bwb:` (een bronnode is alleen object).
- **Direct na de commit**: `werkgebied_store._audit` noteert het werkgebied op de verbinding
  (`db.noteer_na_commit`); het `commit`-event van de engine geeft het aan `begrip_projectie.na_mutatie`
  (`db.na_commit_haak`), een rollback gooit het weg. Elke audited werkgebiedmutatie projecteert dus,
  zonder dat een schrijfpad eraan hoeft te denken. Het event valt **vóór** de COMMIT: `projecteer`
  neemt daarom eerst een leesslot (`FOR SHARE`) op het werkgebied, dat de schrijver afwacht
  (`test_begrippen_postgres.py` bewijst dat). Wat dit proces al zo schreef, slaat hij over.
- **De lus** (`graaf_projectie_v2.lus`, zelfde interval) roept `begrip_projectie.reconcile` aan met een
  eigen vangnet: projecteert wat afwijkt van de hash in het register of wiens graph ontbreekt, en haalt
  graphs weg van verwijderde, (oude) gearchiveerde of lege werkgebieden.
- **Conformiteit** (`conformiteit`, `GET …/begrippen/conformiteit`): diagnostisch, nooit in het
  schrijfpad. Twee lagen: `nl_sbb` (het vastgepinde profiel `shapes/nl-sbb-1.0.0.ttl`, letterlijk uit
  `geonovum/NL-SBB`, CC-BY 4.0; herkomst en hash in `shapes/BRON.md`) en `eigen`
  (`shapes/begrippen-wa.ttl`: herkomst van de definitie, geaccordeerd-op, koppeling → element +
  hash, bron bij een dragende passage, schone wettekst). Een begrip is **conform** als het profiel geen
  Violation geeft op het begrip of zijn bronnen; waarschuwingen en eigen meldingen staan erbij. Zonder
  pyshacl `conform: null`, nooit `true`.
- **Turtle-export** (`GET …/begrippen/export?formaat=ttl[&inclusief=alle]`): dezelfde `bouw_graaf`,
  standaard alleen geaccordeerde begrippen (en relaties tussen twee die meegaan), met `dct:conformsTo`
  NL-SBB, `wa:nlSbbVersie`, `prov:generatedAtTime` en per begrip `wa:nlSbbConform`. `foaf:page` komt
  best-effort uit de brongraaf (`owl:sameAs` = de jci, anders `bwb:bronUrl`); zonder graaf ontbreekt
  hij, de bron-IRI staat er altijd.
- **`GET …/begrippen/samenhang`**: begrippen, koppelingen (rol, beoordeling, actualiteit) en relaties
  (vastgelegd en voorgesteld) voor de samenhangsgraaf van de werkplek, uit Postgres.
- **Graafcontrole** (`graafcontrole.controleer` → `begrippen`): achterstand (hash wijkt af), afwijkingen
  (graph ontbreekt, inhoud niet isomorf), verweesde graphs, de invariant en – met SHACL – het aantal
  niet-conforme begrippen (telt niet mee voor `in_orde`: een concept zonder definitie is gewoon nog niet af).
- **Een nieuwe NL-SBB-versie** is een bewuste overstap: nieuw shapesbestand, nieuwe hash in de test,
  `NL_SBB_VERSIE` en `NL_SBB` mee.
- Tests: `tests/test_begrip_projectie.py` en het slot in `tests/test_begrippen_postgres.py`.

## Begrippen lezen

`begrippen_overzicht.py`; PLAN spoor D, fase F4. Alleen lezend, uit Postgres, over alle actieve
werkgebieden. Een verwijderd begrip of werkgebied (en een oud gearchiveerd werkgebied) bestaat hier niet.

- **`GET /v1/begrippen`** (`q`, `status` herhaalbaar, `werkgebied_id`, `eerst`, `limit`, `offset`) is het
  overzicht van de webapp. Zoeken gebeurt in Python (de inhoud is JSON, de tests draaien op SQLite):
  zonder hoofdletters en diakrieten, rangorde exacte naam → exacte term → in de naam → in een term →
  in de definitie → alle woorden ergens; daarna het werkgebied `eerst`, dan geaccordeerd → concept →
  vervangen. Een rij noemt het werkgebied, `vervangen_door`, `aantal_dragend` en bij een geaccordeerd begrip
  `herbeoordelen`: het aantal dragende passages dat sinds het accorderen veranderde (de actualiteit uit
  Postgres, zoals de aandachtspunten van de kaart; een nieuwe wettekst zonder herannotatie ziet alleen
  `…/herbeoordelingen`). Ook in `verifieer`, zodat Lex het kan noemen. `mijn=true` (een route-parameter,
  geen veld van `BegripZoekvraag`: graph-qa heeft het niet nodig) geeft alleen begrippen met een revisie
  van deze gebruiker; `per_status` telt met dezelfde filters zonder het statusfilter, voor de tellers op
  de knoppen. Het contract is
  `BegripZoekvraag`; graph-qa (`search_begrippen`) vraagt niets wat daar niet in staat.
- **Lex zoekt in de graaf, de api bevestigt** (`POST /v1/begrippen/verifieer {ids, werkgebieden}`), net
  als bij `search_annotaties`: per id de rij van nu of `null`, en per werkgebied de `projectie_hash`
  die `begrip_projectie.invoer_hash` nu zou geven. Wijkt die af van `wa:projectieHash` op het kader in
  de graaf, dan loopt de projectie achter en meldt Lex dat zijn resultaat onvolledig kan zijn.
- **`GET /v1/begrippen/{id}`**: `{werkgebied: {id, naam}, begrip: <kaart>, relaties: <akkoord>}`, zonder
  dat de vrager het werkgebied hoeft te kennen (`get_begrip` van Lex, de werkplek).
- Tests: `tests/test_begrippen_overzicht.py`.

## Bronnen vinden met Lex

`bronnen_runs.py`, `bronnen_run_store.py`, `bronnen_run_contracts.py`; het ontwerp staat in PLAN
spoor D (*Bronnen vinden voor een werkgebied*, fase A). De methoden draaien in graph-qa; de api legt de
invoer vast, toetst en bewaart de kandidaten, en legt de besluiten vast.

- **De invoer is de selectie** (`invoer_van`): kern = bronselecties met rol *analyseren*, context = de
  rest, plus naam en analysevraag. Zonder kern én zonder analysevraag: 409 `geen_vertrekpunt`.
  **Idempotent op (werkgebied, invoer)** (`invoer_id`, een inhoudshash); `laatste` meldt `verouderd`
  als de selectie of de analysevraag intussen veranderde. Een run die `VERLOPEN` (5 min) stil was,
  telt als `mislukt` en mag opnieuw.
- **Eén kandidaat per bepaling**: sleutel (werkgebied, `kandidaat_id(bron_iri)`), over runs heen.
  Vinden meer methoden haar, dan groeit het bewijs (`methode`, `vanuit`, `detail`) en wint de sterkste
  rol (`kern` > `afhankelijkheid` > `aanverwant`). Wat bij `PUT …/uitkomst` al in de selectie staat,
  wordt geen kandidaat.
- **Het besluit hoort bij de kandidaat**: een latere run werkt bewijs, rol en `run_id` bij en laat de
  status staan. **Een uitgesloten kandidaat komt dus niet terug** (de acceptatie van L1). Uitsluiten
  vraagt een reden (422 zonder). `later`, `uitsluiten` en `heropenen` nemen het slot op het werkgebied
  maar dragen geen revisie: ze wijzigen de scope niet.
- **Opnemen** wijzigt de scope en draagt daarom `verwachte_revisie` (412). De api verifieert de bron
  zoals bij zelf opnemen en schrijft selectie én kandidaatstatus in één transactie
  (`werkgebied_store.voeg_bron_toe(..., binnen=…)`). Rol: *analyseren* bij een kernkandidaat, anders
  *context*, tenzij de analist kiest. Haalt de analist die selectie weer weg
  (`verwijder_bron`), dan wordt de kandidaat in dezelfde transactie weer `voorgesteld`.
- `GET …/kandidaten` geeft de laatste run en de kandidaten (sterkste rol eerst), met `in_laatste_run`
  en `in_selectie` (intussen met de hand opgenomen). `…/uitkomst`, `…/loopt` en `…/mislukt` zijn voor
  graph-qa.
- Het artefact van een bronnenbeurt is `{soort: "bronnen", ref: {werkgebied_id, run_id}}`.
- Tests: `tests/test_bronnen_runs.py` (SQLite) en het slot in `tests/test_werkgebieden_postgres.py`.

## Deelvragen

`werkgebied_deelvragen.py`, routes in `werkgebieden.py`; open keuze 4 is besloten op **optioneel**: een
werkgebied zonder deelvragen werkt zoals altijd.

- **Tabellen** `werkgebied_deelvragen` (vraag, volgorde, `status` `actief` | `voorgesteld` | `afgewezen` |
  `vervangen`, `herkomst` `analist` | `lex`, reden, `vervangt`, soft delete) en `werkgebied_deelvraag_koppelingen` (een set per
  deelvraag, `soort` `bron` | `begrip`, zonder foreign key; wat niet meer bestaat valt bij het lezen weg).
  `GET /v1/werkgebieden/{id}` draagt `deelvragen` (actief en voorgesteld, met hun geldige koppelingen).
- **Een actieve deelvraag hoort bij de scope**: toevoegen, wijzigen (tekst, volgorde, overnemen met
  `status: actief`, afwijzen met verplichte reden), weghalen en koppelen lopen door
  `werkgebied_store._gewijzigd` (revisie, 412, audit `deelvraag-*`). Dezelfde vraag nog eens (genormaliseerd:
  hoofdletters, diakrieten, leestekens) geeft 409 `al_gesteld`; koppelen aan iets buiten het werkgebied 422
  `buiten_werkgebied`; een voorstel koppelen 409 `niet_actief`.
- **Voorstellen van Lex** (`POST …/deelvragen/voorstellen {vragen, model}`, graph-qa): geen revisie, alleen
  het slot en een auditregel `deelvragen-voorgesteld`. Wat er al staat, is afgewezen of weggehaald, komt er
  niet bij (`overgeslagen` met de reden).
- **Een verbetering vervangt** (F3d). Met `vervangt: <id>` (herformuleren of splitsen door de deelvragen-agent)
  moet dat een actieve deelvraag zijn (anders 422 `vervangt_onbekend`); elk voorstel draagt de kolom.
  Overnemen (`status: actief`) zet de oude op `vervangen` (audit `deelvraag-vervangen`, alleen bij de eerste
  overname van een splitsing), kopieert haar geldige koppelingen naar de opvolger en zet die op haar plek,
  ná een eerder overgenomen deel (`_op_de_plek_van` nummert de actieve deelvragen opnieuw). Een vervangen
  deelvraag staat niet meer in de lijst, wijzigen geeft 409 `vervangen`, de status zet geen client (422),
  en Lex stelt haar tekst niet opnieuw voor. `koppel_bron_in` volgt een vervangen deelvraag naar haar
  actieve opvolger(s). `GET …/deelvragen/{id}` geeft één deelvraag in elke stand, met `opvolgers` en de open
  `voorstellen` die haar vervangen (het deelvraagpaneel van de werkplek).
- **Dekking** (`GET …/deelvragen/dekking`): per actieve deelvraag `gedekt` (een gekoppeld geaccordeerd
  begrip), `geen_begrip` (wel bronnen of begrippen, geen geaccordeerd) of `geen_bron`; uit Postgres, zonder
  graaf. Een vervangen begrip dekt niets meer.
- **De bronnenrun zoekt per deelvraag**: `bronnen_run_store.invoer_van` neemt de actieve deelvragen op (alleen
  met deelvragen een sleutel, zodat de `invoer_id` van een werkgebied zonder deelvragen gelijk blijft); met
  alleen deelvragen is er ook een vertrekpunt. Op dezelfde manier gaat het dossier mee als sleutel `dossier`
  (alleen de gevulde velden van aanleiding, context, doel, praktijkvoorbeeld en afbakening). Bewijs van de methode `deelvraag` draagt `deelvraag_id`;
  opnemen koppelt de nieuwe selectie in dezelfde transactie aan die deelvragen (`koppel_bron_in`).
- Tests: `tests/test_werkgebied_deelvragen.py`.

## Gesprekken

`gesprek_contracts.py`, `gesprek_store.py`, `routers/gesprekken.py`. Per gebruiker gescopet via
`actieve_userid`; 404 op andermans gesprek.

- **Een gesprek hoort bij een werkgebied of is los** (spoor G1): `werkgebied_id` (leeg = los) en
  `gearchiveerd` (een tijdstip, zoals bij werkgebieden). `POST` neemt `werkgebied_id` aan, `PATCH` wijzigt
  alleen wat meekomt (`titel`, `werkgebied_id` – `""` koppelt los –, `gearchiveerd`), `GET` filtert op
  `werkgebied_id` (`""` = alleen losse) en `gearchiveerd`, en geeft per rij `werkgebied_naam` mee. Koppelen
  aan een onbekend werkgebied geeft de 404 van het werkgebied; werkgebieden zijn gedeeld, dus bestaan is
  genoeg. Verplaatsen of archiveren zet `updated` niet: het gesprek springt niet bovenaan de lijst. Geen
  foreign key: een gewist werkgebied maakt zijn gesprekken los (`werkgebied_store.wis`), en een gewist
  gesprek raakt niets in de andere domeinen. Archiveren, verplaatsen en verwijderen zijn bewust drie
  handelingen; verwijderen blijft echt wissen.

- Een bericht verwijst via **`artefact`** naar wat de beurt opleverde: `{soort, ref, titel}` met
  `soort` `annotatie` (ref `{bron_iri, label?, snapshot_id?}`), `begrippen` (ref
  `{werkgebied_id, run_id}`; met `begrip_id` in plaats van `run_id` alleen nog in berichten van vóór F3d),
  `begrip` (ref `{werkgebied_id, begrip_id, kaart_run_id?, actie?}`: één begrip, F3d), `deelvraag` (ref
  `{werkgebied_id, deelvraag_id}`: één deelvraag, F3d), `bronnen` (ref `{werkgebied_id, run_id}`, fase A),
  `werkgebied` (ref `{werkgebied_id}`: een werkgebied dat Lex in het gesprek samenstelde, activiteit 1)
  of `regels` (gereserveerd, nog niet in gebruik). `Artefact` toetst de
  verplichte ref-sleutels per soort (422). Oudere berichten verwijzen via `annotatie_doel`; graph-qa
  schrijft beide voor een annotatie. Het bericht draagt ook het uitvoeringsspoor van de beurt
  (`tool_executions`). Een antwoord op een overzichtsvraag draagt het
  `overzicht` dat graph-qa uit de graaf bouwde, zodat het blok na herladen hetzelfde is.
  Een voorstel dat Lex niet zonder akkoord start (fase B: het werkgebied annoteren) draagt een
  **`bevestiging`** `{soort: "werkgebied_annoteren" | "begrippen_verdiepen", werkgebied_id, aantal, schatting,
  bereik: "werkgebied" | "deelvragen", deelvraag_id}` (het bereik van de werkvoorraad, zodat de knop na herladen hetzelfde annoteert). Het user-bericht
  dat zo'n voorstel beantwoordt – de knop of *Annuleren* – draagt **`bevestiging_antwoord`** `{keuze: "gestart" | "geannuleerd"}`,
  zodat de knoppen na herladen weg zijn; de werkplek
  toont er een knop bij, ook na herladen. Bij het samenstellen van een werkgebied (activiteit 1) draagt
  elke vraag van Lex een **`vraagkaart`** `{intake_id, soort: vraag|samenvatting, stap, nr, totaal,
  vraag, opties[{label, waarde, bron, omschrijving}], meerkeuze, vrije_tekst, meer_tekst, overslaanbaar,
  vooringevuld, samenvatting, terug, beantwoord}`; de stappen (`IntakeStap`) zijn `naam`, `aanleiding`,
  `context`, `doel`, `analysevraag`, `praktijkvoorbeeld`, `deelvragen`, `buiten`, `regelingen`,
  `bepalingen`, `samenvatting`. `modus` is `samenstellen` (default) of `aanvullen`: het dossier van een
  bestaand werkgebied, met in de samenvatting `{wijzigingen: [{veld, label, toen, nu}]}`. Het user-bericht van een klik draagt
  **`intake_antwoord`** `{intake_id, stap, actie}` (`actie` ook `opslaan`, de knop van het aanvullen): zo bundelt de werkplek na herladen de antwoorden
  in één Vragen-kaart en onderscheidt hij ze van een getypte tussenvraag. `reeks.totaal` mag 1 zijn: een werkgebied kan één nieuwe
  bepaling hebben.
  De review-state zelf blijft in het annotatiedomein. **Een veld dat graph-qa meestuurt moet in
  `BerichtInvoer` staan**, anders laat Pydantic het stil vallen en verdwijnen na het heropenen de
  chip naar het annotatiepaneel en het toolspoor. `tools/graph-qa/tests/test_contract_drift.py`
  toetst dat.
- De verwijzing heeft **geen foreign key**, dus draagt het bericht een eigen label
  (`artefact.titel`; bij oude berichten `annotatie_titel`). Een annotatie verwijderen raakt de
  berichten niet: het gesprek is een verslag.
- **`run_id` is een idempotentiesleutel.** Een agent-beurt hangt niet aan één browserverbinding en
  meerdere tabbladen kunnen op dezelfde run meekijken. `voeg_bericht_toe` geeft bij een bekend
  `run_id` het bestaande bericht terug; de partiële unieke index `ux_gesprek_berichten_run` dekt de
  race tussen replica's, en de insert staat in een SAVEPOINT omdat een `IntegrityError` op Postgres
  anders de hele transactie aborteert.
- **De schrijver is meestal graph-qa**, met een eigen client-id in `WETSANALYSE_API_TOKENS`
  (`graph-qa:<token>`) plus de `X-User-Id` van de jurist. `client_id` is niet aan `user_id`
  gebonden: dat token kan in elk gebruikersgesprek schrijven, en graph-qa blijft daarom intern.

## Login, registratie, 2FA

- **Inloggen gaat met de `userid`** (primaire sleutel van `users`); `email` is verplicht en uniek
  maar geen inlog-identiteit. bcrypt, rollen `beheerder`/`analist`. `/v1/auth/*` hangt achter
  `require_client`; de BFF (Auth.js) is de enige client en zet `X-User-Id` server-side. De
  browsersessie leeft in de frontend.
- **Een TOTP-code geldt één keer** (`users._verbruik_totp`): de gebruikte tijdstap staat in
  `users.totp_laatste_stap` en het vastleggen is één voorwaardelijke `UPDATE`, dus twee
  gelijktijdige pogingen met dezelfde code halen het nooit allebei. Omdat de webapp na het
  2FA-scherm nóg eens verifieert, geeft `/verify` na een verbruikte code een **2FA-ticket** mee
  (`maak_2fa_ticket`, 5 min, Fernet); `verify_credentials` meldt dat als `"ok_totp"`. De 2FA-secret
  is versleuteld met dezelfde Fernet-key als de LLM-keys. Tests zetten de klok stil via
  `users._nu`; `_totp_now` in `tests/test_users_auth.py` schuift per code een stap op.
- **Zelfregistratie** (`registraties.py`): een aanvraag is **geen account** – tot de goedkeuring
  bestaat er geen rij in `users`. De userid wordt afgeleid uit de naam (vier letters achternaam +
  eerste letter voornaam + volgnummer) en is bij goedkeuren corrigeerbaar; de bcrypt-hash gaat
  ongewijzigd over (`users.insert_user_met_hash`), zodat er geen tijdelijk wachtwoord rondgaat.
  **Afwijzen verwijdert de rij**: e-mailadres en volgnummer zijn meteen weer vrij; de reden staat in
  het security-log. Er gaat geen e-mail uit: bij een openstaande aanvraag meldt `/verify` de `code`
  `aanvraag_open`, en **alleen bij het juiste wachtwoord** – anders is het een oracle voor wie er een
  aanvraag heeft liggen.
- **Actief-controle.** `actieve_userid` (`routers/auth.py`) controleert dat het account bestaat en
  actief is, met een cache van 30 s; de admin-router roept `vergeet_actief()` aan bij deactiveren of
  verwijderen, zodat dat meteen bijt. `huidige_userid` leest alleen de header, voor endpoints die hun
  eigen bewijs vragen (wachtwoord, 2FA-code).
- **Admin-bearer levert geen userid.** Admin-endpoints die per-beheerder state schrijven (zoals
  `feedback_gezien_op`) lopen daarom ook via `huidige_beheerder`.
- **Admin-tokens**: `require_admin` (async) accepteert de env-tokens (`WETSANALYSE_ADMIN_TOKENS`,
  het bootstrap-pad) en DB-tokens uit `api_tokens.py`. Die staan alleen als sha256-hash in
  `api_tokens`, worden één keer getoond en zijn intrekbaar; ze voeden o.a. de admin-MCP
  (`tools/wetsanalyse-admin-mcp/`).

## Tokenbudget

`verbruik.py`. **Verbruik is een journaal, de stand is een som.** `token_verbruik` krijgt één rij per
LLM-call; de stand is `sum(...) WHERE userid = ? AND tijdstip >= venster_start`, en het vensterbegin
volgt uit het `anker` in `budget_beleid`. Daaruit volgt:

- **Werk weggooien geeft geen tokens terug.** `userid` is de enige harde sleutel; `gesprek_id` en
  `run_id` zijn metadata zonder foreign key, want `gesprek_store.verwijder_gesprek` en
  `annotatie_v2_store.verwijder_weergave` ruimen hun eigen rijen hard op.
- **De reset vraagt geen cronjob**, en elk getal is navraagbaar tot op de call.
- Wat meetelt is het volle promptvolume (invoer + uitvoer + cache_lees + cache_schrijf): caching
  verlaagt de factuur, niet het budget. De vier getallen staan apart, zodat een gewogen variant een
  rekenregel is en geen migratie.
- Het beleid staat in de database, want een limiet aanpassen mag geen redeploy vragen; de env-waarden
  seeden alleen de eerste rij (`verbruik.ensure_seeded`). Boeken is idempotent op `run_id`.

## Schema

Er is geen Alembic. `db.create_all` maakt bij de start **ontbrekende tabellen** aan;
`db.reconcile_schema` voegt daarna **ontbrekende kolommen** toe (`ALTER TABLE … ADD COLUMN`, mét
`server_default`) en maakt **ontbrekende indexen** aan (`checkfirst`). Nooit droppen of van type
wisselen: dat is een bewuste, handmatige ingreep. Declareer een nieuwe kolom dus altijd in de
`Table` in `db.py`; zonder die declaratie kent SQLAlchemy Core haar niet, ook als ze in de database
bestaat. `_na_kolom` vult een nieuw toegevoegde kolom waar de waarde al elders stond (nu alleen
`gesprek_berichten.run_id` uit `inhoud`).

Portable types: `JSON` wordt `JSONB` op Postgres; datetimes zijn tz-aware (`db.aware` repareert
naïeve SQLite-waarden). Een in-memory SQLite-URL krijgt een `StaticPool`. Let op: in-memory SQLite
deelt één verbinding, dus twee gelijktijdige requests zijn daarop niet te testen.

## Garanties (niet aan tornen)

- **Identiteit uit `X-User-Id`.** Gesprekken zijn per gebruiker gescopet (404 op
  andermans id, lekt niet). De header is vertrouwd omdat alleen de BFF en graph-qa hem zetten – zie
  §*Uitrol* voor wat een publieke ingress daarmee doet.
- **De admin-laag is altijd auth-plichtig.** Geen `AUTH_REQUIRED`-bypass; zonder admin-tokens is
  alles 401. De plaintext-API-key komt nooit terug (alleen `api_key_set`); opslaan vraagt een
  Fernet-master-key.
- **Append-only audit.** Elke annotatie-actie schrijft auditregels; de tijdlijn is `ORDER BY id`.
- **JAS-klassen zijn canoniek**: `validation.GELDIGE_JAS_KLASSEN`, gevoed door `jas_klassen.py`.
  Verzin er geen bij. `tests/test_jas_kleuren_drift.py` bewaakt dat `frontend/lib/jas.ts` dezelfde
  kleuren draagt.
- **De API toetst zelf wat hij vastlegt**, want hij is de laatste partij die iets kan tegenhouden.
  Hij doet de juridische interpretatie niet over: of een fragment letterlijk in de wet staat, toetst
  graph-qa. De API toetst de samenhang van anker, fragment en bron.
- **Een projectie laat nooit een beslissing falen.** GraphDB-fouten in het projectiepad worden
  gelogd en ingehaald door de lus; zoeken en graafcontrole melden onvolledigheid expliciet.
- **Secrets zijn bestanden** (`*_FILE`), nooit plain env in productie.
- **Log nooit tokens, secrets of prompt-inhoud.**

## Observability

`app/observability.py`: gestructureerde JSON-logging (`ts/niveau/categorie/bericht/…velden`,
secret-redactie, `LOG_LEVEL`/`LOG_FORMAT`) plus OpenTelemetry, gated op
`OTEL_EXPORTER_OTLP_ENDPOINT`. `setup()` draait vroeg in `main.py`; `RequestContextMiddleware`
(pure ASGI) zet een `X-Request-Id` en logt per request. `get_tracer()`/`get_meter()` geven no-op-shims
zonder de `otel`-extra, dus code mag onvoorwaardelijk spans en metrics maken. Zie
`docs/observability.md`.

## Commando's

```bash
cd api
uv sync --extra llm --extra dev
uv run --env-file .env uvicorn app.main:app --reload --port 3000   # --env-file is verplicht
uv run pytest -q                                                    # fakes, in-memory SQLite
```

Pre-commit: `uv run --extra dev --extra llm --extra otel --locked pytest -q` – dat draait CI
(`api-docker-publish.yml`) vóór de build.

Twee testsets draaien alleen met een echte database: `test_annotatie_v2_postgres.py` en
`test_projector_v2_integration.py` vragen `ANNOTATIE_TEST_DSN` (asyncpg-URL; elke test krijgt een
eigen schema), de laatste ook `ANNOTATIE_TEST_GRAPHDB_URL`. Raak je het schrijfslot, de revisies of
de projectie, draai ze dan: SQLite kent de rij-locks en de transactie-abort van Postgres niet.

Image bouwen vanaf de **projectroot** (het image neemt `packages/bronmodel` mee):
`docker build -f api/Dockerfile -t wetsanalyse-api .`

## Uitrol

De API draait als container app `<appName>-api` (`deploy/azure/main.bicep`), `maxReplicas: 3`,
non-root. Postgres is een eigen dienst (Azure PostgreSQL Flexible Server), zodat een
image-redeploy de database nooit raakt; bij een cold start overbrugt `_init_db_met_retry` de
wachttijd (`WETSANALYSE_DB_CONNECT_RETRIES`/`_BACKOFF`). `GRAPHDB_URL` wijst naar de interne GraphDB
van dezelfde straat. De verwerking is stateless per request, dus horizontaal schalen is veilig:
de v2-schrijfacties serialiseren op de database, niet in het proces.

**Ingress per straat** (`apiExtern`, default `false`):

- **productie** – intern, alleen bereikbaar binnen de container-apps-omgeving.
- **acceptatie** – publiek (`--api-extern` in `azure-infra.yml`), zodat de admin-MCP bij
  `/v1/admin/*` kan.

> De ingress zit vóór de hele app. Publiek betekent ook `/v1/annotatie`, `/v1/gesprekken`,
> `/v1/auth`, `/v1/berichten` en `/v1/feedback`, en daarmee valt de aanname onder `X-User-Id` weg:
> wie een client-token heeft, kiest zijn eigen identiteit. Op acceptatie is dat een bewuste
> afweging (proefdata); op productie niet. Een guard in `poort.yml` bewaakt dat de default `false`
> blijft en dat `--api-extern` alleen achter de acceptatie-conditie staat.
>
> `apiInternalUrl` is afgeleid van `ingress.fqdn`, en die wordt bij een publieke ingress
> `<app>.<domein>` in plaats van `<app>.internal.<domein>`. Frontend en graph-qa lopen dan via het
> publieke endpoint. Moet dit ooit naar productie, laat die twee dan eerst op de app-naam praten.

**Secrets.** De bicep zet ze als container-app-secrets en mount ze als bestanden onder
`/run/secrets/` (`llm_api_key`, `llm_config_secret`, `api_tokens`, `admin_tokens`, `database_url`).
`azure-infra.yml` roteert ze niet: GitHub environment-secret (`WA_*`) → wat er in Azure draait →
anders vers genereren. `llm-config-secret` is de Fernet-sleutel voor de API-keys van modelprofielen
én de 2FA-secrets; genereer je hem opnieuw, dan zijn alle opgeslagen keys en 2FA-inschrijvingen
onleesbaar. De job faalt bij een ontbrekend secret en wacht na het uitrollen tot elke app een gezonde
revisie draait.

Troubleshooting van de uitrol staat in [`README.md`](README.md#troubleshooting).

## Misbruik- en kostenbeheersing

Knoppen via env (0 = uit; defaults in de README): `WETSANALYSE_RATE_LIMIT_MAX`/`_WINDOW` (per
client → 429), `WETSANALYSE_ADMIN_TEST_RATE_MAX`/`_WINDOW` (krappe limiet op de verbindingstest, die
een betaalde LLM-call doet achter alleen het admin-token), `WETSANALYSE_LLM_MAX_CONCURRENCY` en
`WETSANALYSE_LLM_TIMEOUT_S`. De testfout is gesaniteerd: een vaste melding in de respons, de ruwe
providerfout alleen in het serverlog. De rate-limiter is begrensd (sweep + harde cap van 10.000
sleutels, fail-closed), zodat aanvaller-gekozen sleutels via de publieke login-route het geheugen
niet vullen. `POST /v1/auth/registratie` heeft een eigen rate limit.

## Nog niet gebouwd

- **Externe IdP/OIDC.** De API is zelf de identiteitsbron.
- **Activiteit 3, verder.** Werkgebieden, begrippen en de deterministische voorstellen van Lex
  bestaan, het model voor twijfelparen en definitievoorstellen (fase C), Lex naast de kaart (fase E) en
  herbeoordeling en dekking (fase F1), begripsrelaties en opvolging (fase F2), de NL-SBB-projectie en
  Turtle-export (fase F3) en het lezen over werkgebieden heen (fase F4).
- **RegelSpraak-formalisering.** Komt later.
