# Modelvergelijking baselineproef: 84 primaire pogingen

A = productie vóór deze ronde (master b8117e2, universeel, geen context). U0/K0 = baselinecode universeel/klasseverzameling zonder context; UC/KC = idem met context uit `BronContext.ouders`, het productiemechanisme. Waar dat mechanisme niets oplevert is het verzoek identiek aan U0/K0; die cellen tonen de U0/K0-runs en tellen niet mee in de varianttotalen.

Stabiliteit vergelijkt bron-IRI + exacte offsets + klasse; zij bewijst geen juistheid. Kosten zijn ramingen uit tokens en lijstprijs, geen factuur.

| Variant | Pogingen / geslaagd | Calls (review) | Contractfouten | Voorstellen (menselijk) | Mediaan s/run | USD totaal | USD/run |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 24 / 24 | 28 (3) | 22 | 342 (11) | 22.488 | 0.7294 | 0.0304 |
| U0 | 24 / 24 | 38 (14) | 15 | 424 (5) | 23.722 | 0.6402 | 0.0267 |
| K0 | 24 / 24 | 148 (1) | 0 | 428 (1) | 28.336 | 1.0112 | 0.0421 |
| UC | 6 / 6 | 12 (6) | 9 | 213 (0) | 31.473 | 0.2285 | 0.0381 |
| KC | 6 / 6 | 42 (0) | 0 | 210 (0) | 26.273 | 0.3317 | 0.0553 |

## Herhaalbaarheid

Per variant: aantallen per run; vast/unie.

| Casus | A | U0 | K0 | UC | KC |
|---|---|---|---|---|---|
| IW-9-1 | [3, 3, 3]; 2/4 | [4, 4, 4]; 4/4 | [4, 4, 4]; 3/5 | [4, 4, 4]; 4/4 (= U0) | [4, 4, 4]; 3/5 (= K0) |
| IW-9-5 | [26, 31, 32]; 21/37 | [32, 32, 33]; 31/34 | [31, 31, 31]; 25/37 | [32, 32, 33]; 31/34 (= U0) | [31, 31, 31]; 25/37 (= K0) |
| LI-9.1 | [10, 8, 8]; 8/10 | [15, 15, 16]; 15/16 | [15, 15, 15]; 13/17 | [15, 15, 15]; 13/17 | [16, 16, 16]; 16/16 |
| LI-9.5 | [40, 38, 42]; 24/56 | [56, 56, 56]; 56/56 | [54, 54, 54]; 52/56 | [56, 56, 56]; 56/56 | [54, 54, 54]; 54/54 |
| IW02 | [14, 14, 11]; 10/16 | [11, 11, 11]; 11/11 | [13, 13, 13]; 13/13 | [11, 11, 11]; 11/11 (= U0) | [13, 13, 13]; 13/13 (= K0) |
| AWB04 | [10, 10, 10]; 10/10 | [10, 10, 10]; 9/11 | [13, 13, 13]; 13/13 | [10, 10, 10]; 9/11 (= U0) | [13, 13, 13]; 13/13 (= K0) |
| AWB-4:17-1 | [6, 6, 9]; 6/9 | [11, 10, 9]; 8/12 | [9, 9, 9]; 9/9 | [11, 10, 9]; 8/12 (= U0) | [9, 9, 9]; 9/9 (= K0) |
| IW04 | [3, 2, 3]; 2/3 | [2, 3, 3]; 2/3 | [4, 3, 4]; 3/4 | [2, 3, 3]; 2/3 (= U0) | [4, 3, 4]; 3/4 (= K0) |

## Keuzecriterium (vooraf vastgelegd)

- KC minder contractfouten dan UC: **True**
- Casussen met KC-stabiliteit ≥ UC: **6/8** (drempel 6)
- Kostenfactor KC/UC per run: **1.452** (drempel 3)
- Uitkomst granulariteit: **klasseverzameling**
- Casussen waar UC minder stabiel is dan U0: **1** (bij 5 of meer eerst bevestiging vragen: False)
