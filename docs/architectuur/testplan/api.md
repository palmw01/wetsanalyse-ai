# Testplan, laag api: inventaris en nulmeting

Soort: *nulmeting* (16 nov 2026), een deel van het testplan van Lex Bench ([plan](../plan-lex-bench.md), PR #1632).
Getoetst op master `f4ba6feb`. **Dit document verandert niets aan de code.** Het zegt wat er is, wat het waard is en wat
er mist. De voorstellen in §5 zijn voorstellen: bouwen gebeurt pas na akkoord.

Onder de laag api vallen `api/`, het gedeelde pakket `packages/bronmodel/` en de importer `tools/bwb-import/`.

**Hoe gemeten.** Met de hand gelezen en met kleine scripts geteld (AST en grep over de testbestanden, de routers en
`db.py`). Daarnaast: één testbestand lokaal gedraaid (`test_annotatie_v2.py`: 51 groen in 15 s), en de logs van de laatste
groene `poort`-runs gelezen. **Niet gemeten:** dekking per regel (er draait geen coverage), de volgorde-onafhankelijkheid
(niet in willekeurige volgorde gedraaid) en de volle suite lokaal (bewust niet: zie de grenzen van de opdracht). Waar een
oordeel op lezen rust en niet op een meting, staat dat erbij.

## 0. De stand in het kort

- **De omvang.** 84 testbestanden in `api/tests/` (19.500 regels, ±1.100 testfuncties, 1.286 testgevallen na
  parametrisatie in CI), 15 in `tools/bwb-import/tests/` (218 tests), en **geen eigen testmap voor `bronmodel`**: zijn
  tests staan in `api/tests/test_bronmodel*.py` en verspreid over graph-qa.
- **CI.** De api draait in drie shards met elk een eigen PostgreSQL 16 (`ANNOTATIE_TEST_DSN`), ±2,5 min test per shard en
  ±3,5 min per job met de installatie. bwb-import ±16 s. In de laatste groene run: 1.283 groen, 3 overgeslagen.
- **Het sterke deel.** Het annotatie- en het begrippendomein zijn grondig getest, met echte races op Postgres (`FOR
  UPDATE`, precies één 412, geen verloren revisie), een migratietest die een oude database nabootst, een wislijst-guard bij
  het verwijderen van een werkgebied, en drift-tests die rood worden als alleen de werkplek wijzigt (de kruistests).
- **De zwakke plekken** (§2 en §4):
  1. **De projectie is nooit tegen een echte GraphDB getest.** De integratietest kan het, maar CI zet
     `ANNOTATIE_TEST_GRAPHDB_URL` niet. Dan valt hij terug op een nagebootste GraphDB met rdflib.
  2. **De drie PDF-tests met onafhankelijke tekstextractie slaan in CI altijd over**: de runner heeft geen `pdftotext`.
  3. **Gelijktijdigheid is alleen op Postgres getest voor annotaties, begrippen, werkgebieden en beheerders.**
     Delegaties, bronselectie per deelvraag, deelvragen, werkplaats en verbruik hebben sloten of unieke indexen, maar
     alleen tests op SQLite, en SQLite serialiseert alles. Zo'n test bewijst het slot niet.
  4. **Er is geen rechtentabel.** Welke route `actieve_userid`, `huidige_beheerder` of `beheerder_met_2fa` vraagt, staat
     nergens als geheel getest. Haalt iemand de dependency weg, dan wordt alleen een route rood die toevallig een eigen
     test op 401/403 heeft.
  5. **Een handvol tests is altijd groen**, onder meer de twee SPARQL-injectietests (§4.1).
  6. **Een mutatie zonder enige test**: `POST /v1/werkgebieden/{werkgebied_id}/groepen/{groep_id}/parkeren` (§1.3).

## 1. Inventaris per domein

De tabel telt testfuncties (vóór parametrisatie). *SQLite* is de standaard: elke testmodule start een eigen in-memory
engine (`sqlite+aiosqlite://`, in 32 bestanden). *Postgres* zijn de bestanden met `pytestmark = skipif(not
ANNOTATIE_TEST_DSN)`: lokaal zonder DSN slaan ze over, in CI draaien ze.

| Domein | Bestanden | Tests | Waarvan Postgres | Regels |
|---|---|---|---|---|
| Annotaties | 16 | 141 | 7 (`test_annotatie_v2_postgres`) | 2.490 |
| Werkgebieden (incl. deelvragen, werkvoorraad, wissen) | 6 | 70 | 3 (`test_werkgebieden_postgres`) | 1.309 |
| Begrippen (incl. generiek, runs, onderhoud, relaties, projectie) | 13 | 182 | 6 (`test_begrippen_postgres`) | 3.502 |
| Bronselectie (per deelvraag, bronnen-runs, bepalingen zoeken en detail, runstatus) | 5 | 69 | 0 | 1.224 |
| Gesprekken (incl. artefactversies, context, samenhang-antwoord) | 4 | 88 | 0 | 1.393 |
| Auth en 2FA (login, accounttokens, registraties, herstel, rem, agenttoegang) | 9 | 130 | 5 (`test_beheerders_postgres`) | 2.501 |
| Verbruik | 1 | 39 | 0 | 575 |
| Connectors | 1 | 7 | 0 | 110 |
| Modelkeuzes en modelprofielen (incl. admin, LLM-throttle) | 3 | 25 | 0 | 511 |
| Delegaties | 1 | 17 | 0 | 310 |
| Werkplaats | 2 | 28 | 0 | 583 |
| Projectie naar GraphDB, graafcontrole, graaf en samenhang | 11 | 111 | 4 (`test_projector_v2_integration`) | 1.907 |
| Export (werkgebiedrapport, annotatie-export, PDF-opmaak) | 3 | 113 | 0 | 1.726 |
| Overig (berichten, feedback, observability, schema, opstart, bronmodel) | 7 | 81 | 4 (`test_schema_start`) | 1.275 |

### 1.1 Annotaties

- **Wat getoetst wordt.** De ankertoets (`valideer`: klasse, fragment, bereik, `bron_hash`, dubbele ankers), batches die
  idempotent zijn op `batch_id` plus payload, de lifecycle en het vergrendelen na een oordeel, de grenskeuze, *opnieuw
  annoteren* (vervangen, herstellen, verversen), relaties tussen markeringen (leggen, voorstellen uit de keten met elke
  reden in `relaties_overgeslagen`, `wis_bij`), de weergave in beide vormen, afronden, de statistiek, wissen bij een
  storing van de graaf, en de export (JSON tegen `annotatie-export-v4.schema.json`, PDF).
- **SQLite tegenover Postgres.** Op Postgres staan de races die SQLite niet kan bewijzen: twee gelijke batches tegelijk
  geven één commit en precies drie auditregels; twee schrijvers op dezelfde laag geven één 412 zonder verloren update;
  verplaatsen en beoordelen tegelijk splitsen de eigenaar niet; twee relaties op één drager geven één 412; een voorstel
  en dezelfde relatie van de jurist tegelijk geven één rij. Dat is de goede verdeling.
- **Los of dubbel.**
  - `test_validation.py` (één test: dertien klassen, `Rechtssubject` erin) doet hetzelfde als `test_jas_kleuren_drift`
    en de vocabulairetest samen. Hij kan weg.
  - Vijf drift-tests tegen de werkplek staan als losse bestanden in de api (`test_lifecycle_drift`,
    `test_slotregel_drift`, `test_jas_kleuren_drift`, `test_verklaringen_frontend_drift`, `test_jas_relaties`). Ze doen
    hetzelfde als `tests/poort/test_waardensets.py`, maar dan op een andere plek (§3.2).
  - `test_annotatie_v2.py` is in de praktijk de conftest van 29 andere bestanden: `ONE`, `TWO`, `snapshot`, `element`,
    `request` en de `client`-fixture worden daaruit geïmporteerd (§4.3).

### 1.2 Werkgebieden

- **Wat getoetst wordt.** Aanmaken en wijzigen met revisie (412 `revisie_conflict`), bronselecties met rol en bereik (409
  bij een andere rol), de inventaris, de werkvoorraad (ook met een onbereikbare bron), deelvragen (opstellen, verwijderen,
  dekking, 404 en 409 `niet_actief` en `geen_deelvragen`), het koppelen van gesprekken, en verwijderen en wissen.
- **SQLite tegenover Postgres.** Op Postgres: twee wijzigingen tegelijk geven één 412; dezelfde bron tegelijk toevoegen
  geeft één selectie; twee kandidaten tegelijk opnemen op dezelfde revisie geven één 412. **Deelvragen hebben geen
  Postgres-test**, terwijl `werkgebied_deelvragen.py` vier keer een slot of `IntegrityError` gebruikt.
- **Goed.** `test_werkgebied_verwijderen.py` toetst dat elke tabel met een `werkgebied_id` in de wislijst staat. Een nieuwe
  tabel die vergeten wordt, maakt hem rood. Dat is een structurele test, en zo hoort het.

### 1.3 Begrippen

- **Wat getoetst wordt.** Het grootste domein (182 tests): de begripskaart, koppelingen met bewijsstand, de
  accorderingspoort, revisies, de begrippenketen (manifest, runs, groepen, besluiten), Lex naast de kaart (voorstellen per
  veld, 13 × 409 en 10 × 422), onderhoud (herbeoordeling, herkoppelen, opvolgers), relaties en opvolging, de projectie naar
  NL-SBB met conformiteit en Turtle, het overzicht over werkgebieden heen, en generieke begrippen (ADR-006).
- **Generiek tegenover werkgebied** (`test_begrippen_generiek.py`, 19 tests: 8 × 404 en 7 × 409). Het verschil tussen een
  generiek begrip en zijn gebruik in een werkgebied is goed afgedekt, ook de passages per werkgebied.
- **SQLite tegenover Postgres.** Op Postgres: dezelfde duiding tegelijk aan twee begrippen, twee wijzigingen met één 412,
  twee starts op hetzelfde manifest met één run, twee akkoorden op één groep met één begrip, en dat de projectie wacht op
  een lopende schrijftransactie. Relaties, voorstellen en onderhoud hebben geen Postgres-test.
- **Een gat.** `POST /v1/werkgebieden/{werkgebied_id}/groepen/{groep_id}/parkeren` (`begrippen_runs.py`) heeft geen enkele api-test. Het woord
  `geparkeerd` komt in geen enkele test voor, terwijl de werkplek de knop wel heeft (`frontend/lib/api.ts`). Het is de
  enige van de 132 mutaties zonder één testvermelding.

### 1.4 Bronselectie

- **Wat getoetst wordt.** De voortgang per deelvraag (de statussen uit `Voortgang`), besluiten per deelvraag (opnemen en
  uitsluiten gelden per deelvraag, 10 × 409 en 3 × 412), de volgende deelvraag, het overzicht, de oude waarde die
  `reconcile_schema` omzet, bronnen-runs met kandidaten en bewijs, en de statusmachine van de runs (`test_run_status`: een
  klare run blijft klaar, en een late melding overschrijft niets).
- **SQLite tegenover Postgres.** `bronselectie.py` neemt acht keer een slot, maar **er is geen Postgres-test**. Twee
  besluiten tegelijk op dezelfde deelvraag, of een besluit tijdens het afronden, is dus niet bewezen.
- **Voor Lex Bench.** Arm L2 leest de lijst die het paneel als voorstel toont, in de volgorde van de werkplek (plan §4.4).
  De api-tests toetsen de inhoud van die lijst, maar **niet de volgorde als contract**. Dat is een kleine test met grote
  waarde voor Bench (§5, V8).

### 1.5 Gesprekken

- **Wat getoetst wordt** (`test_gesprekken_api`, 47 tests). Scoping per gebruiker (8 × 404 op andermans gesprek), 401 voor
  een onbekende of gedeactiveerde gebruiker, berichten, artefactversies (ook dat een storing het bericht laat landen zonder
  versie), de contextopbouw en het samenhang-antwoord met een haperende graaf.
- **SQLite tegenover Postgres.** Geen Postgres-tests. Dat is te verdedigen: gesprekken zijn per gebruiker en `gesprek_store`
  heeft weinig gedeelde state. Toch zijn er drie sloten.

### 1.6 Auth en 2FA

- **Wat getoetst wordt** (130 tests). Login met de dummy-bcrypt bij een onbekende gebruiker, TOTP (één keer bruikbaar, geen
  oudere stap na een nieuwere), het 2FA-ticket, herstelcodes, de plicht tot 2FA voor elke weg naar beheerder, de laatste
  beheerder (ook met hoofdletters en via de admin-api), het herstel van de 2FA van de enige beheerder, zelfregistratie,
  de inlogrem (per IP en userid, het globale plafond, spraying), accounttokens (alleen de hash, ingetrokken, verlopen,
  gedeactiveerd, geen erfenis voor een nieuw account met dezelfde naam, geen toegang tot de admin-api) en de agenttoegang
  (het agenttoken beslist niet).
- **SQLite tegenover Postgres.** Op Postgres: vijf races rond de laatste beheerder (twee beheerders degraderen of
  verwijderen elkaar tegelijk, en alles tegelijk laat er precies één over). Dit is het best bewaakte deel van de api.
- **Los of dubbel.** `test_auth.py` (4 tests op `require_client`) en de tokentests in `test_api_tokens.py` overlappen
  deels. Dat is niet erg.

### 1.7 Verbruik

- **Wat getoetst wordt** (39 tests). Het journaal, de stand als som over het venster, het budget per rol, de reset, de
  beheerroutes met 2FA, en dat dezelfde beurt die twee keer tegelijk gemeld wordt één keer boekt (via de unieke index).
- **SQLite tegenover Postgres.** Die laatste test draait met `asyncio.gather` op SQLite. Daar loopt alles na elkaar, dus de
  unieke index wordt geraakt, maar een echte race niet. `test_schema_start` toetst op Postgres wel dat een index op
  dubbelen de start niet tegenhoudt.

### 1.8 Connectors, modelkeuzes en modelprofielen

- **Connectors** (7 tests): het register, de beheerroute met 2FA, 422 op een onbekende naam. Dun, maar het domein is klein.
- **Modelkeuzes** (7) en **admin** (11): de keuze per agentprofiel en per stap met audit, de verbindingstest met een
  krappe limiet (429), profielen met versleutelde sleutels. **`llm_resilience`** (7): de throttle, met twee tests die
  alleen toetsen dat er niets misgaat (§4.1).

### 1.9 Delegaties

- **Wat getoetst wordt** (17 tests). Eén regie per werkgebied en één lopende delegatie per gebruiker, een verweesde regie
  die het slot loslaat, deelgesprekken onder hun ouder, wachten met een vraag zonder slot, de hartslag, en wissen met het
  werkgebied.
- **SQLite tegenover Postgres.** Het slot zit in twee partiële unieke indexen (`ux_delegaties_lopend_regie_werkgebied` en
  `ux_delegaties_lopend_gebruiker`), elk met een **eigen** `sqlite_where` en `postgresql_where` in `db.py`. De tests
  toetsen alleen de SQLite-variant. Lopen de twee voorwaarden ooit uiteen, dan merkt geen test het. Dat geldt voor alle
  vijf de partiële indexen in `db.py`.

### 1.10 Werkplaats

- **Wat getoetst wordt** (28 tests). Onderdelen met een eigenaar, versies die alleen aangroeien, poort 1 bij elke opslag,
  delen en intrekken door een beheerder met 2FA, het beleid, en het image (`test_werkplaats_image`: wat in het image komt).
- **SQLite tegenover Postgres.** Geen Postgres-test op twee gelijktijdige versies van hetzelfde onderdeel.

### 1.11 Projectie naar GraphDB

- **Wat getoetst wordt.** Het RDF-model en de invarianten (`test_graaf_projectie_v2`, `test_vocabulaire`, `test_shacl`),
  de ronde van de lus (een foute laag slaat alleen die laag over, een storing stopt de ronde, begrippen volgen dezelfde
  regel), de graafcontrole met SHACL en de Postgres-stand (21 tests), en op Postgres: een gedeeltelijke HTTP-fout met
  herstel, wezen opruimen zonder vreemde graphs te raken, een hangende graaf die geen besluit blokkeert, en de commit die
  direct in de graaf staat.
- **De beperking.** `test_projector_v2_integration` is gebouwd voor een echte GraphDB (`ANNOTATIE_TEST_GRAPHDB_URL`: hij
  maakt een eigen repository en ruimt die op). **CI zet die variabele niet**, en een `grep` over `.github/` vindt haar
  nergens. Dan bootst de fixture GraphDB na met een rdflib-`Dataset` achter een `MockTransport`. Ook `graafdb_fake.py`
  (vijf bestanden) is rdflib. Dus wat GraphDB anders doet dan rdflib (de REST-api voor repositories, `PUT` op
  `rdf-graphs/service`, de SPARQL-dialecten, de FTS-connector, het gedrag na een herstart) is in de api nooit getest.
- **Goed.** `test_het_rdflib_werk_draait_niet_op_de_event_loop` bewaakt de blokkade van november (memory: *api blokkeert
  event loop*).

### 1.12 Export

- **Wat getoetst wordt** (113 tests, waarvan 83 in `test_werkgebied_export`). Het rapport als één JSON-document (ADR-009),
  het schema dat opnieuw gegenereerd en vergeleken wordt, dat elke tekst in het rapport in de uitvoer komt, Markdown en PDF
  met ingesloten lettertypen, statussen en de delen voor voorstellen, afgewezen en uitgesloten.
- **De beperking.** De drie tests die de PDF-tekst onafhankelijk teruglezen met `pdftotext`
  (`test_werkgebied_export.py:300`, `test_annotatie_export.py:174`, `test_annotatie_v2.py:446`) **slaan in CI over**. De
  laatste groene `poort`-run telt precies drie overgeslagen tests in de api-shards. Lokaal draaien ze wel. Dat de PDF de
  juiste tekst draagt, is in CI dus niet bewezen.

### 1.13 bronmodel

`packages/bronmodel` (4.100 regels, 17 modules plus `bwb/`) heeft **geen eigen testmap**. De tests staan elders:

- in de api: `test_bronmodel.py` (23 tests: snapshot, ankers, eigenaar, actualiteit, de bronquery met een SPARQL-parse) en
  `test_bronmodel_corpus.py` (9 tests: `CorpusMap`, spans, de teksthash);
- in graph-qa: 65 bestanden importeren uit `bronmodel`, vooral `connectors`, `antwoord` en `agentprofiel`;
- in bwb-import: `bwb`, `extern`, `kennisgroepen`, `vindplaats` (19 bestanden over de drie lagen samen raken `bronmodel.bwb`).

Dat werkt, omdat `poort` bij een wijziging in `packages/bronmodel/` alle drie de suites draait. Maar een module zonder
directe test bestaat: `taal.rangnummers` en `taal.normaliseer_vraag` worden in geen enkele test bij naam genoemd, en
`begrip.eigen_toelichting` in één. Ze kunnen indirect getest zijn, maar dat is niet te zien.

### 1.14 bwb-import

- **Wat getoetst wordt** (218 tests, alle offline op fixtures in `tests/fixtures/`). De parser (32), verwijzingen (21) en
  deeldoelen (14), bijlagen (14), slot- en structuurtekst, de boom, de dekking, de WTI-verrijking, de ontologie, de
  kennisgroepen-index, de exitcodes van `main` (24, ook de importpoort vóór de `PUT`) en de schrijver naar GraphDB (55, met
  een nagebootste server). `test_falende_similarity_index_maakt_de_import_niet_rood` toetst alleen dat er geen uitzondering
  komt (§4.1).
- **Wat niet.** Geen test tegen de echte XSD's van overheid.nl in hun volle omvang (`test_validation`, 3 tests), en geen
  test tegen een echte GraphDB. De graafwacht (`--alleen-bij-verlies`) is via de exitcodes getest, niet tegen een lege
  repository.
- **CI.** De poort draait bwb-import met `pip`, de kruistests met `uv` (`scripts/kruistests.sh`). Dat werkt, maar het zijn
  twee manieren om dezelfde afhankelijkheden te installeren.

## 2. Foutpaden: de risicomatrix

**Schaal.** *Goed*: het risico is getoetst op de plek waar het optreedt, met de echte database waar dat ertoe doet.
*Deels*: getoetst, maar niet overal of niet op Postgres. *Zwak*: alleen indirect of met een test die het risico niet echt
kan zien. *Open*: geen test.

### 2.1 De statuscodes per mutatie

De api heeft 232 routes, waarvan 132 mutaties (POST, PUT, PATCH, DELETE). Getelde testbestanden die een statuscode toetsen:
404 in 28, 409 in 28, 412 in 16, 422 in 35, 401 in 18, 403 in 9 en 429 in 5.

| Risico | Dekking | Waar | Oordeel |
|---|---|---|---|
| 412 bij een tussentijdse wijziging (revisietoets) | annotaties, werkgebieden, begrippen, relaties, voorstellen, onderhoud, bronselectie, deelvragen, verwijderen | `test_annotatie_besluiten`, `test_werkgebieden`, `test_begrippen`, `test_begrip_relaties`, `test_bronselectie`, `test_werkgebied_deelvragen`, `test_werkgebied_verwijderen`, en de `*_postgres` | **Goed** per domein. Er is geen test die *elke* mutatie met `verwachte_revisie` langsloopt. Een nieuwe mutatie zonder revisietoets wordt niet vanzelf rood |
| 409 bij een andere bronstand of een vergrendeld element | annotaties (snapshot, verouderd, vergrendeld), begrippen, voorstellen (13), delegaties (14), bronselectie (10) | idem, `test_delegaties`, `test_begrip_voorstellen` | **Goed** |
| 422 bij foute invoer | 35 bestanden, het meest in `test_gesprekken_api` (16), `test_begrip_voorstellen` (10), `test_annotatie_v2` (8) | | **Goed** voor de domeinregels. De Pydantic-validatie zelf (`extra="forbid"`) is niet systematisch getoetst |
| 404 op een onbekend of andermans object | 28 bestanden; generieke begrippen (8), gesprekken (8), werkplaats (8), werkgebied wissen (6) | | **Goed** |
| Een mutatie zonder test | `POST …/groepen/{groep_id}/parkeren` | geen | **Open** |

### 2.2 Gelijktijdigheid en sloten

| Risico | Dekking | Oordeel |
|---|---|---|
| Het globale annotatieslot (`schrijftransactie`, `FOR UPDATE` op `annotatie_v2_state`) | 7 Postgres-races | **Goed** |
| Het rij-slot op een werkgebied, begrip of beheerder | 3 + 6 + 5 Postgres-races | **Goed** |
| De projectie wacht op een lopende schrijftransactie | `test_begrippen_postgres::test_projectie_wacht_op_een_lopende_schrijftransactie` | **Goed** |
| Bronselectie per deelvraag (8 × slot of `IntegrityError` in `bronselectie.py`) | alleen SQLite | **Zwak** |
| Deelvragen (4), werkplaats (3), begripsvoorstellen (2), bronnen-runs (2), gesprekken (3) | alleen SQLite | **Zwak** |
| Delegaties: één lopende per gebruiker, één regie per werkgebied (partiële unieke index) | alleen SQLite, en `postgresql_where` staat los van `sqlite_where` | **Zwak** |
| Verbruik: dezelfde beurt twee keer tegelijk | `gather` op SQLite | **Zwak**: geen echte race |
| Twee replica's met elk een projectielus | niet getest (de lus pakt het slot, maar twee lussen tegelijk niet) | **Open** |

### 2.3 Externe afhankelijkheden

| Risico | Dekking | Oordeel |
|---|---|---|
| GraphDB valt uit tijdens de projectie | `test_projectie_ronde` (storing stopt de ronde), `test_projector_v2_integration` (gedeeltelijke HTTP-fout, hangende graaf, herstel), `graafdb_fake.storing()` | **Deels**: het gedrag van de api is goed getoetst, maar alleen tegen rdflib, nooit tegen GraphDB |
| Een lege GraphDB na een herstart (de projectie bouwt alles terug) | `reconcile` vergelijkt de revisies in de graaf; getest met de nagebootste graaf | **Deels** |
| De bronresolver hapert (GraphDB traag of weg bij het ophalen van de bronboom) | wissen (`test_annotatie_verwijderen`: 503), knoopinfo (503), bepaling-detail en samenhang (`ConnectError`), werkvoorraad (`onbereikbaar`), begrip-onderzoek (`onbereikbaar` in de run) | **Deels**: een batch, een besluit of een export op het moment dat de resolver faalt, is niet getoetst. Een time-out (in plaats van een `ConnectError`) is nergens getoetst |
| `bron_resolver.py` zelf | geen test noemt de module; de logica zit in `bronmodel` en is daar getest | **Deels** |
| De database is bij de start niet bereikbaar | `test_startup_db_retry` (2 tests) | **Goed** |
| bcrypt blokkeert de event loop | `test_bcrypt_pool` (de lus draait door, een volle wachtrij weigert meteen met 503) | **Goed** |
| De LiteLLM-verbindingstest hapert | `test_admin`, `test_llm_resilience` | **Deels** |

### 2.4 Rechten

| Risico | Dekking | Oordeel |
|---|---|---|
| `X-User-Id` ontbreekt, onbekend of inactief (`actieve_userid`, met een cache van 30 s) | `test_gesprekken_api` (401 onbekend, gedeactiveerd verliest toegang), `test_annotatie_v2::test_api_view_active_user…`, verspreid | **Deels**: per domein een paar routes. Er is geen test die de 168 routes met `Depends(actieve_userid)` als geheel bewaakt |
| De beheerder met 2FA (`beheerder_met_2fa`) | 9 routes in `admin.py` (werkplaats, modelkeuzes, connectors, budget, 2FA-reset, verbruik-reset); getest in `test_modelkeuzes`, `test_connectors`, `test_verbruik`, `test_werkplaats`, `test_users_auth` | **Deels**: de 20 andere beheermutaties (profielen, gebruikers, registraties, tokens, berichten) lopen op het admin-token alleen. Dat lijkt een bewuste keuze (de admin-MCP moet erbij), maar **nergens staat vast welke route welk niveau vraagt** |
| `huidige_beheerder` geeft altijd 403, nooit 401 (geen user-enumeratie) | `test_feedback`, `test_berichten` | **Goed** |
| Accounttokens (`wa_pat_…`) | `test_api_tokens` (16 tests) | **Goed** |
| Het agenttoken beslist niet | `test_agent_toegang` (5) en `tests/poort/test_agent_toegang.py` (de lijst `TOEGESTAAN` is wat graph-qa aanroept, geen beslissingsroute erin) | **Goed** |
| Gedeelde lagen tegenover gescopete gesprekken | gesprekken: 404 op andermans gesprek; annotaties en werkgebieden: gedeeld | **Goed** |

### 2.5 Rate limit

| Risico | Dekking | Oordeel |
|---|---|---|
| De inlogrem (missers per IP en userid, globaal plafond, `Retry-After`) | `test_inlogrem` (6), `test_users_auth` | **Goed** |
| Gevoelige handelingen (`sensitive_allowed`, wachtwoord en 2FA) | `test_users_auth` | **Goed** |
| Zelfregistratie per e-mailadres | `test_registraties` | **Goed** |
| De limiet per client (`rate_limited_client`) | alleen `feedback`; `test_feedback` toetst de 429 | **Goed** voor wat er is. Let op: de docstring zegt *op muterende endpoints*, maar alleen feedback gebruikt hem. Dat is een vraag over het ontwerp, geen testgat |
| De telstaat lekt tussen tests | 16 bestanden roepen `ratelimit.reset()` aan, er is geen gedeelde fixture | **Deels** (§4.3) |

### 2.6 Generieke begrippen tegenover werkgebieden

| Risico | Dekking | Oordeel |
|---|---|---|
| Een generiek begrip gebruiken zonder kopie, met passages per werkgebied | `test_begrippen_generiek` (19) | **Goed** |
| Een werkgebied wissen terwijl het een generiek begrip gebruikt | `test_werkgebied_verwijderen`, `test_begrippen_generiek` | **Goed** |
| Gelijktijdig generiek maken en wijzigen in een werkgebied | niet op Postgres | **Open** |

### 2.7 Verwijderen en wissen

| Risico | Dekking | Oordeel |
|---|---|---|
| Een werkgebied wissen neemt alles mee | de wislijst-guard over alle tabellen met `werkgebied_id` | **Goed** |
| Een element of bepaling wissen neemt de relaties mee (`wis_bij`) | `test_annotatie_relaties`, `test_annotatie_verwijderen` | **Goed** |
| Wissen terwijl de graaf weg is | `test_annotatie_verwijderen` (`nep.storing(True)`, 503 van de resolver) | **Goed** |
| Een account wissen en dezelfde userid opnieuw aanmaken | `test_api_tokens::test_nieuw_account_erft_geen_tokens_van_het_oude` | **Deels**: tokens wel; gesprekken, verbruik en werkplaatsonderdelen van het oude account niet |
| Gesprekken in bulk wissen | `test_gesprekken_api` | **Goed** |

### 2.8 Migraties (`reconcile_schema`)

| Risico | Dekking | Oordeel |
|---|---|---|
| Een kolom die in de definitie staat maar in de database ontbreekt | `test_users_auth::test_reconcile_schema_voegt_kolom_toe` (SQLite), `test_schema_start::test_bijgewerkt_is_gelijk_aan_vers` (Postgres: alle nullable kolommen weg, opnieuw opbouwen, gelijk aan vers) | **Goed** |
| Vier replica's starten tegelijk | `test_gelijktijdige_starts_botsen_niet` | **Goed** |
| Een herstart neemt geen tabelslot | `test_een_herstart_neemt_geen_tabelslot` (geen DDL bij een tweede start) | **Goed** |
| Een unieke index op bestaande dubbelen | `test_een_unieke_index_op_dubbelen_houdt_de_start_niet_tegen` | **Goed** |
| Een oude waarde wordt omgezet (bronselectie `later`) | `test_bronselectie` | **Goed** |
| Een NOT NULL-kolom erbij op een gevulde tabel | `reconcile` voegt alleen nullable kolommen of kolommen met default toe; dat er nooit een NOT NULL zonder default bijkomt, toetst geen test | **Open** (klein) |

## 3. De contracten met graph-qa en de werkplek

### 3.1 Wat er is

- **Het routecontract** (`tests/poort/test_routecontract.py` met `routeboek.py`). Statisch: elke aanroep van de browser
  landt op een BFF-route met die methode, een catch-all van de BFF heeft het pad ook upstream, en elke aanroep van de BFF,
  graph-qa en de admin-MCP landt op een api-route met die methode. Een meta-test toetst dat de parser genoeg vindt, en een
  andere dat het contract een verwijderde export vangt. **Sterk**, en het vangt de klasse fout die de browsertests met hun
  mocks niet zien.
- **De waardensets** (`tests/poort/test_waardensets.py`). Zes enums aan beide kanten gelijk: `Lifecycle`, `LaagStatus`,
  `Voortgang`, `KoppelRol`, `Beoordeling` en `BegripStatus`.
- **De drift-tests in de api**: lifecycles, de slotregel (op gedeelde gevallen in `frontend/lib/slotregel.json`, een goed
  patroon), de JAS-kleuren, de verklaringen en de relatiecatalogus.
- **De agenttoegang** (`tests/poort/test_agent_toegang.py`): wat graph-qa aanroept, staat in `TOEGESTAAN`, en daar staat
  geen beslissingsroute in.
- **Aan de kant van graph-qa** (gelezen, niet de laag van deze inventaris):
  - `test_contract_drift.py`: het annotatie-element en het relatievoorstel tegen `annotatie_v2_contracts`, de velden van
    het chatbericht, de parameters van `search_annotaties`, de subtypen, de stappen van de intake en de acties op een
    kaartje;
  - `test_bronnen_vinden.py` tegen `bronnen_run_contracts`;
  - `test_deelvragen.py` tegen `werkgebied_contracts` en `app.routes`;
  - `test_begrippen_manifest_drift.py` tegen `begrip_manifest.py`.
- **De kruistests** (`scripts/kruistests.sh`) vinden deze tests op wat ze lezen, niet uit een lijst. In de api zijn het er
  twaalf. Ze draaien bij elke codewijziging, ook als alleen de andere kant verandert.

### 3.2 Wat niet

- **De vorm van een antwoord van de api richting de werkplek.** `frontend/lib/types.ts` is met de hand geschreven. Het
  routecontract toetst pad en methode, de waardensets zes enums, maar geen test vergelijkt de velden van een antwoord
  (bijvoorbeeld `WerkgebiedOut` of de weergave) met het TypeScript-type. Een veld dat de api hernoemt, wordt in de werkplek
  stil `undefined`.
- **Query-parameters.** Het routecontract kijkt niet naar parameters. Dat is precies de fout van #190 (de BFF liet `lid`
  vallen; memory: *BFF-proxy: forward alle query-params*).
- **De bodies van graph-qa naar de api**, buiten de annotatiebatch en het chatbericht. Werkgebied, deelvragen,
  bronselectie, begrippen-runs en kaartvoorstellen: graph-qa bouwt hun bodies zelf, en alleen `bronnen_run_contracts` en
  `werkgebied_contracts` worden aan die kant gelezen.
- **Versiebeheer van het contract.** Er is geen versienummer tussen graph-qa en de api. Beide komen per commit uit, maar
  tijdens een uitrol draaien ze een paar minuten naast elkaar in verschillende versies. Geen test toetst dat een nieuwe api
  een oude graph-qa nog bedient.
- **De drift-tests staan op drie plekken**: in `tests/poort/` (alleen stdlib), in `api/tests/` (vijf bestanden) en in
  `tools/graph-qa/tests/`. Ze doen hetzelfde soort werk, maar hebben elk een eigen manier om een TypeScript-lijst te parsen.

## 4. De kwaliteit van de tests zelf

### 4.1 Tests die altijd groen zijn

Een AST-scan vond 11 testfuncties zonder `assert`, `raises` of `fail`. Na lezen:

- **Altijd groen, en ze beloven meer dan ze toetsen:**
  - `test_graaf_projectie_v2.py::test_text_cannot_change_query_structure` en
    `::test_herkomstfilters_veranderen_de_querystructuur_niet` roepen alleen `parseQuery(zoek_query(…))` aan. Een
    geslaagde injectie (`" } UNION { ?s ?p ?o } #`) levert ook een geldige query op. **Deze tests worden dus niet rood
    bij precies de fout waar ze naar heten.** Ze moeten de algebra of de variabelen van de geparste query vergelijken met
    die van een onschuldige tekst.
  - `test_berichten.py::test_markeer_alles_gelezen_is_idempotent` roept de functie twee keer aan en kijkt niet naar het
    resultaat.
- **Bewust zonder assert, en terecht:** de no-op-tests in `test_observability` en `test_llm_resilience` (ze toetsen dat
  iets zonder configuratie niet faalt), en
  `tools/bwb-import/.../test_falende_similarity_index_maakt_de_import_niet_rood`. Een `assert` op de logregel of de
  exitcode maakt ze sterker.
- **Schijn:** twee tests in `test_werkgebied_deelvragen` en één in `test_annotatie_v2_postgres` hebben de assert in een
  hulpfunctie (`_samen(…, status=409)`) of roepen een andere test aan. Die zijn in orde.

Daarnaast zijn er **tests die altijd overslaan**: de drie `pdftotext`-tests in CI (§1.12). Een skip die in CI nooit
draait, is een test die niet bestaat.

### 4.2 Volgorde en gedeelde state

- **Module-globale state.** De api heeft drie caches die tussen tests kunnen lekken: `ratelimit._hits`, de actief-cache
  (`vergeet_actief`) en `get_settings` (`lru_cache`). Er is geen gedeelde fixture die ze leegt. 16 bestanden roepen zelf
  `ratelimit.reset()` aan, 6 `vergeet_actief()` en 28 `get_settings.cache_clear()`. De docstring van `vergeet_actief`
  noemt een echte keer dat het misging: een gebruiker bleef van de ene suite in de volgende *onbekend*.
- **De volgorde is niet getoetst.** Er draait geen `pytest-randomly` of iets dergelijks. De shards verdelen per bestand,
  dus de volgorde verschilt wel tussen een lokale run en een shard. Dat is een gedeeltelijke, toevallige controle.
- **Tests die elkaar aanroepen.** `test_annotatie_v2_postgres` voert een test uit `test_annotatie_v2` uit als controle
  op Postgres. Dat is slim hergebruik, maar het maakt van een testfunctie een API.

### 4.3 Fixtures

- `conftest.py` is 27 regels: alleen `sys.path` en `maak_testgebruikers`. Elke module start zijn eigen engine, schema en
  client. **14 bestanden hebben een eigen `client`-fixture**, 6 een eigen kopie van `snapshot` of `ONE`.
- De gedeelde helpers komen uit **testmodules**, niet uit een conftest: uit `test_annotatie_v2` (29 bestanden),
  `test_werkgebieden` (22), `test_begrippen` (10), `test_begrippen_runs` (5) en nog zes andere. Wie een helper in
  `test_annotatie_v2.py` verandert, raakt dus 29 bestanden. Pytest verzamelt bovendien elke geïmporteerde fixture opnieuw
  in de importerende module.
- De Postgres-fixtures zijn goed: een eigen willekeurig schema per test, `search_path` erop, `DROP SCHEMA … CASCADE`
  achteraf, en nooit het publieke schema. Maar de fixture staat zes keer, licht verschillend.
- De nagebootste GraphDB staat twee keer: `graafdb_fake.py` en de fixture in `test_projector_v2_integration.py`.

### 4.4 Doorlooptijd

- CI: drie shards van 139–173 s testtijd, ±3,5 min per job met `uv sync`. De api-poort is daarmee niet de traagste job.
- Lokaal: `test_annotatie_v2.py` 15 s voor 51 tests. De traagste test (2,1 s) is de weergave met export. Elke module die
  het schema op SQLite aanmaakt, betaalt dat per test of per module.
- 794 waarschuwingen in één shard, vooral `DeprecationWarning` van rdflib (`Dataset.default_context`). Dat is ruis die
  een echte waarschuwing verbergt.
- Vier bestanden gebruiken `sleep` (de bcrypt-pool, de projectie-wacht en de integratietest met 2 s per poging). Dat is
  verdedigbaar, maar het zijn de plekken waar een test wankel kan worden.

### 4.5 Tests die alleen op Postgres draaien

29 tests in zes bestanden. **Lokaal slaan ze zonder `ANNOTATIE_TEST_DSN` stil over.** Wie de api lokaal test, ziet groen
zonder dat de races gedraaid hebben. Alleen de poort zet de DSN; daar lopen ze. Dat staat in de projectregels (*tests die alleen lokaal draaien, verrotten*), en voor deze tests geldt
het omgekeerde: ze draaien alleen in CI. Een duidelijke melding bij de skip, of een `make`-doel met een lokale Postgres, zou
helpen.

## 5. Voorstellen, op prioriteit

Elk voorstel is generiek: het lost een soort fout op, niet één geval.

### P1: wat erbij moet

- **V1. De projectie tegen een echte GraphDB in CI.** Een GraphDB-servicecontainer in één api-shard (of een eigen job) en
  `ANNOTATIE_TEST_GRAPHDB_URL` erop. De test bestaat al en ruimt zijn eigen repository op. Let op de licentie: een
  GraphDB Free-image volstaat voor deze test, die een `file-repository` met ruleset `empty` maakt. *Waarom eerst:* de
  projectie is de enige weg van Postgres naar de graaf waar Lex mee zoekt, en een verschil tussen rdflib en GraphDB
  is nu onzichtbaar.
- **V2. `pdftotext` op de runner** (`apt-get install poppler-utils` in de api-job), en de skip in CI omzetten in een
  fout (`if os.getenv("CI")`: falen in plaats van overslaan). Dan draaien de drie PDF-tests echt.
- **V3. Een rechtentabel als test.** Eén test die `app.routes` doorloopt en per route de dependencies leest
  (`require_client`, `require_admin`, `actieve_userid`, `huidige_beheerder`, `beheerder_met_2fa`), en die vergelijkt
  met een tabel in de test. Een nieuwe route zonder vermelding in de tabel faalt. Dat maakt de keuze voor admin-token
  tegenover 2FA ook zichtbaar en bespreekbaar.
- **V4. Postgres-races voor de domeinen met een slot maar zonder race-test**: bronselectie per deelvraag, deelvragen,
  delegaties (één lopende per gebruiker en per werkgebied), werkplaatsversies en verbruik. Zelfde vorm als
  `test_werkgebieden_postgres`: twee gelijktijdige aanroepen, precies één 412 of 409, en de telling klopt.
- **V5. De SPARQL-injectietests echt laten toetsen**: vergelijk de geparste algebra van een kwaadaardige tekst met die
  van een onschuldige.
- **V6. Een test voor `parkeren`**, en een generieke test die elke mutatie in `app.routes` aan minstens één test koppelt
  (via een lijst met uitzonderingen, zoals `BEKEND` in het routecontract).

### P2: wat herschreven moet

- **V7. Eén `conftest.py` met de gedeelde fixtures.** De engine (SQLite en Postgres met een eigen schema), de client, de
  testgebruikers, de snapshot-helpers, en een autouse-fixture die `ratelimit`, de actief-cache en `get_settings` leegt.
  De imports uit `test_annotatie_v2` en `test_werkgebieden` gaan daarnaartoe. Eén Postgres-fixture in plaats van zes.
  Daarna een keer `pytest -p randomly` draaien als meting van de volgorde.
- **V8. De volgorde van de voorstellijst in de bronselectie als contract.** Een test die vastlegt dat de api de lijst per
  deelvraag in een vaste, gedocumenteerde volgorde teruggeeft. Lex Bench meet die lijst (plan §4.4); verandert de volgorde
  stil, dan verandert de meting zonder dat Lex veranderde.
- **V9. Eén plek voor de drift-tests tegen de werkplek.** De vijf in `api/tests/` naar `tests/poort/` (alleen stdlib),
  naast `test_waardensets.py`, met één parser voor TypeScript-lijsten. De slotregel met gedeelde gevallen
  (`slotregel.json`) is het model: gevallen in JSON, beide kanten draaien ze.
- **V10. Eén waarheid voor partiële indexen.** Een test die per `Index` in `db.py` toetst dat `sqlite_where` en
  `postgresql_where` dezelfde tekst hebben (of één helper die beide zet).
- **V11. `bronmodel` krijgt een eigen testmap** (`packages/bronmodel/tests/`), met de tests uit
  `api/tests/test_bronmodel*.py` erheen. De poort draait hem bij een wijziging aan het pakket. Dan is te zien welke module
  geen directe test heeft (`taal`).

### P3: wat er nog bij kan

- **V12. Het antwoordcontract richting de werkplek**: de velden van de belangrijkste antwoorden (weergave, werkgebied,
  bronselectie, begrip) vergelijken met `types.ts`. Bijvoorbeeld met een JSON-schema uit de Pydantic-modellen dat de
  frontend in een test inleest, zoals `werkgebied-rapport-v2.schema.json` al doet voor het rapport.
- **V13. Query-parameters in het routecontract**: per BFF-route toetsen dat elke parameter die de browser stuurt, upstream
  doorgaat.
- **V14. Een compatibiliteitstest voor de uitrol**: de api van deze commit tegen de bodies van graph-qa van de vorige
  release (uit `release/prd`).
- **V15. Een haperende resolver in het schrijfpad**: een batch, een besluit en een export terwijl `_resolve_bron` een
  time-out geeft. Verwacht: 503, en niets geschreven.
- **V16. Een account wissen en dezelfde userid opnieuw aanmaken**, voor alle data per gebruiker (gesprekken, verbruik,
  werkplaats), naar het voorbeeld van de tokentest.
- **V17. De waarschuwingen van rdflib** filteren of verhelpen (`filterwarnings` in `pyproject.toml`), zodat een nieuwe
  waarschuwing opvalt.

### Wat weg kan

- `test_validation.py`: dubbel met `test_jas_kleuren_drift` en `test_vocabulaire`.
- De fixture-kopieën na V7.
- De rdflib-nabootsing in `test_projector_v2_integration` pas als V1 er staat, en dan alleen als de lokale run zonder
  GraphDB ook mag overslaan. Anders houden voor lokaal.

## 6. Wat dit voor Lex Bench betekent

- Bench meet de bronselectie via de api (arm L2 leest het paneel). V8 maakt die lijst een contract, en V4 bewijst dat twee
  gelijktijdige besluiten de stand per deelvraag niet breken. Zonder die twee kan een meetverschil uit de api komen in
  plaats van uit Lex.
- De ketentest van Bench (plan §8) schuift de grens van stap naar stap. In de api is de overdracht tussen bronselectie en
  annotaties (de werkvoorraad uit de selecties) getest in `test_werkgebied_werkvoorraad`, maar die tussen annotaties en
  begrippen (de dragende passages) alleen per domein. Een test die één werkgebied door de hele keten van de api trekt
  (selectie → werkvoorraad → batch → inventaris → begrip met koppeling → export) bestaat niet. Die hoort eerder bij de
  laag keten/E2E dan hier, maar de api kan hem zonder model draaien.
