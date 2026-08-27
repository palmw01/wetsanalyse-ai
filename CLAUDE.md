# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Wat dit project is

Een **agent-platform** voor **Wetsanalyse**: het gestructureerd, brongetrouw en traceerbaar duiden
van Nederlandse wet- en regelgeving volgens de methode Wetsanalyse (Ausems, Bulles & Lokin) en het
Juridisch Analyseschema (JAS). De kern is een gedeployde dienst — de **wetsanalyse-API**, de
**webapp met de werkplek** en de eigen **QA/annotatie-agent (`tools/graph-qa/`, **Lex**)** op de
**BWB-kennisgraaf** — die als container apps op Azure draait. De graaf wordt gevuld
door de **BWB-importer** (`tools/bwb-import/`), die de wettekst rechtstreeks bij overheid.nl ophaalt.

Brongetrouwheid is niet onderhandelbaar: werk alleen met letterlijk opgehaalde wettekst, citeer
letterlijk, en houd elke markering/annotatie herleidbaar naar artikel + lid + `bronreferentie`
(jci-uri). Het platform is een hulpmiddel voor de jurist, geen vervanger — de AI produceert, de mens
beoordeelt en corrigeert; interpretatiekeuzes (incl. twijfel en aannames) worden expliciet gemaakt in
plaats van schijnzekerheid.

> **Scope: activiteit 2.** Het platform levert het markeren + classificeren in JAS-klassen; alle
> contracten dragen `scope: "act2"`. Begrippen (activiteit 3) en de RegelSpraak-formalisering horen
> niet tot de huidige functionaliteit — die worden later op agentische basis gebouwd. graph-qa's
> begrip-definitie-QA (de `definitie`-specialist over de graaf) staat daar los van.

### Platform-componenten

1. **`api/`** — headless FastAPI-backend (PostgreSQL-opslag, per-client bearer-auth) voor de werkplek.
   Bedient het **annotatie-domein** (`/v1/annotatie/*`: documenten/elementen/beslissingen +
   append-only auditlog), de **chatgeschiedenis** (`/v1/gesprekken/*`), het
   **login-/gebruikersbeheer** (de API is de identiteitsbron van de webapp), het
   **LLM-modelprofielbeheer** (`/v1/admin/*`; de env-`LLM_*`-waarden seeden alleen het eerste
   default-profiel) en de **profiel-keuzelijst** (`/v1/profiles`). Annotatie-documenten en gesprekken
   zijn **per gebruiker gescopet**. Eigen `CLAUDE.md` + `README.md`.
2. **`frontend/`** — Next.js-webapp (BFF) bovenop de API. De app **is de werkplek** (`/workbench`, de
   *Lex-pagina*): één chat-achtig gespreksvenster voor **vragen én JAS-annotatie**, live tegen
   graph-qa (SSE); de home leidt daarheen door. Account, beheer en instellingen openen als
   **dialoog over de werkplek heen** (`/instellingen/*`, intercepting routes) in plaats van als eigen
   pagina's; de beheertab (modelprofielen, gebruikers, API-tokens) zit achter een apart admin-token.
   De hele webapp zit achter een **login met userid + wachtwoord** (Auth.js; e-mail verplicht/uniek
   maar geen inlog-identiteit; de API is de identiteitsbron; rollen `beheerder`/`analist`; eenmalige
   eerste-beheerder-registratie via `/setup`; optionele TOTP-2FA). De UI volgt de **Rijkshuisstijl**
   (Belastingdienst-stijlvak: lintblauw, Fira-fonts, het officiële Belastingdienst-logo en
   JAS-klassekleuren uit `docs/wetsanalyse/wa-table.png`). Eigen `CLAUDE.md` + `README.md`.
3. **`tools/graph-qa/`** — de eigen **QA/annotatie-agent**, **Lex** (de naam die de gebruiker ziet; de
   code, het image en de stack heten `graph-qa`), die vragen over
   wet- en regelgeving beantwoordt door de BWB-**kennisgraaf** (GraphDB via MCP) te bevragen en het
   antwoord **brongetrouw** te onderbouwen (grounding + bronnen uit de tool-trace). Eén **unified
   LangGraph-agent**: een **supervisor** kiest per vraag een worker-keten — de **antwoord-worker**
   (specialisten `definitie`/`duiding`/`algemeen`: agent ⇄ tools → verify → finalize) of de
   **annotatie-worker** (ophaal → annoteer → **Critic** → advance, met aandacht-niveau 🟢🟡🔴).
   Endpoints: `POST /v1/runs` (+ `/events`, `/cancel`; de weg van de werkplek — de beurt draait bij de
   agent, de browser kijkt mee), `POST /v1/chat` (SSE, aan de verbinding gekoppeld en **zonder
   eigenaarscontrole** — niet voor de webapp) en `GET /v1/artikel`. De werkplek praat er **direct** mee (SSE);
   de persistente review-state loopt via de API (`/v1/annotatie/*`). Image `ghcr.io/palmw01/graph-qa`.
   Eigen `CLAUDE.md` + `README.md`.
4. **`tools/bwb-import/`** — de **BWB-importer**: haalt de wettekst op bij
   `repository.officiele-overheidspublicaties.nl`, valideert tegen de officiële XSD's, parseert de
   structuur (regeling → hoofdstuk/afdeling → artikel → lid → onderdeel, met verwijzingen) en schrijft
   RDF naar GraphDB, repository `inning`. Met `BWB_IMPORT_WTI=true` komt de WTI-verrijking mee:
   verantwoordelijke organisatie, wetsfamilie, grondslagen, rechtsgebieden, citeertitels. Per wet
   **idempotent** (named-graph `PUT`), dus herimporteren is veilig. Image
   `ghcr.io/palmw01/bwb-import`; draait op Azure als container-app-job met een wekelijkse cron-trigger
   (`deploy/azure/main.bicep`).
5. **De kennisgraaf zelf** (`deploy/azure/main.bicep`) — GraphDB 11.4 met de repository `inning`, plus een
   nginx'je dat het bearer-token controleert en het GraphDB-service-account injecteert. **GraphDB
   ≥ 11.2 heeft de MCP-server ingebouwd** op `/mcp`, dus er is geen aparte MCP-container.
   GraphDB-security staat aan. De opslag is **niet-persistent** (memory-mapped files kunnen geen
   netwerkschijf gebruiken), maar de graaf is volledig reproduceerbaar uit overheid.nl — zie
   §*Uitrollen*.
6. **`.claude/skills/wetsanalyse/`** — de inhoudelijke skill: de operationele uitwerking van de
   JAS-methode (de dertien klassen, het volg-beleid voor verwijzingen, de reviewcontracten) plus de
   scripts eromheen. Zie §*De wetsanalyse-skill*.

### Ondersteunende tools

- **`tools/wetsanalyse-admin-mcp/`** — stdio-MCP die de admin-API (`/v1/admin/*`) als tools ontsluit.

## De onderdelen hangen via paden samen

Dit is een verzameling losse onderdelen, geen monorepo met één buildsysteem. Het bindmiddel
zijn **projectrelatieve paden**, zodat de map portabel is tussen machines/OS'en:

- `.claude/settings.local.json` → een **machine-lokale** allowlist plus de tokens (o.a.
  `WETSANALYSE_ADMIN_TOKEN`). Dit bestand is **gitignored**, dus het reist niet mee: een andere machine/analist bouwt z'n eigen lijst opnieuw op
  via de permissieprompts. De allowlist is bewust krap en portabel — de grants gebruiken wildcards
  in plaats van absolute paden.

Let op bij hernoemen/verplaatsen van de projectmap: een padmismatch leidt hooguit tot een extra
permissieprompt (geen stille breuk). Draai daarna `claude mcp list` → verwacht `✓ Connected`.

## Veelgebruikte commando's

Per onderdeel gelden eigen commando's — zie de respectievelijke `CLAUDE.md`/`README.md`
(`api/`, `frontend/`, `tools/graph-qa/`, `tools/bwb-import/`, `tools/wetsanalyse-admin-mcp/`).
Sessie-MCP-gezondheid vanuit de projectroot: `claude mcp list`.

## De wetsanalyse-skill

`.claude/skills/wetsanalyse/SKILL.md` beschrijft de JAS-methode: de scope (activiteit 2), het
onderscheid werkgebied/bron, de dertien klassen en het volg-beleid voor verwijzingen. Twee dingen om
te weten:

**Het is documentatie, geen code.** De skill draagt de methode; het platform voert hem uit. De
kennisgraaf levert de wettekst, de agent stelt markeringen voor en de jurist beoordeelt ze in de
werkplek. Er zit geen uitvoerbare werkstroom meer in de skill — de reviewlus, de rapportbouw en de
write-guard-hook die daarbij hoorden zijn op 27 aug 2026 verwijderd, samen met de dode
wettenbank-MCP-stap die ze voedde.

**De canonieke klassenlijst staat in de api**, niet meer hier: `api/app/jas_klassen.py`. Die stond
eerder in een skill-script dat de api op runtime inlaadde, waardoor het productie-image een
Claude-skill moest meedragen om te kunnen starten. `frontend/lib/jas.ts` en
`tools/graph-qa/agent/jas_klassen.py` dragen dezelfde waarden, elk met een drift-test erop.

De inhoudelijke `references/` blijven de operationele uitwerking van de methode:

- `references/jas-klassen-referentie.md` — de dertien JAS-klassen. Verzin er geen bij.
- `references/verwijzingen-volgen.md` — het volg-beleid voor cross-referenties: functies,
  diepte-cap 1 + relevantie-gate, bounded delegaties. Een gevolgde delegatie/definitie kan
  promoveren tot een eigen bron in het werkgebied.

## Observability

Alle draaiende onderdelen (API, frontend, graph-qa) zijn **geïnstrumenteerd, niet bemeterd**:
ze emitteren gestructureerde JSON-logs (één gedeelde vorm, bv. `frontend/lib/logger.ts`)
en kunnen OpenTelemetry (traces/metrics/logs) naar een **configureerbaar OTLP-endpoint** sturen
(`OTEL_EXPORTER_OTLP_ENDPOINT`; leeg = alleen logs, nul overhead). Eén trace-id verbindt de keten
frontend → API → graph-qa, geverifieerd op acceptatie (26 aug 2026).

Dat gaat niet vanzelf: `@vercel/otel` maakt wél spans voor uitgaande `fetch`, maar zet géén
`traceparent` op de request. De BFF injecteert hem daarom zelf — `frontend/app/api/_lib/trace.ts`, op
elke fetch naar een upstream. Voeg je een BFF-route toe die zelf fetcht, gebruik dan `metTrace()`;
laat je het weg, dan faalt het **stil**: telemetrie komt gewoon binnen, alleen het verband tussen de
diensten ontbreekt. Zie `docs/observability.md` voor de controle-meting.

**Waar dat endpoint heen wijst verschilt per omgeving, en dat is opzet — de monitoring hoort bij de
omgeving die hij bewaakt.** Op **Azure** (acceptatie en productie) staat per straat een stateless
OTel-collector die doorschrijft naar **Application Insights**, workspace-based op dezelfde Log
Analytics waar de stdout-logs landen; kijken doe je in de portal (Transaction search, Application
map). Elke span draagt `deployment.environment=<appName>`. Application Insights kent geen
OTLP-ingest — vandaar die collector, en niet de Azure-distro in de apps: die zou drie diensten
vendor-locken op de plek waar het ontwerp juist provider-neutraal is.

**Grafana staat als container app naast de straten** (`deploy/azure/grafana.bicep`, uitrollen met
`azure-infra` → actie `grafana`): één exemplaar met een datasource én een dashboard per straat, bereikbaar zonder
portaltoegang, zonder persistente opslag (alles komt as-code uit `deploy/azure/grafana/`). Hij draagt
de SP-credentials als datasource-auth — een managed identity kan niet, want dat vraagt een role
assignment.

Draai de actie in **één** straat: die ene Grafana leest beide workspaces, dus een tweede exemplaar
is dubbelop. Het dashboard `deploy/azure/grafana/dashboard-keten.json` is één sjabloon dat per straat
wordt ingevuld (`__STRAAT__`, `__WORKSPACE__`, `__DSUID__`, `__APPNAME__`). De volledige uitleg
(env-vars, logschema, AVG-redactie) staat in **`docs/observability.md`**.

## Uitrollen

**Azure is de uitrolplek.** Twee straten, elk een zelfstandige omgeving (eigen PostgreSQL, GraphDB,
importer, api, graph-qa, frontend) in een eigen resource group:

| straat | wanneer | `appName` | poort ervoor |
|---|---|---|---|
| **acceptatie** | elke merge naar `master` | `wetsanalyse` | geen — automatisch |
| **productie** | een tag `v*` | `wetsanalyse-prd` | required reviewer op de GitHub-environment |

**Beide straten staan in dezelfde resource group `rg-wetsanalyse`.** De service principal is
Contributor op die groep en mag er geen tweede aanmaken, dus scheiden gebeurt via `appName` — de
bicep is daar volledig op geparametriseerd. Gevolgen om te kennen: geen RBAC-scheiding tussen de
straten, `afbreken` haalt ze allebei weg, en kosten scheid je via de tag `straat: <appName>` die op
elke resource staat. De `opruimen`-actie kent beide straten via de repo-vars `ACCEPTATIE_APP_NAME`
en `PRODUCTIE_APP_NAME` — een derde straat hoort daar ook in, anders ruimt hij die op als wees.

De vier `*-docker-publish.yml`-workflows bouwen naar GHCR (pip-audit/npm-audit vooraf, Trivy-gate
achteraf) en hebben daarna een aparte **`deploy`-job** naar acceptatie; ze luisteren niet op tags.
Productie loopt via **`promote.yml`**: dat bouwt niets, maar neemt de digests over die op acceptatie
draaien — een herbouw van dezelfde broncode levert nog altijd een ander artefact op. Het toetst
daarbij het OCI-label `org.opencontainers.image.revision` tegen de commit achter de tag, zodat er
niets anders uitrolt dan de tag belooft. De credentials, resource group en `APP_NAME` komen uit de
GitHub-environment; de menselijke poort vóór productie zit daar ook, en niet in een
workflow-conditie.

**De applicatie-secrets roteren niet bij een infra-deploy.** `azure-infra.yml` neemt ze over —
GitHub environment-secret (`WA_*`) → wat er in Azure draait → anders vers genereren. Dat is geen
netheid maar noodzaak: `llm-config-secret` is de Fernet-sleutel waarmee de api de API-keys van
modelprofielen én de 2FA-secrets van gebruikers versleutelt.

Twee dingen die die job bewust doet en die je niet moet weghalen: hij **faalt** bij een ontbrekend
secret (dat was eerder een `if` die de stap oversloeg en de run groen liet), en hij **wacht na het
uitrollen tot elke app een gezonde revisie draait**. Dat laatste is nodig omdat
`az deployment group create` al terugkeert zodra de revisie is *aangemaakt*, niet zodra hij draait —
een container die bij het starten crasht bleef anders onopgemerkt en de run gewoon groen. `ScaledToZero`
telt daarbij als gezond: api en graph-qa staan op `minReplicas: 0` en zijn na een deploy zonder
verkeer terecht ingeschaald.

Diezelfde gate zit in de publish-workflows en in `promote.yml`; tot 27 aug 2026 ontbrak hij juist in
de infra-deploy, terwijl deze tekst hem al beschreef.

**Infra blijft handmatig.** `azure-infra.yml` (bicep) is de enige die resources aanmaakt, wijzigt of
verwijdert: kies de straat + `wat-if` (valideert, maakt niets aan), `deploy`, `afbreken`,
`vul-graaf` of `inventaris`. `wat-if` is de default omdat een deploy GraphDB raakt. Zie
`deploy/azure/README.md` — let vooral op de GraphDB-licentie, zonder welke de graaf read-only opkomt.

**De graaf op Azure is niet-persistent, en vult zichzelf.** GraphDB gebruikt memory-mapped files en
kan daarom geen netwerkschijf gebruiken; de graaf is echter volledig reproduceerbaar uit
overheid.nl. Daarom start `azure-infra.yml` de import-job automatisch na elke `deploy`, en draait
diezelfde job wekelijks via een cron-trigger in de bicep. Let op: de similarity-index
(`bwb_similarity`) overleeft een herstart evenmin, en tot hij herbouwd is degradeert
`semantic_search` naar `search_wetgeving`.

**Logs** landen in een Log Analytics workspace per straat (`log-${appName}`, aan de container-apps-
omgeving gekoppeld). Traces/metrics staan uit: `OTEL_EXPORTER_OTLP_ENDPOINT` is leeg.

**Er is geen dev-omgeving meer.** De docker-host-opstelling (Portainer-stacks voor dev, graaf,
importer en observability) is op 27 aug 2026 opgeheven; Azure is sindsdien het enige uitrolpad en
**acceptatie vervult de rol van dev**. Wie een wijziging wil proberen, merget naar `master` en kijkt
op acceptatie.

## Referentiedocumentatie

`docs/` bevat de methodische onderbouwing (niet code):

- `docs/wetsanalyse/` — het bronmateriaal van de methode: `WetsTaal.md`, de JAS-tabel
  `wa-table.png` en `wetsanalyse-rijk/` (hoofdstukken over JAS en het kader, van BZK onder de
  W3C-licentie — zie `wetsanalyse-rijk/BRON.md`). Raadpleeg deze bij inhoudelijke vragen over de
  methode; de skill-`references/` zijn de operationele samenvatting daarvan.

  **Lokaal-only, bewust niet in de repo:** `wetsanalyse-boek.md` (het boek van Boom uitgevers) en
  `handleiding.pages.md`/`leidraad.pages.md` (readers van het Expertisecentrum BRM, "bestemd voor
  gebruik binnen de Belastingdienst"). Deze repo is publiek; dat materiaal is van derden en hoort
  er niet in. Ze stonden er van 13 t/m 27 aug 2026 wél in, doordat de `.gitignore`-regel één
  mapniveau te hoog stond en dus nooit greep. Heb je ze lokaal, dan werken ze gewoon; controleer
  na een wijziging aan die regels altijd met `git check-ignore -v`.
- `docs/regelspraak/` — de RegelSpraak-specificaties (PDF), voor de latere formaliseringsfase.
  Ook lokaal-only (gitignored), dus afwezig in een verse kloon.
- `docs/wetsanalyse-workbench/` — het plan achter de werkplek + de JAS-annotatie-ontologie.
- `docs/kennisbank/PLAN.md` — het gefaseerde plan voor een **tweede corpus** naast de wetsgraaf
  (beleidsstukken en handleidingen die Lex samen met de wettekst mag bevragen). Nog niet gebouwd;
  lees het vóór je aan retrieval of grounding werkt, want het stelt eisen aan beide.
- `docs/observability.md` en `docs/schrijfrichtlijn-lex.md` (de toon van Lex; zijn identiteit staat in
  `tools/graph-qa/agent/prompts.py`).
