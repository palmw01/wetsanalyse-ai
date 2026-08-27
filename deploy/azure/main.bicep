// deploy/azure/main.bicep
// Azure Container Apps-stack voor Wetsanalyse — een ZELFSTANDIGE omgeving:
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

@description('Hoeveel dagen back-ups van PostgreSQL bewaard blijven. Acceptatie heeft genoeg aan een week; voor productie is dit het enige vangnet onder de annotaties, en die zijn — anders dan de graaf — niet te reproduceren.')
@minValue(7)
@maxValue(35)
param backupRetentionDays int = 7

@description('Ondergrens voor api en graph-qa. 0 laat ze naar nul schalen (goedkoop, maar de eerste aanroep na een stille periode wacht op een koude start); 1 houdt ze warm. Acceptatie 0, productie 1.')
@minValue(0)
@maxValue(3)
param minReplicasApps int = 0

@description('Java-heap voor GraphDB. Moet passen binnen het geheugen van de container-app.')
param graphdbHeap string = '2g'

@secure()
@description('GraphDB-licentie, base64-gecodeerd (`base64 -w0 graphdb.license`). VERPLICHT voor een bruikbare graaf: GraphDB 11 laat zonder licentie alleen LEZEN toe, dus de import-job faalt met een 500 op het eerste schrijf-verzoek. Leeg laten kan — de omgeving komt dan op met een lege, read-only graaf.')
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
@description('Bearer-token dat de frontend gebruikt om graph-qa aan te roepen (= graph-qa QA_API_TOKEN).')
param qaApiToken string

@secure()
@description('Bearer-token waarmee graph-qa naar de wetsanalyse-API schrijft. Eigen client in `apiTokens`, zodat het auditspoor laat zien wie er schreef.')
param graphQaApiToken string

// ── Observability (optioneel) ─────────────────────────────────────────────────
@description('Schakel de self-hosted observability-stack in (OTel Collector, Prometheus, Loki, Tempo, Grafana). Default false — bestaande deploys worden niet geraakt.')
param enableObservability bool = false

@description('Grafana Entra ID App Registration client ID. Vereist als enableObservability = true.')
param grafanaEntraClientId string = ''

@description('Azure AD Tenant ID voor Grafana OIDC. Leeg = Entra-auth uitgeschakeld.')
param grafanaTenantId string = ''

@secure()
@description('Grafana Entra ID client secret. Vereist als enableObservability = true.')
param grafanaEntraClientSecret string = ''

@secure()
@description('Grafana admin-wachtwoord (initieel). Vereist als enableObservability = true.')
param grafanaAdminPassword string = ''

// ─────────────────────────────────────────────────────────────────────────────
// 1. PostgreSQL Flexible Server
// ─────────────────────────────────────────────────────────────────────────────
// Draagt zowel de api-tabellen als de LangGraph-checkpointer van graph-qa (aparte tabellen, geen
// botsing). Burstable B1ms is de goedkoopste tier die volstaat; de server kan niet naar nul schalen
// — stop hem als de omgeving een tijd niet gebruikt wordt (zie README).
// Acceptatie en productie delen één resource group — de service principal mag er geen tweede
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
// containers NIET — en dat is precies waar api, frontend en graph-qa hun gestructureerde JSON-logs
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
// metrics in ÉÉN workspace en zijn ze samen te bevragen — een request in `requests` is te koppelen
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
// Observability-module (optioneel — alleen als enableObservability = true)
// ─────────────────────────────────────────────────────────────────────────────
module observability './observability.bicep' = if (enableObservability) {
  name: 'observability'
  params: {
    location: location
    appName: appName
    caeName: cae.name
    grafanaEntraClientId: grafanaEntraClientId
    grafanaTenantId: grafanaTenantId
    grafanaEntraClientSecret: grafanaEntraClientSecret
    grafanaAdminPassword: grafanaAdminPassword
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 2b. OTel-collector — de brug naar Application Insights
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
          // een omgevingsvariabele met `--config=env:` — geen tussenbestand, en geen shell nodig:
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
// 3. GraphDB — de kennisgraaf (intern)
// ─────────────────────────────────────────────────────────────────────────────
// GEEN persistente opslag, en dat is een bewuste keuze. GraphDB's opslaglaag gebruikt
// geheugen-gemapte bestanden en file-locking; op Azure Files levert dat hetzelfde risico als op een
// NFS-share (traagheid, in het slechtste geval stille indexcorruptie) — precies waarom de graaf op
// de zelfgehoste opzet lokale opslag heeft. Een managed disk lost dat op maar kan niet aan een container-app.
//
// Dat kan hier, omdat de graaf volledig REPRODUCEERBAAR is: de import-job haalt alle regelingen
// rechtstreeks bij overheid.nl (~20s). Herstart betekent dus opnieuw importeren, niet dataverlies.
//
// Twee gevolgen om te kennen:
//   • `minReplicas: 1` — schaalt bewust NIET naar nul, want dan is de graaf bij de volgende request
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
// 4. BWB-import — vult de graaf (handmatige job)
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
    // (named-graph PUT), dus dit is veilig — en het is wat de graaf bijhoudt zonder dat er een
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
// 5. API Container App (intern)
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
      ingress: {
        external: false
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
// 6. graph-qa Container App (intern) — de agent op de kennisgraaf
// ─────────────────────────────────────────────────────────────────────────────
// Praat met de GraphDB uit deze stack, via de MCP-server die GraphDB >= 11.2 zelf meebrengt op /mcp.
//
// LET OP — geen auth-proxy zoals in de zelfgehoste opzet. Daar controleert een nginx het bearer-token en vervangt
// het door het GraphDB-service-account; hier is de graaf alleen binnen de Container Apps
// Environment bereikbaar (`external: false`) en dat is de grens. `GRAPHDB_TOKEN` blijft gezet omdat
// de code het fail-closed eist (`require_graph`), maar het is hier GEEN slot — GraphDB draait
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
            // annotatiebeurt NIET vast — de werkplek toont dan netjes markeringen die nergens
            // landen. Dat was tussen 19 aug (commit 98eef5a, één schrijfpad) en 27 aug 2026 het
            // geval op Azure: die commit richtte dev in maar raakte deze bicep niet.
            { name: 'WETSANALYSE_API_URL', value: apiInternalUrl }
            { name: 'WETSANALYSE_API_TOKEN_FILE', value: '/run/secrets/wetsanalyse_api_token' }
            { name: 'SIMILARITY_INDEX', value: 'bwb_similarity' }
            // Uit: dan draait de pure agentische lus. Met decompositie ligt er een vast recept
            // overheen waarin solve_node een eigen agent-lus nabouwt — een tweede implementatie
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
// 7. Frontend Container App (publiek HTTPS)
// ─────────────────────────────────────────────────────────────────────────────
// Interne API-/graph-qa-FQDN uit de resource (bevat `.internal.`); de externe frontend-URL mág met
// de hand (extern = `<app>.<defaultDomain>`) — een `.ingress.fqdn`-referentie zou hier een cycle
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
            // frontend-spans, maar met `ParentId == OperationId` — allemaal roots.
            //
            // Deze vlag zet die eigen instrumentatie uit (de Next.js-documentatie noemt hem
            // expliciet "when you want to use a custom fetch instrumentation library"), waarna de
            // undici-instrumentatie van @vercel/otel het overneemt — en díe injecteert de header wel.
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
output importJobName string = bwbImportJob.name
output dbServerFqdn string = pgServer.properties.fullyQualifiedDomainName

// Observability-outputs (leeg als enableObservability = false)
output observabilityStorageAccount string = enableObservability ? observability.outputs.storageAccountName : ''
output grafanaUrl                  string = enableObservability ? observability.outputs.grafanaUrl : ''
