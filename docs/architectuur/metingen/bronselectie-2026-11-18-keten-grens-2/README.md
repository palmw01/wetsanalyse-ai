# Bronselectie – de grens over de hele keten, tweede ronde (18 nov 2026)

Soort: *meting* (bewijs: niet achteraf wijzigen) · Volgt op [`bronselectie-2026-11-18-keten-grens/`](../bronselectie-2026-11-18-keten-grens/README.md)

## Waarom

In de eerste gepaarde ronde was 120 beter dan 80: van de 172 nodige bepalingen 117 tegen 113 na de keuze, en 138 tegen 133
na de hele keten. Dat verschil was even groot als de spreiding tussen runs. Deze tweede ronde meet hetzelfde nog een keer.

## Wat er gemeten is

De meting is `bronselectie_keten_grens` (run 44387635048), op commit `9865733e`, met dezelfde opzet als de eerste ronde:

- het model kiest één ronde uit 80 en één uit 120 kandidaten, met dezelfde wetstermen (gepaard);
- daarop draait de keten met de afhankelijkheden in de standaard;
- model `claude-sonnet-4-6`, 942k invoertokens.

## Uitkomst

Nodige bepalingen van de 172:

| ronde | grens | na de keuze | na de hele keten | kandidaten | verkeerde deelvraag |
|---|---|---|---|---|---|
| 1 (run 44383743195) | 80 | 113 | 133 | 874 | 16 |
| 1 | 120 | 117 | 138 | 904 | 12 |
| 2 (run 44387635048) | 80 | 109 | 134 | 868 | 13 |
| 2 | 120 | 113 | 138 | 836 | 13 |

Na de keuze wint 120 in elke gepaarde ronde vier bepalingen: in beide rondes hier en ook op 17 nov (103 → 107). Na de
hele keten zijn het er samen 9 (267 → 276).

Per set, over beide rondes samen na de keten:

- **Beter:**
  - LB-08: +6;
  - termijnen: +3;
  - invorderbaarheid: +1;
  - verrekening: +1.
- **Slechter:**
  - kwijtschelding: −1;
  - rekeningafspraken: −1.
  Beide keren alleen in ronde 2, met één bepaling.
- **Gelijk:** de andere vier sets.

Het aantal keuzes bij een verkeerde deelvraag nam niet toe (16 → 12, 13 → 13). Het aantal kandidaten van de afhankelijkheden
bleef ongeveer gelijk (874 → 904, 868 → 836).

## Besluit

De grens gaat naar 120 (`deelvraag_keuze.MAX_KANDIDATEN`). Drie gepaarde rondes wijzen dezelfde kant op, en er komt geen
extra werk voor de jurist bij. De prijs is een keuze-aanroep die ongeveer de helft groter is. Dat is per deelvraag van
~9k naar ~14k invoertokens.
