# Bronselectie – de blinde set Verrekening (stap 8 van het plan Termijnen, 16 nov 2026)

Soort: *meting* · Hoort bij: [het plan](../bronselectie-2026-11-16-plan/README.md), stap 8 · Akkoord gebruiker: 16 nov 2026

## Vastgelegd vóór de meting

- Set: `docs/wetsanalyse/referentieset-bronselectie/verrekening-concept/set.json`, ongewijzigd sinds commit `b3e0215d`
  (4 nov 2026), sha256 `03f502b01ba21db1b751d7d3c16688795ca53920bbeae60fe2a50600f979384d`.
- Opgesteld vóór de code van het plan Termijnen. Er bestond nog geen opname (`graafantwoorden.json`), dus er is offline
  nooit op gemeten. Tijdens het plan is de set niet gelezen of gedraaid; de vlaggen en hun grens (`AANDEEL_STERK`) zijn op
  de zes ontwikkelsets gekozen.
- Vier deelvragen, gebeurtenis *verrekening*, 21 verwachte bepalingen (18 nodig), 3 uitgesloten.
- Wat er gemeten wordt, ligt hier vast vóór de opname: `--intake --b2 --plan` en `--zoekvragen` met de code van stap 7
  (`claude/bronselectie-7-pr-e`), en de combinatie uit het voorstel (`termen_idf`, `verwijzingen`, `brug_omschrijving`,
  `overzicht_streng`) op de woordenroute en de zoekvragenroute. De drempel: een vlag of de combinatie mag op deze set niet
  slechter zijn dan de standaard, op recall nodig.

## Uitkomst

Gemeten met de code van stap 7 (`8f11011f`, branch `claude/bronselectie-7-pr-e`). De opname is gemaakt op acceptatie, en de
herhaling offline gaf precies hetzelfde rapport. Recall nodig, eerst de standaard, dan met de vlag.

**De combinatie uit het voorstel** (`termen_idf`, `verwijzingen`, `brug_omschrijving`, `overzicht_streng`):

- woordenroute: 0,06 → 0,06 (precisie 0,031 → 0,026);
- zoekvragenroute: 0,33 → 0,33;
- hele run: 44 → 28 kandidaten, 18 → 2 zonder deelvraag, 7 van 18 verwacht in beide.

**Oordeel: de combinatie haalt de drempel** (nergens slechter op recall nodig), maar toont op deze set geen winst in de
recall. De winst is de ruis die wegvalt: het overzicht.

**Per vlag**, op de zoekvragenroute (de bronnenrun met een gebeurtenis):

- `termen_idf`, `beurt_sterk`, `overzicht_streng`, `stam_heel`, `brug_omschrijving`: 0,33 → 0,33.
- `woorden_voor_pool`, `vraagvorm_eigen_woord`: 0,33 → **0,22**. Dat bevestigt het besluit om ze niet aan te zetten.
- `definitie_brug`: 0,33 → **0,39**, en op de woordenroute 0,06 → 0,11. Dit is op de definities die al in de graaf staan,
  zonder route 4.

**Wat dit wel en niet bewijst.**

- `stam_heel` kostte op twee ontwikkelsets en is hier gelijk. Hij blijft uit.
- `definitie_brug` was op de ontwikkelsets gelijk, en zit niet in het voorstel. Dat hij hier helpt, mag geen reden zijn om
  hem alsnog aan te zetten: dan is de set niet langer blind voor die keuze. Hij is een kandidaat voor een volgende ronde,
  met een nieuwe blinde set.
- De woordenroute staat op deze set laag (0,06), ook in de standaard. `zonder per_regeling` geeft 0,11. Dat sluit aan bij de
  bevinding van stap 1b: de rangschikking binnen de woordenroute is het zwakke punt.
- Deze set is nu gebruikt. Een volgende ronde vraagt een nieuwe blinde set uit een ander werkgebied.

De rapporten staan in deze map; de opname in `verrekening-concept/graafantwoorden.json`.
