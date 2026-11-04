# Meting bronselectie – rangsignaal per soort regeling (3 nov 2026)

Soort: *meting* · Hoort bij: PLAN spoor F *Vervolg*, de rangschikking van `bepaling_opties` · 0 modelcalls

## Vraag

Op 3 nov 2026 (`bronselectie-2026-11-03`) generaliseerde het zoeken, maar de rangschikking maar half: de
Leidraad Invordering overstroomde met haar lange divisies de top 8. Helpt een rangsignaal voor de soort regeling
(wet vóór beleidsregel) of een lengtecorrectie?

## Opzet

- Twee nieuwe vlaggen op `Zoekprofiel`:
  - `per_regeling`: de plaatsen gaan om de beurt naar de regelingen, de hoogste soort eerst (`overzicht.RANG`,
    uit `bwb:soort`), en binnen een regeling in de volgorde van de fusie. Er zijn geen gewichten.
  - `lengte`: de indexlijsten worden gedempt met √(mediaan/lengte), hoogstens 1.
- **Kiezen** op de twee ontwikkelsets (`bezwaar-ontvankelijkheid-concept`, `invorderbaarheid-deelvragen-concept`).
  De opname van die sets is live aangevuld (`--aanvullen`). Het besluit: `per_regeling` aan, `lengte` uit.
- **Blind** op een nieuwe held-out set `bestuurdersaansprakelijkheid-concept`: Iw 36/49 en Leidraad 36/49,
  4 deelvragen, 22 verwacht, waarvan 18 nodig. De set is gecommit vóór de code (#791) en één keer live gemeten
  (`--opnemen`) tegen acceptatie, na de herimport van 3 nov 2026.

## Uitkomst

| set | route | recall | recall nodig | precisie | uitgesloten | recall pool |
|---|---|---|---|---|---|---|
| bezwaar (ontwikkel) | vorige standaard | 0,42 | 0,47 | 0,22 | 0 | 0,84 |
| bezwaar (ontwikkel) | **+ per_regeling** | **0,47** | **0,53** | 0,25 | 0 | 0,84 |
| bezwaar (ontwikkel) | + lengte | 0,47 | 0,53 | 0,25 | 0 | 0,84 |
| invorderbaarheid (ontwikkel) | vorige standaard | 0,33 | 0,27 | 0,28 | 0 | 0,94 |
| invorderbaarheid (ontwikkel) | **+ per_regeling** | **0,39** | **0,36** | 0,28 | 0 | 0,94 |
| invorderbaarheid (ontwikkel) | + lengte | 0,22 | 0,27 | 0,22 | 0 | 0,94 |
| bestuurdersaansprakelijkheid (**held-out**) | standaard (met per_regeling) | 0,23 | 0,22 | 0,09 | 3 | 0,91 |
| bestuurdersaansprakelijkheid (**held-out**) | zonder per_regeling | 0,23 | 0,22 | 0,09 | 2 | 0,91 |
| bestuurdersaansprakelijkheid (**held-out**) | zonder fusie | 0,36 | 0,39 | 0,19 | 0 | 0,91 |
| bestuurdersaansprakelijkheid (**held-out**) | F3f (21 okt) | 0,32 | 0,39 | 0,16 | 0 | 0,46 |

## Wat het zegt

- `per_regeling` lost op wat het moest oplossen: op de ontwikkelsets komt de wet weer in de top 8, zonder
  verlies. Op de held-out set verandert het niets. Daar overstroomt de Leidraad niet; de top wisselt al af.
- **Het verlies op de held-out set zit in woorden, niet in de soort.** De verwachte bepalingen staan in de pool
  (0,91), maar de fusie zet ze laag. De analist schrijft in eigen woorden ("melden", "loonheffing",
  "aansprakelijk stellen"), de wet gebruikt andere ("mededeling", "loonbelasting", "aansprakelijkstelling").
  Een bepaling die het woord van de vraag letterlijk draagt (Iw art. 2: "belastingen") wint dan van de bepaling
  die het begrip regelt. Zonder fusie scoort de set hoger (0,36 / 0,39). Op de ontwikkelsets was dat juist
  andersom (bezwaar 0,37, invorderbaarheid 0,17): dit is spreiding over sets, geen richting.
- Er staan 3 uitgesloten bepalingen in de top (36a lid 1 twee keer, Leidraad 36.1 één keer). Ze raken de
  deelvraag ("aansprakelijk", "bestuurder"), en de stammen uit de afbakening ("bronbelasting",
  "faillissement") wegen daar niet tegenop.
- Niets is bijgesteld op de held-out set. Hij is na deze ene run een ontwikkelset.

## Volgende stap

De woordenkloof is een eigen ingreep, met een eigen nieuwe set ervoor: synoniemen of begrippen uit de graaf
(`bwb:definieertBegrip`, WTI-trefwoorden) of de similarity-index als extra lijst in de fusie. De rangschikking
op soort is daarmee af.

## Reproduceren

```bash
cd tools/graph-qa
uv run python -m eval.bronselectie_eval --intake --set bestuurdersaansprakelijkheid-concept   # offline op de opname
uv run python -m eval.bronselectie_eval --intake --set invorderbaarheid-deelvragen-concept
uv run python -m eval.bronselectie_eval --intake --set bezwaar-ontvankelijkheid-concept
```

`tests/test_bronselectie_eval.py` pint de getallen.
