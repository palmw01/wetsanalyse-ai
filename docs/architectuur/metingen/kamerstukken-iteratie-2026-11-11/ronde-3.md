# Kamerstukken, iteratieve verbeterrondes – ronde 3 (12 november 2026)

Soort: *meting* · Code: master `a0eeb8de` (bundel 45, #1238, met de PR van ronde 2, #1237) · Straat: acceptatie,
alle connectors aan · Model: `claude-sonnet-4-6` (Foundry) · Uitvoering: de acceptatie-MCP, elke vraag in een eigen
gesprek (de vervolgvragen K21–K22 en K23–K24 in één gesprek) · Vragenset: dezelfde 30 als in [ronde 1](ronde-1.md)
en [ronde 2](ronde-2.md).

De ruwe gegevens staan in [`runs.jsonl`](runs.jsonl) (`"ronde": 3`). De tokens zijn de som van cache lezen, cache
schrijven, uitvoer en invoer uit het `meting`-event.

**Een storing tijdens de ronde.** Rond 23:20 UTC gaf de documentenserver van KOOP time-outs, op acceptatie en
lokaal. K07, K10, K11 en K13 liepen in die tijd en zijn daarna in een nieuw gesprek opnieuw gedraaid; de tabel telt
de tweede run. De eerste K11 leverde wel een bevinding op (A1).

**Hoe er gekeken is.** Bij de lijstroute (geen model) en bij een vraag die gelijk bleef aan ronde 2 zijn route,
toolaanroepen, meting en controle nagelopen, maar is de tekst niet opnieuw helemaal gelezen. Dat staat per vraag in de
notitie van `runs.jsonl`. De vragen waar ronde 2 een fix bracht (K04, K16, K17, K18, K21, K22, K30) zijn helemaal gelezen.

## Uitkomst

**26 goed, 3 deels, 1 fout. Samen 2,51M tokens** (ronde 2: 23 goed, 7 deels, 0 fout, 2,33M tokens). De hogere som komt
uit één vraag: K07 kostte 779k (ronde 2: 359k).

| vraag | oordeel (ronde 2 → 3) | modelrondes | tokens |
|---|---|---|---|
| K01 | goed → **goed** | 0 → 0 | 0 → 0 |
| K02 | goed → **goed** | 0 → 0 | 0 → 0 |
| K03 | goed → **goed** | 0 → 0 | 0 → 0 |
| K04 | deels → **goed** | 0 → 0 | 0 → 0 |
| K05 | goed → **goed** | 0 → 0 | 0 → 0 |
| K06 | goed → **goed** | 0 → 0 | 0 → 0 |
| K07 | goed → **goed** | 10 → 16 | 359k → 779k |
| K08 | goed → **goed** | 0 → 0 | 0 → 0 |
| K09 | goed → **goed** | 0 → 0 | 0 → 0 |
| K10 | deels → **deels** | 7 → 7 | 224k → 224k |
| K11 | goed → **goed** | 3 → 1 | 95k → 34k |
| K12 | goed → **goed** | 0 → 0 | 0 → 0 |
| K13 | goed → **goed** | 1 → 1 | 30k → 34k |
| K14 | goed → **goed** | 2 → 1 | 60k → 34k |
| K15 | goed → **goed** | 6 → 7 | 219k → 267k |
| K16 | deels → **deels** | 10 → 10 | 342k → 356k |
| K17 | deels → **deels** | 9 → 7 | 281k → 214k |
| K18 | deels → **goed** | 5 → 5 | 159k → 160k |
| K19 | goed → **goed** | 2 → 1 | 61k → 30k |
| K20 | goed → **goed** | 4 → 4 | 98k → 96k |
| K21 | deels → **goed** | 0 → 0 | 0 → 0 |
| K22 | goed → **fout** | 2 → 1 | 34k → 3k |
| K23 | goed → **goed** | 0 → 0 | 0 → 0 |
| K24 | goed → **goed** | 3 → 3 | 61k → 61k |
| K25 | goed → **goed** | 0 → 0 | 0 → 0 |
| K26 | goed → **goed** | 5 → 5 | 119k → 121k |
| K27 | goed → **goed** | 0 → 0 | 0 → 0 |
| K28 | goed → **goed** | 3 → 2 | 95k → 68k |
| K29 | goed → **goed** | 1 → 1 | 29k → 33k |
| K30 | deels → **goed** | 3 → 0 | 60k → 0 |

Wat ronde 2 opleverde:
- **De gezamenlijke behandeling staat in de lijst** (K04, K21, K25): "Kamerstukken 33752, nr. L … (gezamenlijk
  behandeld: 33752–33755)".
- **De grens van KOOP** (K16, K17): het model schrijft nu dat het oude dossier "ouder dan het vergaderjaar 1994–1995"
  is en dat de zoekdienst niet verder teruggaat, en niet meer dat het "alleen als PDF" bestaat.
- **De PDF-zin herhaalt zich niet** (K12): "alleen als PDF (onopgemaakt)".
- **Van andere sessies** (in bundel 45):
  - Stb. 2013, 568 staat bij de bronnen (K18);
  - "Zoek kamerstukken over …" is een lijstvraag (K30: 0 tokens, een vaste leemte met de zoekvraag);
  - een genoemd stuk wordt vooraf gelezen. Bij K11, K13, K14, K19 en K29 kost dat één ronde, waar het er eerst twee of
    drie waren.

## Bevindingen, per oorzaak

### A. Eigen code (deze ronde opgelost)

1. **Een onbereikbare bron gaat langs het model** (de eerste K11, tijdens de storing).
   - `get_kamerstuk` gaf `bron_onbereikbaar`, en het model schreef: "zoek het stuk op via kamerstukken.nl met het nummer
     33755, onderdeel 3". Die site en dat "onderdeel" kende het niet; de controle zei ongegrond.
   - Bij alleen een PDF en niet gevonden zegt de code het al zelf (`bron_lezen._zonder_tekst`, ronde 1). Een storing
     hoort daar ook bij, voor elke connector.
2. **Een lettercode uit een gezamenlijke behandeling wordt niet gevonden** (K22, fout).
   - Op "het laatste stuk van dossier 33755" (33752 nr. L) vroeg "wat staat erin?" om `kst-33755-L`: de supervisor
     herschreef de vervolgvraag met het dossier van de lijst. KOOP kent alleen `kst-33752-L`, en Lex zei "niet gevonden".
   - In ronde 2 schreef de supervisor het goede id; het verschil is toeval van het model. De adapter hoort het op te
     vangen: een lettercode van de Eerste Kamer (A, B, … L) geldt voor de hele reeks, en het stuk heet naar het eerste
     dossier. Een nummer in cijfers hoort bij één dossier, dus daar geldt het niet (een bestaande test bewaakt dat).
3. **Een stuk doorzoeken kan alleen met offsets** (K07, 16 rondes, 779k).
   - Het model las drie stukken van 30322 en zocht de passages over de bestuurder met tien offsets. Inhoudelijk is het
     antwoord goed, maar dezelfde vraag kostte in ronde 2 de helft.
   - `zoek_kamerstukken` zoekt in de tekst van álle stukken, maar binnen één stuk kon het niet.
4. **De inhoudpagina blijft op het bovenste niveau** (K15, B3 van ronde 2; `stuk_tekst`, aan deze sessie toegewezen).
   - Gemeten op kst-36200-IX-2 (K15) en Stb. 2009, 610 (B16, de verzamelwet van Staatsblad), voor twee varianten:
     - **variant 1**, een kop met alleen zijn eigen naam en een `diepte` op de eerste pagina. Bij K15 kost niveau 3 dan
       nog 2.330 tekens, en de grens van de inhoud is 2.000; het helpt dus niet. Bij B16 groeit de inhoud van 1.167 naar
       1.557 tekens (het veld `diepte` per kop).
     - **variant 2**, `inhoud: true` zo diep als in één antwoord past, met eigen naam en `diepte`. Bij K15 komen dan 40
       koppen tot niveau 3 (3,3k tekens), met "Artikel 1 Belastingen" op offset 375. Bij B16 past niveau 2 niet naast de
       aanhef per artikel, dus blijft het zoals het was.
   - Gekozen: variant 2. De eerste pagina zegt `inhoud_dieper` met `inhoud_openen` als de inhoudpagina verder gaat. Het
     bronvenster leest alleen de eerste pagina en verandert niet.

### B. Gedeelde code (gemeld bij de hoofdsessie, niet in deze PR)

5. **Een alleen-PDF-stuk staat bij de bronnen met het kale id** (K12): "kst-1278484" in plaats van "Kamerstukken
   32140, nr. 342". Nieuw sinds bundel 45; het blok `stukken` heeft het goede label.
6. **Een stuk dat een voetnoot noemt, staat bij de bronnen** (K11, K18): Stb. 2013, 9 komt uit een voetnoot van
   kst-33755-3 en is niet gelezen. Ook nieuw sinds bundel 45 (de citeervorm telt als genoemd).
7. **Een lijst uit meer zoekvragen mist zoekvraag en totaal** (K17): 24 stukken uit vier zoekvragen door elkaar, ook
   moties over een andere wet.

### C. Wat het model doet

8. **Alle 88 amendementen doorbladeren om er 25 te tonen** (K10, 5 pagina's). De toelichting zegt sinds ronde 2 dat
   18 van de 25 passen, en het model bladert toch.
9. **"Wat bedoelde de wetgever" leunt op de rechtspraak** (K16), en het dossiernummer van de Invorderingswet 1990
   wisselt tussen runs (20588 in K16, 21287 in K17). Dat valt bij KOOP niet na te gaan, want het staat er niet in.

## Wat de PR van ronde 3 verandert

1. `bron_lezen._zonder_tekst`: `bron_onbereikbaar` krijgt een vaste melding ("Kamerstukken is nu niet te bereiken, dus
   kst-33755-3 kan ik niet lezen. Vraag het over een paar minuten opnieuw"), met een test per connector.
2. `SruKamerstukken._terugval`: een lettercode die niet in het hoofddossier staat, vindt het stuk in een gezamenlijke
   behandeling, als dat eenduidig is. Live: `kst-33755-L` wordt `kst-33752-L`, en `kst-33755-1` blijft zichzelf.
3. `get_kamerstuk(woorden=…)`: de alinea's van één stuk die elk woord noemen (de stam van zeven letters, in de tekst of
   de kop), met hun offset. Live: in kst-30322-3 noemen 5 van de 210 alinea's "bestuurder loonbelasting", met de
   toelichting op art. 36b op offset 29 en 31.
4. `stuk_tekst.inhoudpagina`: variant 2 (zie A4), met `inhoud_dieper` op de eerste pagina en een tekst in `INHOUD_ARG`.

## Wat deze meting niet zegt

Dit is één run per vraag. K07 laat zien hoe groot de spreiding bij dezelfde vraag kan zijn (359k en 779k). Tijdens de
storing van KOOP zijn vier vragen opnieuw gedraaid; de eerste runs staan niet in de tabel. De fixes van deze ronde staan
nog niet op acceptatie, dus hun effect op het model is niet gemeten, alleen de toolresultaten. Het oordeel is van deze
sessie, tegen de bron; het is geen juridisch oordeel over de stukken.
