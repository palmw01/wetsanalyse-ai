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
