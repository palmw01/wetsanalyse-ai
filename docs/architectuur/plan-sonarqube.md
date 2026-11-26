# Plan: de bevindingen van SonarQube Cloud oplossen

Soort: *plan* · 26 november 2026 · prioriteit 1 (besluit gebruiker 26 nov 2026)

SonarQube Cloud analyseert de repo automatisch: organisatie `palmw01`, project `palmw01_wetsanalyse-ai`, plan OSS.
Dat gebeurt bij elke push naar master en bij elke PR. Wat broncode is, wat test is en wat erbuiten valt, staat in
`.sonarcloud.properties`. Het doel is dat **alle** bevindingen opgelost zijn, zonder dat Lex anders gaat werken. Daarna
wordt de quality gate een verplichte check in de poort.

## Nulmeting (26 nov 2026, vóór de configuratie)

397 open issues: 193 security, 197 reliability, 60 maintainability. Eén issue kan meer dan één kwaliteit raken.
Daarvan zijn 14 blockers. De grootste groepen:

| regel | aantal | wat |
|---|---|---|
| `pythonsecurity:S8707` | 83 | path injection, vooral CLI-scripts met een pad uit `argv` |
| `python:S8786`, `typescript:S8786` | 72 | regexen met niet-lineaire backtracking (ReDoS) |
| `githubactions`/`docker` S8541, S8544, S6505, S8543 | ±60 | installatie zonder gepinde hashes of met install-scripts |
| `typescript:S6848`, `Web:S6845`, S9379, S6853 | ±30 | toegankelijkheid van de werkplek |
| `azureresourcemanager:S6378`, S6382 | 16 | managed identity, clientcertificaten |

`docs/architectuur/metingen/` valt bewust buiten de analyse. Die scripts zijn bewijs en worden achteraf niet
gewijzigd.

## Fasen

Elke fase is een eigen PR, of een kleine stapel, door de volledige poort: suites, kruistests en browserregressie. De
hoofdsessie bundelt en volgt de uitrol naar acceptatie.

| fase | wat | risico voor Lex | hoe het veilig blijft |
|---|---|---|---|
| **F0** | configuratie: `.github` en `tools/graph-qa/eval` erin, metingen eruit; dit plan | geen | – |
| **F1** | blockers en echte beveiliging: XSS in de begrippenexport, script-injectie in `rollback.yml`, CORS-volgorde, invariante returns, oneindige testlus, test zonder assert | laag | per fix een test die het lek eerst aantoont |
| **F2** | supply chain: `pip`/`npm` met hashes en zonder install-scripts, in workflows en Dockerfiles | laag (raakt de images) | build, Trivy-poort en uitrolpoort op acceptatie |
| **F3** | path injection: één gedeelde padcontrole in plaats van 83 losse fixes | laag | tests op de helper en op elk script dat hem gebruikt |
| **F4** | regexen (ReDoS) in onder meer de detectoren, de verwijzingsherkenning en de citaatcontrole | **hoog** | eerst karakteriseringstests op echte wettekst, dan herschrijven; daarna de annotatie-eval en een lichte meting op acceptatie (ADR-010) |
| **F5** | UI-toegankelijkheid en kleine reliability-issues | middel (UI) | browsertests en screenshots |
| **F6** | Azure-bicep: managed identity en clientcertificaten | – | **besluit gebruiker**: accepteren met reden, of de Azure-rechten aanpassen |
| **F7** | de quality gate als verplichte check in `poort` | – | pas als de teller op nul staat |

## Regels

- **Een fix is generiek.** Eén mechanisme voor een groep, geen uitzondering per bestand.
- **Accepteren in Sonar mag alleen met reden**, vastgelegd in de PR. Het geldt alleen waar de bevinding aantoonbaar
  niet van toepassing is, bijvoorbeeld een bind op `0.0.0.0` in een container achter de ingress. Een besluit dat de
  inrichting raakt (F6) legt de hoofdsessie eerst voor aan de gebruiker.
- **Geen gedragswijziging zonder test die het oude gedrag vastlegt.**
- **Meet na elke fase opnieuw** via de publieke API:
  `https://sonarcloud.io/api/issues/search?componentKeys=palmw01_wetsanalyse-ai&resolved=false&facets=rules`.
