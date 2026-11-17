# Bronselectie – het model kiest uit 80 of 120 kandidaten (17 nov 2026)

Soort: *meting* (bewijs: niet achteraf wijzigen) · Volgt op [`bronselectie-2026-11-17-rangschikking/`](../bronselectie-2026-11-17-rangschikking/README.md)

## Waarom

Op de lijst haalt een grens van 120 er 12 nodige bepalingen bij: 135 in plaats van 123 van de 172. Kiest het model die ook,
als het uit 50% meer tekst moet kiezen?

**Criterium, vóór de run vastgelegd:** de grens gaat naar 120 als het aantal gekozen nodige bepalingen duidelijk stijgt,
meer dan de spreiding tussen runs. Bij 80 is dat 103 tot 109 in de rondes van vandaag. Daarnaast mag geen set duidelijk
zakken en mag de verkeerde deelvraag niet toenemen.

## Wat er gemeten is

`azure-infra` → `eval` → `bronselectie_grens` (`--varianten kandidaten_120`), op acceptatie, live tegen de graaf, met model
`claude-sonnet-4-6`, op commit `36b2c0ab` (run 44192372897). Het model kiest één ronde uit 80 kandidaten (de standaard) en
één ronde uit 120, beide met wetstermen. Het gaat om dezelfde tien sets en 38 deelvragen. De verwachtingen zijn nog concept.

## Uitkomst

Recall op de nodige bepalingen bij 80 en bij 120 kandidaten:

| set | 80 | 120 |
|---|---|---|
| Bestuurdersaansprakelijkheid | 0,72 | 0,72 |
| Bezwaar/ontvankelijkheid | 0,73 | 0,67 |
| Invorderbaarheid | 0,64 | 0,82 |
| Kwijtschelding | 0,76 | 0,76 |
| Rekeningafspraken | 0,57 | 0,71 |
| Termijnen | 0,31 | 0,38 |
| Verrekening | 0,67 | 0,67 |
| LB-07 | 0,50 | 0,55 |
| LB-08 | 0,47 | 0,43 |
| LB-09 | 0,69 | 0,75 |

Afval van de 172 nodige bepalingen, eerst bij 80 en dan bij 120 kandidaten:

- niet gevonden: 8 en 10
- gevonden, maar niet bij de kandidaten: 43 en 31
- bij de kandidaten, maar niet gekozen: 18 en 24
- gekozen: 103 en 107

Verkeerde deelvraag: 11 bij 80, 14 bij 120.

Kosten: de hele run kostte 152 aanroepen, 984k invoertokens en 16k uitvoertokens. Een aanroep bij 120 is ongeveer de helft
groter dan bij 80.

## Besluit

**De grens blijft 80.**

- Het aantal gekozen bepalingen stijgt met 4 (103 → 107). Dat valt binnen de spreiding tussen runs bij 80 (103–109).
- Het model laat meer liggen van wat er staat: 24 tegen 18 niet gekozen.
- De verkeerde deelvraag neemt toe, van 11 naar 14.
- Twee sets zakken licht: Bezwaar met 0,06 en LB-08 met 0,04.

Van de 12 bepalingen die een langere lijst binnenhaalt, kiest het model er dus maar een paar, terwijl elke aanroep de helft
duurder wordt. Winst zit eerder in een betere volgorde binnen de woordenroute: dan staan de nodige bepalingen bij de eerste
80, in plaats van dat de lijst langer wordt (zie de rangdiagnose in de vorige meting: 27 van de 49 gemiste bepalingen staan in
de woordenroute op plaats 81–400).
