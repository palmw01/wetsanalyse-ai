# wetsanalyse-api

Headless HTTP-backend voor de **Wetsanalyse-werkplek**, onder de [frontend](../frontend). De API
bedient:

- het **JAS-annotatiedomein** (markeringen, beslissingen, een append-only auditlog en export), op
  **contract 2**: één laag per bronnode (artikel, lid of onderdeel);
- de **chatgeschiedenis** van de werkplek;
- **login en gebruikersbeheer** – de API is de identiteitsbron van de webapp, inclusief
  zelfregistratie en optionele TOTP-2FA;
- het **LLM-modelprofielbeheer** en de **profiel-keuzelijst**;
- het **tokenbudget** per gebruiker;
- **berichten** (release notes) en **gebruikersfeedback**.

> **De QA/annotatie-agent is een aparte dienst.** `tools/graph-qa/` (Lex) beantwoordt de vragen,
> stelt de JAS-annotaties voor en levert de wettekst uit de graaf; de werkplek praat er direct mee
> (SSE). Deze API bewaart de review-state, projecteert de annotatielagen naar de kennisgraaf en
> bedient login en beheer.

Wie de code wijzigt: lees [`CLAUDE.md`](CLAUDE.md) (architectuur, invarianten, valkuilen).

## Hoe het past in het project

| Onderdeel | Rol |
|-----------|-----|
| **graph-qa** | Lex – beantwoordt vragen, stelt JAS-annotaties voor, levert de wettekst; schrijft de uitkomst van een beurt naar deze API. Eigen LLM-config. |
| **wetsanalyse-api** *(deze map)* | Annotatiedomein, gesprekken, login, beheer, tokenbudget. |
| **PostgreSQL** | De waarheid: annotatielagen + audit, gesprekken, gebruikers, modelprofielen, API-tokens, verbruik. |
| **GraphDB** | Leest de BWB-bronboom (voor ankers en snapshots); de API schrijft de annotatielagen erheen als projectie (`urn:jas:graph:v2:<laag-id>`). |

## Endpoints

Alles staat onder `/v1` en vraagt een client-bearer-token (zie §*Authenticatie*). Endpoints die per
gebruiker werken lezen de identiteit uit de header `X-User-Id`, die de webapp-BFF of graph-qa
server-side zet. Swagger-UI: `/docs`.

**Annotatiedomein, contract 2 – annotaties op bronnodes.** Een laag hoort bij één bron-IRI. Lagen
zijn gedeeld tussen gebruikers; wie wat deed staat in de audit. Specificatie:
[`docs/architectuur/annotatie-bronnodes.md`](../docs/architectuur/annotatie-bronnodes.md).

| Methode | Pad | Wat het doet |
|---------|-----|--------------|
| `GET` | `/v1/annotatie/capabilities` | Welke contractversie actief is |
| `GET` | `/v1/annotatie/verklaringen` | Leesbare namen en uitleg van alles wat in een `trace` kan staan |
| `GET` | `/v1/annotatie/weergave` | De bepaling met segmenten, lagen, markeringen en dekking |
| `GET` | `/v1/annotatie/samenhang` | Bronstructuur, annotaties en letterlijke verwijzingen van het artikel (3D-weergave) |
| `GET` | `/v1/annotatie/dekking` | Is deze bronnode (of subtree) daadwerkelijk behandeld? |
| `POST` | `/v1/annotatie/lagen/batch` | De uitkomst van één agent-ronde, in één transactie (idempotent op `batch_id`) |
| `POST` | `/v1/annotatie/elementen` | Eigen markering van de jurist toevoegen |
| `GET` `DELETE` | `/v1/annotatie/elementen/{id}` | Markering ophalen / een eigen, nog niet beoordeelde markering wissen |
| `POST` | `/v1/annotatie/elementen/{id}/beslissing` | Beslissing: `approve`/`edit`/`reject`/`comment`/`heropen` |
| `POST` | `/v1/annotatie/lagen/{id}/status` | Afronden (`geaccordeerd`) of heropenen (`in_review`) |
| `POST` | `/v1/annotatie/zoeken` | Zoeken in opgeslagen annotaties; kandidaten uit de graaf, geverifieerd tegen PostgreSQL |
| `GET` | `/v1/annotatie/node-lagen` | Overzicht van de lagen (werkvoorraad; `?mijn=`, `?bwbId=`, gepagineerd) |
| `POST` | `/v1/annotatie/weergave/verwijder` | De annotatie van de bepaling in beeld verwijderen (iedere gebruiker; staat in de audit) |
| `POST` | `/v1/annotatie/weergave/export` | Export als `pdf\|csv\|json` |

**Artikelbrede routes (contract 1).** De code bestaat nog en de routes zijn geregistreerd. Onder
contract 2 (de default) geven `POST`/`PUT`/`PATCH` hierop een **409**, behalve de export; `GET` en
`DELETE` werken.

| Methode | Pad | Wat het doet |
|---------|-----|--------------|
| `POST` `GET` | `/v1/annotatie/documenten` | Document aanmaken / lijst met werkvoorraad |
| `GET` `DELETE` | `/v1/annotatie/documenten/{slug}` | Document ophalen / verwijderen |
| `PUT` `POST` | `/v1/annotatie/documenten/{slug}/elementen` | Agent-ronde opslaan (MERGE, optioneel `If-Match`) / eigen markering toevoegen |
| `DELETE` | `/v1/annotatie/documenten/{slug}/elementen/{id}` | Eigen markering verwijderen |
| `POST` | `/v1/annotatie/documenten/{slug}/elementen/{id}/beslissing` | Beslissing |
| `POST` | `/v1/annotatie/documenten/{slug}/status` | Afronden of heropenen |
| `POST` | `/v1/annotatie/documenten/{slug}/export` | Export (`?formaat=pdf\|csv\|json`) |
| `GET` | `/v1/annotatie/documenten/{slug}/audit` | Auditlog van het document (gepagineerd) |
| `GET` | `/v1/annotatie/lagen` | Lijst van de gedeelde artikellagen |
| `GET` | `/v1/annotatie/lagen/{bwbId}/{artikel}` | De gedeelde laag van een artikel |
| `PUT` | `/v1/annotatie/lagen/{bwbId}/{artikel}/elementen` | Agent-ronde samenvoegen in de artikellaag |
| `POST` | `/v1/annotatie/lagen/{bwbId}/{artikel}/hergebruik` | Vastleggen dat Lex de laag hergebruikte |

**Gesprekken** (per gebruiker gescopet):

| Methode | Pad | Wat het doet |
|---------|-----|--------------|
| `POST` `GET` | `/v1/gesprekken` | Gesprek aanmaken / eigen gesprekken |
| `GET` `PATCH` `DELETE` | `/v1/gesprekken/{id}` | Ophalen / hernoemen / verwijderen |
| `POST` | `/v1/gesprekken/{id}/berichten` | Bericht toevoegen (idempotent op `run_id`) |

**Login** (de BFF is de enige client), onder `/v1/auth`:

| Methode | Pad | Wat het doet |
|---------|-----|--------------|
| `GET` | `/v1/auth/setup-status` | Is de users-tabel nog leeg? (dan staat de eenmalige registratie open) |
| `POST` | `/v1/auth/setup` | Maak de allereerste beheerder (alleen bij lege tabel, anders 409) |
| `POST` | `/v1/auth/registratie` | Zelfregistratie: vraag toegang aan (eigen rate limit; maakt géén account) |
| `POST` | `/v1/auth/verify` | Valideer userid + wachtwoord (+ optionele TOTP) |
| `GET` | `/v1/auth/me` | Eigen account (rol + 2FA-status) |
| `POST` | `/v1/auth/change-password` | Eigen wachtwoord wijzigen |
| `POST` | `/v1/auth/2fa/{begin,activate,disable}` | Optionele TOTP-2FA, self-service |

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
| `GET` | `/v1/profiles` | Keuzelijst modelprofielen (alleen naam + default) |

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
| `GET` `POST` | `/v1/admin/api-tokens` | Lijst / nieuw token (eenmalig getoond) |
| `DELETE` | `/v1/admin/api-tokens/{id}` | Token intrekken |
| `GET` | `/v1/admin/registraties` | Zelfregistratie-aanvragen (optioneel `?status=aangevraagd`) |
| `POST` | `/v1/admin/registraties/{id}/goedkeuren` | Account aanmaken (userid corrigeerbaar, rol kiesbaar) |
| `POST` | `/v1/admin/registraties/{id}/afwijzen` | Aanvraag verwijderen; de reden gaat naar het security-log |
| `POST` | `/v1/admin/registraties/goedkeuren` | Meerdere tegelijk goedkeuren (best-effort) |
| `DELETE` | `/v1/admin/registraties/{id}` | Goedgekeurde aanvraag uit het archief halen |
| `GET` `PUT` | `/v1/admin/budget` | Tokenbudget-beleid (budget, resetperiode, aan/uit) |
| `GET` | `/v1/admin/verbruik` | Stand per gebruiker, zwaarste verbruiker eerst |
| `GET` `POST` | `/v1/admin/berichten` | Alle berichten / nieuw bericht |
| `PUT` `DELETE` | `/v1/admin/berichten/{id}` | Bewerken / verwijderen |
| `PATCH` | `/v1/admin/berichten/{id}/publicatie` | (De)publiceren |
| `GET` | `/v1/admin/feedback` | Feedback (gepagineerd) |
| `GET` | `/v1/admin/feedback/ongelezen-aantal` | Ongelezen feedback voor deze beheerder |
| `POST` | `/v1/admin/feedback/markeer-gezien` | Feedback als gezien markeren |
| `DELETE` | `/v1/admin/feedback/{id}` | Feedback verwijderen |
| `GET` | `/v1/admin/annotatie/graafcontrole` | Klopt de annotatiegraaf met Postgres? (alleen lezend; `?shacl=false` sneller) |
| `GET` | `/v1/admin/annotatie-statistiek` | Wat juristen met de voorstellen deden (artikelbrede documenten) |
| `GET` | `/v1/admin/annotatie/projectie` | Stand van de projectie van de artikellagen |
| `POST` | `/v1/admin/annotatie/herprojecteer` | Alle artikellagen opnieuw laten projecteren |
| `POST` | `/v1/admin/annotatie/migreer-naar-lagen` | Documenten samenvoegen tot artikellagen; onder contract 2 een 409 |

**Zonder auth:** `GET /health` (liveness, met `git_sha` en `build_time`) en `GET /ready` (alleen
booleans: `auth_geconfigureerd`, `llm_model_gezet`, `database_geconfigureerd`).

## Model-profielen

De LLM-configuratie leeft in **benoemde modelprofielen** in de database (provider, model, endpoint,
temperatuur, versleutelde API-key). Beheer ze via de admin-endpoints of het beheervenster van de
webapp (`/instellingen/beheer/modelprofielen`); de verbindingstest valideert een profiel met een
kleine LLM-call. De env-`LLM_*`-waarden seeden bij de eerste start één default-profiel en blijven de
fallback-key. Die verbindingstest is de enige LLM-call in deze API. Lex (`graph-qa`) heeft een eigen
LLM-config; deze profielen sturen hem niet aan.

## Lokaal draaien

```bash
cd api
cp .env.example .env            # vul in; zie §Configuratie
uv sync --extra llm --extra dev
uv run --env-file .env uvicorn app.main:app --reload --port 3000
```

`uv run` laadt `.env` **niet** vanzelf; `--env-file .env` is verplicht. Swagger:
`http://localhost:3000/docs`.

De opslag is PostgreSQL:

```bash
docker run -d -p 5432:5432 --name wetsanalyse-postgres-lokaal \
  -e POSTGRES_USER=wetsanalyse -e POSTGRES_PASSWORD=wetsanalyse -e POSTGRES_DB=wetsanalyse postgres:16
```

met `DATABASE_URL=postgresql+asyncpg://wetsanalyse:wetsanalyse@localhost:5432/wetsanalyse`. Voor een
snelle smoke-test zonder Postgres volstaat `DATABASE_URL=sqlite+aiosqlite://` (in-memory; de
`dev`-extra levert `aiosqlite`). De tabellen worden bij de start aangemaakt.

Zonder `GRAPHDB_URL` staan de routes van contract 2 die een bronboom nodig hebben (`weergave`,
`dekking`, `lagen/batch`, …) op 503 en draait er geen projectie. Wie de werkplek lokaal volledig wil
gebruiken, heeft een GraphDB met de repository `inning` nodig (gevuld door `tools/bwb-import/`).

Een Fernet-key (voor `LLM_CONFIG_SECRET`) genereer je met
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

Tests: `uv run pytest -q` (fakes, in-memory SQLite, geen netwerk).

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
| `LLM_CONFIG_SECRET(_FILE)` | – | Fernet-key; versleutelt de API-keys van profielen en de 2FA-secrets. Zonder: geen key-opslag via de UI |
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
| `WETSANALYSE_RATE_LIMIT_MAX` / `_WINDOW` | `30` / `60` (s) | Rate limit per client (`0` = uit) |
| `WETSANALYSE_ADMIN_TEST_RATE_MAX` / `_WINDOW` | `10` / `60` (s) | Rate limit op de verbindingstest |
| `WETSANALYSE_TOKEN_BUDGET` | `500000` | Seed van het tokenbudget; daarna leeft het beleid in de database |
| `WETSANALYSE_TOKEN_BUDGET_DAGEN` | `7` | Seed van de resetperiode |
| `ANNOTATIE_CONTRACT_VERSIE` | `2` | `2` = bronnode-lagen; `1` = artikelbrede documenten (v2-routes geven dan 503) |
| `GRAPHDB_URL` | leeg | GraphDB voor bronboom en projectie; leeg = beide uit |
| `GRAPHDB_REPOSITORY` | `inning` | |
| `JAS_PROJECTIE_INTERVAL` | `60` (s) | Interval van de reconcile-lus van de projectie |
| `CORS_ORIGINS` | leeg | Toegestane browser-origins; leeg = geen cross-origin toegang |
| `LOG_LEVEL` / `LOG_FORMAT` | `info` / `json` | `text` is prettiger lokaal |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | leeg | OpenTelemetry; leeg = alleen logs |
| `OTEL_SERVICE_NAME` | `wetsanalyse-api` | |
| `OTEL_METRICS_ENABLED` | `1` | |
| `GIT_SHA`, `BUILD_TIME` | leeg | Build-herkomst op `/health`; CI zet ze |

## Authenticatie

Elke request (behalve `/health` en `/ready`) vraagt `Authorization: Bearer <token>`. Zonder tokens
en met `WETSANALYSE_AUTH_REQUIRED=1` geeft alles 401 (fail-closed).

De **admin-endpoints** (`/v1/admin/*`) accepteren de tokens uit `WETSANALYSE_ADMIN_TOKENS` plus
intrekbare DB-tokens (`/v1/admin/api-tokens`), en zijn **altijd** auth-plichtig: `AUTH_REQUIRED=0`
geldt hier niet.

## Uitrol

Op Azure draait de API als container app `<appName>-api` (`deploy/azure/main.bicep`), met Azure
PostgreSQL Flexible Server als database en `GRAPHDB_URL` naar de interne GraphDB van dezelfde
straat. Het image `ghcr.io/<owner>/wetsanalyse-api` bouwt `api-docker-publish.yml` vanaf de
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
  of leeg; de graafwacht van de importer vult hem opnieuw.
- **409 "Annotaties gebruiken nu bronnode-lagen"**: een client schrijft naar een artikelbrede
  route terwijl contract 2 actief is.

## Observability

Gestructureerde JSON-logging (request-id-middleware, secret-redactie) plus OpenTelemetry
(traces/metrics/logs), gated op `OTEL_EXPORTER_OTLP_ENDPOINT`. Eén trace-id verbindt frontend →
API → graph-qa. Zie `app/observability.py` en [`docs/observability.md`](../docs/observability.md).
