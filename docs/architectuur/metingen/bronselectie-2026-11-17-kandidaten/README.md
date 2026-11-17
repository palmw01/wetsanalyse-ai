# Bronselectie – hoeveel van het nodige staat op de kandidatenlijst (17 nov 2026)

Soort: *meting* (bewijs: niet achteraf wijzigen) · Volgt op [`bronselectie-2026-11-17-drie-rondes/`](../bronselectie-2026-11-17-drie-rondes/README.md)

## Waarom

In de vorige meting vielen 63 van de 172 nodige bepalingen weg bij het samenstellen van de 40 kandidaten, terwijl het model
van wat er staat bijna alles kiest. Hoe groot moet de lijst zijn?

## Wat er gemeten is

`eval/bronselectie_model_meting.py --kandidaten 40,60,80,120,160,80+definitie_brug` via `azure-infra` → `eval` →
`bronselectie_kandidaten`, op acceptatie, live tegen de graaf, **zonder model** (0 tokens), commit `a264d62d`. Dezelfde tien
sets (38 deelvragen). Per grens: hoeveel nodige bepalingen (kern of afhankelijkheid) op de kandidatenlijst staan
(`kandidaten_route`, dezelfde samenstelling als de bronnenrun).

## Uitkomst

| set | 40 | 60 | 80 | 120 | 160 | 80 + definitie_brug |
|---|---|---|---|---|---|---|
| Bestuurdersaansprakelijkheid | 0,78 | 0,78 | 0,78 | 0,83 | 0,83 | 0,72 |
| Bezwaar/ontvankelijkheid | 0,60 | 0,67 | 0,67 | 0,67 | 0,73 | 0,67 |
| Invorderbaarheid (deelvragen) | 0,55 | 0,64 | 0,82 | 0,82 | 0,82 | 0,73 |
| Kwijtschelding | 0,48 | 0,48 | 0,57 | 0,62 | 0,62 | 0,57 |
| Rekeningafspraken | 0,86 | 0,86 | 0,86 | 0,86 | 0,86 | 0,86 |
| Termijnen | 0,25 | 0,50 | 0,50 | 0,56 | 0,75 | 0,44 |
| Verrekening | 0,33 | 0,44 | 0,56 | 0,56 | 0,56 | 0,56 |
| LB-07 | 0,30 | 0,45 | 0,45 | 0,50 | 0,50 | 0,45 |
| LB-08 | 0,30 | 0,30 | 0,37 | 0,43 | 0,43 | 0,30 |
| LB-09 | 0,19 | 0,19 | 0,25 | 0,25 | 0,31 | 0,38 |
| **totaal (van 172)** | **73** | **84** | **93** | **99** | **104** | **90** |

## Besluit

De grens gaat van 40 naar **80**: de grootste winst per token (+20), daarna nemen de opbrengsten af (+6, +5). De tekst per
kandidaat gaat van 500 naar 300 tekens, zodat een aanroep ongeveer even groot blijft. `definitie_brug` verdringt bij 80 andere
nodige bepalingen (90 tegen 93) en helpt alleen LB-09: niet standaard. Eén modelronde bevestigt de grens.
