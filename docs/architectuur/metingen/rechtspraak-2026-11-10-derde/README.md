# Rechtspraak op acceptatie, derde meting – 10 november 2026

Soort: *meting* · Code: master `cc207f4e` (bundel 31, #1183: #1181 + #1182) · Straat: acceptatie, Rechtspraak en
Kamerstukken aan in het register · Model: `claude-sonnet-4-6` (Foundry) · Uitvoering: de acceptatie-MCP, elke run in een
nieuw gesprek, één tegelijk · Akkoord: gegeven bij de eerste meting en herhaald voor deze meting.

Dit is dezelfde 5×3 als in [`rechtspraak-2026-11-10/`](../rechtspraak-2026-11-10/README.md) en
[`rechtspraak-2026-11-10-na/`](../rechtspraak-2026-11-10-na/README.md), nu na de oplossingen in #1182. De ruwe gegevens per
run staan in [`runs.jsonl`](runs.jsonl). Tokens = cache lezen + cache schrijven + uitvoer per run, uit het `meting`-event.
Volgens de verbruiksteller is het totaal **854.131** (de som per run is 854.087). Bij de nameting was het 824.677.

De hoofdsessie stelde twee vragen: komt de ECLI-vraag weer rond 47k uit, en komt er geen vrije samenvatting meer? Op
allebei is het antwoord **nee**.

## Uitkomst

| # | vraag | eerste (#1178) | nameting (#1181) | nu (#1182) |
|---|---|---|---|---|
| 1 | Wat staat er in ECLI:NL:HR:2022:50? | 3/3 sjabloon, 2 rondes, 47k | 2/3 sjabloon, 3–4 rondes, 72–97k | **2/3** sjabloon, 3 rondes, 72k ×3; run 2 een vrije samenvatting met 3 signalen |
| 2 | Welke uitspraken noemen artikel 36 Iw? | 1/3 met lijstblok, 93–178k | 3/3 `bron_lijst`, 0 tokens | 3/3 `bron_lijst`, 0 tokens, 0,3–4,4 s |
| 3 | De 10 nieuwste uitspraken van de HR in het belastingrecht | 3/3 `bron_lijst`, 0 tokens | 3/3, 0 tokens | 3/3, 0 tokens, 0,3–1,5 s |
| 4 | Wat is een uitspraak op bezwaar? | 3/3 zonder Rechtspraak, 134–178k | 3/3 zonder Rechtspraak, 153–206k | 3/3 zonder Rechtspraak, 10–13 rondes, 178–274k |
| 5 | ECLI zonder tekst | 3/3 eerlijk | 3/3 eerlijk, met een model | **3/3 zonder model**: 0 rondes, 0,3 s |

Wat #1182 deed:

- **De denkregel noemt de regeling**: "zoekt uitspraken bij artikel 36 van Invorderingswet 1990" (was het BWB-id).
- **De zoekvraagzin loopt**: "Gezocht op rechtsgebied belastingrecht en van de Hoge Raad. Nieuwste eerst."
- **Vraag 5 komt uit code**: een leemte ("De tekst van dit stuk staat niet bij de bron …") en het blok *Uit de
  rechtspraak* met het label "Gerechtshof Arnhem-Leeuwarden 14 juni 2023, ECLI…". Er is geen eigen duiding en geen
  systeemtaal meer, en het kost 0 tokens.
- **De bronnenlijst** in de sjabloonruns van vraag 1 noemt alleen wat het antwoord noemt.
- **De controle**: 0 niet-letterlijk in 15 runs. Onbevestigd: 3 signalen, allemaal in vraag 1, run 2.

## Bevindingen

1. **Vraag 1 kost nog steeds 72k, niet 47k.**
   - Op acceptatie heeft de eerste pagina van `get_uitspraak` nu 24 van de 28 rijen. Dat is één meer dan de 23 bij de
     nameting, want het veld `ro` is weg. Lokaal zijn het er 25.
   - In elke run haalt het model de laatste 4 rijen op (offset 24). Dat kost een ronde en een toolaanroep extra: 3 rondes
     en 2 toolaanroepen, ~72k tokens per run.
   - Eén veld minder is dus niet genoeg om de uitspraak op één pagina te krijgen. Twee wegen staan open:
     - de vaste kosten per rij omlaag: de kop (deel › sectietitel) staat op elke rij, ook als die gelijk is aan de rij
       ervoor;
     - een kleine rest (≤ 4 rijen) nog op de eerste pagina laten, als het budget dat toelaat.
2. **De vrije samenvatting komt nog voor (1 van 3).**
   - Run 2 schreef na de tweede pagina tekst in plaats van het sjabloon *extern*. Daarin staan 3 onbevestigde signalen:
     een eigen blokcitaat "Let op: …" en twee afgeronde bedragen ("2.4 euro", "633000 euro").
   - In die run noemt de bronnenlijst de HR-uitspraak uit 1996 en die van het EHRM, maar niet de gelezen
     ECLI:NL:HR:2022:50 zelf. Het antwoord noemt die niet bij id, en `alleen_gelezen_extern` houdt een externe bron alleen
     als het antwoord haar noemt.
   - De nameting had hetzelfde patroon (run 1). Het zit dus niet in één run. Het hangt samen met de tweede pagina: het
     model antwoordt na een `vervolg` vaker in tekst.
3. **Vraag 5: `leesbaar: true` op een stuk zonder tekst.** In de lijstregel staan zaaknummer en rechtsgebied niet, want
   het `stuk` van de leestool draagt ze niet. Dit is klein.
4. **Vraag 4 roept Rechtspraak in 3/3 niet aan.** De denkregel zegt wel "zoekt in de wetgeving en Kamerstukken en
   Rechtspraak": dat is de opsomming van wat aanstaat, geen aanroep. Deze vraag blijft de duurste (178–274k). Run 2 had
   13 rondes en 17 toolaanroepen voor een definitievraag zonder wettelijke definitie. Dat is gemeten, niet onderzocht, en
   het staat los van Rechtspraak.

## Wat deze meting niet zegt

Hetzelfde als in de eerste meting: dit is geen juridisch oordeel over de uitspraken. De begrenzer en de versiecontrole
van de cache zijn onder deze belasting niet zichtbaar. Bij vraag 2, 3 en 5 zijn de runs 2 en 3 alleen op route, duur
en aantal events gelezen; hun vorm is gelijk aan die van run 1.
