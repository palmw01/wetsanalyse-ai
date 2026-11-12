# Wetgeving buiten de kennisgraaf: iteratie, ronde 5 – 12 november 2026

- **Soort:** *meting*.
- **Code:** master `e7e2ab8a` (bundels 49 tot en met 51):
  - #1251 het sjabloon in één ronde;
  - #1252 telvragen via de lijstroute;
  - #1253 de id-controle in `tool_execution`;
  - #1255 de beweringentoets;
  - #1257 geen dubbel antwoord in het denkproces.
- **Straat:** acceptatie.
- **Model:** `claude-sonnet-4-6`.
- **Uitvoering:** zoals ronde 1 ([`ronde-1.md`](ronde-1.md)).
  - Na I17 was het tokenbudget van het gedeelde account op.
  - Na de reset (09:16 UTC) zijn I18–I24 opnieuw gestart, zonder de vraag een tweede keer te bewaren.
- **Lijstvragen:** daarnaast vier lijstvragen voor Kamerstukken en Rechtspraak (L-K1, L-K2, L-R1, L-R2), als
  regressietoets voor #1251.

De ruwe gegevens staan in [`ronde-5-runs.jsonl`](ronde-5-runs.jsonl). Tokens zijn invoer, uitvoer, cache lezen en cache
schrijven samen, uit het `meting`-event. Het veld `sjabloon` komt uit hetzelfde event (nieuw in #1251).

## Score

**27 goed, 3 deels, 0 fout.** Ronde 4 had 26 goed, 2 goed op één zin na (apart geteld) en 2 deels.

**Tokens:** samen 1.331.629, tegen 1.192.260 in ronde 4.
- Het verschil zit in I02 (+124k), I12 (+52k) en I20 (+49k).
- I13, I24, I28 en I06 werden goedkoper (samen −90k).

**Correctierondes:** geen, ook niet van de beweringentoets (#1255).

| vraag | soort | oordeel (r4 → r5) | tokens (r4 → r5) | `sjabloon` |
|---|---|---|---|---|
| I01 | zoeken op onderwerp | goed → **goed** | 90.150 → 91.768 | gevraagd 1, gevuld |
| I02 | combinatie Rechtspraak | goed → **deels** | 112.264 → 236.123 | gevraagd 1, geweigerd `extern.vul` 2, gemist |
| I03 | lezen | goed → **goed** | 964 → 968 | – |
| I04 | artikel lezen | goed → **goed** | 2.956 → 2.902 | – |
| I05 | BW-lid lezen | goed → **goed** | 388 → 366 | – |
| I06 | combinatie Staatsblad | goed → **goed** | 210.537 → 190.206 | gevuld |
| I07 | niet bestaand | goed → **goed** | 0 → 0 | – |
| I08 | artikel lezen | goed → **goed** | 901 → 896 | – |
| I09 | onderdeel lezen | goed → **goed** | 333 → 333 | – |
| I10 | AMvB lezen | goed → **goed** | 528 → 517 | – |
| I11 | ministeriële regeling lezen | goed → **goed** | 797 → 806 | – |
| I12 | beleidsregel opbouw | goed → **deels** | 160.430 → 212.623 | gevraagd 1, geweigerd `extern.vul` + `extern.lijsten`, gevuld |
| I13 | opbouw | goed\* → **goed** | 127.547 → 96.323 | geweigerd `extern.vul` 1, gevuld |
| I14 | zoeken in de tekst | goed\* → **goed** | 68.564 → 69.840 | gevraagd 1, gevuld |
| I15 | eerdere tekst, in de graaf | goed → **goed** | 1.813 → 1.816 | – |
| I16 | eerdere tekst, buiten de graaf | goed → **goed** | 686 → 689 | – |
| I17 | toekomstige datum | goed → **goed** | 925 → 938 | – |
| I18 | vervallen artikel | goed → **goed** | 310 → 313 | – |
| I19 | nog niet in werking | goed → **goed** | 529 → 532 | – |
| I20 | vervallen regeling | deels → **deels** | 135.710 → 185.192 | gevraagd 1, geweigerd `extern.vul` 1, gemist |
| I21 | de graaf gaat voor | goed → **goed** | 1.742 → 1.707 | – |
| I22 | dubbelzinnige afkorting | goed → **goed** | 0 → 0 | – |
| I23 | combinatie Kamerstukken | goed → **goed** | 0 → 0 | – (lijstroute) |
| I24 | BW-uitleg | goed → **goed** | 62.750 → 42.011 | geweigerd `bepaling.vul` 1, gevuld |
| I25 | vervolgvraag | goed → **goed** | 6.803 → 6.755 | – |
| I26 | opnemen buiten de graaf | goed → **goed** | 0 → 0 | – |
| I27 | toevoegen buiten de graaf | goed → **goed** | 0 → 0 | – |
| I28 | graaf en overheid.nl samen | goed → **goed** | 132.092 → 114.514 | geweigerd `duiding.vul` 2, gevuld |
| I29 | connector uit | goed → **goed** | 0 → 0 | – |
| I30 | telling en volledigheid | deels → **goed** | 72.541 → 73.491 | geweigerd `extern.vul` 1, tekst zonder lijst |

\* In ronde 4 goed op "(gezamenlijk behandeld: …)" na. Die zin is weg (#1243).

## De tellers van `meting.sjabloon` (de 30 vragen)

- **Herhaalverzoek (`gevraagd`): 5 keer** (I01, I02, I12, I14, I20). Elke keer had het model een lijst in tekst gezet.
  - AFRONDEN_EXTERN haalt het model bij een lijstvraag dus niet van de tekst af.
  - Bij uitleg rondt het model wel direct af met het sjabloon (I06, I13, I24, I28, L-K1, L-R1, L-R2).
- **Weigeringen: 10.** Per redencode:
  - `extern.vul`: 6 keer. Dat is een `kort_antwoord` dat ontbreekt, of een aanroep zonder stuk en zonder passage, zoals
    bij I30 (telling) en I13 (opbouw).
  - `duiding.vul`: 2 keer.
  - `extern.lijsten`: 1 keer (boven `MAX_LIJST`).
  - `bepaling.vul`: 1 keer.
- **`gemist`: 2 keer** (I02, I20). Na een weigering eindigde het model in vrije tekst.
- **`tekst_ernaast`:** tot 465 tekens (#1257 zet die tekst niet meer in het denkproces).

## Wat ronde 5 oploste

- **Geen ongevraagde lijst meer bij een telling of opbouw.**
  - I30 noemt 174 artikelen (150 geldend, 20 vervallen, 4 nog niet) zonder lijst: *deels* → *goed*.
  - I13 noemt de 14 hoofdstukken uit de bron, zonder de 25 artikelen eronder, en kost 96k in plaats van 128k.
- **"(gezamenlijk behandeld: …)" is weg** (I13, I14; #1243).
- **I24 en I28 zijn goedkoper** (42k en 115k in plaats van 63k en 132k).
- **De lijstvragen voor Kamerstukken en Rechtspraak** (L-K1, L-R1, L-R2) ronden direct af met het sjabloon, zonder
  herhaalverzoek, en zijn gegrond. Ze kosten 99k, 293k en 324k: veel uitspraken en stukken gelezen. L-R1 had twee
  weigeringen.

## Nieuwe bevindingen

1. **I12 (regressie, *deels*, 213k).**
   - Het model zette de opbouw als lijst van paragrafen in tekst.
   - Het herhaalverzoek noemde alle paragrafen uit die lijst, dus het model moest ze in 'stukken' zetten.
   - Daarna volgden twee weigeringen (`extern.vul`, en `extern.lijsten` boven `MAX_LIJST`) en 8 rondes.
   - Het antwoord eindigde met 25 van de 52 paragrafen, die niet gevraagd waren, en met "de limiet van 25 stukken per
     bron" (interne taal).
2. **Het sjabloon zonder stuk en passage** (I30, I13): de prompt zegt "bij een telling blijft 'stukken' leeg", maar
   `antwoord_extern` weigert een aanroep zonder stuk en zonder passage. Dat kost elke keer een ronde.
3. **Herhaalde weigeringen** (I02, I12, I28, L-R1): na twee weigeringen probeerde het model door, tot negen rondes.
4. **I20:**
   - **Beter dan in ronde 4:** geen geraden BWB-id meer (#1253).
   - **Wat nog niet goed is:**
     - eigen kennis in het antwoord ("vóór de digitale opbouw al ingetrokken"), die de beweringentoets niet vangt;
     - de bronnenlijst noemt de zeven regelingen uit `list_regelingen`.
5. **I02:**
   - LiDO gaf voor art. 31 Pw niets. Het antwoord noemt "542 vermeldingen" zonder lijst, en eindigde na een
     herhaalverzoek en twee weigeringen in vrije tekst.
   - De run kostte 236k en 472 s.
6. **L-K2:** de lijstroute zocht de hele woordgroep "bestuurdersaansprakelijkheid Invorderingswet 1990" in de tekst en
   vond niets.

## Oplossing (ronde 6, eigen PR)

Generiek, voor elke connector (`nodes/antwoord.py`, `nodes/sjabloon.py`):

1. **Een lijst in tekst zet de code zelf om** (`lijst_omzetten`), zonder modelronde (`omgezet`).
   - Alleen stukken die in deze beurt gevonden of gelezen zijn, en die de lijst bij id of label noemt, komen in het blok
     `stukken`. De rest van de tekst is het korte antwoord (`zonder_lijstregels`).
   - **Meer stukken dan één blok draagt** (`MAX_LIJST`, een opbouw zoals I12): de tekst is het antwoord
     (`lijst_aangenomen`).
   - **Het herhaalverzoek blijft alleen** als de lijst geen gevonden stuk noemt, als er naast de lijst geen uitleg staat,
     of als het sjabloon niet te vullen is.
2. **Na een tweede weigering in dezelfde beurt** vraagt de code geen derde poging maar een antwoord in tekst (`TEKST_NU`).
   - Na een weigering komt er geen herhaalverzoek meer.
   - Een weigering waarbij de code een genoemd artikel ophaalt, telt niet mee: daar is iets nieuws om aan te wijzen.
3. **De prompt zegt:** zonder stuk en zonder passage antwoord je in tekst (AFRONDEN_EXTERN, bevinding 2).
4. **De bewaking op interne taal** kent "de limiet van N" en "stukkenlijst" (bevinding 1).

## Gemeld, niet hier opgelost

- **I20, eigen kennis:** "vóór de digitale opbouw al ingetrokken" komt nergens vandaan, en de beweringentoets vangt het
  niet. Dat ligt bij Rechtspraak, die de toets bouwde.
- **I20, bronnenlijst:** de regelingen uit `list_regelingen` staan in de bronnenlijst (`provenance`, `REGELINGTOOLS`),
  terwijl het antwoord ze niet noemt. Gemeld bij de eigenaar van provenance.
- **I02, Rechtspraak:** een artikel dat LiDO niet kent levert een telling zonder lijst op.
- **L-K2, Kamerstukken:** de lijstroute zoekt de hele woordgroep in de tekst.
