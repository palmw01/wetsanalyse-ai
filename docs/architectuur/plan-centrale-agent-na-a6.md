# Plan: de open punten van de centrale agent na A6

Soort: *plan* (16 nov 2026). Er is nog niets gebouwd. Het hoort bij
[ADR-016](adr-016-centrale-agent-en-werkplaats.md) en neemt de sectie *Centrale agent na A6* van
[`PLAN.md`](../PLAN.md) over, met bevinding B-2 uit het
[E2E-verslag Rekeningafspraken](../acceptatie/verslag-e2e-rekeningafspraak-2026-11-16.md).

Getoetst op master `ac100b81`. Bronnen:
- de korte meting na A6 ([`na-a6.md`](metingen/centrale-agent-2026-11-15-na-a6/na-a6.md));
- de slotmeting met de slotlijst ([`a6-slot.md`](metingen/centrale-agent-2026-11-15-a6-slot/a6-slot.md));
- het eindverslag ([`a6-eind.md`](metingen/centrale-agent-2026-11-15-a6-eind/a6-eind.md));
- het E2E-verslag;
- de code in `tools/graph-qa/agent/`.

Sinds de slotmeting (op `81bee0d1`) zijn gemerged, en niet gemeten:
- de agentprofielen 1–5 (#1565);
- A7 (#1566, #1574);
- B-3, het nalezen na een subagent (#1595);
- het denkproces D-1–D-15 (#1595, #1597).

**Werkwijze voor elke stap:**
- Een oplossing verandert een algemeen mechanisme, geen maatwerk voor het gemeten artikel, werkgebied of arrest.
- Meten gebeurt licht: één run, een gerichte set, alleen de geraakte vorm, en alleen met akkoord van de gebruiker per
  meting.
- De hoofdsessie bundelt de PR's en merget ze.

## De stand per punt

| # | Punt | Stand op master | Waarheen |
|---|---|---|---|
| 1 | S01: de tekst naast `antwoord_extern` valt weg | geldt | PR A |
| 2 | Citaten bij uitspraken zijn trefwoorden of procedure | geldt deels (#1561 kiest per punt; de slotmeting liet S01 nog 0 van 4 zien) | PR A |
| 3 | Een kind op zijn rondegrens vraagt niets | geldt, behalve het geval "niets gelezen" (#1556, `ongelezen_vraag`) | PR C |
| 4 | De controle per stuk heeft een gerichte set nodig | geldt | PR B |
| 5 | De toets op dragende passages markeert juiste samenvattingen | onbekend: gemeten vóór #1561, daarna niet meer bij HR:2023:1371 | PR B |
| 6 | `delegatie_stand` wordt niet gebruikt | geldt, maar is geen fout: de route in code geeft de stand al (`stand_delegaties`) | PR D |
| 7 | Kinderen lopen tegen hun rondegrens aan | **gebouwd** (agentprofielen 1 en 4, #1565: `max_rondes`/`budget` per profiel, 10 rondes voor wetsgeschiedenis en bepalingen); de meting staat nog open | meting plan agentprofielen |
| 8 | P01: het eindantwoord maakt van het rapport één alinea | geldt, zelfde oorzaak als 1 | PR A |
| B-2 | Het zoeken naar bronnen mist de kern | geldt | PR E (spoor zoekvragen) |

Punt 9 (klein: E05, E08, E03, K18) en punt 10 (de meetset) staan onderaan, bij *Laten vallen of achteraan*.

## Punt 1, 2 en 8: één oorzaak, het sjabloon heeft geen plek per stuk

**De oorzaak.** De vraag "vat per uitspraak samen" eindigt na een rapport met `antwoord_extern`
(`sjablonen/extern.py`, `schema`). Dat sjabloon heeft vier velden:
- `kort_antwoord`: "twee tot vier zinnen";
- `extern`: de aanwijzingen `{id, van_nr, tot_nr}`;
- `stukken`;
- `twijfel`.

Er is geen plek voor wat het model per stuk zegt. Twee dingen gebeuren dan:
- **S01:** het model schrijft het overzicht per stuk náást de aanroep (4.345 tekens `tekst_ernaast`). De code gooit
  die tekst bewust weg (`nodes/antwoord.py`, de regel na `tel_sjabloon(..., "tekst_ernaast")`; de prompt AFRONDEN MET
  EEN SJABLOON zegt het ook). Het antwoord belooft daarna een overzicht dat er niet staat.
- **P01:** het model blijft binnen het sjabloon en perst vier arresten in twee tot vier zinnen.

**Het verband met de citaten (punt 2).** De code kiest de passages bij een stuk per punt van de samenvatting
(`extern.punten`, `dragende`, `herkies`, #1561). Als de samenvatting alleen het korte antwoord is, zijn er weinig
punten. Dan wint de alinea die de meeste woorden van dat korte antwoord deelt, en dat is vaak de inhoudsindicatie met
trefwoorden. Zo ging het bij S01 in de slotmeting: alle vier de citaten waren trefwoordregels. Met een samenvatting per
stuk krijgt `dragende` de woorden waarop die samenvatting rust.

**De oplossing (generiek: het blok `extern` draagt de kern per stuk).**
1. **Elke aanwijzing in `extern` krijgt het veld `kern`**: één tot drie zinnen in eigen woorden over wat dít stuk
   zegt over de vraag. Het veld is strict verplicht en mag leeg zijn, zoals `extern` zelf. Het geldt in
   `antwoord_extern` én in het subsjabloon, dus voor elke connector en elk sjabloon tegelijk.
2. **De code zet de kern in het blok** (`bronmodel.antwoord.Extern.kern`), tussen de kop van het stuk en de passages.
   De werkplek toont het blok al per stuk (`frontend/lib/antwoord.ts`). Een leeg veld toont niets, en een ouder bericht
   zonder veld blijft geldig.
3. **De passages kiezen op de kern van dat stuk.** `herkies` en `dragende` lezen per stuk eerst de kern en daarna
   het korte antwoord. Een inhoudsindicatie die alleen trefwoorden draagt, valt al af (`is_formule`). Een
   inhoudsindicatie met zinnen rangschikt onder een rechtsoverweging die even veel draagt. Dat is een rangregel in
   `_rang`, geen uitsluiting.
4. **De toetsen lezen de kern per stuk.** `gelezen.zonder_steun`, `vraag_niet_in_stuk` en de controle per stuk
   (`stukcontrole`) krijgen de kern met het id waar hij bij hoort. Ze hoeven het stuk dan niet uit koppen of zinnen
   af te leiden (`per_stuk`). Dat is preciezer, en het helpt punt 5.
5. **`kort_antwoord` blijft kort** en vat samen over de stukken heen. De omschrijving zegt: per stuk in `kern`,
   niet in het korte antwoord en niet ernaast.
6. **Tekst naast het sjabloon blijft weggegooid.** Het denkproces en de historie blijven zoals ADR-008 ze wil. De
   telling `tekst_ernaast` laat in de meting zien of de kern het lek dicht.

**Overwogen en afgewezen:**
- Tekst naast `antwoord_extern` toelaten als toelichting. Daarmee komt de vrije tekst terug die ADR-008 wegnam, en de
  toetsen moeten dan het stuk weer uit de tekst afleiden.
- Een apart sjabloon `antwoord_per_stuk`. Dat is een tweede vorm van hetzelfde blok, en de keuze tussen de twee kost
  het model een beslissing die de code niet kan toetsen.

**De tests:**
- schema: `kern` in `antwoord_extern` en het subsjabloon, strict en byte-gelijk zonder connector;
- `tests/context/test_strict_grenzen.py` binnen de grens (het extra veld zit in een array-item, geen nieuwe tool);
- vullen: een kern komt per stuk in het blok, een leeg veld niet;
- de werkplek toont de kern, en een oud bericht blijft geldig (vitest);
- `dragende`/`herkies`: met een kern wint de rechtsoverweging die de kern draagt van de trefwoordregel. Eén
  trefwoordregel in de vorm van S01 ("Artikel …; …; …"), gegenereerd, niet het arrest zelf;
- de toetsen per stuk: `zonder_steun` leest de kern bij het id;
- `tests/context/test_modelverzoeken.py` opnieuw vastgelegd (de schema's veranderen);
- de kruistests: `bronmodel` raakt api en graph-qa.

**Meting.** Ja: dit verandert het schema van elke beurt met een connector. Geraakte vorm: een rapport over uitspraken
of Kamerstukken, samengevat per stuk. Opdrachten: S01, P01 en F02 (rechtspraak), V03 (wetsgeschiedenis). Eén run.
Drempels:
- S01 en P01 geven per stuk een kern;
- `tekst_ernaast` is 0 of klein;
- minstens de helft van de citaten draagt de kern;
- geen onjuiste bron;
- geen regressie op F02.

Zie *Meten* voor het voorstel om dit samen te doen met de meting van de agentprofielen.

**Grootte en risico.** Middel. Het raakt `bronmodel`, graph-qa (schema, vullen, toetsen) en de frontend (één veld in
een bestaand blok). Het risico zit in het voorvoegsel: een veld erbij in elk schema met een connector maakt de cache
één keer koud. De omvang van het schema verandert weinig.

## Punt 4 en 5: de toetsen op een stuk, met een gerichte set

**De oorzaak van punt 5.** `gelezen.zonder_steun` is een toets op woorden: minstens `MIN_STEUN` (de helft) van de
eigen woorden van een duiding staat, op hun stam, in de passages die het rapport uit dat stuk citeert. Een juiste
samenvatting in eigen woorden, of een die rust op een passage die niet geciteerd is, valt daar onder. Het gevolg is
"die de passages van dat stuk niet dragen". De lezer die het wél kan beoordelen, de controle per stuk
(`stukcontrole.py`), draait alleen als de goedkopere toetsen níets vonden. Een valse melding van de woordtoets sluit
de lezer dus juist uit.

**De oorzaak van punt 4.** De lezer draaide sinds de nieuwe regel vier keer, met 0 meldingen. Dat zegt niets, omdat
er geen geval met een bekende tegenspraak in zat.

**De oplossing (generiek: de woordtoets wijst aan, de lezer beslist).**
1. **"Niet dragen" wordt een kandidaat, geen bewering.** Een melding "die de passages van dat stuk niet dragen" gaat
   naar de controle per stuk, met die zin en de passages. Zegt de lezer `steunt`, dan vervalt de melding. Zegt hij
   `spreekt_tegen`, dan blijft ze, met de bevestiging die er al is (`bevestig`). Zegt hij `niet_te_zien`, dan blijft
   de melding zoals nu. "Zonder passage van dat stuk" blijft zonder lezer een bewering: daar valt niets te lezen.
2. **De lezer draait dus ook als de woordtoets iets vond**, maar alleen voor de stukken met zo'n kandidaat, binnen
   de bestaande grenzen (`MAX_STUKKEN`, `MAX_ZINNEN`, `MAX_PASSAGE`). De kosten blijven één aanroep per beurt, en alleen
   na een rapport.
3. **Een gerichte set voor de lezer, offline.** Ongeveer twaalf gevallen in `tests/data/`, elk een passage, een
   zin en het verwachte oordeel:
   - vier omgedraaide beweringen in de woorden van de passage (de vorm van bundel 119);
   - vier juiste samenvattingen in eigen woorden (de vorm van HR:2023:1371 in S01 en F01);
   - twee verwijzingen;
   - twee keer "zegt meer".

   De passages komen uit gelezen openbare uitspraken, kort, en de zinnen zijn eigen tekst. Zonder model toetst de
   suite de plumbing met een gescripte `FakeLLM`. Met het model draait een klein script (`eval/stukcontrole_set.py`)
   de lezer één keer per geval. Dat zijn ongeveer twaalf aanroepen van 3–5k tokens, dus onder 100k, en het gaat alleen
   met akkoord.

**De tests:**
- de woordtoets meldt, de lezer zegt `steunt`, en de melding vervalt;
- de lezer zegt `spreekt_tegen`, en de melding blijft met bevestiging;
- een fout van de lezer laat de melding staan;
- "zonder passage" gaat niet naar de lezer;
- de grenzen;
- de set als datatest: vorm en oordelen.

**Meting.**
- Het script op de set. Akkoord nodig, maar geen acceptatie nodig. Drempel: geen vals `spreekt_tegen` op de juiste
  samenvattingen, en minstens drie van de vier omgedraaide beweringen gevonden.
- Op acceptatie meet de run van PR A het mee: S01 en F01 zonder de valse melding bij een juiste samenvatting.

**Grootte en risico.** Klein tot middel. Het risico: een lezer die te makkelijk `steunt` zegt, laat een echte
afwijking door. Daarom vervalt alleen "niet dragen" op `steunt`, en blijft elke andere toets staan.

**De volgorde met PR A.** Bouw B na A. Met de kern per stuk krijgt de lezer schone paren van stuk en zin, en is de set
meteen in de vorm van het nieuwe blok.

## Punt 3: een begrensd kind vraagt of het verder mag

**De oorzaak.** In de laatste ronde (`met_laatste_ronde`) mag een kind kiezen tussen `klaar`, `vraag` en
`niet_gelukt`. Bij de rondegrens kiest het model `klaar` of `niet_gelukt`, met de ongelezen stukken onder `open`. Een
vraag naar boven komt dan niet. De code maakt die vraag alleen zelf in één geval (`subagent.ongelezen_vraag`, #1556):
een opdracht over een bron naast de wet waarin het kind stukken vond maar er **geen** las. V03 in run 3 viel daaronder.
S04, F02 en P01 (wel gelezen, maar niet alles) vallen erbuiten.

**De oplossing (generiek: begrensd en onvolledig is een vraag uit code).** De regel van `ongelezen_vraag` wordt breder:
- als het kind afsloot op zijn grens (`State.laatste_gehad`, reden rondegrens of budget), of de code het afsloot
  (`afgesloten`);
- en de trace stukken of bepalingen bevat die gevonden zijn en waar de opdracht om vroeg, maar die niet gelezen zijn
  (`gelezen_en_gevonden`, en voor een reeks bepalingen de reeks uit `inhoudsopgave`/`zoek_opbouw` tegen wat gelezen
  is);
- dan komt er een vraag uit code: "Ik las er N van de M; X, Y en Z niet. Zal ik verder lezen?", met de opties
  *Ja, lees verder* en *Nee, rond af*.

Een *ja* hervat het kind met een nieuwe begroting (`subagent.hervat`, zoals nu). Eén keer per delegatie, niet na een
hervatting, en niet als de ongelezen stukken buiten de periode van de jurist vallen. Het rapport blijft staan. De
vraag komt erbij, zoals `ongelezen_vraag` nu doet. Dit is code, geen promptzin. Het model kiest aan zijn grens niet
betrouwbaar voor `vraag`, en de code weet precies wat er ongelezen is.

**Waarom niet alleen meer rondes (punt 7).** De profielen gaven wetsgeschiedenis en bepalingen al 10 rondes. Meer
rondes schuift de grens op, maar een lange reeks raakt haar toch. Het budget is een vangnet, geen doel (plan
agentprofielen). De vraag maakt de grens zichtbaar en laat de jurist beslissen, wat de kosten ook zijn.

**De tests:**
- een kind op de rondegrens met ongelezen stukken geeft de vraag;
- een kind dat alles las, geeft geen vraag;
- na een hervatting geen tweede vraag;
- ongelezen stukken buiten de periode geven geen vraag;
- een reeks bepalingen;
- *ja* hervat, *nee* rondt af met het rapport (`tests/centrale_agent/test_subagent_vragen.py`, `tests/centrale_agent/test_a6_eind.py` uitgebreid).

**Meting.** Ja, met S04 en P01 (de kinderen die tegen de grens lopen) en V03. Dat zijn precies de opdrachten van de
meting van de agentprofielen, dus samen meten (zie *Meten*).

**Grootte en risico.** Klein tot middel. Het risico: een extra vraag waar de jurist liever een afgerond antwoord had.
Daarom geldt de regel alleen bij een kind dat echt op zijn grens stopte, niet bij een kind dat zelf vond dat het genoeg
had.

## Punt 6: `delegatie_stand` en de meetset

**De stand.** F03 is goed sinds #1561. Een vraag over de deelgesprekken krijgt de stand uit code mee
(`overdracht.is_standvraag`, route `stand_delegaties`, `_delegatie_stand` in `supervisie`). Het model hoeft de tool
dan niet aan te roepen. Dat is beter dan een toolaanroep: het kost geen ronde, en de stand komt altijd mee. Alleen de
set eist de tool (`golden_centrale_agent.jsonl`, F03: `tools_verplicht: ["delegatie_stand"]`).

**Het voorstel.**
- De set eist het resultaat, niet de weg: F03 verwacht de stand in het antwoord, met de tool **of** de route
  `stand_delegaties`.
- De tool blijft als vangnet voor een standvraag die de regel niet herkent. Het schema is klein en niet strict.

Weghalen kan ook, als de gebruiker het voorvoegsel kleiner wil. Dan moet de regel `_STANDVRAAG` dat vangnet
overnemen.

In dezelfde PR, omdat het ook alleen de set raakt (punt 10 uit de slotlijst):
- K03 en K09 accepteren "veertien dagen" naast "14 dagen";
- S02 wordt vervangen door een opdracht die een subagent nodig heeft;
- de "goed"-teksten van F05 en S04 noemen het citaat of de volledigheid expliciet.

**De tests:** `tests/evals/test_golden_centrale_agent.py` (de vorm van de set).

**Meting:** nee. Het verandert alleen wat de meting verwacht. Het gedrag van Lex verandert niet.

**Grootte en risico:** klein.

## B-2: het zoeken naar bronnen mist de kern

**Wat B-2 is** (E2E-verslag, tabel *Bevindingen*). Bij deelvraag 1 vond Lex Iw 7a lid 1, Awir 25 en Awb 4:89 niet,
terwijl hij Uitv.reg. Iw art. 40ca lid 1 wel vond, en die verwijst zelf naar 7a. De kandidaten per deelvraag
verschilden nauwelijks: dezelfde bepalingen bij 4 of 5 deelvragen, met ruis uit de Leidraad. De bepaling die het eerste
praktijkvoorbeeld beslist (Uitv.reg. Awir art. 6), ontbrak, terwijl ze binnen het zoekbereik lag.

**Waarom het een meting vraagt.** Het is rangschikking en ontdekking in de bronselectie (spoor zoekvragen). Een
wijziging daar verschuift de uitkomst van elke deelvraag in elk werkgebied. Eerdere rondes lieten zien dat een winst op
één set op een andere set kan omslaan (*Bronselectie zoeken + namen*, 3 nov 2026: de pool ging omhoog, de top-8 maar
half). B-2 hoort bij de centrale agent alleen doordat de E2E-test het vond. Het mechanisme is van `bronnen_vinden.py`,
`deelvraag_zoeken.py` en `zoekvragen.py`.

**De oorzaken in de code:**
1. **`verwijzing_uit` vertrekt alleen vanuit de kern** (`bronnen_vinden.STANDAARD`, met een kern; `ZONDER_KERN` is
   alleen het overzicht). Bij de eerste deelvraag van een nieuw werkgebied is er nog geen kern. Een kandidaat die naar
   de kern verwijst (40ca → 7a), brengt het doel dus niet mee.
2. **De rangschikking per deelvraag** gebruikt de termen van de deelvraag, maar ook de termen die alle deelvragen
   delen (het onderwerp van het werkgebied). Daardoor rangschikken alle deelvragen ongeveer hetzelfde.
3. **De gebeurtenis** (zoekvraag a, `zoekvragen.grondslag`) zoekt waar de gebeurtenis haar bestaansrecht krijgt. Een
   algemene regeling die de handeling zelf regelt (betaling in de Awb), valt erbuiten als de deelvraag haar niet bij
   naam noemt.

**De oplossing (generiek):**
1. **Verwijzingen vanuit de sterkste kandidaten, diepte 1.** Zonder kern volgt `verwijzing_uit` ook de verwijzingen
   van de bovenste N kandidaten van een deelvraag (bijvoorbeeld 5). Ligt het doel binnen het zoekbereik, dan komt het
   mee met de rol *afhankelijkheid* en de herkomst "verwezen vanuit …". Diepte 1 volgens de skill
   (`references/verwijzingen-volgen.md`). Dat is de regel die er al is, met een ander vertrekpunt.
2. **Onderscheidend rangschikken per deelvraag.** Een term weegt zwaarder naarmate hij in minder deelvragen van het
   werkgebied voorkomt, zoals een idf over de deelvragen. Een term die in alle deelvragen staat, telt nog als
   onderwerp, maar bepaalt de volgorde niet. Dezelfde bepaling bij vijf deelvragen kan blijven. Ze staat dan alleen niet
   overal bovenaan.
3. **De gebeurtenis ook in de opschriften.** De gebeurtenis van het dossier (en haar stam, zoals in `zoekvragen`)
   zoekt ook met `zoek_opbouw` in de opschriften van de regelingen in het zoekbereik. Een afdeling die naar de
   handeling heet ("Betaling"), komt zo mee, zonder dat de code een regeling of afdeling bij naam kent.

Niet in dit plan: B-9 (de kaart met regelingen noemt de kern als "buiten"). Dat raakt het filter van het zoekbereik en
hoort bij dezelfde spoor-PR's, maar is een eigen bevinding.

**De tests:**
- eenheidstests op de drie mechanismen, met een nepgraaf;
- `tests/test_bronselectie.py` en `tests/werkgebied/test_zoekvragen.py`;
- de bestaande vijf sets in `docs/wetsanalyse/referentieset-bronselectie/` mogen niet achteruitgaan
  (`eval/bronselectie_eval.py --intake`, offline tegen de opnames).

**Meting.** Ja, offline: `eval/bronselectie_eval.py --intake` tegen de opnames van de graaf. Daar is geen Lex en geen
model voor nodig.
- **Een nieuwe set** `rekeningafspraken-deelvragen-concept`, met de verwachte bepalingen uit het E2E-verslag (Iw 7a,
  Awir 25, Awb 4:89, Uitv.reg. Iw 40ca, Uitv.reg. Awir 6). Het is een **ontwikkelset**: hij is afgeleid uit de
  bevinding, dus winst daarop bewijst niets.
- **Het bewijs komt van een set die het werk niet zag.** De vijf bestaande sets zijn alle ontwikkel (stand 4 nov
  2026). Daarom vraagt het een nieuwe blinde set uit een ander werkgebied, door de agent-jurist opgesteld vóór de
  meting.
- De opname van de nieuwe sets leest de graaf één keer live (`--opnemen`). Dat is lezen, geen vraag aan Lex, maar het
  gaat wel naar acceptatie. Daarom alleen met akkoord.

**Grootte en risico.** Middel. Het risico is ruis: meer kandidaten via verwijzingen. Daarom N klein, diepte 1, alleen
binnen het zoekbereik, en de rol *afhankelijkheid*, niet *kern*.

## Laten vallen of achteraan

- **Punt 9, klein.** Elk punt is op zichzelf klein, en voor de jurist zichtbaar zijn alleen E08 en K18.
  - **E08, een kale IRI als vindplaats:** voor de jurist zichtbaar. Wel doen, los en klein, als er een geval opduikt
    in het gebruik. De vindplaats hoort uit het label te komen (`provenance._labels`).
  - **K18, 61 keer `onbevestigd`:** alleen een signaal, geen afkeuring. Laten vallen tot het in gebruik opvalt.
  - **E05, via `duiding`:** sinds A7 bestaat de keuze voor `duiding` als subagent niet meer (`kiesbaar: false`).
    Waarschijnlijk vervallen, en de eerstvolgende meting laat het zien.
  - **E03, twee sjabloonweigeringen:** dat kost tokens, maar het antwoord klopt. Laten vallen.
- **Punt 10, de meetset:** zit in PR D.

## Samenhang en volgorde

| PR | Inhoud | Hangt af van | Meting |
|---|---|---|---|
| **D** | de meetset: F03 op resultaat, K03/K09, S02, F05/S04 | – | nee |
| **A** | de kern per stuk in `extern`; de passages kiezen erop; de toetsen lezen hem (punt 1, 2, 8) | – | ja, samen met C |
| **C** | begrensd en onvolledig is een vraag uit code (punt 3) | – (raakt andere bestanden dan A) | ja, samen met A |
| **B** | "niet dragen" naar de lezer; de gerichte set (punt 4, 5) | A | offline script; acc via de run van A en C |
| **E** | B-2: verwijzingen vanuit de kandidaten, onderscheidend rangschikken, de gebeurtenis in de opschriften | – (los spoor) | offline eval en een blinde set |

1. **D eerst**: klein, geen gedrag, en de meting na A en C rekent er al mee.
2. **A en C naast elkaar** (andere bestanden: A in de sjablonen en de toetsen, C in `subagent.py` en de afsluiting).
   Ze worden samen gemeten.
3. **B na A**: de lezer krijgt dan de paren uit het nieuwe blok.
4. **E los**, in het spoor zoekvragen. Het hangt niet aan de centrale agent en kan elk moment.

## Meten

**Het voorstel: één meetronde voor A, C en de agentprofielen.**
- De meting van het plan agentprofielen staat nog open (*Meting* in
  [`plan-agentprofielen.md`](plan-agentprofielen.md)). Ze bevat al S01, F01, F02, V03, S04, P01 en M06.
- Dat zijn de opdrachten die A en C raken.
- Eén ronde na de bundel met D, A en C meet dus alle drie, in plaats van twee keer dezelfde opdrachten.
- Licht gehouden: één run, alleen die opdrachten (zonder E01–E05 en zonder S03, S05 en M01, tenzij de gebruiker het
  hele profielplan wil), met een plafond dat de gebruiker kiest. De raming uit run 3 en de slotmeting is ongeveer
  2–2,5M.
- Tijdens de meting wordt er niet gemerged.
- Komt een drempel niet, dan geen nieuwe ronde per bevinding (besluit 15 nov 2026). Dan volgt een voorstel aan de
  gebruiker.

De andere metingen zijn klein en lopen niet over acceptatie:
- het script voor de lezer (B), onder 100k;
- de eval van de bronselectie (E), zonder model, met één opname uit de graaf.

## Open keuzes voor de gebruiker

1. **De kern per stuk (A):** een veld `kern` per aanwijzing in `extern` (voorstel), of tekst naast het sjabloon
   toelaten als toelichting?
2. **Meten (A en C):** samen met de open meting van de agentprofielen, in één ronde (voorstel)? En met welk plafond?
3. **`delegatie_stand` (D):** de tool houden als vangnet en de set op het resultaat laten toetsen (voorstel), of de tool
   weghalen?
4. **B-2 (E):** in het spoor zoekvragen, met een nieuwe ontwikkelset Rekeningafspraken en een nieuwe blinde set uit een
   ander werkgebied (voorstel)? Dat vraagt eenmalig een opname uit de graaf op acceptatie.
5. **Punt 9:** laten vallen, behalve E08 als het in gebruik opduikt (voorstel)?
