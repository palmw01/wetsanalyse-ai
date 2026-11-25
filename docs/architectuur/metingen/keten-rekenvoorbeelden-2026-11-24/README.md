# Meting keten-rekenvoorbeelden: een rekenvoorbeeld is geen norm, maar wel bron (24 nov 2026)

Soort: *meting*. Code: `389289a6` (voor, master) en de branch `claude/keten-rekenvoorbeelden-c83ceb` (na; `voorbeeld.py`
versie 1). Zonder model. Plan: [`plan-lessen-termijnen-bibliotheek.md`](../../plan-lessen-termijnen-bibliotheek.md), V8
en M2. Licht regime (ADR-010): één run, gerichte set, de geraakte vorm.

## Eerst: waarom zijn de voorstellen in Leidraad 9.5 afgewezen?

De audit van de laag van Leidraad Invordering 2008, 9.5 (werkgebied Termijnen, revisie 11, geaccordeerd), gelezen via de
acceptatie-MCP, alleen lezen. Van de 67 voorstellen van de keten (19 nov 2026) zijn er 16 geaccordeerd, 1 gecorrigeerd en
50 afgewezen. De opmerking bij elke afwijzing:

| reden van de jurist | aantal | wat |
|---|---|---|
| "Rekenvoorbeeld, niet de regel." | 42 | 12 losse data ("op 31 oktober", "15 maart"), 5 keer de duur in het voorbeeld ("één maand", "zes weken"), 13 variabelen ("de betalingstermijn", "de dagtekening", "de termijn", "het jaartal", "een schrikkeljaar"), 7 operatoren ("vervalt op", "valt op", "en", "tenzij", "dan wel"), 3 voorwaarden, 1 afleidingsregel, 1 rechtsobject |
| "Deel van een groter element dat al gemarkeerd is (dubbel)." | 6 | in de algemene regel (de derde zin), niet in een voorbeeld |
| "'is gesteld op' kent de termijn een waarde toe" | 2 | in de aanhef, niet in een voorbeeld |
| klasse gelijkgetrokken (gecorrigeerd) | 1 | in de algemene regel |

Wat dat zegt:

- **Bevestigd: het gaat om de voorbeeldzinnen.** 42 van de 50 afwijzingen liggen in de vier voorbeeldzinnen. De zinnen
  zijn met een generiek signaal te herkennen (hieronder): drie met een inleiding of een uitkomst uit een concreet geval,
  één ("Is de betalingstermijn zes weken en is de dagtekening 15 maart, vervalt de termijn op 26 april.") zonder
  inleidend woord.
- **Weerlegd: het zijn niet vooral losse data en bedragen.** Bedragen staan er niet in. Losse data zijn 12 van de 42; de
  rest zijn de woorden van het voorbeeld zelf. De jurist wees het voorbeeld als geheel af, ook "het jaartal" en "een
  schrikkeljaar", die de praktijk nodig heeft en die alleen in het voorbeeld staan. Dat was vóór de regel in de skill
  (`references/markeringslijst.md`, 24 nov 2026): "wijs een markering in een voorbeeld niet af omdat het maar een
  voorbeeld is". Die afwijzingen zeggen dus deels iets over de beoordeling, niet over de keten.
- **De duur in een voorbeeld is de parameter.** De referentie markeert "één maand" en "zes weken" ook binnen de
  voorbeeldzinnen als parameter (6 formuleringen in 9.5). Een duur valt daarom niet onder de concrete waarden die de keten
  weglaat; de skill noemt ook alleen "data en bedragen".

## Wijziging

`tools/graph-qa/agent/jas_pipeline/voorbeeld.py`, na de fusie en vóór de besluiten, zonder model:

1. **Herkennen**, per zin, met twee generieke signalen, elk met een concrete waarde als uitkomst:
   - een *inleiding* ("bijvoorbeeld", "ter illustratie", "stel dat", "dus", of een conclusie als "dan houdt dat in dat",
     "dit betekent dat") met een datum of bedrag als gegeven ná de inleiding; bij een conclusie begint het voorbeeld bij de
     inleiding, want wat ervoor staat is de regel;
   - een *uitkomst uit een concreet geval*: een voorwaardelijke zin ("als …, dan …", of met de persoonsvorm voorop) met een
     kalenderdatum als gegeven in de voorwaarde en als uitkomst in de hoofdzin.
   - Geen voorbeeld: een datum als grens ("vóór 1 april", "met ingang van", "na"), een bedrag zonder inleiding (een
     drempel), een duur alleen, een inleiding zonder concrete waarde.
2. **Toepassen** op elke kandidaat die helemaal binnen een voorbeeld ligt: een datum of bedrag wordt afgewezen
   (`VOORBEELD_WAARDE`); de klassen van een norm vervallen, en blijft er niets over dan afgewezen
   (`VOORBEELD_GEEN_NORM`); de rest krijgt het kenmerk `IN_VOORBEELD`. Dat kenmerk wijst geen klasse aan, houdt een vast
   besluit niet tegen, en staat in de signalen voor de classifier, in de toelichting voor de jurist en in het bewijs voor
   de reviewer.
3. **De reviewer** krijgt één zin (`review.py`, `SYSTEEM`): een fragment met `IN_VOORBEELD` staat in een rekenvoorbeeld,
   geen norm maar wel bron; niet afwijzen omdat het een voorbeeld is, houden als het een kenmerk aanduidt. De tekst tussen
   de methodemarkers verandert niet (`genereer_jas_klassen.py --check` groen); de modelverzoeken zijn opnieuw vastgelegd.

## Meting zonder model

`meting.py` op `acc.json` (de tekst en de elementen van de vier lagen op acceptatie); uitvoer `uit.json`. De referentie
is lokaal (materiaal van derden); in `uit.json` staan alleen aantallen.

**De voorbeeldzinnen**: in 9.5 vier van de vijf zinnen (de derde, de algemene regel, niet); in IW 9 lid 1 en 5 en
Leidraad 9.1 geen.

**Tegen de beslissingen op acceptatie** (elementen van Lex; per element de kandidaat met dezelfde grens):

| bepaling | elementen | geaccordeerd: geraakt | afgewezen: valt weg | afgewezen: kenmerk | afgewezen: gelijk |
|---|---|---|---|---|---|
| IW 9 lid 1 | 6 | 0 van 6 | 0 | 0 | 0 |
| IW 9 lid 5 | 34 | 0 van 25 | 0 | 0 | 5 |
| Leidraad 9.1 | 17 | 0 van 14 | 0 | 0 | 3 |
| Leidraad 9.5 | 67 | **0 van 16** | **16** (12 data, 3 voorwaarden, 1 afleidingsregel) | 26 (13 variabelen, 7 operatoren, 5 duren, 1 rechtsobject) | 8 (dubbel, "is gesteld op") |

(IW 9 lid 5 heeft 2 elementen zonder kandidaat met dezelfde grens en 2 die de jurist van klasse veranderde; die tellen
niet mee.)

- **Het aandeel afwijzingen in 9.5**: van 67 naar hoogstens 51 voorstellen; afgewezen van 50 van 67 (75%) naar
  hoogstens 34 van 51 (67%). Zonder model is dat de bovengrens: van de 26 met het kenmerk beslissen het model en de
  reviewer, en met de nieuwe regel in de skill hoort de jurist er een deel van te houden (het jaartal, het schrikkeljaar,
  de dagtekening).
- **Niets dat de jurist accordeerde, valt weg**, en op de drie bepalingen zonder voorbeeld verandert geen enkele kandidaat.
- **Kandidaat-dekking op variabele en parameter tegen de referentie** (een kandidaat die die klasse kan dragen, niet
  afgewezen, dezelfde woorden): vóór en na gelijk, op elke bepaling. Variabele 20 van 39, parameter 0 van 8. De parameter
  is 0 vóór én na: "één maand" en "zes weken" zijn een Tijdsaanduiding (JAS-PRIORITY-001); dat is M3, niet deze stap.

**Precisie op de hele graaf**: alle 228 bepalingen op acceptatie met een datum of bedrag (acht regelingen). De eerste
versie vond naast de vier zinnen van 9.5 drie andere: een overgangsregeling met "dus" en grensdata (Leidraad 34.6.3) en
twee normen met een drempelbedrag in voorwaarde en hoofdzin (Awir art. 7 lid 3, Leidraad 79.8). Na twee generieke
aanscherpingen (een gegeven ná de inleiding, geen grens; het uitkomst-signaal alleen met kalenderdata) blijven alleen de
vier zinnen van 9.5 over. Die set is daarmee een ontwikkelset, niet meer blind.

## Wat niet gemeten is, en waarom

- **Met het model.** De code draait pas na de merge op acceptatie. Een beurt op Leidraad 9.5 daar schrijft in de gedeelde
  laag, en die is geaccordeerd: dat doet deze meting niet (de opdracht: geen beslissingen van de jurist overschrijven).
  Na de uitrol kan het met een eval-run zonder schrijfpad, of in een laag die niet van Termijnen is. De meting vóór met
  het model is de run van 19 nov 2026 die op acceptatie ligt (67 voorstellen, 50 afgewezen).
- **De blinde bepaling met rekenvoorbeelden uit een andere regeling.** Die bestaat in de graaf niet: van de 228
  bepalingen met een datum of bedrag heeft alleen Leidraad 9.5 rekenvoorbeelden. De bestaande blinde families (Awir, AWR,
  Kwijtschelding, Verrekening, IW 52 en 63b) hebben er geen. De precisieronde hierboven is het naaste, en is geen blinde
  meting. Een blinde meting vraagt een regeling met rekenvoorbeelden in de graaf (een import), of een tekst buiten de graaf
  in de eval.
- **Awb 4:86 lid 2** deelt de referentie wel, maar is niet geannoteerd in het werkgebied Termijnen en is een opsomming
  zonder voorbeeld; niet meegenomen.
