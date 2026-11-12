# De centrale agent, ronde 0: de nulmeting tegen de huidige Lex – 12 november 2026

- **Soort:** *meting* (ADR-016 §A6, stap M0).
- **Code:** master `808c908e` (bundel 78), dezelfde versie voor alle drie de runs.
- **Straat:** acceptatie. **Model:** `claude-sonnet-4-6`.
- **Wat er gemeten is:** de agentset (`tools/graph-qa/eval/golden_centrale_agent.jsonl`, 30 opdrachten) tegen de Lex van
  nu: supervisor, specialisten en regisseur. Drie runs, 90 opdracht-runs, 117 beurten (39 per run, met de opzetbeurten en de bevestigingen).
- **Gegevens:** [`ronde-0-runs.jsonl`](ronde-0-runs.jsonl), één regel per opdracht en run.

Dit is het vertrekpunt van de meetlus. De set beschrijft het doel van ADR-016 (een centrale agent die zelf antwoordt en
subagents opstelt). De Lex van nu heeft geen subagents buiten de regie. Veel samengestelde opdrachten passen daarom niet
op de set; dit verslag legt vast hoe ze nu aflopen.

## Uitkomst in het kort

- **Brongetrouw: 90 van 90.** Geen onjuiste bron en geen verzonnen citaat. Alle 551 citaten staan letterlijk in de
  officiële tekst van de wet of van het gelezen stuk.
- **Gewone vragen: 30 van 30 goed**, maar duur en wisselend. De mediaan is 38,6k tokens en 14 seconden; een uitlegvraag
  kost 93k tot 380k.
- **Delegatie: alleen de regie verdeelt.** M02 en M05 lopen zoals bedoeld, zonder tokens. De andere opdrachten die om
  een of meer subagents vragen, doet één specialist in één context: 26k tot 826k tokens per beurt.
- **Vragen naar boven: 0 van 4.** Lex gokt (V01, V04) of valt in een andere route (V02, V03).
- **Vervolg: 5 van 15 goed.** F01, F02 en F03 mislukken in elke run; in run 2 vallen F02 en F04 in *werkgebied
  samenstellen*.
- **Misroutes: 14 van 90.** M03, M04, V02 en V03 in elke run, F02 en F04 in run 2.
- **Verbruik: 15,38M tokens** over drie runs.

## Uitvoering

- Het script `tools/graph-qa/eval/centrale_agent_meting.mjs` draait de set via de clientbibliotheek van de
  acceptatie-MCP: een sessie uit een accounttoken, de BFF, en per beurt eerst de vraag in het gesprek en dan de run. Eén
  beurt tegelijk, elke opdracht in een nieuw gesprek.
- De bronstand gaat expliciet mee: `bronnen` uit de set (leeg = alleen wetgeving), met `bronnen_herkomst: "gesprek"`.
- De opdrachten met een werkgebied draaien in het meetwerkgebied *Meting centrale agent (M0, ADR-016)*, opgebouwd uit de
  eerste regel van de set: drie deelvragen, het zoekbereik Invorderingswet 1990 en Leidraad Invordering 2008, de
  gebeurtenis *verhaal*. Er is niets opgenomen en niets geannoteerd.
- Een vervolgopdracht heeft opzetbeurten in hetzelfde gesprek; alleen de laatste beurt telt als gemeten. F03 heeft er
  drie: de regie, haar bevestiging en een vraag in het eerste deelgesprek.
- Tijden (UTC): run 1 18:50–19:33, run 2 19:33–20:06, run 3 20:06–20:42. Geen beurt brak af en geen opdracht is
  herhaald.
- `centrale_agent_vat.py` maakt uit de ruwe runs de regels van `ronde-0-runs.jsonl`. De ruwe runs (antwoordtekst en
  events) staan niet in de repo.

## Afwijkingen van §A6

Gemeld aan de hoofdsessie vóór de meting, en akkoord bevonden.

1. **Tokens komen uit het `meting`-event**, niet uit de delta van het accountverbruik. Het account is gedeeld, en het
   budget is tijdens de meting twee keer gereset (zie *Verbruik*). De delta staat als controle in het bestand
   (`delta_account`).
2. **De nulmeting annoteert niet en neemt geen bron op.** Het stoppunt staat per opdracht in de set (`stoppunt`): de
   bevestiging van de gratis bronnenronde wordt gegeven, een ronde die annoteert nooit. Het meetpunt *grote opdracht in
   één keer* is daarom gemeten tot en met de bundel van de bronnenronde.
3. **De set beschrijft het doel, niet de huidige Lex.** `subagent`, `rapport`, `regie_plan` en `delegatie_stand` bestaan
   nog niet. Wat de samenvatting tegen de set toetst (`route_past`, `delegatie_past`, `tools_ontbreken`) is voor de
   route een benadering: een route in code vraagt het model hoogstens één keer, de centrale agent minstens één keer.
4. **De inhoud is beoordeeld door de meetsessie**, niet door de agent-jurist (geen subagents op de laptop).
5. **De bron bij een onderdeel van de Leidraad.** `bron_lezen` leest artikelen, geen divisies van een beleidsregel. De
   citaten uit de Leidraad zijn daarom getoetst tegen de volledige tekst van de toestand uit de BWB-repository.

## Hoe er beoordeeld is

- **Citaten.** Elk blokcitaat en elk citaat van vijf woorden of meer in lopende tekst is gezocht in de officiële tekst:
  de volledige toestanden van de Invorderingswet 1990, de Awb, de Leidraad Invordering 2008 en de AWR uit de
  BWB-repository, en van elk stuk dat het antwoord noemt de tekst bij de Rechtspraak of de officiële bekendmakingen.
  551 citaten in 41 antwoorden; twee treffers bij V04 bleken tekst tussen twee aangehaalde woorden en geen citaat.
  Twee stukken (een Staatsblad uit 1993 en een uitspraak uit 2013) waren niet als tekst op te halen; er was geen citaat
  dat daarvan afhing.
- **Inhoud.** Run 1 is per antwoord gelezen tegen `goed` uit de set en tegen de bepalingen in `bron` (`bron_lezen`:
  onder meer Iw 1, 2, 11 tot en met 22bis, 24, 30 en Awb 4:112). Van run 2 en 3 is het begin van elk antwoord gelezen
  en vergeleken met run 1; de routes zonder model gaven in alle runs dezelfde tekst.
- **Wat niet is nagegaan:** de samenvattingen van uitspraken en Kamerstukken zijn op hun citaten getoetst, niet zin voor
  zin tegen het stuk; of er bij artikel 36 Iw werkelijk geen annotaties bestaan (E10) is niet gecontroleerd.
- **goed / deels / fout** gaat over het antwoord tegen `goed`. Of er gedelegeerd is, staat er los van.

## Per opdracht

Per cel de drie runs. *Sjabloon*: het gevulde sjabloon, `tekst` als het antwoord tekst werd, `(wN)` het aantal
weigeringen. *Controle*: het oordeel van `verify`.

| Opdracht | Route | Modelrondes | Tokens | Duur (s) | Sjabloon | Controle | Oordeel |
|---|---|---|---|---|---|---|---|
| E01 | algemeen | 1 / 1 / 1 | 934 / 935 / 916 | 8 / 5 / 4 | – / – / – | gegrond / gegrond / gegrond | goed / goed / goed |
| E02 | overzicht | 0 / 0 / 0 | 0 / 0 / 0 | 1 / 1 / 1 | – / – / – | gegrond / gegrond / gegrond | goed / goed / goed |
| E03 | duiding | 8 / 6 / 9 | 148k / 115k / 195k | 61 / 94 / 119 | duiding / tekst (w2) / tekst (w2) | gegrond / onbepaald / onbepaald | goed / goed / goed |
| E04 | algemeen | 0 / 0 / 0 | 0 / 0 / 0 | 4 / 0 / 0 | – / – / – | onbepaald / onbepaald / onbepaald | goed / goed / goed |
| E05 | duiding | 3 / 2 / 2 | 78k / 49k / 49k | 35 / 19 / 25 | extern / extern / extern | gegrond / gegrond / gegrond | goed / goed / goed |
| E06 | afgewezen | 1 / 1 / 1 | 2k / 2k / 2k | 3 / 3 / 3 | – / – / – | – / – / – | goed / goed / goed |
| E07 | definitie | 5 / 4 / 5 | 46k / 34k / 46k | 15 / 14 / 15 | begrip / begrip / begrip | gegrond / gegrond / gegrond | goed / goed / goed |
| E08 | duiding | 12 / 9 / 14 | 312k / 193k / 380k | 223 / 157 / 199 | tekst (w3) / tekst (w2) / tekst (w2) | onbepaald / gegrond / onbepaald | goed / goed / goed |
| E09 | duiding | 8 / 6 / 10 | 124k / 93k / 186k | 58 / 50 / 100 | duiding / duiding / tekst (w2) | gegrond / gegrond / gegrond | goed / goed / goed |
| E10 | annotaties_lezen | 3 / 4 / 3 | 32k / 43k / 32k | 20 / 13 / 10 | annotaties / annotaties / annotaties | onbepaald / onbepaald / onbepaald | goed / goed / goed |
| S01 | algemeen | 8 / 11 / 14 | 280k / 453k / 611k | 82 / 160 / 109 | extern / extern (w1) / extern | gegrond / gegrond / gegrond | goed / goed / goed |
| S02 | duiding | 1 / 1 / 1 | 26k / 26k / 26k | 13 / 16 / 12 | extern / extern / extern | gegrond / gegrond / gegrond | goed / goed / goed |
| S03 | algemeen | 5 / 4 / 4 | 83k / 65k / 66k | 56 / 43 / 46 | tekst / tekst / tekst | onbepaald / onbepaald / onbepaald | deels / deels / deels |
| S04 | duiding | 16 / 10 / 8 | 428k / 264k / 186k | 274 / 235 / 153 | tekst (w2) / duiding (w1) / duiding | gegrond / gegrond / gegrond | goed / goed / goed |
| S05 | duiding | 14 / 9 / 9 | 439k / 204k / 266k | 102 / 71 / 74 | duiding / tekst (w2) / duiding | gegrond / gegrond / gegrond | goed / goed / goed |
| M01 | duiding | 16 / 16 / 14 | 487k / 462k / 361k | 433 / 244 / 219 | tekst (w3) / duiding (w1) / tekst (w2) | gegrond / gegrond / onbepaald | goed / goed / goed |
| M02 | regie | 0 / 0 / 0 | 0 / 0 / 0 | 4 / 4 / 3 | – / – / – | – / – / – | goed / goed / goed |
| M03 | bronselectie | 1 / 1 / 1 | 3k / 3k / 3k | 4 / 5 / 5 | – / – / – | – / – / – | deels / deels / deels |
| M04 | werkgebied | 2 / 2 / 2 | 5k / 5k / 5k | 10 / 10 / 9 | – / – / – | – / – / – | fout / fout / fout |
| M05 | regie | 0 / 0 / 0 | 0 / 0 / 0 | 3 / 3 / 3 | – / – / – | – / – / – | goed / goed / goed |
| M06 | duiding | 17 / 6 / 13 | 826k / 160k / 488k | 180 / 63 / 148 | duiding (w2) / extern / duiding (w2) | gegrond / gegrond / gegrond | goed / deels / deels |
| V01 | duiding | 12 / 10 / 10 | 417k / 323k / 343k | 133 / 72 / 113 | extern (w1) / extern / extern (w1) | gegrond / gegrond / gegrond | fout / fout / fout |
| V02 | bronselectie | 0 / 0 / 0 | 0 / 0 / 0 | 1 / 1 / 1 | – / – / – | – / – / – | fout / fout / fout |
| V03 | bronselectie | 0 / 0 / 0 | 0 / 0 / 0 | 1 / 1 / 1 | – / – / – | – / – / – | fout / fout / fout |
| V04 | duiding | 9 / 7 / 6 | 245k / 180k / 147k | 65 / 47 / 43 | duiding / duiding / duiding | gegrond / gegrond / gegrond | deels / deels / deels |
| F01 | duiding | 5 / 4 / 2 | 98k / 69k / 30k | 26 / 28 / 17 | extern / extern / – | gegrond / gegrond / gegrond | fout / fout / fout |
| F02 | duiding / werkgebied | 5 / 2 / 6 | 99k / 5k / 139k | 24 / 13 / 42 | duiding / – / duiding | gegrond / – / gegrond | fout / fout / fout |
| F03 | duiding / algemeen | 2 / 2 / 2 | 18k / 20k / 18k | 11 / 9 / 8 | tekst / tekst / tekst | onbepaald / onbepaald / onbepaald | fout / fout / fout |
| F04 | duiding / werkgebied | 13 / 2 / 14 | 338k / 6k / 426k | 81 / 18 / 107 | duiding / – / duiding | gegrond / – / gegrond | goed / fout / goed |
| F05 | duiding | 9 / 9 / 7 | 167k / 168k / 122k | 111 / 81 / 80 | tekst (w2) / duiding / duiding (w1) | onbepaald / gegrond / gegrond | goed / goed / goed |

## Per meetpunt, tegen de drempels van §A6

De drempels gelden voor de rondes na deze; hier staat de stand van nu.

- **Gewone vragen niet duurder** (de tien enkelvoudige opdrachten). Dit is de maat voor A2.
  - Mediaan over de 30 opdracht-runs: **38,6k tokens** en **14,3 s**. Per run: 38,6k / 38,6k / 38,5k tokens en
    17,6 / 13,3 / 12,2 s.
  - Som per run: 742k / 529k / 891k tokens. De spreiding zit in drie uitlegvragen: E03 115k–195k, E08 193k–380k,
    E09 93k–186k.
  - Zonder model of bijna: E02, E04 (0), E01 (0,9k), E06 (2k). E07 34k–46k voor één definitie, E10 32k–43k voor
    "geen annotaties gevonden".
  - E05 mist de route in code: een genoemd Staatsblad gaat via de specialist `duiding` (49k–78k) in plaats van de
    leesroute zonder model.
- **Juiste delegatie** (drempel ≥ 27/30). Nu **20 van 30 per run**, in elke run dezelfde 20.
  - Past: de opdrachten die geen subagent mogen hebben of er nul toelaten (E, V01, V02, V04, F), en M02 en M05 met drie
    deelgesprekken uit de regisseur.
  - Past niet: S01 tot en met S05, M01, M06 en V03 (geen subagent), M03 en M04 (geen regie).
- **Juiste profielkeuze** (drempel ≥ 13/15). Niet te meten: er zijn nog geen profielen. Bij de vijf opdrachten voor één subagent koos de
  supervisor in elke run dezelfde specialist: `algemeen` bij S01 en S03, `duiding` bij S02, S04 en S05.
- **Brongetrouw en gegrond** (drempel 30/30). **30 van 30 in elke run**: geen onjuiste bron, geen verzonnen citaat.
  - De controle van Lex zelf: 49 keer *gegrond*, 18 keer *onbepaald*, 23 beurten zonder controle (afwijzing, regie,
    vraagkaart). Geen enkele keer *ongegrond*, geen `niet_letterlijk`, geen `unsupported`.
  - *Onbepaald* valt samen met een antwoord in tekst nadat het sjabloon is geweigerd of overgeslagen. Het sjabloon is
    in 19 van de 90 runs geweigerd (34 weigeringen, vooral `antwoord_duiding`) en in 19 runs werd het antwoord tekst.
- **Inhoudelijk juist.**
  - Enkelvoudig: **30 van 30 goed.**
  - Samengesteld (20 opdrachten, 60 runs): **27 goed, 11 deels, 22 fout.** Per groep: één subagent 12 goed en 3 deels;
    meer subagents of fasen 10 goed, 5 deels, 3 fout; een vraag naar boven 3 deels en 9 fout; vervolg 5 goed en 10
    fout.
- **Vragen naar boven** (drempel 4/4). **0 van 4**, in elke run.
  - V01: kiest zonder te vragen de Invorderingswet 1990 en leest 6 tot 10 uitspraken (323k–417k).
  - V02: start de gewone bronselectie en zegt niet dat er geen deelvraag over verjaring is.
  - V03: valt in de bronselectie per deelvraag; de Kamerstukken komen niet aan bod.
  - V04: kiest zelf de wijziging van Stb. 2009, 610 en zegt dat. Inhoudelijk juist, maar er is niet gevraagd.
- **Grote opdracht in één keer.**
  - M02 en M05 (de letterlijke opdracht): het plan uit de stand, de bevestiging, drie deelgesprekken, de bundel met
    *opgeleverd* en *wacht op jou* (8 voorstellen per deelvraag). Drie runs gelijk, 0 tokens, 3 tot 4 s. De volgende
    fase is niet gestart (stoppunt).
  - M03 (een parafrase): komt niet bij de regisseur, maar in de bronselectie-stapmachine bij deelvraag 3.
  - M04 ("werk dit werkgebied uit"): wordt *dossier aanvullen*, met een kaart voor de aanleiding. Geen plan.
- **Kosten van delegatie.** Er is nog geen delegatie buiten de regie. Wat hetzelfde werk nu in één context kost:
  S01 280k–611k, S04 186k–428k, S05 204k–439k, M01 361k–487k, M06 160k–826k. S02 kost 26k: de code leest het genoemde
  Kamerstuk vooraf en het model schrijft één keer.
- **Regressie** (de kwaliteitsset en de routeringsset). Niet in deze ronde; dat is de ronde voor T1 en A1.

## Hoe het nu misgaat

- **Eén specialist doet alles** (21 runs: S01–S05, M01, M06). Het antwoord is meestal goed, maar de context groeit met
  elke ronde: 8 tot 17 modelrondes, tot 826k tokens, tot 433 s. Bij M06 leest de specialist in twee van de drie runs
  geen uitspraak en geeft hij van de rechtspraak alleen tellingen.
- **Een misroute door een vaste weg** (14 runs). Binnen een werkgebied vangt de bronselectie-stapmachine alles wat op
  bronnen zoeken lijkt (M03, V02, V03), en *dossier aanvullen* vangt "werk dit werkgebied uit" (M04). In run 2 viel een
  gewone vervolgvraag buiten een werkgebied in *werkgebied samenstellen* (F02 en F04: "De Invorderingswet 1990." en
  "En geldt dat ook voor zaken die de belastingschuldige least?").
- **Gokken in plaats van vragen** (6 runs: V01, V04). Wat er daarna staat is brongetrouw, maar de jurist heeft niet
  gekozen.
- **Het vervolg pakt het verkeerde op** (F01, F02). F01 antwoordt over een andere uitspraak dan de eerste van het
  overzicht. F02 maakt van het antwoord op een nooit gestelde keuze een beschrijving van de hele wet.
- **Geen zicht op de regie** (F03). Na een bundel en een vraag in een deelgesprek zegt Lex geen toegang te hebben tot
  de bundel of de deelgesprekken, of wijst de vraag af.
- **Het sjabloon wordt geweigerd en het antwoord wordt tekst** (E03, E08, E09, S04, S05, M01, M06, F05). Elke weigering
  kost een ronde; de controle komt dan uit op *onbepaald*. E08 mist het sjabloon in alle drie de runs.
- **Opschriften die de wet niet heeft** (S03). Het overzicht per artikel geeft elk artikel een eigen kopje; zonder
  sjabloon heeft de controle niets te toetsen.

## Verbruik

Uit de `meting`-events, invoer, uitvoer, cache lezen en cache schrijven samen.

| Run | Gemeten beurten | Opzetbeurten | Samen | Cache lezen | Cache schrijven | Invoer | Uitvoer |
|---|---|---|---|---|---|---|---|
| 1 | 4.699.759 | 1.323.199 | 6.022.958 | 4.098.629 | 502.645 | 7.190 | 91.295 |
| 2 | 2.940.590 | 1.266.114 | 4.206.704 | 2.578.559 | 280.542 | 10.444 | 71.045 |
| 3 | 4.126.730 | 1.022.401 | 5.149.131 | 3.673.199 | 367.620 | 7.782 | 78.129 |
| **samen** | **11.767.079** | **3.611.714** | **15.378.793** | | | | |

De kolommen cache, invoer en uitvoer gaan over de gemeten beurten.

- **Waar het in zit.** Per groep, drie runs, gemeten beurten: enkelvoudig 2,16M, één subagent 3,42M, meer subagents of
  fasen 2,81M, een vraag naar boven 1,66M, vervolg 1,72M plus 3,61M aan opzet.
- **De duurste opdrachten per run, met opzet:** run 1 M06 826k, F01 645k, F04 572k, F02 517k, M01 487k; run 2 F01 491k,
  M01 461k, S01 452k, F04 443k; run 3 F04 636k, S01 611k, M06 487k, F02 447k. De vervolgopdrachten zijn duur door hun
  opzet: F01 herhaalt S01, F02 herhaalt V01, F04 herhaalt E08.
- **De schatting vooraf was 4–6M voor alles**; het werd 15,4M. De schatting ging uit van 42k–130k per modelbeurt; een
  uitleg- of leesopdracht kost in werkelijkheid 150k–800k, omdat de cache bij elke ronde de hele context opnieuw leest
  (88 % van de tokens van de gemeten beurten is cache lezen).
- **Spreiding.** Dezelfde opdracht verschilt tot een factor vijf tussen runs (M06 160k–826k, S01 280k–611k). Run 2 is
  1,8M goedkoper dan run 1, deels doordat F02 en F04 daar misroutes zijn.
- **De accountstand** was 671.997 vóór run 1 en 6.694.955 erna: een verschil van 6.022.958, gelijk aan de som van de
  `meting`-events. Daarna is het budget twee keer gereset: om 19:42:56 UTC door de hoofdsessie (tijdens S04 in run 2) en
  een tweede keer tijdens M01 in run 3 (niet door de hoofdsessie). `delta_account` klopt in die twee regels niet.

## Wat dit betekent voor de volgende rondes

- **A2** meet tegen de tien enkelvoudige opdrachten: mediaan 38,6k tokens en 14,3 s, en per opdracht de drie waarden
  hierboven. Bij E03, E08 en E09 is de spreiding zo groot dat één run geen uitspraak toelaat.
- **De vervolgopdrachten** horen bij A2. F04 en F05 werken nu (behalve de misroute in run 2); F01, F02 en F03 niet.
- **De misroute naar *werkgebied samenstellen*** in run 2 is een fout van de huidige routering, los van ADR-016.
- **De opzet maakt de vervolgopdrachten duur.** Voor een ronde die alleen de vervolgbeurt wil meten, is 3,6M aan opzet
  veel; een goedkopere opzet vraagt een wijziging van de set en maakt de rondes onvergelijkbaar met deze.
