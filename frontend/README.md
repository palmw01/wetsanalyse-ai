# Wetsanalyse-frontend

Next.js-webapp (App Router, TypeScript) van het platform. De app **is de werkplek**: een gesprek met
de agent **Lex** (graph-qa), met daarnaast alles wat dat gesprek oplevert. Login, beheer en alles wat
bewaard blijft lopen via de [Wetsanalyse-API](../api/README.md). Regels, invarianten en valkuilen voor
wie code wijzigt staan in [`CLAUDE.md`](CLAUDE.md).

## Wat er in de app zit

| Pad | Wat je er doet |
|---|---|
| `/workbench` (`/` leidt hierheen) | Eén gespreksvenster voor vragen en werk: bepalingen laten annoteren, een werkgebied samenstellen, bronnen per deelvraag kiezen, begrippen uitwerken. Wat een beurt oplevert (een *artefact*) opent naast het gesprek, met een versiekiezer. |
| `/annotaties` | Overzicht van de gedeelde annotaties. `/annotaties/node` toont één bronnode-annotatie, `/annotaties/element/[id]` één markering. |
| `/werkgebieden` | Overzicht, en per werkgebied de tabs Overzicht, Gesprekken, Bronnen, Artefacten en Historie, met detailpagina's voor deelvragen, begrippen en het dossier. Aanmaken gaat via Lex. |
| `/begrippen` | Begrippen over alle werkgebieden heen; `/begrippen/[id]` is de pagina van een generiek begrip. |
| `/bronnen?bron_iri=…` | De pagina van één bepaling: wettekst met markeringen en wat de kennisgraaf erover weet. |
| `/instellingen/*` | Dialoog over de werkplek: account (wachtwoord, 2FA, verbruik), berichten en voor beheerders modelprofielen, gebruikers, aanvragen, API-tokens, berichtenbeheer en feedback. `/beheer` en `/account` leiden door naar de juiste tab. |
| `/login`, `/login/2fa`, `/setup`, `/registreren`, `/disclaimer` | Inloggen, de eerste beheerder, toegang aanvragen en de disclaimer. |

## Architectuur: BFF met server-side token

De browser praat **uitsluitend** met de eigen Next.js-origin (`/api/**`). Die Route Handlers (de
_backend-for-frontend_) proxyen server-side naar de API en graph-qa en injecteren het Bearer-token,
dat dus nooit in de browser komt. Daarmee vervalt CORS (same-origin). De werkplek leest de
SSE-stroom van een lopende beurt met `fetch`; de BFF geeft de stroom ongewijzigd door.

```
Browser ──/api/**──► Next.js (BFF, injecteert token) ──/v1/**──► wetsanalyse-api:3000
                                                     ──/v1/**──► graph-qa:8080
```

Werkgebieden en begrippen lopen via catch-all-routes met een allowlist (`isWerkgebiedRoute`,
`isGeneriekRoute`): een nieuwe api-route vraagt daar een regel. Wat Lex doet, start als beurt in het
gesprek (`/api/annotatie/run`); een pagina start geen run.

## Vormgeving

De app volgt de **Rijkshuisstijl** in het Belastingdienst-stijlvak. Tokens staan in `app/globals.css`
en `tailwind.config.ts`, de primitives in `components/ui/`. De regels staan in
[`CLAUDE.md`](CLAUDE.md) (§*Vormgeving*).

## Lokaal draaien

Vereist Node.js (CI en image draaien op 26), npm, een draaiende API (zie
[`../api/README.md`](../api/README.md)) en, voor de werkplek, een bereikbare graph-qa.

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev -- -p 3001          # http://localhost:3001; 3000 is voor de API
```

Pas `.env.local` eerst aan, want het voorbeeld wijst naar containernamen:

- `API_BASE_URL=http://localhost:3000`, en voor de agent `GRAPH_QA_URL=http://localhost:8080` plus
  `GRAPH_QA_TOKEN` (gelijk aan `QA_API_TOKEN` van de agent);
- `API_TOKEN` en `ADMIN_API_TOKEN`: **alleen het deel na de `:`** uit de tokenlijsten van de API;
- `AUTH_SECRET`: `openssl rand -base64 32`.

> **Eerste keer inloggen.** De webapp zit volledig achter een login met **userid** + wachtwoord;
> e-mail is verplicht en uniek maar geen inlog-identiteit. Is de users-tabel van de API leeg, dan
> stuurt de app je naar `/setup` om eenmalig de eerste **beheerder** aan te maken; daarna sluit die
> route. Verdere gebruikers (rol `analist` of `beheerder`) maak je aan in de beheertab
> **Gebruikers** (eenmalig tijdelijk wachtwoord), of ze melden zich zelf aan op `/registreren`: die
> aanvraag levert pas een account op als een beheerder hem goedkeurt in de tab **Aanvragen**. 2FA
> (TOTP) zet de gebruiker zelf aan in de tab Beveiliging, en is verplicht voor wie het beheer wil gebruiken;
> daarvoor moet `LLM_CONFIG_SECRET` op de **API** gezet zijn (de TOTP-secrets worden ermee versleuteld).

Zonder sessie bereikbaar zijn alleen `/login`, `/login/2fa`, `/setup`, `/registreren`, `/disclaimer` en
`/api/health` (plus de bijbehorende BFF-routes). Voor de rest is een sessie vereist; `/api/**` geeft
zonder sessie 401 als JSON. Na het inloggen vraagt de app eerst akkoord op de disclaimer. De beheertabs
zijn afgeschermd tot de rol `beheerder` met 2FA.

## Scripts

| Commando               | Doel                                                                 |
| ---------------------- | -------------------------------------------------------------------- |
| `npm run dev`          | Dev-server (hot reload)                                              |
| `npm run build`        | Productiebuild (`output: 'standalone'`)                              |
| `npm start`            | Productieserver (na build)                                           |
| `npm run lint`         | ESLint                                                               |
| `npm run typecheck`    | `tsc --noEmit`                                                       |
| `npm test`             | Vitest (node-env, zonder DOM)                                        |
| `npm run test:watch`   | Vitest in watch-modus                                                |
| `npm run test:browser` | Playwright-regressie met gemockte BFF (`scripts/test-*.mjs`)         |

`test:browser` start zelf geen server. In CI gaat het zo, in twee shells:

```bash
npx playwright install --with-deps chromium
AUTH_SECRET=test-only AUTH_TRUST_HOST=true npm run dev -- --hostname 127.0.0.1 --port 3109
```

```bash
npm run test:browser
```

`TEST_URL` overschrijft de basis-URL (default `http://localhost:3109`).

## Omgevingsvariabelen

| Variabele              | Default                       | Beschrijving |
| ---------------------- | ----------------------------- | ------------ |
| `API_BASE_URL`         | `http://wetsanalyse-api:3000` | Server-side adres van de API. |
| `API_TOKEN`            | –                             | Bearer-token voor de API (server-side). |
| `API_TOKEN_FILE`       | –                             | Pad naar een secret-bestand met dat token (heeft voorrang). |
| `ADMIN_API_TOKEN`      | –                             | Admin-bearer voor de beheertabs → `/v1/admin/*` (server-side). |
| `ADMIN_API_TOKEN_FILE` | –                             | Pad naar een secret-bestand met het admin-token (heeft voorrang). |
| `GRAPH_QA_URL`         | `http://graph-qa:8080`        | Server-side adres van graph-qa (de werkplek). |
| `GRAPH_QA_TOKEN`       | –                             | Bearer voor graph-qa (= `QA_API_TOKEN` aan de agentkant). Leeg mag alleen als de agent geen token eist. |
| `GRAPH_QA_TOKEN_FILE`  | –                             | Pad naar een secret-bestand met het graph-qa-token (heeft voorrang). |
| `AUTH_SECRET`          | –                             | Ondertekent de Auth.js-sessiecookie/JWT. Verplicht (`openssl rand -base64 32`). |
| `AUTH_SECRET_FILE`     | –                             | Pad naar een secret-bestand; `docker-entrypoint.sh` laadt het in `AUTH_SECRET` als dat leeg is (Auth.js kent zelf geen `*_FILE`). |
| `AUTH_URL`             | –                             | Publieke origin. **Verplicht achter een reverse proxy** – anders redirecten login/logout naar het interne `0.0.0.0:3000`. |
| `API_TOKEN_LOGIN`      | uit                           | Inloggen met een accounttoken (`1` of `true`); alleen op acceptatie aan, en ook nodig op de API. |
| `LOG_LEVEL`            | `info`                        | Niveau van de JSON-logger. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | leeg                   | OTLP-endpoint; leeg = OpenTelemetry uit, alleen logs. |
| `OTEL_SERVICE_NAME`    | `wetsanalyse-frontend`        | Servicenaam in de traces. |

## Problemen oplossen

| Symptoom | Oorzaak en oplossing |
|---|---|
| `/instellingen/beheer/…` geeft 403 | De gebruiker heeft rol `analist`, de beheerder heeft nog geen 2FA gekoppeld, of `ADMIN_API_TOKEN` ontbreekt. |
| Inloggen springt naar een intern adres | `AUTH_URL` staat niet op de publieke origin. |
| De werkplek bereikt Lex niet | `GRAPH_QA_URL` wijst nog naar de containernaam, of `GRAPH_QA_TOKEN` wijkt af van `QA_API_TOKEN`. |
| De werkplek toont 0 elementen | SSE-frames worden met `\r\n` gescheiden; een handgeschreven parser die de CR niet stript, levert stil niets op. |
| Een filter werkt niet, zonder foutmelding | Een BFF-proxyroute stuurt de query-parameter niet door. |

## Observability

JSON-logs op stdout, en OpenTelemetry zodra `OTEL_EXPORTER_OTLP_ENDPOINT` gezet is. Een BFF-route die
zelf fetcht gebruikt `metTrace()` uit `lib/trace.ts`, anders valt de keten stil uiteen in losse
traces. Zie [`CLAUDE.md`](CLAUDE.md) §*Observability* en
[`../docs/observability.md`](../docs/observability.md).

## Docker en uitrol

Multi-stage `Dockerfile` (standalone, non-root), bouwcontext `frontend/`. Het image start met
`node server.js` via `docker-entrypoint.sh`, op poort 3000, met health op `/api/health`.

```bash
docker build -t wetsanalyse-frontend frontend
```

CI: `.github/workflows/frontend-docker-publish.yml` (lint, typecheck, test, build, npm audit → image
naar GHCR → Trivy), met daarna een `deploy`-job die het image op acceptatie uitrolt. Productie loopt
via `promote.yml`; zie [`../deploy/azure/README.md`](../deploy/azure/README.md).

Op Azure draait de frontend als container app met externe ingress (`deploy/azure/main.bicep`). Hij
praat server→server met de API en graph-qa: graph-qa is overal intern, de API is intern op productie
en publiek op acceptatie. De tokens en het `AUTH_SECRET` komen als secret-bestanden onder
`/run/secrets/` binnen (`API_TOKEN_FILE`, `ADMIN_API_TOKEN_FILE`, `GRAPH_QA_TOKEN_FILE`,
`AUTH_SECRET_FILE`); `AUTH_URL` staat op de publieke origin van de container app. 2FA hergebruikt de
Fernet-sleutel van de API; de frontend heeft daarvoor geen eigen secret.

## Types bijhouden

`lib/types.ts` is met de hand afgeleid van `api/app/annotatie_v2_contracts.py`,
`gesprek_contracts.py`, `werkgebied_contracts.py` en `begrip_contracts.py`, en is de bron van waarheid
aan de TS-kant. Controleren tegen het live OpenAPI-schema bij een contractwijziging, zonder iets in de
repo achter te laten:

```bash
npx openapi-typescript http://localhost:3000/openapi.json -o /tmp/wetsanalyse-openapi.d.ts
```
