# Wetgeving buiten de kennisgraaf: iteratie, ronde 4 en eindverslag – 12 november 2026

- **Soort:** *meting*.
- **Code:** master `a995b0c0` (bundel 46, met #1241 uit ronde 3).
- **Straat:** acceptatie.
- **Model:** `claude-sonnet-4-6`.
- **Uitvoering:** zoals ronde 1 ([`ronde-1.md`](ronde-1.md)):
  - de acceptatie-MCP, elke vraag één run in een eigen gesprek, met `bronnen: ["wetgeving_live"]`;
  - I02, I06 en I23 met de tweede connector;
  - I29 met de connector uit;
  - I25 in twee beurten.

De ruwe gegevens staan in [`ronde-4-runs.jsonl`](ronde-4-runs.jsonl). Tokens zijn invoer, uitvoer, cache lezen en
cache schrijven samen, uit het `meting`-event.

## Score

**26 goed, 2 goed op één gedeelde zin na (apart), 2 deels, 0 fout.**

- Apart geteld zijn I13 en I14. Hun antwoord klopt, maar elke artikelrij zegt "(gezamenlijk behandeld: …)". De fix
  daarvoor (Kamerstukken, #1243) komt pas in bundel 47. Met de lat van ronde 3 zouden ze *deels* zijn.
- Ronde 3 had 24 goed, 6 deels en 0 fout.

Samen kost de ronde **1.192.260 tokens**. Ronde 3 kostte 1.836.261, ronde 2 1.747.246 en ronde 1 3.011.170.

| vraag | soort | oordeel (r3 → r4) | tokens (r3 → r4) | duur |
|---|---|---|---|---|
| I01 | zoeken op onderwerp | goed → **goed** | 89.991 → 90.150 | 23 s |
| I02 | combinatie Rechtspraak | deels → **goed** | 82.690 → 112.264 | 253 s |
| I03 | lezen, onvolledige bron | goed → **goed** | 966 → 964 | 8 s |
| I04 | artikel lezen | goed → **goed** | 2.936 → 2.956 | 12 s |
| I05 | BW-lid lezen | goed → **goed** | 381 → 388 | 10 s |
| I06 | combinatie Staatsblad | goed → **goed** | 117.267 → 210.537 | 46 s |
| I07 | niet bestaand | goed → **goed** | 0 → 0 | 0 s |
| I08 | artikel lezen | goed → **goed** | 892 → 901 | 5 s |
| I09 | onderdeel lezen | goed → **goed** | 360 → 333 | 3 s |
| I10 | AMvB lezen | goed → **goed** | 517 → 528 | 4 s |
| I11 | ministeriële regeling lezen | goed → **goed** | 797 → 797 | 5 s |
| I12 | beleidsregel opbouw | goed → **goed** | 252.599 → 160.430 | 74 s |
| I13 | opbouw | deels → **goed\*** | 630.523 → 127.547 | 71 s |
| I14 | zoeken in de tekst | deels → **goed\*** | 68.523 → 68.564 | 19 s |
| I15 | eerdere tekst, regeling in de graaf | goed → **goed** | 1.822 → 1.813 | 7 s |
| I16 | eerdere tekst, buiten de graaf | goed → **goed** | 687 → 686 | 6 s |
| I17 | toekomstige datum | goed → **goed** | 905 → 925 | 5 s |
| I18 | vervallen artikel | goed → **goed** | 318 → 310 | 4 s |
| I19 | nog niet in werking | goed → **goed** | 500 → 529 | 5 s |
| I20 | vervallen regeling | deels → **deels** | 220.362 → 135.710 | 48 s |
| I21 | de graaf gaat voor | goed → **goed** | 1.742 → 1.742 | 5 s |
| I22 | dubbelzinnige afkorting | goed → **goed** | 0 → 0 | 1 s |
| I23 | combinatie Kamerstukken | goed → **goed** | 0 → 0 | 1 s |
| I24 | BW-uitleg | goed → **goed** | 62.307 → 62.750 | 23 s |
| I25 | vervolgvraag | goed → **goed** | 6.779 → 6.803 | 14 s |
| I26 | opnemen buiten de graaf | goed → **goed** | 0 → 0 | 0 s |
| I27 | toevoegen buiten de graaf | goed → **goed** | 0 → 0 | 0 s |
| I28 | graaf en overheid.nl samen | deels → **goed** | 220.062 → 132.092 | 112 s |
| I29 | connector uit | goed → **goed** | 0 → 0 | 0 s |
| I30 | telling en volledigheid | deels → **deels** | 72.335 → 72.541 | 18 s |

\* Goed op "(gezamenlijk behandeld: …)" na; zie hierboven.

## Wat ronde 3 oploste

- **De duiding van een regeling buiten de graaf rust op `extern`** (#1241). Elk gelezen artikel wordt nog maar één
  keer gelezen.
  - I28 vergelijkt art. 33 Iw (graaf, drie passages) met 2:9 BW lid 1 en 2 (overheid.nl) in het duidingssjabloon,
    gegrond, voor 132k in plaats van 220k.
  - I13 kost 128k in plaats van 631k, met de hoofdstukken uit het veld `opbouw`.
  - I12 kost 160k in plaats van 253k.
- **Een geraden BWB-id noemt zijn regeling** (I20). De fout van `get_wettekst` zei nu "Wet op de loonbelasting 1964",
  en het model zette dat in de twijfel in plaats van de verkeerde wettekst te tonen. 136k in plaats van 220k.
- **Andere sessies:**
  - Rechtspraak: I02 noemt de Participatiewet in de zoekvraag, zonder graafbron. "Artikel 6:162" (I24) is nu bevestigd.

## Nieuwe bevindingen en oplossingen (deze PR)

1. **Een geraden BWB-id zei bij het zoeken alleen "niets gevonden"** (I20).
   - **Het probleem:** het model zocht `zoek_regelingen {bwb_id: BWBR0002471, peildatum: 1995-01-01}`. Pas de tweede
     tool (`get_wettekst`) zei welke wet dat id is.
   - **Oplossing:** een zoekvraag op een BWB-id zonder treffer noemt nu de titel, de soort en de periode van de teksten
     van dat id. Daarbij staat: "Is dat niet de regeling die je zoekt, gebruik dit id dan niet". Een id dat niet bestaat,
     krijgt "kent geen regeling met id …".
   - Het raden zelf (een id uit eigen kennis) is niet weg; zie *Gemeld*.
2. **"De tool meldt uitdrukkelijk …" kwam bij de jurist** (I20).
   - **Oplossing:** de bewaking op interne taal kent nu ook een tool als vertelstem ("de tool", "deze zoektool"). De zin
     valt weg, de rest van het antwoord blijft staan.

## Gemeld, niet hier opgelost (gedeelde code)

- **Elk antwoord via het model wordt twee keer geschreven** (I01, I12, I13, I14, I30, en ook de andere connectors).
  - Het model antwoordt eerst in tekst. Daarna vraagt de code om het sjabloon (`nodes/antwoord._gevonden_zonder_sjabloon`,
    `SJABLOON_GEVRAAGD`), waarna het model alles opnieuw schrijft.
  - Dat kost per vraag een volle modelronde: de 400 à 1.300 uitvoertokens en de context opnieuw, ongeveer 20 à 25k
    tokens.
  - **Voorstel:** na een geslaagde zoekronde van een connector de volgende modelstap het sjabloon laten aanroepen
    (`tool_choice`), in plaats van achteraf te vragen.
- **Een niet gevraagde lijst** (I30, I13).
  - `SJABLOON_GEVRAAGD` zegt "wijs de gevonden stukken aan in 'stukken'". Bij een telling of een opbouw zet het model
    daarom de eerste pagina artikelen onder het antwoord (I30: 17 van de 174, I13: 25 van de 514), terwijl de vraag
    daar niet om vroeg.
  - **Voorstel:** de opbouw van `zoek_artikelen` zonder `woorden` niet als "gevonden stukken" tellen, of de zin in het
    verzoek voorwaardelijk maken ("als de vraag om een lijst vraagt").
- **Weigeringen van het sjabloon zijn in de meting onzichtbaar** (I24: drie schrijfrondes, I28: drie). De reden staat
  alleen in de logs (`sjabloon niet te vullen`). Een telling met de redencode in het `meting`-event zou elke ronde
  zonder Grafana meetbaar maken.
- **Een BWB-id uit eigen kennis** (I20). Een bewaking die een id weigert dat in de vraag noch in een eerdere uitkomst
  staat, hoort in `tool_execution` (al gemeld in ronde 3).
- **"(gezamenlijk behandeld: …)"** (I13, I14, I30): Kamerstukken #1243, bundel 47.

## Eindverslag over de vier rondes

| ronde | code | goed | deels | fout | tokens |
|---|---|---|---|---|---|
| 1 | `1ba00b8f` (bundel 41) | 15 | 13 | 2 | 3.011.170 |
| 2 | `80ca14f4` (bundel 43) | 22 | 7 | 0 | 1.747.246 |
| 3 | `a0eeb8de` (bundel 45) | 24 | 6 | 0 | 1.836.261 |
| 4 | `a995b0c0` (bundel 46) | 26 (+2 apart) | 2 | 0 | 1.192.260 |

- **Kosten:** van ronde 1 naar ronde 4 daalden de tokens met 60 %. De grote posten verdwenen:
  - I13 van 1,0M naar 128k;
  - I20 van 509k naar 136k;
  - I28 van 354k naar 132k.
- **Workflowvragen:** een genoemd artikel, lid of onderdeel loopt in één ronde langs de workflow voor 300 à 3.000
  tokens. Een melding (niet bestaand, dubbelzinnig, connector uit, opnemen) kost 0.
- **Wat open blijft:** de dubbele schrijfronde en de niet gevraagde lijst (beide gedeeld), en het raden van een BWB-id
  bij een regeling die het BWB niet kent.
