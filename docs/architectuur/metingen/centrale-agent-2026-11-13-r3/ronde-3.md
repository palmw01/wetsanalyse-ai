# De centrale agent, ronde 3: A2-2b tegen de nulmeting en ronde 2 – 13 november 2026

- **Soort:** *meting* (ADR-016 §A6, de ronde voor A2; de tweede van hoogstens vier).
- **Code:** master `171c38f4` (bundels 85 tot en met 87: A2-2b, de doorvraagroute, de vindplaatsfix),
  `CENTRALE_AGENT=meten`. De centrale agent heeft nu een kernset van elf tools (profiel `centraal`, voorvoegsel 12,9k
  tokens) en krijgt de andere pas na één aanroep van `meer_tools` (profiel `centraal_breed`).
- **Straat:** acceptatie. **Model:** `claude-sonnet-4-6`, in elke rol.
- **Drempel:** niet duurder (naar prijs gewogen, warm), niet slechter, brongetrouw 100 %.
- **Gegevens:** [`ronde-3-runs.jsonl`](ronde-3-runs.jsonl), [`ronde-3-sets.jsonl`](ronde-3-sets.jsonl) en
  [`ronde-3-toolgebruik.md`](ronde-3-toolgebruik.md). De vorige ronde: [`ronde-2.md`](../centrale-agent-2026-11-12-r2/ronde-2.md).

## Uitkomst

**De ronde is niet goed: de drempel voor de korte beurt is weer niet gehaald.** De bijstelling doet wat ze moest doen
(de overdracht valt op de goede plek, tools worden naast elkaar gevraagd, lange opdrachten zijn goedkoper), maar de
mediaan per opdracht daalt er niet door. Er is één nieuw punt: de vraag naar grondslagen loopt uit de hand.

| Drempel | Nulmeting → ronde 2 → nu | Gehaald |
|---|---|---|
| Mediaan per opdracht, gewogen warm (enkelvoudig; doel ≤ 8,6k) | 8,6k → 11,2k → 11,5k | **nee** |
| Geen opdracht meer dan 25 % duurder | E06 factor 4,4; E10 +70 % (geen centrale-agentbeurt) | **nee** |
| Som per run, gewogen warm (enkelvoudig) | 233,9k / 192,0k / 280,3k → 198,8k / 176,5k / 185,8k → 168,9k / 191,3k / 189,3k | ja |
| Som per run, ruw (enkelvoudig) | 742,1k / 529,4k / 890,6k → 681,8k / 593,4k / 657,7k → 476,2k / 531,6k / 552,2k | ja |
| Mediaan duur (enkelvoudig) | 14,3 s → 10,3 s → 11,4 s | ja |
| Inhoud enkelvoudig | 30/30 → 30/30 → 30/30 goed | ja |
| Vervolg (één run) | 5/15 goed → 3/5 → 2 goed en 1 deels van 5 | ja, op één run |
| Gesprekken (centraal) | 4/4 → 3/4 → 3/4 volgens de scorer, 4/4 inhoudelijk | ja, met een kanttekening |
| Brongetrouw 100 % | geen onjuiste bron, geen verzonnen citaat, geen run ongegrond | ja |
| De overdracht valt waar ze moet (nieuw) | B01–B03 in elke run, B04 en E01–E10 nooit | ja |
| Geen tool buiten het profiel (nieuw) | 0 in 47 beurten | ja |

## Hoe er gemeten is

Zoals ronde 2: het veld `agentvorm` op de beurt, drie cijfers per beurt (ruw, gewogen, gewogen warm), citaten tegen de
officiële tekst, de inhoud door de meetsessie gelezen tegen `goed` en `bron`. Nieuw in deze ronde:

- **De aanvulling** `golden_centrale_agent_breed.jsonl`: B01 (geldigheid), B02 (grondslagen), B03 (wie verwijst naar een
  bepaling), waar de overdracht moet vallen, en B04 (de opbouw van een regeling), waar ze niet hoort.
- **De modelronde op elke toolaanroep** en **de reden van een sjabloonweigering** staan nu op de events; de telling van
  tools per ronde is daarmee hard.

**Afwijkingen van §A6**, dezelfde als in ronde 2: de nulmeting is de basis voor de supervisor (de halvering); de
vervolgopdrachten en de gesprekken rusten op één run; vier van de achttien gesprekken; de inhoud is door de meetsessie
beoordeeld. De kwaliteitsset is in deze ronde niet gedraaid: de gebruiker heeft daar nog niet over beslist.

**De eerste beurten waren koud.** De dienst had een nacht stilgestaan. In de proef vooraf schreven beide vormen hun
uurvoorvoegsel (supervisor 11,5k tokens, centraal 12,3k); in run 1 daarna E05 (17,9k), E10 (8,8k) en B01 (17,1k, het
voorvoegsel van `centraal_breed`). De drempel staat op gewogen warm, waarin dat als gelezen telt.

## Enkelvoudig: E01–E10, drie runs

| Opdracht | Wie | Rondes, nulmeting | Rondes, nu | Ruw, nu | Gewogen warm, nulmeting | Gewogen warm, ronde 2 | Gewogen warm, nu | Mediaan nu tegen nulmeting |
|---|---|---|---|---|---|---|---|---|
| E01 | route in code | 1 / 1 / 1 | 1 / 1 / 1 | 908 / 936 / 928 | 1,6k / 1,6k / 1,5k | 1,5k / 1,7k / 1,6k | 1,5k / 1,6k / 1,6k | -2 % |
| E02 | route in code | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | – |
| E03 | centraal | 8 / 6 / 9 | 6 / 6 / 8 | 119,7k / 122,1k / 177,8k | 44,7k / 52,2k / 72,4k | 46,7k / 57,4k / 49,3k | 51,4k / 57,9k / 69,9k | +11 % |
| E04 | route in code | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | – |
| E05 | route in code | 3 / 2 / 2 | 2 / 2 / 3 | 48,8k / 48,7k / 75,6k | 26,5k / 17,0k / 18,5k | 25,4k / 17,3k / 19,7k | 18,8k / 17,0k / 21,8k | +2 % |
| E06 | centraal | 1 / 1 / 1 | 1 / 1 / 1 | 13,0k / 13,0k / 13,0k | 545 / 515 / 520 | 2,7k / 2,7k / 1,9k | 2,3k / 2,3k / 2,3k | +341 % |
| E07 | centraal | 5 / 4 / 5 | 4 / 4 / 4 | 55,1k / 55,2k / 55,2k | 9,7k / 7,6k / 9,6k | 10,5k / 11,8k / 10,6k | 9,5k / 10,7k / 10,8k | +12 % |
| E08 | centraal | 12 / 9 / 14 | 7 / 7 / 6 | 141,7k / 145,4k / 116,7k | 111,5k / 75,6k / 113,5k | 62,3k / 38,0k / 61,9k | 48,0k / 55,9k / 43,0k | -57 % |
| E09 | centraal | 8 / 6 / 10 | 4 / 7 / 5 | 66,1k / 115,4k / 82,0k | 32,3k / 27,9k / 57,2k | 42,4k / 35,3k / 28,5k | 25,0k / 33,7k / 27,5k | -15 % |
| E10 | route in code | 3 / 4 / 3 | 2 / 2 / 2 | 30,9k / 30,9k / 30,9k | 7,3k / 9,7k / 7,1k | 7,2k / 12,4k / 12,4k | 12,4k / 12,2k / 12,5k | +70 % |
| **som** | | 41 / 33 / 45 | 27 / 30 / 30 | 476,2k / 531,6k / 552,2k | 233,9k / 192,0k / 280,3k | 198,8k / 176,5k / 185,8k | 168,9k / 191,3k / 189,3k | |

- **De mediaan over de 30 opdracht-runs:** gewogen warm 8,6k → 11,2k → 11,5k; ruw
  38,6k → 40,2k → 39,8k.
- **Waarom de mediaan niet daalt.** Hij ligt tussen E07 en E10.
  - E07, één definitie: ruw 72,7k → 55,2k door het kleinere voorvoegsel, gewogen warm 10,6k → 10,7k. Tegen de
    supervisor (9,6k) is dat +12 %: vier modelaanroepen die elk 12,9k voorvoegsel lezen, tegen een supervisorstap van
    2,3k en een specialist met een kleinere toolset.
  - E10, annotaties lezen, is geen beurt van de centrale agent: de route in code kiest de specialist
    `annotaties_lezen`. Die kost 12,4k tegen 7,3k in de nulmeting, bij dezelfde ruwe tokens (30,9k). Het verschil is
    cache schrijven met de korte TTL (6,7k tokens tegen 2,0k). Dat hangt aan de cachestand van die specialist.
  - Zonder E10 is de mediaan 10,7k tegen 9,6k: ook dan boven het doel.
- **E06, de afwijzing:** gewogen warm 0,52k → 2,7k → 2,3k; ruw 2,3k → 17,5k → 13,0k. Nog een factor 4,4. De centrale
  agent leest zijn hele voorvoegsel om één vaste zin te zeggen; een kleiner voorvoegsel lost dat niet op.
- **De lange beurten winnen:** E08 −57 % en E09 −15 % tegen de nulmeting, in minder rondes.
- **E03** (+11 %) weigert in elke run twee keer het sjabloon en eindigt als tekst, met de controle op *onbepaald*.
- **Inhoud en brongetrouwheid:** 30 van 30 goed. Geen run ongegrond.

## De overdracht naar de brede toolset: B01–B04, drie runs

| Opdracht | Overdracht | Toolsets per beurt | Rondes | Ruw | Gewogen warm | Oordeel |
|---|---|---|---|---|---|---|
| B01 | ja | 2 / 2 / 2 | 7 / 6 / 9 | 157,9k / 125,3k / 225,4k | 40,5k / 31,2k / 53,2k | goed / deels / goed |
| B02 | ja | 2 / 2 / 2 | 18 / 10 / 20 | 521,7k / 218,8k / 533,8k | 121,2k / 52,2k / 97,2k | goed / deels / fout |
| B03 | ja | 2 / 2 / 2 | 6 / 6 / 5 | 115,1k / 114,4k / 92,6k | 25,8k / 25,5k / 21,7k | goed / goed / goed |
| B04 | nee | 1 / 1 / 1 | 4 / 6 / 4 | 55,9k / 89,8k / 55,9k | 11,5k / 20,3k / 11,7k | goed / goed / goed |

- **De overdracht valt waar ze moet.** Bij B01, B02 en B03 in alle drie de runs: de route wordt `centraal_breed`, het
  profiel ook, en de beurt gebruikt twee toolsets. Bij B04 (de opbouw, in de kernset) in geen enkele run, en bij
  E01–E10 ook nooit.
- **Geen tool buiten het profiel:** het model vroeg in geen van de 47 beurten om een tool die het niet had.
- **B02, de grondslagen, loopt uit de hand.** 219k tot 534k ruw, 10 tot 20 rondes. Na `grondslagen` (in één ronde negen
  keer naast elkaar) gaat hij over op `raw_sparql` en `graph_schema`, tot vijftien aanroepen. In run 3 eindigt de
  beurt zonder antwoord: "Ik kon deze vraag niet binnen de beurtlimiet afronden". Run 2 geeft de twee regelingen, maar
  leidt de artikelen af uit de delegatiebepalingen van de wet in plaats van uit de graaf.
- **B01, de geldigheid:** het antwoord is in twee van de drie runs goed (in werking sinds 1 januari 2023, dus niet op
  1 januari 2020, met de grens dat de graaf één toestand kent). Run 2 geeft dezelfde gegevens en zegt dat het niet te
  bevestigen is. `geldigheid` van één artikel komt in vier pagina's, die hij na elkaar leest.
- **B03 en B04:** goed in elke run.
- **De overdracht kost een ronde en een tweede voorvoegsel.** B03, de goedkoopste met overdracht, kost 93k–115k ruw en
  22k–26k gewogen warm voor één aanroep van `verwijst_naar_deze`.

## Vervolg: F01–F05, één run

| Opdracht | Oordeel, ronde 2 | Oordeel, nu | Ruw, nulmeting | Ruw, ronde 2 | Ruw, nu | Gewogen warm, nulmeting | Gewogen warm, ronde 2 | Gewogen warm, nu | Opzet ruw, nulmeting | Opzet ruw, ronde 2 | Opzet ruw, nu |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F01 | fout | fout | 97,7k / 69,4k / 29,7k | 183,5k | 63,7k | 24,5k / 19,0k / 15,6k | 42,2k | 15,5k | 547,6k / 422,2k / 368,5k | 714,6k | 441,1k |
| F02 | goed | deels | 99,3k / 5,2k / 139,4k | 280,0k | 54,2k | 23,8k / 5,7k / 39,1k | 109,3k | 19,3k | 418,4k / 294,5k / 308,0k | 597,7k | 381,4k |
| F03 | fout | fout | 17,8k / 19,9k / 17,5k | 17,9k | 13,4k | 5,3k / 4,3k / 4,4k | 3,6k | 3,3k | 121,1k / 110,8k / 134,5k | 165,7k | 75,2k |
| F04 | goed | goed | 337,8k / 5,6k / 426,0k | 229,7k | 88,7k | 80,2k / 6,5k / 102,5k | 62,7k | 39,5k | 235,0k / 437,5k / 210,3k | 255,8k | 117,6k |
| F05 | goed | goed | 167,2k / 167,7k / 121,8k | 162,4k | 130,3k | 61,1k / 53,5k / 47,2k | 51,7k | 44,0k | 1,1k / 1,1k / 1,1k | 1,1k | 1,1k |

- **Veel goedkoper dan ronde 2**, de opzet ook: S01 715k → 441k, V01 598k → 381k, E08 256k → 118k. Eén run per ronde;
  de richting is duidelijk, de grootte niet.
- **F01 blijft fout.** Het overzicht noemt als eerste HR 6 oktober 2023. Het vervolg leest HR 10 april 2026
  (ECLI:NL:HR:2026:586): de eerste uitspraak die hij in de opzet *las*, niet de eerste van zijn eigen overzicht. Hij
  stelt vast dat die niet over bewijslast gaat en biedt aan de andere te doorzoeken.
- **F02 is nu deels.** De opzet (V01, "artikel 30" zonder regeling) gokt nog steeds de Invorderingswet 1990, ondanks de
  nieuwe instructie om bij een artikel zonder regeling te vragen. Het vervolg "De Invorderingswet 1990." geeft de
  wettekst van artikel 30, niet de rechtspraak per uitspraak. In ronde 2 gaf het vervolg dat overzicht wel, voor 280k.
- **F03 ongewijzigd:** geen bundel en geen deelgesprekken in zijn context. Werk voor A4.
- **F04 en F05 goed**, voor minder dan in ronde 2 en dan bij de supervisor.

## De gesprekken en de controles op de supervisorweg

| Gesprek | Vorm | Geslaagd | Rondes | Ruw | Gewogen warm | Wat de scorer mist |
|---|---|---|---|---|---|---|
| a-artikel9-doorvragen | centraal | ja | 5 | 84,4k | 29,1k | – |
| a-definitie-vervolg | centraal | ja | 7 | 128,1k | 42,6k | – |
| f-bronnen-dan-wetsvraag | centraal | ja | 4 | 61,7k | 15,9k | – |
| v-artikel-zonder-wet | centraal | nee | 4 | 53,8k | 9,6k | geen van ['welke regeling', 'welke wet'] in het antwoord |
| v-artikel-zonder-wet | supervisor | nee | 9 | 97,9k | 20,2k | route verduidelijken verwacht, kreeg ['algemeen']; geen van ['welk artikel', 'bedoel je'] in het antwoord |

- **De doorvraagroute werkt nu bij de centrale agent.** In `v-artikel-zonder-wet` gaat beurt 3 ("En het tweede lid?")
  via de route in code: geen model, 0 tokens (ronde 2: 37k).
- **De scorer keurt beurt 1 af op de woorden.** Het antwoord is "Welk artikel 3 bedoel je? … Bedoel je artikel 3 van de
  Invorderingswet 1990, de Algemene wet inzake rijksbelastingen, de Algemene wet bestuursrecht, of een andere
  regeling?". De set verwacht letterlijk "welke regeling" of "welke wet". Inhoudelijk vraagt hij goed door; de vorm
  die de instructie nu voorschrijft, botst met de verwachting in de set.
- **De supervisorweg gaat in dit gesprek nu fout** (in ronde 2 goed). Beurt 2 eindigt met "Kun je aangeven welk
  artikel 3 je precies bedoelt? Bijvoorbeeld: …" en een lijst. Op beurt 3 antwoordt de supervisorweg met de wettekst
  van artikel 3:1, tweede lid, Awb: een gok, en de doorvraagroute greep niet in. Eén run. Of dit komt door de wijziging
  van de doorvraagroute of door de formulering van beurt 2, is hieruit niet te zeggen.
- **K04 en K10 zonder het veld** (de vindplaatsfix): de ongeldige vindplaats is weg. Beide falen nog op de
  bronnenlijst: bij K04 (welke soort regeling is de Leidraad) staat alleen de Awb als bron, bij K10 alleen de
  Invorderingswet 1990. De Leidraad zelf ontbreekt.

## Tools per ronde en het sjabloon

- **Tools naast elkaar:** 129 modelrondes met tools, waarvan 46 met meer dan één; 212 aanroepen, 1,6 per ronde. Voor
  ronde 2 is er geen harde telling om mee te vergelijken. Het aantal modelrondes per run van de enkelvoudige opdrachten
  ging van 32 / 28 / 30 naar 27 / 30 / 30.
- **Uitspraken lezen** gaat nog vaak één per ronde: in de opzet van F01 vijftien keer `get_uitspraak`, over tien
  uitspraken (een lange uitspraak komt in pagina's).
- **Het sjabloon:** 14 weigeringen in 10 van de 47 beurten van de agentset en de aanvulling, alle bij `antwoord_duiding`:
  `genoemd_onbekend` 7 keer (E03 in elke run en E09 één keer: de uitleg noemt een bepaling die niet is opgehaald),
  `passage_niet_te_tonen` 6 keer (E08, B01, F05) en `genoemd_gelezen` 1 keer (B02).

## Brongetrouwheid

208 citaten in 26 antwoorden, alle letterlijk in de officiële tekst: de vier regelingen uit de eerdere rondes, de
Uitvoeringsregeling Invorderingswet 1990 (de ankerteksten van B03) en de tekst van elk genoemd stuk. Geen run
ongegrond; *onbepaald* 15 keer in de 47 beurten van de agentset en de aanvulling, steeds na een antwoord in tekst.

## Verbruik

Uit de `meting`-events; gelijk aan de accountstand na afloop.

| Onderdeel | Ruw |
|---|---|
| De proef in beide vormen | 101.064 |
| E01–E10, drie runs | 1.560.030 |
| B01–B04, drie runs | 2.306.505 |
| F01–F05, één run (waarvan 1.016.429 opzet) | 1.366.812 |
| De vier gesprekken, centraal | 328.000 |
| De controles op de supervisorweg | 278.293 |
| **Samen** | **5.940.704** |

De schatting vooraf was 5–6M.

## Waar het nu op vastzit

- **De korte beurt.** De afwijzing en de enkele definitie blijven duurder dan bij de supervisor, omdat elke modelaanroep
  van de centrale agent zijn voorvoegsel leest. Een kleinere kernset hielp voor de ruwe tokens (−19 % per run), niet
  voor de mediaan gewogen warm. Dit is de tweede ronde waarin de drempel op hetzelfde punt strandt; bij een derde gaat
  het volgens §A6 met een voorstel terug naar de gebruiker.
- **De mediaan hangt aan twee opdrachten**, waarvan één (E10) niet van de centrale agent is. De som per run, de duur en
  de lange beurten zijn beter dan bij de supervisor. Of de mediaan over tien opdrachten de goede maat is voor *niet
  duurder*, is een vraag voor de gebruiker.
- **B02** laat zien wat de brede toolset kan kosten als de eerste tool het antwoord niet geeft.
- **V01** gokt nog steeds; **F01** kiest de eerste gelezen uitspraak in plaats van de eerste genoemde.
- **De supervisorweg** in `v-artikel-zonder-wet`: een mogelijke terugval, op één run.
