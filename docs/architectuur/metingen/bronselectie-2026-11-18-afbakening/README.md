# Bronselectie – de afbakening per onderdeel lezen (18 nov 2026)

Soort: *meting* (bewijs: niet achteraf wijzigen) · Volgt op [`bronselectie-2026-11-18-belang-model/`](../bronselectie-2026-11-18-belang-model/README.md)

## Waarom

Bij een bronnenrun op acceptatie (LB-08) bleek dat de afbakening woord voor woord een lijst stammen werd. Ook "vallen",
"erbuiten", "andere" en "toeslage" werden zo een stam, net als het onderwerp zelf: "aansprak" bij bestuurdersaansprakelijkheid
en "kwijtsch" bij kwijtschelding. En bij "behalve beslag" werd "beslag" uitgesloten. Die stammen zetten bepalingen achteraan in
de woordenroute en halen ze weg uit de grondslag en de pool.

## Wat er gemeten is

`Zoekprofiel.afbakening_onderdelen` (#1717, standaard aan) leest per onderdeel van de opsomming één kernwoord, tegen het
onderwerp van het werkgebied (`zoektermen.uitsluitstammen`). De variant `zonder_afbakening` gebruikt de oude lezing.

`azure-infra` → `eval` → `bronselectie_afbakening`: `--kandidaten 80,80+zonder_afbakening --rangen`, op acceptatie, live
tegen de graaf, op commit `86ab37db` (run 44283533052). Het model kiest hier niet. De wetstermen kostten 47,5k invoertokens
en werden één keer per deelvraag gevraagd voor beide routes, dus de vergelijking is gepaard. Het gaat om dezelfde tien sets
en 38 deelvragen. De verwachtingen zijn nog concept.

## Uitkomst

Nodige bepalingen op de kandidatenlijst bij 80, oude → nieuwe lezing:

- Bestuurdersaansprakelijkheid 0,83 → 0,83
- Bezwaar/ontvankelijkheid 0,80 → 0,87
- Invorderbaarheid 0,73 → 0,73
- Kwijtschelding 0,86 → 0,86
- Rekeningafspraken 1,00 → 1,00
- Termijnen 0,56 → 0,56
- Verrekening 0,67 → 0,72
- LB-07 0,70 → 0,70
- LB-08 0,70 → 0,70
- LB-09 0,75 → 0,75
- **Totaal 128 → 130 van 172**, beter op 2 sets en op geen enkele slechter

Offline, op de opnames, steeg het aandeel nodige bepalingen in de pool van de zoekvragen bij bestuurdersaansprakelijkheid
van 0,889 naar 0,944 en bij bezwaar van 0,615 naar 0,692. Die pool is groter dan de lijst van 80, en daarom komt live minder
van die winst op de lijst.

## Conclusie

De nieuwe lezing blijft aan. De winst op de lijst is klein (+2), maar valt op geen enkele set tegen. De aanleiding was
bovendien een fout in hoe de afbakening werd gelezen, niet een afstemming op een set. De keuze door het model
(`bronselectie_afbakening_model`, ~800k tokens) heb ik niet gemeten.

Nog steeds staan 11 nodige bepalingen in geen enkele lijst, en 11 andere pas op plaats 121–200 in de woordenroute. Bij LB-08
staan artikel 16 en 20 niet in de woordenroute van deelvraag 1. Die vindt nu alleen de methode `opschrift` (#1716), in de
fase van de afhankelijkheden, en die methode valt buiten deze meting.
