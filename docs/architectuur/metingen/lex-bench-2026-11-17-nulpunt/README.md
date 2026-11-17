# Lex Bench, bronselectie – nulpunt (2026-11-17)

Arm L1 (zonder model, route `zoekvragen standaard (stap 8)`) op `bench-bronselectie-v1` (hash `3986e4619bd3`), commit `39221e2d`, zoekversie `za28985cb2f88`. 0 tokens. Alle verwachtingen zijn `concept`: dit is een **trendmeting**, geen oordeel (plan §22, besluit 2). Er is geen totaalcijfer.

| casus | niveau | gebruik | recall nodig | recall | precisie | overlap | Lex mist | Lex onterecht |
|---|---|---|---|---|---|---|---|---|
| LB-01 Termijnen | moeilijk | ontwikkeling | 1/16 | 1/18 | 1/24 | 1/41 | 17 | 23 |
| LB-02 Kwijtschelding voor particulieren | moeilijk | ontwikkeling | 7/21 | 7/24 | 7/32 | 7/49 | 17 | 25 |
| LB-03 Bestuurdersaansprakelijkheid | gemiddeld | ontwikkeling | 8/18 | 9/22 | 7/32 | 9/47 | 13 | 25 |
| LB-04 Ontvankelijkheid van bezwaar tegen een belastingaanslag | gemiddeld | ontwikkeling | 6/15 | 7/19 | 6/32 | 7/45 | 12 | 26 |
| LB-05 Invorderbaarheid van belastingaanslagen | gemiddeld | ontwikkeling | 5/11 | 6/18 | 6/32 | 6/44 | 12 | 26 |
| LB-06 Rekeningafspraken | gemiddeld | ontwikkeling | 2/7 | 2/7 | 2/40 | 2/45 | 5 | 38 |

De categorieën zijn een voorstel van de code: *team mist* en *twijfel* vragen de reviewer en de jurist (LB2). Per niveau staat het rapport in `rapport.json`.
