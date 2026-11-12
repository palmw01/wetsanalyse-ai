# De centrale agent, ronde 2: A2-2 tegen de supervisor – 12 en 13 november 2026

- **Soort:** *meting* (ADR-016 §A6, de ronde voor A2; de eerste van hoogstens vier).
- **Code:** master `06556097` (bundel 82, met A2-2), `CENTRALE_AGENT=meten`. Beide vormen op dezelfde versie: zonder veld
  de supervisor met zijn specialisten, met `agentvorm: "centraal"` de centrale agent (profiel `centraal`, versie
  `99fb700096f8`, 27 tools, een voorvoegsel van 17,5k tokens).
- **Straat:** acceptatie. **Model:** `claude-sonnet-4-6`, in elke rol.
- **Drempel:** niet duurder (naar prijs gewogen, warm), niet slechter, brongetrouw 100 %.
- **Gegevens:** [`ronde-2-runs.jsonl`](ronde-2-runs.jsonl) (de agentset), [`ronde-2-sets.jsonl`](ronde-2-sets.jsonl) (de
  kwaliteitsset en de gesprekken) en [`ronde-2-toolgebruik.md`](ronde-2-toolgebruik.md).

## Uitkomst

**De ronde is niet goed: twee drempels zijn niet gehaald.** De centrale agent is in de som goedkoper en sneller, en
niet slechter in inhoud of brongetrouwheid. Maar een korte beurt is duurder geworden, en één route in code grijpt niet
meer in.

| Drempel | Stand | Gehaald |
|---|---|---|
| Niet duurder: mediaan per opdracht, gewogen warm (enkelvoudig) | 8,6k → 11,2k | **nee** (+30 %) |
| Niet duurder: geen opdracht meer dan 25 % duurder zonder verklaring | E06 factor 4 à 5; E07 +10 tot +25 % | **nee** (verklaard: het voorvoegsel) |
| Niet duurder: de som per run, gewogen warm (enkelvoudig) | 233,9k / 192,0k / 280,3k → 198,8k / 176,5k / 185,8k | ja |
| Niet trager: mediaan duur (enkelvoudig) | 14,3 s → 10,3 s | ja |
| Niet slechter: enkelvoudig | 30/30 goed → 30/30 goed | ja |
| Niet slechter: vervolg | 5/15 goed → 3/5 goed (één run) | ja, op één run |
| Niet slechter: de kwaliteitsset | 18/22 → 19/22 geslaagd | ja |
| Niet slechter: de gesprekken | 4/4 → 3/4 geslaagd | **nee** (de doorvraagroute) |
| Brongetrouw 100 % | geen onjuiste bron, geen verzonnen citaat, geen run ongegrond | ja |

Wat de bouwsessie hierop bijstelt (A2-2b, niet in deze meting): een kernset van tien tools met de andere dertien na een
overdracht, en de instructie om tools naast elkaar aan te roepen. Het voorvoegsel gaat daarmee van 17,5k naar 12,5k.

## Hoe er gemeten is

- **Beide vormen op één versie.** `eval/centrale_agent_meting.mjs` geeft het veld `agentvorm` mee op elke beurt. Welke
  vorm echt draaide, leest de samenvatter uit de run zelf (`vorm_gezien`: een agent met de rol `centraal` in
  `contextopbouw.agenten`, of een aanroep met de rol `supervisor`).
- **Drie cijfers per beurt:** ruw (alle tokens), gewogen (invoer × 1, uitvoer × 5, cache lezen × 0,1, cache schrijven
  × 1,25 bij vijf minuten en × 2 bij een uur; ADR-016 §A6) en gewogen warm (wat de beurt van het uurvoorvoegsel
  schreef, telt als gelezen). De drempel staat op gewogen warm; de ruwe tokens staan ernaast.
- **Beoordeling.** Elk citaat is gezocht in de officiële tekst (de toestanden uit de BWB-repository en de tekst van elk
  genoemd stuk). De inhoud van de agentset is door de meetsessie gelezen tegen `goed` en `bron` uit de set: van elk
  antwoord het begin, van de vervolgopdrachten het hele verloop. De kwaliteitsset en de gesprekken zijn gescoord met de
  scorers van de sets zelf (`eval/centrale_agent_sets.py`).

## Afwijkingen van §A6

1. **De halvering** (keuze van de gebruiker: "Kern met halvering"). De supervisor is voor de agentset niet opnieuw drie
   keer gemeten; de nulmeting op `808c908e` is de basis. Het bewijs dat dat mag, is de controle-run hieronder.
2. **De vervolgopdrachten rusten op één run.** F01 tot en met F05 zijn één keer met de centrale agent gedraaid. Er was
   een verschil met de nulmeting; de andere twee runs zijn in overleg niet gedraaid, omdat A2-2b juist verandert hoeveel
   de centrale agent leest. Over de kosten van het vervolg zegt deze ronde dus weinig; over goed of fout alleen dat het
   in deze ene run zo liep.
3. **De kwaliteitsset en de gesprekken één run per vorm**, in plaats van drie. Voor deze sets is er geen nulmeting, dus
   beide vormen zijn gemeten, per vraag om en om.
4. **Vier van de achttien gesprekken.** Veertien vallen weg:
   - zeven beginnen met "annoteer artikel 9 lid 1" (`a-na-annotatie-waarom`, `a-na-annotatie-volgend-lid`,
     `b-andere-rechtssubjecten`, `b-andere-zonder-woord-annotatie`, `c-waarom-deze-klasse`, `c-leg-markering-uit`,
     `r-tweede-artikel-zelfde-wet`): de annotatieketen valt buiten A2 en schrijft in de gedeelde lagen;
   - zeven F-gesprekken stellen deelvragen of begrippen voor, annoteren, of vragen een aangewezen object
     (`f-deelvragen-opstellen-en-dekking`, `f-deelvraag-splitsen-dan-uitleg`, `f-begrippen-voorstellen-en-meedenken`,
     `f-begrip-voorbeelden-dan-wettelijke-definitie`, `f-werkgebied-annoteren-dan-overzicht`,
     `f-deelvragen-annoteren-dan-deelvraag`, `f-praktijkvoorbeeld-dan-deelvragen`): ze zouden het meetwerkgebied
     wijzigen.
   Over scenario B en C heeft de gebruiker zich niet uitgesproken; ze blijven weg op advies van de hoofdsessie.
5. **De sets via de werkplek**, niet in-process. De route komt daardoor uit het `meting`-event; bij de centrale agent
   telt een verwachting die een specialist bij naam noemt niet als fout.
6. **De inhoud is beoordeeld door de meetsessie**, niet door de agent-jurist.

## De controle: de supervisor is gelijk aan de nulmeting

De tien enkelvoudige opdrachten zonder het veld, één keer. Alle handtekeningen per modelaanroep (rol, model,
`tools_hash`, `system_hash`, het aantal tools en de omvang van systeem en tools) komen voor in de nulmeting en ronde 1,
en geen handtekening van toen ontbreekt. Routes en specialisten zijn gelijk; E02, E04, E06 en E10 geven letterlijk
dezelfde tekst. Ruw 756,2k, gewogen 253,1k, gewogen warm 236,3k; de nulmeting
gaf 742k / 529k / 891k ruw. De vlag op `meten` verandert de bestaande weg dus niet.

## Enkelvoudig: E01–E10, drie runs

Per cel de drie runs. *Wie*: wie de beurt met het veld deed.

| Opdracht | Wie | Rondes, nulmeting | Rondes, centraal | Ruw, nulmeting | Ruw, centraal | Gewogen warm, nulmeting | Gewogen warm, centraal |
|---|---|---|---|---|---|---|---|
| E01 | route in code (algemeen) | 1 / 1 / 1 | 1 / 1 / 1 | 934 / 935 / 916 | 909 / 954 / 926 | 1,6k / 1,6k / 1,5k | 1,5k / 1,7k / 1,6k |
| E02 | route in code | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| E03 | centraal | 8 / 6 / 9 | 5 / 6 / 6 | 148,0k / 114,8k / 195,3k | 116,7k / 148,7k / 148,4k | 44,7k / 52,2k / 72,4k | 46,7k / 57,4k / 49,3k |
| E04 | route in code | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| E05 | route in code (duiding) | 3 / 2 / 2 | 3 / 2 / 3 | 77,8k / 48,7k / 49,0k | 77,4k / 48,8k / 77,2k | 26,5k / 17,0k / 18,5k | 25,4k / 17,3k / 19,7k |
| E06 | centraal | 1 / 1 / 1 | 1 / 1 / 1 | 2,3k / 2,3k / 2,3k | 17,5k / 17,5k / 17,5k | 545 / 515 / 520 | 2,7k / 2,7k / 1,9k |
| E07 | centraal | 5 / 4 / 5 | 4 / 4 / 4 | 45,6k / 34,1k / 45,5k | 72,6k / 72,7k / 72,7k | 9,7k / 7,6k / 9,6k | 10,5k / 11,8k / 10,6k |
| E08 | centraal | 12 / 9 / 14 | 8 / 6 / 8 | 312,0k / 192,8k / 380,0k | 201,4k / 140,4k / 204,1k | 111,5k / 75,6k / 113,5k | 62,3k / 38,0k / 61,9k |
| E09 | centraal | 8 / 6 / 10 | 7 / 6 / 5 | 124,0k / 92,6k / 185,9k | 163,8k / 133,6k / 106,0k | 32,3k / 27,9k / 57,2k | 42,4k / 35,3k / 28,5k |
| E10 | route in code (annotaties_lezen) | 3 / 4 / 3 | 3 / 2 / 2 | 31,6k / 43,2k / 31,6k | 31,6k / 30,9k / 30,9k | 7,3k / 9,7k / 7,1k | 7,2k / 12,4k / 12,4k |
| **som** | | 41 / 33 / 45 | 32 / 28 / 30 | 742,1k / 529,4k / 890,6k | 681,8k / 593,4k / 657,7k | 233,9k / 192,0k / 280,3k | 198,8k / 176,5k / 185,8k |

- **Mediaan over de 30 opdracht-runs:** ruw 38,6k → 40,2k; gewogen warm 8,6k →
  11,2k; duur 14,3 s → 10,3 s.
- **De som daalt, de mediaan stijgt.** Een lange uitlegvraag kost minder rondes en daardoor minder (E08 gewogen warm
  76k–114k → 38k–62k). Een korte beurt draagt nu het voorvoegsel van de centrale agent: 17,5k tokens bij elke
  modelaanroep.
  - E06, de afwijzing: de supervisor zei de vaste zin met 2,3k tokens; de centrale agent leest er 17,5k voor. Gewogen
    warm 0,5k → 1,9k–2,7k.
  - E07, één definitie: ruw 34k–46k → 72,7k, gewogen warm 7,6k–9,7k → 10,5k–11,8k, bij één ronde minder.
- **Geen supervisorstap meer.** Bij de vijf opdrachten van de centrale agent is er geen aanroep met de rol
  `supervisor` (bij de supervisor 2,3k ruw per beurt).
- **Twee routes in code gaan langs de centrale agent heen.** E05 (een genoemd Staatsblad) en E10 (annotaties lezen)
  eindigen ook met het veld bij een specialist (`duiding`, `annotaties_lezen`): de route in code kiest die vóór het
  model. Hun kosten zijn daardoor gelijk aan de nulmeting.
- **De koude cache.** In geen van de drie runs is het uurvoorvoegsel geschreven: gewogen is hier gelijk aan gewogen
  warm. In de proefbeurt vooraf (E07, de eerste beurt van de centrale agent op deze versie) wel: 16,7k tokens
  geschreven, gewogen 43,6k tegen 11,8k warm. Een koud begin kost dus eenmalig ongeveer 32k gewogen extra. Het
  voorvoegsel is voor alle juristen gelijk en blijft een uur warm: koud is de eerste beurt na een uur zonder verkeer op
  de straat en de eerste na een uitrol die het voorvoegsel wijzigt. De supervisorweg heeft hetzelfde, verdeeld over
  meer en kleinere voorvoegsels (in de kwaliteitsset één keer 16,1k).
- **Inhoud en brongetrouwheid.** 30 van 30 goed, zoals in de nulmeting. 163 citaten, alle letterlijk in de officiële
  tekst. Geen run ongegrond; E03 één keer *onbepaald* na een geweigerd sjabloon.

## Vervolg: F01–F05, één run

| Opdracht | Oordeel, nulmeting | Oordeel, centraal | Ruw, nulmeting | Ruw, centraal | Gewogen warm, nulmeting | Gewogen warm, centraal | Opzet ruw, nulmeting | Opzet ruw, centraal | Rondes, centraal |
|---|---|---|---|---|---|---|---|---|---|
| F01 |  | fout | 97,7k / 69,4k / 29,7k | 183,5k | 24,5k / 19,0k / 15,6k | 42,2k | 547,6k / 422,2k / 368,5k | 714,6k | 6 |
| F02 |  | goed | 99,3k / 5,2k / 139,4k | 280,0k | 23,8k / 5,7k / 39,1k | 109,3k | 418,4k / 294,5k / 308,0k | 597,7k | 7 |
| F03 |  | fout | 17,8k / 19,9k / 17,5k | 17,9k | 5,3k / 4,3k / 4,4k | 3,6k | 121,1k / 110,8k / 134,5k | 165,7k | 1 |
| F04 |  | goed | 337,8k / 5,6k / 426,0k | 229,7k | 80,2k / 6,5k / 102,5k | 62,7k | 235,0k / 437,5k / 210,3k | 255,8k | 9 |
| F05 |  | goed | 167,2k / 167,7k / 121,8k | 162,4k | 61,1k / 53,5k / 47,2k | 51,7k | 1,1k / 1,1k / 1,1k | 1,1k | 7 |

De oordelen van de nulmeting: F01 fout × 3, F02 fout × 3, F03 fout × 3, F04 goed / fout / goed, F05 goed × 3.

- **3 van 5 goed**, tegen 5 van 15. Geen misroute naar *werkgebied samenstellen* (in de nulmeting twee keer).
- **F01 blijft fout, in beide vormen.** Het overzicht van de opzet noemt als eerste HR 6 oktober 2023
  (ECLI:NL:HR:2023:1371) en als tweede de conclusie van de A-G (ECLI:NL:PHR:2025:435). Op "de eerste uitspraak uit je
  overzicht" leest de centrale agent vijf pagina's van nummer twee en antwoordt daarover. De volgorde van zijn eigen
  antwoord stuurt het vervolg niet.
- **F02 is nu goed, en duur.** "De Invorderingswet 1990." wordt begrepen als het antwoord op de vraag welke regeling,
  niet meer als een vraag naar de hele wet. Maar de opzet (V01) gokt ook met de centrale agent de regeling zonder te
  vragen, en het vervolg zoekt en leest alle uitspraken opnieuw (280k ruw, 109k gewogen warm).
- **F03 is werk voor A4.** "Ik heb geen bundel of eerdere deelgesprekken in mijn context." De bundel van de regie staat
  niet in zijn historie, en de stand bij de api leest hij nog niet.
- **F04 en F05 goed**, voor ongeveer dezelfde kosten als de supervisor.
- **De opzetbeurten zijn duurder met de centrale agent.** Dezelfde leesopdracht kost als opzet 715k (S01) en 598k
  (V01) ruw, tegen 368k–548k en 294k–418k bij de supervisor. Hij leest dertien tot vijftien uitspraken, vrijwel steeds
  één per ronde, en elke ronde leest de hele context opnieuw.

## De kwaliteitsset: 22 vragen, beide vormen één keer

| Vraag | Begin van de vraag | Geslaagd, supervisor | Geslaagd, centraal | Rondes (S / C) | Ruw (S / C) | Gewogen warm (S / C) |
|---|---|---|---|---|---|---|
| K01 | Wat zijn de invorderingstermijnen bij belastingen? | ja | ja | 8 / 11 | 185,5k / 316,4k | 53,3k / 76,9k |
| K02 | Welke regelingen zitten er in de kennisgraaf? | ja | ja | 3 / 2 | 36,9k / 35,7k | 7,2k / 6,4k |
| K03 | Binnen welke termijn is een naheffingsaanslag invorderbaar | nee (contains) | nee (contains) | 6 / 5 | 75,2k / 113,0k | 25,8k / 30,1k |
| K04 | Welke soort regeling is de Leidraad Invordering 2008? | nee (bronnen) | ja | 7 / 3 | 77,4k / 53,4k | 17,2k / 8,3k |
| K05 | Wie heeft de Invorderingswet 1990 ondertekend? | ja | ja | 4 / 3 | 54,6k / 53,8k | 9,8k / 9,1k |
| K06 | Wat is het weer vandaag? | ja | ja | 1 / 1 | 2,3k / 17,5k | 504 / 2,7k |
| K07 | Wat geldt er als iemand zijn belasting niet op tijd betaal | ja | ja | 6 / 12 | 109,9k / 288,5k | 28,8k / 64,9k |
| K08 | Kan de ontvanger een betalingsregeling weigeren? | ja | ja | 20 / 21 | 812,5k / 756,0k | 156,8k / 149,7k |
| K09 | Wat is een belastingschuldige en binnen welke termijn is e | nee (contains) | nee (contains) | 5 / 6 | 59,4k / 140,2k | 21,9k / 38,6k |
| K10 | Welke soort regeling is de Leidraad Invordering 2008, en w | nee (bronnen) | nee (bronnen) | 5 / 7 | 51,7k / 141,3k | 15,1k / 27,0k |
| K11 | alles over aansprakelijkheid van de bestuurder | ja | ja | 9 / 13 | 197,1k / 341,9k | 61,2k / 80,3k |
| K12 | wat is bekend over het milieu in de milieuwet? | ja | ja | 3 / 3 | 37,2k / 53,4k | 8,0k / 8,7k |
| K13 | Welke bepalingen verwijzen naar artikel 36 van de Invorder | ja | ja | 6 / 4 | 107,6k / 82,6k | 33,1k / 23,5k |
| K14 | Waar definieert de Invorderingswet 1990 het begrip belasti | ja | ja | 3 / 2 | 22,9k / 35,4k | 4,9k / 5,7k |
| K15 | Op welke wettelijke grondslag berust de Leidraad Invorderi | ja | ja | 11 / 6 | 209,1k / 116,1k | 64,5k / 23,2k |
| K16 | Welke hoofdstukken heeft de Invorderingswet 1990? | ja | ja | 4 / 3 | 55,8k / 55,1k | 12,1k / 11,3k |
| K17 | Sinds wanneer geldt de huidige tekst van artikel 36 van de | ja | ja | 12 / 4 | 272,6k / 91,4k | 62,5k / 25,9k |
| K18 | Welke hoofdstukken heeft de Invorderingswet 1990 en welke  | ja | ja | 4 / 3 | 56,4k / 56,1k | 14,6k / 14,3k |
| K19 | Welke artikelen gaan over invordering? | ja | ja | 0 / 0 | 0 / 0 | 0 / 0 |
| K20 | Welke bepalingen gaan over kwijtschelding? | ja | ja | 0 / 0 | 0 / 0 | 0 / 0 |
| K21 | Waar is de invordering geregeld in de Awb? | ja | ja | 0 / 0 | 0 / 0 | 0 / 0 |
| K22 | Wat staat er in artikel 22, derde lid, van de Invorderings | ja | ja | 1 / 1 | 937 / 945 | 1,6k / 1,7k |

- **Geslaagd:** supervisor 18 van 22, centraal 19 van 22.
  - K03 en K09 falen in beide vormen op de tekst "14 dagen": het antwoord zegt "veertien dagen", zoals de wet. Het
    antwoord is juist; de verwachting in de set is te letterlijk.
  - K10 faalt in beide op de bronnenlijst. K04 faalt alleen bij de supervisor: de bronnenlijst draagt daar een
    ongeldige vindplaats (`urn:bwb:{BWB-id`), ook bij K10. Dat lijkt een losse fout in de supervisorweg.
- **Kosten:** ruw 2,43M → 2,75M (+13 %), gewogen warm 599k → 608k (+1,6 %), modelrondes 118 → 110. Mediaan per vraag
  gewogen warm 14,9k → 12,8k, mediaan duur 19,8 s → 15,2 s.
- **Grote verschillen per vraag, in beide richtingen:** K17 62,5k → 25,9k en K15 64,5k → 23,2k; K07 28,8k → 64,9k en
  K01 53,3k → 76,9k. Eén run per vorm: per vraag is dit geen uitspraak, de som wel een aanwijzing.
- **Brongetrouw:** 94 citaten, alle letterlijk in de officiële tekst. Geen run ongegrond; *onbepaald* 13 keer bij de
  supervisor en 12 keer bij de centrale agent, over de kwaliteitsset en de gesprekken samen.

## De gesprekken: vier, beide vormen één keer

| Gesprek | Vorm | Geslaagd | Rondes | Ruw | Gewogen warm | Wat de scorer mist |
|---|---|---|---|---|---|---|
| a-artikel9-doorvragen | supervisor | ja | 9 | 97,5k | 39,4k | – |
| a-definitie-vervolg | supervisor | ja | 9 | 143,3k | 45,9k | – |
| f-bronnen-dan-wetsvraag | supervisor | ja | 4 | 54,3k | 15,4k | – |
| v-artikel-zonder-wet | supervisor | ja | 7 | 92,4k | 15,7k | – |
| a-artikel9-doorvragen | centraal | ja | 5 | 106,8k | 31,0k | – |
| a-definitie-vervolg | centraal | ja | 7 | 153,5k | 42,8k | – |
| f-bronnen-dan-wetsvraag | centraal | ja | 5 | 101,8k | 23,8k | – |
| v-artikel-zonder-wet | centraal | nee | 6 | 108,8k | 17,8k | route verduidelijken verwacht, kreeg ['centraal']; geen van ['welk artikel', 'bedoel je'] in het antwoord |

- **`v-artikel-zonder-wet`, beurt 3** ("En het tweede lid?", terwijl nog niet vaststaat welk artikel). De supervisor
  herhaalt de keuzevraag via de route in code: geen model, 0 tokens. De centrale agent vraagt ook door ("Kun je het
  volledige artikelnummer opgeven?") en gokt niet, maar doet dat met het model (37k ruw) en in andere woorden dan de
  set verwacht. De doorvraagroute in code grijpt bij de centrale agent dus niet in.
- De andere drie gesprekken slagen in beide vormen, voor vergelijkbare kosten (gewogen warm samen 116k → 115k).
- In `f-bronnen-dan-wetsvraag` haalt het antwoord een deelvraag van het werkgebied aan tussen aanhalingstekens; de
  citaatcontrole vindt die niet in de wet. Dat is tekst uit het dossier en geen citaat uit een bron.

## Het toolgebruik

Zie [`ronde-2-toolgebruik.md`](ronde-2-toolgebruik.md). In het kort:

- **In de agentset** (25 beurten) riep de centrale agent elf verschillende tools aan, alle uit wat de kernset van A2-2b
  wordt, plus de rechtspraaktools.
- **In de kwaliteitsset en de gesprekken** (141 aanroepen) vielen er 17 buiten die kernset: `get_regeling_info` 5,
  `geldigheid` 3, `verwijst_naar_deze` 3, `raw_sparql` 3, `grondslagen` 1, `semantic_search` 1 en
  `overzicht_onderwerp` 1. Die vragen (wie ondertekende, sinds wanneer geldt, wie verwijst naar, op welke grondslag)
  lopen na A2-2b dus over de overdracht naar de brede toolset. Het bijlagebestand telt alleen de agentset.
- Leeswerk gaat vaak één aanroep per ronde: `get_uitspraak` en `get_bepaling` elk 43 keer.
- Het sjabloon is 20 keer geweigerd in 12 van de 25 beurten van de centrale agent, vooral `antwoord_duiding`. Bij de
  supervisor in de nulmeting was dat 30 keer in 18 van de 45 duidingsbeurten: geen gevolg van de centrale agent.
- **De rondegrens is afgeleid en overschat het aantal rondes.** De stroom droeg in deze ronde geen rondenummer; vanaf
  de volgende ronde wel (`ronde` op `tool_execution`), en de reden van een weigering (`geweigerd_reden`).

## Verbruik

Uit de `meting`-events. Het accountbudget is tijdens de ronde gereset (23:08:15 UTC, door de hoofdsessie); één
accountdelta klopt daardoor niet.

| Onderdeel | Ruw |
|---|---|
| De controle-run (supervisor, E01–E10) en de proefbeurt | 828.902 |
| E01–E10, drie runs centraal | 1.933.022 |
| F01–F05, één run centraal (waarvan 1.734.842 opzet) | 2.608.229 |
| De kwaliteitsset, beide vormen | 5.173.890 |
| De vier gesprekken, beide vormen | 858.327 |
| **Samen** | **11.402.370** |

De schatting vooraf was ongeveer 8,7M voor stap 2; het werd 10,6M. Het verschil zit in de kwaliteitsset: 5,2M tegen
geschat 2,6M. Eén vraag (K08) kost in beide vormen ruim 750k, en de set is per vraag duurder dan de enkelvoudige
opdrachten.

## Wat de volgende ronde moet laten zien

- **De korte beurt.** E06 en E07 met het kleinere voorvoegsel van A2-2b; de mediaan gewogen warm van de tien
  enkelvoudige opdrachten moet terug naar ten hoogste 8,6k.
- **De overdracht naar de brede toolset.** De vier opdrachten van `golden_centrale_agent_breed.jsonl`: valt
  `meer_tools` waar het moet (geldigheid, grondslagen, wie verwijst naar een bepaling), en blijft het weg bij de opbouw
  van een regeling.
- **Samen ophalen.** Het aantal toolaanroepen per ronde, nu hard te tellen, en daarmee de kosten van de leesopdrachten
  (de opzet van F01 en F02).
- **De doorvraagroute** bij de centrale agent, en F01.
- **Eén run van F01–F05** met de bijgestelde centrale agent.
