# Bronselectie – wetstermen en één keuze per werkgebied (17 nov 2026)

Soort: *meting* (bewijs: niet achteraf wijzigen) · Volgt op [`bronselectie-2026-11-17-kandidaten/`](../bronselectie-2026-11-17-kandidaten/README.md)

## Waarom

Na de grens van 80 kandidaten bleven twee remmen over. De eerste: 36 van de 172 nodige bepalingen vond de index helemaal
niet, omdat de deelvraag andere woorden gebruikt dan de wet (de woordenkloof). De tweede: goede bepalingen stonden bij de
verkeerde deelvraag. Twee proeven, allebei achter een vlag die standaard uit stond:

- `Zoekprofiel.wetstermen` (#1704): één modelstap per deelvraag vertaalt de deelvraag met het dossier naar zoektermen in
  de taal van de wet. De code houdt alleen woorden die in het zoekbereik voorkomen;
- `deelvraag_keuze.PER_WERKGEBIED` (#1703): het model kiest één keer voor alle deelvragen samen in plaats van per
  deelvraag.

**Criterium, vóór de run vastgelegd:** een vlag gaat aan als het aantal gekozen nodige bepalingen duidelijk stijgt, geen
set duidelijk zakt en de verkeerde deelvraag niet toeneemt.

## Wat er gemeten is

Via `azure-infra` → `eval`, op acceptatie, live tegen de graaf, met model `claude-sonnet-4-6`. Dezelfde tien sets (38
deelvragen; 7 referentiesets en LB-07..09 tegen de bevroren teamverwachting). Concept-verwachtingen.

- `bronselectie_wetstermen`, commit `2c2be684` (run 44164047803):
  `--kandidaten 80,80+wetstermen` (de lijst, alleen de vertaalstap kost tokens) en `--varianten wetstermen` (één ronde
  van het model, met afval per bepaling).
- `bronselectie_werkgebied` (run 44161584067): `--rondes 2 --werkgebied`.

De labels "niet bij de 40" in de log zijn een oude naam. Het gaat om de kandidatenlijst, die nu 80 lang is.

## Uitkomst: wetstermen

Nodige bepalingen op de kandidatenlijst (80), zonder en met wetstermen:

- Bestuurdersaansprakelijkheid 0,78 → 0,78
- Bezwaar/ontvankelijkheid 0,67 → 0,80
- Invorderbaarheid 0,82 → 0,73
- Kwijtschelding 0,57 → 0,81
- Rekeningafspraken 0,86 → 1,00
- Termijnen 0,50 → 0,50
- Verrekening 0,56 → 0,72
- LB-07 0,45 → 0,60
- LB-08 0,37 → 0,63
- LB-09 0,25 → 0,75
- **Totaal 93 → 122 van 172**

Recall op de nodige bepalingen na de keuze van het model, zonder → met wetstermen:

- Bestuurdersaansprakelijkheid 0,72 → 0,78
- Bezwaar/ontvankelijkheid 0,60 → 0,73
- Invorderbaarheid 0,73 → 0,73
- Kwijtschelding 0,52 → 0,81
- Rekeningafspraken 0,71 → 0,71
- Termijnen 0,12 → 0,25
- Verrekening 0,56 → 0,72
- LB-07 0,40 → 0,50
- LB-08 0,27 → 0,53
- LB-09 0,25 → 0,69

Afval van de 172, zonder → met wetstermen:

- niet gevonden 36 → 7
- gevonden maar niet bij de kandidaten 43 → 41
- bij de kandidaten maar niet gekozen 15 → 15
- gekozen 78 → 109

Verkeerde deelvraag: standaard 17, model 14, model met wetstermen 12.

Kosten: de vertaalstap kost 47,5k invoertokens en 2,9k uitvoertokens voor 38 deelvragen, ~1,3k per deelvraag. De hele
run (drie routes) kostte 114 aanroepen en 770k invoertokens.

Op geen enkele set zakt de recall na de keuze. Op de lijst zakt alleen Invorderbaarheid (0,82 → 0,73); na de keuze is die
set gelijk.

## Uitkomst: één keuze per werkgebied

Twee rondes. Het beeld is gemengd:

- LB-08 0,27 → 0,48
- Termijnen 0,19 → 0,28
- Invorderbaarheid 0,73 → 0,64
- de precisie is vaak hoger

Afval totaal (twee rondes samen, tegen het model per deelvraag in dezelfde run): gekozen 92 tegen 80, niet gekozen 25
tegen 13. Verkeerde deelvraag per ronde: 14 en 11, tegen 16 en 19 bij het model per deelvraag. ~1M tokens voor de run.

## Besluit

- **`wetstermen` gaat standaard aan.** Het criterium is gehaald: gekozen 78 → 109, op geen set lager na de keuze,
  verkeerde deelvraag 14 → 12, voor ~1,3k tokens per deelvraag.
- **`PER_WERKGEBIED` blijft uit.** Op de verkeerde deelvraag helpt de vlag, maar Invorderbaarheid zakt duidelijk en de
  winst is kleiner dan die van de wetstermen. Hij is niet gemeten samen met de wetstermen. Dat is de volgende meting,
  zodra de wetstermen op acceptatie staan.
- **Termijnen blijft de zwakste set** (0,25). De kandidatenlijst verandert er niet door de wetstermen (0,50). Er wordt
  gekozen tussen de kandidaten, en daar valt veel af: 8 van de 16 staan er niet op, 4 worden niet gekozen.
