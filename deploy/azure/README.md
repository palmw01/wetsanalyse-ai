# Wetsanalyse op Azure – acceptatie en productie

Azure draagt het platform: **acceptatie** (elke merge naar `master`) en **productie** (een tag `v*`).
Elke straat is een **zelfstandige** omgeving op Azure Container Apps met eigen kennisgraaf en eigen
database, zonder verbinding met de docker-host. Die host draagt alleen nog de dev-omgeving.

Beide straten draaien doorlopend. PostgreSQL (B1ms) en GraphDB (`minReplicas: 1`) kunnen geen van
beide naar nul schalen, dus dit zijn vaste kosten – zie *Kosten drukken* onderaan.

| Component | Type | Bereikbaar |
|---|---|---|
| PostgreSQL | Flexible Server (B1ms) | intern |
| GraphDB | Container App | intern |
| BWB-import | Container Apps **Job** (handmatig) | – |
| Eval | Container Apps **Job** (handmatig) | – |
| API | Container App | intern |
| graph-qa | Container App | intern |
| Frontend | Container App | **publiek HTTPS** |
| OTel-collector | Container App (stateless) | intern |
| Log Analytics + Application Insights | Azure Monitor | portal |

Alleen de frontend heeft een publiek adres. De rest praat binnen de Container Apps Environment.

**Monitoring zit in de straat zelf.** De apps sturen OTLP naar de collector van hun eigen straat;
die schrijft door naar Application Insights, workspace-based op dezelfde Log Analytics waar de
stdout-logs al landen. Daarmee staan logs, traces en metrics bij elkaar en is de keten
frontend → api → graph-qa onder één trace-id te volgen. Kijken doe je in de portal: *Application
Insights → Transaction search* of *Application map*. Elke span draagt
`deployment.environment=<appName>`, dus acceptatie en productie zijn te scheiden.

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
*lezen* toe; het eerste schrijf-verzoek van de import-job krijgt een `500 No license was set`. Op de
docker-host zit die licentie in de persistente datadirectory (`/opt/graphdb/home/work/graphdb.license`)
en valt hij niet op – een verse instantie heeft hem niet.

Geef het bestand mee met `--license-file`; het script codeert het naar base64 en zet het als secret
in de deployment, waarna een init-container het op zijn plek schrijft. Controleer eerst of je
licentievoorwaarden een tweede, gelijktijdig draaiende instantie toestaan – dat is een vraag aan
Ontotext, niet aan deze README.

Zonder `--license-file` slaagt de deployment wél; je houdt dan een lege, read-only graaf.

## Deployen

### Twee straten

Azure is de uitrolplek, met een **acceptatie**- en een **productiestraat**. Elke straat is een
zelfstandige omgeving in een eigen resource group, met een eigen `appName` waar alle resourcenamen
uit volgen (`${appName}-api`, `cae-${appName}`, `log-${appName}`, …).

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

- **vars, per environment** – `AZURE_RESOURCE_GROUP`, `APP_NAME`, `LLM_API_BASE`, optioneel
  `LLM_MODEL` en `AZURE_LOCATION`. Deze *moeten* per straat gezet zijn; ze hebben geen default meer,
  zodat een niet-ingerichte straat faalt in plaats van stilletjes op de verkeerde resource group uit
  te komen.
- **secrets** – `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`,
  `AZURE_CLIENT_SECRET`, `AZURE_AI_KEY`, `GRAPHDB_LICENSE_B64` (de licentie als
  `base64 -w0 graphdb.license`). Een job met een environment **erft de repo-secrets**, dus zolang
  beide straten dezelfde service principal en AI-key gebruiken, volstaan de bestaande repo-secrets.
  Wil je gescheiden credentials – aan te raden zodra productie echte gegevens draagt – zet ze dan
  als environment-secret; die overschrijft de repo-variant.

#### De applicatie-secrets roteren niet

Los van de Azure-credentials draagt de stack zijn eigen secrets: de sessiesleutel, de api-/admin-/
qa-tokens, het databasewachtwoord en `llm-config-secret`. Dat laatste is de **Fernet-sleutel**
waarmee de api de API-keys van modelprofielen én de 2FA-secrets van gebruikers versleutelt; roteert
die, dan is dat materiaal onherstelbaar onleesbaar.

`azure-infra.yml` bepaalt ze per deploy in deze volgorde:

1. een **GitHub environment-secret** met die naam (`WA_LLM_CONFIG_SECRET`, `WA_AUTH_SECRET`,
   `WA_DB_ADMIN_PASSWORD`, `WA_API_TOKEN`, `WA_ADMIN_TOKEN`, `WA_QA_API_TOKEN`,
   `WA_GRAPH_QA_API_TOKEN`, `WA_GRAPHDB_TOKEN`) – zet deze als je ze bewust wilt beheren of roteren;
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

Op `productie` staat een **required reviewer** en een deployment-policy die alleen tags `v*`
toelaat; op `acceptatie` alleen de branch `master`. Die poort hoort in de environment te zitten en
niet in een workflow-conditie die je per ongeluk wegcommit.

De workflows falen bewust als een van deze secrets of vars ontbreekt. Eerder was dat een `if` die de
deploy-stap oversloeg – dan was de run groen terwijl er niets was uitgerold.

### Image-swap: automatisch

De vier `*-docker-publish.yml`-workflows bouwen naar GHCR en hebben daarna een `deploy`-job die de
container app op de juiste straat naar de nieuwe **digest** zet (niet naar een tag). Die job wacht
tot de nieuwe revisie daadwerkelijk `Running` is; `az containerapp update` keert namelijk al terug
zodra de revisie is *aangemaakt*, dus een container die bij het starten crasht bleef anders
onopgemerkt.

**Een job lift niet vanzelf mee.** Zo'n `deploy`-job werkt de container **app** bij; een container
app **job** krijgt alleen een nieuw image als de workflow er expliciet een `az containerapp job
update` voor doet, of bij een bicep-deploy (`azure-infra` → `deploy`). Er zijn twee jobs, en beide
worden inmiddels expliciet bijgewerkt: `bwb-import` door zijn eigen publish-workflow, en `eval` door
die van graph-qa — de eval-job draait namelijk hetzelfde image als de graph-qa-app, want de bicep
zet één `graphQaImage` op allebei.

Dat laatste is er pas op 4 sep 2026 bij gekomen, nadat de eval-job maandenlang op het image van de
laatste infra-deploy bleef hangen: hij mat een oudere agent dan er live stond, en niets in het
eval-rapport verraadt dat. Controleer het met `azure-infra` → `inventaris`; die toont sindsdien het
image per job, en `wetsanalyse-eval` hoort dezelfde digest te tonen als `wetsanalyse-graph-qa`.

### Productie: promoveren, niet herbouwen

Een tag `v*` start **`promote.yml`**. Die bouwt niets: hij leest de digests die op *acceptatie*
draaien en zet díe op productie. Zo krijgt productie exact het artefact dat getest is – een
herbouw van dezelfde broncode levert nog altijd een ander image op (verse basis-images, verse
dependency-resolutie).

Vóór hij iets uitrolt, controleert hij per component het OCI-label
`org.opencontainers.image.revision` van het draaiende image tegen de commit achter de tag. Hoort het
er niet bij, dan faalt de promotie met een melding in plaats van iets anders uit te rollen dan de
tag belooft. Praktisch: tag een commit die al op `master` staat en waarvan acceptatie de uitrol
heeft afgerond.

De publish-workflows luisteren daarom **niet** op tags – die bouwen alleen voor acceptatie.

De guard dekt vier targets: de apps `api`, `frontend` en `graph-qa`, plus de job `bwb-import`. De
eval-job zit er bewust niet in: die bestaat alleen op acceptatie.

#### Runbook: een release klaarzetten

De guard eist dat álle vier de images de revisie van de getagde commit dragen. De publish-workflows
zijn padgefilterd, dus een merge bouwt alleen wat veranderde — en een component dat al een tijd
onveranderd is (bijvoorbeeld `api/`) heeft dan géén image bij die commit. Tag je zonder meer, dan
faalt de promotie op precies dat punt.

1. Kies de commit op `master` die je wilt uitbrengen.
2. Draai **alle vier** de `*-docker-publish.yml`-workflows met `workflow_dispatch` op die commit.
   Elke run rolt ook naar acceptatie uit: inhoudelijk identiek, maar met een nieuw digest, want een
   herbouw van dezelfde broncode levert een ander artefact op.
3. Controleer met `azure-infra` → `inventaris` dat acceptatie die vier digests draait.
4. Tag en push. `promote.yml` draait en wacht op de required reviewer.
5. **Vul daarna de graaf van productie.** Promotie geeft productie het nieuwe bwb-import-image, maar
   een `job update` start geen uitvoering — de graaf blijft staan zoals hij was tot de wekelijkse
   cron of een handmatige run. Draai `azure-infra` → omgeving `productie` → actie `vul-graaf` en
   controleer daarna de dekking. Deze stap is op 4 sep 2026 op acceptatie vergeten en kostte een
   halve middag zoeken naar een graaf die "niet bijgewerkt" leek.

### De productiestraat aanzetten

Er is geen Owner-recht voor nodig; alles gebeurt binnen de bestaande resource group.

1. Environment `productie` (Settings → Environments): `AZURE_RESOURCE_GROUP=rg-wetsanalyse`,
   `APP_NAME=wetsanalyse-prd`. De required reviewer en de tag-policy `v*` staan er al op.
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
3. **Terugrollen.** `rollback` → kies straat en app, laat `revisie` leeg om te zien wat er is, en
   draai hem daarna nog eens met de revisie die je wilt terugzetten. Achter dezelfde reviewer als een
   uitrol.

Let op wat terugrollen **niet** doet: `master`, de tag en `release/prd` bewegen niet mee. Een
volgende uitrol brengt de nieuwere versie gewoon weer binnen – repareer dus de oorzaak, of draai de
betreffende commit terug.

### Infra: handmatig

Actions → **azure-infra** → *Run workflow*, met een keuze voor de straat en de actie:

| actie | wat het doet |
|---|---|
| `wat-if` *(default)* | Azure toont welke resources zouden ontstaan of wijzigen. Maakt niets aan – de enige manier om de template tegen je echte subscription te toetsen (quota, regio, rechten). |
| `deploy` | rolt de stack uit (10-15 min; PostgreSQL is de trage stap) en start daarna meteen de import-job, want de graaf komt leeg op. |
| `afbreken` | verwijdert de hele resource group. Vraagt om de naam ter bevestiging. |
| `opruimen` | verwijdert wat er in de groep staat maar niet bij deze straat hoort. Toont eerst wat het zou doen; verwijdert pas als je de groepsnaam intypt. |
| `vul-graaf` | start de import-job en wacht hem af. |
| `eval` | draait de eval-job: **drie** metingen van de annotatieketen tegen de graaf van deze straat, met het rapport in de workflow-samenvatting. Kost LLM-tokens en duurt ~30 min. Vereist een eerdere `deploy` (die maakt de job aan). |
| `inventaris` | read-only overzicht van wat er in de subscription draait. |
| `telemetrie` | vraagt de Log Analytics-workspace of er telemetrie binnenkomt; met een eigen `query` je eigen KQL. Read-only. |
| `grafana` | rolt alleen de Grafana-app uit (`grafana.bicep`). Raakt de applicatiestack niet. |

Dit is de enige workflow die resources aanmaakt, wijzigt of verwijdert. Vandaar `wat-if` als
default: een deploy raakt GraphDB, en die is niet-persistent.

### Wat de bicep niet opruimt

Bicep draait in **incremental mode**: het maakt aan en werkt bij, maar verwijdert nooit iets dat
niet (meer) in de template staat. Haal je een component uit `main.bicep`, dan blijft de draaiende
resource gewoon bestaan – onzichtbaar zolang je alleen naar de template kijkt, en met zijn kosten.

Dat is hier echt gebeurd. Bij het verwijderen van de wettenbank-MCP (commit `9e34b75`, augustus
2026) verdween de `mcpApp`-resource uit de bicep, maar bleven de draaiende mcp-apps staan; daarnaast
stond er een complete tweede omgeving (`wetsanalyse-acc-*`) met een eigen PostgreSQL-server, alle
replicas op `minReplicas: 1` en dus doorlopend aan.

`azure-infra` → `opruimen` lost dat op: het neemt de bicep als waarheid en zet alles wat daar niet
in staat op de lijst. Zonder bevestiging toont het alleen wat het zou doen – draai het zo eerst, en
typ pas daarna de groepsnaam. De verwijdervolgorde is dwingend: container apps en jobs hangen aan
hun managed environment, dus dat kan pas weg als het leeg is.

### Met de hand

```bash
az login
az group create --name rg-wetsanalyse-test --location westeurope

# 1. Kijk eerst wat er zou gebeuren (maakt niets aan)
python3 deploy/azure/gen-deploy.py "<azure-ai-key>" \
    --llm-api-base "https://<resource>.services.ai.azure.com" \
    --license-file /pad/naar/graphdb.license \
    --what-if

# 2. Uitrollen (10-15 min; PostgreSQL is de trage stap)
python3 deploy/azure/gen-deploy.py "<azure-ai-key>" \
    --llm-api-base "https://<resource>.services.ai.azure.com" \
    --license-file /pad/naar/graphdb.license \
    --run
```

Daarna twee handelingen:

```bash
# de graaf vullen (~20s voor zeven regelingen)
az containerapp job start -n <appName>-bwb-import -g <resource-group>

# de eerste beheerder aanmaken
open "<frontendUrl>/setup"     # frontendUrl staat in de deployment-output
```

> **Deze weg is voor een wegwerpomgeving, niet voor acceptatie of productie.** Het script genereert
> bij elke run **verse** tokens en een vers databasewachtwoord; op een draaiende omgeving betekent
> opnieuw deployen dus dat sessies vervallen en de admin-tokens wijzigen. Voor acc en prd loopt de
> weg via `azure-infra.yml`, dat de waarden uit de environment-secrets haalt en ze daarmee stabiel
> houdt. Wil je met de hand tóch een bestaande omgeving bijwerken, bewaar dan het parameterbestand
> (`--params-file`) buiten de repo en hergebruik het.

## De graaf is bewust vluchtig

GraphDB draait **zonder persistente opslag**. Dat is geen bezuiniging maar een gevolg van hoe zijn
opslaglaag werkt: geheugen-gemapte bestanden en file-locking verdragen netwerkopslag slecht (traag,
en in het slechtste geval stille indexcorruptie), en Azure Files is de enige persistente mount die
een container-app kan krijgen. Een managed disk zou het oplossen maar vraagt een VM.

Dat kan hier, omdat de graaf **reproduceerbaar** is: de import-job haalt alle regelingen rechtstreeks
bij overheid.nl. Gevolgen:

- De graphdb-app schaalt **niet naar nul** (`minReplicas: 1`) – anders is de graaf bij de volgende
  request leeg. Dit is de component die doorloopt zolang de omgeving aan staat.
- Na elke herstart van die app moet de import-job opnieuw draaien.
- De similarity-index `bwb_similarity` (voor `semantic_search`) overleeft een herstart evenmin en
  moet opnieuw gebouwd worden; tot dat moment valt de tool terug op `search_wetgeving`.

## Beveiliging – hoe dit afwijkt van de zelfgehoste opzet

Zelfgehost draait GraphDB met eigen security en zit er een auth-proxy voor die het bearer-token van
graph-qa controleert en vervangt door een service-account. **Hier niet**: de graaf is alleen binnen
de Container Apps Environment bereikbaar (`external: false`), en dat is de grens. `GRAPHDB_TOKEN`
wordt wel gezet – de code eist het fail-closed – maar het is hier geen slot.

Voor een standby-/demo-omgeving is dat verdedigbaar. Wordt dit ooit een productieomgeving, dan hoort
hetzelfde service-account + proxy-patroon als in de zelfgehoste opzet erbij.

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

Wat de proxy is: een nginx (`<straat>-graphdb-proxy`) die uitsluitend `/mcp` doorlaat, alleen met het
juiste bearer-token, en al het andere met 404 afwijst – geen Workbench, geen REST-API, geen
SPARQL-endpoint. GraphDB zelf blijft `external: false` en wordt niet aangeraakt, dus de graaf
herstart niet en hoeft niet opnieuw geïmporteerd te worden. Hij schaalt naar nul.

Wat de proxy **niet** doet: read-only afdwingen. Wie erdoor komt heeft dezelfde rechten als Lex – een
SPARQL-body is op nginx-niveau niet betrouwbaar te keuren. Dat is te dragen omdat dit alleen op
acceptatie aan gaat, het token apart intrekbaar is en de graaf reproduceerbaar is uit overheid.nl.
Wil je harder, dan hoort daar GraphDB-security met een read-only account bij; dat raakt `bwb-import`
én graph-qa en is een eigen traject.

Weer dicht: actie **`mcp-proxy-afbreken`** (met de resource group ter bevestiging). `graphdb_proxy`
weer op `false` zetten is **niet** genoeg – een bicep-deploy in incremental mode verwijdert niets, en
`opruimen` beschermt de proxy juist omdat die actie niet kan weten of hij bedoeld is.

Verder ongewijzigd: alle applicatie-secrets zijn **bestanden** (`*_FILE`-patroon via secret-volumes),
nooit platte env-vars.

## Kosten drukken

- **Uit**: `az group delete -n rg-wetsanalyse` – de omgeving is in een kwartier terug te zetten.
- **Pauze**: `az postgres flexible-server stop -n wetsanalyse-db -g rg-wetsanalyse` plus de
  graphdb-app op nul replica's. Api, graph-qa en frontend schalen zelf terug (frontend houdt één
  replica: een cold start laat Auth.js-redirects timeouten).

## Bestanden

| bestand | wat |
|---|---|
| `main.bicep` | de volledige infrastructuur |
| `gen-deploy.py` | genereert de secrets + parameters en roept `az deployment` aan (`--what-if` / `--run`) |
| `.gitignore` | houdt `params.json` en licentiebestanden buiten de repo |

Het image dat elke app draait is een parameter (`apiImage`, `graphQaImage`, …), zodat CI een digest
kan meegeven in plaats van `:latest`.
