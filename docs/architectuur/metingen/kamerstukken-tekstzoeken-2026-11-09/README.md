# Zoeken in de tekst van Kamerstukken – 9 november 2026

Soort: *meting* · Code: branch `claude/kamerstuk-tekstzoeken` (PR 5 van *metadata in het connectorcontract*) · 0
modelcalls, live tegen de SRU van KOOP.

## Vraag

Een onderzoek naar de parlementaire geschiedenis van "uitbetaling op één bankrekeningnummer" (een gesprek buiten Lex,
daarna getoetst) noemde acht stukken die Lex niet vond. `zoek_kamerstukken` zocht alleen in de titel. Vindt
`cql.textAndIndexes` ze wel, en waar staan ze?

De acht stukken, met de hand gecontroleerd in de officiële publicaties:
`kst-32740-1-n1` (Fiscale agenda, herdruk), `kst-33004-3` (MvT Overige fiscale maatregelen 2012), `kst-33402-61`,
`kst-33754-7`, `kst-31066-192`, `kst-31066-202`, `kst-31066-203`, `kst-31066-246`.

## Uitkomst

Plek in de eerste 100 records (`proef.py`):

| zoekvraag | totaal | gevonden | plekken |
|---|---|---|---|
| titel bevat "bankrekeningnummer" | 8 | 3 | 6, 7, 8 |
| tekst, zinsdeel "één bankrekeningnummer" (`=` en `adj` gelijk) | 117 | **8** | 1, 2, 11, 12, 15, 16, 41, 50 |
| tekst, alle woorden "één bankrekeningnummer" (`all`) | 357 | 8 | 1, 5, 6, 26, 32, 40, 45, 49 |
| tekst, zinsdeel "één rekeningnummer" | 117 | 5 | 1, 2, 5, 6, 8 |
| tekst, alle woorden "uitbetaling bankrekeningnummer toeslagen" | 120 | 8 | 1, 8, 11, 14, 18, 19, 30, 34 |
| tekst "POBR1" | 1 | 1 | 1 (`kst-33402-61`; de term staat niet in de titel) |
| tekst, alle woorden "fiscale agenda bankrekeningnummer" | 90 | 4 | 4, 8, 52, 59 |
| tekst, zinsdeel, 2011–2016, oudste eerst | 74 | **8** | Fiscale agenda 1, MvT 33004 6, dan 27–67 |

## Wat dit zegt

- `cql.textAndIndexes` zoekt in de tekst van het stuk, niet alleen in metadata: de Fiscale agenda heet "Brief regering"
  en "POBR1" staat alleen in de tekst van 33402-61.
- Een zinsdeel (`adj`) is scherper dan alle woorden (`all`): 117 tegen 357 treffers, met dezelfde acht.
- Met een periode en de oudste eerst is het een tijdlijn: het beleidsvoornemen (2011) en de MvT staan bovenaan.
- Niet gemeten: of dit op andere onderwerpen even goed werkt (één onderwerp, een ontwikkelset), en hoe Lex de zoekterm
  kiest. Dat laatste meet de acceptatie na de uitrol.

## Gevolg

`zoek_kamerstukken` krijgt het argument `tekst`: een zinsdeel tussen aanhalingstekens als `adj`, losse woorden als `all`,
hoogstens zes woorden. Standaard op relevantie; met een periode en `oudste` voor een tijdlijn.
