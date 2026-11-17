# Bronselectie – een model kiest per deelvraag (17 nov 2026)

Soort: *meting* (bewijs: niet achteraf wijzigen) · Aanleiding: de pilot LB3 van Lex Bench
([`lex-bench-2026-11-17-pilot/`](../lex-bench-2026-11-17-pilot/README.md)) · Akkoord gebruiker: "Ja, start de meting"

## Waarom

In de pilot vond de index ongeveer de helft van de bepalingen die het team nodig vindt (32 van 66), maar de
rangschikking in code hield er 4 over. Twee ingrepen zonder model, offline gemeten en niet gebouwd:

- woorden van de deelvraag die de pool rond de gebeurtenis mist eerst: LB-07 0,05 → 0,10, verder gelijk;
- rangschikken op onderscheidende woorden: LB-07 0,10 → 0,25, maar op de woordenroute Bezwaar 0,60 → 0,40 en
  Invorderbaarheid 0,36 → 0,18.

## Wat er gemeten is

`eval/bronselectie_model_meting.py` via `azure-infra` → `eval` → `bronselectie_model`, op acceptatie, live tegen de
graaf en het model van de straat (`claude-sonnet-4-6`), commit `a477b8c2`, één run. Per set de route
`zoekvragen standaard (stap 8)` naast `model kiest (proef)` (`Zoekprofiel.model_kiest`, #1688): de code verzamelt per
deelvraag tot 40 kandidaten uit de pool en de woordenroute, het model wijst er hoogstens 8 aan met een rol. De
zeven referentiesets met deelvragen en de drie pilotcasussen tegen de bevroren teamverwachting; 38 deelvragen. De
instructie van de modelstap is vóór de meting geschreven en niet op deze sets bijgesteld. Alle verwachtingen zijn
`concept`.

## Uitkomst

Recall nodig, recall en precisie; eerst de route van nu, dan het model.

| set | recall nodig | recall | precisie |
|---|---|---|---|
| bestuurdersaansprakelijkheid-concept | 0,44 → 0,72 | 0,41 → 0,68 | 0,22 → 0,46 |
| bezwaar-ontvankelijkheid-concept | 0,40 → 0,53 | 0,37 → 0,42 | 0,19 → 0,61 |
| invorderbaarheid-deelvragen-concept | 0,46 → 0,55 | 0,33 → 0,61 | 0,19 → 0,56 |
| kwijtschelding-concept | 0,29 → 0,48 | 0,25 → 0,42 | 0,19 → 0,46 |
| rekeningafspraken-deelvragen-concept | 0,29 → 0,71 | 0,29 → 0,71 | 0,05 → 0,16 |
| termijnen-deelvragen-concept | 0,06 → 0,25 | 0,06 → 0,22 | 0,04 → 0,27 |
| verrekening-concept | 0,33 → 0,33 | 0,38 → 0,38 | 0,22 → 0,44 |
| LB-07 Beslistermijn | 0,05 → 0,25 | 0,08 → 0,25 | 0,00 → 0,55 |
| LB-08 Terugvordering toeslag | 0,03 → 0,23 | 0,03 → 0,26 | 0,04 → 0,44 |
| LB-09 Achteraf belasting | 0,12 → 0,19 | 0,10 → 0,16 | 0,06 → 0,27 |

- **Nergens slechter**: recall nodig op negen sets hoger, op Verrekening gelijk; precisie overal hoger.
- **Verbruik**: 38 aanroepen, 241.259 invoer- en 4.090 uitvoertokens, zonder cache: ~6,5k per deelvraag.
- **Grenzen**: één run, concept-verwachtingen, één model. De pilotcasussen zijn ook gebruikt om de fout te vinden,
  niet om de instructie af te stemmen. Het model kan wisselen tussen runs; een volgende meting doet er drie.

## Besluit

`model_kiest` gaat standaard aan, en de bronnenrun krijgt een model (budgetpoort vooraf, verbruik geboekt op
`bronnen-<run>`). Zonder model in de run kiest de code zoals voorheen.
