# ADR-016: hermeting na #1614 (16 nov 2026)

Soort: *meting*, licht regime: één run, de geraakte vorm. Het plafond was het restant van 1,2M na de afgebroken ronde
([`../centrale-agent-2026-11-16-hermeting-c/hermeting-c.md`](../centrale-agent-2026-11-16-hermeting-c/hermeting-c.md),
567k), dus ongeveer 630k. De gebruiker gaf akkoord met "Ja, meten".

## Opzet

- **Code:** graph-qa op `952b0622`. Daarin zit #1614 (zes overdrachten niet-strict: `centraal` met een connector gaat
  van 12 strict tools en 9.473 tekens naar 6 en 8.091), en ook #1611 (C) en PR A (`kern`). Het model is
  `claude-sonnet-4-6`.
- **Volgorde:** S01, P01, F02. Een opdracht startte alleen als haar schatting nog paste; de wachter stond op 620k.
- **Gedraaid:** S01.
- **Niet gedraaid:** P01 en F02. Na S01 stond het verschil op het account op 632k, en dat is het plafond.
- **Het verschil op het account is meer dan S01 alleen.** Het account is gedeeld, en tijdens S01 liep er een run die
  niet van deze meting was (`a279797d…`, met een kind).
  - S01 zelf kostte **432k**: het kind 284k ruw en de centrale agent 147k ruw, uit hun `meting`-events.
  - De rest, ongeveer 200k, is die andere run.
  - Door die run kwam de wachter boven de grens en stopte het meetscript. De beurt van S01 liep op de server gewoon door
    en eindigde `klaar`.
  - De regel in `runs.jsonl` is daarom nagebouwd uit de events van de run (`herbouwd`), en `delta_account` staat leeg.

## S01

**Opdracht:** "Zoek de rechtspraak bij artikel 36 van de Invorderingswet 1990 en vat per uitspraak samen wat de rechter
zegt over de melding van betalingsonmacht."

- **Het kind (`rechtspraak_lezen`)** gaf zijn rapport `klaar`, na 8 rondes en 284k.
- **Er kwam geen vraag en geen aanbod**, en de beurt ging door naar het antwoord. Dat is C.
- **De centrale agent** schreef het antwoord in `antwoord_extern`, na 5 rondes en 147k. Het sjabloon is twee keer
  gevuld; na de eerste keer volgde een correctieronde.
- **Het antwoord:**
  - Een kort antwoord over de stukken heen: wat er gelezen is, en wat niet (vóór 2018, de hoven en de rechtbanken).
  - Vier blokken `extern`, elk met een **kern**: HR:2023:1371, PHR:2025:435, HR:2019:284 en HR:2019:576.
  - Bij twee stukken zegt de kern dat ze maar deels gelezen zijn.
  - Eén aanwijzing klopte niet met wat er gelezen was. Die staat niet als citaat, en een `Leemte` zegt het.

## De citaten (B)

Per stuk: welke getoonde passages de kern dragen.

| Stuk | Getoond | Dragen de kern | Niet |
|---|---|---|---|
| HR:2023:1371 | 8 | r.o. 3.2, 3.3, 3.4 en 5.6.5 | r.o. 2.1 en 2.3 (feiten), 3.1 (inleiding), 5.4 (een ander middel) |
| PHR:2025:435 | 7 | r.o. 1.3 (de discretionaire bevoegdheid) en 1.4 (de lichtpuntjes) | de inhoudsindicatie (een vraag in trefwoorden), r.o. 1.1, 1.2 en 1.5 (de opbouw van de conclusie), 2.2 (feiten) |
| HR:2019:284 | 2 | de inhoudsindicatie (een zin die de kern geeft) en r.o. 3.4.1 | – |
| HR:2019:576 | 3 | de inhoudsindicatie, r.o. 3.1.11 (de tijdige melding uit de kern) en 3.5.1 (de maatstaf) | – |

- **11 van de 20 citaten dragen de kern.** In de slotmeting van A6 was dat bij S01 0 van 4; daar waren het alleen
  trefwoordregels.
- Bij de twee lange stukken staan nog feiten, inleiding en een ander middel tussen de dragende passages. De code vult
  `herkies` aan met alinea's die woorden met de kern delen, en een feitenalinea deelt er genoeg.
- Alle citaten zijn letterlijk: de code neemt ze uit de bron.

## De controle

Het oordeel is *onbepaald*, met vier punten onder `onbevestigd`. Alle vier zijn **vals**:
- **"Samenvatting van … zonder gelezen tekst"**, drie keer, bij HR:2011:BL0202, HR:2011:BR7038 en HR:2017:530. Die ids
  staan in de citaten van gelezen stukken: de Hoge Raad verwijst er zelf naar ("vgl. HR 31 maart 2017, …"). Het antwoord
  vat ze niet samen. `gelezen.ongelezen_samengevat` leest de citaten van de blokken `extern` mee als tekst van Lex.
- **"Volledig gelezen" bij stukken die deels gelezen zijn.** Dit komt uit een zin die juist zegt dat iets *niet* volledig
  gelezen is ("hoofdstukken 6 en 7 zijn niet volledig"). `gelezen.volledig_geclaimd` ziet de ontkenning niet.

## Drempels

| Drempel | Uitkomst |
|---|---|
| **C**: een kind dat `klaar` meldt, krijgt geen vraag, en het eindantwoord komt | **gehaald** |
| **A**: per stuk een kern | **gehaald**: 4 van de 4 blokken |
| **B**: minstens de helft van de citaten draagt de kern | **gehaald, net**: 11 van 20. Bij de lange stukken nog feiten en inleiding |
| **Brongetrouw**: geen onjuiste bron, geen verzonnen citaat | **gehaald**: alle citaten letterlijk, de kernen kloppen met de getoonde passages. De vier `onbevestigd` zijn vals (hierboven) |
| **Verbruik**: hoogstens de vorige meting plus 10 % | **niet gehaald**: 432k tegen 373k in run 3 (+16 %). De centrale agent kostte 147k, met een correctieronde |
| **P01 en F02** | **niet gemeten**: buiten het plafond |

## Voorstel (geen nieuwe ronde)

1. **De citaten van een blok `extern` zijn geen tekst van Lex voor de controle op ongelezen stukken.**
   `ongelezen_samengevat` en de andere duidingtoetsen lezen dan alleen de kern en de toelichting. Dat is generiek, voor
   elke bron naast de wet: een citaat noemt vaak andere stukken.
2. **`volledig_geclaimd` slaat een zin met een ontkenning over**, zoals `vraag_niet_in_stuk` dat al doet.
3. **De citaten bij lange stukken:** `herkies` vult alleen aan met alinea's die meer dragen dan feiten. Bijvoorbeeld een
   rechtsoverweging vóór de feiten, of alleen de alinea's die minstens twee stammen van één punt van de kern dragen.
   Dat vraagt een meting op de citaten (S01, F02).
4. **P01 en F02** met akkoord meten, als het verbruik het toelaat. Bij voorkeur als er geen ander werk op het gedeelde
   account loopt, zodat het verschil op het account klopt.

## Bestanden

- `runs.jsonl`: S01 (`centrale_agent_vat.py`, nagebouwd uit de events), zonder tekst.
- `kinderen.jsonl`: het kind van S01, zonder tekst.

De ruwe runs staan niet in de repo.
