# ADR-016 A6: eindmeting, run 2 (bundel 125, 15 nov 2026)

Soort: *meting* (ADR-016 §A6, de eindmeting), met akkoord van de gebruiker: één volledige run, plafond 5M tokens.

- **Code:** graph-qa op `e8f8d533` (bundel 125, #1537, met #1535 en #1536), `CENTRALE_AGENT=meten`, alle beurten met
  `agentvorm: centraal`. Model `claude-sonnet-4-6`, ook in de kinderen.
- **Nulpunt:** de nulmeting M0 op `808c908e` ([`../centrale-agent-2026-11-12-r0/ronde-0.md`](../centrale-agent-2026-11-12-r0/ronde-0.md)),
  drie runs. Daarnaast run 1 ([`../centrale-agent-2026-11-15-a6/a6.md`](../centrale-agent-2026-11-15-a6/a6.md)).
- **Hoe gemeten:** zoals M0 en run 1, met het meetscript van #1536 (`eval/centrale_agent_meting.mjs`): de agentset in
  volgorde, elke opdracht in een nieuw gesprek, de opdrachten met een werkgebied in het meetwerkgebied *Meting centrale
  agent*. De bewaking leest bij een leeg budget het bestand `BUDGET_OP` en de exitcode 3, en niet het getal 429 in de
  uitvoer. Daarna zouden P01–P03 (de delegatieset) en de kwaliteitsset volgen.
- **Bewaking:** vóór elke opdracht het verbruik van het account. Boven 4,4M start er niets meer. Een wachter stopt alles
  boven 4,95M; hij hoefde niet in te grijpen. Na F04 stond het account op 4,42M. F05 heb ik daarna los gedraaid, omdat
  hij in M0 hoogstens 168k kostte. Zo is de agentset compleet.
- **Vooraf:** de overzichtsvraag over de aanmaning gaf de zes artikelen van de Iw 1990: de graaf was gevuld (0 tokens).
- **Totaal:** 4.561.919 tokens op het account, alle voor de 30 opdrachten (budget gereset om 10:21 UTC).

## Wat er niet gemeten is

- **P01–P03 en de kwaliteitsset (K01–K22)** zijn niet gedraaid: het plafond van 5M liet na de agentset geen ruimte.
  Volgens M0 en ronde 2 kost de kwaliteitsset in één vorm ongeveer 2,6M (K08 alleen al ruim 750k). P01–P03 starten elk
  twee of drie subagents van hoogstens 300k.
- **De uitvoering van M01 en M06.** Beide eindigen nu op de bevestigingskaart `sa_start` (3 subagents, zie hieronder).
  De set klikt die kaart alleen als de opdracht `kaarten.start` heeft, en M01 en M06 hebben dat niet. Gemeten is dus
  het plan met de bevestiging, niet het werk van de subagents en ook niet het eindantwoord.

## Kort

| Meetpunt (§A6) | A6 run 2 | Run 1 | M0 (dezelfde 30, drie runs) | Drempel |
|---|---|---|---|---|
| **Tokens, totaal** | **4,56M** | 2,90M voor 26 (onvolledig) | 4,70M / 2,94M / 4,13M | binnen het plafond |
| **Gewone vragen niet duurder** (E01–E10) | mediaan ruw 45,5k; de vijf die de centrale agent zelf doet (E03, E06–E09): mediaan gewogen warm **34,4k** | 45,6k; 36k | 38,6k; 32,3k | ≤ M0: **net niet gehaald** |
| **Juiste delegatie** | **28 van 30** (29 als S02 telt, zie *S02*) | 19 van 26 | 16 van 26 | ≥ 27/30: **gehaald** |
| **Profielkeuze** | 8 van 8 (zes kinderen, twee plannen) | 2 van 2 | niet te meten | ≥ 13/15: te weinig delegaties om te toetsen |
| **Brongetrouw** | 110 van 112 citaten letterlijk, de andere 2 verklaard. Geen onjuiste bron of verzonnen citaat | 95 van 97 | 551 van 551 | **gehaald** |
| **Inhoud, enkelvoudig** | **10 van 10 goed** | 10 van 10 | 10 van 10 | niet slechter: **gehaald** |
| **Inhoud, samengesteld** (18 beoordeeld, M01 en M06 niet) | **12 goed, 4 deels, 2 fout** | 10 / 4 / 2 op 16 | run 1 op dezelfde 18: 8 / 3 / 7 | beter dan M0: **gehaald** |
| **Vragen naar boven** | **1 van 4** (V01) | 1 van 4 | 0 van 4 | 4/4: **niet gehaald** |
| **Grote opdracht in één keer** | M02–M05: plan, bevestiging, bundel "Wacht op jou"; M04 in fasen; M01 en M06 een plan met bevestiging | M02–M05 | M04 fout, M03 deels | **gehaald** |
| **Regressie (kwaliteitsset)** | niet gedraaid | niet gedraaid | | niet te toetsen |

Eén opdracht kostte meer dan 600k: **V03 met 690k**, zonder subagent, in 14 modelrondes met 17 keer `get_kamerstuk`.

## Per opdracht

`Account`: de delta op het account voor de hele opdracht, inclusief opzet en kinderen. M0: de tokens uit het
`meting`-event per run.

| Opdracht | Route | Subagent | Account | Run 1 | M0 (r1 / r2 / r3) | Sjabloon | Oordeel |
|---|---|---|---|---|---|---|---|
| E01 | algemeen (code) | – | 1k | 1k | 1 / 1 / 1k | – | goed |
| E02 | overzicht (code) | – | 0 | 0 | 0 / 0 / 0 | – | goed |
| E03 | centraal | – | 249k | 172k | 148 / 115 / 195k | gemist, 2× geweigerd (`genoemd_onbekend`) | goed |
| E04 | algemeen (code) | – | 0 | 0 | 0 / 0 / 0 | – | goed |
| E05 | duiding | – | 77k | 77k | 78 / 49 / 49k | extern | goed |
| E06 | afgewezen | – | 18k | 18k | 2 / 2 / 2k | – | goed |
| E07 | centraal | – | 73k | 74k | 46 / 34 / 46k | begrip | goed |
| E08 | centraal | – | 114k | 115k | 312 / 193 / 380k | duiding | goed |
| E09 | centraal | – | 155k | 204k | 124 / 93 / 186k | duiding | goed |
| E10 | annotaties_lezen | – | 10k | 10k | 32 / 43 / 32k | annotaties | goed |
| S01 | centraal | 1 (`algemeen`) | 352k (kind 246k) | 378k | 280 / 453 / 611k | extern | deels |
| S02 | duiding | **geen** | 27k | 27k | 26 / 26 / 26k | extern | goed |
| S03 | centraal | 1 (`duiding`) | 236k (kind 159k) | 113k | 83 / 65 / 66k | gemist, 1× geweigerd (`passage_niet_te_tonen`) | goed |
| S04 | centraal | 1 (`duiding`) | 257k (kind 179k) | 400k | 428 / 264 / 186k | gemist, 1× geweigerd (`passage_niet_te_tonen`) | goed |
| S05 | centraal | 1 (`algemeen`) | 354k (kind 302k) | 174k | 439 / 204 / 266k | extern | deels |
| M01 | subagent_plan | plan 3 (`duiding`) | 0 | 259k | 487 / 462 / 361k | – (kaart) | niet beoordeeld |
| M02 | regie | 3 (`retrieval`) | 0 | 0 | 0 / 0 / 0 | – | goed |
| M03 | regie | 3 (`retrieval`) | 0 | 0 | 3 / 3 / 3k | – | goed |
| M04 | regie, in fasen | 3 (`retrieval`) | 18k | 18k | 5 / 5 / 5k | – | goed |
| M05 | regie | 3 (`retrieval`) | 0 | 0 | 0 / 0 / 0 | – | goed |
| M06 | subagent_plan | plan 3 (`algemeen`) | 0 | 128k | 826 / 160 / 488k | – (kaart) | niet beoordeeld |
| V01 | centraal | – | 69k | 70k | 417 / 323 / 343k | – (vraag) | goed |
| V02 | bronselectie (code) | – | 18k | 0 | 0 / 0 / 0 | – | fout |
| V03 | centraal | **geen** | **690k** | 0 | 0 / 0 / 0 | extern | goed (inhoud) |
| V04 | centraal | – | 239k | 188k | 245 / 180 / 147k | duiding | deels |
| F01 | centraal | 1 (`algemeen`) | 495k (kind 250k) | ongeldig | 98 / 69 / 30k | extern | goed |
| F02 | centraal | 1 (`algemeen`) | 513k (kind 288k) | 479k | 99 / 5 / 139k | extern | deels |
| F03 | regie + centraal | 3 (`retrieval`) | 213k | – | 18 / 20 / 18k | gemist | fout |
| F04 | centraal | – | 245k | – | 338 / 6 / 426k | duiding | goed |
| F05 | centraal | – | 139k | – | 167 / 168 / 122k | duiding | goed |

Toelichting op de oordelen die afwijken van *goed*:

- **S01 (deels).** Eén kind met profiel `algemeen`, dat vier arresten las. De samenvatting van HR:2023:1371 klopt met
  wat bij bundel 123 tegen de tekst is nagelezen, en die van HR:2019:576 staat letterlijk in r.o. 3.1.11. Bij
  HR:2023:563 en :176 zegt het antwoord alleen dat ze gelezen zijn. De citaten bij HR:2023:1371 zijn weer kopregels.
- **S05 (deels).** Lex noemt één wijziging: Stb. 2009, 610 ("mededeling" werd "schriftelijk mededeling"), met de
  inwerkingtreding via Stb. 2010, 176. Dat klopt, en Lex zegt zelf dat eerdere wijzigingen langs de BWB niet te zien
  zijn. Maar de citaten onder *Uit de officiële bekendmakingen* gaan over uitstel van betaling bij een aanmerkelijk belang
  (artikel 25), niet over artikel 36. Ze staan wel letterlijk in Stb. 2009, 610.
- **V02 (fout).** Zoals in M0 en run 1: de route *bronselectie* in code vangt de vraag af. Lex gaat door bij deelvraag 3
  en zegt niet dat er geen deelvraag over verjaring is.
- **V03 (goed, wat de inhoud betreft).** Lex vat per deelvraag de memories van toelichting bij latere wijzigingen samen
  (kst-33402-3, kst-34786-3, kst-34554-3). Hij zegt dat de oorspronkelijke memorie van toelichting buiten de zoekdienst
  valt, en noemt alleen stukken die hij gelezen heeft. Er komt geen kaart voor de jurist, zoals de set vraagt. Maar de
  centrale agent doet alles zelf, waar de set een subagent verwacht. Dat kost 690k.
- **V04 (deels).** Zoals in run 1: Lex kiest zelf de wijziging die de BWB koppelt en zegt dat ook, maar vraagt niet welke
  wijziging bedoeld is. Inhoudelijk klopt het.
- **F02 (deels).** Na "artikel 30?" vraagt Lex welke wet (goed). Op het antwoord "De Invorderingswet 1990" zoekt hij tien
  uitspraken, en een kind leest ze. Het antwoord geeft drie thema's en alleen bij HR:2026:1297 inhoud, geen samenvatting
  per uitspraak.
- **F03 (fout).** De bundel met de bronnen per deelvraag gaat goed (0 tokens). Op "waarom stel je de eerste bepaling
  voor" zoekt de centrale agent opnieuw in de wet (157k), in plaats van de stand te lezen. Op "wat is er veranderd sinds
  je bundel" zegt Lex dat hij dat niet kan zien. `delegatie_stand` wordt niet aangeroepen.

## S02: de verwachting blijft staan

De ontwikkelsessie vindt dat de verwachting bij S02 (één subagent met `get_kamerstuk`) niet klopt, omdat de code het
genoemde Kamerstuk zelf leest. Ik heb besloten **de verwachting in de set niet aan te passen**. Wel tel ik S02 in deze
meting apart.

- **Wat S02 doet:** route `duiding`, één modelronde, drie keer `get_kamerstuk`, 27k. Het antwoord is goed en volledig:
  kst-33755-3 bespreekt alleen artikel 29 Iw 1990 (Artikel II, de ondergrens van vier procent) en het overgangsrecht
  (Artikel III), nagelezen tegen het stuk. Beide citaten zijn letterlijk.
- **Waarom de set blijft staan:** de set heeft vaste groepen van 10, 5, 6, 4 en 5 opdrachten
  (`tests/test_golden_centrale_agent.py`). S02 omzetten naar *enkelvoudig* maakt van de groep *één subagent* een groep
  van vier. Daarmee verandert de set waarmee M0, run 1 en deze run vergeleken worden, midden in de drie runs van A6.
- **Wat ik voorstel:** vervang S02 na A6 door een opdracht die echt een subagent nodig heeft, bijvoorbeeld een memorie
  van toelichting zonder nummer in de vraag. Tot dan tel ik de delegatie op twee manieren: **28 van 30** volgens de set
  en **29 van 30** als S02 goed telt. De drempel van 27 is in beide gevallen gehaald.

## Wat er gefikst is, nagelopen

1. **Delegatie bij S03–S05, M01 en M06: gehaald.**
   - S03 en S04 starten een kind met `duiding` en S05 met `algemeen`. Run 1 deed die drie zelf.
   - M01 en M06 stellen een plan van drie subagents voor, met de bevestigingskaart vóór de start. M01 verdeelt per
     regeling (drie keer `duiding`) en M06 per bron (drie keer `algemeen`). De kaart noemt het plafond (~2,0M samen)
     en zegt dat er nog geen schatting is.
   - P01–P03 zijn niet gemeten.
2. **Vragen naar boven bij V02 en V03: niet gehaald.**
   - V02 gaat nog steeds via de route *bronselectie*.
   - Bij V03 komt er geen subagent, dus ook geen vraag van een subagent aan de centrale agent.
   - V01 vraagt wel welke regeling er bedoeld is, en F02 ook.
3. **De controle per stuk: niet gehaald op PHR:2025:435.**
   - Ze draaide bij S01 (7,6k, geen tegenspraak) en bij F01 (11,0k).
   - Bij F01 meldt ze opnieuw `die de passages van dat stuk tegenspreekt` bij PHR:2025:435. De zin is: de A-G "bespreekt
     vijf mogelijke verzachtingen van de regeling, maar concludeert dat geen ervan in de concrete zaak tot een andere
     uitkomst leidt". Als tegenspraak wijst ze de slotsom aan (r.o. 1.5: "Ik meen dat belanghebbende niets opschiet met
     …"). Dat is geen tegenspraak. Hooguit is de samenvatting iets ruimer dan de slotsom, die het vijfde lichtpuntje
     niet noemt.
   - De samenvatting bleef wel staan in het antwoord, met de passages r.o. 1.1–1.5 erbij.
4. **`onbevestigd` bij S01 en F02: beter.**
   - S01 heeft er 3 (run 1: 6) en F02 0 (run 1: 6).
   - F01 heeft er wel 9. Een daarvan is vals op een andere manier: "1990 uitspraken gelezen (gelezen: 8)". Het jaartal
     uit "Invorderingswet 1990" wordt hier als aantal gelezen.
   - De kinderen hebben er samen 26 (S01 10, F01 6, S05 5, F02 4, S04 1).
5. **E09: de weigering is weg.** Het sjabloon `antwoord_duiding` ging in één keer. E09 kost 155k: minder dan in run 1
   (204k), maar meer dan M0 run 1 (124k). Het valt binnen de spreiding van M0 (93–186k). De inhoud is goed.

## Wat er misging

1. **V03 liep uit de hand: 690k in de centrale agent.** Er was geen subagent en geen plafond. Er waren 14 modelrondes,
   met 17 keer `get_kamerstuk` en 8 keer `zoek_kamerstukken`. Een kind was bij 300k gestopt.
2. **Geweigerde aanroepen na de subagent: 24 in vijf opdrachten.** S03 11 keer `get_artikel`, S04 9 keer
   `get_bepaling`, F01 2 keer, S01 en S05 elk 1 keer. Elke weigering is terecht, en kost 0 ms aan de tool. Maar de
   centrale agent wil na elk rapport zelf nalezen, en bij S03 en S04 kost dat een ronde.
3. **Sjabloonweigeringen:**
   - S03 en S04 kregen elk één weigering `passage_niet_te_tonen`. Daarna werd het antwoord tekst, zonder een enkel
     citaat. De inhoud klopt (art. 18 en 20 nagelezen), maar de jurist ziet geen wettekst.
   - E03 kreeg twee weigeringen `genoemd_onbekend`. Daardoor begint het antwoord met een zin over het antwoord: "Ik laat
     die verwijzing in het antwoord staan als verwijzing die in de wettekst voorkomt …". E03 kost 249k, meer dan elke
     run van M0.
4. **Vervolg op een bundel (F03) leest de stand niet.** Zie hierboven: geen `delegatie_stand`, wel opnieuw zoeken in de
   wet. Dat was ook in M0 fout.
5. **De kinderen zijn duur.** Zes kinderen kostten samen 1,42M, gemiddeld 237k. S05 kwam op 302k, net over de stopgrens.
   Ze beginnen op 15–22k context.
6. **Kleine dingen.**
   - Bij F04 staat als bron van een citaat de kale IRI van de slottekst van artikel 22, derde lid, in plaats van de
     vindplaats.
   - E05 gaat nog via `duiding`.

## Brongetrouw

Getoetst is elk blokcitaat, tegen deze bronnen:
- de volledige toestanden van de Iw 1990, de Awb, de AWR, de Awir en de Leidraad uit de BWB-repository;
- de stukken van de officiële bekendmakingen: Stb. 2009, 265, 2009, 610 en 2010, 176, en kst-33755-3, kst-33402-3,
  kst-34786-3 en kst-34554-3;
- de uitspraken bij de Rechtspraak.

Er zijn 112 citaten in 12 antwoorden, en 110 staan letterlijk in de bron. De andere twee:
- **V03:** een citaat uit kst-34786-3 waaruit Lex het voetnootcijfer en de tekst van voetnoot 26 heeft weggelaten. De
  tekst ervoor en erna is letterlijk.
- **V04:** de vorige tekst van artikel 36, tweede lid, uit de bron buiten de kennisgraaf, zoals in run 1. Die tekst is
  de huidige zonder het woord "schriftelijk".

Er is geen onjuiste bron en geen verzonnen citaat. Bij S03 (zonder citaten) zijn artikel 18 (stilstaan van een
motorrijtuig) en artikel 20 (lijfsdwang) nagelezen; de zin per artikel klopt.

## De derde run

**Run 3 is zinvol, maar pas na twee aanpassingen. Draai hem dan met P01–P03 en de kwaliteitsset erbij.**

- **De drempel voor delegatie is nu gehaald (28 van 30).** Run 3 moet laten zien dat dat geen toeval is. Twee dingen
  zijn hier niet gemeten: de uitvoering van M01 en M06, en P01–P03.
- **Aanpassing 1: geef M01 en M06 `kaarten.start` in de set.** Anders meet ook run 3 alleen het plan. Dat kost per
  opdracht naar schatting 0,5–0,9M (drie kinderen tot 300k).
- **Aanpassing 2: een plafond op de centrale agent bij werk zonder subagent (V03).** Of een fix waardoor V03 een
  subagent start. Anders kan één opdracht opnieuw 0,7M kosten.
- **De vragen naar boven halen deze versie niet (1 van 4).** Daar verandert een extra run niets aan. Dat vraagt een fix
  in de route *bronselectie* (V02) en bij V03.
- **Kosten van run 3 met alles erbij:** de agentset ongeveer 4,5M, M01 en M06 uitgevoerd 1–1,8M, P01–P03 ongeveer
  1,5–2,5M, en de kwaliteitsset ongeveer 2,6M. Samen 10–11M. Dat past niet in één week van 10M. Splits het daarom in
  twee delen: de agentset met M01, M06 en P01–P03, en de kwaliteitsset apart.

## Bestanden

- `a6r2-runs.jsonl`: de 30 opdrachten (`centrale_agent_vat.py`). Let op: `per_rol` dekt bij een opdracht met meer
  beurten alleen de laatste beurt; `delta_account` dekt de hele opdracht.
- `a6r2-kinderen.jsonl`: de zes kindruns (S01, S03, S04, S05, F01, F02) zonder tekst: ouder-run, agentvorm, profiel,
  aanroepen, modellen, ruw, gewogen, beginnende context, sjabloon, tools en `onbevestigd`. De twaalf kinderen van de
  regie (M02–M05, F03) kostten 0 tokens en staan er niet in.

De ruwe runs (antwoordtekst en events) staan niet in de repo.
