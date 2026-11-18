# Bronselectie – het model kiest met het belang van verwijzingen (18 nov 2026)

Soort: *meting* (bewijs: niet achteraf wijzigen) · Volgt op [`bronselectie-2026-11-18-belang/`](../bronselectie-2026-11-18-belang/README.md)

## Waarom

Met het belang van verwijzingen staan er op de kandidatenlijst 125 van de 172 nodige bepalingen, tegen 120 zonder. Kiest het
model ze ook?

**Criterium, vóór de run vastgelegd:** de vlag gaat aan als het aantal gekozen nodige bepalingen stijgt, geen set zakt en de
verkeerde deelvraag niet duidelijk toeneemt. Dat is lichter dan bij de grens van 120, omdat het belang geen tokens kost en de
aanroep naar het model niet groter maakt.

## Wat er gemeten is

`azure-infra` → `eval` → `bronselectie_belang_model` (`--varianten belang`), op acceptatie, live tegen de graaf, model
`claude-sonnet-4-6`, op commit `6708ed49` (run 44205379713). Het model kiest één ronde zonder belang en één ronde met belang.
De vergelijking is gepaard: beide routes gebruiken dezelfde wetstermen per deelvraag (#1713). Het gaat om dezelfde tien sets
en 38 deelvragen. De verwachtingen zijn nog concept.

## Uitkomst

Recall op de nodige bepalingen, zonder en met belang:

- Bestuurdersaansprakelijkheid 0,78 → 0,78
- Bezwaar/ontvankelijkheid 0,73 → 0,73
- Invorderbaarheid 0,64 → 0,64
- Kwijtschelding 0,81 → 0,86
- Rekeningafspraken 0,71 → 0,71
- Termijnen 0,25 → 0,31
- Verrekening 0,61 → 0,61
- LB-07 0,50 → 0,55
- LB-08 0,47 → 0,47
- LB-09 0,69 → 0,69

Afval van de 172 nodige bepalingen, zonder en met belang:

- niet gevonden: 8 en 8
- gevonden, maar niet bij de kandidaten: 43 en 39
- bij de kandidaten, maar niet gekozen: 17 en 18
- gekozen: 104 en 107

Verkeerde deelvraag: 12 zonder en 13 met belang.

Kosten: de hele run kostte 114 aanroepen en 781k invoertokens. Het belang zelf kost geen tokens.

## Besluit

**`belang` gaat standaard aan.** Het criterium is gehaald:

- gekozen 104 → 107;
- beter op 3 sets en op geen enkele set slechter;
- op de lijst in de vorige meting +5, ook zonder verlies;
- de verkeerde deelvraag gaat van 12 naar 13.

De winst is klein: +3 ligt dicht bij wat twee rondes van het model van elkaar kunnen verschillen. Maar beide metingen wijzen
dezelfde kant op, en het belang kost niets aan tokens of aan de grootte van de aanroep. Het kost wel graafverkeer: één vraag per
honderd kandidaten in de voorlopige top, dus hoogstens drie per deelvraag.
