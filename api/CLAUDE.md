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

> **De wettekst komt uit de graaf.** De API leest uit GraphDB de **bronboom** (`bron_resolver.py`):
> daarmee toetst hij ankers, legt hij snapshots vast en levert hij de segmenten van de weergave.

## Architectuur (`app/`)

| Module | Rol |
|---|---|
| `main.py` | Routers, `/health`, `/ready`, lifespan: LLM-throttle, DB-init met bounded retry (`_init_db_met_retry`), seeding van profiel en budgetbeleid, start van de projectielussen als `GRAPHDB_URL` gezet is. |
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
| `samenhang.py` | Structuur, annotaties en verwijzingen van één artikel, voor de 3D-weergave. |
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
  Postgres** (manifest van lagen en revisies). Een storing of een achterlopende projectie is nooit
  een leeg, succesvol resultaat: de respons draagt `volledig`.
- **Bronboom** (`bron_resolver.resolve_bron`): leest alleen de expliciete BWB-named graph, nooit
  een union met de annotatiegraphs. Zonder `GRAPHDB_URL` of bij een haperende GraphDB geeft de
  router 503; een ongeldige bron-IRI 422.
- **`/verklaringen`** levert `vocabulaire/verklaringen.json`: leesbare namen voor alles wat in een
  `trace` kan staan. Dat bestand en `vocabulaire/jas-vocabulaire.ttl` worden **gegenereerd** door
  `tools/graph-qa/scripts/genereer_jas_vocabulaire.py`; bewerk ze niet met de hand.
  `tests/test_vocabulaire.py` bewaakt dat elke klasse van de API een concept heeft.
- **`/samenhang`** (`samenhang.py`) geeft drie soorten relaties en niets anders: de bronboom, de
  letterlijke verwijzingen uit de BWB-import (één stap in en uit, max. `MAX_VERWIJZINGEN`) en de
  actuele markeringen. Er wordt niets afgeleid.

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

## Gesprekken

`gesprek_contracts.py`, `gesprek_store.py`, `routers/gesprekken.py`. Per gebruiker gescopet via
`actieve_userid`; 404 op andermans gesprek.

- Een bericht verwijst via `annotatie_doel` naar de bronnode van zijn annotatie en draagt het
  uitvoeringsspoor van de beurt (`tool_executions`).
  De review-state zelf blijft in het annotatiedomein. **Een veld dat graph-qa meestuurt moet in
  `BerichtInvoer` staan**, anders laat Pydantic het stil vallen en verdwijnen na het heropenen de
  chip naar het annotatiepaneel en het toolspoor. `tools/graph-qa/tests/test_contract_drift.py`
  toetst dat.
- De verwijzing heeft **geen foreign key**, dus draagt het bericht een eigen label
  (`annotatie_titel`). Een annotatie verwijderen raakt de berichten niet: het gesprek is een verslag.
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
- **Begrippen (activiteit 3) en RegelSpraak-formalisering.** Die komen later, op agentische basis en
  buiten deze API.
