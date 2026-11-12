# Nulmeting context: waar de tokens van een beurt heen gaan (12 nov 2026)

Code: master `ecca4dd8` (bundel 57, met #1277: de opbouw per modelverzoek in het `meting`-event), acceptatie,
`claude-sonnet-4-6`. Eén gesprek van vier beurten over artikel 36 Invorderingswet 1990 (`147d148c3c124aaf`). Ruwe
gegevens: [`runs.jsonl`](runs.jsonl).

**Gewogen kosten.** Ik reken in invoer-equivalenten, met de prijsverhouding van Anthropic voor dit model:
- invoer 1×;
- cache lezen 0,1×;
- cache schrijven (5 minuten) 1,25×;
- uitvoer 5×.

Prijzen staan bewust niet in de repo. Alleen de verhouding telt.

| beurt | wat er gebeurde | gewogen | waarvan het koude schrijven in ronde 1 | schrijven in totaal |
|---|---|---|---|---|
| G1-1 | eerste vraag, specialist `definitie` (22 tools) | 71k | 29k (40%) | 70% |
| G1-2 | vervolgvraag binnen 2 min, specialist `duiding` (33 tools): andere `tools_hash` en `system_hash` | 65k | 45k (68%) | 72% |
| G1-3 | vervolgvraag binnen 2 min, weer `duiding`: tools en systeem uit de cache (24,9k gelezen), de historie opnieuw geschreven (18k) | 42k | 23k (54%) | 61% |
| G1-4 | vervolgvraag na ruim 6 minuten, zelfde hashes als G1-3: alles koud (42k geschreven) | 76k | 53k (69%) | 75% |

**Binnen een beurt werkt de cache zoals bedoeld.** Elke ronde leest het hele voorvoegsel en schrijft alleen het nieuwe
toolresultaat (1–6k).

**Het volume zit in het koude begin van elke beurt:** 40–70% van de gewogen kosten. De uitvoer (10–15%) en het
cache-lezen (10–20%) zijn kleiner. Er zijn drie oorzaken:

1. **Een andere specialist is een ander voorvoegsel.** De tools staan vooraan in de cache, en elke specialist
   heeft een eigen set: definitie 20, duiding 30, algemeen alle (+ connectortools en sjablonen). Zonder de
   connectortools, die per vraag aan of uit staan, delen de drie er maar 7, samen 8,3k tekens (≈ 2,4k tokens).
2. **De historie wordt elke beurt opnieuw geschreven.** Het variabele deel van de systeemprompt (plan,
   GESPREKSCONTEXT, BRONNEN IN DEZE BEURT, AFRONDEN_EXTERN; hier 7,6–8,7k tekens) staat vóór de berichten en
   verandert per beurt. Alles erna is dan nieuw voor de cache. Bovendien zit het venster na twee beurten al op
   `MAX_HISTORY_CHARS` (40,3–41,4k tekens). Vanaf dan knipt `_trim_messages` per beurt de voorkant af en
   schuift de krimp van oude toolresultaten op. Dan verandert het voorvoegsel ook zonder het variabele deel.
3. **Na 5 minuten is alles weg.** Een jurist die een antwoord leest en dan doorvraagt, zit al gauw boven de
   5 minuten (G1-4).

**Wat dit betekent voor het plan:**
- Server-compaction, context editing en `/compact` blijven afvallen: de historie is niet de dure post, het
  herschrijven ervan wel.
- **PR 2 (cachepunt op de gedeelde tools) valt af**: het gedeelde deel is ≈ 2,4k tokens, ≈ 2,7k gewogen per
  wissel. Dat is een extra parameter op de poort niet waard. Meer winst vraagt één toolset voor alle antwoordrollen,
  en dat is een ontwerpkeuze over de toolverdeling, geen cachekwestie.
- **PR 3 (1h-TTL op het stabiele voorvoegsel)** is gerechtvaardigd. Het schrijven kost dan 2× in plaats van
  1,25×, en het lezen daarna 0,1× in plaats van opnieuw 1,25×. Bij G1-4 zou dat ≈ 25k tokens tools + systeem
  scheelen, ≈ 28k gewogen (37%). Het geldt alleen voor tools en systeem; de berichten houden 5 minuten (de
  API eist dat een langere TTL vóór een kortere komt).
- **De historie over beurten heen cachen** is de derde winst, ≈ 15–18k geschreven per beurt, ≈ 20k gewogen.
  Het vraagt meer dan een cachepunt:
  - het variabele deel moet ná de historie (op dit model kan dat alleen als tekst in de beurt, niet als
    systeembericht);
  - het venster moet in stappen knippen in plaats van per beurt.

  Dat raakt hoe het model de instructies van de beurt leest. Het is daarom een eigen voorstel met een eigen
  meting, niet in PR 2/3.
- **PR 4 (`HERHAALD` als verwijzing)** blijft open: in deze vier beurten kwam geen herhaalde aanroep voor. Een
  lange beurt (K07-achtig) moet het nog laten zien.

**Grenzen van deze meting:**
- één gesprek en één onderwerp;
- de korte beurten van een vervolggesprek, geen lange beurt van 15+ rondes;
- een supervisoraanroep per beurt (2,2k, in de tabel buiten "eerste ronde");
- bundel 58 kwam tijdens de meting uit. Die raakte de modelverzoeken niet, maar een nieuwe revisie maakt de
  cache ook koud; G1-4 valt mogelijk daaronder. Bij de nameting herhaal ik de pauze van 6 minuten.

## Nameting: TTL van een uur (bundel 59, `d43d6954`)

Nieuw gesprek `522cabe397ad41dd` met twee duidingsvragen en daartussen ruim zes minuten, dezelfde hashes als in de
nulmeting (`tools_hash` `67fda44cabed`, `system_hash` `5cc1b4215950`).

| ronde 1 van de antwoordlus na een pauze van ruim 6 minuten | cache lezen | cache schrijven | gewogen |
|---|---|---|---|
| G1-4, TTL 5 minuten (nulmeting) | 0 | 42.055 | 52,6k |
| G2-2, TTL 1 uur | 24.916 | 11.303 | 16,6k |

- **Foundry accepteert de TTL** (geen terugval; de hit zelf is het bewijs). De supervisor las zijn prompt ook uit de
  cache (2.189 tokens).
- De winst zit in het voorvoegsel: tools + systeemprompt ≈ 24,9k tokens gelezen in plaats van geschreven, ≈ 28,7k
  gewogen per beurt na een pauze. Dat komt overeen met de schatting (28k). Wat nog wordt geschreven, is de
  historie met het variabele deel (oorzaak 2 hierboven). De historie was in G2-2 kleiner dan in G1-4, 22,6k tegen
  40,3k tekens; daarom vergelijk ik alleen het voorvoegsel.
- De totalen van de twee beurten zijn niet te vergelijken: G2-2 had 13 rondes, G1-4 er 4. Dat is spreiding van het
  model, niet van de cache.
- **Nieuw gezien in G2-2:** de lopende beurt werd groter dan `MAX_HISTORY_CHARS` (51k tekens in ronde 7). Toen viel
  de historie van het gesprek in één keer weg (23 → 11 berichten) en werd de lopende beurt opnieuw geschreven
  (23,2k). De lopende beurt zelf kromp niet; dat is de regel. Wel verliest het model in een lange beurt de
  eerdere beurten. Dat is bestaand gedrag, maar het weegt mee in het vervolgvoorstel over de historie.

## Bronwissel: de toolset per vraag (gesprek `fa4e52bf1dcb411c`)

De bronkeuze (ronde 6) geeft elke combinatie van specialist en connectors een eigen toolset. De tools staan
vooraan, dus elke combinatie is een eigen voorvoegsel. Een gesprek waarin de genoemde bron per beurt wisselt:

| beurt | bron in de vraag | `tools_hash` | ronde 1: lezen / schrijven |
|---|---|---|---|
| G3-1 | Kamerstukken | `c602d5763ef5` (26 tools) | 0 / 19,0k – nieuw |
| G3-2 | een uitspraak (ECLI) | `553624a51c9b` (26 tools) | 0 / 39,7k – nieuw, en de historie viel weg (lopende beurt 57k, oude venster) |
| G3-3 | Kamerstukken | `c602d5763ef5` | 17,7k / 24,3k – tools en systeem uit de cache van een uur |

**Wat een wissel kost:** het voorvoegsel van een nieuwe combinatie is ~19k tokens. Met de TTL van een uur kost het
schrijven 2× en het lezen daarna 0,1×, dus ≈ 36k gewogen, één keer per combinatie per uur, voor alle juristen
samen. Komt de combinatie binnen het uur terug, dan is ze warm (G3-3).

**Het alternatief, een vaste toollijst per gesprek** met de keuze als tekst in BRONNEN IN DEZE BEURT:
- de extra connectortools kosten ~2k tokens elk per ronde;
- bij drie extra connectors en ~7 rondes is dat ≈ 4k gewogen per beurt, in elke beurt;
- het omslagpunt ligt bij één wissel per ~9 beurten.

Hoe vaak een combinatie in een gesprek echt wisselt, is niet bekend: de vragensets van ronde 6 hebben één vraag per
gesprek. Bovendien beperkt de bronkeuze wat het model mag aanroepen. Een vaste lijst moet dat met tekst en een
weigering in `dispatch` doen, en een geweigerde aanroep kost een ronde.

**Besluit:** de toolset blijft per vraag. De logregel `model_aanroep` draagt nu `tools_hash`, dus de frequentie is
over een week productieverkeer te meten. Pas dan is het omslagpunt te beoordelen.

`defer_loading` met tool search valt af: dat loont boven ~10k tokens aan toolschema's (de connectortools zijn samen
~8k), en de zoekstap kost een extra ronde.

**Bevestigd in de oude code:** het venster sloeg midden in een beurt om (G3-2, G3-3). Dat lost #1305 op.

## Nameting ADR-015, deel 1 (bundel 64, `4fa61ce9`): de voorkant liep terug

Gesprek `aed3e61031564340`, dezelfde vragen als G1, zonder pauzes.

| beurt | wat er gebeurde | ronde 1: lezen / schrijven | historie |
|---|---|---|---|
| G4-1 | eerste vraag (`definitie`); de beurt groeide tot 83k tekens | 0 / 23,0k | 0 |
| G4-2 | andere specialist (`duiding`): nieuw voorvoegsel | 0 / 40,3k | 32,3k (beurt 1 gekrompen) |
| G4-3 | `duiding` | 25,0k / 10,9k | 21,8k: beurt 1 viel weg |
| G4-4 | `duiding` | 25,0k / 14,7k | 32,9k: beurt 1 kwam gekrompen terug |

Wat werkt:
- het variabele systeemdeel is 0, en de context van de beurt staat in de vraag (7,9–9,0k tekens);
- elke beurt is gegrond en vult haar sjabloon;
- binnen de beurt leest elke ronde het voorvoegsel.

Wat niet werkt: de historie van de vorige beurt kwam niet uit de cache. Alleen tools en systeemprompt werden gelezen
(25,0k). De oorzaak is een ontwerpfout in het eerste venster: het knippunt hing ook af van de laatste beurt, die heel
staat en de beurt erna krimpt. Daardoor liep de voorkant heen en weer (beurt 1 eruit, weer erin).

**Hersteld** (vervolg-PR): het knippunt hangt alleen af van het gekrompen oude deel, op een raster over de gekrompen
historie. Gesimuleerd met de echte cachepunten: ~16k tekens per beurt opnieuw geschreven, tegen 34–36k met het oude
venster, en de voorkant loopt nooit terug (`test_de_cache_leest_de_historie_via_de_cachepunten_van_de_vorige_beurt`).
Deel 2 van de nameting volgt na de uitrol daarvan.

## Nameting ADR-015, deel 2 (bundel 66, `82923318`): het vaste knippunt, en waarom het niet genoeg was

Gesprek `6f5743cc5864437a`, vijf duidingsvragen achter elkaar.

| beurt | ronde 1: lezen / schrijven | historie | wat er gebeurde |
|---|---|---|---|
| G5-1 | 25,0k / 2,9k | 0 | eerste beurt, tools en systeem al warm (gedeeld over gesprekken) |
| G5-2 | 25,0k / 10,5k | 19,4k | beurt 1 gekrompen, dus geschreven: verwacht |
| G5-3 | **32,7k / 6,8k** | 30,6k | de historie van beurt 1 uit de cache; alleen beurt 2 geschreven (G1-3: 24,9k / 18,0k) |
| G5-4 | 25,0k / 12,8k | 23,6k | het venster knipte: het gekrompen oude deel paste niet meer in een halve begroting |
| G5-5 | 25,0k / 16,1k | 33,5k | de voorkant bleef staan, maar de beurt waarmee het venster begon, krimpte nu |

- Alle beurten waren gegrond en vulden hun sjabloon.
- G5-3 laat zien dat het werkt: de historie van een eerdere beurt komt uit de cache.
- G5-4 en G5-5 laten de grens zien. **Een gekrompen beurt was nog 8–19k tekens**: de tussenrondes (zoeken en ophalen)
  bleven staan, alleen met afgekapte resultaten. Met een halve begroting van 20k knipte het venster dan bijna elke
  beurt, en elke knip maakt het hele voorvoegsel nieuw.

**Hersteld** (vervolg-PR): van een oude beurt blijven de vraag en het laatste antwoord over, met het resultaat dat
erbij hoort (`berichten._kern`). De tussenrondes vallen weg als hele paren, en het bronregister houdt ze voor de
controle. Gesimuleerd met de echte cachepunten: 13,6k tekens per beurt opnieuw geschreven. Dat is vrijwel het minimum
(de nieuwe beurt zelf, 13,0k), tegen 16k met #1316 en 34–36k met het oude venster. De nameting daarvan volgt na de
uitrol.

## Nameting ADR-015, deel 3 (bundel 67–68, `95382221`): de kern van oude beurten, en een indexfout

Gesprek `b661556bf1fa4542`, dezelfde vijf vragen als G5.

| beurt | ronde 1: lezen / schrijven | historie | wat er gebeurde |
|---|---|---|---|
| G6-1 | 25,0k / 2,9k | 0 | eerste beurt, tools en systeem warm |
| G6-2 | 25,0k / 6,4k | 10,1k (3 berichten) | beurt 1 als kern (G5-2: 19 berichten, 19,4k) |
| G6-3 | **28,5k / 9,1k** | 28,1k | de kern van beurt 1 uit de cache, alleen beurt 2 geschreven |
| G6-4 | **28,5k / 5,6k** | 18,4k | geen knip meer: alleen de kernen van beurt 2 en 3 geschreven |
| G6-5 | 25,0k / 3,3k | **0** | **fout: de hele historie viel weg** |

- G6-2 t/m G6-4 laten zien wat bedoeld was: oude beurten zijn klein, het venster knipt niet meer, en per beurt wordt
  alleen geschreven wat nieuw is.
- **G6-5 is een fout in #1318.** `_kern` maakt de berichtenlijst korter, maar het knippunt werkte nog met indexen in
  de oorspronkelijke lijst. Kwam het gekrompen oude deel boven de halve begroting (de kernen waren hier ~10k door het
  sjabloonantwoord), dan knipte het venster voorbij het eind. De test en de simulatie hadden kleine antwoorden en
  raakten dat niet.
- Alle beurten waren gegrond en vulden hun sjabloon (twee keer na één weigering van `duiding.vul`, zoals vaker bij
  dit sjabloon).

**Hersteld** (vervolg-PR):
- het venster werkt per beurt in plaats van per berichtindex (`_beurten`), dus er is maar één telling;
- het raster heeft een stap van een kwart begroting, zodat bij kernen van ~8–10k niet alles vóór de laatste beurt in
  één keer wegvalt;
- een regressietest met grote antwoorden faalt op #1318 (venster leeg in beurt 2) en slaagt nu.

Gesimuleerd met de echte cachepunten, per beurt opnieuw geschreven:
- met kleine antwoorden 13,6k (het minimum, de nieuwe beurt, is 13,0k);
- met antwoorden van 8k 32k tegen 45k met het oude venster (het minimum is 28k).

## Controlemeting (bundel 69, `f3344ba8`): de historie blijft

Gesprek `a709a04563c04477`, dezelfde vragen als G5 en G6.

| beurt | ronde 1: lezen / schrijven | historie | wat er gebeurde |
|---|---|---|---|
| G7-2 | 25,0k / 6,2k | 9,3k (3 berichten) | beurt 1 als kern |
| G7-3 | **28,3k / 8,5k** | 25,0k | de kern van beurt 1 uit de cache; de historie bleef in alle 13 rondes staan, ook toen de beurt 81k werd |
| G7-4 | 25,0k / 5,6k | 7,5k (5 berichten) | een geplande knip: beurt 1 viel weg, de kernen van beurt 2 en 3 bleven |
| G7-5 | **27,7k / 13,9k** | 34,8k (27 berichten) | de voorkant bleef staan; alleen beurt 4 geschreven |

**Uitkomst:**
- De historie valt in geen enkele beurt meer weg.
- Een knip gebeurt alleen op het raster en schuift alleen naar voren (G7-4).
- Wat per beurt nieuw geschreven wordt, is de vorige beurt; de rest komt uit de cache.
- Vergeleken met de nulmeting, na een vergelijkbare vervolgbeurt: G1-3 schreef 18,0k, G7-3 8,5k.
- De grens die overblijft is inherent aan een venster dat moet krimpen. De vorige beurt wordt één keer heel en één
  keer als kern geschreven, en een knip maakt het voorvoegsel nieuw.

**Gedrag:**
- Alle beurten waren gegrond.
- In G7-4 eindigde het antwoord in tekst na twee weigeringen van `antwoord_duiding` (`duiding.vul`). Eén weigering per
  beurt kwam in G4–G7 vaker voor (G6-2, G6-4, G7-2), ook al vóór #1318.
- Of de context van de beurt als tekst in de vraag de weigeringen vaker maakt, is met deze steekproef niet te zeggen:
  daarvoor is een vergelijking op een vragenset nodig. Dat is een vervolgpunt, geen bevinding.
