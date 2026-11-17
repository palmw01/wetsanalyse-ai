# Bronselectie – het model kiest, drie rondes en afval per bepaling (17 nov 2026)

Soort: *meting* (bewijs: niet achteraf wijzigen) · Volgt op [`bronselectie-2026-11-17-model/`](../bronselectie-2026-11-17-model/README.md)
en de analyse van de bronselectie (17 nov 2026) · Akkoord gebruiker: "voer alles in 1 keer uit zonder akkoord te vragen"

## Wat er gemeten is

`eval/bronselectie_model_meting.py --rondes 3 --varianten definitie_brug,verwijzingen` via `azure-infra` → `eval` →
`bronselectie_model`, op acceptatie, live tegen de graaf en `claude-sonnet-4-6`, commit `661b7907`. Dezelfde tien sets
(38 deelvragen) als de vorige meting: de zeven referentiesets met deelvragen en LB-07..09 tegen de bevroren
teamverwachting. Alle verwachtingen zijn `concept`.

- de route van vóór het model (`zoekvragen standaard (stap 8)`);
- het model, drie rondes;
- twee varianten die de pool verbreden, elk één ronde: `definitie_brug` en `verwijzingen` in de kandidaten;
- per nodige bepaling waar ze afviel, uit de eerste modelronde.

## Uitkomst

Recall nodig: eerst de route zonder model, dan het model (gemiddelde en spreiding over drie rondes), dan de varianten.

| set | zonder model | model (3 rondes) | definitie_brug | verwijzingen | precisie zonder → model |
|---|---|---|---|---|---|
| Bestuurdersaansprakelijkheid | 0,44 | 0,72 (0,72–0,72) | 0,67 | 0,72 | 0,22 → 0,46 |
| Bezwaar/ontvankelijkheid | 0,40 | 0,53 (0,53–0,53) | 0,53 | 0,53 | 0,19 → 0,61 |
| Invorderbaarheid (deelvragen) | 0,46 | 0,55 (0,55–0,55) | 0,55 | 0,55 | 0,19 → 0,56 |
| Kwijtschelding | 0,29 | 0,48 (0,48–0,48) | 0,52 | 0,48 | 0,19 → 0,46 |
| Rekeningafspraken | 0,29 | 0,62 (0,57–0,71) | 0,57 | 0,57 | 0,05 → 0,14 |
| Termijnen | 0,06 | 0,21 (0,19–0,25) | 0,25 | 0,19 | 0,04 → 0,24 |
| Verrekening | 0,33 | 0,33 (0,33–0,33) | 0,33 | 0,33 | 0,22 → 0,46 |
| LB-07 Beslistermijn | 0,05 | 0,25 (0,25–0,25) | 0,25 | 0,25 | 0,00 → 0,53 |
| LB-08 Terugvordering toeslag | 0,03 | 0,23 (0,23–0,23) | 0,23 | 0,23 | 0,04 → 0,44 |
| LB-09 Achteraf belasting | 0,12 | 0,19 (0,19–0,19) | 0,31 | 0,19 | 0,06 → 0,33 |

**Waar de nodige bepalingen afvielen** (172 over de tien sets, eerste modelronde):

| fase | aantal | aandeel |
|---|---|---|
| niet gevonden (index en pool rond de gebeurtenis) | 36 | 21% |
| gevonden, maar niet bij de 40 kandidaten | 63 | 37% |
| bij de 40, niet gekozen door het model | 8 | 5% |
| gekozen | 65 | 38% |

Verbruik: 190 aanroepen, 1.206.931 invoer- en 20.251 uitvoertokens, zonder cache.

## Wat dit zegt

- **Het model is stabiel**: op acht sets is de recall in alle drie de rondes gelijk, op twee wisselt ze iets (Rekeningafspraken
  0,57–0,71, Termijnen 0,19–0,25). De winst van de vorige meting blijft staan.
- **Het model is niet de rem**: van wat bij de 40 kandidaten staat, kiest het bijna alles wat nodig is (65 van 73). De grootste
  post is **gevonden, maar niet bij de 40** (63): het samenstellen van de kandidatenlijst laat de helft van wat de index vindt vallen.
  Daarna de woordenkloof: 36 bepalingen vindt de index helemaal niet (o.a. LB-09: navordering en vergrijpboete; LB-08:
  herziening en verrekening van het voorschot).
- **`definitie_brug`** helpt waar de woordenkloof een definitie heeft (LB-09 0,19 → 0,31, Kwijtschelding 0,48 → 0,52, Termijnen
  0,21 → 0,25) en kost iets op twee sets (Bestuurdersaansprakelijkheid 0,72 → 0,67, Rekeningafspraken binnen de spreiding).
  Eén ronde: niet beslissend.
- **`verwijzingen` in de kandidaten** verandert niets.

## Grenzen

Eén model, concept-verwachtingen, ontwikkelsets. De afval komt uit de eerste ronde. In de log van de eval-job staan de
afvalregels per set soms naast de verkeerde set (gelijke tijdstempels); de totalen en de setregels zelf kloppen.
