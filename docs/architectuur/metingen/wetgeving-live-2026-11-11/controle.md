# Controle na #1221 – 11 november 2026

Soort: *meting* · Code: master `bb6b46a5` (bundel 40: #1220 en #1221) · Straat: acceptatie, Wetgeving buiten de kennisgraaf
aan · Model: `claude-sonnet-4-6` · Uitvoering: de acceptatie-MCP, elke vraag één run in een nieuw gesprek, één tegelijk ·
Akkoord: hoogstens 200k tokens.

Deze controle toetst de zes oplossingen uit #1221 op de vragen die ze raken. De ruwe gegevens staan in
[`controle-runs.jsonl`](controle-runs.jsonl). Tokens = invoer + uitvoer + cache lezen + cache schrijven uit het `meting`-event:
samen **101.958**. De verbruiksteller steeg met precies dat getal (367.684 → 469.642).

## Uitkomst

| vraag | route | tokens (eerst) | uitkomst |
|---|---|---|---|
| W14 *artikel 31 Pw*, connector uit | vaste melding, geen model | 0 (46.305) | niet in de kennisgraaf, de bron staat uit, aanzetten bij *Bronnen en tools*; `bron_uit`-event |
| W16 *Annoteer artikel 7:610 BW* | vaste melding, geen model | 0 (24.857) | "Burgerlijk Wetboek Boek 7 staat niet in de kennisgraaf, en annoteren kan pas na een import" |
| W01 *artikel 31 Pw* | workflow, 1 ronde | 2.927 (–) | 3 pagina's in code, 42 passages in `extern`, 1 bron, `gegrond`, 40 citaten gecontroleerd |
| W12 *artikel 12 Pw* (vervallen) | workflow, 1 ronde | 320 (19.379) | `Leemte` "vervallen per 1 januari 2026: er geldt geen tekst meer", 1 bron, `gegrond` |
| W07 *artikel 9 Iw op 1 januari 2020* | workflow, 1 ronde | 1.796 (144.001) | toestand `2020-01-01_1`, `eerdere tekst` tot 31 mei 2020, 18 passages, `gegrond`, 6,5 s (83 s) |
| W09 *artikel 8 Pw op 15 januari 2015* | workflow, 1 ronde | 694 (–) | toestand `2015-01-01_1`, `eerdere tekst`, `gegrond` |
| W18 *artikel 3.1 Wet IB 2001* | workflow, 1 ronde | 652 (–) | 13 passages, `gegrond` (criterium < 60k) |
| W13 *Wat regelt artikel 24a Pw?* | duiding (uitlegvraag), 2 rondes | 40.570 (–) | nog niet in werking, per 1 januari 2027; 1 bron |
| W15 *Neem artikel 31 Pw op in de bronselectie* | duiding, alle pagina's in code, 2 rondes | 54.999 (131.439) | **schijnopname**: "staat nu in de bronselectie" |

### Per bevinding

1. **Bronnenlijst: opgelost.** Alle negen runs die een artikel lazen, hebben de gelezen bron `wettekst_live`, ook in de
   modelroute (W13, W15).
2. **Sjabloon en letterlijkheid: opgelost.** Een tekstvraag krijgt het sjabloon `extern` met het hele artikel uit de code, en
   `verify` meldt "n citaten gecontroleerd" met niveau `gegrond`. Een uitlegvraag (W13) loopt nog via de duiding, met
   `onbepaald`, en dat is zo bedoeld.
3. **Bladeren: opgelost.** De code leest alle pagina's, in de workflow (W01, W07) en in `bron_lezen` (W15). Het model bladert
   niet meer.
4. **Eerdere tekst: opgelost.** W07 gaat zonder zoeken en in één ronde naar de juiste toestand.
5. **Annoteren: opgelost.** Er is een vaste melding zonder model.
6. **Connector uit: opgelost.** Er is een vaste melding zonder model, met *Zet aan*.

## Nieuwe bevindingen

1. **Schijnopname bij W15: dit is een garantie.** "Neem artikel 31 van de Participatiewet op in de bronselectie" loopt via
   `bron_lezen` en de duiding. Het model schrijft dan "is volledig opgehaald en staat nu in de bronselectie". Er is niets
   opgenomen, en er was niet eens een werkgebied. In de eerste meting zei het model nog dat een import nodig is: dat hing
   van het model af. **Oplossing:** behandel een verzoek om op te nemen of toe te voegen (aan de bronselectie of het
   werkgebied) voor een regeling buiten de graaf net als annoteren. Dat is een vaste melding in
   `supervisie._buiten_graaf_melding` met `bronselectie.NIET_IN_GRAAF`, vóór het model.
2. **De onderdeelletters ontbreken in de passages** (W01, W09). De rijen dragen `nummer` ("a.", "b."), maar
   `sjablonen.extern.heel_stuk` neemt het niet over. `ExternePassage` heeft er ook geen veld voor. Een lid dat naar "onderdeel
   b" verwijst (W09, lid 2), is zo niet te volgen. **Oplossing:** zet het nummer voor de tekst, of in de kop van de passage,
   zoals de graaf een onderdeel toont.
3. **De toelichting voegt soms iets toe dat niet in de tekst staat** (W09: "het verlagen van bijstand bij jongeren" voor
   artikel 9a, twaalfde lid). `hoeveelheden_buiten` vangt alleen termijnen, bedragen en datums. Dit is hetzelfde risico als bij
   de toelichting uit de graaf. Het hoort bij de toelichtingsprompt van de bepalingsworkflow, niet specifiek bij deze connector.

## Wat deze controle niet zegt

- Het is één run per vraag, dus over de spreiding zegt dit niets. Bij W15 komt de schijnopname van het model. Dat het in de
  eerste meting goed ging, zegt dus niets over de volgende run. Juist daarom hoort de oplossing in code.
- Niet gedraaid zijn W02–W06, W08, W10, W11 en W17. Die raken de zes oplossingen niet, of alleen via routes die hierboven al
  getoetst zijn.
