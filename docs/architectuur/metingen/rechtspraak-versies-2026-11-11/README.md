# Rechtspraak: de tekst van het artikel bij een uitspraak – 11 november 2026

Soort: *meting* · Code: master `d6dcabb5` (bundel 36, #1209 met #1207) · Straat: acceptatie, Rechtspraak, Kamerstukken en
Staatsblad/Staatscourant aan · Model: `claude-sonnet-4-6` · Uitvoering: de acceptatie-MCP, elke vraag één run in een nieuw
gesprek, één tegelijk · Akkoord: de hoofdsessie gaf hoogstens 5 vragen; na vraag 2 ging de schatting over 300k en gaf de
gebruiker akkoord voor de rest.

Deze meting toetst #1207: elke uitspraak uit `zoek_uitspraken` noemt de periode van haar artikelversie in LiDO
(`tekst_vanaf`, `tekst_tot`), of dat de huidige tekst in de graaf is (`tekststand`) en, met een peildatum, of die erin valt
(`op_peildatum`). De ruwe gegevens per run staan in [`runs.jsonl`](runs.jsonl). Tokens = invoer + uitvoer + cache lezen + cache
schrijven uit het `meting`-event: samen **929.469**.

De verbruiksteller steeg met 1.381.354 (191.458 → 1.572.812). Dat is 451.885 meer dan de runs zelf. Het account is gedeeld, en
tijdens de meting werkte er minstens één andere sessie op acceptatie, dus het verschil hoort waarschijnlijk niet bij deze runs.
Per run meet ik daarom het event.

## Uitkomst

| # | vraag | route | tokens | wat de rijen dragen |
|---|---|---|---|---|
| 1 | Welke uitspraken noemen artikel 9 Iw? | vaste lijst, geen model | 0 | 10/10 `huidige tekst`, vanaf 1 juli 2026 |
| 2 | Jurisprudentie over art. 36 Iw die over de huidige tekst gaat? | duiding, 6 rondes | 160.609 | Lex gaf `tekststand: huidige tekst` mee; 16/16 huidige tekst, vanaf 4 juli 2010 |
| 3 | Uitspraken bij art. 25 Iw op peildatum 1 januari 2015 | duiding, 6 rondes | 137.130 | Lex gaf `peildatum` en `tekststand: op peildatum` mee; 14/14 `eerdere tekst`, 1 jan 2014 tot 31 dec 2015, `op_peildatum: true` |
| 4 | Wat heeft de Hoge Raad gezegd over art. 36 Iw? | duiding, 13 rondes, 7 arresten gelezen | 631.730 | lijst en de drie blokken *Uit de rechtspraak*: huidige tekst, vanaf 4 juli 2010 |
| 5 | Uitspraken over art. 25 Iw, in een werkgebied met peildatum 1 januari 2015 | vaste lijst, geen model | 0 | 10/10 `huidige tekst`, `op_peildatum: null` |

Wat werkt:

- **De velden komen aan**, in de lijst (`stukken`) en ook in een blok van een gelezen uitspraak (`extern`, vraag 4): `extern`
  neemt ze over uit de zoekrij van dezelfde ECLI.
- **Lex gebruikt de argumenten zelf** als de vraag erom vraagt: het filter `tekststand` in vraag 2, de peildatum in vraag 3.
- **Het antwoord zegt het onderscheid.** Vraag 2: "470 uitspraken die aan de huidige tekst zijn gekoppeld; die tekst geldt
  vanaf 4 juli 2010. Daarnaast noemen 153 uitspraken een eerdere versie." Vraag 3 noemt de periode van de tekst op de
  peildatum.
- **De grens van LiDO staat bij twijfel** in vraag 2 en 3: de koppeling volgt de datum van de uitspraak, en welke tekst de
  rechter toepaste staat pas in de uitspraak zelf. Vraag 4 laat zien waarom dat nodig is: HR:2023:1371 r.o. 3.1 past artikel 36
  toe "zoals die gold in de tijdvakken" van het geschil (2018–2019).
- **0 ongegrond, 0 niet-letterlijk** in de drie runs met een model.

## Bevindingen

1. **De vaste lijstroute negeert de peildatum van het werkgebied** (vraag 5). Een lijstvraag gaat zonder model naar
   `zoek_uitspraken` met de argumenten uit `agent/bron_lijst.py` (`lees`), en de peildatum uit de werkgebiedcontext zit daar
   niet in. In een werkgebied met peildatum 2015 toont Lex dus de nieuwste uitspraken bij de tekst van nu, zonder te zeggen dat
   ze niet bij de peildatum horen. Dit is het geval waarvoor #1207 het injecteren uit de state "voor later" bewaarde. De oplossing
   hoort in de vaste route: geef de peildatum van het werkgebied mee als `peildatum` (niet als filter). Dan dragen de rijen
   `op_peildatum` en toont de werkplek "niet op de peildatum".
2. **De vaste lijst noemt de telling per tekststand niet** (vraag 1 en 5). Het sjabloon `extern` toont de zoekvraag en
   "10 van de 196", maar niet de toelichtingszin "n van de m uitspraken noemen een eerdere tekst". Voor artikel 9 is dat
   onschuldig: de tien nieuwste horen allemaal bij de huidige tekst. Bij een ouder artikel staat zo'n verschil alleen bij de rijen.
3. **Rijen via het peildatumfilter missen datum en titel** (vraag 3): alleen het jaar, en als orgaan "rechtbank" of
   "gerechtshof". De zoekroute met een filter op een oudere versie haalt de metadata per ECLI kennelijk niet op. Lex vulde de
   instanties in het antwoord zelf goed in. De zoektool duurde hier 30,9 s.
4. **Vraag 4 is duur door het lezen** (13 rondes, 11 leesaanroepen voor 7 arresten, 632k), niet door #1207.
5. **Het blok `stukken` verliest zoekvraag en totaal na het lezen** (vraag 4: 4 rijen, terwijl de tekst "18 van 75" noemt). Dat
   is het bekende punt q8.

## Wat deze meting niet zegt

- Eén run per vraag: over de spreiding zegt dit niets.
- Of de werkplek de labels "eerdere tekst" en "niet op de peildatum" goed toont, is getest in de browsersuite
  (`test-bronvenster-stuk.mjs`), niet op acceptatie bekeken.
- Of een uitspraak bij de "huidige tekst" ook echt die tekst toepaste: dat levert LiDO niet (zie ADR-013).

Voor deze meting zijn vijf gesprekken en één werkgebied aangemaakt ("Meting rechtspraak-versies (uitstel van betaling 2015)",
`677d7740-…`). Er is niets anders gewijzigd of gewist.
