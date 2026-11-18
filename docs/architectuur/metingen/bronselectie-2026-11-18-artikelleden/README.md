# Bronselectie – de andere leden van het artikel van een kernlid (18 nov 2026)

Soort: *meting* (bewijs: niet achteraf wijzigen) · Volgt op [`bronselectie-2026-11-18-keten/`](../bronselectie-2026-11-18-keten/README.md)

## Waarom

De plaatsdiagnose (`bronselectie_afbakening` met de buur per gemiste bepaling, #1727, run 44350651962) liet het volgende
zien. Van de 45 nodige bepalingen die niet bij de 80 kandidaten kwamen, stond bij 22 een ander lid van hetzelfde artikel
wél op de lijst. Voorbeelden zijn Iw 24 lid 2, 4 en 8, Awb 4:15 lid 2 en 4, Awir 24 lid 2 en 3, en AWR 67e lid 6. Daar
gaat het niet om zoeken maar om indeling: de jurist ziet het artikel, maar niet dat lid.

Om die reden voegde #1728 de methode `artikelleden` toe, standaard uit. Bij een opgenomen kernlid stelt ze de andere leden
van hetzelfde artikel voor, als aanverwant, hoogstens 12.

## Wat er gemeten is

Twee metingen op acceptatie, live tegen de graaf, op commit van #1728. Het gaat om dezelfde tien sets. De verwachtingen zijn
nog concept.

- `bronselectie_afhankelijkheden` (run 44358259071), zonder model, vanuit de verwachte kern.
- `bronselectie_keten` (run 44358614199). Hierin kiest het model één ronde (`claude-sonnet-4-6`, 414k invoertokens). Een
  jurist neemt op wat juist is, en daarop draaien de afhankelijkheden, gepaard.

## Uitkomst

Vanuit de verwachte kern, gevonden + via het artikel van de 59 (kandidaten tussen haakjes):

- Standaard: 24+10 (548)
- Met `artikelleden`: **34+10 (676)**

Beter op 5 sets, op geen enkele slechter.

Over de hele keten, nodige bepalingen van de 172:

- Na de keuze door het model: 110
- Na de afhankelijkheden, standaard: 126 (747)
- Na de afhankelijkheden, met `artikelleden`: **138 (912)**

Beter op 7 sets, op geen enkele slechter. Per set: bestuurdersaansprakelijkheid 16 → 17, bezwaar 12 → 13, invorderbaarheid
9 → 10, termijnen 9 → 11, verrekening 14 → 16, LB-07 15 → 17, LB-08 15 → 18. Kwijtschelding, rekeningafspraken en LB-09
bleven gelijk.

Met `artikelleden` staan er na de hele keten 12 nodige bepalingen meer. Dat kost 165 kandidaten meer (+22%), gemiddeld ruim
vier per deelvraag. Ze staan als aanverwant onder de kern, met de zin "staat in hetzelfde artikel als …".

## Besluit

`artikelleden` gaat standaard aan (`bronnen_vinden.STANDAARD`).

## Wat nog mist

Na de keten staan 34 van de 172 nodige bepalingen nergens. Een deel daarvan is een kwestie van zoeken: Awb 4:13, 6:8 en 1:2,
AWR 67n lid 3 en Iw 28 (buiten het zoekbereik). Een ander deel valt weg doordat de woordenroute en de pool om de beurt
worden genomen. Awir 16 lid 1, 5 en 6, AWR 26a lid 2 en Awb 4:93 lid 2 staan in de woordenroute vóór plaats 80, maar
halen de lijst niet.
