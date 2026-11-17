# Bronselectie – de rangschikking van de kandidaten (17 nov 2026)

Soort: *meting* (bewijs: niet achteraf wijzigen) · Volgt op [`bronselectie-2026-11-17-werkgebied-met-wetstermen/`](../bronselectie-2026-11-17-werkgebied-met-wetstermen/README.md)

## Waarom

Met de wetstermen aan vonden de zoekvragen 41 van de 172 nodige bepalingen wel, maar ze haalden de 80 kandidaten niet. Wat
houdt ze tegen: de manier waarop de twee lijsten samengaan, de lengte van de lijst, of de rangschikking binnen een lijst?

## Wat er gemeten is

`azure-infra` → `eval` → `bronselectie_rangschikking`: `--kandidaten 80,120,80+rrf,120+rrf,80+zonder_wetstermen --rangen`.
De meting liep op acceptatie, live tegen de graaf, op commit `2af0f611` (run 44186569672). Het model kiest hier niet; alleen
de wetstermen kostten tokens (47,5k invoer, 2,9k uitvoer, één keer voor alle routes). Het gaat om dezelfde tien sets en 38
deelvragen. De verwachtingen zijn nog concept.

- `rrf` (`Zoekprofiel.menging`, #1709): de woordenroute en de pool rond de gebeurtenis rangschikken op de som van
  1/(60 + plaats), in plaats van om de beurt.
- `--rangen`: per nodige bepaling die de 80 niet haalde, haar plaats in de woordenroute en in de pool, elk tot 400
  opgevraagd.

## Uitkomst

Nodige bepalingen op de kandidatenlijst, van 172:

- 80 (zoals Lex nu werkt): 123
- 80 zonder wetstermen: 93
- 80 met rrf: 124
- 120: 135
- 120 met rrf: 135

Per set, 80 → 120:

- Bestuurdersaansprakelijkheid 0,78 → 0,78
- Bezwaar/ontvankelijkheid 0,80 → 0,80
- Invorderbaarheid 0,73 → 0,91
- Kwijtschelding 0,76 → 0,81
- Rekeningafspraken 1,00 → 1,00
- Termijnen 0,50 → 0,56
- Verrekening 0,72 → 0,78
- LB-07 0,60 → 0,70
- LB-08 0,70 → 0,83
- LB-09 0,75 → 0,81

Waar de 49 staan die de 80 niet haalden (de beste plaats in een van beide lijsten):

- 8 staan in een lijst bij de eerste 80, maar vielen weg doordat elke lijst om de beurt ongeveer 40 plaatsen krijgt;
- 14 staan op plaats 81–120;
- 16 staan op plaats 121–400, vrijwel allemaal in de woordenroute;
- 11 staan in geen van beide lijsten, ook niet tot 400.

Vrijwel elk geval komt uit de woordenroute; de pool rond de gebeurtenis vindt de meeste niet (in 38 van de 49 gevallen
"pool niet in de lijst").

## Wat dit zegt

- **De menging is het probleem niet.** Rrf haalt er 1 bij: de bepalingen die wegvallen staan maar in één lijst, dus een
  menging die op overeenstemming tussen de lijsten let, helpt ze niet.
- **Een langere lijst helpt wel**: 120 haalt er 12 bij, op 7 van de 10 sets. Het model moet dan kiezen uit 50% meer
  tekst, dus de vraag is of het die ook kiest. Dat meet `bronselectie_grens`.
- **De rangschikking binnen de woordenroute** laat 16 bepalingen op plaats 121–400 staan. Dat is de volgende knop, als
  een langere lijst niet genoeg oplevert.
- **De 11 die nergens staan** zijn een zoekprobleem, geen rangschikkingsprobleem.

## Besluit

De menging blijft `afwisselend`. Of de grens naar 120 gaat, hangt af van de keuze door het model (`bronselectie_grens`).
