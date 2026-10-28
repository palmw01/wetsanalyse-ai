# Bronnen vinden met Lex – ablatie per methode (15 okt 2026)

Soort: *meting* · Hoort bij: PLAN spoor D, fase A (A4) · Set:
[`referentieset-bronselectie/invorderbaarheid-concept`](../../../wetsanalyse/referentieset-bronselectie/invorderbaarheid-concept/README.md)

> **Geen juridisch oordeel.** De set is een *concept*, opgesteld door de agent uit de graaf en het
> [invorderingsonderzoek](../../../wetsanalyse/onderzoek-invordering-2026-09-29/dossiers.md); geen
> jurist heeft hem vastgesteld. Het is bovendien één vraag met één kernartikel, en de set is gebruikt
> om een methode te verbeteren (de onderwerp-terugval, hieronder): het is daarmee een
> **ontwikkelset**. De cijfers zeggen iets over het mechanisme, niet over generalisatie.

## Wat er gemeten is

`tools/graph-qa/eval/bronselectie_eval.py` draait de ontdekmethoden (`agent/bronnen_vinden.py`) op de
invoer zoals de api hem vastlegt: kern **Invorderingswet 1990, art. 9**, analysevraag *"Wanneer is een
belastingaanslag invorderbaar?"*, naam *"Invorderbaarheid van belastingaanslagen"*. Live tegen de graaf
van acceptatie (via de MCP-proxy), en de graafantwoorden opgenomen in `graafantwoorden.json` naast de
set; offline afspelen geeft hetzelfde rapport (gecontroleerd, en bewaakt door
`tests/test_bronselectie_eval.py`). Geen model, dus geen tokens.

De set noemt 12 verwachte bepalingen (7 *nodig*: kern of afhankelijkheid), 7 uitgesloten bepalingen
en 1 bepaling buiten de graaf (Algemene termijnenwet – een open punt, niet in de noemer). Maten: zie de
docstring van het script. Een kandidaat raakt een bepaling als hij er gelijk aan is, erbinnen valt of
haar omvat; `exact` telt alleen gelijk of erbinnen.

## Drie rondes

**1. De oorspronkelijke standaard** (overzicht, verwijzing uit, verwijzing in, definitie, opbouw):

| configuratie | aantal | recall nodig | recall | r@10 | overbodig | onbeoordeeld |
|---|---|---|---|---|---|---|
| alleen overzicht | 2 | 0.00 | 0.00 | 0.00 | 0.00 | 2 |
| alleen verwijzing_in | 29 | 0.14 | 0.17 | 0.08 | 0.24 | 20 |
| standaard | 41 | 1.00 | 0.75 | 0.42 | 0.17 | 25 |
| standaard zonder verwijzing_in | 12 | 1.00 | 0.67 | 0.42 | 0.00 | 5 |
| standaard zonder opbouw | 39 | 0.71 | 0.58 | 0.42 | 0.18 | 25 |

Het overzicht vond niets bruikbaars: `onderwerp_uit` haalt geen onderwerp uit "Wanneer is een
belastingaanslag invorderbaar?", en met de hele vraag als onderwerp kwam er Leidraad-ruis uit.
**Reparatie**: zonder onderwerp in de vraag is de naam van het werkgebied het onderwerp.

**2. Na de reparatie van het overzicht.** Het overzicht vindt nu art. 8, 9 en 10, maar raakt zijn
plafond (40) met een rij artikelen uit een ander deel: 36 onbeoordeelde kandidaten, allemaal met rol
*kern*, die de goede naar beneden duwen. Met een kern voegde het **geen** recall toe:

| configuratie | aantal | recall nodig | recall | exact | r@10 | overbodig | onbeoordeeld |
|---|---|---|---|---|---|---|---|
| standaard (met overzicht) | 77 | 1.00 | 0.75 | 0.50 | 0.25 | 0.12 | 59 |
| standaard zonder overzicht | 39 | 1.00 | 0.75 | 0.50 | 0.42 | 0.18 | 23 |
| standaard zonder verwijzing_in | 48 | 1.00 | 0.67 | 0.33 | 0.25 | 0.04 | 39 |
| standaard zonder definitie | 70 | 1.00 | 0.75 | 0.17 | 0.25 | 0.13 | 56 |

**3. De nieuwe standaard** – zie [`meting.md`](meting.md) (volledig) en [`meting.json`](meting.json):

| configuratie | aantal | recall nodig | recall | exact | r@10 | overbodig | onbeoordeeld | rol juist |
|---|---|---|---|---|---|---|---|---|
| **standaard** (verwijzing uit, definitie, opbouw) | **10** | **1.00** | 0.67 | 0.33 | 0.67 | **0.00** | 3 | 0.50 |
| standaard zonder definitie | 3 | 1.00 | 0.67 | 0.00 | 0.67 | 0.00 | 0 | 0.50 |
| standaard zonder opbouw | 8 | 0.57 | 0.42 | 0.33 | 0.42 | 0.00 | 3 | 0.80 |
| standaard + overzicht | 48 | 1.00 | 0.67 | 0.33 | 0.25 | 0.04 | 39 | 0.62 |
| standaard + verwijzing_in | 39 | 1.00 | 0.75 | 0.50 | 0.42 | 0.18 | 23 | 0.56 |
| standaard + gelijkenis | 13 | 1.00 | 0.67 | 0.33 | 0.42 | 0.00 | 6 | 0.50 |

## Besluit (in de code: `bronnen_vinden.STANDAARD`, `ZONDER_KERN`)

Volgens de regel uit het plan – *een methode die niet aantoonbaar helpt, staat niet standaard aan*:

- **Standaard met een kern: verwijzing uit, definitie, opbouw.** 10 kandidaten in plaats van 41; alles
  wat nodig is gevonden, niets uitgeslotens voorgesteld.
- **Overzicht alleen zonder kern** – dan is de analysevraag het enige vertrekpunt. Met een kern voegde
  het geen recall toe en wel 36 onbeoordeelde kernkandidaten.
- **Verwijzing in uit.** Het vindt één aanverwant Leidraad-onderdeel (LI 9.1) extra en levert daarvoor
  alle zeven uitgesloten bepalingen (belasting- en invorderingsrente, verrekening, boetes) en 20
  onbeoordeelde: wat naar art. 9 verwijst, *gebruikt* het invorderbaarheidsmoment vaak alleen.
- **Gelijkenis uit.** Geen recall, drie onbeoordeelde kandidaten.
- **Definitie aan**, ook al is de recall zonder gelijk: alleen zij wijst de definities zelf aan
  (exact 0,33 → 0,00); zonder haar staat er alleen heel artikel 2.

## Wat open blijft

- **Gemist door de standaard**: IW 3 lid 1 en de Leidraad-onderdelen 9.1, 9.4 en 9.5 – allemaal
  *aanverwant*. Beleid bij een wetsartikel vindt geen van de standaardmethoden; `verwijzing_in` wel
  (9.1), met veel ruis. Kandidaat voor een gerichte methode: *beleid dat naar de kern verwijst*
  (verwijzing in, beperkt tot beleidsregels).
- **De rol klopt in de helft van de gevallen**: opbouw zet art. 8 en art. 10 op *aanverwant*, de set
  verwacht *afhankelijkheid* en *kern*. Art. 10 lid 1 begint met "In afwijking van artikel 9"; die
  verwijzing staat in art. 10 en wordt door de standaard (zonder `verwijzing_in`) niet gelezen.
- **Granulariteit**: verwijzing uit levert heel artikel 2 (de verwijzing wijst naar het artikel, niet
  naar onderdeel c). `exact` maakt dat zichtbaar.
- Eén vraag, één concept-set. Een tweede set (andere regeling, held-out) hoort er vóór een volgende
  wijziging aan de methoden bij.
