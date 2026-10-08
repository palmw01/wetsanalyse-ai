# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Wat dit project is

Een **agent-platform** voor **Wetsanalyse**: het gestructureerd, brongetrouw en traceerbaar duiden
van Nederlandse wet- en regelgeving volgens de methode Wetsanalyse (Ausems, Bulles & Lokin) en het
Juridisch Analyseschema (JAS). De kern is een gedeployde dienst – de **wetsanalyse-API**, de
**webapp met de werkplek** en de eigen **QA/annotatie-agent (`tools/graph-qa/`, **Lex**)** op de
**BWB-kennisgraaf** – die als container apps op Azure draait. De graaf wordt gevuld
door de **BWB-importer** (`tools/bwb-import/`), die de wettekst rechtstreeks bij overheid.nl ophaalt.

Brongetrouwheid is niet onderhandelbaar: werk alleen met letterlijk opgehaalde wettekst, citeer
letterlijk, en houd elke markering/annotatie herleidbaar naar artikel + lid + `bronreferentie`
(jci-uri). Het platform is een hulpmiddel voor de jurist, geen vervanger – de AI produceert, de mens
beoordeelt en corrigeert; interpretatiekeuzes (incl. twijfel en aannames) worden expliciet gemaakt in
plaats van schijnzekerheid.

> **Scope: activiteit 2.** Het platform levert het markeren + classificeren in JAS-klassen; alle
> contracten dragen `scope: "act2"`. Begrippen (activiteit 3) en de RegelSpraak-formalisering horen
> niet tot de huidige functionaliteit – die worden later op agentische basis gebouwd. graph-qa's
> begrip-definitie-QA (de `definitie`-specialist over de graaf) staat daar los van.

### Platform-componenten

Details per component staan in de eigen `CLAUDE.md` (bouwen, testen, invarianten, valkuilen) en
`README.md` (draaien, configuratie): [`api/`](api/CLAUDE.md), [`frontend/`](frontend/CLAUDE.md),
[`tools/graph-qa/`](tools/graph-qa/CLAUDE.md). Hieronder alleen wat je nodig hebt om het geheel te
overzien.

1. **`api/`** – headless FastAPI-backend (PostgreSQL-opslag, per-client bearer-auth) voor de werkplek.
   Bedient het **annotatie-domein** (`/v1/annotatie/*`: markeringen, beslissingen en een append-only
   auditlog: één laag per bronnode – artikel, lid of onderdeel), de
   **chatgeschiedenis** (`/v1/gesprekken/*`), het **login-/gebruikersbeheer** (de API is de
   identiteitsbron van de webapp, inclusief zelfregistratie-aanvragen die een beheerder goedkeurt),
   het **LLM-modelprofielbeheer** (`/v1/admin/*`; de env-`LLM_*`-waarden seeden alleen het eerste
   default-profiel), het **tokenbudget per gebruiker** (`/v1/verbruik/*`: meten, tonen, begrenzen —
   verbruik is een append-only journaal en de stand een som over het huidige venster, zodat werk
   weggooien geen tokens teruggeeft en de reset geen cronjob vraagt). Gesprekken zijn **per gebruiker gescopet**; annotatielagen juist **gedeeld** –
   ze dragen het werk van meerdere juristen, en wie wat deed staat in de audit.
2. **`frontend/`** – Next.js-webapp (BFF) bovenop de API. De app **is de werkplek** (`/workbench`, de
   *Lex-pagina*): één chat-achtig gespreksvenster voor **vragen én JAS-annotatie**, live tegen
   graph-qa (SSE); de home leidt daarheen door. Account, beheer en instellingen openen als
   **dialoog over de werkplek heen** (`/instellingen/*`, intercepting routes); `/beheer` is alleen
   nog een doorverwijzing daarheen. De beheertab (modelprofielen, gebruikers, aanvragen, API-tokens)
   zit achter een apart admin-token.
   De hele webapp zit achter een **login met userid + wachtwoord** (Auth.js; e-mail verplicht/uniek
   maar geen inlog-identiteit; de API is de identiteitsbron; rollen `beheerder`/`analist`; eenmalige
   eerste-beheerder-registratie via `/setup`; **zelfregistratie** via `/registreren`, die een beheerder
   goedkeurt voor er een account ontstaat; optionele TOTP-2FA). De UI volgt de **Rijkshuisstijl**
   (Belastingdienst-stijlvak: lintblauw, Fira-fonts, het officiële Belastingdienst-logo en
   JAS-klassekleuren uit `docs/wetsanalyse/wa-table.png`).
3. **`tools/graph-qa/`** – de eigen **QA/annotatie-agent**, **Lex** (de naam die de gebruiker ziet; de
   code, het image en de env-variabelen heten `graph-qa`), die vragen over wet- en regelgeving
   beantwoordt door de BWB-**kennisgraaf** (GraphDB via MCP) te bevragen en het antwoord
   **brongetrouw** te onderbouwen (grounding + bronnen uit de tool-trace). Eén **unified
   LangGraph-agent**: een **supervisor** kiest per vraag een worker-keten – de **antwoord-worker**
   (specialisten `definitie`/`duiding`/`algemeen`: agent ⇄ tools → verify → finalize), de
   **annotatie-worker** (`annoteer → emit`: de hybride keten uit ADR-001 met deterministische
   detectoren, een kleine classifier en een gerichte reviewer op twijfelgevallen, met aandacht-niveau
   🟢🟡), de **leesroute** voor vragen óver bestaande annotaties (`annotaties_zoeken`: eerst zelf
   zoeken met `search_annotaties`, dan pas formuleren – zoeken is een stap in de keten, geen keuze
   van het model) of de **overzichtsroute** voor "welke artikelen gaan over X?" (`overzicht_bouwen`:
   overzicht én tekst komen deterministisch uit de graaf, zonder model, en de werkplek toont het als
   blok – dezelfde vraag geeft hetzelfde overzicht, dezelfde tekst, dezelfde bronnen en dezelfde
   3D-graaf).
   Endpoints: `POST /v1/runs` (+ `/events`, `/cancel`; de weg van de werkplek – de beurt draait bij de
   agent, de browser kijkt mee), `POST /v1/chat` (SSE, aan de verbinding gekoppeld en **zonder
   eigenaarscontrole** – niet voor de webapp). De werkplek praat er **direct** mee
   (SSE); de persistente review-state loopt via de API (`/v1/annotatie/*`). Image
   `ghcr.io/palmw01/graph-qa`.
4. **`tools/bwb-import/`** – de **BWB-importer**: haalt de wettekst op bij
   `repository.officiele-overheidspublicaties.nl`, valideert tegen de officiële XSD's, parseert de
   structuur (regeling → hoofdstuk/afdeling → artikel → lid → onderdeel, met verwijzingen) en schrijft
   RDF naar GraphDB, repository `inning`. Met `BWB_IMPORT_WTI=true` komt de WTI-verrijking mee:
   verantwoordelijke organisatie, wetsfamilie, grondslagen, rechtsgebieden, citeertitels. Per wet
   **idempotent** (named-graph `PUT`), dus herimporteren is veilig. Image
   `ghcr.io/palmw01/bwb-import`; draait op Azure als twee container-app-jobs: de wekelijkse import en
   de graafwacht (zie §*Uitrollen*). Eigen `README.md`.
5. **`packages/bronmodel/`** – gedeeld Python-pakket (`wetsanalyse-bronmodel`) dat api én graph-qa
   gebruiken: de canonieke bronboom, snapshot-ID's, teksthashes en de lokale tekstankers (offsets in
   Unicode-codepoints). Het staat los zodat beide kanten dezelfde bronidentiteit afleiden; een
   wijziging erin bouwt en test beide componenten.
6. **De kennisgraaf zelf** (`deploy/azure/main.bicep`) – GraphDB 11.4 met de repository `inning`.
   **GraphDB ≥ 11.2 heeft de MCP-server ingebouwd** op `/mcp`, dus er is geen aparte MCP-container.
   De opslag is **niet-persistent** (memory-mapped files kunnen geen netwerkschijf gebruiken), maar de
   graaf is volledig reproduceerbaar uit overheid.nl – zie §*Uitrollen*.

   Naast de wetten staan er de **gedeelde JAS-annotatielagen** (`urn:jas:graph:v2:<laag-id>` met
   register `urn:jas:graph:register:v2`, W3C Web Annotation). Eén laag hoort bij één bronnode. Die
   schrijft **alleen de api**, als projectie van Postgres: direct na elke geslaagde commit, met een
   achtergrondlus (`JAS_PROJECTIE_INTERVAL`, 60 s) als vangnet; na een GraphDB-herstart bouwt hij ze
   zelf opnieuw op. Lex gebruikt ze twee keer: vóór het annoteren (een bepaling die al af is gaat
   niet opnieuw door het model) en om ze te doorzoeken (`search_annotaties`, met verificatie tegen
   Postgres). Zie `docs/architectuur/annotatie-bronnodes.md` voor het contract en
   `docs/wetsanalyse-workbench/jas-annotatie-ontologie.md` voor het RDF-model.

   **GraphDB draait op Azure zonder eigen security, en de netwerkgrens is de enige beveiliging:**
   `external: false`, alleen bereikbaar binnen de Container Apps Environment. Het `GRAPHDB_TOKEN` dat
   graph-qa meestuurt is daar geen slot – GraphDB negeert het – en `bwb-import` schrijft zonder
   credentials. Zijn ingress openzetten levert dus een onbeveiligd, schrijfbaar SPARQL-endpoint plus
   de Workbench op internet.

   Wie de graaf van búiten wil bevragen – met een MCP-client zoals Claude Code, langs dezelfde weg
   als Lex – zet de **MCP-proxy** aan: `azure-infra` → straat `acceptatie`, `graphdb_proxy: true`.
   Dat rolt `<appName>-graphdb-proxy` uit, een nginx die uitsluitend `/mcp` doorlaat en een
   bearer-token afdwingt (`WA_GRAPHDB_PROXY_TOKEN`, een environment-secret dat je zelf zet omdat je
   de waarde moet kennen). GraphDB zelf blijft intern; een guard in `poort.yml` bewaakt dat.
   Weghalen doe je met de actie `mcp-proxy-afbreken` – de vlag weer uitzetten is niet genoeg, want
   een bicep-deploy verwijdert niets. De registratie van die MCP-server hoort **machine-lokaal**
   (`claude mcp add`), niet in de repo: die is publiek.
7. **`.claude/skills/wetsanalyse/`** – de inhoudelijke skill: de JAS-methode met JRM 2-verrijking (de
   dertien klassen, fragmentgrenzen, het volg-beleid voor verwijzingen, de agentrollen). Hij is
   tegelijk een **build-input** van graph-qa. Zie §*De wetsanalyse-skill*.

### Ondersteunende tools

- **`tools/wetsanalyse-admin-mcp/`** – stdio-MCP die de admin-API (`/v1/admin/*`) als tools ontsluit.
  Op acceptatie heeft de api daarvoor een publieke ingress (`apiExtern`); op productie niet.
- **`tools/graph-qa/agent/mcp_server.py`** – stdio-MCP (`graph-qa-mcp`, `mcp`-extra) die de
  **getypeerde toollaag** van graph-qa ontsluit: `tools/list` is `anthropic_schemas()`, `tools/call`
  is `dispatch()`. Daarmee krijgt een externe agent exact de tools die Lex heeft in plaats van kale
  SPARQL — en dus ook de opgeloste valkuilen (dubbele punt in een artikelnummer, bepalingen zonder
  eigen tekst). Registreren hoort machine-lokaal; de URL en het token horen niet in deze repo.
- **`tools/nl-sbb-begrip/`** – side project: agent-workflow die voor één wettelijk begrip een
  NL-SBB-definitie opstelt (Markdown + SKOS-Turtle) op basis van de graaf, via die MCP-server.
  Draait niet mee in de dienst en heeft geen eigen CI.

## De onderdelen hangen via paden samen

Dit is een verzameling losse onderdelen, geen monorepo met één buildsysteem. Het bindmiddel zijn
**projectrelatieve paden**, zodat de map portabel is tussen machines/OS'en: `packages/bronmodel` als
path-dependency van api en graph-qa, de skill als build-input van graph-qa, en de projectroot als
Docker-buildcontext voor api en graph-qa.

- `.claude/settings.local.json` → een **machine-lokale** allowlist plus de tokens (o.a.
  `WETSANALYSE_ADMIN_TOKEN`). Dit bestand is **gitignored**, dus het reist niet mee: een andere
  machine/analist bouwt z'n eigen lijst opnieuw op via de permissieprompts. De allowlist is bewust
  krap en portabel – de grants gebruiken wildcards in plaats van absolute paden.

Let op bij hernoemen/verplaatsen van de projectmap: een padmismatch leidt hooguit tot een extra
permissieprompt (geen stille breuk). Draai daarna `claude mcp list` → verwacht `✓ Connected`.

## Veelgebruikte commando's

Per onderdeel gelden eigen commando's – zie de respectievelijke `CLAUDE.md`/`README.md`
(`api/`, `frontend/`, `tools/graph-qa/`, `tools/bwb-import/`, `tools/wetsanalyse-admin-mcp/`).

- Testpoort lokaal activeren (eenmalig per kloon): `git config core.hooksPath .githooks` – de
  pre-push-hook draait de suites van wat je raakt; `SKIP_HOOK=1` slaat hem over.
- Na een wijziging aan de skill: `cd tools/graph-qa && uv run python scripts/genereer_jas_klassen.py`
  (en `scripts/genereer_methodepakket.py` bij een wijziging aan de agentrollen); `--check` is wat CI
  draait.
- Sessie-MCP-gezondheid vanuit de projectroot: `claude mcp list`.

## De wetsanalyse-skill

`.claude/skills/wetsanalyse/SKILL.md` beschrijft de JAS-methode: de scope (activiteit 2), het
onderscheid werkgebied/bron, de dertien platformlabels, de JRM 2-verrijking en het volg-beleid voor
verwijzingen. Twee dingen om te weten:

**De skill draagt de methode; het platform voert hem uit.** De kennisgraaf levert de wettekst, de
agent stelt markeringen voor en de jurist beoordeelt ze in de werkplek. De skill bevat geen
uitvoerbare werkstroom en geen scripts.

**Namen in de api, duiding in de skill.** De canonieke klasse-*namen* (en hun kleuren en volgorde)
staan in `api/app/jas_klassen.py`; `frontend/lib/jas.ts` draagt dezelfde waarden met een drift-test
erop. Ze horen in de api en niet in de skill, zodat het productie-image geen Claude-skill hoeft mee
te dragen om te kunnen starten.

De **inhoudelijke duiding** – omschrijving, herkenningsvraag en uitdrukkingswijze per klasse – komt
uit de skill. Twee bestanden in graph-qa zijn daarvan **afgeleid**:

- `tools/graph-qa/agent/jas_klassen.py` – het JAS_KLASSEN-blok, gegenereerd door
  `tools/graph-qa/scripts/genereer_jas_klassen.py`, bewaakt door `tests/test_methode_drift.py`;
- `tools/graph-qa/agent/methodepakket.py` – de methodetekst per agentrol (`agentrollen.json` +
  `references/agentrollen.md`), gegenereerd door `scripts/genereer_methodepakket.py`, bewaakt door
  `tests/test_methodepakket.py`.

Wil je het gedrag van de agent bijsturen, bewerk dan de markdown en draai het script; bewerk je de
Python, dan faalt de test. Omdat de skill een build-input is, draait `poort` de graph-qa-suite ook
bij een PR die alleen skill-markdown raakt, en bouwt `graph-qa-docker-publish.yml` op
`.claude/skills/wetsanalyse/**`.

De `references/` zijn de operationele uitwerking van de methode, onder meer:

- `references/jas-klassen-referentie.md` – de dertien JAS-klassen, volledig uit
  `docs/wetsanalyse/wetsanalyse-rijk/H2-JAS.md` met regelverwijzingen. **Dit is de bron voor de
  code.** Verzin er geen klassen bij.
- `references/markeren-fragmentgrenzen.md` – hoe je markeert: fragmentgrenzen per klasse,
  overlappende markeringen, opsommingen, verwijzende voornaamwoorden, homoniemen, en wat je juist
  niet markeert. Afgeleid uit het boek en de BRM-readers, in eigen woorden – dat materiaal is van
  derden en mag niet letterlijk in deze publieke repo.
- `references/verwijzingen-volgen.md` – het volg-beleid voor cross-referenties: functies,
  diepte-cap 1 + relevantie-gate, bounded delegaties. Hoort bij het afbakenen van een werkgebied
  over meerdere bronnen; de annotatiestroom in de werkplek volgt zelf geen verwijzingen.
- `references/bronnen.md` – verbindt elke methodestap met bron + sectie en benoemt eigen
  projectkeuzes; de lokale originelen en hun hashes staan in `docs/wetsanalyse/bronnen/manifest.json`.
- `references/annotatieprotocol.md`, `analyseprotocol.md`, `jrm-verrijking.md`, `kwaliteit.md`,
  `agentrollen.md` en `assets/analysedossier.md` – de uitvoervormen (platformannotatie of volledig
  analysedossier) en de rolteksten voor de agent.

## Observability

Alle draaiende onderdelen (API, frontend, graph-qa) zijn **geïnstrumenteerd, niet bemeterd**:
ze emitteren gestructureerde JSON-logs (één gedeelde vorm, bv. `frontend/lib/logger.ts`)
en kunnen OpenTelemetry (traces/metrics/logs) naar een **configureerbaar OTLP-endpoint** sturen
(`OTEL_EXPORTER_OTLP_ENDPOINT`; leeg = alleen logs, nul overhead). Eén trace-id verbindt de keten
frontend → API → graph-qa.

Dat gaat niet vanzelf: `@vercel/otel` maakt wél spans voor uitgaande `fetch`, maar zet géén
`traceparent` op de request. De frontend injecteert hem daarom zelf – `frontend/lib/trace.ts`, op
elke fetch naar een upstream. Voeg je een BFF-route toe die zelf fetcht, gebruik dan `metTrace()`;
laat je het weg, dan faalt het **stil**: telemetrie komt gewoon binnen, alleen het verband tussen de
diensten ontbreekt. Zie `docs/observability.md` voor de controle-meting.

**De monitoring hoort bij de omgeving die hij bewaakt.** Op Azure staat per straat een stateless
OTel-collector (`<appName>-otel-collector`); `main.bicep` zet `OTEL_EXPORTER_OTLP_ENDPOINT` op die
collector voor api, graph-qa, frontend en de eval-job. De collector schrijft door naar **Application
Insights** (`appi-<appName>`), workspace-based op dezelfde Log Analytics-workspace
(`log-<appName>`) waar de stdout-logs landen; kijken doe je in de portal (Transaction search,
Application map) of met `azure-infra` → `telemetrie`. Elke span draagt
`deployment.environment=<appName>`. Application Insights kent geen OTLP-ingest – vandaar die
collector, en niet de Azure-distro in de apps: die zou drie diensten vendor-locken op de plek waar
het ontwerp juist provider-neutraal is.

**Grafana staat als container app naast de straten** (`deploy/azure/grafana.bicep`, uitrollen met
`azure-infra` → actie `grafana`): één exemplaar met een datasource én een dashboard per straat,
bereikbaar zonder portaltoegang, zonder persistente opslag (alles komt as-code uit
`deploy/azure/grafana/`). Hij draagt de SP-credentials als datasource-auth – een managed identity
kan niet, want dat vraagt een role assignment die de SP niet mag maken.

Draai de actie in **één** straat: die ene Grafana leest beide workspaces, dus een tweede exemplaar
is dubbelop (`grafana-afbreken` ruimt het op). Het dashboard `deploy/azure/grafana/dashboard-keten.json`
is één sjabloon dat per straat wordt ingevuld (`__STRAAT__`, `__WORKSPACE__`, `__DSUID__`,
`__APPNAME__`). De volledige uitleg (env-vars, logschema, AVG-redactie) staat in
**`docs/observability.md`**.

## Uitrollen

**Azure is het enige uitrolpad; er is geen dev-omgeving.** Acceptatie is de proeftuin: wie een
wijziging wil proberen, merget naar `master` en kijkt op acceptatie. Twee straten, elk een
zelfstandige omgeving (eigen PostgreSQL, GraphDB, importer, api, graph-qa, frontend, collector):

| straat | wanneer | `appName` | poort ervoor |
|---|---|---|---|
| **acceptatie** | elke merge naar `master` | `wetsanalyse` | geen – automatisch |
| **productie** | een tag `v*` | `wetsanalyse-prd` | required reviewer op de GitHub-environment |

**Beide straten staan in dezelfde resource group `rg-wetsanalyse`.** De service principal is
Contributor op die groep en mag er geen tweede aanmaken, dus scheiden gebeurt via `appName` – de
bicep is daar volledig op geparametriseerd. Gevolgen om te kennen: geen RBAC-scheiding tussen de
straten, `afbreken` haalt ze allebei weg, en kosten scheid je via de tag `straat: <appName>` die op
elke resource staat. De `opruimen`-actie kent beide straten via de repo-vars `ACCEPTATIE_APP_NAME`
en `PRODUCTIE_APP_NAME` – een derde straat hoort daar ook in, anders ruimt hij die op als wees.
Details, inrichting en runbooks: **`deploy/azure/README.md`**.

### Workflows

| workflow | trigger | wat hij doet |
|---|---|---|
| `api-`, `frontend-`, `graph-qa-`, `bwb-import-docker-publish.yml` | push naar `master` (padgefilterd, `*.md` uitgezonderd), `workflow_dispatch` | tests + pip-audit/npm-audit → build naar GHCR → Trivy-gate (HIGH/CRITICAL) → `deploy`-job: image-swap op **digest** naar acceptatie, wacht tot de revisie draait. bwb-import werkt de jobs `bwb-import` en `graafwacht` bij, graph-qa ook de `eval`-job. Luisteren niet op tags. |
| `promote.yml` | tag `v*` | bouwt niets: neemt de digests over die op acceptatie draaien, toetst per image het OCI-label `org.opencontainers.image.revision` tegen de getagde commit, rolt uit naar productie, wacht op gezonde revisies, zet de GHCR-tags `prd`/`prd-vorige` en verzet de branch `release/prd`. |
| `rollback.yml` | handmatig | toont de revisies van `api`, `frontend` of `graph-qa` in een straat; met `revisie` ingevuld zet hij het image van die revisie terug (een image-swap, geen `revision activate`) en wacht tot hij draait. Achter dezelfde environment-poort als een uitrol. |
| `azure-infra.yml` | handmatig | de enige die resources aanmaakt, wijzigt of verwijdert (bicep) – zie hieronder. |
| `poort.yml` | pull request naar `master` | de verplichte check `poort` – zie hieronder. |
| `bouwwacht.yml` | elk kwartier | vergelijkt `:latest` per component met master en dispatcht bij achterstand de publish-workflow. |
| `ghcr-cleanup.yml` | na elke geslaagde publish, of handmatig (default dry-run) | bewaart per image de vijf nieuwste getagde builds; `latest`, `prd` en `prd-vorige` zijn uitgesloten. |
| `geen-omgevingsgegevens.yml` | PR en push naar `master` | faalt op hostnamen, interne IP's en machinenamen in de repo. |
| `dependabot-auto-merge.yml` | Dependabot-PR | zet auto-merge aan voor patch/minor en de groep `patch-and-minor`; majors wachten op een mens. |

**Productie krijgt het geteste artefact, niet een herbouw.** Een herbouw van dezelfde broncode levert
een ander image op (verse basis-images, verse dependency-resolutie). Daarom bouwt `promote.yml` niets
en toetst hij het revisielabel: een tag die niet overeenkomt met wat acceptatie draait, faalt. De
publish-workflows zijn padgefilterd, dus voor een release moeten alle vier de images van de getagde
commit zijn – het runbook staat in `deploy/azure/README.md`. De credentials, resource group en
`APP_NAME` komen uit de GitHub-environment; de menselijke poort vóór productie zit daar ook, en niet
in een workflow-conditie.

**`prd` en `prd-vorige` beschermen productie tegen de retentie.** `ghcr-cleanup` bewaart alleen de
vijf nieuwste builds; zonder die tags verdwijnt het image onder een draaiende straat en strandt de
volgende replica, herstart of rollback op `MANIFEST_UNKNOWN`. `promote.yml` zet ze pas ná de
health-gate, net als `release/prd` – een aanwijzer naar iets dat niet opkwam liegt.

**Terugrollen verzet de code niet.** `rollback.yml` werkt alleen omdat `main.bicep`
`maxInactiveRevisions: 5` op api, graph-qa en frontend zet; zonder die regel ruimt Azure in
single-revision-modus de oude revisies op. Voeg je een app toe aan de keuzelijst van de workflow, zet
die regel er dan ook op. `master`, de tag en `release/prd` bewegen niet mee: de volgende uitrol brengt
de nieuwere versie weer binnen.

**Een merge die uit `GITHUB_TOKEN` voortkomt bouwt niets, en daar staat een wacht voor.** GitHub
onderdrukt élk event dat door dat token wordt veroorzaakt — dus als `dependabot-auto-merge.yml` de
auto-merge aanzet en GitHub de PR daarna zelf merget, vuurt er géén `push` en géén
`pull_request: closed`, en draait er geen publish-workflow. Een job die op de merge wacht
(`merged == true`) lost dat niet op, want die wordt door dezelfde regel onderdrukt; `poort.yml`
verbiedt dat patroon. **`bouwwacht.yml`** meet daarom de toestand in plaats van op een gebeurtenis te
wachten: het OCI-label `org.opencontainers.image.revision` op `:latest` tegen de commits op master
die de paden van die component raken — en alleen bij achterstand een `workflow_dispatch`. Hij leest
de componenten, images en paden uit de publish-workflows zelf, dus een vijfde component wordt
vanzelf bewaakt, en hij herstart niets waarvan de laatste build op dezelfde commit al mislukte. Het
is ook het vangnet voor elke andere gemiste trigger (een te nauw `paths:`-filter, een run die nooit
startte).

**Eén build per image tegelijk.** De publish-workflows hebben `concurrency` met
`cancel-in-progress: false`: twee builds van hetzelfde image pushen allebei `latest`, de tweede ontagt
de digest van de eerste, `ghcr-cleanup` ruimt die op en de deploy van de eerste faalt op
`MANIFEST_UNKNOWN`.

### De poort

`poort.yml` heeft bewust **geen `paths`-filter**: een verplichte check die door een filter niet
draait, laat een PR voorgoed op "expected" staan. Hij bepaalt zelf wat de PR raakt en draait alleen
die suites (`*.md` telt niet mee, behalve onder `.claude/skills/wetsanalyse/`, en
`packages/bronmodel/` triggert api én graph-qa). De frontend draait naast vitest/lint/typecheck een
Playwright-browserregressie (`npm run test:browser`); graph-qa en api draaien tegen een
PostgreSQL-servicecontainer (`RUNSTORE_TEST_DSN`, `ANNOTATIE_TEST_DSN`), zodat de databasetests niet
alleen lokaal bestaan. Daarvóór staan structurele guards:

- geen workflow-job die op `merged == true` wacht;
- elk Python-image met `pip install` verwijdert de vendored pip-SBOM (`pip/_vendor/bom.cdx.json`) –
  Trivy leest die anders als geïnstalleerde pakketten; de toets staat op de vorm, niet op een lijst
  Dockerfiles;
- alle Trivy-poorten hebben één beleid en falen minstens op HIGH;
- `apiExtern` staat default op `false` en wordt alleen op acceptatie gezet;
- GraphDB blijft `external: false`; de proxy staat default uit, alleen op acceptatie, alleen mét
  token, en met een `revisionSuffix` uit de config-hash (secrets zijn niet revisie-scoped, dus een
  configwijziging rolt anders niet uit).

### Infra

**Infra blijft handmatig.** `azure-infra.yml` (bicep via `deploy/azure/gen-deploy.py`) kiest een
straat en een actie: `wat-if` (default; valideert, maakt niets aan), `deploy`, `afbreken`,
`opruimen`, `vul-graaf`, `eval`, `inventaris`, `telemetrie`, `grafana`, `grafana-afbreken` en
`mcp-proxy-afbreken`. `wat-if` is de default omdat een deploy GraphDB raakt. Let vooral op de
GraphDB-licentie (`GRAPHDB_LICENSE_B64`), zonder welke de graaf read-only opkomt.

**De applicatie-secrets roteren niet bij een infra-deploy.** `azure-infra.yml` neemt ze over —
GitHub environment-secret (`WA_*`) → wat er in Azure draait → anders vers genereren. Dat is geen
netheid maar noodzaak: `llm-config-secret` is de Fernet-sleutel waarmee de api de API-keys van
modelprofielen én de 2FA-secrets van gebruikers versleutelt.

Twee dingen die die job bewust doet en die je niet moet weghalen: hij **faalt** bij een ontbrekend
secret of var (een overgeslagen stap zou de run groen laten terwijl er niets is uitgerold), en hij
**wacht na het uitrollen tot elke app een gezonde revisie draait**. Dat laatste is nodig omdat
`az deployment group create` al terugkeert zodra de revisie is *aangemaakt*, niet zodra hij draait —
een container die bij het starten crasht bleef anders onopgemerkt. `ScaledToZero` telt daarbij als
gezond: api en graph-qa staan op `minReplicas: 0` (`MIN_REPLICAS_APPS`) en zijn na een deploy zonder
verkeer terecht ingeschaald. Dezelfde gate zit in de publish-workflows, `promote.yml` en
`rollback.yml`.

**De graaf op Azure is niet-persistent, en vult zichzelf.** GraphDB gebruikt memory-mapped files en
kan daarom geen netwerkschijf gebruiken; de graaf is echter volledig reproduceerbaar uit overheid.nl.
Drie mechanismen houden hem gevuld:

- `azure-infra.yml` start de import-job na elke `deploy`;
- `<appName>-bwb-import` draait wekelijks (maandag 03:00 UTC) via een cron-trigger in de bicep;
- **`<appName>-graafwacht`** peilt elk kwartier met één SPARQL-query (`--alleen-bij-verlies`) en
  importeert alleen bij verlies – dus geen kwartaalbezoek aan overheid.nl. Hij dekt een onverwachte
  herstart van GraphDB, die anders tot de volgende deploy of weekcron een lege graaf zou opleveren
  (Lex antwoordt dan op elke vraag met `Repository inning doesn't exist`).

De uitval is zichtbaar in Grafana (paneel *Graaf weg*, op het logveld `graaf_weg`), en Lex zegt tegen
de jurist wat er speelt in plaats van de kale GraphDB-tekst door te geven. De similarity-index
(`bwb_similarity`) overleeft een herstart evenmin; de importer bouwt hem zelf terug
(`ensure_similarity_index`). Mislukt dat, dan degradeert `semantic_search` naar `search_wetgeving`.

## Referentiedocumentatie

`docs/` bevat de methodische onderbouwing (niet code). **`docs/README.md` is de wegwijzer** – het
legt uit welk bestand bron van derden is, welke specificatie met de code mee moet bewegen en welk
plan mag verouderen.

- `docs/wetsanalyse/` – het bronmateriaal van de methode: `WetsTaal.md`, de JAS-tabel
  `wa-table.png` en `wetsanalyse-rijk/` (hoofdstukken over JAS en het kader, van BZK onder de
  W3C-licentie – zie `wetsanalyse-rijk/BRON.md`). `H2-JAS.md` is de gezaghebbende klassenindeling;
  `references/jas-klassen-referentie.md` in de skill is daarvan de operationele uitwerking, mét
  regelverwijzingen terug naar deze bron. `bronnen/` bevat het manifest van de lokaal bewaarde
  originelen, `referentieset/` de juridische referentieset voor validatie.

  **Lokaal-only, bewust niet in de repo:** `wetsanalyse-boek.md` (het boek van Boom uitgevers) en
  de readers van het Expertisecentrum BRM (`*.pages.md` en als PDF, "bestemd voor gebruik binnen de
  Belastingdienst"). Deze repo is publiek; dat materiaal is van derden en hoort er niet in. De
  `.gitignore`-regels staan op de **vorm** van het bestand in plaats van op één map (`docs/**/*.pdf`,
  `docs/**/*.pages.md`, `docs/**/wetsanalyse-boek.md`), omdat een te specifiek pad een kopie op een
  andere plek doorlaat. Heb je het materiaal lokaal, dan werkt het gewoon; controleer na een
  wijziging aan die regels altijd met `git check-ignore -v <pad>`.
- `docs/regelspraak/` – de RegelSpraak-specificaties (PDF), voor de latere formaliseringsfase.
  Ook lokaal-only (gitignored), dus afwezig in een verse kloon.
- `docs/architectuur/annotatie-bronnodes.md` – de **geldende specificatie** van de annotatielagen:
  eigenaarschap en ankers, opslag en projectie, de leestools en het uitvoeringsspoor.
- `docs/architectuur/adr-001-hybride-jas-pijplijn.md` – het ontwerp van de annotatieketen
  (deterministische detectie → kandidaten → kleine classifier → gerichte review); de enige route.
  Lees het vóór je aan de detectoren, de classifier of de eval werkt: het legt vast welke kennis in
  regels en tests hoort in plaats van in prompts. `adr-002-taalprovider.md` legt de taalanalyse
  (spaCy) vast.
- `docs/architectuur/annotatieketen.md` – hoe de annotatieketen **nu** werkt: stappen,
  configuratie (`CLASSIFIER_GRANULARITEIT` e.d.), beslisbeleid, detectoren en bekende beperkingen.
  `docs/architectuur/metingen/README.md` is het meetlogboek: welke meting bij welke code hoort.
  Meetbestanden zijn bewijs en worden niet achteraf gewijzigd.
- `docs/wetsanalyse-workbench/` – de JAS-annotatie-ontologie (het RDF-model van de lagen).
- `docs/PLAN.md` – het **enige plan**: de open sporen (A validatie V7, B herkomst in werkplek en
  exports, C leerlus, D werkgebieden en begrippen, E kennisbank) en de open keuzes. Lees spoor E vóór
  je aan retrieval of grounding werkt, want het stelt eisen aan beide.
- `docs/observability.md` en `docs/schrijfrichtlijn-lex.md` (de toon van Lex; zijn identiteit staat in
  `tools/graph-qa/agent/prompts.py`).
