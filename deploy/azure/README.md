# Wetsanalyse op Azure — acceptatie en productie

Azure draagt het platform: **acceptatie** (elke merge naar `master`) en **productie** (een tag `v*`).
Elke straat is een **zelfstandige** omgeving op Azure Container Apps met eigen kennisgraaf en eigen
database, zonder verbinding met de docker-host. Die host draagt alleen nog de dev-omgeving.

Beide straten draaien doorlopend. PostgreSQL (B1ms) en GraphDB (`minReplicas: 1`) kunnen geen van
beide naar nul schalen, dus dit zijn vaste kosten — zie *Kosten drukken* onderaan.

| Component | Type | Bereikbaar |
|---|---|---|
| PostgreSQL | Flexible Server (B1ms) | intern |
| GraphDB | Container App | intern |
| BWB-import | Container Apps **Job** (handmatig) | — |
| API | Container App | intern |
| graph-qa | Container App | intern |
| Frontend | Container App | **publiek HTTPS** |

Alleen de frontend heeft een publiek adres. De rest praat binnen de Container Apps Environment.

## Vooraf: de GraphDB-licentie

**Zonder licentie is deze omgeving niet bruikbaar.** GraphDB 11 laat zonder licentiebestand alleen
*lezen* toe; het eerste schrijf-verzoek van de import-job krijgt een `500 No license was set`. Op de
docker-host zit die licentie in de persistente datadirectory (`/opt/graphdb/home/work/graphdb.license`)
en valt hij niet op — een verse instantie heeft hem niet.

Geef het bestand mee met `--license-file`; het script codeert het naar base64 en zet het als secret
in de deployment, waarna een init-container het op zijn plek schrijft. Controleer eerst of je
licentievoorwaarden een tweede, gelijktijdig draaiende instantie toestaan — dat is een vraag aan
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
| productie | een tag `v*` | `rg-wetsanalyse-prd` | `wetsanalyse-prd` |

> **Productie bestaat nog niet.** De service principal is Contributor op `rg-wetsanalyse` en verder
> niets; `az group create` op een nieuwe groep geeft `AuthorizationFailed` op
> `Microsoft.Resources/subscriptions/resourcegroups/write`. Eerste stap voor de productiestraat:
> iemand met Owner-rechten maakt `rg-wetsanalyse-prd` aan en geeft de service principal daar
> Contributor op. Daarna volstaat `azure-infra` → `productie` → `deploy`.

**Inrichten gebeurt per GitHub-environment** (Settings → Environments). Wat waar hoort:

- **vars, per environment** — `AZURE_RESOURCE_GROUP`, `APP_NAME`, `LLM_API_BASE`, optioneel
  `LLM_MODEL` en `AZURE_LOCATION`. Deze *moeten* per straat gezet zijn; ze hebben geen default meer,
  zodat een niet-ingerichte straat faalt in plaats van stilletjes op de verkeerde resource group uit
  te komen.
- **secrets** — `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`,
  `AZURE_CLIENT_SECRET`, `AZURE_AI_KEY`, `GRAPHDB_LICENSE_B64` (de licentie als
  `base64 -w0 graphdb.license`). Een job met een environment **erft de repo-secrets**, dus zolang
  beide straten dezelfde service principal en AI-key gebruiken, volstaan de bestaande repo-secrets.
  Wil je gescheiden credentials — aan te raden zodra productie echte gegevens draagt — zet ze dan
  als environment-secret; die overschrijft de repo-variant.

#### De applicatie-secrets roteren niet

Los van de Azure-credentials draagt de stack zijn eigen secrets: de sessiesleutel, de api-/admin-/
qa-tokens, het databasewachtwoord en `llm-config-secret`. Dat laatste is de **Fernet-sleutel**
waarmee de api de API-keys van modelprofielen én de 2FA-secrets van gebruikers versleutelt; roteert
die, dan is dat materiaal onherstelbaar onleesbaar.

`azure-infra.yml` bepaalt ze per deploy in deze volgorde:

1. een **GitHub environment-secret** met die naam (`WA_LLM_CONFIG_SECRET`, `WA_AUTH_SECRET`,
   `WA_DB_ADMIN_PASSWORD`, `WA_API_TOKEN`, `WA_ADMIN_TOKEN`, `WA_QA_API_TOKEN`,
   `WA_GRAPHDB_TOKEN`) — zet deze als je ze bewust wilt beheren of roteren;
2. anders de waarde die **nu in Azure draait**, uitgelezen uit de container apps;
3. anders **vers gegenereerd** — het geval van een nieuwe straat.

Daardoor is een infra-deploy op een draaiende omgeving veilig. De toets daarop: `wat-if` mag geen
`~ secret`-regels tonen voor de api-, frontend- en graph-qa-apps.

Op `productie` staat een **required reviewer** en een deployment-policy die alleen tags `v*`
toelaat; op `acceptatie` alleen de branch `master`. Die poort hoort in de environment te zitten en
niet in een workflow-conditie die je per ongeluk wegcommit.

De workflows falen bewust als een van deze secrets of vars ontbreekt. Eerder was dat een `if` die de
deploy-stap oversloeg — dan was de run groen terwijl er niets was uitgerold.

### Image-swap: automatisch

De vier `*-docker-publish.yml`-workflows bouwen naar GHCR en hebben daarna een `deploy`-job die de
container app op de juiste straat naar de nieuwe **digest** zet (niet naar een tag). Die job wacht
tot de nieuwe revisie daadwerkelijk `Running` is; `az containerapp update` keert namelijk al terug
zodra de revisie is *aangemaakt*, dus een container die bij het starten crasht bleef anders
onopgemerkt.

### Productie: promoveren, niet herbouwen

Een tag `v*` start **`promote.yml`**. Die bouwt niets: hij leest de digests die op *acceptatie*
draaien en zet díe op productie. Zo krijgt productie exact het artefact dat getest is — een
herbouw van dezelfde broncode levert nog altijd een ander image op (verse basis-images, verse
dependency-resolutie).

Vóór hij iets uitrolt, controleert hij per component het OCI-label
`org.opencontainers.image.revision` van het draaiende image tegen de commit achter de tag. Hoort het
er niet bij, dan faalt de promotie met een melding in plaats van iets anders uit te rollen dan de
tag belooft. Praktisch: tag een commit die al op `master` staat en waarvan acceptatie de uitrol
heeft afgerond.

De publish-workflows luisteren daarom **niet** op tags — die bouwen alleen voor acceptatie.

### Infra: handmatig

Actions → **azure-infra** → *Run workflow*, met een keuze voor de straat en de actie:

| actie | wat het doet |
|---|---|
| `wat-if` *(default)* | Azure toont welke resources zouden ontstaan of wijzigen. Maakt niets aan — de enige manier om de template tegen je echte subscription te toetsen (quota, regio, rechten). |
| `deploy` | rolt de stack uit (10-15 min; PostgreSQL is de trage stap) en start daarna meteen de import-job, want de graaf komt leeg op. |
| `afbreken` | verwijdert de hele resource group. Vraagt om de naam ter bevestiging. |
| `vul-graaf` | start de import-job en wacht hem af. |
| `inventaris` | read-only overzicht van wat er in de subscription draait. |

Dit is de enige workflow die resources aanmaakt, wijzigt of verwijdert. Vandaar `wat-if` als
default: een deploy raakt GraphDB, en die is niet-persistent.

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

- De graphdb-app schaalt **niet naar nul** (`minReplicas: 1`) — anders is de graaf bij de volgende
  request leeg. Dit is de component die doorloopt zolang de omgeving aan staat.
- Na elke herstart van die app moet de import-job opnieuw draaien.
- De similarity-index `bwb_similarity` (voor `semantic_search`) overleeft een herstart evenmin en
  moet opnieuw gebouwd worden; tot dat moment valt de tool terug op `search_wetgeving`.

## Beveiliging — hoe dit afwijkt van de zelfgehoste opzet

Zelfgehost draait GraphDB met eigen security en zit er een auth-proxy voor die het bearer-token van
graph-qa controleert en vervangt door een service-account. **Hier niet**: de graaf is alleen binnen
de Container Apps Environment bereikbaar (`external: false`), en dat is de grens. `GRAPHDB_TOKEN`
wordt wel gezet — de code eist het fail-closed — maar het is hier geen slot.

Voor een standby-/demo-omgeving is dat verdedigbaar. Wordt dit ooit een productieomgeving, dan hoort
hetzelfde service-account + proxy-patroon als in de zelfgehoste opzet erbij.

Verder ongewijzigd: alle applicatie-secrets zijn **bestanden** (`*_FILE`-patroon via secret-volumes),
nooit platte env-vars.

## Kosten drukken

- **Uit**: `az group delete -n rg-wetsanalyse` — de omgeving is in een kwartier terug te zetten.
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
