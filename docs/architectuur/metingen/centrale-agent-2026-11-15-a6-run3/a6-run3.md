# ADR-016 A6: eindmeting, run 3 deel 1 (bundel 126, 15 nov 2026)

Soort: *meting* (ADR-016 §A6, de eindmeting), met akkoord van de gebruiker. Deel 1 is de agentset, met P01–P03. Het
plafond is 5M tokens. De kwaliteitsset is deel 2 en volgt na een eigen akkoord.

- **Code:** graph-qa op `346a7e28` (bundel 126, #1540, met de fixes van #1539), `CENTRALE_AGENT=meten`. Alle beurten
  hebben `agentvorm: centraal`. Model `claude-sonnet-4-6`, ook in de kinderen.
- **Nulpunt:**
  - de nulmeting M0 op `808c908e` ([`../centrale-agent-2026-11-12-r0/ronde-0.md`](../centrale-agent-2026-11-12-r0/ronde-0.md));
  - run 2 ([`../centrale-agent-2026-11-15-a6-run2/a6-run2.md`](../centrale-agent-2026-11-15-a6-run2/a6-run2.md)).
  - P01–P03 hebben geen nulpunt: dit is de eerste keer dat ze worden uitgevoerd. In de meting van A3–A5 faalden ze op
    een 400, of eindigden ze op de kaart.
- **Wat er in de set veranderde:** M01 en M06 hebben nu `kaarten.start`. Daardoor klikt het meetscript op de
  bevestiging, en worden het werk van de subagents en het eindantwoord ook gemeten.
- **Hoe gemeten:** met het meetscript zoals in run 2 (`eval/centrale_agent_meting.mjs`). Elke opdracht draait in een
  nieuw gesprek. Een opdracht met een werkgebied draait in het meetwerkgebied *Meting centrale agent*. De volgorde:
  1. E01–S05;
  2. P01–P03, met `--set golden_centrale_agent_delegatie.jsonl`;
  3. M01–F05.

  P01–P03 staan naar voren gehaald omdat ze in run 2 buiten het plafond vielen.
- **Bewaking:**
  - Vóór elke opdracht leest de keten het verbruik van het account. Boven 4,4M start er niets meer.
  - Een wachter stopt alles boven 4,95M. Hij hoefde niet in te grijpen.
  - Er kwam geen `BUDGET_OP`.
  - Na M06 stond het account op 4,71M. V01 en V02 heb ik daarna nog los gedraaid: ze kostten in run 2 samen 87k.
- **Vooraf:** de overzichtsvraag over de aanmaning gaf de zes artikelen van de Iw 1990, voor 0 tokens. De graaf was dus
  gevuld.
- **Totaal:** 4.751.726 tokens op het account, voor 26 opdrachten. Het budget was gereset om 13:04 UTC.

## Wat er niet gemeten is

Niet gedraaid zijn **V03, V04 en F01–F05**: zeven opdrachten, omdat het plafond werd bereikt. In run 2 kostten ze samen
2,53M. Daardoor ontbreken drie fixes in deze meting:
- de fix voor V03 (één subagent `algemeen`, met `stukken_plafond`);
- de controle per stuk op PHR:2025:435 (F01);
- het jaartal dat niet meer als een aantal gelezen stukken telt (F01).

De controle per stuk is wel gemeten: hij draaide bij S01, M06 en P02 (zie hieronder).

## Kort

| Meetpunt (§A6) | Run 3 deel 1 (26) | Run 2 | M0 (dezelfde 30, drie runs) | Drempel |
|---|---|---|---|---|
| **Tokens, totaal** | **4,75M** voor 23 van de 30 plus P01–P03. Daarvan gaan 1,32M naar M01/M06 uitgevoerd en 1,79M naar P01–P03 | 4,56M voor 30 | 4,70M / 2,94M / 4,13M | binnen het plafond |
| **Gewone vragen niet duurder** (E01–E10) | mediaan ruw **33k**. De vijf opdrachten die de centrale agent zelf doet (E03, E06–E09): mediaan gewogen warm **30k** | 45,5k; 34,4k | 38,6k; 32,3k | ≤ M0: **gehaald** |
| **Juiste delegatie** | **22 van 23** in de agentset (alleen S02 niet, zie run 2). P01–P03: 3 van 3 | 28 van 30 | 16 van 26 | ≥ 27/30: op de 23 gemeten opdrachten **op koers** |
| **Profielkeuze** | **17 van 17** kinderen | 8 van 8 | niet te meten | ≥ 13/15: **gehaald** |
| **Brongetrouw** | **270 van 270** citaten letterlijk, in 13 antwoorden. Geen onjuiste bron en geen verzonnen citaat | 110 van 112 | 551 van 551 | **gehaald** |
| **Inhoud, enkelvoudig** | **10 van 10 goed** | 10 van 10 | 10 van 10 | niet slechter: **gehaald** |
| **Inhoud, samengesteld** (16 beoordeeld) | **13 goed, 2 deels, 1 fout** | op dezelfde 13 van de 30: 7 / 2 / 1, met M01 en M06 niet beoordeeld | | beter dan M0: **gehaald** |
| **Vragen naar boven** | **2 van 2 gemeten** (V01, V02). V03 en V04 zijn niet gedraaid | 1 van 4 | 0 van 4 | 4/4: V02 gehaald, de rest niet te toetsen |
| **Grote opdracht in één keer** | M02–M05 zoals run 2. **M01, M06 en P01–P03 uitgevoerd**: plan, kaart, 2–3 kinderen, één antwoord | M01/M06 alleen het plan | M04 fout, M03 deels | **gehaald** |

Geen opdracht kostte meer dan 900k. De duurste was **M06, met 827k**: drie kinderen van 187k tot 280k.

## Per opdracht

`Account` is de delta op het account voor de hele opdracht, met de opzet en de kinderen erbij. De kolommen *Run 2* en
*M0* komen uit het verslag van run 2.

| Opdracht | Route | Subagent | Account | Run 2 | M0 (r1 / r2 / r3) | Sjabloon | Oordeel |
|---|---|---|---|---|---|---|---|
| E01 | algemeen (code) | – | 1k | 1k | 1 / 1 / 1k | – | goed |
| E02 | overzicht (code) | – | 0 | 0 | 0 / 0 / 0 | – | goed |
| E03 | centraal | – | **149k** | 249k | 148 / 115 / 195k | gemist, 2× geweigerd (`genoemd_in_tekst`) | goed |
| E04 | algemeen (code) | – | 0 | 0 | 0 / 0 / 0 | – | goed |
| E05 | duiding | – | 50k | 77k | 78 / 49 / 49k | extern | goed |
| E06 | afgewezen | – | 18k | 18k | 2 / 2 / 2k | – | goed |
| E07 | centraal | – | 73k | 73k | 46 / 34 / 46k | begrip | goed |
| E08 | centraal | – | 139k | 114k | 312 / 193 / 380k | duiding | goed |
| E09 | centraal | – | **127k** | 155k | 124 / 93 / 186k | duiding | goed |
| E10 | annotaties_lezen | – | 10k | 10k | 32 / 43 / 32k | annotaties | goed |
| S01 | centraal | 1 (`algemeen`) | 373k (kind 244k) | 352k | 280 / 453 / 611k | gemist, 1× geweigerd | deels |
| S02 | duiding | **geen** | 27k | 27k | 26 / 26 / 26k | extern | goed |
| S03 | centraal | 1 (`duiding`) | 198k (kind 118k) | 236k | 83 / 65 / 66k | gemist, 2× geweigerd (`passage_niet_te_tonen`) | goed |
| S04 | centraal | 1 (`duiding`) | 176k (kind 175k) | 257k | 428 / 264 / 186k | – | **fout** |
| S05 | centraal | 1 (`algemeen`) | 227k (kind 151k) | 354k | 439 / 204 / 266k | extern | goed |
| P01 | subagent_plan + centraal | 2 (`algemeen`) | 561k (kinderen 493k) | – | – | extern | deels |
| P02 | subagent_plan + centraal | 2 (`algemeen`) | 651k (kinderen 564k) | – | – | extern | goed |
| P03 | subagent_plan + centraal | 3 (`duiding`) | 584k (kinderen 513k) | – | – | gemist | goed |
| M01 | subagent_plan + centraal | 3 (`duiding`) | **498k** (kinderen 462k) | 0 (alleen plan) | 487 / 462 / 361k | gemist | goed |
| M02 | regie | 3 (`retrieval`) | 0 | 0 | 0 / 0 / 0 | – | goed |
| M03 | regie | 3 (`retrieval`) | 0 | 0 | 3 / 3 / 3k | – | goed |
| M04 | regie, in fasen | 3 (`retrieval`) | 18k | 18k | 5 / 5 / 5k | – | goed |
| M05 | regie | 3 (`retrieval`) | 0 | 0 | 0 / 0 / 0 | – | goed |
| M06 | subagent_plan + centraal | 3 (`algemeen`) | **827k** (kinderen 727k) | 0 (alleen plan) | 826 / 160 / 488k | extern | goed |
| V01 | centraal | – | 46k | 69k | 417 / 323 / 343k | – (vraag) | goed |
| V02 | verduidelijken (code) | – | 0 | 18k | 0 / 0 / 0 | – (vraag) | **goed** |

Toelichting op de oordelen en de opvallende punten:

- **S01 (deels).** Eén kind `algemeen` las vier arresten van de Hoge Raad. HR:2023:1371 is juist samengevat, zoals bij
  bundel 123 tegen de tekst is nagelezen. HR:2023:563, :176 en HR:2020:1502 hebben nu wel een samenvatting, waar run 2
  alleen "gelezen" zei. Maar het sjabloon werd geweigerd (`overig`), en het antwoord heeft **geen enkel citaat**. De set
  vraagt per uitspraak een letterlijke passage over de melding.
- **S03 (goed).** Alle artikelen 11–20 met 18a, elk met één zin. Na het rapport staan er nu **19 citaten** onder het
  antwoord; run 2 had er geen. Ze zijn alle letterlijk.
- **S04 (fout, en een regressie).** Het kind las alle onderdelen 22.1–22.9 van de Leidraad en leverde een rapport
  (`uitkomst: klaar`, sjabloon `rapport`). Het rapport is inhoudelijk goed (nagelezen: 22.1 en 22.5). Toch zegt de
  centrale agent, met 0 modelrondes: "De subagent rondde de opdracht niet af met een rapport. Daarom vat ik de stukken
  niet samen". Daarna volgen 26 kale IRI's. De jurist krijgt niets van het werk. Waarschijnlijk telt de code een
  rapport dat eigen onderdelen "niet meer kon lezen" als onaf. Dat heb ik niet in de code nagegaan.
- **S05 (goed).** Lex noemt Stb. 2009, 610 en Stb. 2010, 176, en die kloppen. De citaten komen nu uit Stb. 2010, 176 en
  gaan over artikel 36. Run 2 citeerde hier passages over artikel 25. Een minpunt: de aanhef ("Wij Beatrix …",
  "Hebben goedgevonden en verstaan:") staat er ook als citaat bij.
- **M01 en P03 (goed).** Dezelfde vergelijkingsvraag, één keer met connectors en één keer zonder. In beide gevallen
  lezen drie kinderen `duiding` elk één regeling. Het antwoord geeft per onderwerp (aanmaning, dwangbevel, betekening,
  tenuitvoerlegging, verzet) de Awb, de Iw en de Leidraad, met 52 en 65 letterlijke citaten. Nagelezen:
  - de bedragen van artikel 4:113 Awb (€ 9 / € 20);
  - artikel 4:118 Awb;
  - de afwijkingen in artikel 12, tweede lid, 13, 14 en 18a Iw.

  Ze kosten 498k en 584k. Dat is hetzelfde als M0 (361–487k), dat het werk zelf deed.
- **M06 (goed).** De drie bronnen zijn elk in een eigen deel samengevat:
  - Kamerstukken: dossiers 25035 en 30322;
  - het Staatsblad;
  - vier uitspraken.

  De 43 citaten staan letterlijk in de bron. Het kost 827k, net als de duurste run van M0 (826k).
- **P01 (deels).** Twee kinderen. Het rapport over de rechtspraak is goed, met vier arresten inhoudelijk
  (HR:2014:896, HR:2013:1910, HR:2012:BX7851 en HR:2018:2257). Het eindantwoord maakt daar één alinea van, zonder
  samenvatting per uitspraak. De twee citaten zijn trefwoorden en inhoudsindicaties van conclusies. Het deel
  Kamerstukken zegt terecht dat er geen toelichting op artikel 22 is gevonden. Toch vraagt de set "per bron apart
  samenvatten", en dat gebeurt niet.
- **P02 (goed).** Per bron:
  - drie memories van toelichting, met wat ze over artikel 26 zeggen;
  - vijf uitspraken, met als kern HR:2016:2735: de burgerlijke rechter is bevoegd bij kwijtschelding, niet de
    belastingrechter.

  Nagelezen tegen kst-26728-3 en kst-36151-3. Een minpunt: bij de uitspraken staan vooral procedurezinnen als citaat
  ("De Staatssecretaris van Financiën heeft een verweerschrift ingediend.").
- **V02 (goed).** "Dit werkgebied heeft geen deelvraag over verjaring." Lex noemt de drie deelvragen en vraagt of hij
  er een moet toevoegen, of bij welke van de drie hij moet zoeken. Dat gaat in code, voor 0 tokens. De fix werkt.
- **E03 (goed).** "Artikel 239 van Boek 3 van het Burgerlijk Wetboek" wordt nu gevonden, en E03 kost 149k in plaats van
  249k. Het sjabloon wordt nog twee keer geweigerd (`genoemd_in_tekst`). Daarna is het antwoord tekst, zonder de zin
  over het antwoord die run 2 had.

## Wat er gefikst is, nagelopen

| Fix (#1539) | Uitkomst |
|---|---|
| V02: vraag aan de jurist bij een deelvraag die er niet is | **Gehaald**, zie boven. |
| V03: één subagent `algemeen`, met `stukken_plafond` | **Niet gemeten** (plafond). |
| F01/PHR:2025:435: de controle per stuk wijst het zinsdeel letterlijk aan | **F01 niet gemeten.** De controle draaide wel drie keer, en is daar **nog niet goed**: zie hieronder. |
| `na_subagent`: geen vraag meer om `get_artikel` na een rapport | **Gehaald.** 0 geweigerde toolaanroepen na een subagent; run 2 had er 24. |
| S03/S04: de rapportcitaten onder het antwoord | **S03 gehaald** (19 citaten). **S04 niet**: daar komt het rapport helemaal niet door. |
| E03: "BW art. 3:239" gevonden | **Gehaald**, 149k. |
| M01 en M06 uitgevoerd | **Gehaald**, beide goed. |
| Het jaartal telt niet als aantal gelezen stukken | Niet gemeten: het speelde in F01. Bij de 26 gemeten opdrachten komt het niet voor. |

### De controle per stuk

Hij draaide bij S01 (7,8k), M06 (7,9k) en P02 (11,5k), en meldde vijf keer `tegenspreekt`. Elke melding is
tegen de volledige tekst van het stuk nagelezen:

| Stuk | Wat Lex zegt | Wat de controle aanwijst | Volgens de tekst | Oordeel |
|---|---|---|---|---|
| HR:2023:1371 (S01) | de gewezen bestuurder wordt altijd toegelaten tot weerlegging (art. 36, leden 5 en 6) | "artikel 36, lid 4, tweede volzin, IW 1990" | de uitspraak: "Daarentegen wordt de gewezen bestuurder (…) steeds toegelaten" | **vals**; het aangewezen stuk is een wetsverwijzing, geen zinsdeel dat iets tegenspreekt |
| HR:2026:586 (M06) | de Hoge Raad vernietigde het oordeel over de vergrijpboete | "De uitkomst hiervan is dat deze klachten niet k[unnen leiden tot vernietiging]" | dat gaat over het principale beroep; het incidentele beroep is gegrond en de Hoge Raad "vernietigt de uitspraak van het Hof" voor de vergrijpboete 2013 | **vals**; de controle leest het verkeerde beroep |
| kst-26728-3 (P02) | de artikelen 25 en 26 gelden niet meer voor commanditaire deelnemingen | "artikelen 25 en 26 van de Invorderingswet 1990, anders dan onder de Wet op de inkomstenbelasting 1964, niet langer van t[oepassing]" | dat staat er letterlijk, en het bevestigt Lex | **vals** |
| kst-36151-3 (P02) | de bestaande kwijtscheldingsbepalingen "in de Invorderingswet en de Awb" zijn ontoereikend | "De bestaande kwijtscheldingsbepalingen in de Awb en de socialezekerheidswetgeving zijn niet …" | het stuk noemt de Awb en de sociale zekerheid, niet de Invorderingswet | **terecht**: Lex zet de verkeerde wet in de zin |
| (S01) HR:2023:181, :183, :184 | – | "samenvatting zonder gelezen tekst" | het antwoord noemt ze alleen als niet gelezen | vals, maar onschuldig |

**Eén van de vier inhoudelijke meldingen is terecht.** De nieuwe eis werkt maar half. De controle wijst nu wel letterlijk
iets aan, maar het aangewezen stuk is een wetsverwijzing (HR:2023:1371), het verkeerde deel van de uitspraak
(HR:2026:586) of juist de passage die Lex bevestigt (kst-26728-3). De twijfel van de ontwikkelsessie klopt dus: het
model doet dit nog niet goed. De zinnen blijven wel in het antwoord staan. De schade is een `onbevestigd` die de jurist
een juiste samenvatting laat wantrouwen.

## Wat er misging

1. **S04: het rapport van het kind haalt het antwoord niet.** Zie boven. Het is een regressie tegen run 2 (goed).
2. **De controle per stuk meldt nog valse tegenspraak.** Drie van de vier inhoudelijke meldingen zijn vals.
3. **Citaten zonder inhoud.** Bij P01 (trefwoorden), P02 (procedurezinnen) en S05 (de aanhef van het besluit) staan
   letterlijke zinnen onder het antwoord die niets dragen. Ze zijn brongetrouw, maar de jurist heeft er niets aan.
4. **S01 zonder citaten.** Het sjabloon `antwoord_extern` werd geweigerd (`overig`), en daarna ging het antwoord als
   tekst, zonder passage.
5. **P01: de rechtspraak per uitspraak gaat verloren.** Het kind had vier arresten met inhoud, en het antwoord maakt
   daar één alinea van.
6. **De kinderen zijn duur, maar wel binnen de grens.** 17 kinderen kostten samen 3,46M, gemiddeld 203k. Het duurste
   was 294k (P02); er ging er geen over de 300k. Ze beginnen op 15–27k context.
7. **Kleinigheden die bleven:**
   - E05 gaat nog via `duiding`;
   - bij E08 staat een kale IRI (de slottekst van artikel 22, derde lid) als vindplaats.

## Brongetrouw

Getoetst is elk blokcitaat, en elk citaat van vijf woorden of meer in de lopende tekst. De bronnen:
- de volledige toestanden van de Iw 1990, de Awb, de AWR, de Awir en de Leidraad uit de BWB-repository;
- elk stuk dat het antwoord noemt, zoals de officiële bekendmakingen en de Rechtspraak het publiceren;
- daarnaast de zinnen die de controle per stuk aanwees.

**Er zijn 270 citaten in 13 antwoorden, en ze staan alle 270 letterlijk in de bron.** Er is geen onjuiste bron, geen
verzonnen citaat en geen stuk genoemd dat niet gevonden is. In de samenvattingen staat één onjuistheid, bij P02, over
kst-36151-3: daar staat de Invorderingswet, waar de Awb en de sociale zekerheid bedoeld zijn.

## Wat er openstaat voor A6

- **V03, V04 en F01–F05 in run 3.** Volgens run 2 kost dat ongeveer 2,5M, plus de kwaliteitsset (deel 2, ongeveer 2,6M).
  Pas daarmee zijn de fixes voor V03, PHR:2025:435 en het jaartal te toetsen.
- **S04.** Een fix in de overdracht van het rapport naar het eindantwoord.
- **De controle per stuk.** Ze is nog niet betrouwbaar genoeg om te markeren. Een mogelijke koers: alleen markeren als
  het aangewezen zinsdeel zelf een bewering bevat. Een wetsverwijzing of een zin die Lex bevestigt telt dan niet.

## Bestanden

- `a6r3-runs.jsonl`: de 26 opdrachten (`centrale_agent_vat.py`): 23 uit de agentset en P01–P03. Let op: `per_rol` dekt
  bij een opdracht met meer beurten alleen de laatste beurt; `delta_account` dekt de hele opdracht.
- `a6r3-kinderen.jsonl`: de 17 kindruns zonder tekst. Per kind staan erin:
  - ouder-run, agentvorm en profiel;
  - aanroepen, modellen, ruw, gewogen en de beginnende context;
  - het sjabloon, de tools en `onbevestigd`.

  De twaalf kinderen van de regie (M02–M05) kostten 0 tokens en staan er niet in.

De ruwe runs (antwoordtekst en events) staan niet in de repo.
