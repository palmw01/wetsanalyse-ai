# Detectorfixes art. 9 lid 5 IW 1990 (`IW05`) – oktober 2026

Soort: *meting* · Gestart: 6 oktober 2026

## Waarom

Een externe review van een TriG-export van acceptatie (art. 9 lid 5 IW 1990) wees vier fouten in de
detectoren aan. Alle vier zijn lokaal nagespeeld tegen de code:

| | Fout | Oorzaak |
|---|---|---|
| **A** | "het aanslagbiljet" krijgt Rechtssubject | een onderwerp in een normsegment krijgt altijd `[RS, RO, VAR]`; er is geen typering van de referent |
| **B** | "vervalt" en "vindt het eerste lid toepassing" krijgen geen Rechtsbetrekking | de normdetector zoekt een modaal of normatief gezegde; een rechtsgevolg als hoofdzin ziet hij niet |
| **C** | de hele eerste volzin wordt Afleidingsregel | de functiedetector neemt het hele segment, dat samenvalt met de normkandidaat |
| **D** | "de toepassing van de eerste volzin" en "de dagtekening van het aanslagbiljet" krijgen Voorwaarde | een nominalisatie krijgt altijd `[RF, VW, RO]`, ongeacht de context |

De fixes zijn een bewuste uitzondering op de stopregel van spoor A (zie `docs/PLAN.md`). Ze blijven
beperkt tot de detectoren: geen prompt, geen nieuwe rol en geen tegenbewijs-semantiek.

## Wat de meting wel en niet zegt

- De referentie is **provisional**. `IW05` is een **conceptcasus**: een AI-voorstel dat nog geen
  jurist zag (`docs/wetsanalyse/referentieset/concept/`).
- De winst wordt alleen op `IW05` gemeten. Die casus telt nooit mee in een v1-totaal; het harnas
  weigert het mengen.
- Op v1 is het criterium uitsluitend **geen regressie**. Daarbuiten mag alleen veranderen wat het
  criterium vooraf noemt.
- Geen van deze cijfers is een juridisch oordeel.

## Criteria vooraf

De criteria stonden vast vóór de nulmeting en de eerste fix, en worden niet meer gewijzigd. Hun
hashes (`tests/test_meetharnas.py` toetst ze):

```
20f69504488ab7b5c94264c40d96a916b98d7ea3dc442d4abe9ee7e62547f4fe  criteria/01-C.yaml
9b27e5ca48a039da18cd4ea2d66718d645dedc6b093be1bdfd07ae4a3ef132f6  criteria/02-B.yaml
c0af34d1e1a57437caa446bc88405e591ae375128beba2b9051ed334011e665f  criteria/03-A.yaml
dbff76c7f9f6c24ae4a09fed222eee74da81f4b6b6b9b8891e6492a14d562037  criteria/04-D.yaml
```

Toetsen gebeurt met `python -m eval.criteria criteria/<x>.yaml --audit-voor <voor> --audit-na <na>
[--model-voor … --model-na …]`. Een regel met `poort: false` is een waarneming.

## Nulmeting (`00-nul/`)

Code: het meetharnas op master `f9ab073`. Keten ongewijzigd: de v1-audit is identiek aan die van
master, op het manifest na.

| Bestand | Wat | Modelcalls |
|---|---|---|
| `audit.json` | `eval.detector_audit`: v1, diagnostiek en concepten | 0 |
| `kandidaat-v1.*`, `kandidaat-iw05.*` | `eval.kandidaat_eval`, met elementdekking voor IW05 | 0 |
| `model-v1.*` | `eval.compare_pipelines`, 16 casussen × 3 | 298 |
| `model-iw05.*` | idem, `--casussen concept:IW05`, × 5 | 55 |

Model `claude-sonnet-4-6` (zelfde als de baseline van 29 september), prompt `0901efefe061`,
`klasseverzameling`, gerichte review aan. Het volledige manifest staat in elk bestand.

**Uitkomst:**

- **IW05, 5 van 5 runs.** De keten maakt precies de fouten uit de export:
  - de hele eerste volzin wordt Afleidingsregel;
  - "het aanslagbiljet" (189–206) wordt Rechtssubject;
  - "de toepassing van de eerste volzin" wordt Voorwaarde;
  - "vervalt" en "vindt het eerste lid toepassing" krijgen geen markering;
  - Rechtsbetrekking krijgt 0% ankerdekking.
- **Deterministisch** (IW05): 8 van 17 conceptelementen hebben een kandidaat op hun plek; 4 gemengde
  unies.
- **v1**: micro-F1 50% (min–max 50–51%), ankerdekking 78%, ankerdekking per klasse in elke ronde
  gelijk. Rechtssubject 92%, Voorwaarde 79%.
- **Geel 0%.** In deze runs ontstond geen enkel twijfelgeval: geen `aandacht` en geen
  HUMAN_REVIEW. De export van acceptatie had dat wel. Dat verschil (model of profiel van acceptatie)
  valt buiten deze meting en is hier niet verklaard.

## Stappen

| Stap | Criterium | Uitslag | Map |
|---|---|---|---|
| 0 | – | nulmeting | `00-nul/` |
