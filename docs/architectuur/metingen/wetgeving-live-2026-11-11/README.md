# Wetgeving buiten de kennisgraaf: eerste meting – 11 november 2026

Soort: *meting* · Code: master `714ddb47` (bundel 39, #1219 met #1218) · Straat: acceptatie, alle vier de connectors aan ·
Model: `claude-sonnet-4-6` · Uitvoering: de acceptatie-MCP, elke vraag één run in een nieuw gesprek, één tegelijk, met
`bronnen: ["wetgeving_live"]` (W14 met `bronnen: []`) · Akkoord: de gebruiker, via de hoofdsessie, voor hoogstens 400k tokens,
elke vraag één keer.

Deze meting toetst de vierde connector (ADR-013, fase 1e) met vragen uit
[`wetgeving_live_vragenset.json`](../../../../tools/graph-qa/tests/data/wetgeving_live_vragenset.json). Het meetplan in
`docs/acceptatie/connectors-meting.md` noemt 18 vragen × 3 runs. Dat past niet in het budget. Daarom staan hier eerst de
garanties en dan de leesvragen, één run per vraag. Na zeven vragen stond de teller op 367.684; daar ben ik gestopt.

De ruwe gegevens per run staan in [`runs.jsonl`](runs.jsonl). Tokens = invoer + uitvoer + cache lezen + cache schrijven
uit het `meting`-event: samen **367.684**. De verbruiksteller van het account steeg met precies dat getal (0 → 367.684).

## Uitkomst

| vraag | soort | route | tokens | uitkomst |
|---|---|---|---|---|
| W04 *Wat staat er in artikel 1 Pw?* | dubbelzinnige afkorting | keuzevraag, geen model | 0 | vraagt welke: Participatiewet, Pensioenwet, Prijzenwet, Provinciewet |
| W14 *artikel 31 Participatiewet* (connector uit) | connector uit | duiding, 4 rondes | 46.305 | niet in de kennisgraaf, de bron staat uit, hoe je hem aanzet; geen tekst |
| W16 *Annoteer artikel 7:610 BW* | annoteren | annotatie, 3 rondes | 24.857 | geen annotatie, maar met de reden "Ongeldig BWB-id" |
| W15 *Neem artikel 31 Pw op in de bronselectie* | werkgebied | vooraf gelezen + 5 rondes | 131.439 | niets opgenomen; "moet eerst worden geïmporteerd" |
| W08 *artikel 9 Iw 1990* | in de graaf | vooraf uit de graaf, 1 ronde | 1.703 | uit de graaf, sjabloon `bepaling`, gegrond; `get_wettekst` niet aangeroepen |
| W12 *artikel 12 Participatiewet* | vervallen | vooraf gelezen, 1 ronde | 19.379 | "vervallen per 1 januari 2026", live van overheid.nl |
| W07 *artikel 9 Iw 1990 op 1 januari 2020* | eerdere tekst | duiding, 7 rondes | 144.001 | toestand `2020-01-01_1` (1 jan t/m 31 mei 2020), 12 leden letterlijk |

### Criteria uit het meetplan

**Garanties** (hier op 1/1 in plaats van 3/3):
- *Geen tekst van overheid.nl voor een toestand in de graaf* (W08): gehaald.
- *Geen gok bij een dubbelzinnige afkorting* (W04): gehaald, zonder model.
- *Geen schijnopname of annotatie* (W15, W16): gehaald.
- *Geen tekst uit eigen kennis* (W14): gehaald.
- *Geen run ongegrond*: geen run is afgekeurd. Maar bij vier van de zes runs met een model staat het niveau op `onbepaald` met
  `cited: 0`. De letterlijke tekst in W07 is dus niet gecontroleerd (zie bevinding 2).

**Slagen:**
- *Het genoemde artikel gaat zonder model naar de tool*: W12 en W15 (de route van W01) wel. W07 niet, maar daar is het ook niet
  ontworpen: de Iw staat in de graaf.
- *W07 met de juiste toestand*: ja. Het label "eerdere tekst" staat er niet letterlijk. Wel staat er "zoals die op 1 januari
  2020 luidde", met de geldigheidsperiode.

Wat werkt:
- **De grens met de graaf houdt.** W08 kwam uit de graaf (1.703 tokens). W07, met een peildatum buiten de graaftoestand, kwam van
  de connector. Daar laat de tekst het verschil echt zien: lid 8 had toen een onderdeel b over de belasting zware motorrijtuigen.
- **De vooraf-stappen werken.** De keuzevraag bij "Pw" en het vooraf lezen van een genoemd artikel (W12, W15) lopen zonder
  modelkeuze.
- **Lex noemt de herkomst steeds**: "niet in de kennisgraaf", "live van overheid.nl", met de geldigheidsperiode, en dat een
  werkgebied of annotatie een import vraagt.

## Bevindingen

1. **Een gelezen wettekst van overheid.nl valt uit de bronnenlijst** (W15, W12, W07: "Klaar · 0 bronnen"). Dat doet
   `grounding.alleen_gelezen_extern`: een bron met een ander brontype dan `wettekst` blijft alleen staan als het antwoord haar id
   noemt, als de vraag dat doet, of als een blok `extern` eruit citeert. Een `bwbt:`-id staat nooit in lopende tekst, en er was
   geen sjabloon. De jurist ziet dus geen bron, en het venster opent niet. **Oplossing:** behandel een gelezen `wettekst_live`-stuk
   (in `stukken`) zoals wettekst. Het is gelezen wettekst en geen zoekresultaat.
2. **Er komt geen sjabloon, dus de letterlijkheid wordt niet gecontroleerd** (W07, W12, W15: geen `antwoord`-event, grounding
   `onbepaald`, "geen vindplaats of citaat genoemd – niets te controleren"). W08 uit de graaf krijgt wel het sjabloon `bepaling`,
   met de tekst uit de code. Een artikel van overheid.nl hoort net zo te lopen: het sjabloon `bepaling` (of `extern`) met de
   rijen van `get_wettekst`, zodat de code de tekst levert en niet het model. Dat lost ook bevinding 1 op (`geciteerd`).
3. **Het model bladert zelf door één artikel** (W15: 3 aanroepen, 42 rijen; W07: 2 aanroepen, 18 rijen). Een pagina van 10–19
   rijen breekt één artikel op, en elke extra ronde leest de hele context opnieuw: 131k en 144k tokens. **Oplossing:** lever een
   gevraagd artikel in zijn geheel (de pagina geldt dan per artikel), of laat de code vooraf alle pagina's lezen.
4. **Een eerdere tekst van een regeling in de graaf gaat niet vooraf** (W07). De code kent het BWB-id al uit de graaf, toch
   deed het model eerst `zoek_regelingen`. Daarna volgden 7 rondes en 83 s. Een genoemd artikel met een peildatum buiten de
   graaftoestand kan dezelfde vooraf-stap volgen als een regeling buiten de graaf.
5. **De annotatieworker herkent BW 7:610 niet** (W16). `get_bronnode` kreeg een leeg BWB-id, en de jurist las "Ongeldig
   BWB-id" in plaats van "staat niet in de kennisgraaf, annoteren kan pas na een import". De herkenning uit
   `agent/buiten_graaf.py` hoort ook vóór de annotatieworker.
6. **Met de connector uit loopt het via het model** (W14, 46k). Het antwoord is goed, maar het model koos `search_wetgeving`.
   De melding `niet_in_graaf` → `bron_uit` komt alleen uit de leestools van de graaf. De herkenning van een genoemde regeling
   buiten de graaf kan ook zonder connector, en dan direct die melding geven.

## Niet gemeten

W01, W02, W03, W05, W06, W09, W10, W11, W13, W17 en W18 heb ik niet gedraaid, omdat het budget op was. W15 liep wel langs
dezelfde vooraf-route als W01. Een vervolgmeting na de oplossingen voor 1–3 zou naar verwachting veel goedkoper zijn: W12 kostte
19k, W08 2k.

## Wat deze meting niet zegt

- Het is één run per vraag, dus over de spreiding zegt dit niets.
- Over zoeken (W03, W05, W10), opbouw (W06), BW Boek 7 (W02), een historische tekst buiten de graaf (W09), niets gevonden
  (W11), een bepaling die nog niet in werking is (W13), graaf en connector in één antwoord (W17) en een groot document (W18) zegt
  deze meting niets.
