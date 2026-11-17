# Bronselectie – één keuze per werkgebied, met wetstermen (17 nov 2026)

Soort: *meting* (bewijs: niet achteraf wijzigen) · Volgt op [`bronselectie-2026-11-17-wetstermen-werkgebied/`](../bronselectie-2026-11-17-wetstermen-werkgebied/README.md)

## Waarom

In de vorige meting gaf `deelvraag_keuze.PER_WERKGEBIED` een gemengd beeld, en de vlag was toen nog niet samen met de
wetstermen gemeten. Sinds #1707 staan de wetstermen standaard aan. Helpt één keuze voor het hele werkgebied nu wel?

**Criterium, hetzelfde als vorige keer en vóór de run vastgelegd:** de vlag gaat aan als het aantal gekozen nodige
bepalingen duidelijk stijgt, geen set duidelijk zakt en de verkeerde deelvraag niet toeneemt.

## Wat er gemeten is

`azure-infra` → `eval` → `bronselectie_werkgebied` (`--rondes 2 --werkgebied`), op acceptatie, live tegen de graaf,
model `claude-sonnet-4-6`, commit `3c349de1` (run 44176079416). Beide routes draaien met de wetstermen: dat is nu de
standaard van het zoekprofiel. Het gaat om dezelfde tien sets en 38 deelvragen. De verwachtingen zijn nog concept.

## Uitkomst

Recall op de nodige bepalingen, gemiddeld over twee rondes, eerst per deelvraag en dan per werkgebied:

| set | per deelvraag | per werkgebied |
|---|---|---|
| Bestuurdersaansprakelijkheid | 0,81 | 0,81 |
| Bezwaar/ontvankelijkheid | 0,67 | 0,60 |
| Invorderbaarheid | 0,68 | 0,77 |
| Kwijtschelding | 0,81 | 0,67* |
| Rekeningafspraken | 0,64 | 0,71 |
| Termijnen | 0,31 | 0,28 |
| Verrekening | 0,67 | 0,75 |
| LB-07 | 0,50 | 0,40 |
| LB-08 | 0,43 | 0,53* |
| LB-09 | 0,69 | 0,78 |

\* In de log van Log Analytics lopen de regels door elkaar, want ze hebben dezelfde tijdstempels. Twee regels "per
werkgebied" stonden niet onder hun set. Op grond van de volgorde horen ze bij Kwijtschelding en LB-08. De totalen hieronder
zijn wel betrouwbaar.

Precisie: per werkgebied is ze op 8 van de 10 sets hoger, bijvoorbeeld bij Verrekening 0,49 → 0,59 en bij Invorderbaarheid
0,51 → 0,64.

Wat er van de 172 nodige bepalingen overbleef, per deelvraag tegenover per werkgebied:

- niet gevonden: 9 en 6
- gevonden, maar niet bij de kandidaten: 41 en 23
- bij de kandidaten, maar niet gekozen: 17 en 35
- gekozen: 105 en 108

Verkeerde deelvraag per ronde: 15 en 19 per deelvraag, 18 en 16 per werkgebied.

Kosten: de hele run kostte 248 aanroepen, 1,32M invoertokens en 34k uitvoertokens.

## Besluit

**`PER_WERKGEBIED` blijft uit.** Het criterium is niet gehaald:

- het aantal gekozen bepalingen stijgt nauwelijks (105 → 108);
- twee sets zakken duidelijk: Kwijtschelding met 0,14 en LB-07 met 0,10;
- de verkeerde deelvraag daalt niet.

De vlag geeft wel een hogere precisie. Ook staan er meer nodige bepalingen bij de kandidaten (de vereniging van de
deelvragen), maar het model laat er meer van liggen (35 tegen 17). Een volgende stap zou die kant moeten aanpakken, bijvoorbeeld meer dan
acht keuzes per deelvraag toestaan als het werkgebied ze samen ziet. Dat is een eigen proef, niet deze vlag.
