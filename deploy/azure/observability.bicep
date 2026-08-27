// deploy/azure/observability.bicep
// Module: self-hosted observability in de bestaande CAE.
// NIET aanroepen via main.bicep zonder review — zie README-azure.md §1.
//
// Inline in main.bicep:
//   module obs 'observability.bicep' = {
//     name: 'observability'
//     params: {
//       caeName: cae.name
//       caeDefaultDomain: cae.properties.defaultDomain
//       storageAccountName: '<globally-unique, max 24 chars>'
//       grafanaEntraClientId: '<app-registration client id>'
//       grafanaTenantId: tenant().tenantId
//       grafanaEntraClientSecret: '<secret>'
//       grafanaAdminPassword: '<password>'
//     }
//   }

@description('Azure-regio; erft van de resource group.')
param location string = resourceGroup().location

@description('app-prefix; moet overeenkomen met main.bicep.')
param appName string = 'wetsanalyse'

@description('Naam van de bestaande CAE (uit main.bicep).')
param caeName string = 'cae-${appName}'

// TODO(bevestig): storage account naam moet globaal uniek zijn (max 24 lowercase alphanum).
// Suggestie: gebruik 'obs' + short project-id + uniqueString(resourceGroup().id).
@description('Naam van het te maken Storage Account.')
param storageAccountName string = take('obs${appName}${uniqueString(resourceGroup().id)}', 24)

// ── Grafana Entra ID OIDC ─────────────────────────────────────────────────────
@description('Azure AD App Registration client ID voor Grafana SSO. Leeg = Entra-auth uitgeschakeld.')
param grafanaEntraClientId string = ''

@description('Azure AD Tenant ID. Leeg = Entra-auth uitgeschakeld.')
param grafanaTenantId string = ''

@secure()
@description('Azure AD App Registration client secret voor Grafana SSO. Leeg = Entra-auth uitgeschakeld.')
param grafanaEntraClientSecret string = ''

@secure()
@description('Grafana admin-wachtwoord (initieel; daarna via UI te wijzigen).')
param grafanaAdminPassword string

// TODO(bevestig): image-versie afstemmen op wat in docker-compose.yml staat bij deploy-moment.
param grafanaImageTag string = '11.4.0'

// ─────────────────────────────────────────────────────────────────────────────
// Entra-auth conditioneel: alleen als álle drie params een niet-lege waarde hebben.
// ─────────────────────────────────────────────────────────────────────────────
var enableEntraAuth = !empty(grafanaEntraClientId) && !empty(grafanaEntraClientSecret) && !empty(grafanaTenantId)

// ─────────────────────────────────────────────────────────────────────────────
// Built-in role: Storage Blob Data Contributor
// ─────────────────────────────────────────────────────────────────────────────
var blobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

// ─────────────────────────────────────────────────────────────────────────────
// Bestaande CAE (niet aanmaken — die staat al in main.bicep)
// ─────────────────────────────────────────────────────────────────────────────
resource cae 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: caeName
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. Storage Account
// ─────────────────────────────────────────────────────────────────────────────
resource sa 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    accessTier: 'Hot'
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

resource blobSvc 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: sa
  name: 'default'
}

resource lokiChunks 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobSvc
  name: 'loki-chunks'
}

resource lokiRuler 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobSvc
  name: 'loki-ruler'
}

resource tempoTraces 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobSvc
  name: 'tempo-traces'
}

resource fileSvc 'Microsoft.Storage/storageAccounts/fileServices@2023-01-01' = {
  parent: sa
  name: 'default'
}

resource sharePrometheus 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = {
  parent: fileSvc
  name: 'prometheus-tsdb'
  properties: { shareQuota: 32 }
}

resource shareGrafana 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = {
  parent: fileSvc
  name: 'grafana-data'
  properties: { shareQuota: 10 }
}

resource shareLokiWal 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = {
  parent: fileSvc
  name: 'loki-wal'
  properties: { shareQuota: 16 }
}

resource shareTempoWal 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = {
  parent: fileSvc
  name: 'tempo-wal'
  properties: { shareQuota: 16 }
}

// Config-bestanden (otel-collector-config.azure.yaml, loki-config.azure.yaml, etc.)
// — upload handmatig of via CI vóór eerste deploy; zie README-azure.md §1.
resource shareConfigs 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = {
  parent: fileSvc
  name: 'obs-configs'
  properties: { shareQuota: 1 }
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. CAE-storagekoppelingen (Azure Files; gebruikt account key — TODO(bevestig):
//    switch naar NFS 4.1 + Premium Storage voor managed-identity mount)
// ─────────────────────────────────────────────────────────────────────────────
resource caeStorePrometheus 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: cae
  name: 'prometheus-tsdb'
  properties: {
    azureFile: {
      accountName: sa.name
      accountKey: sa.listKeys().keys[0].value
      shareName: 'prometheus-tsdb'
      accessMode: 'ReadWrite'
    }
  }
}

resource caeStoreGrafana 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: cae
  name: 'grafana-data'
  properties: {
    azureFile: {
      accountName: sa.name
      accountKey: sa.listKeys().keys[0].value
      shareName: 'grafana-data'
      accessMode: 'ReadWrite'
    }
  }
}

resource caeStoreLokiWal 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: cae
  name: 'loki-wal'
  properties: {
    azureFile: {
      accountName: sa.name
      accountKey: sa.listKeys().keys[0].value
      shareName: 'loki-wal'
      accessMode: 'ReadWrite'
    }
  }
}

resource caeStoreTempoWal 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: cae
  name: 'tempo-wal'
  properties: {
    azureFile: {
      accountName: sa.name
      accountKey: sa.listKeys().keys[0].value
      shareName: 'tempo-wal'
      accessMode: 'ReadWrite'
    }
  }
}

resource caeStoreConfigs 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: cae
  name: 'obs-configs'
  properties: {
    azureFile: {
      accountName: sa.name
      accountKey: sa.listKeys().keys[0].value
      shareName: 'obs-configs'
      accessMode: 'ReadOnly'
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Interne FQDN's (pattern: <app>.internal.<defaultDomain>)
// ─────────────────────────────────────────────────────────────────────────────
var collectorFqdn  = '${appName}-obs-collector.internal.${cae.properties.defaultDomain}'
var tempoFqdn      = '${appName}-obs-tempo.internal.${cae.properties.defaultDomain}'
var lokiFqdn       = '${appName}-obs-loki.internal.${cae.properties.defaultDomain}'
var promFqdn       = '${appName}-obs-prometheus.internal.${cae.properties.defaultDomain}'
var grafanaPublicFqdn = '${appName}-obs-grafana.${cae.properties.defaultDomain}'

// ─────────────────────────────────────────────────────────────────────────────
// 3. OTel Collector (internal)
// ─────────────────────────────────────────────────────────────────────────────
// TODO(bevestig): additionalPortMappings is preview-feature; verifieer beschikbaarheid
// in 2024-03-01 of gebruik 2024-10-02-preview voor 4317 (gRPC) en 8889 (Prometheus scrape).
resource collectorApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${appName}-obs-collector'
  location: location
  dependsOn: [caeStoreConfigs]
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      ingress: {
        external: false
        targetPort: 4318
        transport: 'http'
        additionalPortMappings: [
          { targetPort: 4317, external: false }
          { targetPort: 8889, external: false }
        ]
      }
    }
    template: {
      volumes: [
        { name: 'configs', storageType: 'AzureFile', storageName: 'obs-configs' }
      ]
      containers: [
        {
          name: 'otel-collector'
          image: 'otel/opentelemetry-collector-contrib:0.119.0'
          command: ['--config=/etc/otelcol-contrib/otel-collector-config.azure.yaml']
          resources: { cpu: json('0.5'), memory: '1Gi' }
          volumeMounts: [
            { volumeName: 'configs', mountPath: '/etc/otelcol-contrib' }
          ]
          env: [
            // OTel-collector ondersteunt ${ENV} substitutie in zijn config YAML.
            { name: 'TEMPO_INTERNAL_FQDN', value: tempoFqdn }
            { name: 'LOKI_INTERNAL_FQDN',  value: lokiFqdn }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. Prometheus (internal, Azure Files TSDB)
// ─────────────────────────────────────────────────────────────────────────────
resource prometheusApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${appName}-obs-prometheus'
  location: location
  dependsOn: [caeStorePrometheus, caeStoreConfigs, collectorApp]
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      ingress: {
        external: false
        targetPort: 9090
        transport: 'http'
      }
    }
    template: {
      volumes: [
        { name: 'tsdb',    storageType: 'AzureFile', storageName: 'prometheus-tsdb' }
        { name: 'configs', storageType: 'AzureFile', storageName: 'obs-configs' }
      ]
      containers: [
        {
          name: 'prometheus'
          image: 'prom/prometheus:v3.13.1'
          command: [
            '--config.file=/etc/prometheus/prometheus.azure.yml'
            '--storage.tsdb.path=/prometheus'
            '--storage.tsdb.retention.time=15d'
          ]
          resources: { cpu: json('0.5'), memory: '1Gi' }
          volumeMounts: [
            { volumeName: 'tsdb',    mountPath: '/prometheus' }
            { volumeName: 'configs', mountPath: '/etc/prometheus' }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. Loki (internal, system-assigned identity → Blob Data Contributor)
// ─────────────────────────────────────────────────────────────────────────────
resource lokiApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${appName}-obs-loki'
  location: location
  identity: { type: 'SystemAssigned' }
  dependsOn: [caeStoreLokiWal, caeStoreConfigs, lokiChunks, lokiRuler]
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      ingress: {
        external: false
        targetPort: 3100
        transport: 'http'
      }
    }
    template: {
      volumes: [
        { name: 'wal',     storageType: 'AzureFile', storageName: 'loki-wal' }
        { name: 'configs', storageType: 'AzureFile', storageName: 'obs-configs' }
      ]
      containers: [
        {
          name: 'loki'
          image: 'grafana/loki:3.4.2'
          command: ['-config.file=/etc/loki/loki-config.azure.yaml']
          resources: { cpu: json('0.5'), memory: '1Gi' }
          volumeMounts: [
            { volumeName: 'wal',     mountPath: '/loki' }
            { volumeName: 'configs', mountPath: '/etc/loki' }
          ]
          env: [
            { name: 'STORAGE_ACCOUNT_NAME', value: sa.name }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
}

resource lokiBlobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(sa.id, lokiApp.name, blobDataContributorRoleId)
  scope: sa
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDataContributorRoleId)
    principalId: lokiApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 6. Tempo (internal, system-assigned identity → Blob Data Contributor)
// ─────────────────────────────────────────────────────────────────────────────
resource tempoApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${appName}-obs-tempo'
  location: location
  identity: { type: 'SystemAssigned' }
  dependsOn: [caeStoreTempoWal, caeStoreConfigs, tempoTraces]
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      ingress: {
        external: false
        targetPort: 3200
        transport: 'http'
        additionalPortMappings: [
          { targetPort: 4317, external: false }
          { targetPort: 4318, external: false }
        ]
      }
    }
    template: {
      volumes: [
        { name: 'wal',     storageType: 'AzureFile', storageName: 'tempo-wal' }
        { name: 'configs', storageType: 'AzureFile', storageName: 'obs-configs' }
      ]
      containers: [
        {
          name: 'tempo'
          image: 'grafana/tempo:2.7.1'
          command: ['-config.file=/etc/tempo/tempo-config.azure.yaml']
          resources: { cpu: json('0.5'), memory: '1Gi' }
          volumeMounts: [
            { volumeName: 'wal',     mountPath: '/var/tempo/wal' }
            { volumeName: 'configs', mountPath: '/etc/tempo' }
          ]
          env: [
            { name: 'STORAGE_ACCOUNT_NAME', value: sa.name }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
}

resource tempoBlobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(sa.id, tempoApp.name, blobDataContributorRoleId)
  scope: sa
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDataContributorRoleId)
    principalId: tempoApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 7. Grafana (external ingress, Entra ID auth)
// ─────────────────────────────────────────────────────────────────────────────
resource grafanaApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${appName}-obs-grafana'
  location: location
  dependsOn: [caeStoreGrafana, lokiApp, tempoApp, prometheusApp]
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      ingress: {
        external: true
        targetPort: 3000
        transport: 'auto'
        allowInsecure: false
      }
      secrets: concat([
        { name: 'grafana-admin-pw', value: grafanaAdminPassword }
      ], enableEntraAuth ? [
        { name: 'grafana-entra-secret', value: grafanaEntraClientSecret }
      ] : [])
    }
    template: {
      volumes: [
        { name: 'grafana-data', storageType: 'AzureFile', storageName: 'grafana-data' }
      ]
      containers: [
        {
          name: 'grafana'
          image: 'grafana/grafana:${grafanaImageTag}'
          resources: { cpu: json('0.5'), memory: '1Gi' }
          volumeMounts: [
            { volumeName: 'grafana-data', mountPath: '/var/lib/grafana' }
          ]
          env: concat([
            { name: 'GF_SERVER_ROOT_URL',            value: 'https://${grafanaPublicFqdn}' }
            { name: 'GF_SECURITY_ADMIN_PASSWORD',    secretRef: 'grafana-admin-pw' }
            // Expliciet 'false' als Entra-params ontbreken, 'true' als ze allemaal gezet zijn.
            { name: 'GF_AUTH_AZUREAD_ENABLED',       value: string(enableEntraAuth) }
            // Datasource-URL's voor provision-grafana.sh
            { name: 'GF_DATASOURCES_PROMETHEUS_URL', value: 'http://${promFqdn}' }
            { name: 'GF_DATASOURCES_LOKI_URL',       value: 'http://${lokiFqdn}:3100' }
            { name: 'GF_DATASOURCES_TEMPO_URL',      value: 'http://${tempoFqdn}:3200' }
          ], enableEntraAuth ? [
            { name: 'GF_AUTH_AZUREAD_CLIENT_ID',     value: grafanaEntraClientId }
            { name: 'GF_AUTH_AZUREAD_CLIENT_SECRET', secretRef: 'grafana-entra-secret' }
            { name: 'GF_AUTH_AZUREAD_TENANT_ID',     value: grafanaTenantId }
            { name: 'GF_AUTH_AZUREAD_AUTH_URL',      value: 'https://login.microsoftonline.com/${grafanaTenantId}/oauth2/v2.0/authorize' }
            { name: 'GF_AUTH_AZUREAD_TOKEN_URL',     value: 'https://login.microsoftonline.com/${grafanaTenantId}/oauth2/v2.0/token' }
            { name: 'GF_AUTH_AZUREAD_SCOPES',        value: 'openid email profile' }
            // TODO(bevestig): overweeg GF_AUTH_DISABLE_LOGIN_FORM=true pas nadat Entra ID getest is.
            { name: 'GF_AUTH_AZUREAD_ALLOW_SIGN_UP', value: 'true' }
          ] : [])
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/api/health', port: 3000 }
              initialDelaySeconds: 15
              periodSeconds: 30
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────
@description('Interne OTLP HTTP-URL voor de app-containers (OTEL_EXPORTER_OTLP_ENDPOINT).')
output collectorOtlpHttpUrl string = 'http://${collectorFqdn}:4318'

@description('Publieke Grafana-URL.')
output grafanaUrl string = 'https://${grafanaPublicFqdn}'

@description('Storage account naam (nodig voor config-upload).')
output storageAccountName string = sa.name
