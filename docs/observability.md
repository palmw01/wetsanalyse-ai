# Observability – logging, traces & metrics

Dit project is **geïnstrumenteerd, niet bemeterd**: elke component emitteert gestructureerde logs én
kan OpenTelemetry (traces/metrics/logs) naar een **configureerbaar OTLP-endpoint** sturen. Zonder
endpoint draait alles ongewijzigd met alléén gestructureerde JSON-logging (nul overhead, geen
gedragsverandering).

**De monitoring hoort bij de omgeving die hij bewaakt.** Sinds de dev-omgeving is opgeheven
(27 aug 2026) is dat er nog één:

| omgeving | verzamelpunt | waar kijk je |
|---|---|---|
| **acceptatie / productie** (Azure) | een stateless OTel-collector per straat → **Application Insights**, workspace-based op de Log Analytics van die straat | de Azure-portal (end-to-end transacties, Application Map, KQL) of Grafana |

**De keten deelt één trace-id** – frontend → api → PostgreSQL onder dezelfde `OperationId`,
geverifieerd op acceptatie (26 aug 2026). Dat gaat niet vanzelf: `@vercel/otel` maakt wél spans voor
uitgaande `fetch`, maar zet géén `traceparent` op de request. De BFF injecteert hem daarom zelf
(`frontend/app/api/_lib/trace.ts`, op elke fetch naar een upstream).

Controleer het na een wijziging aan de BFF-routes, want het faalt stil: je ziet gewoon telemetrie,
alleen elke dienst in zijn eigen trace. Zo doe je dat: stuur een request met een eigen `traceparent`-header en kijk of alle diensten
onder dat trace-id verschijnen.

```
curl -H "traceparent: 00-<32 hex>-<16 hex>-01" https://<frontend>/api/health
```

```kusto
union AppRequests, AppDependencies
| where OperationId == "<32 hex>"
| project TimeGenerated, AppRoleName, Name, Id, ParentId
```

Geslaagd = de api verschijnt in die lijst met een `ParentId` die naar een frontend-span wijst.
Zo is het op 26 aug 2026 op beide straten vastgesteld; in productie kwam er zelfs een trace langs die
frontend, api én graph-qa omspande.

`NEXT_OTEL_FETCH_DISABLED=1` staat op de frontend. Dat was een eerdere poging tot een fix en loste
niets op; het klopt nu pas echt, want er ís een eigen fetch-instrumentatie (`metTrace()`).

**Grafana draait op Azure** (`deploy/azure/grafana.bicep`, uitrollen met `azure-infra` → actie
`grafana`): één exemplaar met een datasource per straat, en per straat een dashboard in de map
*Wetsanalyse*. Elke span draagt daarnaast `deployment.environment=<appName>`, zodat acceptatie en
productie ook binnen één workspace te scheiden zijn. De dashboards staan als
sjabloon in `deploy/azure/grafana/` en worden per straat ingevuld. Draai de `grafana`-actie in **één**
straat: dat ene exemplaar leest beide workspaces.

## Wat is geïnstrumenteerd

| Component | Logging | Traces | Metrics |
|-----------|---------|--------|---------|
| **API** (`api/`, FastAPI) | JSON-`dictConfig`, request-id-middleware, access-log | FastAPI-requests, DB | http-server-latency, request-count/foutrate (auto) |
| **Frontend** (`frontend/`, Next.js) | server-side JSON naar stdout in de BFF-lagen | `@vercel/otel`: route handlers + uitgaande `fetch` (traceparent) | request-count/latency (auto) |
| **graph-qa** (`tools/graph-qa/`) | gestructureerde JSON-logs | `/v1/runs` (de weg van de werkplek) en `/v1/chat` + GraphDB-MCP-calls | http-server-latency (auto) |

De **GraphDB-kennisgraaf en de externe diensten** (overheid.nl-bronnen, de LLM-provider) draaien buiten
deze repo en zijn niet geïnstrumenteerd; ze verschijnen in de traces als virtuele peer-node (zie de
service-graph-connector) i.p.v. als eigen span.

## Correlatie

Eén **trace-id** verbindt de keten: `frontend → API → PostgreSQL` en `frontend → graph-qa` (`/v1/runs`, SSE; `/v1/chat` is de niet-webapp-weg). OTel propageert automatisch via de W3C-`traceparent`-header op
uitgaande `fetch`/httpx-calls. Elke logregel draagt `trace_id`/`span_id` zodra er een span actief is,
plus (in de API) een `request_id` per inkomend verzoek (`X-Request-Id`, gegenereerd of overgenomen en
in de response geëchood).

## Logschema

Alle loggers delen dezelfde vorm (bv. `frontend/lib/logger.ts`):

```json
{"ts":"2026-07-16T14:37:23.698Z","niveau":"info","categorie":"functioneel",
 "bericht":"...","trace_id":"…","span_id":"…","<vrije velden>":"…"}
```

- `niveau`: `debug|info|warn|error` (drempel via `LOG_LEVEL`).
- `categorie`: `functioneel` (verkeer) · `audit` (wie deed wat) · `security` (auth/abuse).
- **AVG/dataminimalisatie**: tokens, secrets en verzoek-/antwoordinhoud (chatInput, prompts) worden
  **nooit** gelogd – alleen metadata (status, duur, lengtes, ids, paden). Geheime veldnamen worden
  defensief geredacteerd.

## Aanzetten

Zet in elke stack (of `.env`) het endpoint van je OTel-Collector; laat 'm leeg om OTel uit te houden.

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318   # leeg = uit (alleen JSON-logs)
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf                # API/graph-qa; frontend gebruikt @vercel/otel
OTEL_SERVICE_NAME=wetsanalyse-api                        # per component (zie compose-defaults)
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=productie
LOG_LEVEL=info
LOG_FORMAT=json                                          # API: 'text' is prettiger lokaal
```

De env-vars staan in de `.env.example`'s en (voor Azure) in `main.bicep` (param `otelEndpoint`). In de **API-image** is de `otel`-extra meegebouwd
(`uv sync --extra otel`); lokaal draai je met `uv sync --extra otel`.

## Grafana

Grafana draait als container app naast de straten (`deploy/azure/grafana.bicep`), uit te rollen met
`azure-infra` → actie `grafana`. Draai die in **één** straat: dat exemplaar leest beide workspaces via
een datasource per straat, en krijgt per straat een dashboard in de map *Wetsanalyse*. Alles komt
as-code uit `deploy/azure/grafana/`; er is geen persistente opslag, dus wijzig dashboards daar en niet
in de UI.

Het dashboard is één sjabloon (`dashboard-keten.json`) met placeholders die de bicep per straat
invult: `__STRAAT__`, `__SLUG__`, `__DSUID__`, `__WORKSPACE__` en `__APPNAME__`. Voeg je een
placeholder toe, vul hem dan in **beide** `replace()`-ketens (`dashAcc` en `dashPrd`) – anders staat
de letterlijke tekst in de query van één straat.

## Waarom het endpoint env-config is (en niet in /beheer)

Het OTLP-endpoint is **boot-tijd-infraconfiguratie** via env/compose, niet iets uit het
`/beheer`-scherm. Reden: OpenTelemetry initialiseert **één keer bij processtart** en de
SDK-providers/exporters zijn *set-once* – ze kunnen niet live herpoint worden. Bovendien draaien de
drie services in **aparte containers** met hun eigen env (niet de API-database waar `/beheer` naar
schrijft). Een `/beheer`-veld zou dus alleen de API raken én pas ná herstart werken; env houden is
eerlijker en eenduidiger.

## Verifiëren

- **No-op-gating**: start zonder endpoint → alles draait, alleen JSON-logs.
- **Trace-correlatie**: de werkplek loopt frontend → graph-qa (`/v1/runs`, SSE); login/beheer loopt
  frontend → API → PostgreSQL – één trace deelt de `trace_id`.
- **Geen lek**: `grep` de logoutput op `bearer`/`secret`/de chat-`secret`-waarde → leeg.

### Waar de telemetrie landt, en hoe je hem bevraagt

Alles komt via de collector in **Application Insights** terecht, workspace-based op de Log Analytics
van die straat. Je bevraagt hem met KQL, in de portal of via `azure-infra` → actie `telemetrie`
(read-only; het `query`-veld accepteert een eigen KQL-query, en dat is de manier om een dashboardquery
te toetsen zonder portaltoegang).

De tabellen: `AppRequests` (inkomende requests), `AppDependencies` (uitgaande calls), `AppTraces`
(logregels) en `AppExceptions`. Diensten onderscheid je via **`AppRoleName`** – `wetsanalyse-api`,
`wetsanalyse-frontend`, `wetsanalyse-graph-qa`. Alle drie dragen hetzelfde prefix, zodat één filter de
hele keten vangt; dat was niet altijd zo, want graph-qa heette tot 27 aug 2026 kaal `graph-qa` en viel
daardoor stil buiten ketenbrede queries. Elke span draagt daarnaast
`deployment.environment=<appName>`.

Drie valkuilen, alle drie een keer ingelopen:

- **De console-logs staan in `ContainerAppConsoleLogs_CL`**, met de kolommen `ContainerAppName_s` en
  `Log_s`. De tabel zónder `_CL` bestaat óók en is **altijd leeg** – een query daarop geeft netjes nul
  rijen in plaats van een fout, en is dus niet te onderscheiden van "er is niets aan de hand".
- **`Success == false` is niet hetzelfde als 5xx.** Application Insights rekent ook 4xx als
  niet-succesvol, dus een golf 401's presenteert zich als serverstoring. Wil je echte serverfouten,
  filter dan op `toint(ResultCode) >= 500`.
- **Health-probes domineren het volume.** Container Apps pollt `/health`, `/ready` en `/api/health`
  onophoudelijk; dat was ~95% van alle requests, waardoor beide straten op vrijwel hetzelfde getal
  uitkwamen en het echte verkeer erin verdronk. De dashboardqueries filteren ze daarom expliciet weg.

### Wat je in de errorlog aantreft, en wat het betekent

Gemeten op 27 aug 2026 over 24 uur, beide straten: **geen enkele echte applicatiefout**. Wat er wél
staat, staat er structureel – herken het voordat je gaat zoeken.

**Verreweg het meeste is OTLP-export, niet je applicatie.** Regels als `Failed to export span/logs/
metrics batch – HTTPConnectionPool(host='…-otel-collector', port=80): Connection refused` waren 353
van de 355 meldingen op acceptatie en 52 van de 56 op productie. Ze komen in **bursts rond een
deploy** (305 in het uur van de eerste uitrol, daarna 18, 20, 4) en zijn ertussenin afwezig.

Dat tijdstip is de aanwijzing: bij een deploy wordt de collector zélf opnieuw uitgerold, en tijdens
die wissel verliezen de draaiende apps kortstondig hun exportdoel. Het is nadrukkelijk **niet**
scale-to-zero – de collector staat bewust op `minReplicas: 1` (zie `main.bicep`, met de motivering
dat een exporter het na één poging opgeeft). Die verklaring stond hier eerst wél, en was fout.

Dat patroon is het signaal, niet het niveau. De SDK buffert en probeert opnieuw, dus je verliest
hooguit de eerste seconden telemetrie na een deploy. **Een burst na een uitrol is normaal; een
continue stroom is dat niet** – dán is de collector echt weg en is je observability stuk. Ze landen
als `error` omdat de OTel-SDK dat niveau kiest; dat is bewust zo gelaten, want een `warn` zou het
onderscheid tussen burst en stroom net zo min maken.

**`Run-proxy: actieve run niet op te halen`** (frontend, een enkele keer per dag) is een koude start
van graph-qa tegen de 10-secondentimeout van `frontend/app/api/annotatie/run/route.ts`. De gebruiker
merkt er niets van: de route geeft bewust géén `null` terug – dat zou "er loopt niets" betekenen,
een uitspraak die je hier niet kunt doen – en de client leest het als "onbekend" en zwijgt. Die
timeout niet verhogen: dan wacht de gebruiker een halve minuut op hetzelfde antwoord.

Zoek je dus een echte fout, sluit deze twee uit:

```kql
ContainerAppConsoleLogs_CL
| where TimeGenerated > ago(24h)
| extend j = parse_json(Log_s)
| extend niveau = tolower(tostring(j.niveau))
| where niveau in ('error', 'warn')
| where not(Log_s has_any ('otel-collector', 'exporting', 'export'))
| project TimeGenerated, ContainerAppName_s, niveau, bericht = tostring(j.bericht)
| order by TimeGenerated desc
```

Let op de vorm van dat filter: `has` matcht op **termen**, dus `'export'` vangt `exporting` niet —
vandaar dat beide in de lijst staan. Precies daarop liep de eerste versie van deze query mis.

> **graph-qa is meestal onzichtbaar, en dat klopt.** Hij draait met `minReplicas: 0`
> (`deploy/azure/main.bicep`), dus buiten gebruik zijn er nul replica's: geen liveness-probes, geen
> requests, geen telemetrie. Een leeg paneel betekent hier "er wordt niet gewerkt", niet "de meting is
> stuk" – in een etmaal zijn 9 à 16 requests normaal. De eerste vraag na stilte bevat bovendien een
> koude start; die telt mee in de p95, naast de LLM-tijd van de run zelf.

> **Houdbaarheid: de attributen zijn de pre-1.0 OTel-conventie.** `http_target`/`http_status_code`
> heten in de stabiele HTTP-semconv `http_route` en `http_response_status_code`, en de
> server-duurmetriek gaat van milliseconden naar `http.server.request.duration` in **seconden**. Bij
> een SDK- of collector-upgrade die de nieuwe conventie aanzet, verandert dus wat er binnenkomt – loop
> bij zo'n upgrade de queries in `deploy/azure/grafana/` na. Wie de overgang geleidelijk wil doen, kan
> tijdelijk `OTEL_SEMCONV_STABILITY_OPT_IN=http/dup` zetten: dan emitteert de SDK beide namen naast
> elkaar.
