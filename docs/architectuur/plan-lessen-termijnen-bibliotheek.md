# Plan: lessen uit de begrippen- en afleidingsregelbibliotheek van Termijnen

24 nov 2026. Status: **concept**; de eigenaar heeft de acht vragen beantwoord (§7). Analyse en voorstel. De methode-skill is aangevuld buiten de
methodemarkers (§5a); wat het gedrag van Lex raakt, staat als voorstel in §5b. Daarvan is M2 (V8) gebouwd (#1856) en gemeten,
zonder model (24 nov 2026) en met het model (25 nov 2026).

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
| termijn als parameter | "zes weken" is parameter, parameterwaarde én tijdsaanduiding; het begrip is een parameter | "een termijn is één Tijdsaanduiding, geef hem niet ook een Parameter" (`references/markeringslijst.md`) | het boek (M01 h.4 §12): één Tijdsaanduiding die een parameter verbijzondert en diens relaties overneemt; zie M3 (bijgesteld 24 nov 2026) |
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
- *Gebouwd (24 nov 2026):* `tools/graph-qa/eval/extern_bibliotheek.py` met tests, het manifest in
  `docs/wetsanalyse/referentieset-bibliotheek/`, en de nulmeting hieronder.
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

**V5 · De skill beschrijft de ontleding in hulpregels en het ja/nee-begrip** (skill, references; S). *Het deel buiten
de methodemarkers is in deze PR doorgevoerd, zie §5a; wat een meting vraagt, staat in §5b.*
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
- Eerst nagaan waarom de markeringen zijn afgewezen: gedaan (24 nov 2026, zie hieronder).
- **Nagegaan** (audit van de laag 9.5, acceptatie, alleen lezen): van de 50 afwijzingen hebben er 42 de reden
  "Rekenvoorbeeld, niet de regel", 6 "dubbel" en 2 "is gesteld op". De 42 liggen alle in de vier voorbeeldzinnen; dat
  bevestigt de oorzaak. Maar het zijn niet vooral losse data: 12 data, 5 duren, 13 variabelen, 7 operatoren, 4
  voorwaarden of afleidingsregels en 1 rechtsobject. De jurist wees het voorbeeld als geheel af, ook het jaartal en het
  schrikkeljaar; dat was vóór de regel in de skill (§5a). Bedragen staan er niet in. De referentie markeert de duur in
  het voorbeeld als parameter, dus die laat de keten staan.
- **Gebouwd** (PR "Annotatieketen: een rekenvoorbeeld is geen norm maar wel bron", branch
  `claude/keten-rekenvoorbeelden-c83ceb`): `tools/graph-qa/agent/jas_pipeline/voorbeeld.py`, de reviewerzin, tests.
  Gemeten zonder model: `metingen/keten-rekenvoorbeelden-2026-11-24/`. Gemerged als #1856 (`a74c0041`).
- **Gemeten met het model** (25 nov 2026, `metingen/keten-rekenvoorbeelden-model-2026-11-25/`; één run, de keten zonder
  schrijfpad, het model van acceptatie): in 9.5 van 67 naar 46 voorstellen, waarvan 22 in een voorbeeldzin (was 42); de 22
  die wegvallen had de jurist alle afgewezen; alle 17 geaccordeerde of gecorrigeerde staan er nog; het aandeel afgewezen
  van 75% naar hoogstens 61%. IW 9 lid 1: geen voorbeeld, geen kenmerk, de 6 geaccordeerde blijven. 30.359 tokens. Blind:
  niet mogelijk (zie de meting).

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

## 5c. De nulmeting (V1, 24 nov 2026)

Het werkgebied Termijnen op acceptatie (revisie 37) tegen de referentie, zonder model en alleen lezend. Meetlogboek:
`docs/architectuur/metingen/README.md`. Het rapport zelf, met namen, staat lokaal.

| | referentie | gedekt | anders gesneden | zonder begrip | niet gemarkeerd | alleen op naam | ontbreekt |
|---|---|---|---|---|---|---|---|
| begrippen | 36 | 1 | 17 | 5 | 6 | 2 | 5 |
| waarvan ja/nee | 13 | 0 | 6 | 2 | 3 | 0 | 2 |

| | referentie | gevonden | anders gesneden | ontbreekt |
|---|---|---|---|---|
| regels | 25 | 2 | 3 | 20 |

Wat dit zegt:

- **Strenger dan de handvergelijking van §3.1**, en dat is bedoeld. Daar telde een begrip met dezelfde betekenis als
  gelijkwaardig (13 van 39); hier telt alleen een begrip dat op dezelfde formuleringen rust en niets anders draagt.
  "Anders gesneden" is de grootste groep: één begrip in Lex (*termijn*, *vervaldag*, *aantal termijnen*, *voorlopige
  aanslag*) draagt de formuleringen van twee tot vier begrippen uit de referentie. Dat is les 1 in getallen.
- **Zes formuleringen zijn niet gemarkeerd**, vooral in de rekenvoorbeelden van de Leidraad (les 3, V8), en vijf zijn
  gemarkeerd zonder begrip (V5, V6).
- **Van de regels zijn er twee op naam terug** (aantal termijnen, termijnbedrag). De drie "anders gesneden" vallen op
  *bepalen van de vervaldag* en *bepalen van het aantal termijnen*: de regels met meer gevallen waar de referentie
  kleine regels heeft.
- De analysevraag van het werkgebied is breder; de drie regels en ruim zestig begrippen die alleen in het werkgebied
  staan, gaan grotendeels over de verrekening en zeggen hier niets.

Dit is de maat waartegen V5 tot en met V9 gemeten worden: meer `gedekt`, minder `anders_gesneden` en `niet_gemarkeerd`,
meer regels `gevonden`, zonder dat de begrippen die alleen in het werkgebied staan onterecht verdwijnen.

## 5a. Wat in de skill is doorgevoerd

Alleen tekst buiten de methodemarkers. De secties tussen de markers (`agentrollen.md`, `nl-sbb-en-b1.md`,
`deelvragen-en-bronnen.md`) zijn byte-gelijk; in `tools/graph-qa/agent/methodepakket.py` veranderden alleen de hashes van
`SKILL.md` en `references/bronnen.md` en de hash van het pakket, geen sectietekst. De methodeversie blijft 3.0. De
generatoren zijn gedraaid (`--check` groen) en `tests/methode/` en `tests/poort/` slagen.

| wijziging | waar | de les waarop ze rust |
|---|---|---|
| *Ontleden in kleine regels*: een voorwaarde die iets afleidt wordt een eigen regel; een indeling is een regel; een deel van een waarde is een begrip; algemene hulpregels één keer; een regel per element; het moment van toepassen als invoer; een vaste waarde uit het waardebereik; twee momenten zijn twee begrippen | `references/afleidingsregels.md` | les 1 en 2 (§4); voorbeelden 1 en 2 (§3.2) |
| *Toetsen met een voorbeeldtabel*: kolom per geval, een oordeel over de invoer en over de uitkomst, met opzet een geval dat niet kan, de grenzen van elke vergelijking | `references/afleidingsregels.md`, `references/analyseprotocol.md` §5 | les 5 |
| *Wat de praktijk aan een begrip toevoegt*: de werklijst en de volgorde van 3a; de klasse kan verschuiven; de vorm van een ja/nee-begrip; het waardebereik; de naam van een kenmerk noemt zijn object; interpretatie apart; het gesprek hoort erbij | `references/begrippen.md` | les 1, 4, 6 en 7 |
| Een rekenvoorbeeld in de bron is geen norm, maar wel bron: markeer de woorden die een kenmerk aanduiden, niet de losse data; wijs zo'n markering niet af omdat het een voorbeeld is | `references/markeringslijst.md` | les 3; voorbeeld 3 (§3.2) |
| Twee rijen in de kwaliteitsrubriek: *Begrippen* en *Afleidingsregels* | `references/kwaliteit.md` | les 1, 4 en 5 |
| Voorbeeld 5: één regel ontleed in kleine regels, met een voorbeeldtabel (een eigen uitwerking van IW 9 lid 5, geen overname) | `references/voorbeelden.md` | les 1, 2 en 5 |
| Een zin bij werkstroom D en F, en drie veelgemaakte fouten | `SKILL.md` | les 1, 3 en voorbeeld 1 |
| M15 (het praktijkwerk als bron, lokaal) en P23 (wat eruit is overgenomen, en wat niet) | `references/bronnen.md` | herleidbaarheid |

**Bewust niet overgenomen** (de praktijk wijkt hier af van de methode, of de eigenaar moet kiezen, §7): geen
operatorbegrippen, geen begrip voor een rechtsbetrekking, "bepaal" in plaats van "bepalen", en de termijn als parameter
én tijdsaanduiding. De regel "een termijn is één Tijdsaanduiding" staat ongewijzigd in de skill.

**Het waardebereik.** De skill zegt dat je het vastlegt "in de toelichting, tot het platform een veld heeft". De
eigenaar heeft P15 bijgesteld (§7, besluit 1); met V2 wordt dat een veld en gaat die bijzin eruit.

## 5b. Voorstellen die het gedrag van Lex veranderen (niet doorgevoerd; vragen een meting, ADR-010)

Elk voorstel is uitgeschreven als toen → nu. Geen ervan staat in deze PR.

**M1 · De begrippen-agent kent de vorm van een ja/nee-begrip en het waardebereik**
(`references/nl-sbb-en-b1.md`, sectie `nl-sbb-taalniveau`; rol `begrippen`)
- Toen: de sectie beschrijft de vier velden (definitie, uitleg, toelichting, voorbeeld) en zegt niets over een begrip
  dat alleen waar of onwaar kan zijn.
- Nu, als extra zin na de beschrijving van de definitie: "Kan een begrip alleen waar of onwaar zijn, dan beschrijft de
  definitie de situatie waarin het waar is ('situatie waarin …'), zonder de regel die het afleidt en zonder
  ontkenning."
- Zodra V2 er is, een tweede zin: "Bij een variabele of parameter stel je het waardebereik voor uit de passages: ja/nee,
  datum, bedrag, aantal, duur of een vaste lijst."
- Meting: licht (één run), de begrippen van Termijnen als set, met de ja/nee-begrippen uit de referentie (V1) als
  toets: komt de definitie in de afgesproken vorm, en verslechtert geen andere definitie?

**M2 · De annotatieketen behandelt een rekenvoorbeeld als voorbeeld**
(`tools/graph-qa/agent/jas_pipeline/`: detectoren, en de prompts van `classificatie.py` en `review.py`, P20)
- Toen: een voorbeeldzin wordt gemarkeerd als elke andere zin. In Leidraad 9.5 leverde dat 67 voorstellen op, waarvan
  er 49 zijn afgewezen.
- Nu (gebouwd, 24 nov 2026): V8. Een stap na de fusie (`voorbeeld.py`) herkent de voorbeeldzin aan een inleiding met
  een datum of bedrag als gegeven, of aan een voorwaardelijke zin met een kalenderdatum als gegeven en als uitkomst;
  een datum of bedrag daarbinnen wordt niet voorgesteld, de normklassen vervallen, de rest krijgt het kenmerk *in een
  voorbeeld*; de reviewer krijgt de regel uit `references/markeringslijst.md` in één zin. Een duur valt er niet onder
  (in een voorbeeld noemt die de parameter).
- Gemeten zonder model (`metingen/keten-rekenvoorbeelden-2026-11-24/`): in 9.5 vallen 16 van de 50 afgewezen voorstellen
  weg (12 data, 3 voorwaarden, 1 afleidingsregel), 26 krijgen het kenmerk, en 0 van de 16 geaccordeerde wordt geraakt;
  op IW 9 lid 1 en 5 en Leidraad 9.1 verandert niets. De kandidaat-dekking op variabele en parameter tegen de referentie
  is vóór en na gelijk. Op de hele graaf (228 bepalingen met een datum of bedrag) herkent de stap alleen de vier zinnen
  van 9.5, na twee aanscherpingen op deze set.
- Gemeten met het model (25 nov 2026, `metingen/keten-rekenvoorbeelden-model-2026-11-25/`, één run zonder schrijfpad):
  in 9.5 46 voorstellen (was 67), 22 in een voorbeeldzin (was 42), 12 data afgewezen met `VOORBEELD_WAARDE`, 28
  kandidaten met het kenmerk; de 22 die wegvallen had de jurist alle afgewezen, de 17 geaccordeerde of gecorrigeerde staan
  er alle nog. Op IW 9 lid 1 doet de stap niets.
- Open: een blinde bepaling met rekenvoorbeelden (de graaf heeft buiten Leidraad 9.5 geen enkele); de reviewerzin, want
  in deze run kwam geen twijfelgeval bij de reviewer; en meer runs, als de vraag is of de 5 operatoren die het model nu
  afwees structureel wegvallen.
- De kennis hoort in de detector en zijn tests, niet in de prompt (ADR-001). De promptwijziging is één zin.
- Meting: vóór en na op de vier gedeelde bepalingen (recall op variabele en parameter tegen de referentie, en het
  aandeel afwijzingen), daarna op een blinde bepaling met rekenvoorbeelden uit een andere regeling.

**M3 · De termijn als tijdsaanduiding die een parameter verbijzondert** (bijgesteld 24 nov 2026; de eerdere vorm,
een markering Parameter naast de Tijdsaanduiding, vervalt)
(`references/jas-klassen-referentie.md` §10, `references/markeringslijst.md`, `references/markeren-fragmentgrenzen.md`,
`references/voorbeelden.md`, `relaties.json`; api, werkplek en keten)
- Waarom bijgesteld: de bron zegt het anders dan de eerste versie van M3. Een formulering die zowel tijdsaanduiding als
  parameter of variabele kan zijn, krijgt de specifiekere klasse, de tijdsaanduiding (H2:107). Het boek voegt toe dat de
  analyse vastlegt of zij een parameter of een variabele verbijzondert, en dat zij de relaties van die klasse overneemt
  (M01 h.4 §12, *Relatie met andere klassen*). Een termijn is dus geen markering Parameter, maar één Tijdsaanduiding
  met het subtype *verbijzondert parameter*. De praktijkbibliotheek bedoelt hetzelfde: een vaste waarde, alleen in een
  tijdsklasse. Wat de praktijk met de parameter wil (hem in een regel gebruiken, met een waarde per tijdvak), kan
  daarmee ook: de tijdsaanduiding mag de relaties van een parameter aan (`invoer`, `operand`, `waarde`).
- Toen: alleen het subtype *verbijzondert parameter*, en de catalogus liet een tijdsaanduiding geen relaties van een
  parameter of variabele aangaan; "is kenmerk van" kon alleen van een Variabele komen. Het voorbeeld van art. 9 lid 1
  Iw 1990 maakte van "de dagtekening" een Variabele (acceptatie, 24 nov 2026).
- Nu (gebouwd, PR "Tijdsaanduiding verbijzondert een parameter of een variabele"):
  - het subtype *verbijzondert variabele* naast *verbijzondert parameter*, in de skill, de api (contract en
    `jas_klassen.JAS_SUBTYPEN`), de vocabulaire en de keten; de jurist kiest het in de werkplek (de chips onder de
    klasse op de reviewkaart), en de api weigert een subtype van een andere klasse;
  - de catalogus heeft `verbijzonderingen` (klasse → subtype → de klasse die zij verbijzondert); `toegestaan` laat een
    kant met een verbijzondering ook gelden als die klasse, in api, werkplek en keten;
  - het voorbeeld van art. 9 lid 1 (E05) is een Tijdsaanduiding die een variabele verbijzondert, kenmerk van het
    aanslagbiljet; de termijn (E04) blijft *verbijzondert parameter*.
- De keten zet *verbijzondert variabele* niet zelf: of een datum per geval verschilt, is een oordeel over de context.
  Wat de keten markeert, verandert dus niet, en de tekst tussen de methodemarkers ook niet; daarom geen meting van de
  keten. Een regel (V7) gebruikt de termijn via de tijdsaanduiding.
- Open: de plaatsaanduiding kent volgens het boek dezelfde verbijzondering (M01 h.4 §13); die heeft nog geen subtype.

**M4 · De regels-agent stelt hulpregels voor** (R5, staat op HOLD)
- Toen: `opstellen` maakt per dragende formulering één regel met de voorwaarden als tekst.
- Nu: V9. De volledigheidstoets leest de gaten `voorwaarde_zonder_begrip` en `voorwaarde_herhaald` (V6) en stelt per gat
  een ja/nee-begrip met een regel voor, in code.
- Meting: bijlage A §7 van ADR-018, met de referentie van V1 als maat.

**M5 · De agent-jurist en de agent-gegevensspecialist van het acceptatieteam** (`.claude/agents/`, `docs/acceptatie/`)
- Zij lezen de skill als maatstaf. De wijzigingen van §5a veranderen dus wat zij bij een volgende e2e doen (minder
  afwijzen in een rekenvoorbeeld, meer ja/nee-begrippen). Dat is bedoeld, maar het maakt een volgende e2e niet
  vergelijkbaar met die van 19 en 20 nov 2026. Noteer dat in het logboek van de volgende run.

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

## 7. Besluiten van de eigenaar (24 nov 2026), en de vragen waarop ze antwoord geven

| nr | vraag | besluit | gevolg |
|---|---|---|---|
| 1 | klasse en waardebereik op het begrip | **ja, beide**: P15 wordt bijgesteld | V2 kan beginnen; de alinea over het waardebereik in de skill blijft; M1 krijgt zijn tweede zin zodra V2 er is |
| 2 | operatorbegrippen | **houden zoals nu** | geen wijziging; de praktijk wordt hier niet gevolgd |
| 3 | de termijn als parameter | **de praktijk volgen** | bijgesteld 24 nov 2026 naar de bron: een termijn is een Tijdsaanduiding die een parameter verbijzondert (M3) |
| 4 | hoe ver gaat de ontleding | **een gedeelde set** in het generieke kader (ADR-006) | zo staat het in de skill (§5a); V9 stelt een hulpregel alleen voor als hij daar nog niet bestaat |
| 5a | de naam van een kenmerk | **het object erbij waar verwarring dreigt**, en altijd bij een generiek begrip | zo staat het in de skill; V10 is het signaal daarbij |
| 5b | "bepaal" of "bepalen" | **bepalen …**, zonder "van het" | de vorm van de skill blijft; de namen in Termijnen ("bepalen van het …") wijken daarvan af: nagaan waar "van het" vandaan komt (de naamgeving bij het maken van een regel) en dat generiek rechtzetten, in de bundel van V6. **Uitgevoerd:** geen code maakt die vorm; hij komt uit de import en de invoer van de jurist. De volledigheidstoets meldt hem nu als gat `regelbegrip_bepalen_van`, met de naam "bepalen <uitvoer>" als voorstel. Hernoemen in Termijnen doet de jurist |
| 6 | het regelbegrip | **blijft een begrip, maar apart getoond** | nieuw voorstel V11 hieronder |
| 7 | vervaldag en begindatum invorderbaar | **twee begrippen in Termijnen** | een wijziging in het werkgebied op acceptatie, door de jurist; niet in deze sessie gedaan (het account is gedeeld, en er was alleen leestoegang afgesproken) |
| 8 | de andere trajecten als blinde set | **niet gekozen** | de referentie blijft bij Termijnen; een blinde set voor M2 en M3 komt uit de bestaande blinde families |

**V11 · Het regelbegrip staat bij zijn regel** (frontend, api-leesvorm; S; geen meting). De begrippenlijst van een
werkgebied en het overzicht *Begrippen* tonen een begrip met de rol regelbegrip niet tussen de gewone begrippen, maar
bij de regel (op de regelkaart en in de tab *Afleidingsregels*), met een filter om ze toch te zien. Het begrip zelf, zijn
grondslag en de NL-SBB-projectie veranderen niet. De telling van begrippen noemt ze apart. Hoort in de bundel van V2–V4.

**Bijgestelde volgorde.** (1) V1 met de nulmeting; (2) V2, V3, V4 en V11 in één bundel; (3) V6 met de naam zonder
"van het"; (4) M3 (gebouwd 24 nov 2026, zonder wijziging aan wat de keten markeert, dus zonder meting van de keten);
(5) V7; (6) V8 met M2; (7) M1 na V2; (8) V9, V10 en M4 als R5 van start gaat.

De vragen zoals ze gesteld zijn:


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

- ~~**De originelen van de methode** (het boek, de Handleiding, de Leidraad) zijn voor dit plan niet opnieuw gelezen.~~
  Nagegaan op 25 nov 2026: zie §10.
- ~~**Waarom de markeringen in Leidraad 9.5 zijn afgewezen.**~~ Nagegaan op 24 nov 2026 (V8): 42 van de 50 met de reden
  "Rekenvoorbeeld, niet de regel", alle in de voorbeeldzinnen; zie V8 en `metingen/keten-rekenvoorbeelden-2026-11-24/`.
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

## 10. Naast de bronnen van de methode (25 nov 2026)

Gelezen, lokaal en in eigen woorden: de Handleiding (M02) §3.5 (activiteit 3), §3.6 (activiteit 4), §3.7 (activiteit 5)
en §3.8 (het kennismodel); de Leidraad (M03) §2.4 (de deelactiviteiten per hoofdactiviteit); het boek (M01) h.3 stap 3
en 4 en h.4 de klassen Voorwaarde, Afleidingsregel en Variabele. Daarnaast de skill en de code op master (`d10beadb`).
De Handleiding is de actuele versie van h.3 van het boek. Waar ze verschillen, volgt dit plan de Handleiding.

### 10.1 Wat de bronnen bevestigen

Hier hoeft niets te gebeuren. De bronnen zeggen hetzelfde als het plan of de skill, of het staat er al.

| onderwerp | de bron | stand |
|---|---|---|
| "bepalen <uitvoer>" zonder lidwoord | M02 §3.5.2a: de naam van een afleidingsregel of rechtsfeit begint met een werkwoord, en een naam begint nooit met een lidwoord of voorzetsel | besluit 5b en het gat `regelbegrip_bepalen_van` (#1852) |
| het object of de wet in de naam | M02 §3.5.2a: voeg de context toe als hetzelfde woord in verschillende wetten iets anders aanduidt | besluit 5a; V10 |
| ja/nee en waardebereik | M01 h.4 *Variabele*: een waarde is een getal of datum, tekst, een opsomming of een booleaanse waarde; M02 §3.5.2a noemt de soort als eigenschap | V2 gebouwd; M1 wacht op een meting |
| klasse op het begrip | M02 §3.8.2a: de begrippenlijst van het kennismodel noemt per begrip de klasse | V2 gebouwd |
| ontleding in hulpregels | M01 h.4 *Afleidingshiërarchie*; het uitgewerkte voorbeeld in M02 §3.5.5c is een keten van regels die elkaars uitvoer gebruiken | §5a; V9 op HOLD |
| de voorbeeldreeks per regel | M02 §3.6.2b en M03 ad 4b: per regel elk in- en uitvoerbegrip een waarde, om te toetsen of de uitkomst juridisch juist en volledig is | V3 gebouwd |
| de regeltaal voor voorwaarden | M02 §3.5.5c: "aan alle volgende voorwaarden" of "ten minste één", ook genest, en "moet berekend worden als" | staat in `api/app/regeltekst.py` |
| een operator krijgt een begrip | M02 §3.5.2b: "verminderd met" wordt het begrip "min" | besluit 2 (houden) |
| interpretatie en ontbrekend uitvoeringsbeleid | M02 §3.5.3 en §3.7; M03 ad 5 | open punten, met een bronsoort per lezing |
| een betekeniswijziging geeft een nieuw begrip | M02 §3.5.2a | de opvolger (spoor M); de geldigheid ontbreekt, zie B3 |

### 10.2 Wat er nog ontbreekt

De punten staan in de volgorde waarin ze het meeste opleveren voor de minste moeite. Ze zijn generiek: geen enkel
punt kent een bepaling of begrip uit Termijnen. Geen punt raakt de tekst tussen de methodemarkers, dus geen punt vraagt
een meting. B2 vraagt er wel een als de begrippenketen de naamregels ook gaat toepassen.

**B1 · Twee verouderde zinnen in de skill** (`references/begrippen.md`; S; geen meting)
- `references/begrippen.md` (§*Begrippen*) zegt dat je geen begripstype of JAS-duiding voorstelt. Bij het waardebereik
  zegt het dat het platform er geen veld voor heeft en dat het in de toelichting moet. Sinds V2 (#1833) heeft het begrip
  een afgeleide klasse met een keuze van de analist (`klasse_keuze`), en een veld `waardebereik`.
- Oplossing:
  - zeg dat de klasse uit de markeringen komt en dat de analist haar met een reden kan verleggen;
  - zeg dat het waardebereik in zijn eigen veld staat.
- Het bestand staat buiten de methodemarkers, maar is een build-input: het bronpakket wordt opnieuw gegenereerd.

**B2 · De naamregels van de methode als signaal** (api `begrip_store.eenduidigheid`; S; geen meting)
- Probleem: M02 §3.5.2a geeft vuistregels voor de naam en de definitie. De skill noemt er een deel van. De code toetst
  alleen de kringdefinitie, de rekenregel in de definitie, de homoniem en de parameterwaarde, en bij een regelbegrip de
  vorm "bepalen van het".
- Oplossing: een aandachtspunt, geen poort, voor wat mechanisch te zien is:
  - de naam begint met een lidwoord of voorzetsel;
  - de naam begint met een hoofdletter;
  - er staat een Romeins cijfer in de naam;
  - er staat een ontkenning in de naam ("niet", "geen");
  - het woord "voor" staat in de naam;
  - de definitie eindigt op een punt.
- De regels die zich niet mechanisch laten toetsen, komen in de skill, in §*De naam*:
  - het enkelvoud, behalve waar het meervoud iets anders betekent;
  - een afkorting in de naam staat voluit in de definitie;
  - gebruik in de naam begrippen die er al zijn.
- `regelbegrip_bepalen_van` (#1852) is één geval van de eerste regel. Hij gaat in dezelfde toets op, of blijft het gat
  bij de regel met de naam als voorstel.
- Eerst nagaan: hoe schrijft Lex nu definities (met of zonder slotpunt), en wat schrijft NL-SBB voor? Botsen die met
  M02, dan beslist de eigenaar. Laat de begrippenketen de regels ook toepassen bij het voorstellen, dan is dat een
  wijziging van gedrag, en dus een meting (ADR-010).

**B3 · Ontbrekende waarden in een voorbeeldreeks** (api `regel_store.past_in`; S; geen meting)
- Probleem: in M01 stap 4a staan in de voorbeeldreeks met opzet kolommen met een onbekende invoer. Zo toets je of de
  regels compleet zijn. `past_in` geeft bij "onbekend" in een datumveld `False`, dus een onterecht signaal.
- Oplossing: "onbekend", "leeg" en "n.v.t." passen in elk waardebereik (`None`), met een test. Neem in de skill
  (`references/afleidingsregels.md`, *Toetsen met een voorbeeldtabel*) op dat een kolom met een onbekende invoer erbij
  hoort.

**B4 · De controlemiddelen van activiteit 4 als signaal** (api, inventaris; S–M; geen meting)
- M02 §3.6.1 noemt vaste controles. Twee ervan raken activiteit 3, en geen van beide wordt nu gemeld.
  - **Elk begrip heeft een definitie en minstens één voorbeeld.** De poort vraagt nu een definitie en een toelichting,
    geen voorbeeld. Voorstel: een aandachtspunt "nog geen voorbeeld". Of het een voorwaarde voor accorderen wordt, is een
    vraag aan de eigenaar, want het verandert de werkwijze van het acceptatieteam (M5).
  - **Bij elke variabele staat van welk object zij een kenmerk is.** De relatie `kenmerk` bestaat in de catalogus, maar
    niets meldt een variabele zonder die relatie. Voorstel: een signaal in de inventaris bij een Variabele zonder
    actieve relatie `kenmerk`. Dat geldt ook voor een Tijdsaanduiding die een variabele verbijzondert (M3).
- Het tweede punt geeft V10 houvast: het object volgt dan uit de relatie, niet uit de naam.

**B5 · Het voorbeeld bij een begrip als stelling met toelichting** (api `begrip_contracts.Voorbeeld`, kaart, skill; S;
geen meting)
- Probleem: in M03 ad 3a en het uitgewerkte voorbeeld in M02 §3.5.5b is elk voorbeeld bij een begrip een stelling. Ze
  is waar of niet waar en heeft een toelichting die zegt waarom. Er zijn ook met opzet onware stellingen bij. Lex heeft
  de tekst en een oordeel (`wel`, `niet`, `onzeker`), maar geen toelichting. De skill (§*De vorm van een voorbeeld*)
  noemt de stelling niet.
- Oplossing:
  - een optioneel veld `toelichting` bij het voorbeeld, met dezelfde vorm als bij een regelvoorbeeld;
  - in de skill één alinea: een voorbeeld bij een begrip is een stelling die waar of niet waar is, en de toelichting
    zegt waarom. M03 maakt dat onderscheid zelf: zo'n stelling toetst de naam en de definitie, en de voorbeeldreeks
    toetst de regel.
- Stelt de begrippen-agent de voorbeelden voor, dan valt de toelichting onder de meting van M1.
- **Eerst een besluit van de eigenaar.** Spoor I1 (#753, 27 okt 2026) heeft de toelichting bij een voorbeeld bewust
  geschrapt, om het model gelijk te trekken met NL-SBB. Het waarom staat sindsdien in de motivatie van het voorstel van
  Lex, en niet bij het voorbeeld zelf. Dit punt draait dat terug, zoals V2 dat met P15 deed. **Besluit van de eigenaar
  (25 nov 2026): de toelichting komt terug.** Gebouwd in dezelfde PR als B1 en B3.

**B6 · De subklasse op het begrip** (api `klasse_van`, kaart; S; geen meting)
- Probleem: volgens M01 stap 3a en M02 §3.5.2a horen bij de eigenschappen van een begrip de klasse en haar verdieping,
  zoals de soort rechtsbetrekking of rechtsfeit. V2 leidt de klasse af. Het subtype staat wel op de markering
  (`JAS_SUBTYPEN`), maar niet op het begrip.
- Oplossing: leid het subtype af zoals de klasse, uit de dragende markeringen, en toon het naast de klasse. Geen nieuw
  invoerveld: wijkt het af, dan kiest de analist het op de markering.

**B7 · Primaire bron en interpretatiebron** (skill `references/werkgebied.md` en `references/begrippen.md`; S; geen
meting)
- Probleem: volgens M03 §2.4 en M02 §3.7 zijn de parlementaire geschiedenis en de jurisprudentie geen primaire bron
  maar een interpretatiebron. Ze worden pas primair als de wet of een beleidsregel ze overneemt. Afwijkende
  jurisprudentie neem je niet over zonder een standpunt van het verantwoordelijke ministerie, en jurisprudentie die de
  gangbare lezing steunt, noem je in de toelichting (M02 §3.5.4). De skill kent de rollen *analyseren* en *context*,
  maar zegt dit niet. De open punten kennen de bronsoorten wel.
- Oplossing:
  - één alinea in `werkgebied.md` bij de rol van een bron: een interpretatiebron heeft de rol *context*;
  - één alinea in `begrippen.md`: jurisprudentie en wetsgeschiedenis onderbouwen een lezing in de toelichting of in
    een open punt, maar dragen geen begrip.
- Het gat `rust_op_contextbron` doet dit al voor een regel.

**B8 · De geldigheid van een begrip** (api, projectie; M; besluit van de eigenaar)
- Probleem: volgens M01 stap 3a en M02 §3.5.2a horen bij een begrip een ingangsdatum en, als die bekend is, een
  einddatum. Wijzigt de betekenis, dan komt er een nieuw begrip, en de data op het oude en het nieuwe begrip leggen
  vast per wanneer. Lex legt bij een opvolger vast wanneer iemand het oude begrip verving. Dat is de datum van de
  registratie, niet de juridische datum.
- Voorstel: optionele velden `geldig_vanaf` en `geldig_tot` op het begrip. De opvolger stelt de ingangsdatum voor uit
  de versie van de dragende passage, en het oude begrip krijgt de dag ervoor als einddatum. De velden gaan buiten de
  kern van NL-SBB mee, net als het waardebereik (ADR-003).
- Ook hier heeft spoor I1 (#753) een veld `geldigheid` geschrapt, samen met de JAS-duiding en de eigenschappen. V2 haalde
  de klasse terug; dit punt zou de geldigheid terughalen.
- Vraag aan de eigenaar: een eigen veld, of afleiden uit de versies van de bronnen waarop het begrip rust? Het tweede
  is minder werk voor de analist, maar mist een wijziging die uit jurisprudentie komt.

**B9 · Een signaal aan de wetgever** (api `open_punt_contracts`; S; besluit van de eigenaar)
- Probleem: volgens M02 §3.5.2a signaleer je synoniemen, homoniemen en inconsistenties tussen termen bij de
  wetgevingsafdeling, zodat de wetgever ze bij een volgende wijziging kan oplossen. Lex kan bij een open punt alleen
  *gesignaleerd* zeggen als het om ontbrekend uitvoeringsbeleid gaat.
- Voorstel: *gesignaleerd* ook bij een interpretatiekeuze, met de geadresseerde (beleid of wetgever) erbij. Een nieuwe
  soort is niet nodig.

### 10.3 Wat buiten deze methode valt

- **Juridische scenario's** (activiteit 1c, 3c en 4a in M02 en M03): de begintoestand, het rechtsfeit, de
  rechtsgevolgen en de eindtoestand per gebeurtenis. Dat is de skill *wetsuitvoering* (JRM), en de methodes blijven
  gescheiden (`plan-methodes-scheiden.md`). Met een wetsanalyse verbonden is alleen de verwijzing van een scenario naar
  het dossier.
- **Het kennismodel** (activiteit 6): het gegevens-, regel- en procesmodel. De begrippenlijst die M02 §3.8.2a noemt,
  is met V2 en B6 compleet: naam, definitie, de formulering in de primaire bron, de klasse, de voorbeelden, de
  eigenschappen, de relaties en de interpretatiebronnen. De rest valt onder RegelSpraak, en dat is nog geen
  functionaliteit.
- **Het diagram per centrale klasse** en de volgorde waarin je gebeurtenissen afwerkt (M02 §3.4, M03 ad 2c): dat zit in
  activiteit 2 en het diagram (`api/app/diagram.py`), niet in dit plan.

### 10.4 Volgorde

1. B1, B3 en B5, in één bundel: kleine correcties in de skill en het model, zonder gedragsverandering. **Gebouwd** (PR
   #1861, branch `claude/bundel-methodebronnen-1`); B5 na het besluit van de eigenaar.
2. B2, B4 en B6, in één bundel met signalen. Eerst de toets uit B2 (slotpunt, NL-SBB).
3. B7, met B1, als de skill toch wordt gewijzigd.
4. B8 en B9, na het besluit van de eigenaar.

B2 en B6 raken `api/app/begrip_store.py`, en B3 raakt `api/app/regel_store.py`. Er werkt één schrijver tegelijk aan
een bestand.
