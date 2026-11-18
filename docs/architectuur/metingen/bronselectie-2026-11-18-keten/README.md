# Bronselectie – de hele keten: keuze, opnemen, afhankelijkheden (18 nov 2026)

Soort: *meting* (bewijs: niet achteraf wijzigen) · Volgt op [`bronselectie-2026-11-18-beleidsregel/`](../bronselectie-2026-11-18-beleidsregel/README.md)

## Waarom

`lid_verwijzing` (#1722) en `beleidsregel` (#1724) zijn gemeten vanuit de verwachte kern. De metingen van de kandidatenlijst
en van de keuze door het model raken ze niet, want ze draaien pas op een opgenomen kern. Deze meting volgt de hele keten.
Zo blijkt hoeveel van de winst overblijft als de kern komt uit wat het model echt koos.

## Wat er gemeten is

`azure-infra` → `eval` → `bronselectie_keten` (#1725):
`--rondes 1 --keten standaard-lid_verwijzing-beleidsregel,standaard`. Gedraaid op acceptatie, live tegen de graaf, met model
`claude-sonnet-4-6`, op commit `cb9ee2bd` (run 44338415850). Per deelvraag:

1. Het model kiest, in één ronde.
2. Een jurist neemt op wat juist is: wat het model koos en wat een verwachte bepaling van die deelvraag raakt.
3. Daarop draaien de afhankelijkheden: zonder de twee nieuwe methoden, en met (de standaard van nu). Beide op dezelfde keuze.

Geteld worden de nodige bepalingen (kern en afhankelijkheid), precies of eronder. Het gaat om dezelfde tien sets en 172 nodige
bepalingen; de verwachtingen zijn nog concept. Het model kostte 414k invoertokens en 8k uitvoertokens (76 aanroepen).

## Uitkomst

Nodige bepalingen na de keuze | na de afhankelijkheden zonder de nieuwe methoden | met (kandidaten van de afhankelijkheden):

- Bestuurdersaansprakelijkheid: 14/18 | 14/18 (119) | **16/18 (144)**
- Bezwaar/ontvankelijkheid: 13/15 | 13/15 (95) | 13/15 (96)
- Invorderbaarheid: 8/11 | 8/11 (34) | **9/11 (60)**
- Kwijtschelding: 17/21 | 18/21 (30) | 18/21 (45)
- Rekeningafspraken: 4/7 | 4/7 (53) | 4/7 (56)
- Termijnen: 5/16 | 5/16 (14) | **7/16 (19)**
- Verrekening: 12/18 | 12/18 (59) | **14/18 (68)**
- LB-07: 11/20 | 13/20 (20) | **15/20 (24)**
- LB-08: 14/30 | 14/30 (136) | **16/30 (146)**
- LB-09: 11/16 | 12/16 (48) | **13/16 (58)**
- **Totaal: na de keuze 109/172 | zonder 113/172 (608) | met 125/172 (716)**

Hoe dat uitvalt:

- Met de nieuwe methoden staan er na de hele keten 12 nodige bepalingen meer: 125 tegen 113 van de 172.
- Dat kost 108 kandidaten meer, verdeeld over 38 deelvragen (+18%).
- De methoden zijn op 7 sets beter en op geen enkele slechter.
- Vanuit de verwachte kern was de winst 11 van 59. Hier is het meer, omdat het model ook bepalingen als kern kiest die de set
  als afhankelijkheid verwacht, en daar hangen weer andere aan.

De keuze zelf (109/172) staat los van deze wijziging. Het is één ronde. Eerder kwam de keuze uit op 104–107, en de spreiding
tussen rondes is groot.

## Besluit

`lid_verwijzing` en `beleidsregel` blijven standaard aan.

## Wat nog mist

- **Nog niet in een lijst.** 47 van de 172 nodige bepalingen staan na de hele keten nergens. Het grootste deel daarvan valt
  af vóór de afhankelijkheden: in de kernfase gaat het mis bij de woordenkloof en de rangschikking (zie
  [`bronselectie-2026-11-18-afbakening/`](../bronselectie-2026-11-18-afbakening/README.md)).
- **De opgenomen kern is te gunstig.** Hier neemt een jurist precies op wat juist is. In het echt komen de afhankelijkheden
  ook op een kern die de jurist zelf toevoegt of anders kiest.
