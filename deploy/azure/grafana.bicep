// Grafana voor de Azure-straten — één plek waar acceptatie én productie te zien zijn.
//
// Waarom dit een APARTE template is en niet een resource in main.bicep: Grafana hoort bij geen van
// beide straten, en een dashboardwijziging mag geen volle infra-deploy vragen. `main.bicep` raakt
// GraphDB, en die is niet-persistent — dat is precies waarom `wat-if` daar de default is. Deze
// template raakt één container app en verder niets.
//
// Waarom geen Azure Managed Grafana: dat vereist een managed identity plus een role assignment op
// de resource group, en de service principal mag geen role assignments maken. Zelfde reden waarom
// hier de SP-credentials meegaan als datasource-auth in plaats van een identiteit.
//
// Waarom geen persistente opslag: alles wat dit ding weet, staat in deze repo — datasources en
// dashboards komen als file-provisioning mee en zijn in de UI dus read-only. Een herstart brengt ze
// ongewijzigd terug. Wat je wél verliest is handwerk in de UI: zelfgemaakte dashboards, extra
// gebruikers, opgeslagen voorkeuren. Dat is een bewuste ruil (geen storage account, geen mount, geen
// staat om te back-uppen) en dezelfde als op de docker-host. Wil je een paneel bewaren, zet het dan
// in `grafana/dashboard-keten.json` — niet in de UI.

@description('Waar Grafana landt: de container-apps-omgeving van deze straat (cae-<appName>).')
param appName string

@description('De acceptatiestraat, voor de eerste datasource. Leeg = geen datasource.')
param acceptatieAppName string = 'wetsanalyse'

@description('De productiestraat, voor de tweede datasource. Leeg = geen datasource.')
param productieAppName string = 'wetsanalyse-prd'

param location string = resourceGroup().location

param grafanaImage string = 'grafana/grafana:12.0.2'

@description('Service principal die de Log Analytics-workspaces mag lezen.')
param azureTenantId string
param azureClientId string
param azureSubscriptionId string

@secure()
param azureClientSecret string

@secure()
param grafanaAdminPassword string

var straatTags = {
  straat: appName
  onderdeel: 'observability'
}

// De omgeving bestaat al — deze template maakt geen straat aan.
resource cae 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: 'cae-${appName}'
}

// Bewust `resourceId()` en geen `existing`-lookup: een straat die (nog) niet bestaat hoort deze
// deploy niet te laten falen. De datasource wijst dan naar iets wat er niet is en geeft een
// leesbare fout in Grafana zelf — beter dan een deploy die halverwege afbreekt.
var wsAcc = resourceId('Microsoft.OperationalInsights/workspaces', 'log-${acceptatieAppName}')
var wsPrd = resourceId('Microsoft.OperationalInsights/workspaces', 'log-${productieAppName}')

var heeftAcc = !empty(acceptatieAppName)
var heeftPrd = !empty(productieAppName)

// ─────────────────────────────────────────────────────────────────────────────
// Provisioning: datasources
// ─────────────────────────────────────────────────────────────────────────────
var dsAcc = '''
  - name: Acceptatie
    uid: azmon-acceptatie
    type: grafana-azure-monitor-datasource
    isDefault: true
    jsonData:
      azureAuthType: clientsecret
      cloudName: azuremonitor
      tenantId: $AZ_TENANT_ID
      clientId: $AZ_CLIENT_ID
      subscriptionId: $AZ_SUBSCRIPTION_ID
      logAnalyticsDefaultWorkspace: __WS_ACC__
    secureJsonData:
      clientSecret: $AZ_CLIENT_SECRET
'''

var dsPrd = '''
  - name: Productie
    uid: azmon-productie
    type: grafana-azure-monitor-datasource
    jsonData:
      azureAuthType: clientsecret
      cloudName: azuremonitor
      tenantId: $AZ_TENANT_ID
      clientId: $AZ_CLIENT_ID
      subscriptionId: $AZ_SUBSCRIPTION_ID
      logAnalyticsDefaultWorkspace: __WS_PRD__
    secureJsonData:
      clientSecret: $AZ_CLIENT_SECRET
'''

// De service-principal-waarden staan als `$AZ_*` in de YAML en worden door GRAFANA zelf ingevuld
// uit de omgeving — geverifieerd, ook voor `secureJsonData` en voor een secret met tekens als & | #.
// Daarmee komt het geheim nooit in een bicep-expressie of in het deployment-record terecht; alleen
// de container-app-secret draagt hem. Dat scheelt precies de linter-waarschuwing die je krijgt als
// je een @secure() param door replace() haalt — en die waarschuwing had gelijk.
var datasourcesYaml = replace(replace(replace(
  'apiVersion: 1\ndatasources:\n__ACC____PRD__',
  '__ACC__', heeftAcc ? dsAcc : ''),
  '__PRD__', heeftPrd ? dsPrd : ''),
  '__WS_ACC__', wsAcc)

var datasourcesMetWorkspaces = replace(datasourcesYaml, '__WS_PRD__', wsPrd)

// ─────────────────────────────────────────────────────────────────────────────
// Provisioning: dashboards
// ─────────────────────────────────────────────────────────────────────────────
// Eén sjabloon, per straat ingevuld. Zo staat er in de repo één dashboard om te onderhouden, maar
// ziet de gebruiker er twee — één per straat, elk met zijn eigen workspace en datasource. Een
// datasource-variabele zou dat ook doen, maar dan moet de workspace-id per query alsnog meebewegen.
var sjabloon = loadTextContent('grafana/dashboard-keten.json')

var dashAcc = replace(replace(replace(replace(replace(
  sjabloon, '__SLUG__', 'acceptatie'), '__STRAAT__', 'acceptatie'), '__DSUID__', 'azmon-acceptatie'), '__WORKSPACE__', wsAcc), '__APPNAME__', acceptatieAppName)

var dashPrd = replace(replace(replace(replace(replace(
  sjabloon, '__SLUG__', 'productie'), '__STRAAT__', 'productie'), '__DSUID__', 'azmon-productie'), '__WORKSPACE__', wsPrd), '__APPNAME__', productieAppName)

var dashboardProviderYaml = '''
apiVersion: 1
providers:
  - name: wetsanalyse
    orgId: 1
    folder: Wetsanalyse
    type: file
    disableDeletion: true
    allowUiUpdates: false
    options:
      path: /etc/grafana/provisioning/dashboards/wetsanalyse
'''

// Container Apps kennen geen configmounts — dezelfde beperking als bij de OTel-collector. Die loste
// het op met `--config=env:`; Grafana kan dat niet en leest alleen uit /etc/grafana/provisioning.
// Vandaar deze opstartregel: schrijf de bestanden uit env en geef het daarna over aan het echte
// entrypoint. Geverifieerd dat dit image een `/bin/sh` heeft en dat die map schrijfbaar is voor de
// grafana-gebruiker (uid 472) — bij de collector bleek dat níét zo, en dan faalt de container stil
// vóór de eerste logregel.
var opstart = 'set -e\nmkdir -p /etc/grafana/provisioning/datasources /etc/grafana/provisioning/dashboards/wetsanalyse\nprintf "%s" "$DS_YAML" > /etc/grafana/provisioning/datasources/wetsanalyse.yaml\nprintf "%s" "$DASH_PROVIDER" > /etc/grafana/provisioning/dashboards/wetsanalyse.yaml\nprintf "%s" "$DASH_ACC" > /etc/grafana/provisioning/dashboards/wetsanalyse/acceptatie.json\nprintf "%s" "$DASH_PRD" > /etc/grafana/provisioning/dashboards/wetsanalyse/productie.json\nexec /run.sh'

resource grafanaApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${appName}-grafana'
  location: location
  tags: straatTags
  properties: {
    environmentId: cae.id
    configuration: {
      ingress: {
        external: true
        targetPort: 3000
        transport: 'auto'
        allowInsecure: false
      }
      secrets: [
        // Alleen wat écht geheim is staat hier. De provisioning-YAML en de dashboards zijn
        // gewone configuratie — die als secret wegzetten maakt ze niet veiliger, alleen
        // moeilijker te inspecteren, en het geheim erin (de clientSecret) vult Grafana zelf in
        // uit `AZ_CLIENT_SECRET`.
        { name: 'admin-password', value: grafanaAdminPassword }
        { name: 'az-client-secret', value: azureClientSecret }
      ]
    }
    template: {
      containers: [
        {
          name: 'grafana'
          image: grafanaImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          command: [ '/bin/sh' ]
          args: [ '-c', opstart ]
          env: [
            { name: 'DS_YAML', value: datasourcesMetWorkspaces }
            // Grafana vult deze zelf in op de `$AZ_*`-plekken in de provisioning-YAML.
            { name: 'AZ_TENANT_ID', value: azureTenantId }
            { name: 'AZ_CLIENT_ID', value: azureClientId }
            { name: 'AZ_SUBSCRIPTION_ID', value: azureSubscriptionId }
            { name: 'AZ_CLIENT_SECRET', secretRef: 'az-client-secret' }
            { name: 'DASH_PROVIDER', value: dashboardProviderYaml }
            { name: 'DASH_ACC', value: dashAcc }
            { name: 'DASH_PRD', value: dashPrd }
            { name: 'GF_SECURITY_ADMIN_USER', value: 'admin' }
            { name: 'GF_SECURITY_ADMIN_PASSWORD', secretRef: 'admin-password' }
            // Dit ding staat aan het open internet: geen anonieme toegang, geen zelfregistratie.
            { name: 'GF_AUTH_ANONYMOUS_ENABLED', value: 'false' }
            { name: 'GF_USERS_ALLOW_SIGN_UP', value: 'false' }
            // Zonder persistente opslag heeft telemetrie-naar-Grafana-zelf geen zin, en het scheelt
            // een uitgaande verbinding vanuit een app die credentials draagt.
            { name: 'GF_ANALYTICS_REPORTING_ENABLED', value: 'false' }
            { name: 'GF_ANALYTICS_CHECK_FOR_UPDATES', value: 'false' }
          ]
        }
      ]
      scale: {
        // Naar nul mag: een dashboard dat niemand openslaat hoeft niet te draaien, en een koude
        // start kost hier alleen de eerste paginalading. Anders dan de collector, die telemetrie zou
        // missen tijdens het opkomen.
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

output grafanaUrl string = 'https://${grafanaApp.properties.configuration.ingress.fqdn}'
