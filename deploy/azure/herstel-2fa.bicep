// De eenmalige job van `azure-infra` → actie `2fa-herstel`: de 2FA van de enige beheerder wissen, als die
// authenticator én herstelcodes kwijt is (deploy/azure/README.md §*2FA voor beheerders*).
//
// Waarom een job in de straat en niet een query vanaf de runner: de job draait in de container-apps-omgeving,
// dus langs dezelfde weg naar PostgreSQL als de api, zonder een firewallregel voor een runner. Hij voert
// `python -m app.herstel_2fa` uit, met het api-image dat nu draait: het effect is `users.reset_2fa`, en
// de weigeringen (een andere beheerder met 2FA, geen beheerder, …) staan in die module en haar tests.
//
// Waarom een aparte template en niet een job in main.bicep: hij hoort er alleen te zijn zolang de actie
// loopt, want hij draagt de verbindingsstring van de database. De workflow verwijdert hem daarna, en
// `opruimen` ruimt een achtergebleven exemplaar op (hij staat bewust niet op de lijst `hoort_erbij`).
// `az containerapp job create` kan een secret niet als bestand mounten; deze template wel, zoals bij de
// andere jobs (*_FILE).

@description('De straat: de job landt in cae-<appName>.')
param appName string

param location string = resourceGroup().location

@description('Het image dat de api-app van deze straat nu draait (met digest).')
param apiImage string

@secure()
@description('De database-url van de api-app, letterlijk overgenomen.')
param databaseUrl string

@description('Het account waarvan de 2FA weg moet.')
param herstelUserid string

@description('Wie het doet, voor het security-log: github:<login>.')
param herstelDoor string

resource cae 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: 'cae-${appName}'
}

resource herstelJob 'Microsoft.App/jobs@2024-03-01' = {
  name: '${appName}-2fa-herstel'
  location: location
  tags: {
    straat: appName
  }
  properties: {
    environmentId: cae.id
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 300
      replicaRetryLimit: 0   // een reset herhalen is nooit de bedoeling
      manualTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
      }
      secrets: [
        { name: 'database-url', value: databaseUrl }
      ]
    }
    template: {
      volumes: [
        {
          name: 'herstel-secrets'
          storageType: 'Secret'
          secrets: [
            { secretRef: 'database-url', path: 'database_url' }
          ]
        }
      ]
      containers: [
        {
          name: 'herstel-2fa'
          image: apiImage
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          volumeMounts: [
            { volumeName: 'herstel-secrets', mountPath: '/run/secrets' }
          ]
          command: ['python', '-u', '-m', 'app.herstel_2fa']
          env: [
            { name: 'DATABASE_URL_FILE', value: '/run/secrets/database_url' }
            { name: 'HERSTEL_USERID', value: herstelUserid }
            { name: 'HERSTEL_DOOR', value: herstelDoor }
          ]
        }
      ]
    }
  }
}

output jobNaam string = herstelJob.name
