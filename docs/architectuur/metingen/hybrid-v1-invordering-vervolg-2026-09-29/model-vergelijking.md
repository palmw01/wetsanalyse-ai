# Modelvergelijking: 72 primaire pogingen

A = baseline b8117e2; B = a0699a5 met lege aanvullende context; C = dezelfde code met vooraf bevroren graafcontext. Drie pogingen per variant en casus. Volgorde per ronde A/B/C, B/C/A, C/A/B. Geen uitrol of opslag van annotaties.

Een voorstel voor menselijke beoordeling telt als voorstel, niet als juridisch geaccepteerd element. Stabiliteit vergelijkt bron-IRI + exacte offsets + klasse; zij bewijst geen juistheid. Mislukte pogingen worden afzonderlijk geteld en niet vervangen.

| Variant | Pogingen / geslaagd | Calls (review) | Voorstellen (menselijk) | Mediaan s/run | Kostenraming USD |
|---|---:|---:|---:|---:|---:|
| A_huidig | 24 / 24 | 27 (3) | 343 (5) | 24.557 | 0.6987 |
| B_verbeterd | 24 / 24 | 159 (2) | 410 (2) | 94.846 | 2.0224 |
| C_context | 24 / 24 | 156 (2) | 405 (8) | 75.711 | 3.0166 |

Kosten zijn een raming uit de gerapporteerde input-, output- en cachetokens en de in elk runbestand opgenomen lijstprijs; geen Azure-factuur. SDK-retries staan op nul; de bestaande classifier mag één identieke herpoging doen bij ontbrekende tooluitvoer. Deze herpogingen worden apart geteld. Eventuele mislukte pipelinepogingen blijven in de noemer. De adapter kan bij een geweigerd cachepunt eenmaal zonder caching herhalen; de vastgelegde calls meten adapteraanroepen, geen netwerkverkeer.

De eerste zes pogingen draaiden sequentieel. Daarna zijn maximaal drie onafhankelijke casussen tegelijk uitgevoerd, met een barrière tussen de rondes en dezelfde variantrotatie per casus. Zie `modelruns/planner.json`. Latentie is daardoor mede afhankelijk van parallelisme en is geen zuivere snelheidsbenchmark.

Tijdens ronde 1 bleek de lokale onderzoekssnapshot van de controles niet afgesloten: de hoogste geselecteerde ouder verwees naar de niet meegeleverde regelingwortel. Dit gaf `V_ANKER`, onafhankelijk van de modelkeuze. De lokale boom is expliciet afgebakend, met behoud van de echte externe graafouder, teksten, offsets, directe oudercontext en alle primaire reacties. De betrokken pogingen zijn zonder herhaalde classificatie gereplayed; hun oorspronkelijke bestanden blijven bewaard. `modelruns/correctie-snapshot.json` en `snapshot-herstel/` registreren deze correctie. De vergelijking gebruikt de herstelde uitvoer en telt iedere primaire poging eenmaal. Dit was een fout in de proefopbouw, geen juridische afwijzing en geen gewijzigde productvalidator.

## Herhaalbaarheid

Aantallen zijn de drie runs in rondevolgorde. ‘Vast/unie’ is het aantal voorstellen dat in alle geslaagde runs terugkomt, gedeeld door alle verschillende voorstellen.

| Casus | A: aantallen; vast/unie | B: aantallen; vast/unie | C: aantallen; vast/unie |
|---|---|---|---|
| IW-9-1 | [3, 3, 2]; 2/4 | [3, 3, 3]; 3/3 | [3, 3, 3]; 3/3 |
| IW-9-5 | [27, 27, 32]; 24/34 | [28, 28, 28]; 26/30 | [26, 28, 28]; 18/36 |
| LI-9.1 | [9, 10, 10]; 9/10 | [15, 13, 15]; 13/15 | [15, 15, 16]; 14/16 |
| LI-9.5 | [41, 41, 40]; 25/58 | [56, 55, 56]; 55/56 | [48, 48, 49]; 41/56 |
| IW02 | [13, 13, 13]; 12/14 | [13, 13, 12]; 11/14 | [14, 13, 13]; 13/14 |
| AWB04 | [10, 10, 10]; 10/10 | [10, 10, 10]; 9/11 | [16, 13, 16]; 12/17 |
| AWB-4:17-1 | [7, 8, 7]; 6/10 | [10, 10, 9]; 8/11 | [11, 9, 10]; 9/12 |
| IW04 | [3, 2, 2]; 2/3 | [4, 3, 3]; 3/4 | [3, 2, 3]; 2/3 |

De volledige toegevoegde, verdwenen, anders geklasseerde en wisselende voorstellen staan in [het beoordelingsdossier](model-dossier.md). [De machineleesbare vergelijking](model-vergelijking.json) bevat ook tokens, besluitstatus, twijfels en resolutieregels.
