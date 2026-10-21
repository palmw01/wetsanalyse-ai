# Bepalingen per deelvraag – blind, op een nieuwe set (21 okt 2026)

Soort: *meting* · Hoort bij: PLAN spoor F3f · Set:
[`referentieset-bronselectie/bezwaar-ontvankelijkheid-concept`](../../../wetsanalyse/referentieset-bronselectie/bezwaar-ontvankelijkheid-concept/README.md)

> **Geen juridisch oordeel.** De set is een *concept*: de agent stelde hem op uit de letterlijke tekst
> in de graaf, en geen jurist heeft hem vastgesteld. Het zijn vier deelvragen bij één analysevraag. De
> cijfers zeggen iets over het mechanisme, niet over generalisatie.

## Wat er gemeten is

`tools/graph-qa/eval/bronselectie_eval.py --intake` draait per deelvraag twee routes:

- **`bepaling_opties`** (F3f) is wat de intake per deelvraag aanbiedt en wat de deelvragen-agent nu
  zoekt. De invoer is de deelvraag, het dossier en de afbakening, binnen de gekozen regelingen
  (Awb en AWR). Er komen hoogstens 8 opties uit, plus hoogstens 2 die als "buiten de afbakening"
  gemarkeerd zijn.
- **De vorige deelvraagmethode** dient als ijkpunt: het overzicht per deelvraag, op artikelniveau,
  hoogstens 15. Dat is `bronnen_vinden._deelvraag` zoals het tot deze PR was.

De meting draaide live tegen de graaf van acceptatie, via de MCP-proxy, en de antwoorden zijn
opgenomen in `graafantwoorden.json` naast de set. Offline afspelen geeft hetzelfde rapport; dat is
gecontroleerd en wordt bewaakt door `tests/test_bronselectie_eval.py`. Er is geen model gebruikt.

**Blind.** De set staat in een eigen commit, vóór de meetcode. Deze uitkomst is de eerste run. Daarna
zijn twee bijstellingen van de rangschikking op deze set uitgeprobeerd; ze staan hieronder. Geen van
beide hielp, dus de gemeten code is de blinde.

## Uitkomst

| route | opties | recall | recall nodig | exact | precisie | uitgesloten | uitgesloten gemarkeerd |
|---|---|---|---|---|---|---|---|
| **bepaling_opties** | 32 (8 per deelvraag) | **0,21** | 0,20 | **0,21** | 0,13 | 1 | 2 |
| vorige deelvraagmethode | 21 | 0,16 | 0,20 | 0,05 | 0,10 | 2 | 0 |

Per deelvraag (gevonden / verwacht) voor `bepaling_opties`:

| deelvraag | gevonden |
|---|---|
| termijn en aanvang | 1/6 |
| eisen aan het bezwaarschrift | 2/5 |
| te laat ingediend | 1/3 |
| wie bezwaar kan maken | 0/5 |

De volledige uitvoer staat in [`meting.md`](meting.md) en [`meting.json`](meting.json).

**Wat beter is:**

- *Exact* gaat van 0,05 naar 0,21. Een optie is nu het lid zelf, waar de vorige methode een heel
  artikel aanwees.
- Wat aan de afbakening raakt, valt niet meer stil weg. Het staat gemarkeerd onderaan. In deze set
  waren dat twee van de uitgesloten bepalingen, en geen van beide stond aangevinkt.

**Wat zwak is:** de recall in absolute zin. In de bewuste top 8 vindt Lex één op de vijf verwachte
leden.

## Diagnose: de rangschikking, niet het zoeken

De verwachte leden zitten in de treffers van de index, meestal hoog. Een losse diagnose langs dezelfde
proxy wees uit:

- Awb 6:7 staat 4e bij de artikelen;
- 7:1 lid 1 staat 3e bij de leden;
- AWR 22j staat 2e;
- 6:9 lid 1 staat 10e.

De rangschikking daarna gooit ze eruit. Die telt hoeveel termen van de deelvraag letterlijk in de
tekst staan, en dat gaat op twee punten mis:

- **Geen stemming.** "ingediend" raakt "indienen" niet, en "bezwaarschrift" raakt "bezwaar- of
  beroepschrift" niet. Awb 6:7 raakt daardoor maar één term.
- **Geen gewicht.** Een algemeen woord als "termijn" of "maken" telt even zwaar als
  "belastingaanslag". AWR-leden die toevallig "belastingaanslag" en "termijn" noemen, winnen zo van
  de Awb-kern.

**Twee bijstellingen geprobeerd, op deze set, na de blinde run:**

1. de score van de index als eerste sleutel: recall 0,16;
2. een gewicht per term naar zeldzaamheid: recall 0,16.

Geen van beide hielp, en beide zijn teruggedraaid. Verder bijstellen op deze set zou er een
ontwikkelset van maken.

## Wat dit betekent

- `bepaling_opties` is beter dan wat er was. De intake en de deelvragen-agent gebruiken hem daarom
  allebei.
- Als enige bron van bepalingen is hij nog te zwak. Lex zegt op het kaartje dat de analist ook zelf
  artikelen kan noemen. Opgenomen bronnen blijven verder aan te vullen vanuit het gesprek ("Zoek
  bepalingen bij de deelvragen").
- **Vervolg:**
  - de rangschikking met stemming en een structuursignaal: de kop van het deel, zoals "Algemene
    bepalingen over bezwaar en beroep";
  - gemeten op een **nieuwe** set, want deze is na vandaag een ontwikkelset.
