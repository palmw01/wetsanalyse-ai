# Wetgeving buiten de kennisgraaf: iteratie, ronde 1 – 11 november 2026

Soort: *meting* · Code: master `1ba00b8f` (bundel 41: #1223 en eerdere) · Straat: acceptatie · Model: `claude-sonnet-4-6` ·
Uitvoering: de acceptatie-MCP, elke vraag één run in een eigen gesprek, met `bronnen: ["wetgeving_live"]`. I02, I06 en I23
draaien met de tweede connector erbij, I29 met de connector uit. Verbruik: deze keer geen grens.

De vragenset (30 vragen, met de verwachte route en de kern van het juiste antwoord, vooraf gecontroleerd tegen overheid.nl)
staat in [`vragenset.json`](vragenset.json). De ruwe gegevens per run staan in [`ronde-1-runs.jsonl`](ronde-1-runs.jsonl).
Tokens = invoer + uitvoer + cache lezen + cache schrijven uit het `meting`-event.

## Score

**15 goed, 13 deels, 2 fout**, samen **3.011.170 tokens**. Twee vragen nemen samen meer dan de helft daarvan: I13
(1,0M) en I20 (509k).

| vraag | soort | oordeel | tokens | duur |
|---|---|---|---|---|
| I01 | zoeken op onderwerp | goed | 65.957 | 16 s |
| I02 | combinatie Rechtspraak | deels | 93.967 | 24 s |
| I03 | lezen, onvolledige bron | deels | 81.775 | 22 s |
| I04 | artikel lezen | goed | 2.870 | 7 s |
| I05 | BW-lid lezen | goed | 377 | 7 s |
| I06 | combinatie Staatsblad | deels | 185.367 | 33 s |
| I07 | niet bestaand | deels | 44.073 | 12 s |
| I08 | artikel lezen | deels | 899 | 5 s |
| I09 | onderdeel lezen | deels | 2.904 | 5 s |
| I10 | AMvB lezen | deels | 82.434 | 22 s |
| I11 | ministeriële regeling lezen | deels | 84.971 | 26 s |
| I12 | beleidsregel opbouw | deels | 98.591 | 22 s |
| I13 | opbouw | fout | 1.035.240 | 62 s |
| I14 | zoeken in de tekst | goed | 44.959 | 17 s |
| I15 | eerdere tekst, regeling in de graaf | goed | 1.815 | 6 s |
| I16 | eerdere tekst, buiten de graaf | goed | 686 | 6 s |
| I17 | toekomstige datum | deels | 907 | 9 s |
| I18 | vervallen artikel | goed | 333 | 3 s |
| I19 | nog niet in werking | goed | 519 | 4 s |
| I20 | vervallen regeling | fout | 509.129 | 103 s |
| I21 | de graaf gaat voor | goed | 1.724 | 5 s |
| I22 | dubbelzinnige afkorting | goed | 0 | 0 s |
| I23 | combinatie Kamerstukken | goed | 0 | 1 s |
| I24 | BW-uitleg | goed | 41.029 | 18 s |
| I25 | vervolgvraag | deels | 85.579 | 32 s |
| I26 | opnemen buiten de graaf | goed | 0 | 0 s |
| I27 | toevoegen buiten de graaf | goed | 0 | 0 s |
| I28 | graaf en overheid.nl samen | deels | 325.909 | 185 s |
| I29 | connector uit | goed | 0 | 1 s |
| I30 | telling en volledigheid | deels | 219.156 | 26 s |
Wat goed gaat:
- **Een genoemd artikel** loopt via de workflow, in één ronde voor 333 tot 2.904 tokens: het hele artikel staat in het blok
  `extern`, met de letters van de onderdelen, één bron `wettekst_live` en `gegrond`. Zo gingen I04, I05, I08, I15, I16, I18
  en I19.
- **De vaste meldingen**, voor annoteren, opnemen, de connector uit en een dubbelzinnige afkorting, kosten 0 tokens (I22,
  I26, I27, I29).
- **De graaf gaat voor** (I21).
- **De combinatie met Kamerstukken** loopt via een lijst zonder model (I23).
- **De grenzen** noemt Lex eerlijk: een niet volledig leesbare toestand (I03, I12) en een niet-bestaande wet (I07).

## Bevindingen, oorzaak en oplossing

Opgelost in de PR van deze ronde (eigen code, met tests in `tests/test_wetgeving_live_routes.py` en
`tests/test_bepaling_workflow.py`):

1. **Geen opbouw, dus bladeren** (I13 fout, 21 rondes en 1,0M tokens zonder antwoord; I30 219k).
   - Oorzaak: `zoek_artikelen` gaf alleen artikelen, 25 tot 35 per pagina. Voor de hoofdstukken of het aantal vervallen
     artikelen bladerde het model alle pagina's door.
   - Oplossing: zonder woorden geeft de eerste pagina ook `opbouw` (de delen op het hoogste niveau, met aantal, eerste en
     laatste artikel) en `telling` (totaal, geldend, vervallen, nog niet in werking).
2. **Lid en onderdeel vielen weg** (I09).
   - Oorzaak: "tweede lid, onderdeel c" werd niet gelezen, want de herkenning kende alleen "lid N". `get_wettekst` had ook
     geen onderdeel-argument.
   - Oplossing: `lees_buiten` neemt lid en onderdeel uit `lees_aanwijzing` en de vorm "onderdeel c". `get_wettekst` krijgt
     `onderdeel` en houdt de aanhef van het lid erbij.
3. **Besluiten, regelingen en algemene wetten niet herkend** (I03, I10, I11, I12: 5 tot 6 rondes, 80 tot 100k).
   - Oorzaak: de kandidaten waren alleen een titel op -wet of een titel die met "Wet" begint.
   - Oplossing: ook een besluit of regeling met jaartal, "Algemene …wet" en "Besluit/Regeling" met woorden met een
     hoofdletter. De zoekdienst beslist daarna nog steeds op een exact gelijke titel.
4. **De bekendmaking van een artikel ontbrak** (I06: 7 rondes en 185k voor "welk Staatsblad").
   - Oplossing: `get_wettekst` geeft `publicatie` mee, de bron van het artikel uit de BWB als "Stb. 2025, 312". Dit is een
     nieuw metadataveld in de beschrijving van de connector.
5. **Een peildatum zonder toestand** (I20 fout, 18 rondes gissen naar BWB-id's, 509k, en een eindclaim uit eigen kennis).
   - Oplossing: `zoek_regelingen` zegt nu wat de BWB van een regeling met precies die titel heeft:
     - geen regeling ("raad geen BWB-id's");
     - de periode van haar teksten;
     - of dat ze op die datum onder een andere titel stond.
6. **Een toekomstige peildatum zonder nieuwe tekst** (I17).
   - Oorzaak: de tekst van nu kwam zonder enige uitleg.
   - Oplossing: een `Leemte` in code: "Voor 1 januari 2028 is in het Basiswettenbestand geen andere tekst bekend: dit is de
     tekst die geldt vanaf … Een latere wijziging kan nog worden gepubliceerd."
7. **R28b** (gedeeld, rechtspraak). Een vervolgvraag naar een stuk werd als wettekstvraag gelezen.
   - Oplossing:
     - een vraag die een stuk aanwijst (id, signaal van een andere connector, stukwoord), is geen tekstvraag;
     - een datum telt alleen als peildatum als de jurist hem typte.

Gemeld aan de hoofdsessie (gedeelde code, eigenaar nog aan te wijzen):

8. **supervisie**, het wetgeving-blok:
   - een herschreven vervolgvraag gaat niet langs `lees_buiten` (I25, 83k en leden in eigen woorden);
   - een stukvraag krijgt toch de wettekst vooraf (I02);
   - een genoemde Wet-titel die niet in het BWB staat, kan een vaste melding krijgen (I07).
9. **grounding**:
   - een gelezen maar ongebruikt `wettekst_live`-stuk blijft in de bronnenlijst (I20);
   - `curate_sources` houdt alle graafregelingen uit `search_wetgeving` als het antwoord geen BWB-id noemt (I07, I11, I20).
10. **bronmodel.bwb**:
    - de structuur van het BBBB (beleidsregel) is onbekend, dekking 0% (I12);
    - de hele Algemene douanewet wordt geweigerd bij 98,5% dekking, ook als het gevraagde artikel volledig gelezen is (I03).
11. **sjablonen/duiding**: een verwijzing naar een gelezen `wettekst_live`-artikel wordt geweigerd, en het model schreef de
    interne melding naar de jurist (I28, 12 rondes, 326k).
12. **Rechtspraak en provenance**:
    - `zoek_uitspraken` kent een regeling buiten de graaf niet;
    - een graaf-IRI uit dat foutresultaat kwam in de bronnenlijst (I02).

Open, niet in deze ronde:
- **De toelichting** van de workflow draait soms een uitzondering om of voegt iets toe (I08, I17). Dit geldt ook voor
  artikelen uit de graaf.
