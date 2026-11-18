# Bronselectie – de grens van 80 of 120 kandidaten over de hele keten (18 nov 2026)

Soort: *meting* (bewijs: niet achteraf wijzigen) · Volgt op [`bronselectie-2026-11-18-menging/`](../bronselectie-2026-11-18-menging/README.md) en [`bronselectie-2026-11-17-grens-120/`](../bronselectie-2026-11-17-grens-120/README.md)

## Waarom

Van de nodige bepalingen die na de hele keten missen, staan er zes in de woordenroute vóór plaats 80. Toch halen ze de
lijst niet. Dat komt doordat de woordenroute en de pool om de beurt worden genomen. Meer plekken voor de woordenroute
kostte meer dan het opleverde (`bronselectie-2026-11-18-menging`). Dubbelen kosten al geen plek, en wie in beide lijsten
staat eerst nemen is in feite `rrf` (124 tegen 123 op 17 nov). Wat dan nog overblijft is de grens zelf. Op 17 nov kwamen
er bij 120 kandidaten 135 van de 172 op de lijst, tegenover 123 bij 80. Toen koos het model 103 → 107, binnen de
spreiding, maar zonder de afhankelijkheden van nu.

## Wat er gemeten is

De meting is `bronselectie_keten_grens` (run 44383743195), op commit `d572fa9c` (#1733), live op acceptatie.

- Het model kiest één ronde uit 80 en één ronde uit 120 kandidaten. Beide gebruiken dezelfde wetstermen, dus de
  vergelijking is gepaard.
- De jurist neemt op wat juist is. Daarop draaien de afhankelijkheden met de standaard.
- Model `claude-sonnet-4-6`, 939k invoertokens. Tien sets, met concept-verwachtingen.

## Uitkomst

Nodige bepalingen van de 172:

| grens | na de keuze | na de hele keten | kandidaten van de afhankelijkheden |
|---|---|---|---|
| 80 | 113 | 133 | 874 |
| 120 | **117** | **138** | 904 |

Per set na de hele keten:

- **Beter:**
  - LB-08: 17 → 21;
  - verrekening: 14 → 15.
- **Gelijk:** de andere acht sets.
- **Slechter:** geen.

Na de keuze verloren kwijtschelding en termijnen er elk één, terwijl LB-08 er drie won.

Bij 80 komt de keten nu uit op 133. In run 44358614199 was dat 138, met dezelfde methoden. De keuze van het model
verschilt dus tussen runs met ongeveer vijf bepalingen over de hele keten. Dat is even groot als het verschil tussen de
twee grenzen.

## Besluit

De grens blijft 80. Twee metingen wijzen dezelfde kant op (+4 na de keuze, nu en op 17 nov), maar het verschil valt
binnen de spreiding tussen runs en zit vooral in één set, LB-08. Daar staat tegenover:

- een keuze uit 120 kost per deelvraag ongeveer de helft meer invoer;
- op 17 nov steeg het aantal keuzes bij een verkeerde deelvraag van 11 naar 14.

Wil je dit zeker weten, dan is een tweede gepaarde ronde nodig, ongeveer 1M tokens.
