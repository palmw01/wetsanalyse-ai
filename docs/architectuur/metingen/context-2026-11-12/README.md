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
   heeft een eigen set: definitie 20, duiding 30, algemeen alle (+ connectortools en sjablonen). De drie delen er 16,
   samen 35,5k tekens (≈ 10k tokens). Die worden nu bij elke wissel opnieuw geschreven.
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
- **PR 2 (cachepunt op de gedeelde tools)** is gerechtvaardigd: ≈ 10k tokens lezen in plaats van schrijven bij
  elke wissel van specialist, ≈ 11k gewogen.
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
