# ADR-016 A3–A5, hermeting na de fix en de delegatieregel (14 nov 2026)

Soort: *meting*, licht regime: één run, alleen de vorm `centraal`.

- **Code:** graph-qa op `b6a70016` (bundel 113, #1483), `CENTRALE_AGENT=meten`. Daarin zitten:
  - **#1480:** de delegatietools zijn niet meer strict. Dat is de fix van de 400 met een connector.
  - **#1481:** de delegatieregel is scherper.
- **Nulpunt:** de meting van #1482 op `23eb57bb`
  ([`../centrale-agent-2026-11-14-a3a5/a3a5.md`](../centrale-agent-2026-11-14-a3a5/a3a5.md)). Voor F05 is het nulpunt
  de meting van #1464 (`d2c1f585`, [`../centraal-afrondregel-2026-11-14/afrondregel.md`](../centraal-afrondregel-2026-11-14/afrondregel.md)).
- **Wat gemeten is,** na overleg met de hoofdsessie (de gebruiker wil de metingen licht houden):
  - **De fix:** S01, S05, D01 en P01. P02 viel af, en op de kaart van P01 is niet geklikt.
  - **De regel:** S03 en S04 moeten delegeren; E03, E09 en F05 moeten zelf blijven antwoorden. E06 en E07 vielen af.
- **Plafond:** 4M op het account. Na S01, S05, D01 en P01 stond het op 2,37M. Daar is de meting gestopt voor overleg
  (eerst stond het plafond op 3M), en daarna liep ze door tot 3,52M.

## Kort

| Wat | Drempel | Uitkomst |
|---|---|---|
| De fix: geen 400 meer | S01, S05, D01, P01 lopen | **Gehaald.** Geen enkele fout |
| A3 met connector (S01, S05) | delegeert | **Niet gehaald.** Beide lezen zelf |
| A4 (D01) | vraag in plaats van gok | **Niet gehaald.** Eén subagent, maar die kiest zelf "de meest recente" uitspraken |
| A5 (P01) | plan en kaart `sa_start` | **Gehaald.** Twee subagents, een plafond, de kaart. Uitvoeren niet gemeten |
| De regel: S03 en S04 delegeren | elk één subagent | **Gehaald.** Elk één subagent met profiel *duiding* (`profiel_past`) |
| De regel: E03, E09, F05 zelf | geen kindgesprek | **Gehaald.** 0 kindgesprekken |
| Rapport van de subagent | brongetrouw en gevuld | **Brongetrouw, maar 1 van 3 gevuld.** Bij S03 en D01 viel het rapport terug op tekst |
| Brongetrouw | geen onjuiste bron of verzonnen citaat | **Gehaald.** 127 citaten letterlijk, nagelezen in de officiële bronnen; één vals alarm |
| Kosten | niet duurder | **Gemengd.** Zie §*Kosten per delegatie* |

**Wat naar T1/A1 gaat** (gevraagd door de hoofdsessie):

1. **S01 en S05 lezen zelf in plaats van te delegeren.** S01 roept 18 keer `get_uitspraak` aan in 13 rondes, voor 659k ruw en
   151,9k gewogen warm. S05 kost 272k ruw. Beide antwoorden zijn *gegrond*.
2. **D01 kiest "de meest recente" in plaats van te vragen.** De subagent schrijft: "Omdat het dossier geen
   datumafbakening bevat, heb ik de meest recente en inhoudelijk relevante stukken gelezen." Er komt geen kaart
   `sa_vraag`.
3. **De kosten per delegatie** zijn hoog: 0,28M ruw bij S03 en S04, en 1,35M bij D01 (§*Kosten per delegatie*).
4. **Het rapport valt in twee van de drie delegaties terug op tekst** (S03: 2× `passage_niet_te_tonen`; D01:
   `extern.blokken` en `geen_passage`). Het kind van S03 eindigt daardoor als `niet_gelukt`.

## Per opdracht

### De fix en A3 met connector

| Opdracht | #1482 | Nu | Gewogen warm (ouder) | Ruw (boom) | Oordeel |
|---|---|---|---|---|---|
| S01 rechtspraak bij art. 36 | 400 | zelf: 18× `get_uitspraak`, 13 rondes, `antwoord_extern` | 151,9k | 659k | loopt; geen subagent; *gegrond* |
| S05 Staatsblad bij art. 36 | 400 | zelf: 4× `get_bekendmaking`, 9 rondes, `antwoord_duiding` | 61,7k | 272k | loopt; geen subagent; *gegrond* |
| D01 periode van het dossier | 400 | 1 subagent (*algemeen*), geen vraag | 150,4k | 1.354k | loopt; geen vraag; *gegrond* |
| P01 art. 22, rechtspraak + Kamerstukken | 400 | plan met 2 subagents (*algemeen*), kaart `sa_start` | 23,8k | 82k | loopt; plan en kaart goed |

- **P01:** de kaart noemt per subagent wat hij zoekt, en het plafond: "Ze stoppen bij ~1.928.783 tokens samen, een kwart
  van wat je deze week nog hebt". Een schatting geeft hij niet ("er zijn nog geen eerdere runs"). P01 staat niet in de
  meetbestanden: het meetscript is vóór de klik gestopt. De cijfers komen uit de run zelf.
- **D01:** het antwoord noemt alleen gelezen uitspraken, met hun ECLI. Het zegt ook dat er "ten minste 623 uitspraken"
  zijn die artikel 36 noemen.

### De regel

| Opdracht | #1482 | Nu | Gewogen warm (ouder) | Ruw (boom) | Oordeel |
|---|---|---|---|---|---|
| S03 hoofdstuk dwanginvordering | zelf, 3 rondes, sjabloon gemist, *onbepaald* | 1 subagent (*duiding*), rapport niet gevuld | 33,9k | 279k | delegeert; *gegrond*; lijst art. 11–20 |
| S04 Leidraad bij art. 22 | zelf, 11 rondes, *gegrond* | 1 subagent (*duiding*), rapport gevuld | 34,6k | 284k | delegeert; *onbepaald* |
| E03 | 84,3k, 10 rondes | zelf, 9 rondes | 77,7k | 234k | geen subagent; −8 % |
| E09 | 56,6k, 9 rondes | zelf, 10 rondes | 64,8k | 245k | geen subagent; +15 % |
| F05 (nulpunt #1464) | 40,7k, 6 rondes | zelf, 5 rondes | 41,0k | 114k | geen subagent; +1 % |

- **S03** geeft nu per artikel van hoofdstuk III één zin, van artikel 11 tot en met 20. Het kind eindigde als
  `niet_gelukt` (geen rapport), maar de toolresultaten van het kind staan in het bronspoor van de ouder. Zo kon de ouder
  het overzicht toch schrijven, en is het *gegrond*.
- **S04** noemt "alle 26 onderdelen" van de Leidraad bij artikel 22. Het zegt zelf dat 22.8.10–22.8.12 en de opsommingen
  in 22.9.2.1 en 22.9.2.2 niet op te vragen waren. Het oordeel van de controle is *onbepaald*.
- **E09 +15 %** valt binnen de regel (minder dan 25 %). Het blijft wel boven ronde 4 (25,1k).

## Kosten per delegatie

Het kind is een eigen run. Zijn cijfers komen uit zijn eigen `meting`-event (gewogen zoals in ADR-016 §A6), die van de
ouder uit de meting van de beurt.

| Opdracht | Ouder: ruw / gewogen warm | Kind: profiel, rondes, ruw / gewogen warm | Rapport van het kind | Boom: ruw / gewogen warm | Zelf gedaan in #1482 |
|---|---|---|---|---|---|
| S03 | 109k / 33,9k | *duiding*, 7, 170k / 85,9k | gemist (2× `passage_niet_te_tonen`) | 279k / 119,8k | 62k / 26,4k (onvolledig) |
| S04 | 81k / 34,6k | *duiding*, 6, 203k / 127,0k | gevuld (na 1× `passage_niet_te_tonen`) | 284k / 161,6k | 406k / 163,8k |
| D01 | 553k / 150,4k | *algemeen*, 13, 801k / 257,6k | gemist (`extern.blokken` 2×, `geen_passage`) | 1.354k / 408,0k | – (400) |

- **S04 delegeren is even duur als zelf doen** (161,6k tegen 163,8k gewogen warm), en ruw zelfs goedkoper (284k tegen 406k).
- **S03 is duurder dan in #1482** (119,8k tegen 26,4k), maar toen was het antwoord onvolledig en *onbepaald*.
- **D01 is de duurste beurt van de meting.** De ouder kost 553k ruw in 12 rondes en het kind 801k in 13. Het bronspoor
  van de ouder telt 15 keer `get_uitspraak`, met die van het kind erbij. Hoe dat lezen over ouder en kind verdeeld is,
  heb ik niet uitgesplitst. Het kind vult zijn rapport niet.
- **P01**, het plan zonder uitvoering, kost 82k ruw en 23,8k gewogen warm. Het eerste verzoek schreef het nieuwe
  voorvoegsel (23.008 tokens in de uurcache).

## Brongetrouw – gehaald

Elk blokcitaat is nagelezen in de officiële tekst:

- de Iw 1990, de Awb en de Leidraad, lokaal;
- de uitspraken van S01 en D01 bij de Rechtspraak (elf ECLI's, opgehaald met `data.rechtspraak.nl/uitspraken/content`);
- de Staatsbladen van S05 (stb-2009-610 en stb-2010-176).

| | Citaten | Letterlijk |
|---|---|---|
| S01 | 48 | 48 |
| D01 | 48 | 48 |
| S05 | 10 | 10 |
| E03, E09, F05 | 21 | 21 |
| S04 | 1 | vals alarm: de woorden "bodem" en "Stoffering" tussen aanhalingstekens, met lopende tekst ertussen |

Geen enkele beurt heeft `unsupported` of `niet_letterlijk`. *Onbepaald* zijn S04 en E03, E03 met één `onbevestigd`.

## Keuzes die ik maakte

- **Gestopt bij 2,37M.** Het plafond was eerst 3M, en de vier opdrachten van de fix kostten al 2,37M (D01 alleen
  1,35M). De hoofdsessie verlaagde daarna de opdracht en zette het plafond op 4M.
- **De kinderen apart gemeten.** De meetsamenvatting telt alleen de ouder. De kosten van een kind komen uit zijn eigen
  run (`lex_wacht` op het run-id uit het event `regie`). Voor D01 staat dat id niet in de events van de ouder; het kwam
  uit de lijst van runs met `ouder_run_id`.
- **De citaten van uitspraken en het Staatsblad zelf nagelezen** bij de officiële bron, in plaats van te vertrouwen op het
  oordeel van de controle.

## Open

1. **S01 en S05 lezen zelf** (T1/A1). Het zijn leesopdrachten bij één artikel met een connector, en de regel van #1481
   raakt ze niet, waar hij S03 en S04 wel raakt.
2. **D01 kiest zelf in plaats van te vragen** (T1/A1). De subagent kent `status: vraag`, maar gebruikt hem niet.
3. **De kosten per delegatie** (T1/A1): 0,28M ruw voor één leesopdracht in de graaf, 1,35M met een connector.
4. **Het rapport valt terug op tekst** in twee van de drie delegaties. Dezelfde weigeringen als bij het
   duidingssjabloon (`passage_niet_te_tonen`) houden ook het rapport tegen.
5. **P01 na de klik en P02** zijn niet gemeten: dat volgt na de kostenronde van T1/A1.
6. **E09** blijft duurder dan ronde 4 (64,8k tegen 25,1k).

## Verbruik

| | Ruw (account) |
|---|---|
| S01 | 658.842 |
| S05 | 272.479 |
| D01 (ouder en kind) | 1.353.546 |
| P01 (plan, geen klik) | 82.040 |
| S03 (ouder en kind) | 279.247 |
| S04 (ouder en kind) | 283.946 |
| E03 | 234.400 |
| E09 | 244.829 |
| F05 (met opzet) | 114.044 |
| **Totaal** | **3.523.373** |

Het account begon op 0 na de reset van 08:50 UTC. Het totaal is gelijk aan de som van de beurten, dus er liep tegelijk
niets anders.

Gegevens: [`her-runs.jsonl`](her-runs.jsonl) (7 regels) en [`her-delegatie-runs.jsonl`](her-delegatie-runs.jsonl) (D01).
De meetsamenvatting telt per regel de ouder. De cijfers van de kinderen staan alleen in dit verslag.
