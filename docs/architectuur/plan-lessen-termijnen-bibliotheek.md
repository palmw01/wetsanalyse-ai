# Plan: lessen uit de begrippen- en afleidingsregelbibliotheek van Termijnen

24 nov 2026. Status: **concept, ter bespreking**. Analyse en voorstel; er is geen code gewijzigd.

Dit plan legt gevalideerd praktijkwerk naast de methode en naast Lex. Het vult
[`plan-lessen-e2e-termijnen.md`](plan-lessen-e2e-termijnen.md) aan: dat plan trok lessen uit wat een agentteam mét Lex
deed, dit plan uit wat een team van juristen en analisten zónder Lex opleverde over hetzelfde onderwerp.

> **Over het materiaal.** De drie exports zijn van derden en staan niet in deze repo. Dit document beschrijft ze in
> eigen woorden, met een paar namen als voorbeeld. De ruwe vergelijkingstabellen, met de letterlijke namen, staan
> buiten de repo (zie §8).

## Samenvatting

- **Het praktijkwerk is een keten van kleine regels.** Voor vijf bepalingen (Awb 4:86 lid 2, IW 1990 art. 9 lid 1 en 5,
  Leidraad Invordering 9.1 en 9.5) legde het team 171 markeringen, een veertigtal begrippen en 26 afleidingsregels vast (25 met een eigen pagina voor dit traject).
  Elke regel leidt één begrip af, vaak in één of twee regels tekst, en bijna elke voorwaarde is zelf weer de uitkomst van
  een andere regel.
- **Lex heeft over dezelfde bepalingen 6 regels en mist ruim 40% van de begrippen.** Van 39 vergelijkbare begrippen
  heeft het werkgebied Termijnen op acceptatie er 13 gelijkwaardig, 9 anders gesneden en 17 niet. Wat ontbreekt, is
  bijna steeds hetzelfde soort begrip: een ja/nee-kenmerk, een tussenresultaat of een kalenderwaarde.
- **De oorzaak zit in vier plekken van de keten**, niet in losse gevallen:
  1. een voorwaarde blijft in Lex tekst in een geval, terwijl de praktijk er een begrip met een eigen regel van maakt;
  2. de rekenvoorbeelden in beleidsregels zijn in Lex vrijwel geheel afgewezen, terwijl de praktijk daar zeven
     hulpregels uit haalt;
  3. een begrip in Lex heeft geen klasse en geen waardebereik, terwijl de bibliotheek die bij elk begrip voert;
  4. de regeltaal van Lex kent geen herhaling per termijn, geen vaste waarde uit een opsomming en geen peildatum.
- **Op drie punten doet Lex juist meer dan de praktijk**: operatorbegrippen (7), begrippen voor rechtsbetrekkingen
  (ongeveer 12) en een regelbegrip als begrip. De methode vraagt ze; de bibliotheek heeft ze niet. Dat is geen fout van
  Lex, wel een vraag aan de eigenaar (§7).
- **Het voorstel**: eerst meten tegen dit materiaal (een lokale referentieset voor begrippen en regels, §6), dan drie
  wijzigingen zonder gedragsverandering (klasse en waardebereik op het begrip, de voorbeeldtabel per regel, de
  bibliotheekvelden), en daarna de wijzigingen die het gedrag van Lex raken en een meting vragen. Wat aan R5 van het
  afleidingsregelsplan raakt, staat er als voorstel bij en wacht op het sein van de eigenaar.

## 0. Wat er gelezen is, en drie kanttekeningen

Gelezen, volledig via een omzetting naar platte tekst en per veld uitgelezen:

- de **afleidingsregelbibliotheek**: 32 regelpagina's, waarvan 26 van het traject Termijnen en 6 van Verrekenen;
- de **begrippenbibliotheek**: 173 begrippagina's uit zes trajecten, waarvan 36 met het traject Termijnen in de kop
  en nog een handvol gedeeld met andere trajecten;
- de **wetsanalyse zelf** (hoofdvraag 1, termijnstructuur en invorderbaarheid): activiteit 1 tot en met 4, het
  werkbestand van activiteit 3, en een pagina met door een taalmodel voorgestelde definities "ter inspiratie".
  Activiteit 5 verwijst alleen naar een bijlage, activiteit 6 is leeg.

Van Lex: het werkgebied *Termijnen* op acceptatie (revisie 37, gelezen 24 nov 2026 via de acceptatie-MCP): het dossier,
90 begrippen, 9 regels, de open punten, en de annotatie van de vier bepalingen die beide analyses delen.

Drie kanttekeningen, die de vergelijking begrenzen:

1. **De analysevraag verschilt.** De praktijk beantwoordt de initiële registratie (aantal termijnen, termijnbedragen,
   begindatum invorderbaar). Het werkgebied in Lex vraagt naar de verwerking van een negatieve voorlopige aanslag, met
   de termijnstructuur als vierde deelvraag. De vergelijking gaat daarom alleen over de vier gedeelde bepalingen en de
   begrippen en regels die daarop rusten. Awb 4:86 is in Lex geen bron.
2. **Het werkgebied in Lex is geen mensenwerk.** De begrippen en regels daar zijn opgesteld en geaccordeerd door het
   agentteam van de e2e-proef (zie [`afleidingsregels-termijnen-team.md`](afleidingsregels-termijnen-team.md)), onder
   het account van de eigenaar. Een verschil zegt dus iets over Lex, de skill en de briefing van dat team samen.
3. **De koppeling tussen de twee is met de hand gelegd**, op naam en definitie, en niet door een jurist beoordeeld. De
   aantallen zijn een orde van grootte, geen meting.

## 1. Het praktijkmateriaal

### 1.1 De afleidingsregel

Elke regel is één pagina met vaste velden:

| veld | inhoud |
|---|---|
| naam | gebiedende wijs: "bepaal" gevolgd door de naam van het begrip dat de regel afleidt |
| afleidingsregel | de regeltekst, met elke begripsnaam als verwijzing naar het begrip |
| eigenaar | het organisatieonderdeel dat de regel beheert |
| formulering uit primaire juridische bron | het lid of de alinea, met de dragende woorden vet |
| klasse | altijd *Afleidingsregel* |
| interpretatie | wat de regel toevoegt aan de tekst (bijna altijd leeg) |
| gerelateerde begrippen | (bijna altijd leeg: de verwijzingen in de regeltekst doen het werk) |
| opmerkingen | het gesprek van het team: voorstellen, tegenwerpingen, besluiten met datum |
| status | "afgestemd in werksessie" met een datum |
| voorbeelden | een tabel met genummerde gevallen (zie hieronder) |

Wat opvalt:

- **Eén regel, één uitvoer, meer gevallen.** Een regel met varianten herhaalt de kop per geval ("wordt berekend als …
  indien …", "wordt gesteld op … indien …"), met de voorwaarden als lijst onder EN of OF. Dat is dezelfde keuze als
  Lex maakte (één regel per uitvoer, als beslistabel; `references/afleidingsregels.md`).
- **De regels zijn klein.** Van de 25 regels met een eigen pagina voor dit traject hebben er 19 één uitkomst met
  hoogstens twee voorwaarden. Voorbeelden van de korrel:
  een regel die alleen het jaartal uit een datum haalt, een regel die zegt wanneer een jaar een schrikkeljaar is, een
  regel die een termijn de *enige* noemt als het aantal termijnen één is.
- **Een voorwaarde is bijna altijd een begrip.** "Is gedagtekend in november of eerder" is geen zinsdeel in een
  voorwaarde, maar een ja/nee-begrip met een eigen regel. De grote regels lezen daardoor als een opsomming van
  uitkomsten van kleinere regels.
- **De taal is half formeel.** Vaste wendingen (wordt berekend als, wordt gesteld op, is … indien), EN en OF in
  hoofdletters, haakjes voor nesting, vaste waarden tussen aanhalingstekens ('december', 'voorlopige aanslag'),
  rekenen met datums (plus 1 dag, min 1 dag, plus n maanden), een ondergrens ("met een minimum van") en een
  **herhaling**: bepaal voor de eerste en elke volgende termijn, tot het aantal termijnen is bereikt.
- **Een peildatum** is invoer van de twee regels die zeggen of iets invorderbaar *is*, zonder dat er een begrip voor is.
- **Beleid is bron.** Tien regels rusten alleen op de Leidraad, vaak op één woord in een rekenvoorbeeld ("het
  jaartal", "een schrikkeljaar").
- **De voorbeeldtabel** staat bij alle 25 regels: kolommen zijn genummerde gevallen, rijen zijn eerst de
  invoerbegrippen met een waarde, dan de vraag of de invoer juist is, dan de uitvoer als voorspelling, dan de vraag of
  die voorspelling juridisch juist is. Er staan bewust ook gevallen met onmogelijke invoer in, gemarkeerd als niet van
  toepassing. De pagina van activiteit 4 bundelt die tabellen en noemt ze uitdrukkelijk voorbeelden, geen
  risicodekkende testgevallen.

### 1.2 Het begrip

Vaste velden: naam, definitie, eigenaar, formulering uit de primaire juridische bron, **klasse**, **waarde**,
interpretatie, gerelateerde begrippen, opmerkingen (soms een tweede vak voor de gegevensanalyse) en status. Bovenaan
staat in welke trajecten het begrip wordt gebruikt.

- **Klasse.** Over de hele bibliotheek: Variabele 78, Rechtsobject 38, Parameter 19, Rechtssubject 18, Tijdsaanduiding 5,
  Rechtsfeit 1, leeg 14. Er is geen enkel operatorbegrip en geen begrip voor een rechtsbetrekking.
- **Waarde** is het waardebereik: Boolean (17 keer, waarvan 13 in Termijnen), datum, een bedrag met het aantal decimalen en de ondergrens, een
  getal, "1 t/m 31", een opsomming van toegestane waarden. Bij een parameter staat hier de waarde zelf ("6 weken"),
  dus niet in de definitie.
- **De naam** van een kenmerk noemt het object waar het bij hoort: het kenmerk gevolgd door de naam van het object, en
  die objectnaam draagt zelf het domein (de aanslag *in de invordering*, tegenover die in de heffing). Het team hernoemde
  een begrip toen bleek dat het niet alleen voor voorlopige aanslagen gold.
- **Een ja/nee-begrip** heeft een definitie die begint met "situatie waarin …". Het team besloot uitdrukkelijk géén
  voorvoegsel ("is", "indicator") te gebruiken, na een afweging met de leesbaarheid van de latere regels.
- **Tussenresultaten zijn begrippen.** Bij 13 van de 36 Termijnen-begrippen zegt de pagina dat het de uitkomst van een
  regel is. Het bronveld is bijna altijd gevuld, maar bij zo'n afgeleid begrip is dat het lid waarin de regel staat of
  één woord in de Leidraad, niet een eigen formulering.
- **De definitie blijft dicht bij de bron waar die er is**, en wordt herschreven waar de wet stroef is; de
  wetsdefinitie staat dan in het bronveld en de afwijking in *interpretatie*.
- **Interpretatie is een eigen veld.** Voorbeeld: een belastingsoort die de wet niet noemt maar die het team toch onder
  de bepaling brengt, met de reden en de verwijzing naar activiteit 5.
- **Voorbeelden** met goed/fout en een reden staan er voor twee begrippen (drie die eronder vallen, drie die er net
  buiten vallen), nog "ter review".

### 1.3 De wetsanalyse

- **Activiteit 1**: een hoofdvraag in de vorm van een opdracht ("bepaal …, zodanig dat …"), vijf deelvragen met een
  categorie, een praktijkvoorbeeld uit het bestaande systeem plus zes uitgerekende scenario's, en een bronnentabel met
  per bepaling de categorie (begrip, verklarend) en de deelvragen. Afgevallen bepalingen blijven doorgehaald staan.
- **Activiteit 2**: per lid of alinea een tabel met een rij per klasse (zestien rijen: de paren variabele/waarde,
  parameter/waarde en delegatie/invulling staan apart), de letterlijke formuleringen, een toelichting, een status
  (to do, concept, definitief) en een afbeelding van de gemarkeerde tekst.
  - **Veel overlap.** Dezelfde woorden staan onder drie of vier klassen: de hele zin als afleidingsregel, een deel als
    voorwaarde, daarbinnen variabelen, een parameter en zijn waarde, en de operatoren.
  - **Operatoren zijn de grootste klasse** (39 van 171), ook kleine woorden als "na", "of", "dan", "telkens".
  - **Parameter én tijdsaanduiding.** "Zes weken" staat onder Parameter, Parameterwaarde en Tijdsaanduiding.
  - **Rechtssubjecten zijn impliciet**: niet gemarkeerd, wel in de toelichting genoemd met waaruit ze volgen.
  - **Rekenvoorbeelden zijn geannoteerd**: de drie alinea's van Leidraad 9.5 leveren 77 markeringen, de meeste van
    alle bepalingen.
  - De toelichting nummert de afleidingsregels en variabelen en zegt welke voorwaarde bij welke regel hoort. Dat is de
    samenhang van deelactiviteit 2c, in woorden.
- **Activiteit 3** begint met een werkbestand: tabellen per klasse met *klasse, gemarkeerde tekst, vindplaats,
  begripsnaam, toelichting*. Alle formuleringen met dezelfde betekenis staan in één rij met één begripsnaam.
  - Het werk gaat in een vaste volgorde: eerst rechtssubject, rechtsobject, variabele, parameter en tijdsaanduiding;
    daarna de regels voor rechtsfeiten, afleidingsregels, rechtsbetrekkingen en voorwaarden.
  - **De klasse verschuift bij het maken van het begrip.** De drie soorten voorlopige aanslag zijn in activiteit 2
    rechtsobject; in activiteit 3 worden het ja/nee-variabelen, omdat ze de uitkomst van een regel zijn. Vier
    parameter-markeringen zijn doorgehaald met "is geen parameter, onderdeel van de afleidingsregel".
  - De regels staan er eerst in natuurlijke taal met een RegelSpraak-vorm ernaast; die tweede vorm verhuisde later naar
    activiteit 6.

### 1.4 De keten

Wettekst → markering per klasse → werkbestand (formulering naar begripsnaam) → begrip in de bibliotheek → regel in de
bibliotheek die begrippen verbindt → voorbeeldtabel → validatie. Elke stap verwijst terug: de regel citeert het lid met
de dragende woorden vet, het begrip citeert zijn formuleringen, het werkbestand noemt de vindplaats.

## 2. Naast de methode

Vergeleken met de skill (`.claude/skills/wetsanalyse/`) en met wat
[`plan-lessen-e2e-termijnen.md`](plan-lessen-e2e-termijnen.md) §0 uit het boek, de Handleiding en de Leidraad vastlegde.
De originelen zelf zijn voor dit plan niet opnieuw gelezen (zie §9).

**Waar de praktijk de methode volgt, en de skill dat ook zegt**

- Eén regel per afgeleid begrip, met een naam die met het werkwoord begint (`references/afleidingsregels.md`).
- Een tussenresultaat krijgt een begrip, ook zonder eigen formulering (`references/begrippen.md`, *Begrippen*).
- Een parameterwaarde hoort niet in de definitie van de parameter.
- Een begrip wordt hergebruikt voor elke formulering met dezelfde betekenis; het werkbestand is daar het bewijs van.
- Interpretaties die de tekst open laat, worden benoemd en naar activiteit 5 verwezen.
- Voorbeelden toetsen een regel, met een grensgeval erbij.

**Waar de praktijk verder gaat dan de skill beschrijft**

| onderwerp | praktijk | skill |
|---|---|---|
| ontleding in hulpregels | elke voorwaarde die iets afleidt, wordt een eigen regel met een eigen begrip, tot en met kalenderfeiten | noemt tussenresultaten, maar zegt niet dat een samengestelde voorwaarde een eigen regel wordt |
| ja/nee-begrip | vaste vorm: definitie "situatie waarin …", waardebereik Boolean, geen voorvoegsel | geen vorm voor een ja/nee-begrip |
| waardebereik | bij elk begrip waar het kan | "een begripstype of JAS-duiding stel je niet voor" (`references/begrippen.md`) |
| klasse op het begrip | bij elk begrip, en ze mag afwijken van de klasse van de markering | de klasse hoort bij de markering; op het begrip is het een open besluit (B8 in `plan-begrip-per-formulering.md`) |
| voorbeeldtabel | invoer en uitvoer per begrip, met een oordeel over de invoer én over de uitkomst | één zin per voorbeeld (`references/begrippen.md`, *De vorm van een voorbeeld*) |
| regeltaal | herhaling per termijn, vaste waarden, datumrekenen, ondergrens, peildatum | taalpatronen zonder herhaling of vaste waarde |
| rekenvoorbeeld in beleid | wordt geannoteerd en draagt hulpregels | niet genoemd |

**Waar de praktijk afwijkt van de skill**

| onderwerp | praktijk | skill | wie volgt het boek? |
|---|---|---|---|
| operatorbegrip | geen enkel, bij 39 operator-markeringen | een operator krijgt een begrip dat je hergebruikt | de skill (M01 h.3 stap 3b), volgens `plan-lessen-e2e` §0 |
| begrip voor een rechtsbetrekking | geen; het werkbestand zegt dat dit later komt | een begrip met de handeling vooraan | de skill; de praktijk is hier niet af |
| regelbegrip | de regel staat in een eigen bibliotheek, niet als begrip | eerst een begrip voor de regel, dan de regel | de skill |
| termijn als parameter | "zes weken" is parameter, parameterwaarde én tijdsaanduiding; het begrip is een parameter | "een termijn is één Tijdsaanduiding, geef hem niet ook een Parameter" (`references/markeringslijst.md`) | open: de praktijk kiest voor het regelmodel de parameter |
| naam van de regel | "bepaal …" | "bepalen …" | een vormkeuze |
| rechtssubject | alleen impliciet, in de toelichting | markeren waar de tekst het noemt | geen verschil: de tekst noemt er hier geen |

De afwijking bij de termijn heeft gevolgen: wie "zes weken" alleen als tijdsaanduiding markeert, heeft geen parameter
om in de regel te gebruiken. `tools/graph-qa/eval/extern_dossier.py` vangt dit bij het meten al op (een
tijdsaanduiding met subtype *verbijzondert parameter* dekt een parameter-referentie), maar in de regel zelf blijft het
verschil bestaan.

## 3. Naast Lex

### 3.1 Aantallen

**Markeringen** (praktijk → Lex actief, Lex totaal met afgewezen):

| bepaling | praktijk | Lex actief | Lex totaal |
|---|---|---|---|
| IW 9 lid 1 | 14 | 9 | 9 |
| IW 9 lid 5 | 34 | 31 | 40 |
| Leidraad 9.1 | 32 | 17 | 20 |
| Leidraad 9.5 | 77 | 18 | 67 |

De verdeling over de klassen verschilt sterk. In de praktijk is 23% operator en 13% parameter of parameterwaarde; in het
hele werkgebied van Lex is dat 6% en 1%. Lex heeft naar verhouding veel meer rechtsobjecten (31% tegen 10%).

**Begrippen**: van 39 vergelijkbare begrippen heeft Lex er 13 gelijkwaardig, 9 anders gesneden en 17 niet. Van de 17:
acht ja/nee-begrippen, vijf kalender- of telwaarden, twee datums rond *invorderbaar*, één parameter en één opsomming.

**Regels**: van de 26 regels hebben er drie een directe tegenhanger (aantal termijnen, termijnbedrag, vervaldag). Vijf
regels over vervaldatum en begindatum invorderbaar vallen in Lex samen in één regel met vier gevallen. Achttien
ontbreken: zes die een aanslag indelen, zeven kalenderregels, drie over termijnnummer en enige of laatste termijn, en de
twee die zeggen of iets invorderbaar is.

**Alleen in Lex**: zeven operatorbegrippen, ongeveer twaalf begrippen voor een rechtsbetrekking en zeven actieve
regelbegrippen. De rest van het verschil komt uit de bredere analysevraag.

### 3.2 Sprekende voorbeelden

1. **Het moment van invorderbaarheid.** De praktijk onderscheidt de uiterste dag van betaling en de dag erna, waarop de
   aanslag invorderbaar wordt, met een regel die de ene uit de andere afleidt (één dag verschil). Lex heeft één begrip
   *vervaldag* met een definitie die beide momenten in één zin noemt. De hoofdvraag van de praktijk (de begindatum
   invorderbaar) heeft in Lex dus geen eigen begrip en geen regel. In IW 9 lid 5 is de markering van "invorderbaar" als
   variabele afgewezen.
2. **De soorten aanslag.** De praktijk maakt van "een voorlopige aanslag in de inkomstenbelasting" een ja/nee-begrip
   met een regel op twee kenmerken (de soort aanslag en de belastingsoort), en daarboven één samengesteld begrip voor
   alle aanslagen die onder lid 5 vallen. Lex heeft de losse objecten als begrip en schrijft de combinatie als voorwaarde
   in het eerste geval van de regel voor het aantal termijnen. Een tweede regel die dezelfde groep nodig heeft, moet die
   voorwaarde herhalen.
3. **Het rekenvoorbeeld in de Leidraad.** In Leidraad 9.5 stelde de keten "het jaartal" en "een schrikkeljaar" voor als
   variabele; bij de beoordeling zijn ze afgewezen, net als 47 andere markeringen in die bepaling. De praktijk maakt
   er begrippen van en bouwt er de kalenderregels op.
4. **De zes weken.** Praktijk: één parameterbegrip met de waarde in het waardeveld. Lex: een begrip voor de termijn en
   een apart begrip voor de waarde. Dat volgt de skill, maar het kost twee begrippen waar de praktijk er één heeft.
5. **De afronding.** De praktijk rekent het termijnbedrag per termijn uit over wat er nog over is, en rondt naar boven
   af, zodat het restant in de laatste termijn landt. Dat is een keuze van het team, vastgelegd in de regel, het
   waardebereik en zes scenario's. In Lex staat dezelfde vraag terecht als open punt *ontbrekend uitvoeringsbeleid*; de
   regel deelt alleen. Hier doet Lex wat de methode vraagt, en laat de praktijk zien hoe het punt daarna wordt gesloten.

### 3.3 Oorzaken in de keten

| nr | verschil | oorzaak | waar |
|---|---|---|---|
| O1 | ja/nee-begrippen en indelingsregels ontbreken | een voorwaarde is in het regelmodel een tekst met markeringen, of een verwijzing naar een geval van een andere regel; er is geen stap die van een voorwaarde een begrip met een eigen regel maakt, en geen signaal dat het ontbreekt | `api/app/regel_contracts.py` (`Voorwaarde`); de gatenlijst in `references/afleidingsregels.md` kent `voorwaarde_zonder_markering`, niet "voorwaarde zonder begrip" |
| O2 | kalender- en hulpregels ontbreken | de markeringen in de rekenvoorbeelden zijn afgewezen; zonder markering geen begrip (terecht: `begrip_store` weigert een begrip zonder passage) en dus geen regel. De skill zegt niets over de rol van een voorbeeldalinea | beoordeling van de laag Leidraad 9.5; `references/markeringslijst.md` |
| O3 | geen waardebereik, geen klasse op het begrip | het begripmodel heeft naam, alternatieve termen, definitie, uitleg, toelichting en voorbeelden, en niets anders | `api/app/begrip_contracts.py` (`BegripInhoud`); besluit P15, heroverweging B8 |
| O4 | weinig parameters | de skill verbiedt de dubbele markering, en de keten sluit de parameter uit van de begrippen | `references/markeringslijst.md`; `tools/graph-qa/agent/begrippen_pipeline/geen_begrip.yaml` (klassen *Operator* en *Parameter en parameterwaarde*; B4 haalt de parameter eruit) |
| O5 | de grote regels kunnen niet precies worden opgeschreven | een term in een uitkomst is een begrip, een operator of vrije tekst; er is geen vaste waarde, geen herhaling over een verzameling en geen invoer zonder begrip | `api/app/regel_contracts.py` (`Term`, `Geval`, `Invoer`); `api/app/regeltekst.py` |
| O6 | voorbeelden zijn een lijst zinnen | het model kent waarden per begrip en een oordeel, maar geen oordeel over de invoer en geen tabelvorm; de volledige reeks is in het plan uitgesteld | `api/app/regel_contracts.py` (`RegelVoorbeeld`); `plan-afleidingsregels-in-lex.md` §13.2, "Later" |
| O7 | korte, kale namen | de naamrichtlijn zegt "zo kort als kan" en "dicht bij de wet"; de praktijk noemt het object in de naam om homoniemen over trajecten heen te voorkomen | `references/begrippen.md`, *De naam* |
| O8 | geen plek voor eigenaar, werksessie en discussie | Lex heeft wie en wanneer accordeerde, een toelichting en open punten, maar geen eigenaar en geen gesprek per begrip | `BegripInhoud`; ADR-006 voor het gebruik over werkgebieden heen |

O1 en O2 verklaren samen het grootste deel van de ontbrekende begrippen en regels: de ja/nee-begrippen met hun
indelingsregels (O1) en de kalenderwaarden met hun hulpregels (O2).

## 4. De lessen

1. **Een regel is pas af als elke voorwaarde een begrip is.** De praktijk schrijft geen zinsdelen in een voorwaarde. Wat
   getoetst wordt, heeft een naam, een waardebereik en een eigen regel. Zo ontstaat een keten die een ontwikkelaar regel
   voor regel kan bouwen en een jurist regel voor regel kan nalopen.
2. **Klein is de norm.** De meeste regels passen op één of twee regels tekst. Een regel met vier gevallen en geneste
   voorwaarden is de uitzondering, en ook die bestaat uit verwijzingen naar kleine regels.
3. **Beleid en rekenvoorbeelden dragen regels.** De Leidraad levert de helft van de regels. Een voorbeeldalinea is geen
   norm, maar wel de plek waar de woorden staan voor wat de uitvoering moet kunnen uitrekenen.
4. **Een begrip heeft een klasse en een waardebereik.** Zonder waardebereik is een voorbeeld niet te toetsen en een regel
   niet te bouwen. De klasse van het begrip mag verschillen van die van de markering: wat de tekst als object noemt,
   kan in de regels een ja/nee-kenmerk zijn.
5. **Valideren gebeurt met een tabel per regel.** Invoer en uitvoer per begrip, met een oordeel over allebei, en met
   opzet ook onmogelijke invoer. Het is licht, het staat bij de regel, en het is het bewijs achter "afgestemd".
6. **De naam draagt het object en het domein.** Dat maakt namen lang, maar het voorkomt dat één woord in twee trajecten
   iets anders betekent. De bibliotheek is gedeeld over zes trajecten; de naam is daar de sleutel.
7. **Het gesprek hoort bij het begrip.** Voorstellen, tegenwerpingen en het besluit met datum staan op de pagina. Wie
   later twijfelt, leest waarom het zo is.
8. **De praktijk is niet in alles het voorbeeld.** Operatorbegrippen, rechtsbetrekkingen en rechtsfeiten ontbreken, één
   bepaling staat nog op "to do", en enkele definities zijn een concept. Lex hoeft dat niet over te nemen.

## 5. Het verbeterplan

Elke stap begint, zoals altijd, met een korte toets of dit de beste verbetering is. De voorstellen zijn generiek: geen
enkel voorstel kent een bepaling, een begrip of een regel uit Termijnen.

### Prioriteit 1: meten, en wat geen gedrag van Lex verandert

**V1 · Een lokale referentie voor begrippen en regels** (graph-qa `eval/`; M; geen meting nodig, het ís de meting)
- Probleem: er is geen maat. De vergelijking in dit plan is handwerk (§0, kanttekening 3).
- Oplossing: zie §6. Eerst een nulmeting op het bestaande werkgebied, zonder Lex te laten draaien.
- Volgorde: eerst. Alles hierna wordt hieraan afgemeten.

**V2 · Klasse en waardebereik op het begrip** (api, projectie, frontend; M; geen meting)
- Probleem: O3. De bibliotheek voert beide bij vrijwel elk begrip; Lex bij geen enkel.
- Oplossing: neem B8 uit `plan-begrip-per-formulering.md` nu, in twee delen.
  - De **klasse** wordt afgeleid uit de dragende markeringen en getoond op de kaart. Wijkt het begrip af (object in de
    tekst, kenmerk in de regels), dan kiest de analist een andere klasse, met een reden; dat geeft een signaal, geen
    weigering.
  - Het **waardebereik** is een optioneel, gestructureerd veld: de soort (ja/nee, datum, bedrag, aantal, duur, tekst,
    opsomming) en waar het past de eenheid, het aantal decimalen, de grenzen of de toegestane waarden. Het is hetzelfde
    veld als D5 van het afleidingsregelsplan.
- De NL-SBB-projectie houdt de klasse als relatie naar het JAS-topbegrip; het waardebereik gaat mee als eigen
  eigenschap buiten de kern van NL-SBB (ADR-003 krijgt een aanvulling).
- Vraagt: het besluit van de eigenaar over P15 (§7, vraag 1).

**V3 · De voorbeeldtabel per regel** (api, frontend, rapport; S tot M; geen meting)
- Probleem: O6. Het model kan het bijna; de vorm en twee oordelen ontbreken.
- Oplossing:
  - een voorbeeld is een kolom: een waarde per invoerbegrip en per uitvoerbegrip (het veld `waarden` bestaat);
  - twee oordelen in plaats van één: is de invoer mogelijk, en is de uitkomst juridisch juist; "niet van toepassing"
    is een geldige uitkomst van het eerste;
  - de regelkaart toont de voorbeelden als tabel met de gevallen als kolommen; de export houdt de lijstvorm;
  - met V2 toetst de api een waarde tegen het waardebereik van het begrip (een signaal bij een datum in een ja/nee-veld).
- Dit haalt een stuk van activiteit 4b naar voren uit "Later" in `plan-afleidingsregels-in-lex.md` §13.2. Het maken
  van voorbeelden door Lex blijft bij R5 en R6.

**V4 · Eigenaar en gesprek bij begrip en regel** (api, frontend; S; geen meting)
- Probleem: O8.
- Oplossing: een optioneel veld *eigenaar* op het begrip en de regel, en het gesprek als opmerkingen in de bestaande
  audit (wie, wanneer, tekst), zichtbaar op de kaart. De interpretatie heeft al een plek: een open punt van de soort
  *interpretatiekeuze* dat aan het begrip hangt. De kaart toont dat punt bij het begrip, met de gekozen lezing.
- Eerst toetsen of de bestaande toelichting en open punten niet al volstaan; zo ja, dan is dit alleen weergave.

### Prioriteit 2: wat de methodetekst of het gedrag van Lex raakt

**V5 · De skill beschrijft de ontleding in hulpregels en het ja/nee-begrip** (skill, references; S; meting alleen als de
tekst tussen de methodemarkers wijzigt)
- Probleem: de skill noemt tussenresultaten, maar niet de korrel die de praktijk laat zien (§2).
- Oplossing, in `references/afleidingsregels.md` en `references/begrippen.md`, buiten de methodemarkers:
  - een voorwaarde die zelf iets afleidt, wordt een eigen regel met een eigen begrip; de regel erboven verwijst ernaar;
  - de vorm van een ja/nee-begrip: definitie "situatie waarin …", waardebereik ja/nee, geen ontkenning en geen
    voorvoegsel in de naam;
  - een voorbeeldalinea in een beleidsregel is geen norm, maar kan de formulering leveren voor een begrip dat een regel
    nodig heeft; markeer wat een regel draagt;
  - de volgorde van activiteit 3a uit het werkbestand: eerst subjecten, objecten, variabelen, parameters en tijd, dan de
    regels.
- Vraagt: de antwoorden op vraag 2, 3 en 4 in §7. Wijzigt de regel over de termijn als parameter, dan raakt dat
  `references/markeringslijst.md` en de annotatieketen, en dat vraagt een meting.

**V6 · Het gat "voorwaarde zonder begrip"** (skill `regelgaten.json`, api; S; geen meting, het is een signaal)
- Probleem: O1. Niemand ziet dat een voorwaarde een zinsdeel is gebleven.
- Oplossing: twee nieuwe gaten bij het regelobject, uitgerekend in code zoals de bestaande:
  - `voorwaarde_zonder_begrip`: een voorwaarde verwijst naar geen geval van een andere regel en noemt geen invoerbegrip
    van de regel;
  - `voorwaarde_herhaald`: dezelfde markeringen dragen een voorwaarde in twee of meer regels; dan hoort er één regel
    onder die beide gebruiken.
- Een gat is een signaal en blokkeert het accorderen niet, zoals de andere.
- Dit deel kan los van R5: het rekent op regels die er al zijn.

**V7 · De regeltaal: vaste waarde, herhaling en peildatum** (api `regel_contracts`, `regeltekst`; M; geen meting)
- Probleem: O5. Ruim de helft van de praktijkregels gebruikt een vaste waarde, een herhaling, een peildatum of een
  bewerking op een datum, en past nu dus niet zonder vrije tekst.
- Oplossing, in het model en in de afgeleide regeltekst:
  - een term van de soort *waarde*: een toegestane waarde van een begrip met een opsomming (V2), of een getal met een
    eenheid;
  - *voor elke*: een regel die zijn uitvoer per element van een verzameling afleidt, met het begrip dat telt
    (`onderwerp_begrip_id` bestaat al als onderwerp; hier komt het begrip van de verzameling bij);
  - een ondergrens en bovengrens als operator met twee operanden;
  - een invoer die het moment van toepassen is (peildatum), als vast begrip in het generieke kader.
- Toets: de 26 regels van de referentie moeten erin passen zonder een term van de soort *tekst*. Dat is dezelfde maat
  als bij R1 (de set R1–R8).
- Grens: dit is geen RegelSpraak. Het blijft natuurlijke taal in een vast patroon.

**V8 · Voorbeeldalinea's in de annotatieketen** (graph-qa; M; **vraagt een meting**, ADR-010)
- Probleem: O2. In Leidraad 9.5 is 73% van wat de keten voorstelde afgewezen. Dat is veel beoordelingswerk, en de
  markeringen die de praktijk nodig had, gingen mee verloren.
- Oplossing: de keten herkent een voorbeeldzin (een concreet getal of een concrete datum als uitkomst, ingeleid door
  "bijvoorbeeld", "dus" of "dan houdt dat in dat") en geeft de markeringen daarbinnen een kenmerk *in een voorbeeld*.
  - De waarden zelf (een datum, een bedrag) worden niet meer als losse tijdsaanduiding of variabele voorgesteld.
  - De woorden die een kenmerk aanduiden (het jaartal, de laatste dag van de maand) blijven voorgesteld.
  - Het voorbeeld als geheel wordt aangeboden als voorbeeld bij de regel die het illustreert (V3), niet als norm.
- Meten: op de gedeelde bepalingen tegen de referentie (recall op variabele en parameter, en het aandeel afwijzingen),
  en daarna op een blinde bepaling met rekenvoorbeelden uit een andere regeling.
- Eerst nagaan waarom de markeringen zijn afgewezen: de beslissingen in de audit van die laag zijn voor dit plan niet
  gelezen (§9).

### Prioriteit 3: voorstel bij R5 en verder (staat op HOLD)

**V9 · Lex stelt hulpregels en hun begrippen voor** (graph-qa regels-agent, api; L; meting volgens bijlage A §7)
- Raakt R5 (`opstellen`, `volledigheidstoets`) en wacht op het sein van de eigenaar.
- Voorstel: de volledigheidstoets leest de gaten van V6 en stelt per gat voor: een begrip (naam uit de formulering,
  waardebereik ja/nee of de soort van de waarde) en een regel met de voorwaarde als enig geval. In code, zonder model;
  de naam volgt de richtlijn van V10.
- De referentie van V1 is hier de maat: hoeveel van de 18 ontbrekende regels komen als voorstel, en hoeveel voorstellen
  zijn onterecht.

**V10 · De naam noemt het object** (skill, begrippen-agent; S; meting als een modelstap de naam voorstelt)
- Probleem: O7.
- Voorstel: een signaal op de begripskaart als een kenmerk (klasse variabele of parameter, V2) in zijn naam het object
  niet noemt waar het volgens zijn relaties bij hoort. Geen automatische hernoeming. Voor een generiek begrip (ADR-006)
  weegt het signaal zwaarder.
- Vraagt: vraag 5 in §7.

### Volgorde

1. De eigenaar beantwoordt de vragen van §7 (ze bepalen V2, V5 en V10).
2. V1, met de nulmeting.
3. V2, V3 en V4 in één bundel: geen gedragsverandering van Lex, één keer testen en uitrollen.
4. V5 en V6 in één bundel (skill en signalen). Wijzigt de tekst tussen de methodemarkers, dan eerst een meting.
5. V7, met de 26 regels als toets.
6. V8, met een meting vóór en na.
7. V9 en V10 als R5 van start gaat.

V2, V3 en V7 raken `api/app/regel_contracts.py` of `begrip_contracts.py`: één schrijver tegelijk per bestand.

## 6. Dit materiaal als referentieset

Het materiaal blijft buiten de repo. De code die het leest en vergelijkt, staat er wel in en kent geen enkel pad. Dat is
de vorm die `tools/graph-qa/eval/extern_dossier.py` al heeft voor activiteit 2.

- **Inlezen.** Twee lezers naast de bestaande: één voor een begrippagina en één voor een regelpagina, elk naar een
  neutraal schema (naam, definitie, klasse, waardebereik, bron met artikel en lid, status; en voor een regel: uitvoer,
  gevallen, de genoemde begrippen als invoer, voorbeelden). De lezers krijgen een map als argument en draaien op
  onvertrouwde invoer: alleen de standaardbibliotheek, geen uitvoering van wat erin staat.
- **Waar het staat.** In `docs/acceptatie/lokaal/` (gitignored) of buiten de repo. In de repo komt alleen een manifest
  zonder inhoud: de naam van de set, de datum van de export, het aantal pagina's en een hash per bestand, zoals
  `docs/wetsanalyse/bronnen/manifest.json` dat doet voor de originelen van de methode.
- **Wat er gemeten wordt**, tegen een werkgebied op acceptatie (alleen lezen):
  1. *markeringen*: bestaat al (recall per klasse, strikt en ruim);
  2. *begrippen*: per referentiebegrip of er in het werkgebied een begrip is dat op dezelfde formuleringen rust. De
     koppeling gaat via de vindplaats en de gemarkeerde tekst uit het werkbestand, niet via de naam. Uitkomst: gedekt,
     anders gesneden (één begrip in Lex draagt formuleringen van meer referentiebegrippen, of omgekeerd), ontbreekt;
  3. *regels*: per referentieregel of er een regel is met een uitvoerbegrip dat in stap 2 aan de referentie-uitvoer is
     gekoppeld, en hoeveel van de invoerbegrippen overeenkomen;
  4. *voorbeelden*: de voorbeeldtabellen zijn invoer en verwachte uitkomst. Zodra een regel in Lex uitvoerbaar genoeg
     is opgeschreven (V7), kan een voorbeeld uit de referentie als voorbeeld bij de regel worden gezet en door een
     jurist beoordeeld. Lex rekent zelf niet.
- **Wat het niet is.** Eén analyse, geen gouden standaard: de set heeft eigen gaten (§4, les 8) en een andere
  analysevraag. De uitkomst is dekking en verschil, met een jurist die de verschillen beoordeelt
  (`docs/wetsanalyse/referentieset/adjudicatieprotocol.md`). Het is ook een **ontwikkelset**: wie de keten verbetert
  met dit materiaal voor ogen, meet daarna op iets anders. De vijf andere trajecten in de begrippenbibliotheek
  (waaronder verrekenen en invorderingsrente) zijn daarvoor de eerste kandidaten, zodra daar een werkgebied voor is.
- **In het meetlogboek** (`docs/architectuur/metingen/README.md`) komt per meting alleen de uitkomst in getallen, met
  de naam en de hash van de set, niet de inhoud.

## 7. Open vragen aan de eigenaar

1. **Klasse en waardebereik op het begrip (V2).** Mag het besluit van 13 nov 2026 (P15: een begrip draagt geen type)
   worden bijgesteld, met de klasse afgeleid uit de markeringen en het waardebereik als optioneel veld? De praktijk en
   B8 pleiten ervoor.
2. **Operatorbegrippen.** De praktijk maakt ze niet; het boek wel, en Lex nu ook. Blijven ze, of tellen ze niet meer mee
   in de dekking van een werkgebied?
3. **De termijn als parameter.** De praktijk markeert "zes weken" als parameter, parameterwaarde én tijdsaanduiding en
   maakt er één parameterbegrip van met de waarde in het waardebereik. De skill verbiedt de dubbele markering en maakt
   twee begrippen. Welke lijn volgt Lex?
4. **Hoe ver gaat de ontleding?** De praktijk maakt een regel voor het schrikkeljaar en voor de laatste dag van de maand.
   Is dat de norm voor Lex, of horen algemene kalenderregels in een gedeelde set die een werkgebied gebruikt zonder ze
   opnieuw te maken (het generieke kader van ADR-006)?
5. **De naam.** Volgt Lex de bibliotheek (het kenmerk met het object en het domein in de naam) of de huidige richtlijn
   (zo kort als kan)? En "bepaal" of "bepalen"?
6. **Het regelbegrip.** In de praktijk is een regel geen begrip. In Lex is het regelbegrip een begrip tussen de andere.
   Blijft dat zo, of krijgt het een eigen plek buiten de begrippenlijst?
7. **Vervaldag en begindatum invorderbaar.** De praktijk houdt ze uit elkaar, met een dag verschil. Is dat de lezing die
   in het werkgebied Termijnen moet komen? Dit is een inhoudelijke vraag voor de jurist, geen wijziging aan Lex.
8. **Mag de referentie breder?** De begrippenbibliotheek bevat vijf andere trajecten. Mogen die als blinde set dienen,
   en zijn daar de bijbehorende wetsanalyses van beschikbaar?

## 8. Waar het ruwe materiaal staat

Buiten de repo, op de machine van de eigenaar: de drie exports als platte tekst, de veldtabellen per pagina, wat
acceptatie teruggaf, en de vergelijkingstabellen met de letterlijke namen (begrip voor begrip, regel voor regel,
markeringen per bepaling). Het pad staat in het bericht bij de PR-sessie, niet hier.

## 9. Wat niet is nagegaan

- **De originelen van de methode** (het boek, de Handleiding, de Leidraad) zijn voor dit plan niet opnieuw gelezen. §2
  steunt op de skill en op `plan-lessen-e2e-termijnen.md` §0.
- **Waarom de markeringen in Leidraad 9.5 zijn afgewezen.** De beslissingen in de audit van die laag zijn niet gelezen.
- **De afbeeldingen** in de export (de gemarkeerde teksten van activiteit 2 en de schermafdrukken van de regels in de
  regeltaal van het team) zijn niet bekeken; alleen de tabellen en de tekst.
- **De bijlagen** waar activiteit 1 en 5 naar verwijzen, zitten niet in de export.
- **De regels van Lex in detail.** Van de negen regels zijn naam, uitvoer, soort, het aantal gevallen en de open punten
  gelezen, niet elke voorwaarde.
- **De koppeling van begrippen** is op naam en definitie gelegd, niet op de formuleringen waarop ze rusten (dat is wat
  V1 moet gaan doen).
- **Wat de keten zou voorstellen op een schoon werkgebied.** Er is geen run van Lex gestart; de vergelijking gaat over
  wat er op acceptatie ligt, na beoordeling door het agentteam.
- **De vijf andere trajecten** in de begrippenbibliotheek zijn alleen geteld, niet vergeleken.
