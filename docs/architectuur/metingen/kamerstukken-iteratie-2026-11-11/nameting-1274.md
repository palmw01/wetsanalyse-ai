# Kamerstukken – nameting van #1274 (12 november 2026)

Soort: *meting*. Gemeten op acceptatie, op master `a120e579` (bundel 55, met #1274), met `claude-sonnet-4-6` (Foundry),
via de acceptatie-MCP, elke vraag in een eigen gesprek. De bronstand is die van ronde 6: geen beperking per gesprek.

Gerichte nameting van de drie fixes uit #1274 (L-K2, K10, K15), plus vijf andere vragen:
- K10b is nieuw: "Hoeveel amendementen zijn er bij 36602?";
- verder K07, K11, K16 en K17.

De ruwe gegevens staan in [`runs.jsonl`](runs.jsonl) (`"ronde": "nameting-1274"`).

**Een onderbreking.** Halverwege was het tokenbudget op. K11, K16, K17 en K10b kregen daardoor een 429 (`budget_op`). Na
de reset zijn die vier één keer opnieuw gedraaid; geen vraag is twee keer gemeten.

## Uitkomst

| vraag | oordeel (ronde 6 → nameting) | modelrondes | tokens |
|---|---|---|---|
| L-K2 | deels → **goed** | 0 → 0 | 0 → 0 |
| K10b (nieuw) | – → **goed** | 0 | 0 |
| K10 | deels → **deels** | 10 → 11 | 359k → 390k |
| K15 | goed → **goed** | 9 → 6 | 295k → 175k |
| K07 | goed → **deels** | 6 → 13 | 123k → 438k |
| K11 | goed → **goed** | 1 → 1 | 26k → 26k |
| K16 | deels → **goed** | 16 → 15 | 531k → 596k |
| K17 | goed → **goed** | 0 → 0 | 0 → 0 |

**Wat de fixes deden:**
1. **L-K2: geen stuk valt meer stil weg.** Lex geeft nu 8 memories van toelichting, waar het er in ronde 6 7 waren. Ook
   kst-24172-3 staat erbij, waarvan de titel niet met de dossiertitel begint. De officiële zoekdienst geeft er met
   dezelfde woorden ook 8. Dit gaat zonder model, met de kanttekening over de woordgroep.
2. **K10b: een kaal dossiernummer telt.** "Hoeveel amendementen zijn er bij 36602?" geeft 88, precies, uit `totaal`. De
   SRU telt er ook 88. Er komt geen model aan te pas, dus 0 tokens.
3. **K15: `per_kop` staat op de eerste pagina**, lokaal nagelopen tegen de echte bron.
   - Het verdeelt 223 treffers over 5 koppen op twee niveaus.
   - Het model gebruikte 6 rondes in plaats van 9, maar bladerde nog steeds door (offset 9, 22 en 42).
   - Vijf koppen is te grof om te kiezen. Bij deze begroting liggen de treffers onder een paar grote hoofdstukken, dus
     een derde niveau zou meer zeggen.

## Bevindingen, alleen benoemd

1. **K10 blijft deels.**
   - De eerste aanroep was nu wel `dossier: 36602, soort: amendement`, maar daarna zocht het model op de titelwoorden
     "Belastingplan 2025" en bladerde alles door.
   - De toelichting zegt weer "90 amendementen"; de bron telt er 88.
   - Het model gebruikt het `totaal` van zijn eigen eerste zoekvraag niet. Een vraag die het wetsvoorstel bij naam noemt
     ("bij het Belastingplan 2025"), leest de code nog niet: daarvoor moet ze het dossier uit de naam halen.
2. **K07 is deels, door iets nieuws.**
   - Het antwoord begint met procestaal van het model: "Nu heb ik de letterlijke tekst van alinea 148. Ik kan het
     antwoord nu opbouwen."
   - Dat komt doordat `antwoord_duiding` twee keer werd geweigerd (`duiding.vul`), waarna het model in tekst antwoordde
     (`gemist: 1`). Die tekst bevatte zijn eigen aanloop.
   - 13 rondes en 438k tokens.
   - Dit raakt de afronding van het sjabloon en de grens tussen denkproces en antwoord, niet de connector. Het is voor de
     sessie van het denkproces.
3. **K16 noemt geen dossiernummer of jaar meer zonder bron.**
   - De twijfel zegt nu alleen dat de memorie van vóór 1994 niet bij KOOP staat.
   - Het model zocht wel `dossier: 20588`, zonder resultaat.
   - Rechtspraak stond aan, maar er is geen uitspraak gelezen.
   - 15 rondes en 596k tokens: de duurste vraag.

## Wat deze meting niet zegt

- Het is één run per vraag. K07 (123k → 438k) en K16 (531k → 596k) laten zien hoe groot de spreiding is.
- Het oordeel is van deze sessie, getoetst tegen de bron; het is geen juridisch oordeel.
