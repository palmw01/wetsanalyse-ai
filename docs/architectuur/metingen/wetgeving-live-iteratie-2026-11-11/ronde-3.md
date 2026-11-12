# Wetgeving buiten de kennisgraaf: iteratie, ronde 3 – 12 november 2026

- **Soort:** *meting*.
- **Code:** master `a0eeb8de` (bundel 45, met #1236 uit ronde 2).
- **Straat:** acceptatie.
- **Model:** `claude-sonnet-4-6`.
- **Uitvoering:** zoals ronde 1 ([`ronde-1.md`](ronde-1.md)):
  - de acceptatie-MCP, elke vraag één run in een eigen gesprek, met `bronnen: ["wetgeving_live"]`;
  - I02, I06 en I23 met de tweede connector;
  - I29 met de connector uit;
  - I25 in twee beurten.

I23 tot en met I30 gaven eerst een 429, want het gedeelde budget was op. Na de reset om 23:33 UTC zijn ze opnieuw
gestart, zonder dat de vraag een tweede keer werd bewaard.

De ruwe gegevens staan in [`ronde-3-runs.jsonl`](ronde-3-runs.jsonl). Tokens zijn invoer, uitvoer, cache lezen en
cache schrijven samen, uit het `meting`-event.

## Score

**24 goed, 6 deels, 0 fout.** Ronde 2 had 22 goed, 7 deels en 0 fout, met I12 apart.

Samen kost de ronde **1.836.261 tokens**; zonder I12 is dat 1.583.662. Ronde 2 kostte 1.747.246, met I12 op
bundel 41 (40.240).

De lat is gelijk aan die van ronde 2. Een lijst moet een link, de zoekvraag en het totaal dragen. Een zin in de
lijst die niet klopt (I14, I30) telt als *deels*.

| vraag | soort | oordeel (r2 → r3) | tokens (r2 → r3) | duur |
|---|---|---|---|---|
| I01 | zoeken op onderwerp | deels → **goed** | 89.374 → 89.991 | 21 s |
| I02 | combinatie Rechtspraak | deels → **deels** | 122.792 → 82.690 | 56 s |
| I03 | lezen, onvolledige bron | deels → **goed** | 89.460 → 966 | 6 s |
| I04 | artikel lezen | goed → **goed** | 2.897 → 2.936 | 10 s |
| I05 | BW-lid lezen | goed → **goed** | 353 → 381 | 8 s |
| I06 | combinatie Staatsblad | goed → **goed** | 240.750 → 117.267 | 52 s |
| I07 | niet bestaand | goed → **goed** | 0 → 0 | 0 s |
| I08 | artikel lezen | goed → **goed** | 940 → 892 | 9 s |
| I09 | onderdeel lezen | goed → **goed** | 330 → 360 | 8 s |
| I10 | AMvB lezen | goed → **goed** | 514 → 517 | 9 s |
| I11 | ministeriële regeling lezen | goed → **goed** | 793 → 797 | 9 s |
| I12 | beleidsregel opbouw | goed → **goed** | 130.474 → 252.599 | 114 s |
| I13 | opbouw | deels → **deels** | 416.889 → 630.523 | 252 s |
| I14 | zoeken in de tekst | goed → **deels** | 67.756 → 68.523 | 36 s |
| I15 | eerdere tekst, regeling in de graaf | goed → **goed** | 1.799 → 1.822 | 12 s |
| I16 | eerdere tekst, buiten de graaf | goed → **goed** | 676 → 687 | 12 s |
| I17 | toekomstige datum | goed → **goed** | 925 → 905 | 4 s |
| I18 | vervallen artikel | goed → **goed** | 302 → 318 | 3 s |
| I19 | nog niet in werking | goed → **goed** | 520 → 500 | 3 s |
| I20 | vervallen regeling | deels → **deels** | 187.022 → 220.362 | 59 s |
| I21 | de graaf gaat voor | goed → **goed** | 1.742 → 1.742 | 4 s |
| I22 | dubbelzinnige afkorting | goed → **goed** | 0 → 0 | 1 s |
| I23 | combinatie Kamerstukken | goed → **goed** | 0 → 0 | 1 s |
| I24 | BW-uitleg | goed → **goed** | 62.336 → 62.307 | 25 s |
| I25 | vervolgvraag | goed → **goed** | 6.823 → 6.779 | 14 s |
| I26 | opnemen buiten de graaf | goed → **goed** | 0 → 0 | 0 s |
| I27 | toevoegen buiten de graaf | goed → **goed** | 0 → 0 | 0 s |
| I28 | graaf en overheid.nl samen | deels → **deels** | 353.524 → 220.062 | 123 s |
| I29 | connector uit | goed → **goed** | 0 → 0 | 1 s |
| I30 | telling en volledigheid | deels → **deels** | 98.729 → 72.335 | 18 s |

## Wat ronde 2 oploste

- **"Artikel 1:1 van de Algemene douanewet"** (I03) loopt nu langs de workflow: zes leden letterlijk, 966 tokens. In
  ronde 2 kostte dat 89k via het model.
- **De lijst onder het antwoord** draagt nu een link, de zoekvraag en het totaal: "3 van de 82 stukken" (I01),
  "7 stukken" (I14) en "17 van de 174" (I30). Daardoor gaat I01 van *deels* naar *goed*.
- **Een eerdere tekst** heet in het label "eerdere tekst, geldig van 2020-01-01 tot en met 2020-05-31" (I15, I16).
- **Twee apart gelezen leden** zijn elk een eigen stuk (I28). Het antwoord toont lid 1 en lid 2 van artikel 2:9 BW
  apart.

## Nieuwe bevindingen en oplossingen (deze PR)

1. **De duiding van een regeling buiten de graaf was niet te vullen** (I12, I13, I24, I28).
   - **Het probleem:** het duidingsjabloon eist ten minste één passage in `onderbouwing`, en daar past alleen
     wettekst uit de kennisgraaf. Bij een regeling buiten de graaf kon het model dus niets aanwijzen. Het schreef het
     antwoord opnieuw (I13 acht keer, I28 vijf keer), tot het overstapte op het sjabloon voor bronnen naast de wet.
   - **De kosten:** I13 kostte 631k tokens en 252 s, I12 253k (in bundel 44 nog 130k), I28 220k en I24 drie pogingen.
   - **Erger:** zette het model de tekst van overheid.nl in `onderbouwing`, dan zei de weigering "haal de bepaling op
     met get_artikel". Het model las daarop dezelfde leden opnieuw: 2.3 en 2.7 Wet IB 2001 elk drie keer, 2:9 lid 1 en
     2 BW twee keer.
   - **Oplossing:** `duiding.vul` laat `onderbouwing` leeg als `extern` een gelezen stuk van overheid.nl aanwijst
     (`live_stukken`). Die tekst is dan de onderbouwing.
   - Een weigering zonder passage noemt het id van het gelezen stuk en zegt dat het in `extern` hoort.
   - Een gelezen stuk van overheid.nl in `onderbouwing` krijgt dezelfde zin (`_live_van`): "staat al in het gesprek …
     lees haar niet opnieuw".
   - Een Kamerstuk of uitspraak telt hier niet als onderbouwing: wat de wet zegt, onderbouwt alleen wettekst.

2. **Een gelezen artikel had in de lijst de titel van de wet** (I13).
   - **Het probleem:** "Artikel 2.3 …: Wet inkomstenbelasting 2001" stond tussen "Artikel 2.4: Bepalingen
     heffingsgrondslagen". Het stuk van `get_wettekst` vervangt de zoekrij.
   - **Oplossing:** het stuk draagt het opschrift van de bepaling ("Middelen"). Het label noemt de regeling al.

3. **Een geraden BWB-id leek een andere wet** (I20).
   - **Het probleem:** de fout zei alleen "BWBR0002471 heeft geen toestand die op 1995-01-01 geldt". Dat id is de Wet
     op de loonbelasting 1964, niet de Wet op de inkomstenbelasting 1964.
   - **Oplossing:** de fout noemt de titel van de regeling bij dat id.
   - Het raden zelf is niet weg; zie *Open*.

## Gemeld, niet hier opgelost (gedeelde code)

- **"(gezamenlijk behandeld: Hoofdstuk 3 … en § 3.2 …)" bij elke artikelrij** (I13, I14, I30). Gemeld bij Kamerstukken.
  - `bronmodel.antwoord.reeks_tekst` leest elke `reeks` als Kamerstukkendossiers.
  - Voor wetgeving_live is `reeks` volgens de beschrijving de plek in de regeling (`MetadataVeld("reeks", "plek in de
    regeling")`).
  - De zin hoort uit het label van het veld bij de connector te komen, of alleen bij een reeks van dossiers te staan.
  - De frontend (`reeksTekst`) doet hetzelfde.
- **"artikel 31 van Wet werk en bijstand"** in de zoekvraag van `zoek_uitspraken`, bij een vraag over de Participatiewet
  (I02). LiDO geeft de oude citeertitel. Gemeld bij Rechtspraak.
- **Nog open uit ronde 2**, beide bij Rechtspraak:
  - `urn:bwb:BWBR0015703` uit `zoek_uitspraken` staat in de bronnenlijst (I02);
  - "artikel 6:162" en "artikel 2:9" blijven onbevestigd (I24, I28).

## Open (model, niet in code gevangen)

- **I20:**
  - **Wat goed ging:** het antwoord zegt nu eerlijk dat de tekst van 1995 niet gevonden is, en toont geen verkeerde
    wettekst meer.
  - **Wat niet goed ging:** het model raadde drie BWB-id's en zette eigen kennis in de uitleg ("per 1 januari 2001
    vervangen"). Ook toonde het negen wijzigingswetten als lijst.
  - Een bewaking die een BWB-id weigert dat in de vraag noch in een eerdere uitkomst staat, hoort in `tool_execution`.
    Dat is gedeelde code.
- **I30:** de lijst van 17 artikelen was niet gevraagd. De zin "twee thematische tussenhoofdstukken" komt nergens
  vandaan.
