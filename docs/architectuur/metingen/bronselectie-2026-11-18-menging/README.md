# Bronselectie – een verhouding tussen de woordenroute en de pool (18 nov 2026)

Soort: *meting* (bewijs: niet achteraf wijzigen) · Volgt op [`bronselectie-2026-11-18-artikelleden/`](../bronselectie-2026-11-18-artikelleden/README.md)

## Waarom

Na de hele keten misten nog 34 van de 172 nodige bepalingen (#1730, run 44366365852). Zes daarvan stonden in de
woordenroute vóór plaats 80, maar haalden de kandidatenlijst toch niet: Iw 8 lid 1, Awb 4:93 lid 2, Awir 16 lid 1, 5 en 6
en Awir 19 lid 1. De menging `afwisselend` neemt de woordenroute en de pool rond de gebeurtenis om en om, dus de pool vult
de helft van de 80 plekken.

#1731 voegde daarom twee mengingen toe, standaard uit. Bij `woorden_2` krijgt de woordenroute twee plekken per plek van de
pool, bij `woorden_3` drie.

## Wat er gemeten is

De meting is `bronselectie_menging` (run 44373117987), op commit `74463710` en live op acceptatie. Het model kiest daarin
niet: de meting kijkt alleen wat er bij de 80 kandidaten staat. De varianten zijn gepaard, met dezelfde wetstermen (47,5k
invoertokens). Het gaat om tien sets, met concept-verwachtingen.

## Uitkomst

Nodig bij de kandidaten, van de 172:

- `afwisselend` (standaard): **126**
- `woorden_2`: 123
- `woorden_3`: 121

Per set, gevonden van wat nodig is:

- **Slechter:**
  - termijnen (16): 9 → 6 met `woorden_2`, 5 met `woorden_3`;
  - bezwaar (15): 13 → 12 bij beide;
  - kwijtschelding (21): 18 → 17 met `woorden_3`;
  - LB-07 (20): 13 → 12 met `woorden_3`.
- **Beter:** LB-08 (30), 21 → 22 met `woorden_2` en 23 met `woorden_3`.
- **Gelijk:** de andere sets.

De standaard komt hier uit op 126; in run 44350651962 was dat 127. Dat verschil komt van de wetstermen, die het model per
run opnieuw maakt.

## Besluit

De menging blijft `afwisselend`. De pool rond de gebeurtenis brengt bepalingen binnen die de woordenroute pas veel later
noemt. Bij termijnen is dat het sterkst. Wat de woordenroute met meer plekken wint, verliest de lijst aan de pool. Beide
varianten blijven bestaan als meetoptie (`--kandidaten 80+woorden_2`), maar niet als standaard.

## Wat nog mist

De zes bepalingen hierboven vragen een andere oplossing dan een vaste verhouding. Een mogelijke richting is de dubbelen
tussen woordenroute en pool eerst te tellen, zodat een plek die de pool aan een bepaling uit de woordenroute geeft niet
verloren gaat. Dat is nog niet onderzocht.
