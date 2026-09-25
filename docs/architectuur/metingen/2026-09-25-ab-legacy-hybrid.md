# Meting 25 sep 2026 — legacy tegen hybrid_v1 (bijlage bij ADR-001)

Soort: *meting* · Harnas: `tools/graph-qa/eval/compare_pipelines.py` · Model: `claude-sonnet-4-6`
(providerdefault-temperatuur) · 16 ontwikkelcasussen × 3 herhalingen · referentie: `provisional`

**Dit is geen kwaliteitsoordeel.** De referentieset bestaat uit conceptmarkeringen die nog niet
juridisch zijn beoordeeld. Recall heet hier daarom *ankerdekking*. De cijfers zeggen welke kant het
op gaat en waar de fouten zitten, niet of een annotatie juridisch juist is.

## Uitvoering

1. **Nachtmeting** (96 runs, 0 fouten): beide routes op de code van #508.
2. **Correctie referentie:** RVV01–03 "voetgangers" wees naar het woorddeel in
   "voetgangerslichten" (zie `docs/wetsanalyse/referentieset/README.md`). De nachtmeting is opnieuw
   geanalyseerd tegen de gecorrigeerde referentie ("hybrid vóór").
3. **Hermeting hybrid_v1** (48 runs, 0 fouten) met de fixes van PR 17 ("hybrid ná"). Legacy is niet
   opnieuw gemeten: de code is ongewijzigd.

## Uitkomst

| maat | legacy | hybrid vóór | hybrid ná (PR 17) |
|---|---:|---:|---:|
| micro-F1 | 39% | 46% | **49%** |
| precisie | 34% | 33% | 35% |
| ankerdekking | 47% | 75% | **84%** |
| macro-F1 | 45% | 56% | **62%** |
| precisie, alleen onbetwist | 48% | 33% | 35% |
| exacte span | 52% | 81% | **88%** |
| detectie stabiel over runs | 64% | 75% | 84% |
| klasse unaniem over runs | 92% | 90% | 93% |
| modelaanroepen per run | 3,9 | 1,3 | 1,3 |
| seconden per run | 81 | 30 | ~30 |
| elementen per run | 7,1 | 11,7 | 12,2 |

Foutcategorieën (ADR-001 §12), over drie rondes:

| | SPAN_ERROR | CLASSIFICATION_ERROR | CANDIDATE_MISSED |
|---|---:|---:|---:|
| legacy | 61 | 13 | 55 |
| hybrid vóór | 38 | 17 | 8 |
| hybrid ná | 21 | 12 | 7 |

F1 per klasse, hybrid vóór → ná: Parameter 61 → 88%, Operator 26 → 43%, Tijdsaanduiding 64 → 78%,
Afleidingsregel 67 → 77%, Variabele 46 → 50%, Rechtsbetrekking 71 → 65%, Rechtssubject 51 → 48%,
Voorwaarde 63 → 62%, Rechtsobject 20 → 21%, Brondefinitie 50 → 50%, Delegatie 100 → 100%.

## Wat eruit volgt

- **Grenzen:** de spankeuze door het model was de grootste foutbron. Het koos 82× een optie en was
  daarmee 8× raak, terwijl de kandidaatspan 23× raak was geweest. Die keuze staat nu uit
  (`CLASSIFIER_SPANKEUZE`).
- **Precisie** blijft de zwakke plek: hybrid stelt meer voor dan de conceptset bevat, en precisie
  tegen een onvolledige ankerset is geen kwaliteitsoordeel. Of die extra voorstellen terecht zijn,
  kan alleen een beoordeelde referentie laten zien.
- **Rechtsobject en Rechtssubject** blijven laag. Dat is semantiek (drager van recht/plicht tegenover
  een grammaticale rol), en precies waar het model nog het meest moet doen.
- **Legacy weghalen (PR 18)** vraagt een beoordeelde (`adjudicated`) referentieset.
