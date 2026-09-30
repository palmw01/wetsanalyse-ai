# Wetsanalyse op Azure – acceptatie en productie

Azure is het enige uitrolpad, met twee straten: **acceptatie** (elke merge naar `master`) en
**productie** (een tag `v*`). Er is geen aparte dev-omgeving; acceptatie is de proeftuin. Elke straat
is een **zelfstandige** omgeving op Azure Container Apps met eigen kennisgraaf en eigen database.

Beide straten draaien doorlopend. PostgreSQL (B1ms), GraphDB (`minReplicas: 1`), de collector en de
frontend (`minReplicas: 1`) schalen niet naar nul, dus dit zijn vaste kosten – zie *Kosten drukken*
onderaan.

| Component | Naam | Type | Bereikbaar |
|---|---|---|---|
| PostgreSQL | `<appName>-db` | Flexible Server (B1ms) | intern |
| GraphDB | `<appName>-graphdb` | Container App | intern, altijd |
| GraphDB-MCP-proxy | `<appName>-graphdb-proxy` | Container App, optioneel | **publiek HTTPS**, alleen op acceptatie |
| BWB-import | `<appName>-bwb-import` | Container Apps **Job**, wekelijks (ma 03:00 UTC) | – |
| Graafwacht | `<appName>-graafwacht` | Container Apps **Job**, elk kwartier | – |
| Eval | `<appName>-eval` | Container Apps **Job**, handmatig | – |
| API | `<appName>-api` | Container App | intern; op acceptatie **publiek** (`apiExtern`) |
| graph-qa | `<appName>-graph-qa` | Container App | intern |
| Frontend | `<appName>-frontend` | Container App | **publiek HTTPS** |
| OTel-collector | `<appName>-otel-collector` | Container App (stateless) | intern |
| Log Analytics + Application Insights | `log-<appName>`, `appi-<appName>` | Azure Monitor | portal |
| Grafana | `<appName>-grafana` | Container App, in één straat | publiek HTTPS |

De frontend is de publieke ingang. Op acceptatie heeft de api daarnaast een publieke ingress, zodat
de admin-MCP (`tools/wetsanalyse-admin-mcp/`) erbij kan. Die ingress zit vóór de hele app – ook
`/v1/annotatie`, `/v1/gesprekken` en `/v1/auth` – en daarom staat hij op productie dicht:
`apiExtern` heeft default `false` en `azure-infra.yml` zet hem alleen voor acceptatie. `poort.yml`
bewaakt beide.

**Monitoring zit in de straat zelf.** De apps (api, graph-qa, frontend) en de eval-job sturen OTLP
naar de collector van hun eigen straat; die schrijft door naar Application Insights, workspace-based
op dezelfde Log Analytics waar de stdout-logs landen. Daarmee staan logs, traces en metrics bij
elkaar en is de keten frontend → api → graph-qa onder één trace-id te volgen. Kijken doe je in de
portal (*Application Insights → Transaction search* of *Application map*) of met `azure-infra` →
`telemetrie`. Elke span draagt `deployment.environment=<appName>`, dus acceptatie en productie zijn
te scheiden.

**Grafana draait hier ook**, als container app naast de straten: `azure-infra` → actie `grafana`
(template `grafana.bicep`, dashboards in `grafana/`). Eén exemplaar bedient beide straten – een
datasource en een dashboard per straat – en is bereikbaar zonder portaltoegang. Apart van `deploy`
gehouden, want een dashboardwijziging hoort geen infra-deploy te vragen die GraphDB raakt.

Drie dingen om te weten:

- **Geen persistente opslag.** Datasources en dashboards komen als file-provisioning uit deze repo en
  zijn in de UI read-only; een herstart brengt ze ongewijzigd terug. Wat je wél verliest is handwerk
  in de UI (zelfgemaakte dashboards, extra gebruikers, voorkeuren). Wil je een paneel bewaren, zet
  het dan in `grafana/dashboard-keten.json`.
- **Hij draagt de service-principal-credentials** als datasource-auth, want een managed identity
  vereist een role assignment en die mag de SP niet maken. Grafana staat extern; het admin-wachtwoord
  is dus de enige poort. Leg hem vast als environment-secret `WA_GRAFANA_ADMIN_PASSWORD` – anders
  wordt er bij de eerste uitrol een gegenereerd, en dat moet je daarna uit de app-secret opvissen.
- **Schaalt naar nul.** De eerste paginalading wekt hem; dat kost een koude start van enkele seconden.

Rol Grafana in **één** straat uit: dat exemplaar leest beide workspaces via een datasource per
straat. Een tweede uitrol in de andere straat maakt een tweede, overbodige app aan – die wordt door
`opruimen` níét als wees herkend, want `$s-grafana` staat voor beide straten op de beschermde lijst.
Daar is de actie **`grafana-afbreken`** voor: kies de straat waarvan het exemplaar weg mag en typ de
groepsnaam ter bevestiging. Hij waarschuwt als je daarmee de laatste Grafana weghaalt, en de
dashboards zijn niets waard om te bewaren – die komen as-code uit `deploy/azure/grafana/`.

## Vooraf: de GraphDB-licentie

**Zonder licentie is deze omgeving niet bruikbaar.** GraphDB 11 laat zonder licentiebestand alleen
*lezen* toe; het eerste schrijf-verzoek van de import-job krijgt een `500 No license was set`. Een
verse instantie heeft de licentie niet vanzelf.

Geef het bestand mee met `--license-file` (in CI: het secret `GRAPHDB_LICENSE_B64`); het script
codeert het naar base64 en zet het als secret in de deployment, waarna een init-container het op
zijn plek schrijft. Controleer eerst of je licentievoorwaarden een tweede, gelijktijdig draaiende
instantie toestaan – dat is een vraag aan Ontotext, niet aan deze README.

Zonder licentie slaagt de deployment wél; je houdt dan een lege, read-only graaf.

## Deployen

### Twee straten

Elke straat heeft een eigen `appName` waar alle resourcenamen uit volgen (`${appName}-api`,
`cae-${appName}`, `log-${appName}`, …).

| straat | rolt uit bij | resource group | `appName` |
|---|---|---|---|
| acceptatie | elke merge naar `master` | `rg-wetsanalyse` | `wetsanalyse` |
| productie | een tag `v*` | `rg-wetsanalyse` | `wetsanalyse-prd` |

**Beide straten delen één resource group.** Dat is geen ontwerpvoorkeur maar een gevolg van de
rechten: de service principal is Contributor op `rg-wetsanalyse` en mag geen resource groups
aanmaken (`az group create` → `AuthorizationFailed` op
`Microsoft.Resources/subscriptions/resourcegroups/write`). Binnen de groep kan hij alles, en omdat
`main.bicep` volledig op `appName` is geparametriseerd, staat een tweede complete omgeving er
gewoon naast: `cae-wetsanalyse-prd`, `wetsanalyse-prd-api`, `wetsanalyse-prd-db`, enzovoort.

Wat je daarvoor inlevert, en waar je op moet letten:

- **Geen RBAC-scheiding.** Wie bij acceptatie mag, mag bij productie.
- **`afbreken` haalt béide straten weg** – die actie verwijdert de hele groep. Hij toont daarom
  eerst wat erin staat.
- **Kosten scheiden gaat via tags.** Elke resource draagt `straat: <appName>`; filter daarop in
  Cost analysis.
- **`opruimen` kent alle straten** (repo-vars `ACCEPTATIE_APP_NAME` en `PRODUCTIE_APP_NAME`).
  Voeg je ooit een derde straat toe, zet die dan óók in die lijst – anders ruimt de actie hem op als
  wees.

**Inrichten gebeurt per GitHub-environment** (Settings → Environments). Wat waar hoort:

- **vars, per environment** – `AZURE_RESOURCE_GROUP`, `APP_NAME` en `LLM_API_BASE` zijn verplicht en
  hebben geen default, zodat een niet-ingerichte straat faalt in plaats van stilletjes op de
  verkeerde resource group uit te komen. Optioneel: `LLM_MODEL` (default `claude-sonnet-4-6`),
  `AZURE_LOCATION` (default `northeurope`), `BACKUP_RETENTION_DAYS` (default `7`) en
  `MIN_REPLICAS_APPS` (default `0`, voor api en graph-qa).
- **secrets** – `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`,
  `AZURE_CLIENT_SECRET`, `AZURE_AI_KEY`, `GRAPHDB_LICENSE_B64` (de licentie als
  `base64 -w0 graphdb.license`). Een job met een environment **erft de repo-secrets**, dus zolang
  beide straten dezelfde service principal en AI-key gebruiken, volstaan de repo-secrets. Wil je
  gescheiden credentials – aan te raden zodra productie echte gegevens draagt – zet ze dan als
  environment-secret; die overschrijft de repo-variant.

Op `productie` staat een **required reviewer** en een deployment-policy die alleen tags `v*`
toelaat; op `acceptatie` alleen de branch `master`. Die poort hoort in de environment te zitten en
niet in een workflow-conditie die je per ongeluk wegcommit.

De workflows **falen** bewust als een van deze secrets of vars ontbreekt (een preflight-stap). Een
`if` die de stap oversloeg zou de run groen laten terwijl er niets is uitgerold.

#### De applicatie-secrets roteren niet

Los van de Azure-credentials draagt de stack zijn eigen secrets: de sessiesleutel, de api-/admin-/
qa-tokens, het databasewachtwoord en `llm-config-secret`. Dat laatste is de **Fernet-sleutel**
waarmee de api de API-keys van modelprofielen én de 2FA-secrets van gebruikers versleutelt; roteert
die, dan is dat materiaal onherstelbaar onleesbaar.

`azure-infra.yml` bepaalt ze per deploy in deze volgorde:

1. een **GitHub environment-secret** met die naam (`WA_LLM_CONFIG_SECRET`, `WA_AUTH_SECRET`,
   `WA_DB_ADMIN_PASSWORD`, `WA_API_TOKEN`, `WA_ADMIN_TOKEN`, `WA_QA_API_TOKEN`,
   `WA_GRAPH_QA_API_TOKEN`, `WA_GRAPHDB_TOKEN`, `WA_GRAPHDB_PROXY_TOKEN`) – zet deze als je ze bewust
   wilt beheren of roteren;
2. anders de waarde die **nu in Azure draait**, uitgelezen uit de container apps;
3. anders **vers gegenereerd** – het geval van een nieuwe straat.

> **Twee tokens rond graph-qa, in tegengestelde richting.** `WA_QA_API_TOKEN` is waarmee de
> *frontend* graph-qa aanroept (diens eigen `QA_API_TOKEN`). `WA_GRAPH_QA_API_TOKEN` is waarmee
> *graph-qa naar de api schrijft* om de uitkomst van een annotatiebeurt vast te leggen; het staat als
> eigen client `graph-qa:` in `apiTokens`, zodat het auditspoor laat zien wie er schreef. Ontbreekt
> dat tweede token, dan draait een annotatie gewoon door maar landt de uitkomst nergens – de
> werkplek meldt dan "deze agent heeft geen verbinding met de wetsanalyse-API".

Daardoor is een infra-deploy op een draaiende omgeving veilig. De toets daarop: `wat-if` mag geen
`~ secret`-regels tonen voor de api-, frontend- en graph-qa-apps.

### Image-swap: automatisch

De vier `*-docker-publish.yml`-workflows bouwen naar GHCR (pip-audit/npm-audit vooraf, Trivy-gate op
HIGH/CRITICAL achteraf) en hebben daarna een `deploy`-job die de container app op acceptatie naar de
nieuwe **digest** zet (niet naar een tag). Die job wacht tot de nieuwe revisie daadwerkelijk
`Running` is; `az containerapp update` keert namelijk al terug zodra de revisie is *aangemaakt*, dus
een container die bij het starten crasht bleef anders onopgemerkt. Bestaat de doel-app nog niet (een
verse straat zonder infra), dan waarschuwt de job en slaat hij de swap over in plaats van rood te
worden: het image staat dan wél in GHCR.

**Een job lift niet vanzelf mee.** Zo'n `deploy`-job werkt de container **app** bij; een container
app **job** krijgt alleen een nieuw image als de workflow er expliciet een `az containerapp job
update` voor doet, of bij een bicep-deploy (`azure-infra` → `deploy`). Daarom werkt de
bwb-import-workflow de jobs `bwb-import` én `graafwacht` bij (ze draaien hetzelfde importer-image), en
de graph-qa-workflow ook de `eval`-job (de bicep zet één `graphQaImage` op app en job). Blijft een
job achter, dan meet of importeert hij met een ouder image dan er live staat, en niets in zijn
uitvoer verraadt dat. Controleer het met `azure-infra` → `inventaris`: die toont het image per job,
en `<appName>-eval` hoort dezelfde digest te tonen als `<appName>-graph-qa`.

Mist een merge zijn build – bijvoorbeeld een Dependabot-PR die door `GITHUB_TOKEN` is gemerged, wat
geen `push`-event oplevert – dan vangt `bouwwacht.yml` dat binnen een kwartier op: hij vergelijkt het
revisielabel op `:latest` met master en dispatcht de publish-workflow bij achterstand.

**Retentie.** `ghcr-cleanup.yml` draait na elke geslaagde publish en bewaart per image de vijf
nieuwste getagde builds plus hun attestaties; `latest`, `prd` en `prd-vorige` zijn uitgesloten.
Handmatig draaien is standaard een dry-run.

### Productie: promoveren, niet herbouwen

Een tag `v*` start **`promote.yml`**. Die bouwt niets: hij leest de digests die op *acceptatie*
draaien en zet díe op productie. Zo krijgt productie exact het artefact dat getest is – een
herbouw van dezelfde broncode levert nog altijd een ander image op (verse basis-images, verse
dependency-resolutie). De publish-workflows luisteren daarom **niet** op tags.

Vóór hij iets uitrolt, controleert hij per component het OCI-label
`org.opencontainers.image.revision` van het draaiende image tegen de commit achter de tag. Hoort het
er niet bij, dan faalt de promotie met een melding in plaats van iets anders uit te rollen dan de
tag belooft. De guard dekt vier targets: de apps `api`, `frontend` en `graph-qa`, plus de job
`bwb-import`; de `graafwacht`-job krijgt hetzelfde importer-image. De `eval`-job werkt hij niet bij:
meten gebeurt op acceptatie.

Na de health-gate doet hij nog twee dingen:

- **GHCR-tags `prd` en `prd-vorige`.** Wat productie draait en de versie daarvoor krijgen een tag,
  zodat `ghcr-cleanup` ze niet opruimt. Zonder die bescherming verdwijnt het image onder een
  draaiende straat zodra er vijf nieuwere builds zijn, en strandt de volgende replica, herstart of
  rollback op `MANIFEST_UNKNOWN`.
- **Branch `release/prd`** wijst naar de gepromoveerde commit, zodat `git log release/prd -1`
  toont wat er in productie draait. De tag blijft het onveranderlijke ijkpunt.

#### Runbook: een release klaarzetten

De guard eist dat álle vier de images de revisie van de getagde commit dragen. De publish-workflows
zijn padgefilterd, dus een merge bouwt alleen wat veranderde — en een component dat al een tijd
onveranderd is (bijvoorbeeld `api/`) heeft dan géén image bij die commit. Tag je zonder meer, dan
faalt de promotie op precies dat punt.

1. Kies de commit op `master` die je wilt uitbrengen.
2. Draai **alle vier** de `*-docker-publish.yml`-workflows met `workflow_dispatch` op die commit.
   Elke run rolt ook naar acceptatie uit: inhoudelijk identiek, maar met een nieuw digest.
3. Controleer met `azure-infra` → `inventaris` dat acceptatie die vier digests draait.
4. Tag en push. `promote.yml` draait en wacht op de required reviewer.
5. **Vul daarna de graaf van productie.** Promotie geeft productie het nieuwe bwb-import-image, maar
   een `job update` start geen uitvoering — de graaf blijft staan zoals hij was tot de wekelijkse
   cron of een handmatige run. Draai `azure-infra` → omgeving `productie` → actie `vul-graaf` en
   controleer daarna de dekking; zonder deze stap lijkt de graaf "niet bijgewerkt".

### De productiestraat aanzetten

Er is geen Owner-recht voor nodig; alles gebeurt binnen de bestaande resource group.

1. Environment `productie` (Settings → Environments): `AZURE_RESOURCE_GROUP=rg-wetsanalyse`,
   `APP_NAME=wetsanalyse-prd`, `LLM_API_BASE`. Zet de required reviewer en de tag-policy `v*`.
2. `azure-infra` → `productie` → `wat-if`. Verwacht **uitsluitend `+`-regels** voor
   `wetsanalyse-prd-*` en `cae-wetsanalyse-prd`. Zie je een `~` op een bestaande
   `wetsanalyse-*`-resource, stop dan: het is dezelfde groep, en dan raakt de deploy acceptatie.
3. `azure-infra` → `productie` → `deploy`. Verse straat, dus verse secrets – hier juist goed. De
   import-job vult daarna automatisch de graaf.
4. Open de frontend-URL uit de samenvatting op `/setup` en maak de eerste beheerder aan.
5. Vanaf dan gaat elke release via een tag `v*` → `promote.yml`.

### Als er iets misgaat

1. **Wat draait er?** `git log release/prd -1` toont de commit die in productie staat; `azure-infra`
   → `inventaris` toont de images en revisies.
2. **Wat zegt de telemetrie?** `azure-infra` → `telemetrie` (per straat). Zonder `query` krijg je de
   standaardset: wat er binnenkwam, requests per dienst met p95, en trace-ids die over meerdere
   diensten lopen. Met `query` stel je je eigen KQL-vraag – read-only.
3. **Terugrollen.** `rollback` → kies straat en app (`api`, `frontend` of `graph-qa`), laat `revisie`
   leeg om de revisies met hun image te zien, en draai hem daarna nog eens met de revisie die je wilt
   terugzetten. Hij controleert eerst of die revisie bestaat, zet dan haar image terug en wacht tot
   de nieuwe revisie draait. Achter dezelfde environment-poort als een uitrol.

Terugrollen is een image-swap en geen `revision activate`: de apps draaien in single-revision-modus,
en multiple-revision-modus zou blijvend ander gedrag zijn dan de bicep beschrijft. Er valt alleen
iets te kiezen omdat `main.bicep` `maxInactiveRevisions: 5` op api, graph-qa en frontend zet – zonder
die regel ruimt Azure de oude revisies op. Voeg je een app toe aan de keuzelijst, zet die regel er
dan ook op.

Let op wat terugrollen **niet** doet: `master`, de tag en `release/prd` bewegen niet mee. Een
volgende uitrol brengt de nieuwere versie gewoon weer binnen – repareer dus de oorzaak, of draai de
betreffende commit terug.

### Infra: handmatig

Actions → **azure-infra** → *Run workflow*, met een keuze voor de straat en de actie:

| actie | wat het doet |
|---|---|
| `wat-if` *(default)* | Azure toont welke resources zouden ontstaan of wijzigen. Maakt niets aan – de enige manier om de template tegen je echte subscription te toetsen (quota, regio, rechten). |
| `deploy` | rolt de stack uit (10-15 min; PostgreSQL is de trage stap), wacht tot elke app een gezonde revisie draait (`ScaledToZero` telt als gezond) en start daarna meteen de import-job, want de graaf komt leeg op. Met `graphdb_proxy: true` (alleen acceptatie) komt de MCP-proxy mee. |
| `afbreken` | verwijdert de hele resource group – dus beide straten. Vraagt om de naam ter bevestiging. |
| `opruimen` | verwijdert wat er in de groep staat maar niet bij een straat hoort. Toont eerst wat het zou doen; verwijdert pas als je de groepsnaam intypt. |
| `vul-graaf` | start de import-job en wacht hem af. |
| `eval` | draait de eval-job: eerst de retrieval-smoke (gratis), daarna **drie** metingen van de annotatieketen, met het rapport in de workflow-samenvatting. Kost LLM-tokens. Vereist een eerdere `deploy` (die maakt de job aan). **Niet vlak na een `deploy` draaien**: die start de importjob, en zolang die loopt herschrijft GraphDB de graaf. De smoke wacht daar zelf op, maar dat kost wachttijd. |
| `inventaris` | read-only overzicht van wat er in de subscription draait, met het image per app en job. |
| `telemetrie` | vraagt de Log Analytics-workspace of er telemetrie binnenkomt; met een eigen `query` je eigen KQL. Read-only. |
| `grafana` | rolt alleen de Grafana-app uit (`grafana.bicep`). Raakt de applicatiestack niet. |
| `grafana-afbreken` | verwijdert de Grafana-app van de gekozen straat. Vraagt de groepsnaam ter bevestiging. |
| `mcp-proxy-afbreken` | verwijdert de GraphDB-MCP-proxy. Vraagt de groepsnaam ter bevestiging. |

Dit is de enige workflow die resources aanmaakt, wijzigt of verwijdert. Vandaar `wat-if` als
default: een deploy raakt GraphDB, en die is niet-persistent. Hij geeft de images die nu draaien mee
aan de deploy, zodat een infra-deploy geen `:latest` over een gepromoveerde digest heen zet.

### Wat de bicep niet opruimt

Bicep draait in **incremental mode**: het maakt aan en werkt bij, maar verwijdert nooit iets dat
niet (meer) in de template staat. Haal je een component uit `main.bicep`, dan blijft de draaiende
resource gewoon bestaan – onzichtbaar zolang je alleen naar de template kijkt, en met zijn kosten.

`azure-infra` → `opruimen` lost dat op: het neemt de bicep als waarheid en zet alles wat daar niet
in staat op de lijst. Zonder bevestiging toont het alleen wat het zou doen – draai het zo eerst, en
typ pas daarna de groepsnaam. De verwijdervolgorde is dwingend: container apps en jobs hangen aan
hun managed environment, dus dat kan pas weg als het leeg is. Voeg je een resource aan de bicep toe,
zet hem dan ook op de lijst van wat erbij hoort in die stap – anders gooit `opruimen` hem weg.

### Met de hand

```bash
az login
az group create --name rg-wetsanalyse-test --location westeurope

# 1. Kijk eerst wat er zou gebeuren (maakt niets aan)
python3 deploy/azure/gen-deploy.py "<azure-ai-key>" \
    --llm-api-base "https://<resource>.services.ai.azure.com" \
    --resource-group rg-wetsanalyse-test \
    --license-file /pad/naar/graphdb.license \
    --what-if

# 2. Uitrollen (10-15 min; PostgreSQL is de trage stap)
python3 deploy/azure/gen-deploy.py "<azure-ai-key>" \
    --llm-api-base "https://<resource>.services.ai.azure.com" \
    --resource-group rg-wetsanalyse-test \
    --license-file /pad/naar/graphdb.license \
    --run
```

Zonder `--what-if` of `--run` schrijft het script alleen `params.json` en print het het
az-commando. Defaults: `--resource-group rg-wetsanalyse`, `--location westeurope`,
`--app-name wetsanalyse`, `--llm-model claude-sonnet-4-6`.

Daarna twee handelingen:

```bash
# de graaf vullen (~20s voor zeven regelingen)
az containerapp job start -n <appName>-bwb-import -g <resource-group>

# de eerste beheerder aanmaken
open "<frontendUrl>/setup"     # frontendUrl staat in de deployment-output
```

> **Deze weg is voor een wegwerpomgeving, niet voor acceptatie of productie.** Het script neemt de
> applicatie-secrets over uit de omgeving (`WA_*`-variabelen) en genereert ze anders **vers**; op een
> draaiende omgeving betekent opnieuw deployen zonder die variabelen dus dat sessies vervallen, de
> admin-tokens wijzigen en de Fernet-sleutel roteert. Voor acc en prd loopt de weg via
> `azure-infra.yml`, dat ze stabiel houdt. Wil je met de hand tóch een bestaande omgeving bijwerken,
> zet dan de `WA_*`-variabelen of bewaar het parameterbestand (`--params-file`) buiten de repo en
> hergebruik het.

## De graaf is bewust vluchtig

GraphDB draait **zonder persistente opslag**. Dat is geen bezuiniging maar een gevolg van hoe zijn
opslaglaag werkt: geheugen-gemapte bestanden en file-locking verdragen netwerkopslag slecht (traag,
en in het slechtste geval stille indexcorruptie), en Azure Files is de enige persistente mount die
een container-app kan krijgen. Een managed disk zou het oplossen maar vraagt een VM.

Dat kan hier, omdat de graaf **reproduceerbaar** is: de import-job haalt alle regelingen (`bwbIds` in
`main.bicep`) rechtstreeks bij overheid.nl. Gevolgen:

- De graphdb-app schaalt **niet naar nul** (`minReplicas: 1`) – anders is de graaf bij de volgende
  request leeg. Dit is de component die doorloopt zolang de omgeving aan staat.
- Na elke herstart van die app moet er opnieuw geïmporteerd worden, en dat gaat vanzelf: de job
  **`<appName>-graafwacht`** draait elk kwartier, peilt met één SPARQL-query of alle regelingen er
  staan (`--alleen-bij-verlies`) en importeert alléén bij verlies. Op een complete graaf stopt hij
  binnen een seconde en raakt hij overheid.nl niet aan. Zonder die wacht hing herstel aan een
  `deploy` of aan de weekcron, en kon de graaf tot bijna zeven dagen onbruikbaar zijn; Lex weigert
  dan terecht om uit eigen geheugen te citeren (`Repository inning doesn't exist`). Het paneel
  *Graaf weg* in het Grafana-dashboard maakt uitval zichtbaar. Handmatig forceren blijft
  `azure-infra` → `vul-graaf`.
- De similarity-index `bwb_similarity` (voor `semantic_search`) overleeft een herstart evenmin. De
  importer bouwt hem zelf terug (`ensure_similarity_index`, net als de FTS-connector); zonder die
  index valt `semantic_search` stil terug op `search_wetgeving`. Mislukt de herbouw, dan blijft de
  import groen — de wettekst staat er dan gewoon — en zegt de importlog waarom.
- De import controleert de tekstdekking per regeling (`minDekking`, default `0.995`); zakt een
  regeling eronder, dan eindigt de job met exitcode 2 en wordt hij rood, terwijl de graaf wél volledig
  geschreven is.

## Beveiliging

GraphDB draait hier **zonder eigen security**: de graaf is alleen binnen de Container Apps
Environment bereikbaar (`external: false`), en die netwerkgrens is de enige beveiliging.
`GRAPHDB_TOKEN` wordt wel gezet – graph-qa eist het fail-closed – maar GraphDB negeert het; het is
hier geen slot. `bwb-import` schrijft zonder credentials.

Voor de huidige omgevingen is dat verdedigbaar. Hoort er ooit harder bij, dan is dat GraphDB-security
met een service-account (read-only voor graph-qa) en een proxy die het token controleert; dat raakt
`bwb-import` én graph-qa en is een eigen traject.

Alle applicatie-secrets zijn **bestanden** (`*_FILE`-patroon via secret-volumes), nooit platte
env-vars.

### De graaf van buiten bevragen (MCP-proxy)

Omdat de netwerkgrens de enige beveiliging is, mag GraphDB's eigen ingress **nooit** extern. Wil je
de graaf toch met een MCP-client bevragen – Claude Code, langs dezelfde weg als Lex – zet dan de
proxy aan:

1. Zet op de GitHub-environment `acceptatie` het secret **`WA_GRAPHDB_PROXY_TOKEN`** (bijv.
   `openssl rand -hex 24`). Zelf zetten, want je moet de waarde kennen: hij gaat in de MCP-config van
   je werkstation, en een GitHub-secret kun je niet teruglezen. `gen-deploy.py` genereert hem daarom
   bewust niet en faalt hard als hij ontbreekt.
2. Draai `azure-infra` → straat `acceptatie`, actie `deploy`, **`graphdb_proxy: true`**. De
   samenvatting van de run toont de URL.
3. Registreer de server machine-lokaal – **niet** in de repo, die is publiek:
   ```bash
   claude mcp add --transport http graphdb <url>/mcp \
     --header "Authorization: Bearer <token>"
   ```

Wat de proxy is: een nginx (`<appName>-graphdb-proxy`) die uitsluitend `/mcp` doorlaat, alleen met
het juiste bearer-token, en al het andere met 404 afwijst – geen Workbench, geen REST-API, geen
SPARQL-endpoint. GraphDB zelf blijft `external: false` en wordt niet aangeraakt, dus de graaf
herstart niet en hoeft niet opnieuw geïmporteerd te worden. Hij schaalt naar nul. De nginx-config
zit in een secret, en secrets zijn in Container Apps niet revisie-scoped; daarom hangt de
`revisionSuffix` aan een hash van de config, anders rolt een configwijziging niet uit.

Wat de proxy **niet** doet: read-only afdwingen. Wie erdoor komt heeft dezelfde rechten als Lex – een
SPARQL-body is op nginx-niveau niet betrouwbaar te keuren. Dat is te dragen omdat dit alleen op
acceptatie aan gaat, het token apart intrekbaar is en de graaf reproduceerbaar is uit overheid.nl.

Weer dicht: actie **`mcp-proxy-afbreken`** (met de resource group ter bevestiging). `graphdb_proxy`
weer op `false` zetten is **niet** genoeg – een bicep-deploy in incremental mode verwijdert niets, en
`opruimen` beschermt de proxy juist omdat die actie niet kan weten of hij bedoeld is.

`poort.yml` bewaakt de grens: GraphDB blijft `external: false`, `graphdbProxyExtern` heeft default
`false`, de proxy bestaat alleen mét token, en `--graphdb-proxy-extern` staat in de workflow alleen
achter een acceptatie-conditie.

## Kosten drukken

- **Uit**: `az group delete -n rg-wetsanalyse` – haalt beide straten weg; een straat is in een
  kwartier terug te zetten.
- **Pauze**: `az postgres flexible-server stop -n <appName>-db -g rg-wetsanalyse` plus de
  graphdb-app op nul replica's. Api en graph-qa schalen zelf terug; de frontend houdt één replica,
  want een cold start laat Auth.js-redirects timeouten.

## Bestanden

| bestand | wat |
|---|---|
| `main.bicep` | de volledige infrastructuur van één straat |
| `gen-deploy.py` | neemt de secrets over of genereert ze, schrijft de parameters en roept `az deployment` aan (`--what-if` / `--run`) |
| `grafana.bicep` | de Grafana-app (actie `grafana`) |
| `grafana/dashboard-keten.json` | het dashboardsjabloon, per straat ingevuld |
| `.gitignore` | houdt `params.json` en licentiebestanden buiten de repo |

Het image dat elke app draait is een parameter (`apiImage`, `graphQaImage`, `frontendImage`,
`bwbImportImage`), zodat CI een digest kan meegeven in plaats van `:latest`.
