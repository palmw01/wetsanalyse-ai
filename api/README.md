# wetsanalyse-api

Headless HTTP-backend voor de **Wetsanalyse-werkplek**, onder de [frontend](../frontend). De API
bedient:

- het **JAS-annotatiedomein** (markeringen, beslissingen, een append-only auditlog en export): één
  laag per bronnode (artikel, lid of onderdeel);
- de **chatgeschiedenis** van de werkplek;
- **login en gebruikersbeheer** – de API is de identiteitsbron van de webapp, inclusief
  zelfregistratie en TOTP-2FA (verplicht voor beheer) met herstelcodes;
- het **LLM-modelprofielbeheer**;
- het **tokenbudget**: per rol ingesteld, per gebruiker gemeten;
- **berichten** (release notes) en **gebruikersfeedback**;
- de **werkgebieden**: dossier, deelvragen, bronselectie per deelvraag, inventaris, annotatie-werkvoorraad
  en PDF-export;
- de **begrippen**: begrippen per werkgebied en generiek, hun koppelingen naar annotatiepassages,
  voorstellen van Lex, relaties, herbeoordeling en de NL-SBB-projectie;
- de **versies van artefacten**: de stand van een artefact na elke beurt van Lex.

> **De QA/annotatie-agent is een aparte dienst.** `tools/graph-qa/` (Lex) beantwoordt de vragen,
> stelt de JAS-annotaties voor en levert de wettekst uit de graaf; de werkplek praat er direct mee
> (SSE). Deze API bewaart de review-state, projecteert annotaties en begrippen naar de kennisgraaf en
> bedient login en beheer.

Wie de code wijzigt: lees [`CLAUDE.md`](CLAUDE.md) (architectuur, invarianten, valkuilen).

## Hoe het past in het project

| Onderdeel | Rol |
|-----------|-----|
| **graph-qa** | Lex – beantwoordt vragen, stelt JAS-annotaties voor, levert de wettekst; schrijft de uitkomst van een beurt naar deze API. Eigen LLM-config. |
| **wetsanalyse-api** *(deze map)* | Annotatiedomein, werkgebieden, begrippen, gesprekken, login, beheer, tokenbudget. |
| **PostgreSQL** | De waarheid: annotatielagen + audit, werkgebieden, begrippen, gesprekken, gebruikers, modelprofielen, API-tokens, verbruik. |
| **GraphDB** | Leest de BWB-bronboom (voor ankers en snapshots); de API schrijft de annotatielagen (`urn:jas:graph:v2:<laag-id>`) en de begrippen (`urn:wa:graph:werkgebied:<id>`) erheen als projectie. |

## Endpoints

Alles staat onder `/v1` en vraagt een client-bearer-token (zie §*Authenticatie*). Endpoints die per
gebruiker werken lezen de identiteit uit de header `X-User-Id`, die de webapp-BFF of graph-qa
server-side zet.

**`/docs` (Swagger-UI) en `/openapi.json` zijn de volledige lijst.** Hieronder staan de domeinen, en per
domein met een klein en stabiel oppervlak de routes zelf. Werkgebieden en begrippen tellen samen ruim
honderd routes; die vind je in `/docs`, en het gedrag staat in [`CLAUDE.md`](CLAUDE.md).

| Prefix | Domein | Bereik |
|---|---|---|
| `/v1/annotatie` | Lagen op bronnodes, beslissingen, weergave, zoeken, samenhang, graaf, export | gedeeld |
| `/v1/werkgebieden` | Dossier, bronselecties, deelvragen, bronselectie per deelvraag, inventaris, werkvoorraad, export | gedeeld |
| `/v1/werkgebieden/{id}/begrippen` | Begrippen, koppelingen, voorstellen van Lex per veld | gedeeld |
| `/v1/werkgebieden/{id}/…` | `begrippen-runs`, `groepen`, `verdieping`, `bronnen-runs`, `kandidaten`, `herbeoordelingen`, `dekking`, `relaties`, `regies` (ADR-012) | gedeeld |
| `/v1/begrippen` | Begrippen over werkgebieden heen, generieke begrippen, verificatie voor Lex | gedeeld |
| `/v1/artefact-versies` | De stand van een artefact na een beurt van Lex | gedeeld |
| `/v1/gesprekken` | Chatgeschiedenis | per gebruiker |
| `/v1/verbruik` | Eigen tokenbudget | per gebruiker |
| `/v1/auth` | Login, 2FA, accounttokens, zelfregistratie | – |
| `/v1/berichten`, `/v1/feedback` | Release notes en feedback | – |
| `/v1/admin` | Beheer, achter het admin-token | – |

Routes die alleen graph-qa aanroept (zoals `…/uitkomst`, `…/loopt`, `…/mislukt` van de runs) laat de BFF
niet door.

**Annotatiedomein – annotaties op bronnodes.** Een laag hoort bij één bron-IRI. Lagen
zijn gedeeld tussen gebruikers; wie wat deed staat in de audit. Specificatie:
[`docs/architectuur/annotatie-bronnodes.md`](../docs/architectuur/annotatie-bronnodes.md).

| Methode | Pad | Wat het doet |
|---------|-----|--------------|
| `GET` | `/v1/annotatie/capabilities` | Wat deze api kan (`samenhang`) |
| `GET` | `/v1/annotatie/verklaringen` | Leesbare namen en uitleg van alles wat in een `trace` kan staan |
| `GET` | `/v1/annotatie/weergave` | De bepaling met segmenten, lagen, markeringen en dekking |
| `GET` | `/v1/annotatie/samenhang` | Bronstructuur, annotaties en letterlijke verwijzingen van het artikel, voor de samenhangsgraaf |
| `GET` | `/v1/annotatie/samenhang/meer` | Dezelfde samenhang voor hoogstens 30 bepalingen in één verzoek |
| `GET` | `/v1/annotatie/samenhang/antwoord` | De ketting bij een antwoord: keten, doel, markeringen, begrippen en verwijzingen |
| `GET` | `/v1/annotatie/graaf` | De complete graaf van alle of de gevraagde regelingen, zonder tekst |
| `POST` | `/v1/annotatie/plaatsen` | Regeling en pad van hoogstens 500 bepalingen |
| `GET` | `/v1/annotatie/knoop` | Wat de kennisgraaf over één knoop weet: geldigheid, herkomst, grondslag, genoemd in, begrip, vindplaats, verwijzingen en alle triples ruw |
| `GET` | `/v1/annotatie/dekking` | Is deze bronnode (of subtree) daadwerkelijk behandeld? |
| `POST` | `/v1/annotatie/lagen/batch` | De uitkomst van één agent-ronde, in één transactie (idempotent op `batch_id`) |
| `POST` | `/v1/annotatie/elementen` | Eigen markering van de jurist toevoegen |
| `GET` `DELETE` | `/v1/annotatie/elementen/{id}` | Markering ophalen / een eigen, nog niet beoordeelde markering wissen |
| `GET` | `/v1/annotatie/elementen/{id}/graaf` | De RDF van een markering en de graafcontrole van haar laag |
| `POST` | `/v1/annotatie/elementen/{id}/beslissing` | Beslissing: `approve`/`edit`/`grens`/`reject`/`comment`/`heropen` |
| `POST` | `/v1/annotatie/lagen/{id}/beslissingen` | Bulk op één laag: `approve`/`reject`/`heropen`/`comment`/`edit` (klasse, toelichting), één transactie en één revisie |
| `POST` | `/v1/annotatie/lagen/{id}/status` | Afronden (`geaccordeerd`) of heropenen (`in_review`) |
| `GET` | `/v1/annotatie/lagen/{id}/revisies` | Revisiehistorie van een laag |
| `POST` | `/v1/annotatie/zoeken` | Zoeken in opgeslagen annotaties; kandidaten uit de graaf, geverifieerd tegen PostgreSQL |
| `GET` | `/v1/annotatie/node-lagen` | Overzicht van de lagen (werkvoorraad; `?mijn=`, `?bwbId=`, gepagineerd) |
| `POST` | `/v1/annotatie/weergave/verwijder` | De annotatie van de bepaling in beeld verwijderen (iedere gebruiker; staat in de audit) |
| `POST` | `/v1/annotatie/relaties` | Een relatie tussen twee markeringen leggen (ADR-011; type en klassen uit de catalogus) |
| `POST` | `/v1/annotatie/relaties/{id}/beslissing` | Een relatie goedkeuren, afwijzen, heropenen of becommentariëren |
| `POST` | `/v1/annotatie/relaties/{id}/wis` | Een eigen relatie wissen |
| `POST` | `/v1/annotatie/impliciet` | Een impliciete partij (rechtssubject zonder anker) vastleggen, alleen door de jurist |
| `POST` | `/v1/annotatie/impliciet/{id}/wis` | Een eigen impliciete partij wissen, met haar relaties |
| `POST` | `/v1/annotatie/weergave/export` | Export als `pdf\|csv\|json\|trig` |
| `GET` | `/v1/annotatie/export-schema` | Het JSON-schema van de export |

**Gesprekken** (per gebruiker gescopet):

| Methode | Pad | Wat het doet |
|---------|-----|--------------|
| `POST` `GET` | `/v1/gesprekken` | Gesprek aanmaken / eigen gesprekken |
| `GET` | `/v1/gesprekken?ouder_id=` | De deelgesprekken van een regiegesprek (ADR-012) |
| `GET` `PATCH` `DELETE` | `/v1/gesprekken/{id}` | Ophalen / hernoemen, aan een werkgebied koppelen of archiveren / verwijderen |
| `POST` | `/v1/gesprekken/{id}/berichten` | Bericht toevoegen (idempotent op `run_id`) |

**Login** (de BFF is de enige client), onder `/v1/auth`:

| Methode | Pad | Wat het doet |
|---------|-----|--------------|
| `GET` | `/v1/auth/setup-status` | Is de users-tabel nog leeg? (dan staat de eenmalige registratie open) |
| `POST` | `/v1/auth/setup` | Maak de allereerste beheerder (alleen bij lege tabel, anders 409) |
| `POST` | `/v1/auth/registratie` | Zelfregistratie: vraag toegang aan (eigen rate limit; maakt géén account) |
| `POST` | `/v1/auth/verify` | Valideer userid + wachtwoord (+ TOTP-code of herstelcode) |
| `GET` | `/v1/auth/me` | Eigen account (rol, 2FA-status, `tfa_nodig`, `herstelcodes_over`, de stand van de rondleiding) |
| `PATCH` | `/v1/auth/me/rondleiding` | Stand van de rondleiding: de aangeboden versie (gaat alleen omhoog) en de knop op het startscherm |
| `POST` | `/v1/auth/change-password` | Eigen wachtwoord wijzigen |
| `POST` | `/v1/auth/2fa/{begin,activate,disable}` | TOTP-2FA, self-service; `begin` vraagt het wachtwoord en weigert (409) bij actieve 2FA, behalve mét een code (opnieuw koppelen: de nieuwe app vervangt de oude bij `activate`), `activate` geeft de herstelcodes, `disable` neemt ook een herstelcode en weigert (409) voor een beheerder |
| `POST` | `/v1/auth/2fa/herstelcodes` | Vervang de herstelcodes, met een code uit de app of een herstelcode |
| `POST` | `/v1/auth/api-token/verify` | Wissel een accounttoken in voor de identiteit van het account (alleen met `API_TOKEN_LOGIN`) |
| `GET` | `/v1/auth/api-token/{id}/status` | Geldt het accounttoken nog? (alleen met `API_TOKEN_LOGIN`) |

**Tokenbudget, berichten, feedback, keuzelijst:**

| Methode | Pad | Wat het doet |
|---------|-----|--------------|
| `GET` | `/v1/verbruik` | Eigen stand: percentage, resterend, resetdatum, waarschuwing, blokkade |
| `GET` | `/v1/verbruik/controle` | Mag deze gebruiker een beurt starten? (pre-check van graph-qa) |
| `POST` | `/v1/verbruik` | Boek het verbruik van een afgeronde beurt (idempotent op `run_id`) |
| `GET` | `/v1/berichten` | Gepubliceerde release notes (gepagineerd) |
| `GET` | `/v1/berichten/ongelezen-aantal` | Aantal ongelezen berichten |
| `POST` | `/v1/berichten/lees-alles` | Alles als gelezen markeren |
| `POST` | `/v1/feedback` | Feedback insturen (`verbeteridee`/`probleemmelding`/`compliment`/`vraag`) |

**Beheer**, achter het admin-token, onder `/v1/admin`:

| Methode | Pad | Wat het doet |
|---------|-----|--------------|
| `GET` | `/v1/admin/profiles` | Lijst modelprofielen (nooit de key, alleen `api_key_set`) |
| `GET` `PUT` `DELETE` | `/v1/admin/profiles/{name}` | Ophalen / maken of bijwerken (API-key write-only) / verwijderen (niet de default) |
| `POST` | `/v1/admin/profiles/{name}/default` | Markeer als default |
| `POST` | `/v1/admin/profiles/{name}/test` | Test de verbinding (kleine, betaalde LLM-call) |
| `GET` `POST` | `/v1/admin/users` | Lijst accounts / account maken (geeft eenmalig een tijdelijk wachtwoord) |
| `PATCH` `DELETE` | `/v1/admin/users/{userid}` | Rol/actief wijzigen (laatste actieve beheerder beschermd) / verwijderen |
| `POST` | `/v1/admin/users/{userid}/reset-password` | Nieuw tijdelijk wachtwoord |
| `POST` | `/v1/admin/users/{userid}/verbruik/reset` | Geef een gebruiker zijn volledige budget terug voor dit venster; het journaal blijft intact. Vraagt `X-User-Id` van een beheerder met 2FA |
| `POST` | `/v1/admin/users/{id}/2fa/reset` | Haal 2FA van een ander account; vraagt naast het admin-token `X-User-Id` van een beheerder met 2FA |
| `GET` `POST` | `/v1/admin/api-tokens` | Lijst / nieuw token (eenmalig getoond); met `userid` een accounttoken (409 als `API_TOKEN_LOGIN` uit staat) |
| `DELETE` | `/v1/admin/api-tokens/{id}` | Token intrekken |
| `GET` | `/v1/admin/registraties` | Zelfregistratie-aanvragen (optioneel `?status=aangevraagd`) |
| `POST` | `/v1/admin/registraties/{id}/goedkeuren` | Account aanmaken (userid corrigeerbaar, rol kiesbaar) |
| `POST` | `/v1/admin/registraties/{id}/afwijzen` | Aanvraag verwijderen; de reden gaat naar het security-log |
| `POST` | `/v1/admin/registraties/goedkeuren` | Meerdere tegelijk goedkeuren (best-effort) |
| `DELETE` | `/v1/admin/registraties/{id}` | Goedgekeurde aanvraag uit het archief halen |
| `GET` `PUT` | `/v1/admin/budget` | Tokenbudget-beleid (resetperiode, aan/uit); `GET` toont ook het budget per rol. `PUT` vraagt `X-User-Id` van een beheerder met 2FA |
| `PUT` | `/v1/admin/budget/rollen/{rol}` | Tokenbudget van een rol; vraagt `X-User-Id` van een beheerder met 2FA |
| `GET` | `/v1/admin/verbruik` | Stand per gebruiker, zwaarste verbruiker eerst |
| `GET` `POST` | `/v1/admin/berichten` | Alle berichten / nieuw bericht |
| `PUT` `DELETE` | `/v1/admin/berichten/{id}` | Bewerken / verwijderen |
| `PATCH` | `/v1/admin/berichten/{id}/publicatie` | (De)publiceren |
| `GET` | `/v1/admin/feedback` | Feedback (gepagineerd) |
| `GET` | `/v1/admin/feedback/ongelezen-aantal` | Ongelezen feedback voor deze beheerder |
| `POST` | `/v1/admin/feedback/markeer-gezien` | Feedback als gezien markeren |
| `DELETE` | `/v1/admin/feedback/{id}` | Feedback verwijderen |
| `GET` | `/v1/admin/annotatie/graafcontrole` | Klopt de annotatiegraaf met Postgres? (alleen lezend; `?shacl=false` sneller) |
| `GET` | `/v1/admin/annotatie-statistiek` | Wat juristen met de voorstellen deden (`?limit=` lagen) |

**Zonder auth:** `GET /health` (liveness, met `git_sha` en `build_time`) en `GET /ready` (alleen
booleans: `auth_geconfigureerd`, `llm_model_gezet`, `database_geconfigureerd`).

## Afwijkingen van de REST-richtlijnen, met reden

De API staat achter de BFF; op productie is de ingress intern. De REST-regels gelden bij het aanbieden van een API,
dus hier is afwijken verdedigbaar. Ook graph-qa valt hieronder.

- Geen `API-Version`-header: alle clients (de BFF, graph-qa en op acceptatie de admin-MCP) staan in dezelfde repo.
- Geen `application/problem+json`: de fouten zijn FastAPI-`detail`, en de frontend leest die vorm.
- Geen OpenAPI-`contact`: er is geen externe afnemer.
- `/docs` en `/openapi.json` staan aan, zonder token: de repo is publiek, dus ze tonen niets nieuws. Op acceptatie is de
  ingress publiek (`apiExtern`); de routes onder `/v1` vragen daar een token.

## Model-profielen

De LLM-configuratie leeft in **benoemde modelprofielen** in de database (provider, model, endpoint,
temperatuur, versleutelde API-key). Beheer ze via de admin-endpoints of het beheervenster van de
webapp (`/instellingen/beheer/modelprofielen`); de verbindingstest valideert een profiel met een
kleine LLM-call. De env-`LLM_*`-waarden seeden bij de eerste start één default-profiel en blijven de
fallback-key. Die verbindingstest is de enige LLM-call in deze API. Lex (`graph-qa`) heeft een eigen
LLM-config; deze profielen sturen hem niet aan.

## Lokaal draaien

Vereist [uv](https://docs.astral.sh/uv/), Python ≥ 3.11 en PostgreSQL (image en CI: 16).

```bash
cd api
cp .env.example .env            # minimaal WETSANALYSE_API_TOKENS, WETSANALYSE_ADMIN_TOKENS, DATABASE_URL
uv sync --extra llm --extra dev
uv run --env-file .env uvicorn app.main:app --reload --port 3000
```

`uv run` laadt `.env` **niet** vanzelf; `--env-file .env` is verplicht. Controleer de stand op
`http://localhost:3000/ready`; Swagger staat op `http://localhost:3000/docs`.

Extras: `llm` (LiteLLM, alleen voor de verbindingstest van een modelprofiel), `otel` (OpenTelemetry) en
`dev` (tests, `aiosqlite`).

De opslag is PostgreSQL:

```bash
docker run -d -p 5432:5432 --name wetsanalyse-postgres-lokaal \
  -e POSTGRES_USER=wetsanalyse -e POSTGRES_PASSWORD=wetsanalyse -e POSTGRES_DB=wetsanalyse postgres:16
```

met `DATABASE_URL=postgresql+asyncpg://wetsanalyse:wetsanalyse@localhost:5432/wetsanalyse`. Voor een
snelle smoke-test zonder Postgres volstaat `DATABASE_URL=sqlite+aiosqlite://` (in-memory; de
`dev`-extra levert `aiosqlite`). De tabellen worden bij de start aangemaakt.

Zonder `GRAPHDB_URL` staan de annotatieroutes die een bronboom nodig hebben (`weergave`,
`dekking`, `lagen/batch`, …) op 503 en draait er geen projectie. Wie de werkplek lokaal volledig wil
gebruiken, heeft een GraphDB met de repository `inning` nodig (gevuld door `tools/bwb-import/`).

Een Fernet-key (voor `LLM_CONFIG_SECRET`) genereer je met
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

Tests: `uv run pytest -q` (fakes, in-memory SQLite, geen netwerk). CI draait
`uv run --extra dev --extra llm --extra otel --locked pytest -q`. De postgres-suites draaien alleen met
`ANNOTATIE_TEST_DSN` (een asyncpg-URL), de projectie-integratie ook met `ANNOTATIE_TEST_GRAPHDB_URL`.

## Configuratie

Elke secret is te zetten als `NAAM` of als `NAAM_FILE` (pad naar een bestand); de `_FILE`-variant
wint. Op Azure staan alle secrets als bestand onder `/run/secrets/`.

| Variabele | Default | Betekenis |
|-----------|---------|-----------|
| `WETSANALYSE_API_TOKENS(_FILE)` | – | Client-tokens, `id:token,id2:token2` |
| `WETSANALYSE_AUTH_REQUIRED` | `1` | `0` zet de client-auth uit (alleen lokaal; geldt niet voor `/v1/admin`) |
| `WETSANALYSE_ADMIN_TOKENS(_FILE)` | – | Admin-tokens, zelfde vorm |
| `DATABASE_URL(_FILE)` | `postgresql+asyncpg://localhost:5432/wetsanalyse` | Een kale `postgresql://` wordt naar asyncpg omgezet |
| `WETSANALYSE_DB_CONNECT_RETRIES` / `_BACKOFF` | `30` / `2` (s) | Bounded retry bij het opstarten |
| `LLM_CONFIG_SECRET(_FILE)` | – | Fernet-key; versleutelt de API-keys van profielen en de 2FA-secrets. Zonder: geen key-opslag via de UI, geen 2FA, dus ook geen beheer |
| `LLM_PROVIDER` | `azure_ai` | Seed/fallback van het default-profiel (`azure_ai` = Foundry, `azure` = Azure OpenAI) |
| `LLM_MODEL`, `LLM_API_BASE`, `LLM_API_KEY(_FILE)` | leeg | Idem |
| `LLM_API_VERSION` | – | Alleen voor `azure` |
| `LLM_OUTPUT_STRATEGY` | `prompt_and_parse` | Idem |
| `LLM_TEMPERATURE` | `0` | Idem |
| `LLM_DEFAULT_PROFILE` | `azure-sonnet` | Naam van het geseede profiel |
| `WETSANALYSE_LLM_TIMEOUT_S` | `300` | Wandklok-timeout per LLM-call (`0` = uit) |
| `WETSANALYSE_LLM_MAX_PROMPT_TOKENS` | `0` | Cap op prompt-tokens (`0` = afleiden uit het model) |
| `WETSANALYSE_LLM_PROMPT_CACHING` | `1` | Prompt caching aan/uit |
| `WETSANALYSE_LLM_MAX_CONCURRENCY` | `4` | Plafond op gelijktijdige LLM-calls (`0` = uit) |
| `WETSANALYSE_RATE_LIMIT_MAX` / `_WINDOW` | `30` / `60` (s) | Rate limit op `POST /v1/feedback` (per client), de login (missers per client-IP en userid, plus een ruimer globaal plafond) en wachtwoord en 2FA (per userid); `0` = uit |
| `WETSANALYSE_ADMIN_TEST_RATE_MAX` / `_WINDOW` | `10` / `60` (s) | Rate limit op de verbindingstest |
| `WETSANALYSE_TOKEN_BUDGET` | `500000` | Seed van het tokenbudget van elke rol; daarna leeft het budget per rol in de database |
| `WETSANALYSE_TOKEN_BUDGET_DAGEN` | `7` | Seed van de resetperiode |
| `GRAPHDB_URL` | leeg | GraphDB voor bronboom en projectie; leeg = beide uit |
| `GRAPHDB_REPOSITORY` | `inning` | |
| `JAS_PROJECTIE_INTERVAL` | `60` (s) | Interval van de reconcile-lus van de projectie |
| `API_TOKEN_LOGIN` | uit | Inloggen met een accounttoken (`1` of `true`); alleen op acceptatie aan, en ook nodig op de frontend |
| `CORS_ORIGINS` | leeg | Toegestane browser-origins; leeg = geen cross-origin toegang |
| `LOG_LEVEL` / `LOG_FORMAT` | `info` / `json` | `text` is prettiger lokaal |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | leeg | OpenTelemetry; leeg = alleen logs. Vraagt de extra `otel` |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` | |
| `OTEL_SERVICE_NAME` | `wetsanalyse-api` | |
| `OTEL_METRICS_ENABLED` | `1` | |
| `GIT_SHA`, `BUILD_TIME` | leeg | Build-herkomst op `/health`; CI zet ze |

## Authenticatie

Elke route onder `/v1` vraagt `Authorization: Bearer <token>`; alleen `/health`, `/ready`, `/docs` en
`/openapi.json` niet. Zonder tokens en met `WETSANALYSE_AUTH_REQUIRED=1` geeft alles 401 (fail-closed).

De **admin-endpoints** (`/v1/admin/*`) accepteren de tokens uit `WETSANALYSE_ADMIN_TOKENS` plus
intrekbare DB-tokens (`/v1/admin/api-tokens`), en zijn **altijd** auth-plichtig: `AUTH_REQUIRED=0`
geldt hier niet.

**Accounttokens** (prefix `wa_pat_`, 90 dagen geldig) horen bij één account. De BFF wisselt ze in voor een
gewone sessie; ze openen `/v1/admin` nooit. Zonder `API_TOKEN_LOGIN` geven de routes 404.

## Uitrol

Op Azure draait de API als container app `<appName>-api` (`deploy/azure/main.bicep`), met Azure
PostgreSQL Flexible Server als database en `GRAPHDB_URL` naar de interne GraphDB van dezelfde
straat. De ingress is intern op productie en publiek op acceptatie, voor de admin-MCP en de
acceptatie-MCP. Het image `ghcr.io/<owner>/wetsanalyse-api` bouwt `api-docker-publish.yml` vanaf de
**projectroot**:

```bash
docker build -f api/Dockerfile -t wetsanalyse-api .
```

De build-context is de projectroot omdat het image `packages/bronmodel` meeneemt. Uitrollen naar
acceptatie en productie, en het beheer van de secrets: zie [`CLAUDE.md`](CLAUDE.md#uitrol) en
[`deploy/azure/README.md`](../deploy/azure/README.md).

### Troubleshooting

- **Kan niet verbinden met de database / `OperationalError`**: controleer de `database-url`-secret
  op de container app en of de PostgreSQL-firewall de container-apps-omgeving toelaat.
- **Revisie komt niet op**: `az containerapp revision list` toont de status; de logs staan in de
  Log Analytics-workspace `log-<appName>`.
- **503 "De brongraaf is tijdelijk niet beschikbaar"** op annotatieroutes: GraphDB is onbereikbaar
  of de repository ontbreekt; de graafwacht van de importer vult hem opnieuw.
- **Alles geeft 401**: `WETSANALYSE_API_TOKENS` is leeg terwijl auth aanstaat. Vul tokens, of zet lokaal
  `WETSANALYSE_AUTH_REQUIRED=0`.
- **De API start met lege configuratie**: `--env-file .env` ontbreekt bij `uv run`.
- **Niemand kan 2FA koppelen, dus het beheer blijft dicht**: `LLM_CONFIG_SECRET` ontbreekt.

## Observability

JSON-logs op stdout, en OpenTelemetry zodra `OTEL_EXPORTER_OTLP_ENDPOINT` gezet is. Zie
[`docs/observability.md`](../docs/observability.md).
