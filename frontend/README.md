# Wetsanalyse-frontend

Next.js (App Router) + TypeScript-webapp. De app **is de werkplek**: een chat-achtige werkruimte
tegen de graph-qa-agent **Lex**; login, beheer en alles wat bewaard blijft lopen via de
[Wetsanalyse-API](../api). Architectuurregels, invarianten en valkuilen voor wie code wijzigt staan
in [`CLAUDE.md`](CLAUDE.md).

- **De werkplek** (`/workbench`, de *Lex-pagina*; `/` leidt hierheen door): één gespreksvenster met
  twee werkwijzen – **vragen** aan Lex (brongetrouwe Q&A over de kennisgraaf) en **JAS-annotatie**
  (Lex stelt markeringen voor, de jurist beoordeelt ze per element). De beurt draait bij graph-qa,
  de werkplek kijkt mee via SSE; de review-state staat in de API.
- **De annotaties** staan los van de gesprekken: `/annotaties` is het overzicht, `/annotaties/node`
  toont één bronnode-annotatie (contract 2) en `/annotaties/<slug>` een artikeldocument. Beide tonen
  dezelfde inhoud als het paneel in de werkplek.
- **Het instellingenvenster** (`/instellingen/*`) opent als dialoog over de werkplek heen: account
  (wachtwoord, 2FA, verbruik), berichten en – voor beheerders – modelprofielen, gebruikers,
  aanvragen, API-tokens, berichtenbeheer en feedback. Het beheer loopt via `/api/admin/*` met een
  apart admin-token. `/beheer` en `/account` zijn redirects naar de bijbehorende tab.

## Architectuur – BFF met server-side token

De browser praat **uitsluitend** met de eigen Next.js-origin (`/api/**`). Die Route Handlers (de
_backend-for-frontend_) proxyen server-side naar de API en graph-qa en injecteren het Bearer-token,
dat dus nooit in de browser komt. Daarmee vervalt CORS (same-origin) en werkt SSE (de native
`EventSource` kan geen `Authorization`-header sturen; de BFF doet dat en pipet de stream door).

```
Browser ──/api/**──► Next.js (BFF, injecteert token) ──/v1/**──► wetsanalyse-api:3000
                                                     ──/v1/**──► graph-qa:8080
```

## Vormgeving – Rijkshuisstijl (Belastingdienst)

De app volgt de **Rijkshuisstijl** in het Belastingdienst-stijlvak: lintblauw `#154273` + hemelblauw
`#007bc7` op wit, het officiële Belastingdienst-logo (`public/belastingdienst-logo.svg`, ongewijzigd)
en **Fira Sans/Mono** als vrij alternatief voor Rijksoverheid Sans. De design tokens staan centraal
(CSS-variabelen in `app/globals.css` → Tailwind in `tailwind.config.ts`), de primitives in
`components/ui/` (40px-knoppen/velden, 48px op aanraakschermen). De **JAS-klassekleuren**
(`lib/jas.ts`) zijn de labelkleuren uit de officiële JAS-tabel `docs/wetsanalyse/wa-table.png`.
Kleur en typografie lopen via de tokens, niet via losse hex-waarden.

## Lokaal draaien

Vereist een draaiende API (zie [`../api/CLAUDE.md`](../api/CLAUDE.md)) en, voor de werkplek, een
bereikbare graph-qa.

```bash
cd frontend
cp .env.example .env.local      # vul API_BASE_URL, API_TOKEN, ADMIN_API_TOKEN, AUTH_SECRET, GRAPH_QA_URL
npm install
npm run dev                     # http://localhost:3000
```

Draait de lokale API óók op poort 3000, start de frontend dan op een andere poort:
`npm run dev -- -p 3001`. De tokenwaarden zijn **alleen het deel na de `:`** uit de token-lijst van
de API (`API_TOKEN` uit de gewone lijst, `ADMIN_API_TOKEN` uit de admin-lijst).

> **Eerste keer inloggen.** De webapp zit volledig achter een login met **userid** + wachtwoord;
> e-mail is verplicht en uniek maar geen inlog-identiteit. Is de users-tabel van de API leeg, dan
> stuurt de app je naar `/setup` om eenmalig de eerste **beheerder** aan te maken; daarna sluit die
> route. Verdere gebruikers (rol `analist` of `beheerder`) maak je aan in de beheertab
> **Gebruikers** (eenmalig tijdelijk wachtwoord), of ze melden zich zelf aan op `/registreren`: die
> aanvraag levert pas een account op als een beheerder hem goedkeurt in de tab **Aanvragen**. 2FA
> (TOTP) is optioneel en zet de gebruiker zelf aan in de accounttab; daarvoor moet
> `LLM_CONFIG_SECRET` op de **API** gezet zijn (de TOTP-secrets worden ermee versleuteld).

Zonder sessie bereikbaar zijn alleen `/login`, `/setup`, `/registreren`, `/disclaimer` en
`/api/health` (plus de bijbehorende BFF-routes); de rest stuurt naar `/login`. De beheertabs zijn
bovendien afgeschermd tot de rol `beheerder`.

## Scripts

| Commando               | Doel                                                                 |
| ---------------------- | -------------------------------------------------------------------- |
| `npm run dev`          | Dev-server (hot reload)                                              |
| `npm run build`        | Productiebuild (`output: 'standalone'`)                              |
| `npm start`            | Productieserver (na build)                                           |
| `npm run lint`         | ESLint                                                               |
| `npm run typecheck`    | `tsc --noEmit`                                                       |
| `npm test`             | Vitest (node-env, zonder DOM)                                        |
| `npm run test:browser` | Playwright tegen een devserver op poort 3109 met gemockte BFF (`scripts/test-*.mjs`, zie `CLAUDE.md`) |

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
| `LOG_LEVEL`            | `info`                        | Niveau van de JSON-logger. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | leeg                   | OTLP-endpoint; leeg = OpenTelemetry uit, alleen logs. |

## Observability

De BFF is geïnstrumenteerd via `@vercel/otel` (`instrumentation.ts`): tracing van route handlers en
uitgaande `fetch`, alleen actief als `OTEL_EXPORTER_OTLP_ENDPOINT` gezet is. `lib/trace.ts` zet de
`traceparent` op elke upstream-fetch, `lib/logger.ts` is de server-only JSON-logger. Zie
`CLAUDE.md` §Observability en [`../docs/observability.md`](../docs/observability.md).

## Docker en uitrol

Multi-stage `Dockerfile` (standalone, non-root). CI: `.github/workflows/frontend-docker-publish.yml`
(lint, typecheck, test, build, npm audit → image naar GHCR → Trivy), met daarna een `deploy`-job die
het image op acceptatie uitrolt. Productie loopt via `promote.yml` (zie de projectroot-`CLAUDE.md`).

Op Azure draait de frontend als container app met externe ingress (`deploy/azure/main.bicep`); hij
praat server→server met de API en graph-qa, die allebei intern-only zijn. De tokens en het
`AUTH_SECRET` komen als secret-bestanden onder `/run/secrets/` binnen (`API_TOKEN_FILE`,
`ADMIN_API_TOKEN_FILE`, `GRAPH_QA_TOKEN_FILE`, `AUTH_SECRET_FILE`); `AUTH_URL` staat op de publieke
origin van de container app. 2FA hergebruikt de Fernet-sleutel van de API; de frontend heeft
daarvoor geen eigen secret.

## Types bijhouden

`lib/types.ts` is met de hand afgeleid van `api/app/annotatie_contracts.py`,
`api/app/annotatie_v2_contracts.py` en `api/app/gesprek_contracts.py`, en is de bron van waarheid
aan de TS-kant. Controleren tegen het live OpenAPI-schema bij een contractwijziging:

```bash
npx openapi-typescript http://localhost:3000/openapi.json -o lib/openapi.d.ts
```
