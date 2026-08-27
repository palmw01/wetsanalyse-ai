# Observability — Azure Container Apps deploy

Self-hosted Prometheus / Loki / Tempo / Grafana in de bestaande CAE, naast de bestaande app-containers.
Object storage via Azure Blob (managed identity); state via Azure Files.

---

## 1. Bicep deploy-volgorde

### 1a. Voeg de module toe aan main.bicep

`main.bicep` zelf wijzig je **niet** — voeg onderaan toe:

```bicep
module obs 'observability.bicep' = {
  name: 'observability'
  params: {
    location: location
    appName: appName
    caeName: cae.name
    storageAccountName: '<globally-unique, max 24 lowercase alphanum>'  // TODO(bevestig)
    grafanaEntraClientId: '<app-registration client id>'
    grafanaTenantId: tenant().tenantId
    grafanaEntraClientSecret: '<client secret>'
    grafanaAdminPassword: '<initial admin password>'
  }
}

output collectorOtlpHttpUrl string = obs.outputs.collectorOtlpHttpUrl
output grafanaUrl            string = obs.outputs.grafanaUrl
```

### 1b. Upload de config-bestanden naar Azure Files

Doe dit **vóór** de eerste bicep-deploy (of direct daarna, vóór de containers starten):

```bash
# Haal de storage account naam op uit de bicep-output:
SA=$(az deployment group show -g <rg> -n main --query properties.outputs.storageAccountName.value -o tsv 2>/dev/null \
     || az deployment group show -g <rg> -n observability --query properties.outputs.storageAccountName.value -o tsv)

# Vervang de CAE DNS-suffix in de Prometheus-config:
CAE_SUFFIX=$(az containerapp env show -n cae-wetsanalyse -g <rg> \
             --query properties.defaultDomain -o tsv)
sed "s/\${CAE_DNS_SUFFIX}/${CAE_SUFFIX}/g" \
    deploy/observability/prometheus.azure.yml > /tmp/prometheus.azure.yml

# Upload alle configs naar de obs-configs share:
az storage file upload --account-name "$SA" --share-name obs-configs \
    --source deploy/observability/otel-collector-config.azure.yaml \
    --path otel-collector-config.azure.yaml --auth-mode login

az storage file upload --account-name "$SA" --share-name obs-configs \
    --source deploy/observability/loki-config.azure.yaml \
    --path loki-config.azure.yaml --auth-mode login

az storage file upload --account-name "$SA" --share-name obs-configs \
    --source deploy/observability/tempo-config.azure.yaml \
    --path tempo-config.azure.yaml --auth-mode login

az storage file upload --account-name "$SA" --share-name obs-configs \
    --source /tmp/prometheus.azure.yml \
    --path prometheus.azure.yml --auth-mode login
```

### 1c. Deploy

```bash
az deployment group create \
  -g <resource-group> \
  -f deploy/azure/main.bicep \
  -p @deploy/azure/params.json \
     grafanaEntraClientSecret='...' \
     grafanaAdminPassword='...'
```

Of alleen de observability-module (iteratief):

```bash
az deployment group create \
  -g <resource-group> \
  -f deploy/azure/observability.bicep \
  -p storageAccountName='...' \
     grafanaEntraClientId='...' \
     grafanaTenantId='...' \
     grafanaEntraClientSecret='...' \
     grafanaAdminPassword='...'
```

### 1d. OTEL_EXPORTER_OTLP_ENDPOINT in de app-containers

Na deploy geeft `obs.outputs.collectorOtlpHttpUrl` de interne collector-URL.
Voeg die toe aan de env van `apiApp`, `frontendApp` en `graphQaApp` in main.bicep:

```bicep
{ name: 'OTEL_EXPORTER_OTLP_ENDPOINT', value: obs.outputs.collectorOtlpHttpUrl }
```

---

## 2. provision-grafana.sh tegen de nieuwe Grafana

De bestaande `provision-grafana.sh` verwacht `GRAFANA_URL` en `GRAFANA_TOKEN`.
De datasource-uid's `wa-prometheus`, `wa-loki`, `wa-tempo` (uit `grafana-datasources.yaml`)
moeten overeenkomen met wat in de dashboards staat.

```bash
# Haal de Grafana-URL op:
GRAFANA_URL=$(az deployment group show -g <rg> -n main \
              --query "properties.outputs.grafanaUrl.value" -o tsv)

# Maak een service-account token aan in Grafana (eenmalig, via UI of API):
# Grafana UI → Administration → Service accounts → Add → Admin-rol → Add token
GRAFANA_TOKEN='<service-account-token>'

# Provision datasources + dashboards + alerting:
GRAFANA_URL="$GRAFANA_URL" GRAFANA_TOKEN="$GRAFANA_TOKEN" \
  bash deploy/observability/provision-grafana.sh

GRAFANA_URL="$GRAFANA_URL" GRAFANA_TOKEN="$GRAFANA_TOKEN" \
  bash deploy/observability/alerting/apply.sh
```

> De dashboards (`grafana-dashboard-wetsanalyse.json`, `grafana-dashboard-topologie.json`)
> verwachten datasource-uid's `wa-prometheus`, `wa-loki`, `wa-tempo`. De Postgres-datasource
> `wa-postgres` werkt niet in de CAE-variant (geen directe PG-toegang vanuit Grafana tenzij
> je een extra firewall-regel toevoegt) — TODO(bevestig).

---

## 3. Verificatie

```bash
# Alle 5 container apps draaien:
az containerapp list -g <rg> --query "[?starts_with(name,'wetsanalyse-obs')].{name:name,status:properties.runningStatus}" -o table

# Collector bereikbaar vanuit een andere app (tijdelijke exec):
az containerapp exec -n wetsanalyse-api -g <rg> \
  --command "curl -s http://wetsanalyse-obs-collector.internal.<cae-suffix>:8889/metrics | head -5"

# Loki health:
az containerapp exec -n wetsanalyse-obs-loki -g <rg> \
  --command "wget -qO- http://localhost:3100/ready"

# Tempo health:
az containerapp exec -n wetsanalyse-obs-tempo -g <rg> \
  --command "wget -qO- http://localhost:3200/ready"

# Grafana bereikbaar:
curl -s "$(az deployment group show -g <rg> -n main \
  --query properties.outputs.grafanaUrl.value -o tsv)/api/health"

# Blob containers aangemaakt:
az storage container list --account-name "$SA" --auth-mode login \
  --query "[].name" -o tsv
```

Na een testanalyse in de webapp: Grafana → Explore → Tempo → zoek op `service.name = wetsanalyse-api`.
