Set: Invorderbaarheid van belastingaanslagen – status concept (trendmeting, geen kwaliteitsoordeel tot vaststelling)
Analysevraag: Wanneer is een belastingaanslag invorderbaar?
Verwacht: 12 (nodig: 7), uitgesloten: 7, buiten de graaf: 1

| configuratie | aantal | recall nodig | recall | exact | r@10 | r@20 | overbodig | onbeoordeeld | rol juist | onvolledig |
|---|---|---|---|---|---|---|---|---|---|---|
| alleen overzicht | 40 | 0.43 | 0.25 | 0.00 | 0.08 | 0.25 | 0.05 | 36 | 0.33 | overzicht |
| alleen verwijzing_uit | 1 | 0.57 | 0.42 | 0.00 | 0.42 | 0.42 | 0.00 | 0 | 0.80 | – |
| alleen verwijzing_in | 29 | 0.14 | 0.17 | 0.17 | 0.08 | 0.08 | 0.24 | 20 | 0.50 | – |
| alleen definitie | 7 | 0.57 | 0.33 | 0.33 | 0.33 | 0.33 | 0.00 | 3 | 1.00 | – |
| alleen opbouw | 2 | 0.43 | 0.25 | 0.00 | 0.25 | 0.25 | 0.00 | 0 | 0.00 | – |
| alleen gelijkenis | 3 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 3 | – | – |
| standaard | 10 | 1.00 | 0.67 | 0.33 | 0.67 | 0.67 | 0.00 | 3 | 0.50 | – |
| standaard zonder verwijzing_uit | 9 | 1.00 | 0.58 | 0.33 | 0.58 | 0.58 | 0.00 | 3 | 0.57 | – |
| standaard zonder definitie | 3 | 1.00 | 0.67 | 0.00 | 0.67 | 0.67 | 0.00 | 0 | 0.50 | – |
| standaard zonder opbouw | 8 | 0.57 | 0.42 | 0.33 | 0.42 | 0.42 | 0.00 | 3 | 0.80 | – |
| standaard + overzicht | 48 | 1.00 | 0.67 | 0.33 | 0.25 | 0.25 | 0.04 | 39 | 0.62 | overzicht |
| standaard + verwijzing_in | 39 | 1.00 | 0.75 | 0.50 | 0.42 | 0.50 | 0.18 | 23 | 0.56 | – |
| standaard + gelijkenis | 13 | 1.00 | 0.67 | 0.33 | 0.42 | 0.67 | 0.00 | 6 | 0.50 | – |
| alles | 80 | 1.00 | 0.75 | 0.50 | 0.25 | 0.25 | 0.11 | 62 | 0.67 | overzicht |

Gemist door de standaard: urn:bwb:BWBR0004770:artikel:3:lid:1, urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.1, urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.4, urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.5
Overbodig in de standaard: niets
