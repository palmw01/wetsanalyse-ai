# ADR-016: een samenvatting rust per stuk op dat stuk (bundel 120, 14 nov 2026)

Soort: *meting*, licht regime: één run, alleen de vorm `centraal`, alleen D01, met akkoord van de gebruiker.

- **Code:** graph-qa op `c45cfd19` (bundel 120, #1509), `CENTRALE_AGENT=meten`. Daarin zit **#1508**:
  - een regel onder een kop die een stuk noemt, gaat over dat stuk;
  - een inhoudswoord uit de vraag in een duiding van een gelezen stuk, dat niet in dat stuk staat, is een bewering;
  - ook het rapport van een subagent rust op zijn eigen passages;
  - een afbakening die de jurist niet koos, noemt de code in het rapport, en het eind-event draagt `afbakening` en
    `gelezen`.
- **Nulpunt:** D01 in de meting van #1507 op `4e2e57a3`
  ([`../centrale-agent-2026-11-14-bundel119/bundel119.md`](../centrale-agent-2026-11-14-bundel119/bundel119.md)): 636k.
- **Hoe gemeten:** dezelfde vraag en dezelfde drie antwoorden als bij bundel 118 en 119, in een lokale kopie van de set
  die niet in de repo staat. Het kind stelde drie vragen, dus alle drie de antwoorden zijn gebruikt.
- **Vooraf:** de overzichtsvraag over de aanmaning gaf de zes artikelen: de graaf was gevuld.
- **Bewaking:** een kind stopt in de code bij 300k. Er stond één run op het programma; bundel 119 kostte 636k.
- **Totaal:** 572.864 tokens op het account; plafond 1M.

## Kort

| Punt uit #1508 | Uitkomst |
|---|---|
| 1. "Tijdig betalingsonmacht gemeld" bij HR:2023:563 | **Komt niet meer voor, maar zonder dat de toets ingreep.** Het hervatte deel las HR:2023:563 niet, en het antwoord noemt hem alleen onder *Niet inhoudelijk gelezen*. Er was niets tegen te houden of te herstellen |
| 2. De bewijslast bij HR:2023:181/184 | **Niet te toetsen.** Geen van beide uitspraken is gelezen of samengevat |
| 3. Het veld `stukken` in het tweede rapport | **Klopt met wat gelezen is, maar dekt de samenvatting niet.** Het noemt PHR:2025:435, GHARL:2025:1599 en PHR:2024:936, die deel 1 las. Deel 2 las zelf niets. Het rapport vat HR:2023:1371 als eerste samen, maar dat stuk staat niet in `stukken` en ook niet in `gelezen` |
| 4. Een afbakening die de jurist niet koos | **Gehaald in het rapport, niet in het eindantwoord.** Het rapport van deel 2 draagt `afbakening: ["tekst: huidige tekst"]`: het kind zocht alleen bij de huidige tekst van artikel 36 (40 treffers in 2022–2024). De periode staat er terecht niet in. Het eindantwoord noemt de afbakening niet, en de regel van het kind in het eind-event `regie` heeft geen veld `afbakening`, wel `gelezen` |
| 5. Valse treffers | **Geen.** `grounding`: *gegrond*, `unsupported` 0, `onbevestigd` 0. Geen correctieronde in de centrale agent of in een kind; beide rapporten werden in één keer gevuld. De ene weigering (`antwoord_extern:extern.vul:overig`) is van het sjabloon, niet van een toets. Kosten van de toetsen: 0 |

| Ook gemeten | Uitkomst |
|---|---|
| De vragen komen in één keer | **Gehaald.** Drie vragen (periode, instanties, aspect). Kaart 2 en 3 kwamen zonder modelronde (0 tokens, < 1 s) |
| De beurt met de vraag eindigt met alleen de kaart | **Gehaald.** Geen modelronde van de centrale agent |
| Citaten | **Geen blokcitaten.** `cited`: 2. De citaatcontrole vond één aanhaling die niet letterlijk is, maar dat is een vals alarm: de tekst tussen twee losse aanhalingstekens rond "lichtpuntjes" |
| Kosten | **573k**, tegen 636k bij #1507 (−10 %) en 626k bij #1504 |

**Wat naar T1/A1 gaat:**

1. **Het hervatte deel leest niets.** Het begint met 70k context, doet twee keer `zoek_uitspraken` (2022–2024, huidige
   tekst) en levert in de derde aanroep het rapport. Dat kost 226k. De aanroepen groeien van 71k naar 81k; na twee
   aanroepen (145k) kwam het rapport, vermoedelijk omdat een volgende ronde boven het plafond van 300k zou uitkomen. Van de
   40 treffers in de gekozen periode is er dus geen enkele door deel 2 gelezen.
2. **Binnen de gekozen periode staat één gelezen uitspraak in het antwoord.** Dat is PHR:2024:936, en die gaat over
   verjaring, niet over de melding. Twee van de vier blokken zijn uitspraken uit 2025, met de vermelding "buiten de
   periode". Bij bundel 119 waren het vijf blokken binnen de periode.
3. **HR:2023:1371 wordt samengevat zonder dat een kind hem las.** Het eindantwoord begint met "wat de subagent
   inhoudelijk heeft kunnen lezen" en zet HR:2023:1371 bovenaan. Geen van beide delen vroeg hem op: deel 1 las negen
   andere stukken, deel 2 geen. De inhoud komt uit PHR:2025:435, die de tussenbeslissing beschrijft. Het rapport zegt dat
   zelf ("aangehaald in PHR:2025:435, r.o. 3.9"), en het eindantwoord laat dat weg. De inhoud klopt met de uitspraak
   (§*Brongetrouw*). `ongelezen_samengevat` ziet het niet, en de toets op het rapport ook niet.
4. **Een teken uit een ander schrift.** In het blok over PHR:2025:435 staat "niet-mel**د**ende": een Arabische letter
   midden in een Nederlands woord. Dat komt van het model; geen toets ziet het.

## Brongetrouw

De samenvattingen in het eindantwoord zijn vergeleken met de volledige tekst via de open data van de Rechtspraak.

| Uitspraak | Lex zegt | Volgens de tekst | Oordeel |
|---|---|---|---|
| HR:2023:1371 | drie middelen verworpen; art. 36 dwingend; niet melden is een "vergaande onzorgvuldigheid"; geen discretionaire bevoegdheid; niet te toetsen aan art. 3:4 Awb of het ongeschreven evenredigheidsbeginsel; prejudiciële vragen | r.o. 3.3, 5.2.2 en 5.4; middel 1 faalt, middel 2 en 3 falen voor een deel, de vragen staan in onderdeel 6 | **klopt in hoofdlijnen**; "drie van vier" staat er niet zo. Niet gelezen (punt 3) |
| PHR:2024:936 | verjaring; uitstel aan de aansprakelijkgestelde verlengt de termijn niet; bij uitstel vervalt de grondslag | A-G Koopman "ontkennend"; de belastingschuldige is "niet (meer) in gebreke" | **klopt** |
| PHR:2025:435 (buiten de periode) | vijf lichtpuntjes, waaronder art. 6:11 Awb en Harderwijk; terugkomen van de gebonden bevoegdheid | 1.2–1.5, met dezelfde punten | **klopt** |
| GHARL:2025:1599 (buiten de periode) | na verwijzing het criterium van de andere afloop; geen oordeel over de melding | "andere afloop" 13 keer; "melding" komt niet voor; uitzendbureau, omzetbelasting 2008 | **klopt** |

## Per beurt

| Beurt | Wat | Account | Centrale agent | Kind |
|---|---|---|---|---|
| 0 | opdracht → kaart 1 (periode) | 258.668 | 0 modelrondes | deel 1: 7 aanroepen, 13 tools (11× `get_uitspraak`), 259k ruw / 88,2k gewogen warm, `vraag` (3 vragen), begint op 22k |
| 1 | antwoord 1 → kaart 2 (instanties) | 0 | 0 | — |
| 2 | antwoord 2 → kaart 3 (aspect) | 0 | 0 | — |
| 3 | antwoord 3 → hervatten, eindantwoord | 314.196 | 3 modelrondes, 0 tools, 88k ruw / 39,5k gewogen warm | deel 2: 3 aanroepen, 2 tools (`zoek_uitspraken`), 226k ruw / 107,3k gewogen warm, `klaar` met rapport, begint op 70k |

## Open punten

- De punten 1 en 2 van #1508 zijn niet echt getoetst: de uitspraken waar ze over gaan, kwamen niet in het antwoord.
- Waarom deel 2 na twee zoekaanroepen afrondt: uit de events is niet te zien of de code de laatste ronde aankondigde.
- Waarom de toetsen een samenvatting van HR:2023:1371 doorlaten terwijl dat stuk niet in `gelezen` staat. Mogelijk telt
  de beschrijving in PHR:2025:435 (wel gelezen) als steun. Dat is uit de events niet na te gaan.

## Bestanden

- `b120-delegatie-runs.jsonl`: D01 (één regel, `centrale_agent_vat.py`), met de status en de stukken van beide
  rapporten.
- `b120-kinderen.jsonl`: de twee delen van de kindrun (aanroepen, modellen, ruw, gewogen, beginnende context,
  sjabloon, tools), zonder tekst.
