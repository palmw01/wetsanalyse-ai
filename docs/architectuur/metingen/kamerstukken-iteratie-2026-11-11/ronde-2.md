# Kamerstukken, iteratieve verbeterrondes – ronde 2 (11 november 2026)

Soort: *meting* · Code: master `80ca14f4` (bundel 43, #1232, met de PR van ronde 1, #1227) · Straat: acceptatie, alle
connectors aan · Model: `claude-sonnet-4-6` (Foundry) · Uitvoering: de acceptatie-MCP, elke vraag in een eigen gesprek
(de vervolgvragen K21–K22 en K23–K24 in één gesprek) · Vragenset: dezelfde 30 als in [ronde 1](ronde-1.md)
([`tests/data/kamerstukken_vragenset_30.json`](../../../../tools/graph-qa/tests/data/kamerstukken_vragenset_30.json)).

De ruwe gegevens staan in [`runs.jsonl`](runs.jsonl) (`"ronde": 2`). De tokens zijn de som van cache lezen, cache
schrijven, uitvoer en invoer uit het `meting`-event. Deze keer liepen er soms twee of drie vragen tegelijk. Dat raakt
de tokens per run niet. Het oordeel is nagegaan tegen de bron. De twijfelgevallen zijn met de eigen tools tegen KOOP
gecontroleerd, lokaal en met dezelfde adapter.

## Uitkomst

**23 goed, 7 deels, 0 fout. Samen 2,33M tokens** (ronde 1: 16 goed, 12 deels, 2 fout; 3,62M tokens). Negen vragen gaan
een stap omhoog. Geen enkele vraag gaat omlaag.

| vraag | oordeel (ronde 1 → 2) | modelrondes | tokens |
|---|---|---|---|
| K01 | goed → **goed** | 0 → 0 | 0 → 0 |
| K02 | goed → **goed** | 0 → 0 | 0 → 0 |
| K03 | goed → **goed** | 0 → 0 | 0 → 0 |
| K04 | deels → **deels** | 0 → 0 | 0 → 0 |
| K05 | goed → **goed** | 0 → 0 | 0 → 0 |
| K06 | goed → **goed** | 0 → 0 | 0 → 0 |
| K07 | deels → **goed** | 19 → 10 | 961k → 359k |
| K08 | goed → **goed** | 0 → 0 | 0 → 0 |
| K09 | fout → **goed** | 0 → 0 | 0 → 0 |
| K10 | deels → **deels** | 9 → 7 | 315k → 224k |
| K11 | goed → **goed** | 4 → 3 | 129k → 95k |
| K12 | goed → **goed** | 1 → 0 | 27k → 0 |
| K13 | goed → **goed** | 1 → 1 | 30k → 30k |
| K14 | fout → **goed** | 1 → 2 | 0,4k → 60k |
| K15 | deels → **goed** | 11 → 6 | 450k → 219k |
| K16 | deels → **deels** | 14 → 10 | 510k → 342k |
| K17 | deels → **deels** | 11 → 9 | 383k → 281k |
| K18 | deels → **deels** | 6 → 5 | 196k → 159k |
| K19 | goed → **goed** | 2 → 2 | 61k → 61k |
| K20 | deels → **goed** | 4 → 4 | 97k → 98k |
| K21 | deels → **deels** | 0 → 0 | 0 → 0 |
| K22 | goed → **goed** | 3 → 2 | 65k → 34k |
| K23 | goed → **goed** | 0 → 0 | 0 → 0 |
| K24 | goed → **goed** | 4 → 3 | 97k → 61k |
| K25 | deels → **goed** | 0 → 0 | 0 → 0 |
| K26 | goed → **goed** | 4 → 5 | 90k → 119k |
| K27 | deels → **goed** | 1 → 0 | 27k → 0 |
| K28 | goed → **goed** | 3 → 3 | 94k → 95k |
| K29 | goed → **goed** | 1 → 1 | 29k → 29k |
| K30 | deels → **deels** | 3 → 3 | 60k → 60k |

Wat ronde 1 opleverde:
- **Een oud Kamerstuk heeft weer koppen** (K07). Bij kst-30322-3 werkt `inhoud` nu. Het model citeert de MvT en de nota
  van 30322 letterlijk over art. 36b, met 10 rondes in plaats van 19.
- **Het soortfilter staat op de rubriek** (K10). Het telt nu 88 amendementen bij het Belastingplan 2025, zonder de
  brieven met het woord in de titel.
- **Vaste meldingen uit code** (K12, K27). Een stuk dat alleen als PDF bestaat of niet gevonden wordt, gaat niet meer
  langs het model: 0 tokens. Het niet-bestaande id staat niet meer bij de bronnen.
- **De slotzin noemt het totaal** (K25): "16 stukken.".
- **Geen vals alarm bij een tabel** (K28). Tabel 1 is geopend, en `onbevestigd` is leeg.
- **Van andere sessies** (in bundel 43):
  - het onderwerp van een lijstvraag zonder werkwoord (K09: "inkomstenbelasting");
  - een genoemd stuk gaat vóór de bepalingsroute (K14: de MvT bij Artikel II in plaats van de wettekst van art. 29);
  - de toelichting bij een lijst op relevantie klopt (K20);
  - een lijst uit meer pagina's houdt zoekvraag en totaal (K10, K20);
  - meer alinea's per aanwijzing (K15: 6 rondes in plaats van 11).

## Bevindingen, per oorzaak

### A. Eigen code van Kamerstukken (deze ronde opgelost)

1. **Een lege uitkomst zegt niet waar de zoekdienst ophoudt** (K16, K17).
   - Dossier 20588, de Invorderingswet 1990 uit 1988–1990, gaf 0 stukken met de toelichting "Geen Kamerstukken in
     dossier 20588.".
   - Het model schreef daarna twee keer dat die stukken "alleen als PDF" bij KOOP staan. Dat klopt niet: het oudste
     Kamerstuk in de zoekdienst is van het vergaderjaar 1994-1995 (gemeten met `volgorde: oudste`), en wat ouder is, staat
     er niet in.
   - De grenzen van de connector zeiden dat ook niet.
2. **Een stuk uit een gezamenlijke behandeling staat er zonder uitleg** (K04, K21, K25).
   - In de lijst van dossier 33755 heten tien stukken "Kamerstukken 33752, nr. B…L", en het laatste stuk van 33755 is
     "33752, nr. L".
   - De data draagt `reeks: [33752, 33753, 33754, 33755]`, maar het antwoord zegt het niet. Dat was bevinding C14 van
     ronde 1. Het blijkt geen gedrag van het model: de regel van een stuk noemt de reeks niet.

### B. Gedeelde code (gemeld bij de hoofdsessie)

3. **De inhoud op de eerste pagina blijft op niveau 2** (K15; `stuk_tekst`, aan deze sessie toegewezen).
   - kst-36200-IX-2 (een begroting, vijf niveaus) krijgt de zeven koppen van niveau 2. Het model zocht "Artikel 1
     Belastingen" met vijf offsets.
   - De lus probeerde alleen alles, 2 en 1. Die probeert nu elke diepte, maar dat lost K15 niet op. Niveau 3 telt 32
     koppen (binnen `MAX_INHOUD`) van samen 4.554 tekens. De inhoud mag hoogstens een kwart van het paginabudget gebruiken
     (2.000 tekens), want de koppen dragen hun hele pad.
   - `inhoud: true` geeft alleen niveau 1 (hier twee koppen), dus ook die weg leidt niet dieper.
   - Open voor ronde 3: een inhoud die per kop alleen zijn eigen naam draagt, of een inhoudpagina op een diepere laag.
     Dat is een contractwijziging voor elke connector en voor het bronvenster.
4. **Een pagina geeft minder rijen dan `aantal`** (K10, K20; `per_eenheid`, niet van deze sessie).
   - `aantal: 25` levert 18 rijen op, omdat het paginabudget eerder op is.
   - Het model bladert dan zelf verder: bij K10 vijf pagina's om alle 88 amendementen te zien, terwijl het antwoord er 25
     toont.
5. **Een stuk in citeervorm telt niet als bron** (K18; `grounding`, niet van deze sessie). Stb. 2013, 568 is gelezen,
   maar alleen kst-33755-3 staat bij de bronnen. Dit was bevinding 10 van ronde 1.
6. **"Zoek kamerstukken over …" is geen lijstvraag** (K30; `bron_lijst`, niet van deze sessie). Het model antwoordt in
   vrije tekst, zonder sjabloon en zonder zoekvraag in woorden.

### C. Wat het model doet

7. **Een hele memorie van toelichting als passages** (K11, K18). Zonder vraag naar één onderdeel citeert het model elke
   alinea van kst-33755-3. Dat klopt letterlijk, maar het antwoord kiest niet.
8. **"Wat bedoelde de wetgever" leunt op de rechtspraak** (K16). De Kamerstukken van 30322 zijn gelezen, maar staan
   alleen als lijst in het antwoord. De uitleg komt uit HR 6 oktober 2023, ECLI:NL:HR:2023:1371.
9. **Een toolterm in de twijfel** (K14): "staat op offset 16 van hetzelfde stuk".

## Wat de PR van ronde 2 verandert

1. `zoek_kamerstukken` noemt bij een lege uitkomst de grens van de zoekdienst (`GRENS`, `EERSTE_VERGADERJAAR`). Dat geldt
   voor een dossier en voor een zoekvraag: "vanaf het vergaderjaar 1994-1995; wat ouder is, staat er niet in, ook niet
   als PDF". De `grenzen` van de connector zeggen het ook.
2. De regel van een stuk met een reeks zegt "(gezamenlijk behandeld: 33752–33755)": in de tekst (`bronmodel.antwoord`,
   `reeks_tekst`) en in de werkplek (`reeksTekst` in `lib/antwoord.ts`, de metaregel van het blok `stukken`).
3. `stuk_tekst.inhoud_van` probeert elke diepte, van diep naar ondiep, in plaats van alles, 2 en 1. Dat is een correcte
   verbreding; K15 lost het niet op (zie B3).

## Wat deze meting niet zegt

Dit is één run per vraag. De spreiding tussen runs is niet gemeten. Bij de vragen waar het model aan het werk is, kan
een deel van het verschil met ronde 1 toeval zijn: K26 kostte nu 5 rondes, waar het er eerst 4 waren. De lijstroute en
de vaste meldingen gebruiken geen model, en die uitkomsten zijn vast. Het oordeel goed, deels of fout is van deze sessie,
tegen de bron. Het is geen juridisch oordeel over de stukken.
