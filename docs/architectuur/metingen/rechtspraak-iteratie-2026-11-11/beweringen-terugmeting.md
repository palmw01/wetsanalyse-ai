# Rechtspraak, iteratie: de toets op beweringen tegen eerdere rondes (12 november 2026)

Soort: *terugmeting* zonder model. Het meet hoe vaak de nieuwe toets op beweringen (`tools/graph-qa/agent/beweringen.py`)
afgaat op antwoorden die al beoordeeld zijn. De toets is gebouwd in ronde 4.

**Werkwijze.** Per run uit ronde 2, ronde 3 en de twee controles neem ik de getoetste tekst van het antwoord: de blokken
buiten `NIET_GETOETST`, of anders de vrije tekst. Dat waren 38 antwoorden met zo'n tekst. De andere antwoorden waren
alleen een lijst of een melding van de code. Daarna voer ik de connectortools uit de `tool_execution`-events opnieuw uit,
met dezelfde argumenten, live en zonder graaf. Ik toets tegen drie dingen: die resultaten, de blokken die uit de bron
komen (`door: "bron"`) en de vraag. Ronde 1 doet niet mee: de code van toen gaf andere resultaten, dus opnieuw uitvoeren
toetst haar niet.

## Uitkomst

8 van de 38 antwoorden hadden een treffer.

| soort | treffers | voorbeelden | oordeel |
|---|---|---|---|
| vals alarm | 2 | "CRvB" (de bron noemt de Centrale Raad van Beroep voluit, R22 ronde 2); "1990" in "Invorderingswet 1990" (R28b) | **opgelost**: een afkorting en het jaar in de naam van een regeling tellen niet |
| afgeleid getal | 2 | "bijna 73%" van het totaal (R22 ronde 2); "samen: 166" (K17-R22) | terecht volgens de regel: het model rekende ze zelf uit, en de bron noemt ze niet |
| niet opnieuw uit te voeren | 6 antwoorden | "153 een eerdere tekst", "213", "168"/"177" bij de huidige tekst, "88 rechtbanken" bij een peildatum | tellingen per tekststand of op een peildatum: daarvoor heeft de zoektool de graaf nodig (`bwb:inwerking`), en die ontbreekt hier. Ze stonden in `per_tekststand` van het echte resultaat |

Op deze antwoorden geeft de toets dus geen vals alarm meer. Twee afgeleide getallen leveren een correctieronde op.

## Wat deze meting niet zegt

- Het opnieuw uitvoeren gebeurt zonder graaf. Een feit dat alleen uit een graaftool komt (wettekst, een inwerkingtreding),
  toetst deze meting niet. Die feiten vallen dus buiten deze terugmeting, maar ze blijven in de echte trace.
- LiDO loopt door: een totaal van nu kan afwijken van dat van toen. Die gevallen heb ik met de hand nagelopen.
- De kosten van een correctieronde meet ronde 4 op acceptatie.
