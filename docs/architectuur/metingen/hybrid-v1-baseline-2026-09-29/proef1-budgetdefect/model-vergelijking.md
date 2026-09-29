# Modelvergelijking baselineproef: 84 primaire pogingen

A = productie vóór deze ronde (master b8117e2, universeel, geen context). U0/K0 = baselinecode universeel/klasseverzameling zonder context; UC/KC = idem met context uit `BronContext.ouders`, het productiemechanisme. Waar dat mechanisme niets oplevert is het verzoek identiek aan U0/K0; die cellen tonen de U0/K0-runs en tellen niet mee in de varianttotalen.

Stabiliteit vergelijkt bron-IRI + exacte offsets + klasse; zij bewijst geen juistheid. Kosten zijn ramingen uit tokens en lijstprijs, geen factuur.

| Variant | Pogingen / geslaagd | Calls (review) | Contractfouten | Voorstellen (menselijk) | Mediaan s/run | USD totaal | USD/run |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 24 / 24 | 29 (5) | 30 | 342 (12) | 22.369 | 0.7208 | 0.0300 |
| U0 | 24 / 24 | 37 (10) | 6 | 411 (18) | 34.273 | 0.8668 | 0.0361 |
| K0 | 24 / 24 | 156 (3) | 0 | 406 (3) | 73.631 | 1.9022 | 0.0793 |
| UC | 6 / 6 | 8 (2) | 3 | 210 (3) | 28.205 | 0.2443 | 0.0407 |
| KC | 6 / 6 | 45 (1) | 0 | 200 (1) | 92.15 | 0.6188 | 0.1031 |

## Herhaalbaarheid

Per variant: aantallen per run; vast/unie.

| Casus | A | U0 | K0 | UC | KC |
|---|---|---|---|---|---|
| IW-9-1 | [3, 4, 3]; 3/4 | [3, 5, 5]; 2/6 | [3, 3, 3]; 3/3 | [3, 5, 5]; 2/6 (= U0) | [3, 3, 3]; 3/3 (= K0) |
| IW-9-5 | [22, 28, 31]; 20/35 | [28, 28, 28]; 27/29 | [28, 30, 28]; 26/30 | [28, 28, 28]; 27/29 (= U0) | [28, 30, 28]; 26/30 (= K0) |
| LI-9.1 | [9, 10, 9]; 9/10 | [14, 15, 16]; 13/17 | [13, 14, 15]; 13/15 | [16, 15, 15]; 15/16 | [14, 14, 14]; 12/16 |
| LI-9.5 | [39, 38, 40]; 27/51 | [56, 56, 56]; 39/72 | [53, 53, 53]; 53/53 | [54, 54, 56]; 40/70 | [53, 53, 52]; 48/57 |
| IW02 | [11, 14, 13]; 11/15 | [11, 13, 12]; 11/13 | [13, 13, 11]; 11/13 | [11, 13, 12]; 11/13 (= U0) | [13, 13, 11]; 11/13 (= K0) |
| AWB04 | [10, 10, 10]; 10/10 | [10, 10, 10]; 9/11 | [13, 13, 13]; 13/13 | [10, 10, 10]; 9/11 (= U0) | [13, 13, 13]; 13/13 (= K0) |
| AWB-4:17-1 | [11, 8, 10]; 6/14 | [8, 10, 9]; 8/10 | [8, 8, 8]; 7/9 | [8, 10, 9]; 8/10 (= U0) | [8, 8, 8]; 7/9 (= K0) |
| IW04 | [3, 3, 3]; 3/3 | [3, 2, 3]; 2/3 | [3, 4, 3]; 2/4 | [3, 2, 3]; 2/3 (= U0) | [3, 4, 3]; 2/4 (= K0) |

## Keuzecriterium (vooraf vastgelegd)

- KC minder contractfouten dan UC: **True**
- Casussen met KC-stabiliteit ≥ UC: **4/8** (drempel 6)
- Kostenfactor KC/UC per run: **2.533** (drempel 3)
- Uitkomst granulariteit: **universeel**
- Casussen waar UC minder stabiel is dan U0: **0** (bij 5 of meer eerst bevestiging vragen: False)
