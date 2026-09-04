// deploy/azure/main.bicep
// Azure Container Apps-stack voor Wetsanalyse – een ZELFSTANDIGE omgeving:
//
//   PostgreSQL Flexible Server · GraphDB · BWB-import (job) · API · graph-qa · Frontend
//   + Log Analytics, Application Insights en een OTel-collector (de monitoring van deze straat)
//
// Deze stack praat NIET met de docker-host: hij brengt zijn eigen kennisgraaf mee. Dat scheelt een
// publieke ingang naar het thuisnetwerk, en maakt de omgeving los aan- en uitzetbaar.
//
// Deployment (vanuit de projectroot):
//   python3 deploy/azure/gen-deploy.py "<azure-ai-key>" \
//       --llm-api-base https://<resource>.services.ai.azure.com [--run]
//
// Na de deployment moet de import-job één keer draaien om de graaf te vullen; zie README.

@description('Azure-regio; erft van de resource group.')
param location string = resourceGroup().location

@description('Naam-prefix voor alle resources.')
param appName string = 'wetsanalyse'

@description('PostgreSQL-servernaam (moet globaal uniek zijn in Azure).')
param dbServerName string = '${appName}-db'

// ── Images ───────────────────────────────────────────────────────────────────
@description('Image-tags. CI kan hier een digest meegeven (ghcr.io/...@sha256:...).')
param apiImage string = 'ghcr.io/palmw01/wetsanalyse-api:latest'
param graphQaImage string = 'ghcr.io/palmw01/graph-qa:latest'
param frontendImage string = 'ghcr.io/palmw01/wetsanalyse-frontend:latest'
param bwbImportImage string = 'ghcr.io/palmw01/bwb-import:latest'
param graphdbImage string = 'ontotext/graphdb:11.4.0'
param otelCollectorImage string = 'otel/opentelemetry-collector-contrib:0.119.0'

// ── LLM-configuratie ─────────────────────────────────────────────────────────
@description('LLM-modelnaam (bijv. claude-sonnet-4-6).')
param llmModel string

@description('Azure AI Foundry base-URL.')
param llmApiBase string

@description('LLM-provider (default: azure_ai).')
param llmProvider string = 'azure_ai'

// ── Kennisgraaf ──────────────────────────────────────────────────────────────
@description('De BWB-regelingen die de import-job in de graaf zet.')
param bwbIds array = [
  'BWBR0002320'
  'BWBR0004766'
  'BWBR0004770'
  'BWBR0005537'
  'BWBR0018472'
  'BWBR0019237'
  'BWBR0024096'
]

@description('Hoeveel dagen back-ups van PostgreSQL bewaard blijven. Acceptatie heeft genoeg aan een week; voor productie is dit het enige vangnet onder de annotaties, en die zijn – anders dan de graaf – niet te reproduceren.')
@minValue(7)
@maxValue(35)
param backupRetentionDays int = 7

@description('Ondergrens voor api en graph-qa. 0 laat ze naar nul schalen (goedkoop, maar de eerste aanroep na een stille periode wacht op een koude start); 1 houdt ze warm. Acceptatie 0, productie 1.')
@minValue(0)
@maxValue(3)
param minReplicasApps int = 0

@description('Api-ingress publiek bereikbaar? Alleen acceptatie, zodat de admin-MCP (tools/wetsanalyse-admin-mcp) erbij kan; de default false houdt productie dicht.')
param apiExtern bool = false

@description('Rolt de externe MCP-proxy vóór GraphDB uit, zodat een MCP-client van buiten de graaf kan bevragen. Alleen acceptatie; default false. GraphDB zelf blijft altijd intern – deze parameter raakt die ingress niet.')
param graphdbProxyExtern bool = false

@description('Java-heap voor GraphDB. Moet passen binnen het geheugen van de container-app.')
param graphdbHeap string = '2g'

@secure()
@description('GraphDB-licentie, base64-gecodeerd (`base64 -w0 graphdb.license`). VERPLICHT voor een bruikbare graaf: GraphDB 11 laat zonder licentie alleen LEZEN toe, dus de import-job faalt met een 500 op het eerste schrijf-verzoek. Leeg laten kan – de omgeving komt dan op met een lege, read-only graaf.')
param graphdbLicenseBase64 string = ''

// ── Secrets ───────────────────────────────────────────────────────────────────
@secure()
param llmApiKey string

@secure()
param llmConfigSecret string

@secure()
param apiTokens string

@secure()
param adminTokens string

@secure()
param authSecret string

@secure()
param frontendApiToken string

@secure()
param frontendAdminToken string

@secure()
param dbAdminPassword string

@secure()
@description('Bearer-token waarmee graph-qa de GraphDB-MCP aanroept. Zie de noot bij graphQaApp: binnen deze omgeving is dit geen slot, de code eist het wel.')
param graphdbToken string

@secure()
@description('Bearer-token voor de EXTERNE GraphDB-MCP-proxy. Staat bewust los van graphdbToken: dat laatste is intern en wordt door GraphDB genegeerd, dit is het enige echte slot op de proxy en moet apart in te trekken zijn. Leeg = de proxy wordt niet uitgerold, ook niet met graphdbProxyExtern.')
param graphdbProxyToken string = ''

@secure()
@description('Bearer-token dat de frontend gebruikt om graph-qa aan te roepen (= graph-qa QA_API_TOKEN).')
param qaApiToken string

@secure()
@description('Bearer-token waarmee graph-qa naar de wetsanalyse-API schrijft. Eigen client in `apiTokens`, zodat het auditspoor laat zien wie er schreef.')
param graphQaApiToken string

// ─────────────────────────────────────────────────────────────────────────────
// 1. PostgreSQL Flexible Server
// ─────────────────────────────────────────────────────────────────────────────
// Draagt zowel de api-tabellen als de LangGraph-checkpointer van graph-qa (aparte tabellen, geen
// botsing). Burstable B1ms is de goedkoopste tier die volstaat; de server kan niet naar nul schalen
// – stop hem als de omgeving een tijd niet gebruikt wordt (zie README).
// Acceptatie en productie delen één resource group – de service principal mag er geen tweede
// aanmaken. Daarmee is een tag de enige manier om in de portal te zien wat wélke straat kost.
var straatTags = {
  straat: appName
}

resource pgServer 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = {
  name: dbServerName
  location: location
  tags: straatTags
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    administratorLogin: 'wetsanalyse'
    administratorLoginPassword: dbAdminPassword
    version: '16'
    storage: {
      storageSizeGB: 32
      autoGrow: 'Enabled'
    }
    backup: {
      backupRetentionDays: backupRetentionDays
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
  }
}

// `0.0.0.0-0.0.0.0` is niet "geen toegang" maar Azure's speciale regel **sta alle Azure-diensten
// toe** – en dat is breder dan het klinkt: het geldt voor elke tenant, niet alleen de onze. Wie een
// Azure-abonnement heeft kan het netwerkpad naar deze server bereiken; daarna beschermt alleen nog
// het wachtwoord (dat sterk en gegenereerd is, en niet roteert bij een deploy).
//
// Waarom het toch zo staat: fijnmaziger filteren vraagt vaste bron-IP's, en die heeft de
// container-apps-omgeving niet zolang er geen VNet-integratie is. Wil je dit echt dichtzetten, dan
// is dat de weg: de omgeving in een subnet, PostgreSQL achter een private endpoint, en deze regel
// weg. Dat is een forse wijziging met eigen kosten en een deploy die de database raakt – bewust niet
// gedaan, maar hier vastgelegd zodat de afweging vindbaar is.
resource pgFirewall 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-06-01-preview' = {
  parent: pgServer
  name: 'AllowAllAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource pgDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-06-01-preview' = {
  parent: pgServer
  name: 'wetsanalyse'
  properties: {
    charset: 'utf8'
    collation: 'en_US.utf8'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. Container Apps Environment
// ─────────────────────────────────────────────────────────────────────────────
// De logs moeten ergens landen. Zonder `appLogsConfiguration` bewaart Azure de stdout van de
// containers NIET – en dat is precies waar api, frontend en graph-qa hun gestructureerde JSON-logs
// heen schrijven. De observability-stack (Grafana/Tempo/Loki) draait alleen op de docker-host en is
// van buiten het LAN niet bereikbaar, dus die kan deze omgeving niet bedienen; een Log Analytics
// workspace per straat is wat het hier doorzoekbaar maakt.
//
// PerGB2018 met 30 dagen retentie: de goedkoopste zinnige stand. Traces en metrics komen erbij via
// Application Insights hieronder, dat op dezelfde workspace schrijft.
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${appName}'
  location: location
  tags: straatTags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Application Insights, workspace-based op de workspace hierboven. Daarmee staan logs, traces en
// metrics in ÉÉN workspace en zijn ze samen te bevragen – een request in `requests` is te koppelen
// aan de logregels van dezelfde beurt.
//
// Dit is wat de keten frontend → api → graph-qa onder één trace-id zichtbaar maakt. Zonder dit
// bestaat die correlatie wel in de code (elke dienst propageert traceparent) maar nergens in beeld.
resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${appName}'
  location: location
  tags: straatTags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
    // De portal-ingang volstaat; de apps praten via de collector, niet via een SDK-key.
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

resource cae 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${appName}'
  location: location
  tags: straatTags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 2b. OTel-collector – de brug naar Application Insights
// ─────────────────────────────────────────────────────────────────────────────
// Application Insights kent geen OTLP-ingest. De twee wegen erheen zijn een collector ertussen, of
// de Azure Monitor OTel-distro ín de apps. Dat laatste is een codewijziging in drie diensten én
// vendor-lock op precies de plek waar het ontwerp provider-neutraal wil zijn: de apps kennen alleen
// een configureerbaar OTLP-endpoint, en leeg = uit.
//
// Deze collector is STATELESS: geen opslag, geen state, een herstart kost niets. Hij schaalt naar
// nul als er geen verkeer is en komt op zodra een app iets stuurt.
var collectorConfig = '''
receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318
      grpc:
        endpoint: 0.0.0.0:4317

processors:
  batch:
    timeout: 5s
  # Zonder cap kan een piek in de app de collector opblazen.
  memory_limiter:
    check_interval: 1s
    limit_percentage: 80
    spike_limit_percentage: 20

exporters:
  azuremonitor:
    connection_string: "${env:AZMON_CONNECTION_STRING}"

service:
  telemetry:
    logs:
      level: warn
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [azuremonitor]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [azuremonitor]
    logs:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [azuremonitor]
'''

resource collectorApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${appName}-otel-collector'
  location: location
  tags: straatTags
  properties: {
    environmentId: cae.id
    configuration: {
      // Intern-only: alleen de apps in deze omgeving sturen erheen.
      ingress: {
        external: false
        targetPort: 4318
        transport: 'auto'
        additionalPortMappings: [
          { external: false, targetPort: 4317, exposedPort: 4317 }
        ]
      }
      secrets: [
        { name: 'azmon-connection-string', value: insights.properties.ConnectionString }
        { name: 'collector-config', value: collectorConfig }
      ]
    }
    template: {
      containers: [
        {
          name: 'otel-collector'
          image: otelCollectorImage
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'AZMON_CONNECTION_STRING', secretRef: 'azmon-connection-string' }
            { name: 'COLLECTOR_CONFIG', secretRef: 'collector-config' }
          ]
          // Container Apps kennen geen configmounts. De collector leest zijn config rechtstreeks uit
          // een omgevingsvariabele met `--config=env:` – geen tussenbestand, en geen shell nodig:
          // dit image heeft er geen (`/bin/sh` bestaat niet), dus een `command: ['/bin/sh', …]`
          // laat de container stil falen vóór de eerste logregel.
          args: ['--config=env:COLLECTOR_CONFIG']
        }
      ]
      scale: {
        // Bewust NIET naar nul. Een exporter probeert één keer en geeft het op: met scale-to-zero
        // valt de eerste export in de koude start van de container, en die spans zijn dan weg —
        // precies de telemetrie waarmee je zou merken dat er iets aan de hand is. Dit is met 0.25
        // vCPU de goedkoopste container in de stack; hem laten draaien is het waard.
        minReplicas: 1
        maxReplicas: 2
      }
    }
  }
}

var collectorEndpoint = 'http://${collectorApp.name}'

// ─────────────────────────────────────────────────────────────────────────────
// 3. GraphDB – de kennisgraaf (intern)
// ─────────────────────────────────────────────────────────────────────────────
// GEEN persistente opslag, en dat is een bewuste keuze. GraphDB's opslaglaag gebruikt
// geheugen-gemapte bestanden en file-locking; op Azure Files levert dat hetzelfde risico als op een
// NFS-share (traagheid, in het slechtste geval stille indexcorruptie) – precies waarom de graaf op
// de zelfgehoste opzet lokale opslag heeft. Een managed disk lost dat op maar kan niet aan een container-app.
//
// Dat kan hier, omdat de graaf volledig REPRODUCEERBAAR is: de import-job haalt alle regelingen
// rechtstreeks bij overheid.nl (~20s). Herstart betekent dus opnieuw importeren, niet dataverlies.
//
// Twee gevolgen om te kennen:
//   • `minReplicas: 1` – schaalt bewust NIET naar nul, want dan is de graaf bij de volgende request
//     leeg. Dit is de enige component die doorloopt zolang de omgeving aan staat.
//   • De similarity-index (`bwb_similarity`, voor semantic_search) overleeft een herstart evenmin
//     en moet opnieuw gebouwd worden; tot dat moment degradeert de tool naar search_wetgeving.
var heeftLicentie = !empty(graphdbLicenseBase64)

resource graphdbApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${appName}-graphdb'
  location: location
  tags: straatTags
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      ingress: {
        external: false
        targetPort: 7200
        transport: 'auto'
      }
      secrets: heeftLicentie ? [
        { name: 'graphdb-license', value: graphdbLicenseBase64 }
      ] : []
    }
    template: {
      // De licentie komt als base64-secret binnen en wordt door een init-container naar een gedeeld
      // EmptyDir geschreven. Twee redenen voor die omweg: een Container Apps-secret is een string
      // (het licentiebestand is binair), en een secret-volume rechtstreeks op /opt/graphdb/home/work
      // zou de werkdirectory van GraphDB overschrijven. `graphdb.license.file` laat ons het bestand
      // elders neerzetten.
      volumes: heeftLicentie ? [
        {
          name: 'graphdb-license-b64'
          storageType: 'Secret'
          secrets: [
            { secretRef: 'graphdb-license', path: 'graphdb.license.b64' }
          ]
        }
        {
          name: 'graphdb-license'
          storageType: 'EmptyDir'
        }
      ] : []
      initContainers: heeftLicentie ? [
        {
          name: 'license-decode'
          image: 'mcr.microsoft.com/azurelinux/base/core:3.0'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          command: ['/bin/sh', '-c']
          args: ['base64 -d /b64/graphdb.license.b64 > /license/graphdb.license && echo licentie-geplaatst']
          volumeMounts: [
            { volumeName: 'graphdb-license-b64', mountPath: '/b64' }
            { volumeName: 'graphdb-license', mountPath: '/license' }
          ]
        }
      ] : []
      containers: [
        {
          name: 'graphdb'
          image: graphdbImage
          // Azure ACA Consumption vereist een geldige CPU/geheugen-combi; 4Gi kan alleen met 2.0 CPU.
          resources: {
            cpu: json('2.0')
            memory: '4Gi'
          }
          volumeMounts: heeftLicentie ? [
            { volumeName: 'graphdb-license', mountPath: '/license' }
          ] : []
          env: [
            { name: 'GDB_JAVA_OPTS', value: heeftLicentie ? '-Xms1g -Xmx${graphdbHeap} -Dgraphdb.license.file=/license/graphdb.license' : '-Xms1g -Xmx${graphdbHeap}' }
          ]
          probes: [
            {
              type: 'Readiness'
              httpGet: { path: '/rest/repositories', port: 7200 }
              initialDelaySeconds: 30
              periodSeconds: 15
              timeoutSeconds: 10
              failureThreshold: 10
            }
            // Zonder Liveness blijft een vastgelopen GraphDB draaien zolang hij de poort openhoudt.
            // Dat weegt hier zwaarder dan elders: dit is de enige component met minReplicas én
            // maxReplicas op 1, dus er is geen tweede replica die het overneemt. Ruim afgesteld —
            // GraphDB start traag (de Readiness wacht al 30s) en een te scherpe liveness zou hem
            // tijdens het opkomen doodslaan.
            //
            // LET OP: `initialDelaySeconds` mag bij Container Apps hoogstens 60 zijn; hoger wordt
            // geweigerd met `ContainerAppProbeInitialDelaySecondsOutOfRange`. Dat is een
            // preflight-controle van de resource provider en `what-if` voert hem NIET uit — een
            // groene what-if bewijst hier dus niets. Deze waarde stond op 120 en maakte de template
            // vanaf 27 aug 2026 onuitrolbaar; het viel niemand op omdat infra handmatig is en er
            // sindsdien geen deploy meer was.
            //
            // De bedoelde speling blijft gelijk: die is initialDelay + failureThreshold × period,
            // dus 120 + 5×30 = 270 s werd 60 + 7×30 = 270 s. Verlaag `failureThreshold` niet zonder
            // te bedenken dat je daarmee de opstarttijd van GraphDB inkort.
            {
              type: 'Liveness'
              httpGet: { path: '/rest/repositories', port: 7200 }
              initialDelaySeconds: 60
              periodSeconds: 30
              timeoutSeconds: 10
              failureThreshold: 7
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

var graphdbInternalUrl = 'https://${graphdbApp.properties.configuration.ingress.fqdn}'

// ─────────────────────────────────────────────────────────────────────────────
// 3b. GraphDB-MCP-proxy – de ENIGE weg naar de graaf van buiten (optioneel, acceptatie)
// ─────────────────────────────────────────────────────────────────────────────
// Waarom een aparte app en niet gewoon `external: true` op GraphDB: GraphDB draait hier zonder eigen
// security (zie de noot bij graphQaApp). Zijn ingress openzetten levert een onbeveiligd, SCHRIJFBAAR
// SPARQL-endpoint plus de Workbench op internet – de netwerkgrens ís de beveiliging. Deze nginx zet
// er een echte grens omheen en laat GraphDB zelf ongemoeid, dus geen enkele interne client
// (graph-qa, de eval-job, bwb-import) verandert en de graaf hoeft niet te herstarten.
//
// Wat hij doorlaat: uitsluitend `/mcp`, en alleen met het juiste bearer-token. Geen `/rest`, geen
// Workbench, geen SPARQL-endpoint. Het token is een EXACTE match op de hele Authorization-header;
// geen regex, want daar win je dit spel niet mee.
//
// Wat hij NIET afdwingt: read-only. Wie door de deur komt heeft dezelfde rechten als Lex, want een
// SPARQL-body is op nginx-niveau niet betrouwbaar te keuren (de allowlist in
// tools/graph-qa/agent/mcp_client.py beschermt alleen graph-qa zelf). Dat is te dragen omdat dit
// alleen op acceptatie aan gaat, het token apart intrekbaar is, en de graaf volledig
// reproduceerbaar is uit overheid.nl (`vul-graaf`). Wil je harder, dan hoort daar GraphDB-security
// met een read-only account bij – dat raakt bwb-import én graph-qa en is een eigen traject.
var graphdbProxyAan = graphdbProxyExtern && !empty(graphdbProxyToken)

// Placeholders in plaats van interpolatie: een Bicep multi-line string (''') doet GEEN `${}`, en
// een nginx-config staat vol `$variabelen` die je daar juist met rust wilt laten. Zelfde aanpak als
// de Grafana-dashboards in deploy/azure/grafana/, die met `__STRAAT__` en `__DSUID__` werken.
var graphdbProxyConfigSjabloon = '''
# De sleutel van de map hieronder is de HELE Authorization-header ("Bearer " + het token, samen
# ruim 50 tekens) en past niet in nginx' standaard hash-bucket van 64 bytes. Zonder deze regel
# weigert nginx te starten met "could not build map_hash" – en dat is precies wat er bij de eerste
# uitrol gebeurde: lokaal getest met een kort voorbeeldtoken, in Azure met een echte van 48 hex.
map_hash_bucket_size 256;

map $http_authorization $mag_erdoor {
  default                     0;
  "Bearer __TOKEN__"          1;
}

server {
  listen 8080;

  # Alles wat geen /mcp is bestaat hier niet: de Workbench en de REST-API blijven binnen.
  location / {
    return 404;
  }

  location /mcp {
    if ($mag_erdoor = 0) {
      return 401;
    }

    # Het interne adres binnen de Container Apps Environment – hetzelfde patroon als
    # `collectorEndpoint` hierboven. De ingress van GraphDB luistert op 80 en stuurt door naar 7200.
    proxy_pass http://__GRAPHDB__;

    # MCP Streamable HTTP antwoordt met text/event-stream. Zonder deze vier regels houdt nginx het
    # antwoord vast tot de stream sluit, en dan lijkt elke tool-aanroep te hangen.
    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_set_header Connection "";
    proxy_read_timeout 300s;

    # GEEN `proxy_set_header Host $host`. De router van Container Apps kiest de doel-app op de
    # Host-header; met de externe hostname erin stuurt hij de aanroep terug naar deze proxy en
    # loopt hij rond. De default van proxy_pass (de upstream-naam) is precies wat hier moet staan.
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
'''

var graphdbProxyConfig = replace(
  replace(graphdbProxyConfigSjabloon, '__GRAPHDB__', '${appName}-graphdb'),
  '__TOKEN__',
  graphdbProxyToken
)

resource graphdbProxyApp 'Microsoft.App/containerApps@2024-03-01' = if (graphdbProxyAan) {
  name: '${appName}-graphdb-proxy'
  location: location
  tags: straatTags
  // Expliciet, want de upstream staat als string in de nginx-config en niet als resource-referentie
  // – bicep leidt hier dus geen volgorde uit af. nginx WEIGERT te starten als de naam in `proxy_pass`
  // bij het opstarten niet resolvet ("host not found in upstream"), dus op een verse straat zou de
  // proxy in een crashloop komen tot GraphDB er is.
  dependsOn: [
    graphdbApp
  ]
  properties: {
    environmentId: cae.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        transport: 'auto'
        allowInsecure: false
      }
      secrets: [
        // De linter ziet een gewone string en niet meer dat het token eronder `@secure()` is – die
        // markering overleeft de `replace()` niet. De waarde komt wél uit graphdbProxyToken, staat
        // nergens in een output en een container-app-secret is niet terug te lezen in de portal.
        #disable-next-line use-secure-value-for-secure-inputs
        { name: 'proxy-config', value: graphdbProxyConfig }
      ]
    }
    template: {
      // Secrets zijn in Container Apps NIET revisie-scoped: een gewijzigde secret-waarde levert
      // geen nieuwe revisie op, en de draaiende container houdt de oude. Hier zit de hele
      // nginx-config in een secret, dus zonder deze suffix rolt een configwijziging simpelweg niet
      // uit — dat is precies wat er bij de tweede uitrol gebeurde: de fix zat in het secret, maar
      // dezelfde (gefaalde) revisie bleef staan. Met de hash van de config in de suffix dwingt elke
      // wijziging — ook een tokenrotatie — een nieuwe revisie af.
      //
      // De hash lekt niets bruikbaars: uniqueString is niet omkeerbaar, en wie hem in Azure kan
      // zien, kan het secret zelf toch al lezen.
      revisionSuffix: 'c${substring(uniqueString(graphdbProxyConfig), 0, 8)}'
      // Container Apps kennen geen configmounts, maar een secret-volume schrijft de string wél als
      // bestand – hetzelfde patroon als de GraphDB-licentie hierboven. nginx laadt alles in
      // /etc/nginx/conf.d/*.conf; de mount verbergt de default.conf die het image daar zelf
      // neerzet, dus deze config is het enige dat er staat.
      volumes: [
        {
          name: 'proxy-config'
          storageType: 'Secret'
          secrets: [
            { secretRef: 'proxy-config', path: 'default.conf' }
          ]
        }
      ]
      containers: [
        {
          name: 'nginx'
          image: 'nginx:1.27-alpine'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          volumeMounts: [
            { volumeName: 'proxy-config', mountPath: '/etc/nginx/conf.d' }
          ]
        }
      ]
      scale: {
        // Naar nul: dit is gereedschap voor een mens aan een toetsenbord, geen dienst waar iets van
        // afhangt. De koude start kost de eerste aanroep een paar seconden.
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. BWB-import – vult de graaf (handmatige job)
// ─────────────────────────────────────────────────────────────────────────────
// Een Job en geen container-app: importeren is een eindige taak. De importer maakt de repository
// `inning` zelf aan als die ontbreekt (`GraphDbWriter.ensure_constraints`), dus dit is de enige stap
// tussen een lege GraphDB en een bruikbare graaf.
//
// Draaien: `az containerapp job start -n ${appName}-bwb-import -g <rg>`. Doe dat na elke deployment
// en na elke herstart van de graphdb-app.
resource bwbImportJob 'Microsoft.App/jobs@2024-03-01' = {
  name: '${appName}-bwb-import'
  location: location
  tags: straatTags
  properties: {
    environmentId: cae.id
    // Wekelijks herimporteren, net als de zelfgehoste importer. De import is per wet idempotent
    // (named-graph PUT), dus dit is veilig – en het is wat de graaf bijhoudt zonder dat er een
    // deploy voor nodig is. `azure-infra.yml` start hem daarnaast direct na elke deploy, want
    // GraphDB is niet-persistent en komt dus leeg op.
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: 3600
      replicaRetryLimit: 1
      scheduleTriggerConfig: {
        cronExpression: '0 3 * * 1'   // maandag 03:00 UTC
        parallelism: 1
        replicaCompletionCount: 1
      }
    }
    template: {
      containers: [
        {
          name: 'bwb-import'
          image: bwbImportImage
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          // De CLI (app/main.py), niet de HTTP-service uit de Dockerfile-CMD: een job heeft geen
          // webserver nodig en de exitcode is meteen het resultaat van de import.
          command: ['python', '-m', 'app.main']
          args: bwbIds
          env: [
            { name: 'GRAPHDB_URL', value: graphdbInternalUrl }
            { name: 'GRAPHDB_REPOSITORY', value: 'inning' }
            { name: 'GRAPHDB_BASE_IRI', value: 'urn:bwb:' }
            { name: 'GRAPHDB_ONTOLOGY_IRI', value: 'urn:bwb-ns:' }
            { name: 'BWB_VALIDATE_XSD', value: 'true' }
            { name: 'BWB_IMPORT_WTI', value: 'true' }
            { name: 'BWB_DETECT_TEKSTUELE_REFS', value: 'true' }
            { name: 'HOME', value: '/tmp' }
          ]
        }
      ]
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. API Container App (intern; op acceptatie publiek – zie `apiExtern`)
// ─────────────────────────────────────────────────────────────────────────────
var dbUrl = 'postgresql+asyncpg://wetsanalyse:${dbAdminPassword}@${pgServer.properties.fullyQualifiedDomainName}:5432/wetsanalyse?ssl=require'
// psycopg-scheme voor de LangGraph-checkpointer van graph-qa (geen +asyncpg, andere driver).
var checkpointDbUrl = 'postgresql://wetsanalyse:${dbAdminPassword}@${pgServer.properties.fullyQualifiedDomainName}:5432/wetsanalyse?sslmode=require'

resource apiApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${appName}-api'
  location: location
  tags: straatTags
  dependsOn: [pgDatabase]
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      // Bewaar een handvol inactieve revisies, anders is `rollback.yml` een knop zonder inhoud:
      // in de single-revision-modus (de default) deactiveert Azure de oude revisie bij elke
      // image-swap en ruimt hem daarna op. Gemeten op 27 aug 2026: alle drie de apps hadden nog
      // precies één revisie, terwijl de nummering (41/57/75) tientallen voorgangers verried.
      // Inactieve revisies draaien niet en kosten dus geen replicas.
      maxInactiveRevisions: 5
      // DE INGRESS ZIT VÓÓR DE HELE APP, niet alleen voor /v1/admin. Met `apiExtern` worden ook
      // /v1/annotatie, /v1/gesprekken, /v1/auth, /v1/berichten en /v1/feedback publiek bereikbaar,
      // en daarmee verschuift een vertrouwensgrens: de api leest de identiteit uit de header
      // `X-User-Id` omdat die "nooit uit browser-input komt" – hij wordt server-side door de BFF
      // gezet. Publiek houdt die aanname geen stand; wie een client-token uit `apiTokens` heeft,
      // kiest zijn eigen X-User-Id en leest of schrijft in elk gesprek en annotatiedocument.
      //
      // Daarom staat de default op false en zet alleen de acceptatie-tak van `azure-infra.yml` hem
      // aan (`--api-extern` in gen-deploy.py). Op acceptatie staan geen reviewbeslissingen van
      // juristen; op productie wel, en die straat blijft dicht. Een guard in `poort` bewaakt beide.
      ingress: {
        external: apiExtern
        targetPort: 3000
        transport: 'auto'
      }
      secrets: [
        { name: 'llm-api-key', value: llmApiKey }
        { name: 'llm-config-secret', value: llmConfigSecret }
        { name: 'api-tokens', value: apiTokens }
        { name: 'admin-tokens', value: adminTokens }
        { name: 'database-url', value: dbUrl }
      ]
    }
    template: {
      // Secrets als BESTANDEN, niet als env-var. Dat is een harde afspraak van de api
      // (`api/CLAUDE.md` → "Secrets zijn bestanden"): een env-dump of een procesoverzicht lekt ze
      // anders. De code leest elk secret via `${NAAM}_FILE`.
      volumes: [
        {
          name: 'api-secrets'
          storageType: 'Secret'
          secrets: [
            { secretRef: 'llm-api-key', path: 'llm_api_key' }
            { secretRef: 'llm-config-secret', path: 'llm_config_secret' }
            { secretRef: 'api-tokens', path: 'api_tokens' }
            { secretRef: 'admin-tokens', path: 'admin_tokens' }
            { secretRef: 'database-url', path: 'database_url' }
          ]
        }
      ]
      containers: [
        {
          name: 'api'
          image: apiImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          volumeMounts: [
            {
              volumeName: 'api-secrets'
              mountPath: '/run/secrets'
            }
          ]
          env: [
            // Telemetrie naar de collector in deze omgeving, die het doorschrijft naar Application
            // Insights. Leeg laten = uit; dat was de stand tot nu toe.
            { name: 'OTEL_EXPORTER_OTLP_ENDPOINT', value: collectorEndpoint }
            { name: 'OTEL_SERVICE_NAME', value: 'wetsanalyse-api' }
            // De straat staat op elke span, zodat acceptatie en productie in dezelfde workspace
            // uit elkaar te houden zijn.
            { name: 'OTEL_RESOURCE_ATTRIBUTES', value: 'deployment.environment=${appName}' }
            { name: 'LLM_PROVIDER', value: llmProvider }
            { name: 'LLM_MODEL', value: llmModel }
            { name: 'LLM_API_BASE', value: llmApiBase }
            { name: 'WETSANALYSE_AUTH_REQUIRED', value: '1' }
            { name: 'HOME', value: '/tmp' }
            { name: 'LLM_API_KEY_FILE', value: '/run/secrets/llm_api_key' }
            { name: 'LLM_CONFIG_SECRET_FILE', value: '/run/secrets/llm_config_secret' }
            { name: 'WETSANALYSE_API_TOKENS_FILE', value: '/run/secrets/api_tokens' }
            { name: 'WETSANALYSE_ADMIN_TOKENS_FILE', value: '/run/secrets/admin_tokens' }
            { name: 'DATABASE_URL_FILE', value: '/run/secrets/database_url' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 3000 }
              initialDelaySeconds: 15
              periodSeconds: 30
              timeoutSeconds: 5
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: { path: '/ready', port: 3000 }
              initialDelaySeconds: 10
              periodSeconds: 10
              timeoutSeconds: 5
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicasApps
        maxReplicas: 3
      }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 6. graph-qa Container App (intern) – de agent op de kennisgraaf
// ─────────────────────────────────────────────────────────────────────────────
// Praat met de GraphDB uit deze stack, via de MCP-server die GraphDB >= 11.2 zelf meebrengt op /mcp.
//
// LET OP – geen auth-proxy zoals in de zelfgehoste opzet. Daar controleert een nginx het bearer-token en vervangt
// het door het GraphDB-service-account; hier is de graaf alleen binnen de Container Apps
// Environment bereikbaar (`external: false`) en dat is de grens. `GRAPHDB_TOKEN` blijft gezet omdat
// de code het fail-closed eist (`require_graph`), maar het is hier GEEN slot – GraphDB draait
// zonder eigen security. Zodra deze omgeving meer dan standby/demo wordt, hoort daar hetzelfde
// service-account + proxy-patroon als in de zelfgehoste opzet.
resource graphQaApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${appName}-graph-qa'
  location: location
  tags: straatTags
  dependsOn: [pgDatabase]
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      // Bewaar een handvol inactieve revisies, anders is `rollback.yml` een knop zonder inhoud:
      // in de single-revision-modus (de default) deactiveert Azure de oude revisie bij elke
      // image-swap en ruimt hem daarna op. Gemeten op 27 aug 2026: alle drie de apps hadden nog
      // precies één revisie, terwijl de nummering (41/57/75) tientallen voorgangers verried.
      // Inactieve revisies draaien niet en kosten dus geen replicas.
      maxInactiveRevisions: 5
      ingress: {
        external: false
        targetPort: 8080
        transport: 'auto'
      }
      secrets: [
        { name: 'llm-api-key', value: llmApiKey }
        { name: 'graphdb-token', value: graphdbToken }
        { name: 'qa-api-token', value: qaApiToken }
        { name: 'wetsanalyse-api-token', value: graphQaApiToken }
        { name: 'checkpoint-db-url', value: checkpointDbUrl }
      ]
    }
    template: {
      volumes: [
        {
          name: 'graph-qa-secrets'
          storageType: 'Secret'
          secrets: [
            { secretRef: 'llm-api-key', path: 'llm_api_key' }
            { secretRef: 'graphdb-token', path: 'graphdb_token' }
            { secretRef: 'qa-api-token', path: 'qa_api_token' }
            { secretRef: 'wetsanalyse-api-token', path: 'wetsanalyse_api_token' }
            { secretRef: 'checkpoint-db-url', path: 'checkpoint_db_url' }
          ]
        }
      ]
      containers: [
        {
          name: 'graph-qa'
          image: graphQaImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          volumeMounts: [
            {
              volumeName: 'graph-qa-secrets'
              mountPath: '/run/secrets'
            }
          ]
          env: [
            // Telemetrie naar de collector in deze omgeving, die het doorschrijft naar Application
            // Insights. Leeg laten = uit; dat was de stand tot nu toe.
            { name: 'OTEL_EXPORTER_OTLP_ENDPOINT', value: collectorEndpoint }
            { name: 'OTEL_SERVICE_NAME', value: 'wetsanalyse-graph-qa' }
            // De straat staat op elke span, zodat acceptatie en productie in dezelfde workspace
            // uit elkaar te houden zijn.
            { name: 'OTEL_RESOURCE_ATTRIBUTES', value: 'deployment.environment=${appName}' }
            // graph-qa gebruikt de Anthropic-SDK → de base-URL draagt het `/anthropic`-segment
            // (i.t.t. de api/LiteLLM die kale LLM_API_BASE gebruikt).
            { name: 'AZURE_FOUNDRY_BASE_URL', value: '${llmApiBase}/anthropic' }
            { name: 'AZURE_FOUNDRY_API_KEY_FILE', value: '/run/secrets/llm_api_key' }
            { name: 'LLM_MODEL', value: llmModel }
            { name: 'GRAPHDB_MCP_URL', value: '${graphdbInternalUrl}/mcp' }
            { name: 'GRAPHDB_TOKEN_FILE', value: '/run/secrets/graphdb_token' }
            { name: 'GRAPHDB_REPOSITORY_ID', value: 'inning' }
            { name: 'QA_API_TOKEN_FILE', value: '/run/secrets/qa_api_token' }
            // Zonder deze twee is `legt_zelf_vast` false en legt de agent de uitkomst van een
            // annotatiebeurt NIET vast – de werkplek toont dan netjes markeringen die nergens
            // landen. Dat was tussen 19 aug (commit 98eef5a, één schrijfpad) en 27 aug 2026 het
            // geval op Azure: die commit richtte dev in maar raakte deze bicep niet.
            { name: 'WETSANALYSE_API_URL', value: apiInternalUrl }
            { name: 'WETSANALYSE_API_TOKEN_FILE', value: '/run/secrets/wetsanalyse_api_token' }
            { name: 'SIMILARITY_INDEX', value: 'bwb_similarity' }
            // Uit: dan draait de pure agentische lus. Met decompositie ligt er een vast recept
            // overheen waarin solve_node een eigen agent-lus nabouwt – een tweede implementatie
            // met eigen vangnetten, die uiteen kan lopen met agent_node.
            { name: 'ENABLE_DECOMPOSITION', value: '0' }
            // Gespreksgeheugen in Postgres, NIET op schijf: het filesystem van een container-app is
            // ephemeer en de app kan schalen, dus een SQLite-bestand verliest het geheugen bij
            // elke herstart en is per-replica verschillend.
            { name: 'CHECKPOINT_DB_URL_FILE', value: '/run/secrets/checkpoint_db_url' }
            { name: 'HOME', value: '/tmp' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8080 }
              initialDelaySeconds: 15
              periodSeconds: 30
              timeoutSeconds: 5
              failureThreshold: 3
            }
            // Zonder Readiness routeert Container Apps verkeer zodra de container start, ook als de
            // app nog niet kan antwoorden. Bij een koude start van deze agent (LangGraph + MCP) is
            // dat tientallen seconden, en dan loopt de werkplek tegen de 10s-timeout van
            // frontend/app/api/annotatie/run/route.ts – zichtbaar als "Run-proxy: actieve run niet
            // op te halen". `/health` is hier triviaal, dus liveness en readiness toetsen hetzelfde;
            // het punt is niet wát er getoetst wordt maar dát routering wacht tot het proces
            // antwoordt. Een eigen /ready (zie api/app/main.py) zou scherper zijn.
            {
              type: 'Readiness'
              httpGet: { path: '/health', port: 8080 }
              initialDelaySeconds: 5
              periodSeconds: 5
              timeoutSeconds: 5
              failureThreshold: 6
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicasApps
        maxReplicas: 2
      }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 6b. Eval-job – meet de annotatieketen tegen de échte graaf (handmatig)
// ─────────────────────────────────────────────────────────────────────────────
// Waarom dit hier moet draaien en niet op een ontwikkelmachine: GraphDB staat op `external: false`
// en is dus alleen bínnen deze omgeving bereikbaar. `eval/run_eval.py --annotatie` draait de agent
// in-proces en heeft een directe graafverbinding nodig, dus een job in dezelfde omgeving is de
// enige plek waar de keten tegen echte wettekst te meten valt.
//
// Handmatige trigger, geen schedule: elke run kost LLM-tokens. Draaien via `azure-infra.yml`
// (actie `eval`) of `az containerapp job start -n ${appName}-eval -g <rg>`.
//
// DRIE RUNS PER VARIANT, en dat is de kern van de meting. JAS-annotatie kent interpretatieruimte
// en dezelfde bepaling levert tussen runs sterk verschillende uitkomsten op (geel varieerde
// 38–77%). Eén run is daarom geen meting maar een anekdote; drie runs geven een bandbreedte. De
// loop gaat door na een mislukte run en meldt aan het eind of er één faalde — anders verlies je de
// runs die wél slaagden.
//
// TWEE VARIANTEN, in één uitvoering. `vol` is de volle klassenreferentie uit de skill (~14,5k
// tekens); `kort` is dezelfde referentie tot de eerste zin per veld (~5,6k), even groot als de
// verkorte referentie die tot 1 sep 2026 in de prompt stond. Op 1 sep is die prompt verdubbeld op
// de redenering dat de bron rijker is dan wat erin stond — niet op een meting. Dit beantwoordt die
// vraag met cijfers.
//
// Beide varianten in dezelfde uitvoering draaien is geen gemak maar methode: dezelfde graafstand,
// hetzelfde model, dezelfde dag. Een vergelijking over twee deploys heen zou die drie door elkaar
// halen met het effect dat je wilt meten.
resource evalJob 'Microsoft.App/jobs@2024-03-01' = {
  name: '${appName}-eval'
  location: location
  tags: straatTags
  properties: {
    environmentId: cae.id
    configuration: {
      triggerType: 'Manual'
      // Zes runs (twee varianten × drie) × acht cases × een annotatieketen van 60–90 s ≈ 60 min;
      // twee uur geeft lucht.
      replicaTimeout: 7200
      replicaRetryLimit: 0   // opnieuw proberen zou de meting vervuilen, niet redden
      manualTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
      }
      // Een job draagt zijn eigen secrets; hij kan niet bij die van de graph-qa-app.
      secrets: [
        { name: 'llm-api-key', value: llmApiKey }
        { name: 'graphdb-token', value: graphdbToken }
      ]
    }
    template: {
      volumes: [
        {
          name: 'eval-secrets'
          storageType: 'Secret'
          secrets: [
            { secretRef: 'llm-api-key', path: 'llm_api_key' }
            { secretRef: 'graphdb-token', path: 'graphdb_token' }
          ]
        }
      ]
      containers: [
        {
          name: 'eval'
          image: graphQaImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          volumeMounts: [
            { volumeName: 'eval-secrets', mountPath: '/run/secrets' }
          ]
          command: ['sh', '-c']
          args: [
            'rc=0; for v in vol kort; do for i in 1 2 3; do echo "=== VARIANT $v · RUN $i VAN 3 ==="; ANNOTATIE_PROMPT_KORT=$( [ "$v" = kort ] && echo true || echo false ) python eval/run_eval.py --annotatie || rc=1; done; done; echo "=== KLAAR (rc=$rc) ==="; exit $rc'
          ]
          env: [
            { name: 'AZURE_FOUNDRY_BASE_URL', value: '${llmApiBase}/anthropic' }
            { name: 'AZURE_FOUNDRY_API_KEY_FILE', value: '/run/secrets/llm_api_key' }
            { name: 'LLM_MODEL', value: llmModel }
            { name: 'GRAPHDB_MCP_URL', value: '${graphdbInternalUrl}/mcp' }
            { name: 'GRAPHDB_TOKEN_FILE', value: '/run/secrets/graphdb_token' }
            { name: 'GRAPHDB_REPOSITORY_ID', value: 'inning' }
            { name: 'SIMILARITY_INDEX', value: 'bwb_similarity' }
            { name: 'HOME', value: '/tmp' }
            // Moet gezet zijn, en moet naar /tmp wijzen. `Settings.checkpoint_db_path` heeft een
            // RELATIEVE default (`conversations_checkpoints.db`), dus zonder deze regel probeert de
            // agent een SQLite-bestand in de workdir `/app` te maken — en die is voor appuser
            // alleen lees-/uitvoerbaar (`chmod a+rX` in de Dockerfile). De eerste eval-run viel
            // daarop om met een aiosqlite-fout in `_checkpointer_ctx`.
            //
            // Bewust /tmp en niet de gedeelde Postgres: het geheugen van een eval-run hoort bij die
            // run en verdwijnt met de container. Zet hier dus géén CHECKPOINT_DB_URL neer.
            { name: 'CHECKPOINT_DB_PATH', value: '/tmp/eval-checkpoints.db' }
            // Traceerbaar in dezelfde Application Insights als de rest, maar onder een eigen naam:
            // een eval-run is geen gebruikersverkeer en moet de latency-grafieken niet vervuilen.
            { name: 'OTEL_EXPORTER_OTLP_ENDPOINT', value: collectorEndpoint }
            { name: 'OTEL_SERVICE_NAME', value: 'wetsanalyse-eval' }
            { name: 'OTEL_RESOURCE_ATTRIBUTES', value: 'deployment.environment=${appName}' }
            // BEWUST NIET GEZET, en dat is een veiligheidsmaatregel, geen vergetelheid:
            //
            // WETSANALYSE_API_URL/_TOKEN – zonder die twee is `legt_zelf_vast` false en schrijft de
            // agent niets weg. Zou de job ze wél dragen, dan landt elke eval-run als annotatie-
            // document in de werkvoorraad van een jurist. Een meting mag de gemeten toestand niet
            // veranderen.
            //
            // CHECKPOINT_DB_URL – die wijst naar de gedeelde Postgres waar de gesprekken van de
            // juristen in staan; eval-gesprekken horen daar niet tussen. Let op: weglaten geeft
            // GEEN in-memory checkpointer (dat dacht ik eerst) maar de SQLite-terugval — vandaar
            // de expliciete CHECKPOINT_DB_PATH hierboven.
          ]
        }
      ]
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 7. Frontend Container App (publiek HTTPS)
// ─────────────────────────────────────────────────────────────────────────────
// Interne API-/graph-qa-FQDN uit de resource (bevat `.internal.`); de externe frontend-URL mág met
// de hand (extern = `<app>.<defaultDomain>`) – een `.ingress.fqdn`-referentie zou hier een cycle
// geven omdat frontendPublicUrl binnen frontendApp zelf als AUTH_URL wordt gebruikt.
var apiInternalUrl = 'https://${apiApp.properties.configuration.ingress.fqdn}'
var graphQaInternalUrl = 'https://${graphQaApp.properties.configuration.ingress.fqdn}'
var frontendPublicUrl = 'https://${appName}-frontend.${cae.properties.defaultDomain}'

resource frontendApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${appName}-frontend'
  location: location
  tags: straatTags
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      // Bewaar een handvol inactieve revisies, anders is `rollback.yml` een knop zonder inhoud:
      // in de single-revision-modus (de default) deactiveert Azure de oude revisie bij elke
      // image-swap en ruimt hem daarna op. Gemeten op 27 aug 2026: alle drie de apps hadden nog
      // precies één revisie, terwijl de nummering (41/57/75) tientallen voorgangers verried.
      // Inactieve revisies draaien niet en kosten dus geen replicas.
      maxInactiveRevisions: 5
      ingress: {
        external: true
        targetPort: 3000
        transport: 'auto'
        allowInsecure: false
      }
      secrets: [
        { name: 'api-token', value: frontendApiToken }
        { name: 'admin-api-token', value: frontendAdminToken }
        { name: 'auth-secret', value: authSecret }
        { name: 'graph-qa-token', value: qaApiToken }
      ]
    }
    template: {
      volumes: [
        {
          name: 'frontend-secrets'
          storageType: 'Secret'
          secrets: [
            { secretRef: 'api-token', path: 'frontend_api_token' }
            { secretRef: 'admin-api-token', path: 'frontend_admin_token' }
            { secretRef: 'auth-secret', path: 'frontend_auth_secret' }
            { secretRef: 'graph-qa-token', path: 'frontend_graph_qa_token' }
          ]
        }
      ]
      containers: [
        {
          name: 'frontend'
          image: frontendImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          volumeMounts: [
            {
              volumeName: 'frontend-secrets'
              mountPath: '/run/secrets'
            }
          ]
          env: [
            // Telemetrie naar de collector in deze omgeving, die het doorschrijft naar Application
            // Insights. Leeg laten = uit; dat was de stand tot nu toe.
            { name: 'OTEL_EXPORTER_OTLP_ENDPOINT', value: collectorEndpoint }
            { name: 'OTEL_SERVICE_NAME', value: 'wetsanalyse-frontend' }
            // Next.js instrumenteert `fetch` zélf en maakt daar een span voor, maar injecteert geen
            // W3C-traceparent. Daardoor begon elke aanroep naar de api een NIEUWE trace: gemeten op
            // acceptatie kwamen de twee /health-calls op precies dezelfde milliseconde aan als de
            // frontend-spans, maar met `ParentId == OperationId` – allemaal roots.
            //
            // Deze vlag zet die eigen instrumentatie uit (de Next.js-documentatie noemt hem
            // expliciet "when you want to use a custom fetch instrumentation library"), waarna de
            // undici-instrumentatie van @vercel/otel het overneemt – en díe injecteert de header wel.
            { name: 'NEXT_OTEL_FETCH_DISABLED', value: '1' }
            // De straat staat op elke span, zodat acceptatie en productie in dezelfde workspace
            // uit elkaar te houden zijn.
            { name: 'OTEL_RESOURCE_ATTRIBUTES', value: 'deployment.environment=${appName}' }
            { name: 'NODE_ENV', value: 'production' }
            { name: 'API_BASE_URL', value: apiInternalUrl }
            { name: 'GRAPH_QA_URL', value: graphQaInternalUrl }
            { name: 'AUTH_URL', value: frontendPublicUrl }
            { name: 'AUTH_TRUST_HOST', value: 'true' }
            { name: 'HOME', value: '/tmp' }
            { name: 'API_TOKEN_FILE', value: '/run/secrets/frontend_api_token' }
            { name: 'ADMIN_API_TOKEN_FILE', value: '/run/secrets/frontend_admin_token' }
            { name: 'AUTH_SECRET_FILE', value: '/run/secrets/frontend_auth_secret' }
            { name: 'GRAPH_QA_TOKEN_FILE', value: '/run/secrets/frontend_graph_qa_token' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/api/health', port: 3000 }
              initialDelaySeconds: 15
              periodSeconds: 30
              timeoutSeconds: 5
              failureThreshold: 3
            }
            // Zelfde reden als bij graph-qa, al is het risico hier klein: deze app staat op
            // minReplicas 1 en is dus zelden koud. Meegenomen zodat alle drie de apps hetzelfde
            // patroon volgen – liveness zegt "leeft nog", readiness "stuur maar verkeer".
            {
              type: 'Readiness'
              httpGet: { path: '/api/health', port: 3000 }
              initialDelaySeconds: 5
              periodSeconds: 5
              timeoutSeconds: 5
              failureThreshold: 6
            }
          ]
        }
      ]
      // Niet naar nul: Auth.js-sessies verdragen een cold start slecht (de eerste request na het
      // opschalen kan seconden duren en de login-redirect timeout't dan).
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────
output frontendUrl string = 'https://${frontendApp.properties.configuration.ingress.fqdn}'
output apiInternalFqdn string = apiApp.properties.configuration.ingress.fqdn
output graphQaInternalFqdn string = graphQaApp.properties.configuration.ingress.fqdn
output graphdbInternalFqdn string = graphdbApp.properties.configuration.ingress.fqdn
// Leeg als de proxy niet is uitgerold. Met de hand opgebouwd in plaats van via `.ingress.fqdn`,
// want een resource achter een `if` mag je niet onvoorwaardelijk uitlezen.
output graphdbProxyUrl string = graphdbProxyAan ? 'https://${appName}-graphdb-proxy.${cae.properties.defaultDomain}' : ''
output importJobName string = bwbImportJob.name
output dbServerFqdn string = pgServer.properties.fullyQualifiedDomainName
