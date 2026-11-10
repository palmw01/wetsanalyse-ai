# Rechtspraak op acceptatie – 10 november 2026

Soort: *meting* · Code: master `1c1a6366` (bundel 29, #1177: #1170 + #1171 + #1172) · Straat: acceptatie, met
Rechtspraak en Kamerstukken aan in het register · Model: `claude-sonnet-4-6` (Foundry) · Uitvoering: de acceptatie-MCP
(`lex_start`, de run-events, `GET /api/account/verbruik`), elke run in een nieuw gesprek en één run tegelijk.

Het akkoord van de gebruiker was "Akkoord" (10 nov 2026), op het meetplan van de aanvulling op #1170.

De ruwe gegevens per run staan in [`runs.jsonl`](runs.jsonl): gesprek, run-id, routes, tools, modelrondes, duur, tokens
uit het `meting`-event, het oordeel van de controle en een opmerking. Meetbestanden worden niet achteraf gewijzigd.

## Vragen en verwachting

| # | vraag | verwacht |
|---|---|---|
| 1 | Wat staat er in ECLI:NL:HR:2022:50? | lezen zonder supervisor, het blok *Uit de rechtspraak*, gegrond |
| 2 | Welke uitspraken noemen artikel 36 van de Invorderingswet 1990? | LiDO per artikel, het blok *Gevonden Rechtspraak* met de zoekvraag in woorden |
| 3 | Geef de 10 nieuwste uitspraken van de Hoge Raad in het belastingrecht | de lijstroute zonder model, via de zoekfeed (#1171) |
| 4 | Wat is een uitspraak op bezwaar? | Rechtspraak niet geraakt (de signalen uit #1170) |
| 5 | Wat staat er in ECLI:NL:GHARL:2023:5000? (alleen metadata) | een eerlijke melding |

## Uitkomst (drie runs per vraag)

Tokens = cache lezen + cache schrijven + uitvoer per run, uit het `meting`-event. Het totaal voor alle vijftien runs
was 1.019.997 volgens de verbruiksteller (die telt cache lezen ×1, dus een bovengrens voor de kosten).

| # | route | modelrondes | duur (s) | tokens | controle | uitkomst |
|---|---|---|---|---|---|---|
| 1 | `bron_lezen` → duiding | 2 / 2 / 2 | 31 / 15 / 17 | 47k / 47k / 48k | gegrond ×3 | **haalt het**: sjabloon *extern*, label "Hoge Raad 21 januari 2022, ECLI:NL:HR:2022:50", 8 letterlijke passages |
| 2 | duiding (supervisor) | 8 / 5 / 5 | 54 / 26 / 37 | 178k / 93k / 94k | gegrond ×3 | **1 van 3**: alleen run 1 het blok *Gevonden Rechtspraak* (22 van 623, "Gezocht bij artikel 36 van Invorderingswet 1990. Nieuwste eerst."); run 2 en 3 zonder sjabloon |
| 3 | `bron_lijst` | 0 / 0 / 0 | 1,6 / 0,4 / 0,3 | 0 | onbepaald ×3 | **haalt het**: 10 van 19.523, "Gezocht op soort „uitspraak”, van de Hoge Raad en rechtsgebied belastingrecht. Nieuwste eerst." |
| 4 | definitie (supervisor) | 8 / 10 / 8 | 47 / 37 / 29 | 134k / 178k / 140k | onbepaald ×3 | **haalt het**: geen enkele Rechtspraak-tool (run 1 en 2 per tool gelezen, run 3 dezelfde vorm), sjabloon *begrip* met een leemte |
| 5 | `bron_lezen` → duiding | 1 / 1 / 1 | 19 / 6 / 5 | 21k ×3 | gegrond ×3 | **haalt het**: "niet beschikbaar in de open data", met de link; in run 1 en 3 ook gerecht, datum, zaaknummer en rechtsgebied uit de metadata |

Wat werkt zoals bedoeld:

- **Een genoemde ECLI** wordt zonder supervisor gelezen (één toolaanroep, `get_uitspraak`). De kop van de rechtsoverweging
  staat bij elke passage ("Uitspraak › 3 Beoordeling van de middelen") en het label komt uit de metadata.
- **De lijstvraag zonder artikel** gaat in code, zonder model en in onder twee seconden, via de zoekfeed: de instantie en het
  rechtsgebied komen uit de waardelijsten, en het totaal noemt de hele periode. De tien zijn van 6 november 2026, de laatste
  uitspraakdag van de Hoge Raad vóór de meting.
- **"Uitspraak op bezwaar"** raakt Rechtspraak niet: de fiscale procestaal is geen signaal meer.
- **Een uitspraak zonder tekst** wordt een eerlijke zin met de link, nooit een verzonnen inhoud.
- **De controle** keurt niets af: 0 onbevestigd, 0 niet-letterlijk in alle vijftien runs.

## Bevindingen (op volgorde van belang)

1. **Vraag 2: het sjabloon ontbreekt in 2 van 3 runs**, en dan schrijft Lex de lijst zelf.
   - Run 2 zegt "De lijst hierboven toont de 22 meest recente", maar er staat geen lijst: `antwoord` is `null`.
   - Run 3 typt de 22 uitspraken over als tabel, met datum en instantie. Hier kloppen ze met het zoekresultaat, maar het
     blok `stukken` bestaat juist om dat overtypen te voorkomen.
   - In beide runs zit een ronde met ~540 uitvoertokens vóór het eindantwoord. Dat wijst op een sjabloonpoging die niet te
     vullen was (`Onvulbaar`), waarna het model tekst gaf. De logs (`sjabloon gemist`) zijn via de MCP niet te lezen,
     omdat de Grafana-variabelen ontbreken. Dit is de eerste plek om te zoeken.
   - Mogelijke oorzaak: de vraag "welke uitspraken noemen artikel 36" laat de duidingspecialist het sjabloon *bepaling*
     kiezen, met de leden van het artikel. Het lukte één keer, in run 1, na `get_artikel` en `get_lid`, met 8 rondes.
2. **Vraag 2 kost veel.** Er beslist een supervisor, er komt een zoektocht naar het BWB-id (`search_wetgeving`), en het
   kost 5 tot 8 rondes en 93k tot 178k tokens. Een vaste route "uitspraken bij artikel X van wet Y" (zoals `bron_lijst`,
   met het artikel uit de vraag) zou dit zonder model doen. `lees_aanwijzing` kent het artikel en de regeling al.
3. **Het label van een zoekrij is de kale ECLI** (in vraag 2 en 3). Bij het lezen is het "Hoge Raad 21 januari 2022, ECLI…",
   bij het zoeken alleen de ECLI, terwijl gerecht en datum in de rij staan. `rij_van` kan `label_van` gebruiken.
4. **Spaties vallen weg bij een regelafbreking in de bron.** De Rechtspraak schrijft `<?linebreak?>` tussen zinnen, en
   `lees()` plakt de zinnen dan aan elkaar ("bankrekeningen.In bezwaar"). De passage is daardoor niet meer letterlijk
   gelijk aan de bron zoals een lezer haar ziet.
5. **Het rechtsoverwegingnummer (`ro`) staat niet in het antwoordblok.** De leestool geeft het (`ro: "2.1"`), maar
   `ExternePassage` neemt het niet over, dus de jurist ziet "Uitspraak › 2 Uitgangspunten in cassatie" zonder "r.o. 2.1".
6. **In de zoekvraagzin van vraag 3 staat "soort „uitspraak”"**: de lijstroute leest het woord "uitspraken" als filter.
   Dat sluit de conclusies uit. Dat mag, maar het hoort dan bewust te zijn; voor een lijst "uitspraken van de Hoge Raad"
   is weglaten waarschijnlijk beter.
7. **Bij een lezing zonder tekst (vraag 5) ontbreekt de resultaatregel** "Rechtspraak · …" in het denkproces. Run 2 zei
   "Het systeem meldt", wat systeemtaal is (zie de schrijfrichtlijn).

Los van Rechtspraak (gezien in vraag 4, niet gemeten):

- een antwoord met alleen een leemte en een toelichting krijgt 31 tot 38 bronnen mee;
- de toelichting noemt "artikel 7:12 Awb" en "artikel 25 AWR", terwijl de controle zegt "geen vindplaats genoemd".

## Wat deze meting niet zegt

- Of de uitspraken inhoudelijk over het artikel gaan: dat is een vermelding volgens LiDO, en het juridisch oordeel is niet
  gemeten (zie `lido-spike-2026-11-10`, 25 van 30).
- De begrenzer en de versiecontrole van de cache: die zijn onder deze belasting niet zichtbaar.
- Productie: daar staat Rechtspraak niet aan.
