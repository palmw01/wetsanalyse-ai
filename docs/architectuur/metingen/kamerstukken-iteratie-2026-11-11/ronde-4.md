# Kamerstukken, iteratieve verbeterrondes – ronde 4 en eindverslag (12 november 2026)

Soort: *meting* · Code: master `229b9063` (bundel 47, #1245, met de PR van ronde 3, #1243) · Straat: acceptatie,
alle connectors aan · Model: `claude-sonnet-4-6` (Foundry) · Uitvoering: de acceptatie-MCP, elke vraag in een eigen
gesprek (de vervolgvragen K21–K22 en K23–K24 in één gesprek) · Vragenset: dezelfde 30 als in [ronde 1](ronde-1.md),
[ronde 2](ronde-2.md) en [ronde 3](ronde-3.md).

De ruwe gegevens staan in [`runs.jsonl`](runs.jsonl) (`"ronde": 4`). De tokens zijn de som van cache lezen, cache
schrijven, uitvoer en invoer uit het `meting`-event.

**Een onderbreking.** Na K06 was het tokenbudget van het account op (429 `budget_op`). De hoofdsessie zette het terug,
en K07–K12 liepen daarna in hun eigen gesprekken, zonder de vraag opnieuw te bewaren. Er is geen vraag twee keer
gedraaid.

**Hoe er gekeken is.** Bij de lijstroute (geen model) zijn route, filters, totaal en meting nagelopen. Bij de vragen met
een model zijn de tekst, de passages, de toolaanroepen en de bronnen gelezen, ook bij de vragen die in ronde 3 al goed
waren.

## Uitkomst

**27 goed, 3 deels, 0 fout. Samen 2,36M tokens** (ronde 3: 26 goed, 3 deels, 1 fout, 2,51M tokens).

| vraag | oordeel (ronde 3 → 4) | modelrondes | tokens |
|---|---|---|---|
| K01 | goed → **goed** | 0 → 0 | 0 → 0 |
| K02 | goed → **goed** | 0 → 0 | 0 → 0 |
| K03 | goed → **goed** | 0 → 0 | 0 → 0 |
| K04 | goed → **goed** | 0 → 0 | 0 → 0 |
| K05 | goed → **goed** | 0 → 0 | 0 → 0 |
| K06 | goed → **goed** | 0 → 0 | 0 → 0 |
| K07 | goed → **goed** | 16 → 11 | 779k → 392k |
| K08 | goed → **goed** | 0 → 0 | 0 → 0 |
| K09 | goed → **goed** | 0 → 0 | 0 → 0 |
| K10 | deels → **deels** | 7 → 7 | 224k → 227k |
| K11 | goed → **goed** | 1 → 1 | 34k → 34k |
| K12 | goed → **goed** | 0 → 0 | 0 → 0 |
| K13 | goed → **goed** | 1 → 1 | 34k → 34k |
| K14 | goed → **goed** | 1 → 1 | 34k → 34k |
| K15 | goed → **goed** | 7 → 7 | 267k → 264k |
| K16 | deels → **deels** | 10 → 14 | 356k → 504k |
| K17 | deels → **deels** | 7 → 8 | 214k → 259k |
| K18 | goed → **goed** | 5 → 5 | 160k → 162k |
| K19 | goed → **goed** | 1 → 1 | 30k → 30k |
| K20 | goed → **goed** | 4 → 4 | 96k → 98k |
| K21 | goed → **goed** | 0 → 0 | 0 → 0 |
| K22 | fout → **goed** | 1 → 2 | 3k → 34k |
| K23 | goed → **goed** | 0 → 0 | 0 → 0 |
| K24 | goed → **goed** | 3 → 3 | 61k → 63k |
| K25 | goed → **goed** | 0 → 0 | 0 → 0 |
| K26 | goed → **goed** | 5 → 5 | 121k → 122k |
| K27 | goed → **goed** | 0 → 0 | 0 → 0 |
| K28 | goed → **goed** | 2 → 2 | 68k → 69k |
| K29 | goed → **goed** | 1 → 1 | 33k → 34k |
| K30 | goed → **goed** | 0 → 0 | 0 → 0 |

Wat ronde 3 opleverde, gezien op acceptatie:
- **De lettercode in de reeks** (K22, was fout). De supervisor schreef de vervolgvraag weer als `kst-33755-L`, en de
  adapter vond het stuk als `kst-33752-L`. De motie Essers c.s. staat er volledig en letterlijk.
- **Zoeken binnen één stuk** (K07: 779k → 392k). In kst-30322-7 gaf `woorden: "bestuurdersaansprakelijkheid artikel
  36b"` zes alinea's. Inhoudelijk is het antwoord gelijk aan ronde 2 en 3.
- **De diepere inhoudpagina** (K15). Het model sprong met offset 375 naar "Artikel 1 Belastingen", die uit de
  inhoudpagina komt.
- **Van andere sessies** (bundel 46 en 47):
  - een alleen-PDF-stuk staat bij de bronnen met zijn label ("Kamerstukken 32140, nr. 342", K12);
  - een stuk uit een voetnoot staat niet meer bij de bronnen (K11, K18).

## Bevindingen, per oorzaak

### A. Eigen code (deze ronde opgelost)

1. **Nul treffers bij `woorden` zegt niet welk woord het stuk mist** (K07, K16).
   - Vijf keer gaf `get_kamerstuk(woorden=…)` nul treffers, telkens op woorden die elk wel in het stuk staan maar
     nooit samen. Voorbeelden: "bestuurdersaansprakelijkheid loonbelasting" in kst-30322-7 en "artikel 36 bestuurder
     aansprakelijk" in kst-29944-3 en kst-32129-3.
   - De toelichting zei alleen "probeer minder of andere woorden". Het model raadde dan welk woord eruit moest, en dat
     kostte telkens een ronde.
   - Nu telt `per_woord` in hoeveel alinea's elk woord los staat. Komt een woord nergens voor, dan zegt de toelichting
     welk woord weg kan; komt elk woord los voor, dan zegt ze dat er minder woorden tegelijk moeten.

### B. Gedeelde code of een andere connector (vervolgwerk, niet gebouwd)

2. **De tekst van Rechtspraak was tweemaal onbereikbaar** (K16): `get_uitspraak` gaf `bron_onbereikbaar` voor
   ECLI:NL:HR:2023:1371 en ECLI:NL:HR:2023:563, terwijl `zoek_uitspraken` (LiDO) wel antwoordde. Ik heb niet gemeten of
   het een storing was of de begrenzer. Dit is voor de Rechtspraak-sessie.
3. **Een telvraag gaat langs het model** (K26, "Hoeveel Kamerstukken hebben de Douanewet in de titel?"): één
   toolaanroep, vijf modelrondes, 122k tokens, en dat al drie rondes lang. Het totaal komt uit de bron (72). Een
   telvraag past in de lijstroute (`bron_lijst`), die gedeeld is.

### C. Wat het model doet

4. **Alle 88 amendementen doorbladeren om er 25 te tonen** (K10, vijf pagina's van 16–19). Zo gaat het sinds ronde 2,
   terwijl de toelichting zegt dat er 18 van de 25 passen.
5. **Wat niet in de bron staat** (K16, K17):
   - het dossiernummer 20588 voor de Invorderingswet 1990, dat KOOP niet heeft;
   - het advies de "fysieke archieven" te raadplegen;
   - in K17 de intrekking van 35930 nr. 12, die het model bij 36369 zet.

   De controle ziet dit niet, omdat het in de toelichting staat en niet in een citaat. K16 leunt verder op de wettekst
   en niet op de memorie.
6. **Een woord dat overal staat** (K15): `woorden: "Belastingdienst"` gaf 223 alinea's, en het model bladerde er drie
   pagina's van door. Het antwoord is goed, en de twijfel noemt wat niet gelezen is.

## Wat de PR van ronde 4 verandert

1. `get_kamerstuk(woorden=…)`: bij nul treffers met twee of meer woorden staan `per_woord` (stam → aantal alinea's) en
   een toelichting die zegt welk woord weg kan. Er is een test met de fixture kst-99001-3; één woord zonder treffer
   blijft zoals het was.

## Eindverslag over vier rondes

| ronde | code | goed | deels | fout | tokens | grootste kostenpost |
|---|---|---|---|---|---|---|
| 1 | `1ba00b8f` | 16 | 12 | 2 | 3,62M | K07 + K16 1,47M (oud schema zonder koppen) |
| 2 | `80ca14f4` | 23 | 7 | 0 | 2,33M | K16 342k, K07 359k |
| 3 | `a0eeb8de` | 26 | 3 | 1 | 2,51M | K07 779k (offsets in drie stukken) |
| 4 | `229b9063` | 27 | 3 | 0 | 2,36M | K16 504k, K07 392k |

- **Van 16 naar 27 goed**, en geen fout meer. De veertien vragen zonder model (lijstroute en vaste meldingen) kosten
  0 tokens en zijn sinds ronde 3 allemaal goed.
- **De tokens daalden met een derde** (3,62M → 2,36M). Wat er nog over is, zit in vier vragen: K07, K10, K15 en K16,
  samen 1,39M.
- **De drie vragen die deels blijven** (K10, K16, K17), zijn deels door wat het model doet (C4 en C5), niet door de
  connector. De bron levert wat ze kan; dat KOOP niet verder teruggaat dan 1994-1995, staat sinds ronde 2 in elk leeg
  resultaat.

Open vervolgwerk, buiten deze sessie: B2 (Rechtspraak), B3 (de telvraag in de lijstroute) en een toets op beweringen
in de toelichting die niet uit een gelezen stuk komen (C5).

## Wat deze meting niet zegt

Dit is één run per vraag. K16 laat de spreiding zien: 356k in ronde 3, 504k nu, bij hetzelfde oordeel. De fix van deze
ronde staat nog niet op acceptatie, dus het effect op het model is niet gemeten, alleen het toolresultaat. Het oordeel
is van deze sessie, tegen de bron; het is geen juridisch oordeel over de stukken.
