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
| 1 – C | 01-C | **geslaagd** | [`01-C/`](01-C/README.md) |
| 2 – B | 02-B | **geslaagd** (waarneming B7 lager, variatie) | [`02-B/`](02-B/README.md) |
| 3 – A | 03-A | **niet geslaagd op A8**: twee niet-voorziene, wel bedoelde v1-wijzigingen, geen anker verloren | [`03-A/`](03-A/README.md) |
| 4 – D | 04-D | **geslaagd** | [`04-D/`](04-D/README.md) |
| totaal | – | nulmeting tegen stap 4 | [`05-totaal/`](05-totaal/) |

Elke stap is gemeten op de code van zijn eigen commit, in een aparte worktree. De meetcommits zijn
codegelijk aan de PR-commits na de rebase (`git diff --quiet <meetcommit> <pr-commit> -- tools api
packages`); alleen de docs verschillen.

## Uitkomst (nulmeting → stap 4)

**IW05, diagnostisch, × 5** (`05-totaal/vergelijk-iw05.md`):

| maat | voor | na |
|---|---|---|
| micro-F1 | 29% | 37% |
| ankerdekking | 41% | 53% |
| exacte span | 47% | 65% |

Alle drie liggen buiten de spreiding. Per fout in 5/5 runs:

- volzin 1 is geen Afleidingsregel meer, "zoveel … als …" wel;
- "het aanslagbiljet" is Rechtsobject;
- "De eerste termijn vervalt …" wordt gemarkeerd, als Rechtsfeit, terwijl het concept
  Rechtsbetrekking zegt;
- "de toepassing van de eerste volzin" is Rechtsfeit in 4/5 runs, geen Voorwaarde meer.

Dit is een conceptcasus: dat het model de conceptklasse vaker raakt, is geen juridisch oordeel.

**v1, 16 × 3** (`05-totaal/vergelijk-v1.md`):

| maat | voor | na |
|---|---|---|
| ankerdekking | 78% | 79% |
| micro-precisie | 37% | 35% |
| micro-F1 | 50% | 49% |

- **Ankerdekking per klasse.** Het minimum is voor geen enkele klasse lager, en geen v1-anker gaat
  verloren.
- **Precisie** daalt met 2 procentpunt, buiten de band van drie rondes.

**Bevinding over de spreiding.** Drie rondes onderschatten de variatie tussen runs. De
controlegroep (`05-totaal/controlegroep.txt`) maakt dat zichtbaar:

- De acht v1-casussen met **bit-identieke classifierinvoer** schommelen in precisie tussen 48,6%
  en 50,0%.
- In stap C en B is de code op v1 identiek aan de nulmeting. Toch verschuift de precisie in de
  geraakte casussen daar al tussen 28,3% en 30,3%.
- In A en D ligt ze op 27,6–28,1%, net onder die band.

Een kleine precisiekost van ongeveer 1–2 procentpunt in de geraakte casussen (IW01–04, AWB01–03,
WZT01) is dus niet uit te sluiten. Hij komt van extra Rechtsobject-voorstellen. Aantonen kan het pas
met 5 rondes.

**Lessen voor het harnas.** De vlag "buiten spreiding" is een signaal om uit te zoeken, geen bewijs.
Een controlegroep met ongewijzigde invoer hoort bij elke vergelijking.

**Gemengde unies.** Op IW05 verdwijnt de unie op volzin 1. Op E17 ("vindt het eerste lid
toepassing") staan nu twee echte hypothesen: Afleidingsregel uit de functiedetector en
Rechtsbetrekking uit de gevolgdetector. Het model kiest daar 5/5 Afleidingsregel.

Of een klassegebonden bewijsmodel (EvidenceHypothesis) dat beter zou beslissen, hoort bij V7. Het is
ook reviewvraag 1 van het concept.

## Open na deze fixes

- **Relaties.** De ALS→DAN-verbanden en de invoer en uitkomst van de afleiding ontbreken nog
  (kandidaten 4 en 9).
- **Generieke naamwoordgroepen.** "De eerste termijn", "het jaar" en "de inkomstenbelasting" houden
  Rechtssubject als hypothese (kandidaat 2).
- **Nesting.** "de dagtekening" is nog een eigen kandidaat binnen de tijdsaanduiding (kandidaat 10).
- **"die in de dagtekening … is vermeld"** valt buiten de nominalisatiecontexten.
- **Klassekeuze van het model.** Het kiest Rechtsfeit voor "vervalt …" en Afleidingsregel voor
  "vindt … toepassing". Of dat juist is, beslist een jurist.
- **Twijfel.** Geel kwam in geen enkele lokale run voor, op acceptatie wel. Dat verschil is niet
  verklaard.
